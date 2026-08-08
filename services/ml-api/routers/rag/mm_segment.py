"""Pixel-accurate mask refinement via Segment Anything (backlog item 5,
final item of the CV backlog).

Every detector in this project (mm_objects/mm_signatures/mm_tampering)
already reports a rectangular bbox — good enough for "roughly where," but a
rectangle around a signature's ink strokes or a tampering region's irregular
edited boundary includes a lot of dead space that isn't actually the thing
of interest. This module takes an already-detected bbox as a SAM box PROMPT
(not full "segment everything," far too slow on CPU) and returns the
precise mask's contour as a normalized polygon — same spirit as every bbox
elsewhere in this codebase (a plain JSON array, not a raw image), so the
frontend can draw it as an SVG polygon with no new asset/decoding path.

Uses Zigeng/SlimSAM-uniform-77 (~39 MB, 77%-pruned distillation of SAM ViT-B)
via transformers' SamModel/SamProcessor — full SAM (ViT-H, ~2.4 GB) is not
viable on a CPU-only free-tier Space; SlimSAM keeps mask quality close to
full SAM at a fraction of the size/compute (~0.6s CPU for a whole batch of
box prompts on one image, since the expensive image encoder runs once and
is shared across every box). Lazy-loaded, same pattern as mm_similar.py's
CLIP model and mm_tables.py's Table Transformer.
"""
from __future__ import annotations

import base64
import io
import logging

logger = logging.getLogger(__name__)

_MODEL_NAME = "Zigeng/SlimSAM-uniform-77"
_MAX_REGIONS = 6      # bounds CPU cost per image; low-confidence tail regions
                      # already got cut off by each detector's own _MAX_DETECTIONS
_MAX_POLYGON_POINTS = 40  # enough to look like a real outline, cheap to ship/draw

_processor = None
_model = None
_load_error: str | None = None


def _ensure_loaded() -> bool:
    global _processor, _model, _load_error
    if _model is not None:
        return True
    try:
        from transformers import SamModel, SamProcessor

        logger.info("Loading %s (~39 MB) for mask refinement …", _MODEL_NAME)
        _processor = SamProcessor.from_pretrained(_MODEL_NAME)
        _model = SamModel.from_pretrained(_MODEL_NAME)
        _model.eval()
        return True
    except Exception as exc:
        logger.warning("SAM load failed — mask refinement disabled: %s", exc)
        _load_error = str(exc)
        return False


def _mask_to_polygon(mask, w: int, h: int) -> list[list[float]] | None:
    """Largest-contour outline of a boolean mask, simplified and normalized
    to 0-1 image-relative points. None if the mask is empty/degenerate."""
    import cv2
    import numpy as np

    contours, _ = cv2.findContours(mask.astype("uint8"), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < 4:
        return None
    peri = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, 0.01 * peri, True).reshape(-1, 2)
    if len(approx) > _MAX_POLYGON_POINTS:
        idx = np.linspace(0, len(approx) - 1, _MAX_POLYGON_POINTS).astype(int)
        approx = approx[idx]
    if len(approx) < 3:
        return None
    return [[round(float(x) / w, 4), round(float(y) / h, 4)] for x, y in approx]


def refine_masks(b64: str, regions: list[dict]) -> list[dict]:
    """Given an image and a list of {label, confidence, bbox} detections
    already found on it, adds a `mask` (normalized polygon points) to each
    of the first _MAX_REGIONS entries where SAM successfully refines the
    box. Returns NEW dicts (originals untouched); regions past the cap, or
    where refinement fails, are returned unchanged — plain bbox rendering
    still works either way, this is purely additive. Best-effort: [] input
    or any failure returns `regions` as-is."""
    if not regions or not _ensure_loaded():
        return regions
    try:
        import numpy as np
        import torch
        from PIL import Image

        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        w, h = img.size
        if w == 0 or h == 0:
            return regions

        to_refine = regions[:_MAX_REGIONS]
        boxes = [[bx * w, by * h, (bx + bw) * w, (by + bh) * h] for bx, by, bw, bh in (r["bbox"] for r in to_refine)]

        inputs = _processor(img, input_boxes=[boxes], return_tensors="pt")
        with torch.no_grad():
            outputs = _model(**inputs)
        masks = _processor.image_processor.post_process_masks(
            outputs.pred_masks.cpu(), inputs["original_sizes"].cpu(), inputs["reshaped_input_sizes"].cpu()
        )[0]  # [n_boxes, n_candidate_masks, H, W]
        scores = outputs.iou_scores[0]  # [n_boxes, n_candidate_masks]

        refined = list(regions)
        for i in range(len(to_refine)):
            best = int(scores[i].argmax())
            polygon = _mask_to_polygon(masks[i, best].numpy(), w, h)
            if polygon:
                refined[i] = {**regions[i], "mask": polygon}
        return refined
    except Exception as exc:
        logger.warning("Mask refinement failed: %s", exc)
        return regions
