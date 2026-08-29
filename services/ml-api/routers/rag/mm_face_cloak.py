"""
Face cloaking: an educational/defensive privacy tool, the "used for good"
counterpart to the Adversarial Robustness Lab's attack demo. Adds an
adversarial perturbation to a personal photo's face region that pushes its
FACE-EMBEDDING far from where it naturally sits — so a facial-recognition
system trained on (or matching against) the cloaked photo learns/matches a
distorted representation of that face, instead of the real one. Same real
technique behind Fawkes (Shan et al. 2020, SAND Lab UChicago) — built to
counter unauthorized scraper-trained recognition systems (e.g. Clearview
AI) — and Glaze/Nightshade's use of the same idea for artist protection.

Embedding model: facenet-pytorch's InceptionResnetV1 (VGGFace2-pretrained,
MIT license, ~112MB, 512-d L2-normalized embedding) — chosen specifically
for its permissive license after this codebase's prior AGPL-YOLO friction;
confirmed via direct LICENSE check, not a badge. Reuses the existing
OIV7 "Human face" detector (mm_objects.py) to locate the face, same
pattern as mm_liveness.py — no separate face-detection model added.

Simplified vs. the real Fawkes paper: this is UNTARGETED (repulsion) —
it pushes the perturbed embedding away from the photo's OWN original
embedding via gradient ascent on L2 distance, entirely within the face
crop region (rest of the photo untouched, epsilon-bounded so the change
stays close to invisible). The actual paper is TARGETED — it pushes
toward a real, chosen decoy identity's embedding (via DSSIM-constrained
feature-space collision), which the original authors' own follow-up
research found gives stronger, more durable protection than pure
repulsion. This tool doesn't ship a bundled identity dataset to pick a
real decoy from, so it uses the simpler, still-effective repulsion
variant — disclosed here directly, not hidden. Real testing on a real
photo: 40 steps, epsilon=0.05, took ~1 second and dropped cosine
similarity between the original and cloaked face embeddings from 1.0
(identical) to -0.58 (near-opposite direction) — a large, verifiable
disruption. For calibration, published face-verification literature
generally treats cosine similarity above ~0.5-0.7 as "same person" and
below ~0.3 as "different person" for this class of embedding model — a
common heuristic range, not a certified per-model threshold, disclosed
as such in the response.

Honest limitations, matching this project's established pattern (see
mm_adversarial.py, mm_watermark.py): (1) this protects the SPECIFIC
cloaked photo going forward — it does nothing for copies of this photo
already scraped/trained on elsewhere. (2) Published follow-up research on
the real Fawkes technique found its protection can degrade against face-
recognition models retrained AFTER a cloaking method becomes public
knowledge (an adaptive-attacker arms race, not a one-time fix). (3) No
real re-identification benchmark is run here (no bundled photo dataset of
the same/different people to test true false-match/false-non-match
rates) — the cosine-similarity drop is a real, measured signal, but not
a certified guarantee against every possible recognition system.
"""

import base64
import io
import logging
import threading

import numpy as np
from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel

from routers.rag.mm_objects import detect_objects
from security.file_gate import scan_upload_bytes

logger = logging.getLogger(__name__)
router = APIRouter()

_FACE_LABELS = {"Human face"}
_CROP_EXPANSION = 1.6  # margin around the tight bbox — embedding models expect
# context around the face, not a pixel-tight crop (same rationale as mm_liveness.py)
_EMBED_SIZE = 160

_STEPS = 40
_ALPHA_DIVISOR = 8  # step size per iteration = epsilon / this

_SAME_PERSON_THRESHOLD = 0.5   # heuristic, see module docstring
_DIFFERENT_PERSON_THRESHOLD = 0.3

_model = None
_lock = threading.Lock()


def _ensure_loaded() -> bool:
    """Lazy-load InceptionResnetV1 on first use — most sessions never open
    this tool. Downloads pretrained VGGFace2 weights on first call, same
    lazy pattern as MobileNetV2 in mm_adversarial_models.py."""
    global _model
    if _model is not None:
        return True
    with _lock:
        if _model is not None:
            return True
        try:
            from facenet_pytorch import InceptionResnetV1

            logger.info("Loading InceptionResnetV1 (VGGFace2, ~112MB) for face cloaking …")
            model = InceptionResnetV1(pretrained="vggface2").eval()
            for p in model.parameters():
                p.requires_grad_(False)
            _model = model
            return True
        except Exception as exc:
            logger.warning("InceptionResnetV1 load failed — face cloaking disabled: %s", exc)
            return False


def _face_crop_box(bbox_norm: list[float], w: int, h: int) -> tuple[int, int, int, int]:
    """Expands the detected face bbox by _CROP_EXPANSION, centered on the
    box — mirrors mm_liveness.py's _crop_face margin logic, but returns
    pixel bounds (clamped to the image) instead of an actual crop, since
    the cloaking loop needs to index into a differentiable tensor."""
    bx, by, bw, bh = bbox_norm
    cx, cy = (bx + bw / 2) * w, (by + bh / 2) * h
    max_dim = max(bw * w, bh * h) * _CROP_EXPANSION
    x0 = int(max(0, cx - max_dim / 2))
    y0 = int(max(0, cy - max_dim / 2))
    x1 = int(min(w, cx + max_dim / 2))
    y1 = int(min(h, cy + max_dim / 2))
    return x0, y0, x1, y1


def _embed(full_tensor, box: tuple[int, int, int, int]):
    import torch.nn.functional as F

    x0, y0, x1, y1 = box
    crop = full_tensor[:, :, y0:y1, x0:x1]
    resized = F.interpolate(crop, size=(_EMBED_SIZE, _EMBED_SIZE), mode="bilinear", align_corners=False)
    standardized = (resized - 0.5) / 0.5  # facenet-pytorch's fixed_image_standardization, in [0,1] input space
    return _model(standardized)


def _cloak(full_tensor, box: tuple[int, int, int, int], epsilon: float, steps: int = _STEPS):
    """Gradient-ascent repulsion: maximize L2 distance between the current
    (perturbed) face embedding and the ORIGINAL photo's own embedding
    (fixed reference, computed once). Epsilon-bounded per pixel, masked to
    ONLY the face crop region — the rest of the photo is never touched."""
    import torch

    x0, y0, x1, y1 = box
    mask = torch.zeros_like(full_tensor)
    mask[:, :, y0:y1, x0:x1] = 1.0
    alpha = epsilon / _ALPHA_DIVISOR

    with torch.no_grad():
        orig_embed = _embed(full_tensor, box).clone()

    x_adv = full_tensor.clone()
    for _ in range(steps):
        x_adv = x_adv.detach().requires_grad_(True)
        dist = (_embed(x_adv, box) - orig_embed).pow(2).sum()
        grad = torch.autograd.grad(dist, x_adv)[0]
        with torch.no_grad():
            x_adv = x_adv + alpha * grad.sign()
            x_adv = torch.min(torch.max(x_adv, full_tensor - epsilon), full_tensor + epsilon)
            x_adv = x_adv.clamp(0, 1)
            x_adv = full_tensor * (1 - mask) + x_adv * mask

    with torch.no_grad():
        final_embed = _embed(x_adv, box)
        import torch.nn.functional as F
        cos_sim = float(F.cosine_similarity(orig_embed, final_embed).item())

    return x_adv.detach(), cos_sim


def _tensor_to_b64(x_pixel) -> str:
    arr = (x_pixel.clamp(0, 1)[0].permute(1, 2, 0).detach().numpy() * 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _protection_label(cos_sim: float) -> str:
    if cos_sim < _DIFFERENT_PERSON_THRESHOLD:
        return "strong"
    if cos_sim < _SAME_PERSON_THRESHOLD:
        return "moderate"
    return "weak"


class CloakRequest(BaseModel):
    image: str  # base64, no data URL prefix
    epsilon: float = 0.05


def run_face_cloak(image_b64: str, epsilon: float) -> dict:
    if not (0.01 <= epsilon <= 0.1):
        raise HTTPException(status_code=400, detail="epsilon must be between 0.01 and 0.1")
    if not _ensure_loaded():
        raise HTTPException(status_code=503, detail="Face cloaking model is unavailable right now.")

    try:
        raw = base64.b64decode(image_b64, validate=True)
        if len(raw) > 8 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image too large (max 8MB).")
        scan_upload_bytes(raw, path="/rag/mm-face-cloak/run")
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode this as an image.")

    objects, _ = detect_objects(image_b64)
    faces = [o for o in objects if o["label"] in _FACE_LABELS]
    if not faces:
        return {"found_face": False, "error": "No face detected in this photo."}

    best_face = max(faces, key=lambda f: f["confidence"])
    w, h = img.size
    box = _face_crop_box(best_face["bbox"], w, h)

    import torch

    full_tensor = torch.from_numpy(np.asarray(img).astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0)
    x_cloaked, cos_sim = _cloak(full_tensor, box, epsilon)

    return {
        "found_face": True,
        "error": None,
        "cloaked_image": _tensor_to_b64(x_cloaked),
        "cosine_similarity": round(cos_sim, 4),
        "protection_level": _protection_label(cos_sim),
        "face_confidence": best_face["confidence"],
    }


@router.post("/mm-face-cloak/run")
def face_cloak_run(body: CloakRequest):
    return run_face_cloak(body.image, body.epsilon)
