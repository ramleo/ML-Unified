"""FFT-based moire / scan-line pattern detection — flags photos of a screen
or a scanned document by finding a periodic spike hidden in the image's
frequency content.

This is a WHOLE-IMAGE verdict, same shape as mm_steganography.py's
{detected, confidence} — a moire pattern spans the whole frame (it comes
from interference between the camera sensor grid and the display/scan grid),
not one localized region, so there's no bbox to draw.

Two other FFT techniques were tried and rejected in this codebase before
this one (see mm_steganography.py's docstring and the
project_tampering_detector_precision memory) — both measured broad
frequency-band energy or shape, which real JPEG compression noise swamps by
orders of magnitude. This module avoids that failure mode differently: it
looks for an isolated narrow SPIKE relative to its local neighborhood, not
an average over a band, and a first attempt (blind 2D FFT with the DC-axis
excluded to dodge a border-discontinuity artifact) turned out to have its
own real bug — that exclusion also blinded it to axis-aligned moire
(straight horizontal scan lines), the single most common real-world case.

This module instead uses a Radon-style angular sweep: rotate the image
through many angles, collapse each rotation to a 1D brightness profile, and
look for a spike in THAT profile's 1D spectrum relative to its local
neighborhood. Periodicity in any orientation shows up strongly in the
profile perpendicular to it, including angle 0 — no directional blind spot.

Real, disclosed limitation, verified directly (not assumed): this only
reliably separates FINE-period moire (roughly 4-8px per cycle at 512px
working resolution) — the physically realistic scale for real camera-vs-
screen or scanner interference — from 5 real test photos (JPEG-native and
PNG) at ratio 4.3-7.7. Coarse patterns (~30px+ period) are much closer to
ordinary macro-scale image gradients and were NOT reliably separable; that's
not actually a gap in real moire coverage since genuine moire doesn't occur
at that scale, but it means this module should not be described as a
general "repeating pattern" detector.
"""
from __future__ import annotations

import base64
import io
import logging

import numpy as np
from fastapi import APIRouter
from PIL import Image, ImageDraw
from pydantic import BaseModel
from scipy.ndimage import median_filter, rotate

logger = logging.getLogger(__name__)
router = APIRouter()

_WORK_DIM = 512  # working resolution the calibration below was measured at
_ANGLE_STEP_DEG = 3  # finer steps recover diagonal patterns the exact synthetic
# angle would otherwise miss between samples; 3 degrees costs ~0.3s/image and
# closes that gap without a large runtime hit (60 rotations of a 512px image)
_MARGIN_FRAC = 0.15  # crop this fraction off each edge after rotation to drop
# the reflect-padding artifact rotation introduces at the corners
_EXCLUDE_LOW_BINS = 6  # drop near-DC / slow-gradient content from each profile's spectrum
_NBHD = 15  # local-median window for the spike-vs-neighborhood ratio

# Calibrated against 5 real test photos (bike PNG, china/flower/grace_hopper
# JPEGs, a product PNG) with no moire: observed ratio 4.03-7.75. Synthetic
# fine-period (4-8px) moire at a moderate amplitude cleared 12+ in 89 of 90
# angle/frequency/amplitude/base-photo combinations tested; the one miss was
# the weakest case (amp=8, freq=8px, axis-aligned) at 7.94, right at the real-
# photo ceiling. These two bounds anchor the confidence scale below.
_CLEAN_CEILING = 8.0    # at/below this -> confidence 0.0
_MOIRE_FLOOR = 15.0     # at/above this -> confidence 1.0


def _prep_gray(b64: str) -> np.ndarray | None:
    img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("L")
    w, h = img.size
    if w < 64 or h < 64:
        return None
    scale = min(1.0, _WORK_DIM / max(w, h))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    return np.asarray(img, dtype=np.float32)


def moire_spike_ratio(gray: np.ndarray) -> float:
    """Max, over a sweep of rotation angles, of the strongest spike in that
    angle's 1D projection spectrum relative to its local neighborhood
    median. See module docstring for why a per-angle 1D profile is used
    instead of the 2D FFT spectrum directly."""
    h, w = gray.shape
    margin = int(_MARGIN_FRAC * min(h, w))
    best = 0.0
    for angle in range(0, 180, _ANGLE_STEP_DEG):
        rotated = rotate(gray, angle, reshape=False, order=1, mode="reflect")
        crop = rotated[margin:h - margin, margin:w - margin]
        profile = crop.mean(axis=0)
        profile = profile - profile.mean()
        window = np.hanning(len(profile))
        spectrum = np.abs(np.fft.rfft(profile * window))
        spectrum = spectrum[_EXCLUDE_LOW_BINS:]
        if len(spectrum) < _NBHD * 2:
            continue
        local_median = median_filter(spectrum, size=_NBHD)
        nonzero = local_median > 1e-6
        ratio = np.zeros_like(spectrum)
        ratio[nonzero] = spectrum[nonzero] / local_median[nonzero]
        best = max(best, float(ratio.max()))
    return best


def detect_moire(b64: str) -> dict:
    """Returns {detected: bool, confidence: float} — whole-image verdict,
    no bbox. {detected: False, confidence: 0.0} on any failure or if the
    image is too small to test; never blocks ingestion."""
    try:
        gray = _prep_gray(b64)
        if gray is None:
            return {"detected": False, "confidence": 0.0}
        ratio = moire_spike_ratio(gray)
        confidence = float(np.clip(
            (ratio - _CLEAN_CEILING) / (_MOIRE_FLOOR - _CLEAN_CEILING),
            0.0, 1.0,
        ))
        return {"detected": confidence > 0.0, "confidence": round(confidence, 3)}
    except Exception as exc:
        logger.warning("Moire detection failed: %s", exc)
        return {"detected": False, "confidence": 0.0}


def describe_moire(result: dict | None) -> str:
    """Same rationale as describe_steganography: baked into the stored
    chunk text so groundedness/citation scoring can back a "was this
    photographed off a screen" answer."""
    if not result or not result.get("detected"):
        return ""
    conf_pct = round(result["confidence"] * 100)
    return (f"Possible screen/scan pattern detected in this image ({conf_pct}% confidence) — "
            "a repeating ripple shows up in the image's underlying frequency structure that "
            "isn't there in an ordinary photo, the kind of pattern that appears when a photo "
            "is taken of a screen or a scanned document rather than a real scene directly.")


class VisualizeRequest(BaseModel):
    image: str  # b64 image, the same citation image already shown to the user


_MARKER_DC_EXCLUDE_FRAC = 0.035  # matches the detector's own DC-exclusion scale
_MARKER_RADIUS = 10
_MARKER_COLOR = (255, 80, 60)


def extract_moire_spectrum_visualization(b64: str, max_dim: int = 500) -> str:
    """Renders the image's own 2D log-magnitude FFT spectrum with the
    strongest non-DC frequency circled in red.

    A first version of this just showed the raw spectrum with no marker,
    relying on a viewer noticing it looked different from a clean photo's —
    verified directly (not assumed) that this does NOT work: a clean photo
    and a moire photo's raw spectra rendered near-identically to the eye,
    both dominated by the same smooth central falloff every real image
    produces. Circling the actual peak fixes this the same way this
    codebase's other "show me why" features do (a literal bbox, not a
    vibe) — see mm_tampering.py, or the direct user feedback that drove
    steganography's bit-plane visualization to be captioned more concretely.

    The circled point is found independently of the detector's own 1D
    per-angle Radon sweep (see moire_spike_ratio) — it's simply the
    brightest pixel in the 2D spectrum outside a small DC-centered disk,
    plus its symmetric mirror point (a real image's spectrum is always
    point-symmetric about DC). This reliably lands on the true injected
    frequency for a clearly-detected case (verified: matches the expected
    bin location for a known synthetic pattern), but is a DIFFERENT
    algorithm from the actual detector, so for a marginal/low-confidence
    case the circle may land on ordinary image content rather than the
    exact frequency the Radon sweep responded to — illustrative, not a
    precise attribution."""
    img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("L")
    w, h = img.size
    scale = min(1.0, max_dim / max(w, h))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    gray = np.asarray(img, dtype=np.float32)
    window = np.outer(np.hanning(gray.shape[0]), np.hanning(gray.shape[1]))
    spectrum = np.abs(np.fft.fftshift(np.fft.fft2(gray * window)))
    logmag = np.log1p(spectrum)
    normalized = (logmag - logmag.min()) / (logmag.max() - logmag.min() + 1e-6)
    out = (normalized * 255).astype(np.uint8)
    rgb = Image.fromarray(out, mode="L").convert("RGB")

    hh, ww = logmag.shape
    cy, cx = hh // 2, ww // 2
    yy, xx = np.mgrid[0:hh, 0:ww]
    dc_r = _MARKER_DC_EXCLUDE_FRAC * min(hh, ww)
    dc_mask = (yy - cy) ** 2 + (xx - cx) ** 2 <= dc_r ** 2
    searchable = logmag.copy()
    searchable[dc_mask] = -1
    py, px = np.unravel_index(np.argmax(searchable), searchable.shape)

    draw = ImageDraw.Draw(rgb)
    r = _MARKER_RADIUS
    for my, mx in [(py, px), (2 * cy - py, 2 * cx - px)]:
        draw.ellipse([mx - r, my - r, mx + r, my + r], outline=_MARKER_COLOR, width=2)

    buf = io.BytesIO()
    rgb.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@router.post("/mm-moire/visualize")
def visualize_moire(body: VisualizeRequest):
    """Returns {"image": <b64>} — the illustrative FFT spectrum image (see
    extract_moire_spectrum_visualization). Computed on demand, not at
    ingest, since it's only ever needed if a user opens the "Possible
    screen/scan pattern" dropdown option."""
    return {"image": extract_moire_spectrum_visualization(body.image)}
