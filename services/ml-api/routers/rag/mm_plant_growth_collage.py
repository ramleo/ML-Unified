"""Collage-seam detection for mm_plant_growth.py.

A single photo with 2+ detected plants is ambiguous: several distinct
plants coexisting right now, or a before/after COLLAGE of one plant — two
separate photos stitched into one file, a common "plant progress" post
format. Object detection alone can't tell these apart (a bounding box says
WHAT is in it, never whether two boxes are the same subject at a different
time). This module adds a second, independent CV-only check: a collage
almost always has a visible SEAM — a straight line where a sharp edge
coincides with a color/exposure jump, because the two halves came from
different shots (different lighting/white-balance/scene), which a single
continuous photo does not have.

Split out of mm_plant_growth.py to keep that file under the project's
400-line limit.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

# Deliberately conservative (real seam + real color jump + a centered plant
# on both sides all required together) — a false positive here silently
# mis-splits a genuine single photo, which is worse than falling back to
# compare mode on a real collage we missed.
_SEAM_SEARCH_MARGIN = 0.05  # search window: midline ± this fraction of the dimension
_SEAM_EDGE_RATIO = 3.0      # seam gradient must exceed this multiple of the image's median gradient
_SEAM_BASELINE_FLOOR = 1.0  # floor for the median-gradient baseline so a near-flat image doesn't
                             # divide-by-near-zero and trivially "pass" on any nonzero edge
_SEAM_COLOR_DIFF_MIN = 18.0  # minimum summed mean-RGB difference (0-255 scale) between the two halves


def _seam_candidate(gray: np.ndarray, axis: int, size: int) -> int | None:
    """Finds the strongest straight edge near the midline along `axis`
    (1=vertical seam via columns, 0=horizontal seam via rows). Returns the
    seam's pixel position, or None if nothing there is meaningfully sharper
    than the rest of the image (i.e. no seam, just ordinary photo detail)."""
    if axis == 1:
        grad = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)).mean(axis=0)
    else:
        grad = np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)).mean(axis=1)

    lo = int(size * (0.5 - _SEAM_SEARCH_MARGIN))
    hi = int(size * (0.5 + _SEAM_SEARCH_MARGIN))
    if hi <= lo:
        return None
    window = grad[lo:hi]
    peak_idx = lo + int(np.argmax(window))
    peak_val = grad[peak_idx]

    baseline = max(float(np.median(grad)), _SEAM_BASELINE_FLOOR)
    if peak_val < baseline * _SEAM_EDGE_RATIO:
        return None
    return peak_idx


def _color_jump_at(rgb: np.ndarray, orientation: str, position: int) -> bool:
    side_a = rgb[:, :position] if orientation == "vertical" else rgb[:position, :]
    side_b = rgb[:, position:] if orientation == "vertical" else rgb[position:, :]
    if side_a.size == 0 or side_b.size == 0:
        return False
    mean_a = side_a.reshape(-1, 3).mean(axis=0)
    mean_b = side_b.reshape(-1, 3).mean(axis=0)
    return float(np.abs(mean_a - mean_b).sum()) >= _SEAM_COLOR_DIFF_MIN


def _plant_centered_in_each_half(boxes: list[list[float]], orientation: str, frac: float) -> bool:
    """Requires a detected plant box roughly centered in BOTH halves (not
    just anywhere) so a photo that merely has a strong background line (a
    doorframe, a wall edge) isn't mistaken for a collage seam."""
    axis = 0 if orientation == "vertical" else 1
    centers = [b[axis] + b[axis + 2] / 2 for b in boxes]

    def _has_center_in(lo: float, hi: float) -> bool:
        pad = (hi - lo) * 0.2
        return any(lo + pad <= c <= hi - pad for c in centers)

    return _has_center_in(0.0, frac) and _has_center_in(frac, 1.0)


def detect_collage_seam(rgb: np.ndarray, boxes: list[list[float]]) -> dict | None:
    """Looks for a before/after collage seam: a straight line where a sharp
    edge coincides with a color/exposure jump AND a plant is centered on
    each side. Only 2-panel vertical or horizontal splits are considered —
    not grids — since that covers every real collage seen so far; returns
    None (caller falls back to compare mode) on anything less than a
    confident match on all three signals."""
    if len(boxes) < 2:
        return None
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    h, w = gray.shape

    for orientation, size, axis in (("vertical", w, 1), ("horizontal", h, 0)):
        position = _seam_candidate(gray, axis=axis, size=size)
        if position is None:
            continue
        if not _color_jump_at(rgb, orientation, position):
            continue
        if not _plant_centered_in_each_half(boxes, orientation, position / size):
            continue
        return {"orientation": orientation, "position": position}
    return None


def split_at_seam(img: Image.Image, seam: dict) -> tuple[np.ndarray, np.ndarray]:
    arr = np.asarray(img)
    position = seam["position"]
    if seam["orientation"] == "vertical":
        return arr[:, :position], arr[:, position:]
    return arr[:position, :], arr[position:, :]
