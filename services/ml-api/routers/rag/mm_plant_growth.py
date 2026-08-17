"""Plant growth quantification from an uploaded timelapse photo series.

Pure local image processing, no external API and no budget cost — same
category as mm_watermark.py, unlike mm_ai_fill.py/mm_text_to_image.py.

Leaf/plant area is measured with a simple HSV green-hue threshold, not a
segmentation model: green foliage occupies a fairly narrow, predictable hue
band regardless of lighting, and this needs to run on up to 30 frames per
request cheaply. `area_fraction` (leaf pixels / total pixels) is only
meaningful RELATIVE to other frames of the SAME photo (consistent framing,
similar distance/zoom) — it is not a real-world area measurement, so growth
is reported as a percentage change from the first frame, not an absolute unit.
"""
from __future__ import annotations

import base64
import io
import logging

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

_MIN_FRAMES = 2
_MAX_FRAMES = 30
_LOW_CONFIDENCE_THRESHOLD = 0.01  # area_fraction below this = likely no plant found

# OpenCV hue is 0-180. This band covers yellow-green through blue-green
# foliage; saturation/value floors exclude near-black shadow and
# near-white blown highlights, which would otherwise fall inside the hue
# band by accident on a desaturated/overexposed patch.
_HUE_LOW, _HUE_HIGH = 30, 95
_SAT_MIN, _VAL_MIN = 40, 40

_MASK_OVERLAY_COLOR = np.array([34, 197, 94])  # matches frontend accent #22c55e-ish green
_MASK_OVERLAY_ALPHA = 0.45


def _leaf_mask(rgb: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    lower = np.array([_HUE_LOW, _SAT_MIN, _VAL_MIN])
    upper = np.array([_HUE_HIGH, 255, 255])
    return cv2.inRange(hsv, lower, upper) > 0


def measure_leaf_area(b64: str) -> dict:
    """Returns {"ok": True, "area_fraction": float, "mask_preview": <b64 PNG>}
    on success, or {"ok": False, "error": <str>} if the image can't be decoded."""
    try:
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        rgb = np.asarray(img)
        mask = _leaf_mask(rgb)
        area_fraction = float(mask.sum()) / mask.size

        overlay = rgb.copy()
        overlay[mask] = (
            overlay[mask] * (1 - _MASK_OVERLAY_ALPHA) + _MASK_OVERLAY_COLOR * _MASK_OVERLAY_ALPHA
        ).astype(np.uint8)
        buf = io.BytesIO()
        Image.fromarray(overlay).save(buf, format="PNG")

        return {
            "ok": True,
            "area_fraction": area_fraction,
            "mask_preview": base64.b64encode(buf.getvalue()).decode(),
        }
    except Exception as exc:
        logger.warning("Plant growth leaf-area measurement failed: %s", exc)
        return {"ok": False, "error": "could not measure this frame"}


class PlantGrowthFrame(BaseModel):
    image: str  # b64 image, any common format
    label: str = ""


class PlantGrowthRequest(BaseModel):
    frames: list[PlantGrowthFrame]


@router.post("/mm-plant-growth")
def plant_growth_endpoint(body: PlantGrowthRequest):
    if not (_MIN_FRAMES <= len(body.frames) <= _MAX_FRAMES):
        raise HTTPException(
            status_code=400,
            detail=f"provide between {_MIN_FRAMES} and {_MAX_FRAMES} frames",
        )

    measured = []
    for i, frame in enumerate(body.frames):
        if not frame.image.strip():
            raise HTTPException(status_code=400, detail=f"frame {i} is missing an image")
        result = measure_leaf_area(frame.image)
        label = frame.label.strip() or f"Day {i}"
        if not result.get("ok"):
            measured.append({
                "label": label,
                "area_fraction": 0.0,
                "mask_preview": None,
                "low_confidence": True,
            })
            continue
        measured.append({
            "label": label,
            "area_fraction": result["area_fraction"],
            "mask_preview": result["mask_preview"],
            "low_confidence": result["area_fraction"] < _LOW_CONFIDENCE_THRESHOLD,
        })

    baseline = measured[0]["area_fraction"]
    frames_out = []
    for m in measured:
        growth_pct = (
            ((m["area_fraction"] - baseline) / baseline * 100.0) if baseline > 0 else 0.0
        )
        frames_out.append({**m, "growth_pct": round(growth_pct, 1)})

    return {"frames": frames_out}
