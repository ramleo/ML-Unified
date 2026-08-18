"""Single-photo, multiple-plants comparison mode for the Plant Growth
Quantification tool — split out of mm_plant_growth.py to keep that file
under the project's 400-line cap.

Compares plants' CURRENT leaf area to each other (relative_pct: largest
plant = 100%), not a time-series growth % — there's no baseline to grow from
with only one photo, so this is a genuinely different aggregation from
growth mode, not a degenerate case of it.
"""
from __future__ import annotations

import base64
import io
import logging

from fastapi import HTTPException
from PIL import Image

logger = logging.getLogger(__name__)


def compare_single_photo(frame, auto_detect: bool, low_confidence_threshold: float) -> dict:
    """Uses each plant's ABSOLUTE leaf_pixel_count for the comparison, not
    its area_fraction (leaf pixels / that plant's OWN crop size) — a small
    plant's tight crop and a large plant's tight crop can land on nearly
    identical fractions (both crops are mostly foliage), which would hide
    the real size difference the crop size itself already encodes. Absolute
    pixel counts are only comparable because all plants share one photo, one
    camera distance — unlike growth% across frames, where only the SAME
    plant's fraction over time is used (crop size for one plant is fairly
    stable frame to frame, unlike comparing crops of different plants)."""
    from routers.rag.mm_plant_growth import _crop, _detect_plant_boxes, _measure_frame

    if not auto_detect:
        raise HTTPException(
            status_code=400,
            detail="Auto-detect must be on to compare plants within a single photo.",
        )
    try:
        img = Image.open(io.BytesIO(base64.b64decode(frame.image))).convert("RGB")
    except Exception as exc:
        logger.warning("Plant growth could not decode the photo: %s", exc)
        raise HTTPException(status_code=400, detail="could not decode this photo")

    boxes = _detect_plant_boxes(frame.image)
    if len(boxes) < 2:
        raise HTTPException(
            status_code=400,
            detail=(
                "Found fewer than 2 plants in this photo to compare — try a photo with "
                "multiple distinct plants, or add a second photo to measure growth over time instead."
            ),
        )

    measured = [_measure_frame(img, _crop(img, box)) for box in boxes]
    pixel_counts = [m["leaf_pixel_count"] if m.get("ok") else 0 for m in measured]
    max_count = max(pixel_counts, default=0)

    plants = []
    for idx, (m, count) in enumerate(zip(measured, pixel_counts)):
        area_fraction = m["area_fraction"] if m.get("ok") else 0.0
        plants.append({
            "index": idx,
            "area_fraction": area_fraction,
            "relative_pct": round(count / max_count * 100.0, 1) if max_count > 0 else 0.0,
            "mask_preview": m.get("mask_preview") if m.get("ok") else None,
            "low_confidence": (not m.get("ok")) or area_fraction < low_confidence_threshold,
            "greenness_index": m.get("greenness_index", 0.0) if m.get("ok") else 0.0,
            "leaf_count": m.get("leaf_count", 0) if m.get("ok") else 0,
            "leaf_pixel_count": count,
        })

    return {"mode": "compare", "plants": plants}
