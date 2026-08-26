"""
Text-Prompted Video Object Tracking & Masking — pending-list #46.

Originally scoped around Meta's SAM3 ("SAM3 magic rotoscope"). Researched
before writing any code and found a real blocker: SAM3's checkpoints are
gated behind a Meta access request under a non-standard custom license,
with no clean pip package. This uses "Grounded-SAM" instead — a
well-established real combined technique: Grounding DINO (IDEA Research,
Apache 2.0, ungated) finds the described object once on the first frame,
then SAM2 (Meta, Apache 2.0, ungated) tracks and masks it through every
subsequent frame using its video memory mechanism. Both are inference-only
forward passes (no gradient-based per-scene optimization), so — unlike 3D
Gaussian Splatting (#45, rejected: needs a CUDA rasterizer through
thousands of optimization steps) — this genuinely runs on this Space's
confirmed cpu-basic hardware, just slower than a GPU would give.

Deliberately NOT done, disclosed rather than glossed over:
- No exported video file — the response is a sampled-frame preview (a
  bounded number of JPEG frames with the mask overlaid), not a
  full-resolution/full-framerate re-encoded video. Avoids a server-side
  video-encoding step entirely.
- Clips are capped short and downsampled in both fps and resolution
  before processing — CPU inference latency, not a bug.
- Grounding DINO's real PyPI package (`groundingdino-py`) declares an
  unpinned, non-headless `opencv-python` dependency that would collide
  with this project's `opencv-python-headless` (and in a slim Docker
  image, non-headless opencv-python typically fails to import at all —
  missing libGL.so.1). Verified locally: Grounding DINO's actual
  inference code (`load_model`/`predict`) only needs `cv2.imread`/
  `cv2.cvtColor`-level calls, which `opencv-python-headless` already
  provides — so `groundingdino-py` is installed with `--no-deps` and its
  real transitive deps are pinned explicitly, deliberately excluding
  opencv-python. See requirements-base.txt's comment for the full list.
"""

import base64
import logging
import os
import shutil
import tempfile
import threading

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from routers.rag.mm_video import prepare_video

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_DURATION_S = 6.0
_TARGET_FPS = 4.0
_MAX_FRAMES = 20
_MAX_DIM = 480  # long-edge resize before processing — CPU-latency bound
_BOX_THRESHOLD = 0.35
_TEXT_THRESHOLD = 0.25
_MASK_COLOR = (255, 0, 128)

_GROUNDING_MODEL = None
_SAM2_PREDICTOR = None
_lock = threading.Lock()


def _ensure_grounding_loaded():
    global _GROUNDING_MODEL
    if _GROUNDING_MODEL is not None:
        return _GROUNDING_MODEL
    with _lock:
        if _GROUNDING_MODEL is not None:
            return _GROUNDING_MODEL
        from huggingface_hub import hf_hub_download
        from groundingdino.util.inference import load_model

        logger.info("Loading Grounding DINO (SwinT, ~694MB) — first use only …")
        config_path = hf_hub_download(repo_id="ShilongLiu/GroundingDINO", filename="GroundingDINO_SwinT_OGC.cfg.py")
        ckpt_path = hf_hub_download(repo_id="ShilongLiu/GroundingDINO", filename="groundingdino_swint_ogc.pth")
        _GROUNDING_MODEL = load_model(config_path, ckpt_path, device="cpu")
        return _GROUNDING_MODEL


def _ensure_sam2_loaded():
    global _SAM2_PREDICTOR
    if _SAM2_PREDICTOR is not None:
        return _SAM2_PREDICTOR
    with _lock:
        if _SAM2_PREDICTOR is not None:
            return _SAM2_PREDICTOR
        from sam2.sam2_video_predictor import SAM2VideoPredictor

        logger.info("Loading SAM2 (hiera-tiny, ~150MB) — first use only …")
        _SAM2_PREDICTOR = SAM2VideoPredictor.from_pretrained("facebook/sam2.1-hiera-tiny", device="cpu")
        return _SAM2_PREDICTOR


def _resize_long_edge(frame: np.ndarray, max_dim: int) -> np.ndarray:
    h, w = frame.shape[:2]
    scale = max_dim / max(h, w)
    if scale >= 1.0:
        return frame
    return cv2.resize(frame, (int(w * scale), int(h * scale)))


def _extract_sampled_frames(cap, duration_s: float, frames_dir: str) -> int:
    """Seeks + resizes frames into frames_dir as 00000.jpg, 00001.jpg, ...
    (SAM2's video init_state() expects a directory of JPEGs). Returns the
    number of frames actually written."""
    usable_duration = min(duration_s, _MAX_DURATION_S)
    interval = 1.0 / _TARGET_FPS
    n_frames = min(_MAX_FRAMES, int(usable_duration / interval) + 1)

    written = 0
    for i in range(n_frames):
        t = i * interval
        if t > usable_duration:
            break
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            break
        frame = _resize_long_edge(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), _MAX_DIM)
        Image.fromarray(frame).save(os.path.join(frames_dir, f"{written:05d}.jpg"), quality=85)
        written += 1
    return written


def _ground_first_frame(frame0_path: str, text_prompt: str) -> tuple[float, float, float, float] | None:
    """One Grounding DINO forward pass on frame 0 — the video tracker below
    never needs to call it again. Returns an absolute-pixel xyxy box for
    the highest-confidence match, or None if nothing cleared the threshold."""
    from groundingdino.util.inference import load_image, predict

    model = _ensure_grounding_loaded()
    image_source, image = load_image(frame0_path)
    boxes, logits, _phrases = predict(
        model=model, image=image, caption=text_prompt,
        box_threshold=_BOX_THRESHOLD, text_threshold=_TEXT_THRESHOLD, device="cpu",
    )
    if len(boxes) == 0:
        return None
    best = int(logits.argmax())
    h, w = image_source.shape[:2]
    cx, cy, bw, bh = boxes[best].tolist()
    x0, y0 = (cx - bw / 2) * w, (cy - bh / 2) * h
    x1, y1 = (cx + bw / 2) * w, (cy + bh / 2) * h
    return (x0, y0, x1, y1)


def _track_and_mask(frames_dir: str, box: tuple[float, float, float, float]) -> dict[int, np.ndarray]:
    import torch

    predictor = _ensure_sam2_loaded()
    masks: dict[int, np.ndarray] = {}
    with torch.inference_mode():
        state = predictor.init_state(video_path=frames_dir)
        predictor.add_new_points_or_box(
            inference_state=state, frame_idx=0, obj_id=1,
            box=np.array(box, dtype=np.float32),
        )
        for frame_idx, _obj_ids, mask_logits in predictor.propagate_in_video(state):
            masks[frame_idx] = (mask_logits[0] > 0).cpu().numpy().squeeze(0)
    return masks


def _overlay_and_encode(frame_path: str, mask: np.ndarray | None) -> str:
    frame = np.array(Image.open(frame_path).convert("RGB"))
    if mask is not None and mask.any():
        color = np.array(_MASK_COLOR, dtype=np.float32)
        frame = frame.astype(np.float32)
        frame[mask] = frame[mask] * 0.4 + color * 0.6
        frame = frame.astype(np.uint8)
    buf = cv2.imencode(".jpg", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])[1]
    return base64.b64encode(buf).decode()


@router.post("/mm-rotoscope/track")
async def track_object(video: UploadFile = File(...), text_prompt: str = Form(...)):
    text_prompt = text_prompt.strip()
    if not text_prompt:
        raise HTTPException(status_code=400, detail="Type a short description of the object to track.")

    file_bytes = await video.read()
    try:
        cap, tmp_path, _n_frames, duration_s = prepare_video(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    frames_dir = tempfile.mkdtemp(prefix="rotoscope_")
    try:
        written = _extract_sampled_frames(cap, duration_s, frames_dir)
        cap.release()
        os.unlink(tmp_path)
        if written < 2:
            raise HTTPException(status_code=400, detail="Could not extract enough frames from this video.")

        frame0_path = os.path.join(frames_dir, "00000.jpg")
        box = _ground_first_frame(frame0_path, text_prompt)
        if box is None:
            raise HTTPException(
                status_code=422,
                detail=f"Couldn't find \"{text_prompt}\" in the first frame — try a clearer description, "
                       f"or trim the clip so the object is visible from the start.",
            )

        masks = _track_and_mask(frames_dir, box)

        frames_out = []
        for i in range(written):
            path = os.path.join(frames_dir, f"{i:05d}.jpg")
            frames_out.append(_overlay_and_encode(path, masks.get(i)))

        warnings = []
        if duration_s > _MAX_DURATION_S:
            warnings.append(f"Clip trimmed to the first {_MAX_DURATION_S:.0f}s — longer clips aren't processed.")

        return {"frames": frames_out, "fps_used": _TARGET_FPS, "frame_count": len(frames_out), "warnings": warnings}
    finally:
        shutil.rmtree(frames_dir, ignore_errors=True)
