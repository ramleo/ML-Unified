"""Plant growth quantification from an uploaded timelapse photo series.

Pure local image processing, no external API and no budget cost — same
category as mm_watermark.py, unlike mm_ai_fill.py/mm_text_to_image.py.

Leaf/plant area is measured with a simple HSV green-hue threshold, not a
segmentation model: green foliage occupies a fairly narrow, predictable hue
band regardless of lighting, and this needs to run on up to 30 frames per
request cheaply. `area_fraction` (leaf pixels / total pixels of whichever
region was measured) is only meaningful RELATIVE to other frames of the SAME
photo (consistent framing, similar distance/zoom) — it is not a real-world
area measurement, so growth is reported as a percentage change from the
first frame, not an absolute unit.

Auto-detect (`auto_detect=True`, the default) reuses the existing 601-class
object detector (mm_objects.py's detect_objects(), already zero-cost local
ONNX — same "Plant"/"Houseplant"/"Flowerpot" classes it already knows,
nothing new trained) to find and crop individual plants in a photo BEFORE
measuring, the same crop-then-remeasure pattern mm_objects.py already uses
for person->face and vehicle->plate. Without this, two plants in one photo
would silently blend into one meaningless combined area_fraction.
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

from routers.rag.mm_objects import detect_objects

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

_PLANT_LABELS = {"Plant", "Houseplant", "Flowerpot"}
_CROP_PAD_RATIO = 0.15  # same ratio mm_objects.py uses for its own person/vehicle crops


def _leaf_mask(rgb: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    lower = np.array([_HUE_LOW, _SAT_MIN, _VAL_MIN])
    upper = np.array([_HUE_HIGH, 255, 255])
    return cv2.inRange(hsv, lower, upper) > 0


def _leaf_area_and_mask(rgb: np.ndarray) -> dict:
    """Core measurement over an already-decoded RGB array — shared by the
    whole-frame path and the per-crop auto-detect path so a crop never has
    to round-trip through base64 just to reuse this logic."""
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


def measure_leaf_area(b64: str) -> dict:
    """Returns {"ok": True, "area_fraction": float, "mask_preview": <b64 PNG>}
    on success, or {"ok": False, "error": <str>} if the image can't be decoded."""
    try:
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        return _leaf_area_and_mask(np.asarray(img))
    except Exception as exc:
        logger.warning("Plant growth leaf-area measurement failed: %s", exc)
        return {"ok": False, "error": "could not measure this frame"}


def _detect_plant_boxes(b64: str) -> list[list[float]]:
    """Normalized [x,y,w,h] boxes for Plant/Houseplant/Flowerpot detections,
    sorted left-to-right (x-center ascending) — the ordering later frames
    are matched against, relying on the same "consistent framing across the
    series" assumption this tool already requires for growth% to be
    meaningful at all. Empty list on no detections or any failure;
    detect_objects() itself never raises (returns ([], 0) on failure)."""
    objects, _ = detect_objects(b64)
    boxes = [o["bbox"] for o in objects if o["label"] in _PLANT_LABELS]
    boxes.sort(key=lambda b: b[0] + b[2] / 2)
    return boxes


def _crop(img: Image.Image, bbox: list[float], pad_ratio: float = _CROP_PAD_RATIO) -> np.ndarray:
    w, h = img.size
    x0, y0, bw, bh = bbox[0] * w, bbox[1] * h, bbox[2] * w, bbox[3] * h
    pad_x, pad_y = bw * pad_ratio, bh * pad_ratio
    left = max(0, int(x0 - pad_x))
    top = max(0, int(y0 - pad_y))
    right = min(w, int(x0 + bw + pad_x))
    bottom = min(h, int(y0 + bh + pad_y))
    return np.asarray(img.crop((left, top, right, bottom)))


class PlantGrowthFrame(BaseModel):
    image: str  # b64 image, any common format
    label: str = ""


class PlantGrowthRequest(BaseModel):
    frames: list[PlantGrowthFrame]
    auto_detect: bool = True


def _measure_frame(img: Image.Image, region: np.ndarray | None) -> dict:
    """region=None measures the whole frame; otherwise measures the given
    cropped array. Never raises — a failure here just marks this one
    frame/track entry low_confidence rather than 500ing the whole batch."""
    try:
        rgb = np.asarray(img) if region is None else region
        return _leaf_area_and_mask(rgb)
    except Exception as exc:
        logger.warning("Plant growth region measurement failed: %s", exc)
        return {"ok": False, "error": "could not measure this region"}


def _to_frame_entry(result: dict, label: str) -> dict:
    if not result.get("ok"):
        return {"label": label, "area_fraction": 0.0, "mask_preview": None, "low_confidence": True}
    return {
        "label": label,
        "area_fraction": result["area_fraction"],
        "mask_preview": result["mask_preview"],
        "low_confidence": result["area_fraction"] < _LOW_CONFIDENCE_THRESHOLD,
    }


def _finalize_track(entries: list[dict]) -> dict | None:
    if not entries:
        return None
    baseline = entries[0]["area_fraction"]
    frames_out = []
    for e in entries:
        growth_pct = ((e["area_fraction"] - baseline) / baseline * 100.0) if baseline > 0 else 0.0
        frames_out.append({**e, "growth_pct": round(growth_pct, 1)})
    return {"frames": frames_out}


@router.post("/mm-plant-growth")
def plant_growth_endpoint(body: PlantGrowthRequest):
    if not (_MIN_FRAMES <= len(body.frames) <= _MAX_FRAMES):
        raise HTTPException(
            status_code=400,
            detail=f"provide between {_MIN_FRAMES} and {_MAX_FRAMES} frames",
        )
    for i, frame in enumerate(body.frames):
        if not frame.image.strip():
            raise HTTPException(status_code=400, detail=f"frame {i} is missing an image")

    labels = [frame.label.strip() or f"Day {i}" for i, frame in enumerate(body.frames)]
    imgs: list[Image.Image | None] = []
    for frame in body.frames:
        try:
            imgs.append(Image.open(io.BytesIO(base64.b64decode(frame.image))).convert("RGB"))
        except Exception as exc:
            logger.warning("Plant growth could not decode a frame: %s", exc)
            imgs.append(None)

    # track_count comes from frame 0 alone (it's already the growth
    # baseline every other frame is measured against) — later frames only
    # ever supply UP TO that many boxes, matched by left-to-right position.
    track_count = 1
    frame0_boxes: list[list[float]] = []
    if body.auto_detect and imgs[0] is not None:
        frame0_boxes = _detect_plant_boxes(body.frames[0].image)
        if frame0_boxes:
            track_count = len(frame0_boxes)

    tracks: list[list[dict]] = [[] for _ in range(track_count)]
    for i, (frame, img, label) in enumerate(zip(body.frames, imgs, labels)):
        if img is None:
            for t in range(track_count):
                tracks[t].append(_to_frame_entry({"ok": False}, label))
            continue

        if track_count == 1 and not frame0_boxes:
            tracks[0].append(_to_frame_entry(_measure_frame(img, None), label))
            continue

        boxes = frame0_boxes if i == 0 else _detect_plant_boxes(frame.image)
        for t in range(track_count):
            if t < len(boxes):
                region = _crop(img, boxes[t])
                tracks[t].append(_to_frame_entry(_measure_frame(img, region), label))
            else:
                # This plant wasn't found in this frame (occluded, moved
                # out of shot) — an honest "missing" signal, not a
                # fabricated 0%-growth data point.
                tracks[t].append({"label": label, "area_fraction": 0.0, "mask_preview": None, "low_confidence": True})

    plants = []
    for idx, entries in enumerate(tracks):
        finalized = _finalize_track(entries)
        if finalized:
            plants.append({"index": idx, **finalized})

    return {"plants": plants}
