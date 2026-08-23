"""Chi-square LSB steganalysis — detects hidden data embedded via least-
significant-bit replacement (the most common image-steganography technique).

This is a WHOLE-IMAGE verdict, unlike mm_tampering.py's region-based
detectors: a steganographic payload is typically spread across the entire
image (or a large contiguous run from the start), not localized to one
splice-able region, so there's no bbox to draw — {detected, confidence}
only.

Two other approaches were tried first and rejected before this one (see
project_tampering_detector_precision memory for the full record):
1. An FFT "periodic-artifact" detector aimed at AI-generated splices — the
   real target signal existed on an isolated synthetic test but was swamped
   by ordinary real-photo detail once embedded in an actual photo.
2. A near-Nyquist-frequency energy ratio (also FFT-based) aimed at THIS
   steganography problem — worked cleanly on one PNG test image but failed
   completely on real JPEG-native photos: JPEG's own compression dumps
   energy into exactly the frequency band this measured, varying by 2-3
   orders of magnitude between ordinary untampered photos, swamping the
   real signal.

This module uses the classical Westfeld-Pfitzmann chi-square attack
instead — a SPATIAL-domain technique (histogram value-pairs), not
frequency-domain, chosen specifically because it doesn't share either
failure mode above: verified directly against the same JPEG-native test
photos that broke approach #2, and the signal held up cleanly on all of
them (see chi_square_lsb_stat's docstring for the actual test numbers).

How it works: LSB replacement pairs up adjacent pixel values (2k, 2k+1) and
tends to EQUALIZE their histogram counts (embedding a ~50/50 random bit
stream flips each pair toward a 50/50 split of their combined total). A
natural, untouched photo has no such pairing structure — its value-pair
histogram counts are naturally imbalanced. The chi-square statistic
measures how far the observed pair counts are from a fully-equalized
model: LOW chi-square means "consistent with LSB embedding", HIGH
chi-square means "looks like an ordinary photo".

Real, disclosed limitation (matches the well-documented behavior of this
technique in the literature, not specific to this implementation):
sensitivity drops off sharply below ~20-30% embedding rate — a small
hidden message occupying only a few percent of the image's pixels will not
reliably separate from a clean baseline. This ships as a signal for
"substantial" LSB payloads, not a guarantee against a small one.

Second real limitation, found live after shipping (not by the original
calibration, which only tested large images): the chi-square statistic
needs enough pixel-value diversity to be reliable, and how much is
CONTENT-dependent, not a clean fixed cutoff — a smooth/low-detail JPEG
photo produced false positives even close to its own native resolution,
while a higher-detail lossless image stayed reliable much smaller (see
_MIN_DIM below for the real numbers). Below that floor the check is
skipped entirely rather than reported with reduced confidence, since
there's no reliable signal to report at all — but the floor is a
heuristic with real margin, not a guarantee against every image.
"""
from __future__ import annotations

import base64
import io
import logging

import numpy as np
from fastapi import APIRouter
from PIL import Image
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

_MIN_EXPECTED = 4  # skip a value-pair with too few samples to be meaningful
# Calibrated against real test images (bike PNG + 3 native-JPEG photos,
# grace_hopper/china/flower), embedding LSB payloads into the RGB channels
# directly (the realistic scenario) and averaging chi-square-per-dof across
# R/G/B (see detect_steganography's docstring for why average, not min or a
# grayscale conversion — both were tried first and rejected). Observed:
# clean 14.86-45.54, 100%-rate embed 0.94-1.09, 50% 4.59-12.01. These two
# bounds anchor the confidence scale below.
_CHI_SQ_STEGO_CEILING = 2.0   # at/below this -> confidence 1.0
_CHI_SQ_CLEAN_FLOOR = 13.0    # at/above this -> confidence 0.0

# Real bug found live (not caught by the original calibration, which only
# tested full-resolution images): the chi-square statistic needs enough
# real pixel-value diversity to behave the way _CHI_SQ_CLEAN_FLOOR assumes,
# and how much is "enough" is CONTENT-dependent, not a clean fixed cutoff —
# confirmed directly on two different real images:
#   - china.jpg (a soft, low-detail JPEG, one of this module's own clean
#     calibration images) was already only marginally clean at its full
#     native 640x427 size (14.86, barely above the 13.0 floor) and flipped
#     to a false 27-59% "detected" once resized down to 500px or smaller —
#     zero embedding either time.
#   - the bike PNG (higher-detail, more real texture, lossless) stayed
#     correctly clean down to ~500px (15.42) and only degraded below the
#     floor at ~450px (12.82).
# There's no single dimension that's safe for every image — a genuinely
# smooth/low-detail photo could in principle still misfire above this
# floor. 500 sits above china.jpg's own marginal native size (427, already
# only barely clean) and comfortably above the bike PNG's real failure
# point (450) with its actual clean value there (15.42) — not a guarantee
# against all content, just real margin above what was actually observed.
_MIN_DIM = 500


def chi_square_lsb_stat(channel: np.ndarray) -> float | None:
    """channel: 2D uint8 array (one color channel or grayscale). Returns
    chi-square-per-degree-of-freedom for the (2k, 2k+1) value-pair
    histogram, or None if the channel has too little value diversity to
    test at all (e.g. a near-blank crop)."""
    hist, _ = np.histogram(channel, bins=256, range=(0, 256))
    chi_sq, dof = 0.0, 0
    for k in range(128):
        h0, h1 = float(hist[2 * k]), float(hist[2 * k + 1])
        expected = (h0 + h1) / 2.0
        if expected < _MIN_EXPECTED:
            continue
        chi_sq += (h0 - expected) ** 2 / expected + (h1 - expected) ** 2 / expected
        dof += 1
    if dof == 0:
        return None
    return chi_sq / dof


def detect_steganography(b64: str) -> dict:
    """Returns {detected: bool, confidence: float} — whole-image verdict,
    no bbox (see module docstring for why). {detected: False, confidence: 0}
    on any failure or if the image is too small/uniform to test; never
    blocks ingestion.

    Only meaningful on a losslessly-saved image (PNG/BMP/TIFF) — LSB data
    does not survive JPEG re-compression, so a genuine LSB payload could
    not exist in a JPEG-sourced image in the first place. Still runs on a
    JPEG upload (rather than refusing) since a JPEG-native photo is a valid
    negative-control case, but true positives only arise from lossless
    sources.
    """
    try:
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        arr = np.asarray(img)
        if arr.shape[0] < _MIN_DIM or arr.shape[1] < _MIN_DIM:
            return {"detected": False, "confidence": 0.0}

        # AVERAGE chi-square across R/G/B — two other combinations were
        # tried first and rejected. MIN across channels produced a real
        # false positive (china.jpg's R channel alone read as 35%
        # "detected" with zero embedding — ordinary per-channel content
        # variance, not a signal). Converting to grayscale/luminance FIRST
        # (a single derived channel) destroyed the signal entirely — 0%
        # confidence even at 100% embedding rate — because PIL's weighted
        # luminance formula (a rounded weighted sum of R/G/B) doesn't
        # preserve the clean bit-level equalization pattern that exists in
        # each RGB channel individually. Averaging keeps the real per-channel
        # signal (unlike luminance) while damping single-channel noise
        # (unlike min) — verified against all 4 test images with LSB
        # embedded directly into RGB (the realistic case): clean 14.86-45.54,
        # 100%-rate embed 0.94-1.09, no false positives.
        stats = [chi_square_lsb_stat(arr[:, :, c]) for c in range(3)]
        stats = [s for s in stats if s is not None]
        if not stats:
            return {"detected": False, "confidence": 0.0}
        chi_sq = float(np.mean(stats))

        confidence = float(np.clip(
            (_CHI_SQ_CLEAN_FLOOR - chi_sq) / (_CHI_SQ_CLEAN_FLOOR - _CHI_SQ_STEGO_CEILING),
            0.0, 1.0,
        ))
        return {"detected": confidence > 0.0, "confidence": round(confidence, 3)}
    except Exception as exc:
        logger.warning("Steganography detection failed: %s", exc)
        return {"detected": False, "confidence": 0.0}


def describe_steganography(result: dict | None) -> str:
    """Same rationale as mm_tampering.describe_tampering: baked into the
    stored chunk text so groundedness/citation scoring can back a "does
    this contain hidden data" answer."""
    if not result or not result.get("detected"):
        return ""
    conf_pct = round(result["confidence"] * 100)
    return (f"Possible hidden data detected in this image ({conf_pct}% confidence) — "
            "every pixel has a color number, and hidden data quietly nudges some of those "
            "numbers so that certain pairs (like pixels colored 100 vs. 101) show up equally "
            "often, something a normal photo almost never does on its own. A strong hint, not "
            "proof, and only works on PNG-style images (a JPEG photo can't hide data this way).")


class VisualizeRequest(BaseModel):
    image: str  # b64 image, the same citation image already shown to the user


def extract_lsb_visualization(b64: str, max_dim: int = 500) -> str:
    """Renders the red channel's least-significant-bit plane as its own
    black/white image — purely illustrative, NOT a claim about where a
    hidden payload is located (there is no "where": see the module
    docstring on why this is a whole-image signal). Every pixel's last bit
    becomes black (0) or white (1); a normal, untouched photo's version of
    this looks like plain static/noise, same as a photo carrying a hidden
    payload — the point is to make the otherwise-invisible thing the
    detector reads concretely visible, not to visually distinguish clean
    from tampered. Downsized to `max_dim` on the long side since precision
    doesn't matter for an illustration and this keeps the response small."""
    img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    w, h = img.size
    scale = min(1.0, max_dim / max(w, h))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.NEAREST)
    r = np.asarray(img)[:, :, 0]
    bitplane = ((r & 1) * 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(bitplane, mode="L").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@router.post("/mm-steganography/visualize")
def visualize_steganography(body: VisualizeRequest):
    """Returns {"image": <b64>} — the illustrative bit-plane image (see
    extract_lsb_visualization). Computed on demand, not at ingest, since
    it's only ever needed if a user actually opens the "Possible hidden
    data" dropdown option."""
    return {"image": extract_lsb_visualization(body.image)}
