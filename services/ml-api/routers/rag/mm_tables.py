"""Table-region detection via Microsoft's Table Transformer (backlog item 4).

A real, text-based PDF page already gets a precise table bbox for free via
PyMuPDF's native page.find_tables() (mm_pdf.py) — pure vector geometry, no
model needed, and out of scope here. The gap this module closes: a
standalone image upload (mm_image.py) has no PDF vector structure to lean
on, so a table Mistral OCR reconstructs as markdown (split_pipe_tables)
currently gets NO bbox at all — no citation highlight box, unlike every
other chunk type this project produces. table-transformer-detection (DETR,
ResNet-18 backbone, ~110 MB) finds each table's RASTER bounding box
straight from pixels, closing that gap for the image-upload path.

Lazy-loaded on first use, same pattern as mm_similar.py's CLIP model — most
image uploads have no table at all, so paying the one-time model-load cost
eagerly on every upload would be wasteful. Best-effort only: [] on any
failure, never blocks ingestion.
"""
from __future__ import annotations

import base64
import io
import logging
import threading

logger = logging.getLogger(__name__)

_MODEL_NAME = "microsoft/table-transformer-detection"
_CONF_THRESHOLD = 0.7  # table-transformer's own recommended operating point
_MAX_TABLES = 4

_processor = None
_model = None
_lock = threading.Lock()
_load_error: str | None = None


def _ensure_loaded() -> bool:
    global _processor, _model, _load_error
    if _model is not None:
        return True
    with _lock:
        if _model is not None:
            return True
        try:
            from transformers import AutoImageProcessor, TableTransformerForObjectDetection

            logger.info("Loading table-transformer-detection (~110 MB) for table-region detection …")
            _processor = AutoImageProcessor.from_pretrained(_MODEL_NAME)
            _model = TableTransformerForObjectDetection.from_pretrained(_MODEL_NAME)
            _model.eval()
            return True
        except Exception as exc:
            logger.warning("Table Transformer load failed — table-region detection disabled: %s", exc)
            _load_error = str(exc)
            return False


def detect_table_regions(b64: str) -> list[dict]:
    """Returns up to _MAX_TABLES {bbox: [x,y,w,h] normalized 0-1, confidence}
    for detected table regions, sorted TOP-TO-BOTTOM (by y0) — callers pair
    these positionally against an OCR-derived list of table blocks, which
    itself carries no independent position info of its own. [] on any
    failure, no detection, or the model failing to load."""
    if not _ensure_loaded():
        return []
    try:
        import torch
        from PIL import Image

        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        w, h = img.size
        if w == 0 or h == 0:
            return []

        inputs = _processor(images=img, return_tensors="pt")
        with torch.no_grad():
            outputs = _model(**inputs)
        target_sizes = torch.tensor([[h, w]])
        results = _processor.post_process_object_detection(
            outputs, threshold=_CONF_THRESHOLD, target_sizes=target_sizes)[0]

        regions = [
            {"confidence": round(float(score), 3),
             "bbox": [round(x0 / w, 4), round(y0 / h, 4),
                      round((x1 - x0) / w, 4), round((y1 - y0) / h, 4)]}
            for score, (x0, y0, x1, y1) in zip(results["scores"].tolist(), results["boxes"].tolist())
        ]
        regions.sort(key=lambda r: r["bbox"][1])
        return regions[:_MAX_TABLES]
    except Exception as exc:
        logger.warning("Table region detection failed: %s", exc)
        return []
