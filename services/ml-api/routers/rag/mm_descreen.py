"""FFT descreen — remove a periodic halftone / moire / scan-line pattern from a
scanned or screen-photographed image before it is read.

Printed material is reproduced with a halftone screen (a regular grid of dots);
scanning or photographing it interferes with the sensor grid and leaves a
periodic ripple over the whole frame. That ripple is a small number of sharp,
isolated *spikes* in the image's 2D Fourier spectrum, sitting well away from the
low-frequency centre where the real picture content lives. Removing them is a
classic, non-generative operation: notch out those spikes and transform back.

This is the counterpart to mm_moire.py, which only *detects* the pattern (a
whole-image verdict). Here we actually remove it, and — unlike mm_deblur.py,
which uses a paid generative model that can invent detail — this cannot
hallucinate: it only subtracts periodic energy that is genuinely present, so a
photo with no screen pattern comes back essentially unchanged (removed = 0).

The spike test is the 2D analogue of mm_moire's: magnitude divided by a local
median, so an isolated peak that stands far above its neighbourhood is kept and
the smooth spectral falloff every real image has is not. Peak-finding runs on a
windowed luminance spectrum; the soft notch mask it produces is applied to each
un-windowed colour channel, so edges are not darkened and colour is preserved.
"""
from __future__ import annotations

import base64
import io
import logging

import numpy as np
from fastapi import APIRouter
from PIL import Image, ImageDraw
from pydantic import BaseModel
from scipy.ndimage import median_filter

from security.file_gate import gate_or_raise

logger = logging.getLogger(__name__)
router = APIRouter()

_WORK_DIM = 1024        # cap the long edge; bounds FFT + median-filter cost on CPU
_DC_EXCLUDE_FRAC = 0.045  # protect this radius of low frequencies (real content)
_NBHD = 9               # local-median window for the spike-vs-neighbourhood ratio
_RATIO_THRESH = 10.0    # a bin must stand this far above its local median to notch.
# Measured against synthetic ground truth: a realistic clean image (smooth
# content + mild texture/noise) tops out around 5x, while a genuine halftone
# screen frequency stands at hundreds of x — 10x sits with clear margin between
# them. The tradeoff is honest and disclosed: a very faint screen may fall below
# it, and a strong *real* repeating texture (fabric, brick) can exceed it, since
# a notch filter cannot tell a print screen from genuinely periodic content.
_MAX_NOTCHES = 16       # cap notched peaks (halftone has few dominant ones + mirrors)
_NOTCH_SIGMA = 2.4      # radius (px) of the soft gaussian notch around each spike
_MIN_DIM = 64
_MARKER_RADIUS = 9
_MARKER_COLOR = (255, 80, 60)


def _prep_rgb(raw: bytes) -> np.ndarray | None:
    """Decode to an RGB float array, capped at _WORK_DIM on the long edge."""
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = img.size
    if w < _MIN_DIM or h < _MIN_DIM:
        return None
    scale = min(1.0, _WORK_DIM / max(w, h))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    return np.asarray(img, dtype=np.float32)


def _find_screen_peaks(lum: np.ndarray) -> list[tuple[int, int]]:
    """Return (row, col) of periodic spikes in lum's centred 2D spectrum.

    A spike is a local maximum whose magnitude is _RATIO_THRESH× its local
    median, outside a DC-centred disk. Each kept peak is added together with its
    point-symmetric mirror (a real image's spectrum is symmetric about DC).
    """
    h, w = lum.shape
    window = np.outer(np.hanning(h), np.hanning(w))
    spec = np.abs(np.fft.fftshift(np.fft.fft2(lum * window)))
    local_med = median_filter(spec, size=_NBHD)
    ratio = spec / (local_med + 1e-6)

    cy, cx = h // 2, w // 2
    yy, xx = np.mgrid[0:h, 0:w]
    dc_r = _DC_EXCLUDE_FRAC * min(h, w)
    ratio[(yy - cy) ** 2 + (xx - cx) ** 2 <= dc_r ** 2] = 0.0

    peaks: list[tuple[int, int]] = []
    work = ratio.copy()
    for _ in range(_MAX_NOTCHES):
        idx = int(np.argmax(work))
        py, px = divmod(idx, w)
        if work[py, px] < _RATIO_THRESH:
            break
        peaks.append((py, px))
        peaks.append((2 * cy - py, 2 * cx - px))  # mirror
        # blank a small area so the next argmax finds a distinct spike
        r = 2 * _NBHD
        for my, mx in (peaks[-2], peaks[-1]):
            work[max(0, my - r):my + r, max(0, mx - r):mx + r] = 0.0
    return peaks


def _notch_mask(shape: tuple[int, int], peaks: list[tuple[int, int]]) -> np.ndarray:
    """A multiplicative mask (1 everywhere, a soft gaussian dip to ~0 at each
    peak) for the centred spectrum. Soft rather than a hard zero to avoid the
    ringing a sharp cutoff would leave in the reconstructed image."""
    h, w = shape
    mask = np.ones((h, w), dtype=np.float32)
    if not peaks:
        return mask
    yy, xx = np.mgrid[0:h, 0:w]
    for py, px in peaks:
        d2 = (yy - py) ** 2 + (xx - px) ** 2
        mask *= 1.0 - np.exp(-d2 / (2.0 * _NOTCH_SIGMA ** 2))
    return mask


def _apply_notch(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Apply the centred-spectrum notch mask to each colour channel and invert."""
    out = np.empty_like(rgb)
    for c in range(3):
        f = np.fft.fftshift(np.fft.fft2(rgb[:, :, c]))
        f *= mask
        out[:, :, c] = np.real(np.fft.ifft2(np.fft.ifftshift(f)))
    return np.clip(out, 0, 255)


def _to_b64_png(arr: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(arr.astype(np.uint8), mode="RGB").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _spectrum_png(lum: np.ndarray, peaks: list[tuple[int, int]]) -> str:
    """The image's log-magnitude spectrum with every notched peak circled, so a
    viewer can see what was removed and why (same 'show the evidence' pattern as
    mm_moire's visualiser)."""
    window = np.outer(np.hanning(lum.shape[0]), np.hanning(lum.shape[1]))
    logmag = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(lum * window))))
    norm = (logmag - logmag.min()) / (logmag.max() - logmag.min() + 1e-6)
    rgb = Image.fromarray((norm * 255).astype(np.uint8), mode="L").convert("RGB")
    draw = ImageDraw.Draw(rgb)
    r = _MARKER_RADIUS
    for py, px in peaks:
        draw.ellipse([px - r, py - r, px + r, py + r], outline=_MARKER_COLOR, width=2)
    return _to_b64_png(np.asarray(rgb, dtype=np.uint8))


def descreen(raw: bytes) -> dict:
    """Remove periodic screen/halftone patterns. Returns the cleaned image, the
    number of frequency peaks removed, and a spectrum image marking them. On a
    photo with no periodic pattern, removed = 0 and the image is returned as-is
    (re-encoded), which is the honest result — nothing was there to remove."""
    rgb = _prep_rgb(raw)
    if rgb is None:
        return {"ok": False, "error": "Image too small (min 64×64) or unreadable."}
    lum = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    peaks = _find_screen_peaks(lum)
    mask = _notch_mask(lum.shape, peaks)
    cleaned = _apply_notch(rgb, mask) if peaks else rgb
    return {
        "ok": True,
        "cleaned": _to_b64_png(cleaned),
        "spectrum": _spectrum_png(lum, peaks),
        "removed": len(peaks) // 2,  # peaks are stored with their mirrors
        "width": int(rgb.shape[1]),
        "height": int(rgb.shape[0]),
    }


class DescreenRequest(BaseModel):
    image: str  # b64-encoded image


@router.post("/mm-descreen")
def descreen_endpoint(body: DescreenRequest):
    raw = base64.b64decode(body.image)
    gate_or_raise(raw, path="/rag/mm-descreen")
    return descreen(raw)
