"""Leaf-mask connected-component fallback for plant detection.

The general 601-class object detector (mm_objects.py) can under-detect
plants it wasn't trained to recognize well — small/young seedlings,
stylized illustrations, or anything that just doesn't resemble its
"Houseplant"/"Flowerpot" training examples — sometimes finding only 1 box
(or merging several plants into one) where a human clearly sees more.

detect_plant_blobs() doesn't depend on the detector's training distribution
at all: it finds distinct green blobs directly via connected-component
analysis on mm_plant_growth.py's own HSV leaf mask, needing only that
foliage is green and plants are spatially separated. Called only as a
fallback (mm_plant_growth._detect_plant_boxes()) when the object detector
finds fewer than 2 plants, since it's noisier than the detector on real
photos with background greenery the detector correctly ignores.

Split out of mm_plant_growth.py to keep that file under the project's
400-line limit.
"""
from __future__ import annotations

import cv2
import numpy as np

_MIN_AREA_FRACTION = 0.003  # ignore mask blobs smaller than this fraction of the image — noise, not a plant
_CLOSE_KERNEL_FRACTION = 0.015  # morphological closing kernel, relative to the image's shorter side


def detect_plant_blobs(mask: np.ndarray) -> list[list[float]]:
    """mask: boolean/0-1 HSV leaf mask (h, w), as produced by
    mm_plant_growth._leaf_mask(). Returns normalized [x,y,w,h] boxes,
    sorted left-to-right, one per sufficiently large connected green blob.
    A morphological close first bridges small gaps WITHIN one plant's own
    foliage (a shadow line between two leaves) so it isn't counted as two
    separate plants."""
    h, w = mask.shape[:2]
    binary = mask.astype(np.uint8)

    kernel_size = max(3, int(min(h, w) * _CLOSE_KERNEL_FRACTION))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    min_area = _MIN_AREA_FRACTION * h * w

    boxes = []
    for label in range(1, num_labels):  # label 0 is the background component
        x, y, bw, bh, area = stats[label]
        if area < min_area:
            continue
        boxes.append([x / w, y / h, bw / w, bh / h])

    boxes.sort(key=lambda b: b[0] + b[2] / 2)
    return boxes
