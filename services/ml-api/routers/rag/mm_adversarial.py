"""
Adversarial examples: attack + defense demo, for educational/defensive
purposes — shows how a small, human-imperceptible pixel perturbation can
fool an image classifier, and how a cheap input-preprocessing defense can
recover the correct prediction. This is the same failure mode that matters
for this codebase's other CV tools (plate reader, face liveness, tampering
detector): if a classifier can be fooled by an engineered perturbation, its
output shouldn't be trusted blindly.

Target model: torchvision's pretrained MobileNetV2 (ImageNet-1000), a
generic off-the-shelf classifier, NOT any model used elsewhere in this
codebase — this demo is illustrative of a general ML robustness property,
not an attack against this app's own tools. torch/torchvision are already
transitive dependencies here (timm, pinned for mm_tables.py, requires
torchvision), so nothing new is added to requirements.

Attack: FGSM (single gradient step) or PGD (a few iterative steps, project
onto the epsilon L-infinity ball each step) — both untargeted: the attack
just pushes the prediction away from whatever the model currently predicts,
not toward a specific chosen wrong label. Real gradient access is required
for this (unlike this codebase's other CV tools, which only need forward-
pass ONNX inference), which is why this needs the real torch model instead
of an ONNX-exported one.

Also computes Grad-CAM for both the original and adversarial prediction —
a heatmap of which image regions actually drove that specific prediction,
via the last conv block's activations weighted by their gradient toward the
predicted class's logit. This is the more concrete, visual half of the
demo: the label change alone doesn't show WHY the model was fooled, but
comparing where it was "looking" before vs. after does.

Defense: JPEG recompression at a configurable quality. This is presented
honestly as a PARTIAL, unreliable mitigation, not a fix — real testing
during development (a real photo, multiple epsilon/quality combinations)
found it sometimes disrupts the SPECIFIC wrong label an attack converged to
(more often against iterative PGD than single-step FGSM) but rarely
restores the original correct label outright, especially when the model's
original top-1 confidence was already unremarkable to begin with. This
matches the real adversarial-ML literature's mixed findings on input-
preprocessing defenses — reporting the honest, sometimes-negative result
here rather than only shipping favorable parameter combinations. Two
outcomes are surfaced separately: `recovered` (exact match to the
original label — the strict, ideal outcome) and `disrupted` (the defended
prediction differs from the raw adversarial one — a weaker signal that the
defense did SOMETHING, even without full recovery).
"""

import base64
import io
import logging
import threading

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

_model = None
_categories: list[str] = []
_lock = threading.Lock()

_MAX_IMAGE_BYTES = 8 * 1024 * 1024
_IMG_SIZE = 224
_MEAN = [0.485, 0.456, 0.406]
_STD = [0.229, 0.224, 0.225]


def _ensure_loaded() -> bool:
    """Lazy-load MobileNetV2 on first use — most sessions never open this
    tool. Downloads pretrained ImageNet weights on first call, same pattern
    as CLIP in mm_photo_search.py / mm_similar.py."""
    global _model, _categories
    if _model is not None:
        return True
    with _lock:
        if _model is not None:
            return True
        try:
            import torch
            from torchvision.models import MobileNet_V2_Weights, mobilenet_v2

            logger.info("Loading MobileNetV2 (ImageNet, ~14MB) for adversarial demo …")
            weights = MobileNet_V2_Weights.IMAGENET1K_V1
            model = mobilenet_v2(weights=weights)
            model.eval()
            for p in model.parameters():
                p.requires_grad_(False)
            _model = model
            _categories = list(weights.meta["categories"])
            return True
        except Exception as exc:
            logger.warning("MobileNetV2 load failed — adversarial demo disabled: %s", exc)
            return False


def _to_tensor(img):
    from torchvision import transforms

    prep = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(_IMG_SIZE),
        transforms.ToTensor(),  # -> [0,1], shape (3, H, W)
    ])
    return prep(img).unsqueeze(0)  # (1, 3, 224, 224)


def _normalize(x):
    import torch

    mean = torch.tensor(_MEAN).view(1, 3, 1, 1)
    std = torch.tensor(_STD).view(1, 3, 1, 1)
    return (x - mean) / std


def _predict(x_pixel) -> dict:
    import torch
    import torch.nn.functional as F

    with torch.no_grad():
        logits = _model(_normalize(x_pixel))
        probs = F.softmax(logits, dim=1)[0]
        top3_conf, top3_idx = torch.topk(probs, 3)
    top3 = [{"label": _categories[i], "confidence": round(float(c), 4)} for c, i in zip(top3_conf, top3_idx)]
    return {"label": top3[0]["label"], "confidence": top3[0]["confidence"], "top3": top3, "top1_index": int(top3_idx[0])}


def _tensor_to_b64(x_pixel) -> str:
    from PIL import Image

    arr = (x_pixel.clamp(0, 1)[0].permute(1, 2, 0).detach().numpy() * 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _fgsm(x, true_idx: int, epsilon: float):
    import torch
    import torch.nn.functional as F

    x_adv = x.clone().requires_grad_(True)
    logits = _model(_normalize(x_adv))
    loss = F.cross_entropy(logits, torch.tensor([true_idx]))
    grad = torch.autograd.grad(loss, x_adv)[0]
    x_adv = (x_adv + epsilon * grad.sign()).clamp(0, 1)
    return x_adv.detach()


def _pgd(x, true_idx: int, epsilon: float, steps: int = 10):
    import torch
    import torch.nn.functional as F

    alpha = epsilon / 4
    x_adv = x.clone()
    for _ in range(steps):
        x_adv = x_adv.detach().requires_grad_(True)
        logits = _model(_normalize(x_adv))
        loss = F.cross_entropy(logits, torch.tensor([true_idx]))
        grad = torch.autograd.grad(loss, x_adv)[0]
        x_adv = x_adv.detach() + alpha * grad.sign()
        x_adv = torch.min(torch.max(x_adv, x - epsilon), x + epsilon)  # project to epsilon ball
        x_adv = x_adv.clamp(0, 1)
    return x_adv.detach()


def _jpeg_recompress(x_pixel, quality: int):
    """The defense: re-encode the (possibly adversarial) image through a
    lossy JPEG pass, then decode it back — destroys the attack's
    high-frequency perturbation while leaving real image content intact."""
    from PIL import Image

    arr = (x_pixel.clamp(0, 1)[0].permute(1, 2, 0).detach().numpy() * 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    recompressed = Image.open(buf).convert("RGB")
    return _to_tensor(recompressed)


def _perturbation_preview_b64(x_orig, x_adv, amplify: float = 8.0) -> str:
    """Amplified visualization of the perturbation itself — the raw diff is
    far too subtle to see at normal contrast, which is the whole point of
    the attack, so this exists purely to make that point visible."""
    from PIL import Image

    diff = ((x_adv - x_orig)[0].permute(1, 2, 0).detach().numpy() * amplify + 0.5)
    arr = np.clip(diff * 255, 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _grad_cam(x_pixel, target_index: int):
    """Grad-CAM: shows WHERE in the image the model is 'looking' to justify
    a given prediction — the standard way to make an otherwise-abstract
    "why did it predict that" question visible. Hooks the last conv block's
    activations (model.features' output), weights each activation channel
    by its global-average-pooled gradient w.r.t. the target class's logit,
    and upsamples the resulting map back to image size. Comparing this for
    the original vs. adversarial prediction is the actual point: an
    imperceptible pixel change can shift not just the label but WHERE the
    model claims to be looking."""
    import torch
    import torch.nn.functional as F

    activations = {}

    def hook(_module, _input, output):
        activations["value"] = output

    handle = _model.features.register_forward_hook(hook)
    x = x_pixel.clone().requires_grad_(True)
    logits = _model(_normalize(x))
    handle.remove()

    act = activations["value"]
    act.retain_grad()
    logits[0, target_index].backward()

    grad = act.grad
    weights = grad.mean(dim=(2, 3), keepdim=True)
    cam = F.relu((weights * act).sum(dim=1, keepdim=True))
    cam = F.interpolate(cam, size=(_IMG_SIZE, _IMG_SIZE), mode="bilinear", align_corners=False)[0, 0]
    cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)
    return cam.detach()


def _heatmap_overlay_b64(x_pixel, cam) -> str:
    import cv2
    from PIL import Image

    orig = (x_pixel.clamp(0, 1)[0].permute(1, 2, 0).detach().numpy() * 255).astype(np.uint8)
    heat = (cam.numpy() * 255).astype(np.uint8)
    heat_color = cv2.cvtColor(cv2.applyColorMap(heat, cv2.COLORMAP_JET), cv2.COLOR_BGR2RGB)
    overlay = np.clip(orig.astype(np.float32) * 0.55 + heat_color.astype(np.float32) * 0.45, 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(overlay).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


class RunRequest(BaseModel):
    image: str  # base64, no data URL prefix
    epsilon: float = 0.03
    method: str = "fgsm"  # "fgsm" | "pgd"
    jpeg_quality: int = 75


def run_adversarial_demo(image_b64: str, epsilon: float, method: str, jpeg_quality: int) -> dict:
    if method not in ("fgsm", "pgd"):
        raise HTTPException(status_code=400, detail="method must be 'fgsm' or 'pgd'")
    if not (0.001 <= epsilon <= 0.2):
        raise HTTPException(status_code=400, detail="epsilon must be between 0.001 and 0.2")
    if not (10 <= jpeg_quality <= 95):
        raise HTTPException(status_code=400, detail="jpeg_quality must be between 10 and 95")
    if not _ensure_loaded():
        raise HTTPException(status_code=503, detail="Adversarial demo model is unavailable right now.")

    from PIL import Image

    try:
        raw = base64.b64decode(image_b64, validate=True)
        if len(raw) > _MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail="Image too large (max 8MB).")
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode this as an image.")

    x = _to_tensor(img)
    original = _predict(x)
    original_top1_index = original.pop("top1_index")
    original_cam = _grad_cam(x, original_top1_index)

    x_adv = _fgsm(x, original_top1_index, epsilon) if method == "fgsm" else _pgd(x, original_top1_index, epsilon)
    adversarial = _predict(x_adv)
    adversarial_top1_index = adversarial.pop("top1_index")
    adversarial["fooled"] = adversarial["label"] != original["label"]
    adversarial_cam = _grad_cam(x_adv, adversarial_top1_index)

    x_defended = _jpeg_recompress(x_adv, jpeg_quality)
    defended = _predict(x_defended)
    defended.pop("top1_index")
    defended["recovered"] = defended["label"] == original["label"]
    defended["disrupted"] = defended["label"] != adversarial["label"]

    return {
        "original": {**original, "heatmap": _heatmap_overlay_b64(x, original_cam)},
        "adversarial": {**adversarial, "image": _tensor_to_b64(x_adv), "heatmap": _heatmap_overlay_b64(x_adv, adversarial_cam)},
        "defended": {**defended, "image": _tensor_to_b64(x_defended)},
        "perturbation_preview": _perturbation_preview_b64(x, x_adv),
    }


@router.post("/mm-adversarial/run")
def adversarial_run(body: RunRequest):
    return run_adversarial_demo(body.image, body.epsilon, body.method, body.jpeg_quality)
