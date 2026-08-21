"""
Model loading, prediction, Grad-CAM, and image encode/decode helpers for
the Adversarial Robustness Lab. Split out of mm_adversarial.py (router/
orchestration) purely to keep files under this codebase's ~400-line
convention. Attacks (FGSM/PGD/patch/black-box) live in
mm_adversarial_attacks.py; defenses (JPEG recompression, randomized
smoothing) live in mm_adversarial_defenses.py — both import `_model`,
`_normalize`, `_categories` from THIS module. See mm_adversarial.py's
module docstring for the actual feature narrative (attack/defense
framing, real test findings).

Callers MUST access `_model`, `_categories`, `_transfer_model` through
this module (e.g. `models._model`), never via `from mm_adversarial_models
import _model` — those globals are REASSIGNED (not mutated in place)
inside `_ensure_loaded`/`_ensure_transfer_loaded`, and a `from x import y`
binding only copies the reference at import time, so a direct import
would silently stay stuck on the pre-load `None`/`[]` value forever.
"""

import base64
import io
import logging
import threading

import numpy as np

logger = logging.getLogger(__name__)

_model = None
_categories: list[str] = []
_lock = threading.Lock()

_transfer_model = None
_transfer_lock = threading.Lock()

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


def _ensure_transfer_loaded() -> bool:
    """Lazy-load ResNet18 — a DIFFERENT architecture family (residual convs
    vs. MobileNetV2's depthwise-separable convs) used ONLY for the optional
    transferability check: does a perturbation crafted against MobileNetV2
    also fool a model that never saw the attack's gradients? Confirmed
    ResNet18_Weights and MobileNet_V2_Weights share an identical ImageNet
    category ordering (verified directly, not assumed), so both models'
    predictions can be compared/indexed via the same `_categories` list."""
    global _transfer_model
    if _transfer_model is not None:
        return True
    with _transfer_lock:
        if _transfer_model is not None:
            return True
        try:
            from torchvision.models import ResNet18_Weights, resnet18

            logger.info("Loading ResNet18 (ImageNet, ~45MB) for transferability check …")
            model = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
            model.eval()
            for p in model.parameters():
                p.requires_grad_(False)
            _transfer_model = model
            return True
        except Exception as exc:
            logger.warning("ResNet18 load failed — transferability check disabled: %s", exc)
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


def _predict(x_pixel, model=None) -> dict:
    """model=None uses the primary attack target (MobileNetV2, module-level
    _model); pass _transfer_model to classify with the second architecture
    instead — used only by the transferability check."""
    import torch
    import torch.nn.functional as F

    with torch.no_grad():
        logits = (model or _model)(_normalize(x_pixel))
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
