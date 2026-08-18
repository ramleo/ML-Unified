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

The object detector can under-detect plants it wasn't trained to recognize
well — small/young seedlings, stylized illustrations — sometimes finding
only 1 box (or merging several into one) where a human clearly sees more.
_detect_plant_boxes() falls back to mm_plant_growth_blobs.detect_plant_
blobs() in that case: connected-component analysis directly on this tool's
own HSV leaf mask, which only needs foliage to be green and spatially
separate, not recognizable to a general-purpose detector.

A single photo with 2+ detected plants is ambiguous: it could be several
distinct plants coexisting right now (compare mode: rank current sizes
against each other), or it could be a before/after COLLAGE of one plant —
two separate photos stitched into one file, a common "plant progress" post
format. Object detection alone can't tell these apart (a bounding box says
WHAT is in it, never whether two boxes are the same subject at a different
time). mm_plant_growth_collage.py's detect_collage_seam() adds a second,
independent CV-only check: a collage almost always has a visible SEAM — a
straight line where a sharp edge coincides with a color/exposure jump,
because the two halves came from different shots (different lighting/
white-balance/scene), which a single continuous photo does not have. When a
confident seam is found (_auto_split_collage()), the photo is split there
and run through the ordinary 2-frame growth path instead of compare mode —
panel order is assumed left-to-right / top-to-bottom (natural reading
order), which is a real assumption, not a guarantee, since there is no
caption OCR to confirm which panel came first.
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
from routers.rag.mm_plant_growth_blobs import detect_plant_blobs
from routers.rag.mm_plant_growth_collage import detect_collage_seam, split_at_seam

logger = logging.getLogger(__name__)

router = APIRouter()

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
    leaf_pixel_count = int(mask.sum())
    area_fraction = float(leaf_pixel_count) / mask.size

    overlay = rgb.copy()
    overlay[mask] = (
        overlay[mask] * (1 - _MASK_OVERLAY_ALPHA) + _MASK_OVERLAY_COLOR * _MASK_OVERLAY_ALPHA
    ).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(overlay).save(buf, format="PNG")

    return {
        "ok": True,
        "area_fraction": area_fraction,
        "leaf_pixel_count": leaf_pixel_count,
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
    """Normalized [x,y,w,h] boxes for detected plants, sorted left-to-right
    (x-center ascending) — the ordering later frames are matched against,
    relying on the same "consistent framing across the series" assumption
    this tool already requires for growth% to be meaningful at all.

    Tries the general object detector (Plant/Houseplant/Flowerpot classes)
    first. If it finds fewer than 2 plants, falls back to
    mm_plant_growth_blobs.detect_plant_blobs() on this tool's own leaf
    mask — the detector can miss small seedlings or stylized/illustrated
    plants it wasn't trained on, but the leaf-mask blob approach doesn't
    care what the plant looks like, only that it's green and spatially
    separate from other green regions. Only used as a fallback (not
    always) because it's noisier on real photos with background greenery
    the detector correctly ignores."""
    objects, _ = detect_objects(b64)
    boxes = [o["bbox"] for o in objects if o["label"] in _PLANT_LABELS]
    boxes.sort(key=lambda b: b[0] + b[2] / 2)
    if len(boxes) >= 2:
        return boxes

    try:
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        mask_boxes = detect_plant_blobs(_leaf_mask(np.asarray(img)))
        if len(mask_boxes) > len(boxes):
            return mask_boxes
    except Exception as exc:
        logger.warning("Plant growth mask-based fallback detection failed: %s", exc)
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


def _auto_split_collage(frame: PlantGrowthFrame) -> dict | None:
    """If this single photo looks like a two-panel before/after collage
    (see _detect_collage_seam), splits it at the seam and runs the two
    halves through the exact same measurement used for a genuine 2-photo
    growth-mode upload (_measure_frame / _finalize_track, no new
    measurement code) — this is what a user would get by manually
    pre-splitting the file and uploading both halves. Returns None when no
    confident seam is found, so the caller falls through to compare mode."""
    try:
        img = Image.open(io.BytesIO(base64.b64decode(frame.image))).convert("RGB")
    except Exception:
        return None

    boxes = _detect_plant_boxes(frame.image)
    seam = detect_collage_seam(np.asarray(img), boxes)
    if seam is None:
        return None

    region_a, region_b = split_at_seam(img, seam)
    entries = [
        _to_frame_entry(_measure_frame(img, region_a), "Panel 1"),
        _to_frame_entry(_measure_frame(img, region_b), "Panel 2"),
    ]
    finalized = _finalize_track(entries)
    if not finalized:
        return None
    return {"mode": "growth", "plants": [{"index": 0, **finalized}], "auto_split_collage": True}


def _compare_single_photo(frame: PlantGrowthFrame, auto_detect: bool) -> dict:
    """One photo, multiple plants — compares their CURRENT leaf area to each
    other (relative_pct: largest plant = 100%), not a time-series growth %.
    There's no baseline to grow from with only one photo, so this is a
    genuinely different aggregation, not a degenerate case of the
    multi-frame path below.

    Uses each plant's ABSOLUTE leaf_pixel_count for the comparison, not its
    area_fraction (leaf pixels / that plant's OWN crop size) — a small
    plant's tight crop and a large plant's tight crop can land on nearly
    identical fractions (both crops are mostly foliage), which would hide
    the real size difference the crop size itself already encodes. Absolute
    pixel counts are only comparable because all plants share one photo, one
    camera distance — unlike growth% across frames, where only the SAME
    plant's fraction over time is used (crop size for one plant is fairly
    stable frame to frame, unlike comparing crops of different plants)."""
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
            "low_confidence": (not m.get("ok")) or area_fraction < _LOW_CONFIDENCE_THRESHOLD,
        })

    return {"mode": "compare", "plants": plants}


@router.post("/mm-plant-growth")
def plant_growth_endpoint(body: PlantGrowthRequest):
    if not (1 <= len(body.frames) <= _MAX_FRAMES):
        raise HTTPException(
            status_code=400,
            detail=f"provide between 1 and {_MAX_FRAMES} frames",
        )
    for i, frame in enumerate(body.frames):
        if not frame.image.strip():
            raise HTTPException(status_code=400, detail=f"frame {i} is missing an image")

    if len(body.frames) == 1:
        if body.auto_detect:
            split_result = _auto_split_collage(body.frames[0])
            if split_result is not None:
                return split_result
        return _compare_single_photo(body.frames[0], body.auto_detect)

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

    return {"mode": "growth", "plants": plants}
