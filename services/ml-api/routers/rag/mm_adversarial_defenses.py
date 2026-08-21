"""
The two defense implementations for the Adversarial Robustness Lab: JPEG
recompression and randomized smoothing. Split out of
mm_adversarial_models.py purely to keep files under this codebase's
~400-line convention. See mm_adversarial.py's module docstring for the
defense narrative and real test findings; see mm_adversarial_models.py's
docstring for why `_model`/`_normalize`/`_categories` must be accessed via
`models.` rather than imported by value.
"""

import io

import numpy as np

from . import mm_adversarial_models as models


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
    return models._to_tensor(recompressed)


_SMOOTH_SAMPLES = 25
_SMOOTH_SIGMA = 0.25  # real sweep during dev: 0.15 too weak to disrupt a
# strong PGD attack at all; 0.35+ starts destroying real image content
# instead of just the perturbation (see mm_adversarial.py's module
# docstring for the honest finding this produced)


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
        logits = models._model(models._normalize(batch))
        preds = logits.argmax(dim=1)
        counts = torch.bincount(preds, minlength=len(models._categories))
        top_idx = int(counts.argmax())

        # mean softmax distribution across all noisy samples, for a
        # top3/confidence shape consistent with _predict()'s single-sample
        # output — vote_confidence (below) is the real smoothing signal.
        mean_probs = F.softmax(logits, dim=1).mean(dim=0)
        top3_conf, top3_idx = torch.topk(mean_probs, 3)

    top3 = [{"label": models._categories[i], "confidence": round(float(c), 4)} for c, i in zip(top3_conf, top3_idx)]
    return {
        "label": models._categories[top_idx],
        "confidence": round(float(mean_probs[top_idx]), 4),
        "top3": top3,
        "vote_confidence": round(float(counts[top_idx]) / num_samples, 4),
        "num_samples": num_samples,
        "sigma": sigma,
    }
