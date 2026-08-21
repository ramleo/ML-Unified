"""
Model loading, attacks (FGSM/PGD), defenses (JPEG recompression, randomized
smoothing), Grad-CAM, and image encode/decode helpers for the Adversarial
Robustness Lab. Split out of mm_adversarial.py (which owns the router,
request schema, and orchestration) purely to keep each file under this
codebase's ~400-line-per-file convention — no behavior changed in the
split. See mm_adversarial.py's module docstring for the actual feature
narrative (attack/defense framing, real test findings).

Callers MUST access `_model`, `_categories`, `_transfer_model` through this
module (e.g. `models._model`), never via `from mm_adversarial_models import
_model` — those globals are REASSIGNED (not mutated in place) inside
`_ensure_loaded`/`_ensure_transfer_loaded`, and a `from x import y` binding
only copies the reference at import time, so a direct import would silently
stay stuck on the pre-load `None`/`[]` value forever.
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

_SMOOTH_SAMPLES = 25
_SMOOTH_SIGMA = 0.25  # real sweep during dev: 0.15 too weak to disrupt a
# strong PGD attack at all; 0.35+ starts destroying real image content
# instead of just the perturbation (see mm_adversarial.py's module
# docstring for the honest finding this produced)


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


def _fgsm(x, label_idx: int, epsilon: float, targeted: bool = False):
    """Untargeted: ascend the loss w.r.t. the TRUE label (push away from it).
    Targeted: descend the loss w.r.t. the TARGET label (push toward it) —
    same gradient, opposite sign."""
    import torch
    import torch.nn.functional as F

    x_adv = x.clone().requires_grad_(True)
    logits = _model(_normalize(x_adv))
    loss = F.cross_entropy(logits, torch.tensor([label_idx]))
    grad = torch.autograd.grad(loss, x_adv)[0]
    step = -epsilon * grad.sign() if targeted else epsilon * grad.sign()
    x_adv = (x_adv + step).clamp(0, 1)
    return x_adv.detach()


def _pgd(x, label_idx: int, epsilon: float, steps: int = 10, targeted: bool = False):
    import torch
    import torch.nn.functional as F

    alpha = epsilon / 4
    x_adv = x.clone()
    for _ in range(steps):
        x_adv = x_adv.detach().requires_grad_(True)
        logits = _model(_normalize(x_adv))
        loss = F.cross_entropy(logits, torch.tensor([label_idx]))
        grad = torch.autograd.grad(loss, x_adv)[0]
        step = -alpha * grad.sign() if targeted else alpha * grad.sign()
        x_adv = x_adv.detach() + step
        x_adv = torch.min(torch.max(x_adv, x - epsilon), x + epsilon)  # project to epsilon ball
        x_adv = x_adv.clamp(0, 1)
    return x_adv.detach()


_PATCH_MAX_STEPS = 150
_PATCH_LR = 0.08


def _adversarial_patch(x, label_idx: int, targeted: bool, patch_frac: float, max_steps: int = _PATCH_MAX_STEPS, lr: float = _PATCH_LR):
    """A DIFFERENT attack family from FGSM/PGD: instead of a tiny,
    imperceptible epsilon-bounded perturbation over the WHOLE image, this
    optimizes a single square region (unconstrained within [0,1], no
    epsilon ball) — a visible "sticker" patch, the kind that could in
    principle be printed and physically placed in a scene. This is the
    single-image, single-placement version (patch optimized for THIS exact
    photo and THIS exact center position) — not the original Brown et al.
    2017 paper's UNIVERSAL patch (trained across many images/positions/
    rotations via expectation-over-transformation to work anywhere, on
    any photo). Real testing found the two attack goals behave very
    differently here: UNTARGETED patches fool the classifier almost
    instantly (often within 1-2 gradient steps, sometimes before real
    optimization even helps — a patch this size is already a large, blunt
    perturbation on its own). TARGETED patches (forcing one exact chosen
    label) are genuinely harder and slower — a small patch (10% of the
    image) failed to reach the target at all within the step budget in
    real testing, while a larger patch (25%) reached it in a handful of
    steps. Early-stops the moment the goal is met (fooled for untargeted,
    exact target for targeted) rather than always running the full step
    budget, so `patch_steps` in the response is a real, honest measure of
    how much optimization this specific run actually needed."""
    import torch
    import torch.nn.functional as F

    size = x.shape[-1]
    p = max(4, int(round(patch_frac * size)))
    top = (size - p) // 2
    mask = torch.zeros_like(x)
    mask[:, :, top:top + p, top:top + p] = 1.0
    patch = torch.rand_like(x)

    for step in range(max_steps):
        patch = patch.detach().requires_grad_(True)
        x_patched = x * (1 - mask) + patch * mask
        logits = _model(_normalize(x_patched))
        pred_idx = int(logits.argmax(dim=1)[0])
        if (not targeted and pred_idx != label_idx) or (targeted and pred_idx == label_idx):
            return x_patched.clamp(0, 1).detach(), step
        loss = F.cross_entropy(logits, torch.tensor([label_idx]))
        grad = torch.autograd.grad(loss, patch)[0]
        with torch.no_grad():
            step_dir = -lr * grad.sign() if targeted else lr * grad.sign()
            patch = (patch + step_dir).clamp(0, 1)

    x_patched = (x * (1 - mask) + patch * mask).clamp(0, 1)
    return x_patched.detach(), max_steps


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


def _randomized_smooth(x_pixel, num_samples: int = _SMOOTH_SAMPLES, sigma: float = _SMOOTH_SIGMA) -> dict:
    """Second defense: randomized smoothing (Cohen et al. 2019) — classify
    many independently Gaussian-noised copies of the (possibly adversarial)
    image and take a majority vote, instead of a single deterministic
    prediction. The intuition: an adversarial perturbation is a small,
    precisely-targeted direction in pixel space; large random noise on top
    of it perturbs the input away from that precise direction on most
    samples, so the vote tends toward the image's "true" neighborhood in
    pixel space rather than the attacker's chosen wrong label. This is an
    EMPIRICAL vote, not the formal certified-radius guarantee from the
    original paper (that requires many more samples, e.g. 1000s, plus a
    concentration-bound computation this demo doesn't do) — reported here as
    `vote_confidence`, the plain fraction of noisy samples that agreed with
    the majority label, not a certified robustness radius."""
    import torch
    import torch.nn.functional as F

    with torch.no_grad():
        noise = torch.randn(num_samples, *x_pixel.shape[1:]) * sigma
        batch = (x_pixel.repeat(num_samples, 1, 1, 1) + noise).clamp(0, 1)
        logits = _model(_normalize(batch))
        preds = logits.argmax(dim=1)
        counts = torch.bincount(preds, minlength=len(_categories))
        top_idx = int(counts.argmax())

        # mean softmax distribution across all noisy samples, for a
        # top3/confidence shape consistent with _predict()'s single-sample
        # output — vote_confidence (below) is the real smoothing signal.
        mean_probs = F.softmax(logits, dim=1).mean(dim=0)
        top3_conf, top3_idx = torch.topk(mean_probs, 3)

    top3 = [{"label": _categories[i], "confidence": round(float(c), 4)} for c, i in zip(top3_conf, top3_idx)]
    return {
        "label": _categories[top_idx],
        "confidence": round(float(mean_probs[top_idx]), 4),
        "top3": top3,
        "vote_confidence": round(float(counts[top_idx]) / num_samples, 4),
        "num_samples": num_samples,
        "sigma": sigma,
    }


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
