"""Blur/quality detection via high-frequency edge energy (MMRAG-01).

A sharp image carries strong high-frequency content (edges, texture); a
blurry one is dominated by low frequencies. Uses the variance of the
Laplacian (a discrete high-pass filter — the classic, well-established
no-reference blur check) rather than a raw FFT energy ratio: an earlier
version of this file used an FFT-based ratio that looked fine on synthetic
Gaussian-blur tests but turned out to be NON-MONOTONIC on real photos —
past a certain blur radius the score climbed back up, scoring a heavily
blurred photo as "sharper" than a mildly blurred one (root cause: extreme
blur pushes almost all energy into a couple of near-DC bins, and FFT edge/
padding effects reintroduce spurious high-frequency content at that
extreme). Variance-of-Laplacian doesn't have that failure mode — verified
monotonic across real photos (grace_hopper.jpg, sklearn's china/flower
samples) from unblurred through radius-40 Gaussian blur.

Threshold calibrated on log1p(variance) (see Part 208/209 session notes):
sharp photos, UI screenshots, and even sparse line-art all score >=5.3;
any noticeably blurred version (Gaussian radius >=2-3, or a real
out-of-focus photo) drops to <=2.6. No model, no GPU — cheap enough to run
per figure/image at upload time.
"""
from __future__ import annotations

import base64
import io

import cv2
import numpy as np
from PIL import Image

_BLUR_THRESHOLD = 4.0  # on log1p(Laplacian variance) — see calibration above
_MAX_SIDE = 512  # downscale cap — sharpness signal doesn't need full resolution


def blur_score(png_b64: str) -> dict:
    """Returns {"score": float, "blurry": bool}. Higher score = sharper.
    score is log1p(variance of the Laplacian) of the grayscale image."""
    img = Image.open(io.BytesIO(base64.b64decode(png_b64))).convert("L")
    img.thumbnail((_MAX_SIDE, _MAX_SIDE))
    arr = np.asarray(img, dtype=np.uint8)

    variance = cv2.Laplacian(arr, cv2.CV_64F).var()
    score = float(np.log1p(variance))
    return {"score": round(score, 2), "blurry": score < _BLUR_THRESHOLD}
