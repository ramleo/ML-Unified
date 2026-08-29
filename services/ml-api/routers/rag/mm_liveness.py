"""Face liveness / anti-spoofing detection — distinguishes a real face held
up to a camera from a spoofed presentation of one (a printed photo, a phone/
screen replay). This is the same category of check that gates biometric
face-unlock and identity-verification (KYC) flows against someone holding up
a photo of a person instead of actually being them.

Model: MiniFASNetV2-SE (600KB, quantized ONNX, 128x128 RGB input, binary
real/spoof classifier), from minivision-ai/Silent-Face-Anti-Spoofing
(Apache-2.0, 2020) via its community ONNX port facenox/face-antispoof-onnx
(Apache-2.0, 2025) — LICENSE file checked directly in both repos before
adopting, not just trusted from a badge; the trained weights ship under the
SAME Apache-2.0 license as the code in both repos, unlike the Ultralytics
YOLO situation where the weights turned out to carry a separate AGPL claim
despite permissively-licensed code. Reported 98.2% accuracy / 0.9984 AUC is
measured only on CelebA-Spoof, the dataset it was trained and tested on —
not independently verified here beyond confirming the pipeline mechanics
work correctly (a real face crop scores clearly "real" with a strong logit
margin).

Real, disclosed limitation, not a hedge: academic liveness-detection
literature is consistent that cross-dataset generalization is genuinely
poor — a naive CNN trained on one spoof-attack dataset and tested on a
different one (e.g. trained on CASIA-FASD, tested on Replay-Attack) scores
close to a coin flip (~45-48% error rate); even sophisticated cross-domain
methods only get this down to ~20-30% error, still far worse than same-
dataset performance. This model has NOT been tested against this specific
codebase's own camera/lighting/spoof-attempt conditions — expect it to work
well in controlled conditions and be genuinely unreliable at the edges
(a phone-screen replay behaves very differently to these models than a flat
printed photo), not a bulletproof verdict. Every result is labeled with this
caveat rather than presented as a certainty.

Reuses the existing OIV7 face detector (mm_objects.py's detect_objects) to
locate the face before cropping — no separate face-detection model needed,
same "Human face" class already powering "Detect faces" elsewhere."""
from __future__ import annotations

import base64
import io
import logging
import os
import threading

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel

from routers.rag.mm_objects import detect_objects
from security.file_gate import scan_upload_bytes

logger = logging.getLogger(__name__)

router = APIRouter()

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "face-liveness.onnx")
_INPUT_SIZE = 128
_CROP_EXPANSION = 1.5  # match the ONNX port's own preprocessing — a tight face bbox alone loses context the model was trained on
_FACE_LABELS = {"Human face"}

_session = None
_session_lock = threading.Lock()


def _get_session():
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                import onnxruntime as ort
                _session = ort.InferenceSession(_MODEL_PATH, providers=["CPUExecutionProvider"])
    return _session


def _crop_face(img_bgr: np.ndarray, bbox_norm: list[float]) -> np.ndarray:
    """Expands the detected face bbox by _CROP_EXPANSION and reflection-pads
    at the edges — mirrors facenox/face-antispoof-onnx's own crop() exactly,
    since the model was trained on crops shaped this way, not a tight bbox."""
    h, w = img_bgr.shape[:2]
    bx, by, bw, bh = bbox_norm
    x0, y0 = bx * w, by * h
    x1, y1 = x0 + bw * w, y0 + bh * h
    box_w, box_h = x1 - x0, y1 - y0
    max_dim = max(box_w, box_h)
    cx, cy = x0 + box_w / 2, y0 + box_h / 2

    crop_size = int(max_dim * _CROP_EXPANSION)
    cx0 = int(cx - crop_size / 2)
    cy0 = int(cy - crop_size / 2)

    x_start, y_start = max(0, cx0), max(0, cy0)
    x_end, y_end = min(w, cx0 + crop_size), min(h, cy0 + crop_size)
    top_pad, left_pad = max(0, -cy0), max(0, -cx0)
    bottom_pad = max(0, (cy0 + crop_size) - h)
    right_pad = max(0, (cx0 + crop_size) - w)

    crop = img_bgr[y_start:y_end, x_start:x_end] if x_end > x_start and y_end > y_start else np.zeros((0, 0, 3), dtype=img_bgr.dtype)
    return cv2.copyMakeBorder(crop, top_pad, bottom_pad, left_pad, right_pad, cv2.BORDER_REFLECT_101)


def _preprocess(face_crop: np.ndarray) -> np.ndarray:
    """Letterbox-resize to 128x128 + normalize to [0,1] + CHW — the exact
    steps facenox/face-antispoof-onnx's preprocess() uses, replicated here
    rather than imported since that repo isn't a runtime dependency."""
    old_h, old_w = face_crop.shape[:2]
    ratio = _INPUT_SIZE / max(old_h, old_w)
    new_h, new_w = int(old_h * ratio), int(old_w * ratio)
    interp = cv2.INTER_LANCZOS4 if ratio > 1.0 else cv2.INTER_AREA
    resized = cv2.resize(face_crop, (new_w, new_h), interpolation=interp)

    pad_h, pad_w = _INPUT_SIZE - new_h, _INPUT_SIZE - new_w
    top, bottom = pad_h // 2, pad_h - pad_h // 2
    left, right = pad_w // 2, pad_w - pad_w // 2
    padded = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_REFLECT_101)

    arr = padded.transpose(2, 0, 1).astype(np.float32) / 255.0
    return arr[None, ...]


def check_liveness(b64: str) -> dict:
    """Returns {"found_face": bool, "real_score": float|None, "error": str|None}.
    `real_score` is a single 0-1 number (sigmoid of the model's real-minus-
    spoof logit gap): 1.0 = confidently real, 0.0 = confidently spoof, 0.5 =
    the model has no real signal either way. Deliberately NOT a pre-decided
    bool+confidence split — real-world testing (a live webcam face scored
    "spoofed" at only 52% under dim/low-contrast conditions, a near coin
    flip) showed the model's confidence collapses toward 0.5 under exactly
    the lighting a webcam produces, and a single low-confidence frame isn't
    reliable enough to commit to a verdict on its own. Returning the raw
    signed score lets the caller average several frames before deciding —
    see FaceLivenessRunner.tsx's multi-frame capture, which is the actual
    fix; a single frame's verdict is not trustworthy near 0.5. `real_score`
    is None when no face was confidently detected — never guesses on an
    image with nothing to check."""
    try:
        raw = base64.b64decode(b64)
        scan_upload_bytes(raw, path="/rag/mm-liveness")
        pil_img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:
        logger.warning("Liveness check: could not decode image: %s", exc)
        return {"found_face": False, "real_score": None, "error": "could not decode image"}

    objects, _ = detect_objects(b64)
    faces = [o for o in objects if o["label"] in _FACE_LABELS]
    if not faces:
        return {"found_face": False, "real_score": None, "error": None}

    best_face = max(faces, key=lambda f: f["confidence"])
    img_bgr = cv2.cvtColor(np.asarray(pil_img), cv2.COLOR_RGB2BGR)

    try:
        face_crop = _crop_face(img_bgr, best_face["bbox"])
        if face_crop.size == 0:
            return {"found_face": True, "real_score": None, "error": "face crop failed"}
        batch = _preprocess(face_crop)
        session = _get_session()
        logits = session.run(None, {session.get_inputs()[0].name: batch})[0][0]
        real_logit, spoof_logit = float(logits[0]), float(logits[1])
        real_score = float(1 / (1 + np.exp(-(real_logit - spoof_logit))))
        return {"found_face": True, "real_score": round(real_score, 4), "error": None}
    except Exception as exc:
        logger.warning("Liveness inference failed: %s", exc)
        return {"found_face": True, "real_score": None, "error": "inference failed"}


class LivenessRequest(BaseModel):
    image: str  # b64 image, any common format


@router.post("/mm-liveness")
def liveness_endpoint(body: LivenessRequest):
    if not body.image.strip():
        raise HTTPException(status_code=400, detail="image is required")
    return check_liveness(body.image)
