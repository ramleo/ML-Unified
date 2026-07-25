"""Blur/quality detection via Fourier high-frequency energy (MMRAG-01).

A sharp image carries strong high-frequency content (edges, texture); a
blurry one is dominated by low frequencies. Pure NumPy FFT check — no
model, no GPU — run once per standalone image or PDF figure page at
upload time, so a low-quality scan/photo can be flagged before it
silently degrades OCR/caption accuracy downstream.

Scores the fraction of total spectral energy sitting outside a low-frequency
disc (a ratio, not a raw magnitude) — that normalization is deliberate: raw
high-frequency magnitude scales with image size/contrast and misclassifies
plain screenshots as blurry. The ratio held up across real UI screenshots,
synthetic line-art, and text/photo textures during calibration (see Part 208
session notes): sharp content generally lands ~0.6-0.9, a clearly noticeable
blur drops it to ~0.1-0.3. A flat, sparse-but-sharp image (e.g. a mostly
blank diagram) can still read low — this is a no-reference heuristic, not a
certainty, so treat "blurry" as "worth a second look," never a hard fact.
"""
from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image

_LOW_FREQ_RADIUS_RATIO = 0.08  # fraction of the shorter dimension masked out
                               # as "low frequency" (DC + broad shapes) before
                               # measuring the remaining high-frequency energy
_BLUR_THRESHOLD = 0.35
_MAX_SIDE = 512  # downscale cap — sharpness signal doesn't need full resolution


def blur_score(png_b64: str) -> dict:
    """Returns {"score": float, "blurry": bool}. Higher score = sharper.
    score is the fraction (0-1) of spectral energy outside the low-frequency disc."""
    img = Image.open(io.BytesIO(base64.b64decode(png_b64))).convert("L")
    img.thumbnail((_MAX_SIDE, _MAX_SIDE))
    arr = np.asarray(img, dtype=np.float32)

    magnitude = np.abs(np.fft.fftshift(np.fft.fft2(arr)))
    h, w = magnitude.shape
    cy, cx = h // 2, w // 2
    radius = int(min(h, w) * _LOW_FREQ_RADIUS_RATIO)
    yy, xx = np.ogrid[:h, :w]
    mask = (yy - cy) ** 2 + (xx - cx) ** 2 > radius ** 2

    total = magnitude.sum()
    score = float(magnitude[mask].sum() / total) if total else 0.0
    return {"score": round(score, 3), "blurry": score < _BLUR_THRESHOLD}
