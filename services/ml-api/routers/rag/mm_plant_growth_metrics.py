"""Per-frame health/detail metrics beyond leaf area.

area_fraction (mm_plant_growth.py) only tells you how much of the frame is
green — it can't distinguish a healthy plant from one that's the same size
but turning yellow, and it can't tell you if a plant grew more LEAVES
versus just bigger existing ones. These two metrics fill those gaps,
computed on the same leaf mask mm_plant_growth.py already produces, no new
model or API call:

- greenness_index: an RGB-only vegetation index (NGRDI) used as a
  chlorophyll/health proxy — smartphone cameras have no near-infrared
  channel, so research-grade multispectral vegetation indices aren't
  available, but RGB-only indices like NGRDI are an established substitute
  for exactly this reason.
- count_leaves: individual leaf count via connected components — a
  DIFFERENT granularity than mm_plant_growth_blobs.detect_plant_blobs
  (which separates distinct PLANTS and deliberately closes gaps to merge
  one plant's leaves into a single box). Leaf counting must NOT do that
  closing, or every leaf would merge into one blob and always count as 1.
"""
from __future__ import annotations

import cv2
import numpy as np

_LEAF_MIN_AREA_FRACTION = 0.004  # ignore leaf-count blobs smaller than this fraction of the region — noise flecks, not a real leaf


def greenness_index(rgb: np.ndarray, mask: np.ndarray) -> float:
    """Mean NGRDI ((G-R)/(G+R)) over the leaf-masked pixels. Roughly
    -1..1, higher = more vividly green/healthy foliage. A drop between
    frames of the SAME plant/crop can flag yellowing or stress that the
    area measurement alone would miss entirely, since a plant can stay the
    same size while its foliage discolors."""
    if not mask.any():
        return 0.0
    r = rgb[..., 0].astype(np.float32)
    g = rgb[..., 1].astype(np.float32)
    denom = g + r
    ngrdi = np.divide(g - r, denom, out=np.zeros_like(denom), where=denom > 0)
    return float(ngrdi[mask].mean())


def count_leaves(mask: np.ndarray) -> int:
    """Connected-component count directly on the leaf mask — deliberately
    no morphological CLOSING (unlike detect_plant_blobs, which closes gaps
    on purpose to merge one plant's leaves into a single box): here the
    goal is the opposite, counting individual leaves separately. A light
    OPENING only removes single-pixel noise without merging adjacent
    leaves together."""
    h, w = mask.shape[:2]
    binary = mask.astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
    min_area = _LEAF_MIN_AREA_FRACTION * h * w
    return sum(1 for label in range(1, num_labels) if stats[label, cv2.CC_STAT_AREA] >= min_area)
