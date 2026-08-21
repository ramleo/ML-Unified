"""
Style cloaking: the artist-protection counterpart to Face Cloak, both
"used for good" applications of the Adversarial Robustness Lab's attack
demo. Adds an adversarial perturbation to an image that pushes its
CLIP image embedding far from where it naturally sits — so an AI model
trained to mimic this image's style (scraping it for style-transfer or
fine-tuning) learns a distorted representation instead of the real one.
Same real technique family as Glaze/Nightshade (Shan et al. 2023, SAND
Lab UChicago) — built to counter unauthorized AI style-mimicry trained
on artists' work without consent — and the same idea Face Cloak applies
to face-recognition embeddings instead of style embeddings.

Embedding model: openai/clip-vit-base-patch32 via `transformers`
(MIT license, ~600MB, 512-d L2-normalized embedding). CLIP was chosen
because style-transfer/fine-tuning pipelines commonly use CLIP or
CLIP-adjacent encoders to represent an image's visual "look," and this
codebase already depends on `transformers` (mm_similar.py uses a CLIP
model via sentence-transformers) — no new model family introduced.
Whole-image perturbation, unlike Face Cloak's face-crop-only mask: a
face photo has one small region that matters to the target model, but
an artwork's style is a property of the whole image, so there's no
sub-region to isolate.

Simplified vs. the real Glaze/Nightshade papers: this is UNTARGETED
(repulsion) — it pushes the perturbed image's CLIP embedding away from
the image's OWN original embedding via gradient ascent on cosine
similarity, epsilon-bounded so the change stays close to invisible.
Glaze's actual technique is TARGETED (pushes toward a different, chosen
art style's feature-space region) and Nightshade specifically targets
poisoning a model's association between a concept and its rendering —
both are more sophisticated and more durable than plain repulsion. This
tool doesn't ship a bundled style-target dataset to pick a real decoy
style from, so it uses the simpler, still-effective repulsion variant —
disclosed here directly, not hidden.

Real calibration testing (not guessed): CLIP image-embedding cosine
similarity between two UNRELATED synthetic images (different shapes,
colors, composition) measured 0.65-0.77 — much higher than the
"different person" baseline in face-embedding space, because CLIP
embeddings share generic visual/scene structure even for unrelated
content. This directly shapes the protection thresholds below, which
are NOT copied from mm_face_cloak.py's face-embedding thresholds.
Real cloaking test: epsilon=0.06, 40 steps, took ~1-2 seconds and
dropped cosine similarity between the original and cloaked embeddings
from 1.0 (identical) to -0.36 — well below the unrelated-image
baseline, meaning the cloaked image now reads as MORE different from
its own original than two random unrelated images typically do.

Honest limitations, matching this project's established pattern (see
mm_face_cloak.py, mm_adversarial.py, mm_watermark.py): (1) this protects
the SPECIFIC cloaked image going forward — it does nothing for copies of
this image already scraped/trained on elsewhere. (2) The real Glaze
research is an ongoing arms race against adaptive style-mimicry models
that train to be robust against known cloaking methods, not a
permanent, one-time fix. (3) No real style-mimicry benchmark is run
here (no actual fine-tuning or style-transfer pipeline to test against)
— the cosine-similarity drop is a real, measured signal against the
CLIP encoder itself, not a guarantee against every possible style-
mimicry system, which may use a different encoder entirely.
"""

import base64
import io
import logging
import threading

import numpy as np
from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

_CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"
_EMBED_SIZE = 224
_CLIP_MEAN = [0.48145466, 0.4578275, 0.40821073]
_CLIP_STD = [0.26862954, 0.26130258, 0.27577711]

_STEPS = 40
_ALPHA_DIVISOR = 8  # step size per iteration = epsilon / this

# Calibrated against real unrelated-image CLIP cosine similarity (0.65-0.77),
# not copied from face-embedding thresholds — see module docstring.
_STRONG_THRESHOLD = 0.5
_MODERATE_THRESHOLD = 0.75

_model = None
_lock = threading.Lock()
_mean_t = None
_std_t = None


def _ensure_loaded() -> bool:
    """Lazy-load CLIP on first use — most sessions never open this tool."""
    global _model, _mean_t, _std_t
    if _model is not None:
        return True
    with _lock:
        if _model is not None:
            return True
        try:
            import torch
            from transformers import CLIPModel

            logger.info("Loading CLIP (%s) for style cloaking …", _CLIP_MODEL_NAME)
            model = CLIPModel.from_pretrained(_CLIP_MODEL_NAME).eval()
            for p in model.parameters():
                p.requires_grad_(False)
            _model = model
            _mean_t = torch.tensor(_CLIP_MEAN).view(3, 1, 1)
            _std_t = torch.tensor(_CLIP_STD).view(3, 1, 1)
            return True
        except Exception as exc:
            logger.warning("CLIP load failed — style cloaking disabled: %s", exc)
            return False


def _embed(full_tensor):
    import torch.nn.functional as F

    resized = F.interpolate(full_tensor, size=(_EMBED_SIZE, _EMBED_SIZE), mode="bilinear", align_corners=False)
    normed = (resized - _mean_t) / _std_t
    out = _model.get_image_features(pixel_values=normed)
    return F.normalize(out, dim=-1)


def _cloak(full_tensor, epsilon: float, steps: int = _STEPS):
    """Gradient-ascent repulsion: minimize cosine similarity between the
    current (perturbed) image embedding and the ORIGINAL image's own
    embedding (fixed reference, computed once). Epsilon-bounded per pixel,
    applied to the whole image — style is a whole-image property, unlike
    a face's localized crop region in mm_face_cloak.py."""
    import torch
    import torch.nn.functional as F

    alpha = epsilon / _ALPHA_DIVISOR

    with torch.no_grad():
        orig_embed = _embed(full_tensor).clone()

    x_adv = full_tensor.clone()
    for _ in range(steps):
        x_adv = x_adv.detach().requires_grad_(True)
        sim = F.cosine_similarity(_embed(x_adv), orig_embed).mean()
        grad = torch.autograd.grad(sim, x_adv)[0]
        with torch.no_grad():
            x_adv = x_adv - alpha * grad.sign()
            x_adv = torch.min(torch.max(x_adv, full_tensor - epsilon), full_tensor + epsilon)
            x_adv = x_adv.clamp(0, 1)

    with torch.no_grad():
        final_embed = _embed(x_adv)
        cos_sim = float(F.cosine_similarity(orig_embed, final_embed).item())

    return x_adv.detach(), cos_sim


def _tensor_to_b64(x_pixel) -> str:
    arr = (x_pixel.clamp(0, 1)[0].permute(1, 2, 0).detach().numpy() * 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _protection_label(cos_sim: float) -> str:
    if cos_sim < _STRONG_THRESHOLD:
        return "strong"
    if cos_sim < _MODERATE_THRESHOLD:
        return "moderate"
    return "weak"


class CloakRequest(BaseModel):
    image: str  # base64, no data URL prefix
    epsilon: float = 0.06


def run_style_cloak(image_b64: str, epsilon: float) -> dict:
    if not (0.01 <= epsilon <= 0.12):
        raise HTTPException(status_code=400, detail="epsilon must be between 0.01 and 0.12")
    if not _ensure_loaded():
        raise HTTPException(status_code=503, detail="Style cloaking model is unavailable right now.")

    try:
        raw = base64.b64decode(image_b64, validate=True)
        if len(raw) > 8 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image too large (max 8MB).")
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode this as an image.")

    import torch

    full_tensor = torch.from_numpy(np.asarray(img).astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0)
    x_cloaked, cos_sim = _cloak(full_tensor, epsilon)

    return {
        "cloaked_image": _tensor_to_b64(x_cloaked),
        "cosine_similarity": round(cos_sim, 4),
        "protection_level": _protection_label(cos_sim),
    }


@router.post("/mm-style-cloak/run")
def style_cloak_run(body: CloakRequest):
    return run_style_cloak(body.image, body.epsilon)
