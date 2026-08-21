"""
Adversarial examples: attack + defense demo, for educational/defensive
purposes — shows how a small, human-imperceptible pixel perturbation can
fool an image classifier, and how two cheap input-side defenses (JPEG
recompression, randomized smoothing) each partially — but never reliably —
recover the correct prediction. This is the same failure mode that matters
for this codebase's other CV tools (plate reader, face liveness, tampering
detector): if a classifier can be fooled by an engineered perturbation, its
output shouldn't be trusted blindly.

This file owns the router, request schema, and orchestration only — model
loading, the attacks, the defenses, Grad-CAM, and image encode/decode
helpers live in mm_adversarial_models.py (split out purely to keep both
files under this codebase's ~400-line convention; no behavior changed by
the split).

Target model: torchvision's pretrained MobileNetV2 (ImageNet-1000), a
generic off-the-shelf classifier, NOT any model used elsewhere in this
codebase — this demo is illustrative of a general ML robustness property,
not an attack against this app's own tools. torch/torchvision are already
transitive dependencies here (timm, pinned for mm_tables.py, requires
torchvision), so nothing new is added to requirements.

Attack: FGSM (single gradient step) or PGD (a few iterative steps, project
onto the epsilon L-infinity ball each step). Untargeted by default — the
attack pushes the prediction away from whatever the model currently
predicts, not toward a specific chosen wrong label. Optionally targeted:
the caller picks one of the 1000 ImageNet labels and the attack instead
descends the loss w.r.t. THAT label (same gradient machinery, opposite
sign/direction), trying to force that exact misclassification rather than
just any wrong one — a strictly harder attack than untargeted, since it
constrains not just "be wrong" but "be wrong in this specific way", so it
is not guaranteed to succeed within the same epsilon budget that reliably
fools the model untargeted. Real gradient access is required for this
(unlike this codebase's other CV tools, which only need forward-pass ONNX
inference), which is why this needs the real torch model instead of an
ONNX-exported one.

Also computes Grad-CAM for both the original and adversarial prediction —
a heatmap of which image regions actually drove that specific prediction,
via the last conv block's activations weighted by their gradient toward the
predicted class's logit. This is the more concrete, visual half of the
demo: the label change alone doesn't show WHY the model was fooled, but
comparing where it was "looking" before vs. after does.

Defense 1: JPEG recompression at a configurable quality. This is presented
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

Defense 2: randomized smoothing (Cohen et al. 2019 style, empirical vote
only — NOT the paper's certified-radius guarantee, which needs orders of
magnitude more samples plus a concentration-bound computation this demo
skips). Classifies `_SMOOTH_SAMPLES` independently Gaussian-noised copies
of the adversarial image and majority-votes. Real sigma sweep during
development on a strong PGD attack (epsilon=0.08): sigma=0.15 barely
disrupted anything (96% vote agreement stayed on the attacker's chosen
wrong label); sigma=0.35+ started destroying real image content, landing
on unrelated labels unconnected to either the original or the attack;
sigma=0.25 (the shipped default) sometimes recovered the correct label but
with visibly LOW vote_confidence (~0.3-0.4, i.e. barely a plurality,
changing between runs on the identical input due to the noise itself) —
an honest instability, not a bug, and reported directly via
`vote_confidence` rather than hidden behind a single point prediction.
Same overall conclusion as the JPEG defense: a real, sometimes-partial
mitigation, not a reliable fix, consistent with this project's honesty
pattern for defenses (see RDAP, region-sharpen corroboration, watermark
limits elsewhere in this codebase).

Optional transferability check (`check_transfer=True`): classifies the
SAME adversarial image (crafted only against MobileNetV2, no gradient
access to a second model at all) with ResNet18 — a different architecture
family — and reports whether ResNet18's own prediction also changed. Off
by default since it triggers a second (~45MB) lazy model download on
first use; see mm_adversarial_models.py's `_ensure_transfer_loaded` for
why the two models' category orderings are safe to compare directly.

Real finding from a method/epsilon sweep on a real photo (both models,
same image, `check_transfer=True`): FGSM's single-step perturbation did
NOT transfer to ResNet18 at ANY tested epsilon (0.02-0.08) — ResNet18 kept
its own correct prediction throughout, even though FGSM reliably fooled
MobileNetV2 itself every time. PGD's multi-step perturbation DID transfer
at every tested epsilon, changing ResNet18's prediction too (though never
to the exact same wrong label MobileNetV2 landed on — cross-model transfer
moves the OTHER model's prediction, not necessarily to the source attack's
specific target). This is a single-image, single-model-pair result, not a
general claim about FGSM vs. PGD transferability — reported as observed,
not extrapolated, matching this module's existing honesty pattern.
"""

import base64
import io

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import mm_adversarial_models as models

router = APIRouter()

_MAX_IMAGE_BYTES = 8 * 1024 * 1024


class RunRequest(BaseModel):
    image: str  # base64, no data URL prefix
    epsilon: float = 0.03
    method: str = "fgsm"  # "fgsm" | "pgd"
    jpeg_quality: int = 75
    target_label: str | None = None  # None = untargeted; else one of the 1000 ImageNet labels
    check_transfer: bool = False  # opt-in: also classify x_adv with ResNet18


def run_adversarial_demo(
    image_b64: str,
    epsilon: float,
    method: str,
    jpeg_quality: int,
    target_label: str | None = None,
    check_transfer: bool = False,
) -> dict:
    if method not in ("fgsm", "pgd"):
        raise HTTPException(status_code=400, detail="method must be 'fgsm' or 'pgd'")
    if not (0.001 <= epsilon <= 0.2):
        raise HTTPException(status_code=400, detail="epsilon must be between 0.001 and 0.2")
    if not (10 <= jpeg_quality <= 95):
        raise HTTPException(status_code=400, detail="jpeg_quality must be between 10 and 95")
    if not models._ensure_loaded():
        raise HTTPException(status_code=503, detail="Adversarial demo model is unavailable right now.")

    target_idx: int | None = None
    if target_label is not None:
        try:
            target_idx = models._categories.index(target_label)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown target_label: {target_label!r}")

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

    x = models._to_tensor(img)
    original = models._predict(x)
    original_top1_index = original.pop("top1_index")
    original_cam = models._grad_cam(x, original_top1_index)

    if target_idx is not None:
        # Targeted: if the model already predicts the target label, there's
        # nothing to attack toward — surface that plainly instead of running
        # a pointless attack that trivially "succeeds".
        if target_idx == original_top1_index:
            raise HTTPException(
                status_code=400,
                detail=f"The model already predicts {target_label!r} for this image — pick a different target.",
            )
        attack_label_idx, targeted = target_idx, True
    else:
        attack_label_idx, targeted = original_top1_index, False

    x_adv = (
        models._fgsm(x, attack_label_idx, epsilon, targeted=targeted)
        if method == "fgsm"
        else models._pgd(x, attack_label_idx, epsilon, targeted=targeted)
    )
    adversarial = models._predict(x_adv)
    adversarial_top1_index = adversarial.pop("top1_index")
    adversarial["fooled"] = adversarial["label"] != original["label"]
    if targeted:
        adversarial["target_label"] = target_label
        adversarial["target_achieved"] = adversarial["label"] == target_label
    adversarial_cam = models._grad_cam(x_adv, adversarial_top1_index)

    x_defended = models._jpeg_recompress(x_adv, jpeg_quality)
    defended = models._predict(x_defended)
    defended.pop("top1_index")
    defended["recovered"] = defended["label"] == original["label"]
    defended["disrupted"] = defended["label"] != adversarial["label"]

    smoothed = models._randomized_smooth(x_adv)
    smoothed["recovered"] = smoothed["label"] == original["label"]
    smoothed["disrupted"] = smoothed["label"] != adversarial["label"]

    transfer = None
    if check_transfer:
        if not models._ensure_transfer_loaded():
            raise HTTPException(status_code=503, detail="Transferability check model is unavailable right now.")
        transfer_original = models._predict(x, model=models._transfer_model)
        transfer_original.pop("top1_index")
        transfer_adversarial = models._predict(x_adv, model=models._transfer_model)
        transfer_adversarial.pop("top1_index")
        transfer = {
            "model": "resnet18",
            "original": transfer_original,
            "adversarial": transfer_adversarial,
            # transferred: the SAME perturbation (crafted only against
            # MobileNetV2, no gradient access to ResNet18 at all) ALSO
            # changed ResNet18's own prediction — the actual point of the
            # test, distinct from whether it landed on MobileNetV2's exact
            # wrong label (an unrealistic bar for a black-box transfer).
            "transferred": transfer_adversarial["label"] != transfer_original["label"],
        }

    return {
        "original": {**original, "heatmap": models._heatmap_overlay_b64(x, original_cam)},
        "adversarial": {
            **adversarial,
            "image": models._tensor_to_b64(x_adv),
            "heatmap": models._heatmap_overlay_b64(x_adv, adversarial_cam),
        },
        "smoothed": smoothed,
        "defended": {**defended, "image": models._tensor_to_b64(x_defended)},
        "transfer": transfer,
        "perturbation_preview": models._perturbation_preview_b64(x, x_adv),
    }


@router.post("/mm-adversarial/run")
def adversarial_run(body: RunRequest):
    return run_adversarial_demo(
        body.image, body.epsilon, body.method, body.jpeg_quality, body.target_label, body.check_transfer
    )


@router.get("/mm-adversarial/categories")
def adversarial_categories():
    """The 1000 ImageNet label strings, for the frontend's targeted-attack
    label picker. Triggers the lazy model load if it hasn't happened yet
    (categories come from the loaded weights' metadata)."""
    if not models._ensure_loaded():
        raise HTTPException(status_code=503, detail="Adversarial demo model is unavailable right now.")
    return {"categories": models._categories}
