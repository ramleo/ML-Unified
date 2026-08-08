"""Region removal via LaMa inpainting — remove a detected region (object,
face, signature, tampering hit) from an image/video-frame citation.

Deliberately reuses whatever region data already exists rather than adding a
new region-selection UI: a SAM-refined polygon mask (see mm_segment.py, only
ever present on signature/tampering detections) when available, else a
dilated rectangle built from the detection's own bbox. Every input here is
already normalized [x,y,w,h]/[[x,y],...] page-relative, same convention as
every other mm_*.py endpoint.

LaMa (via the `simple-lama-inpainting` package) rather than a diffusion
model — a single ~200 MB JIT-traced model, CPU-fast (sub-second per call),
matching this project's established "smallest specialized model for the
job" pattern (dHash, Table Transformer, SlimSAM). Lazy-loaded on first use,
same skeleton as mm_similar.py/mm_tables.py.
"""
from __future__ import annotations

import base64
import io
import logging
import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

_model = None
_lock = threading.Lock()
_load_error: str | None = None


def _ensure_loaded() -> bool:
    global _model, _load_error
    if _model is not None:
        return True
    with _lock:
        if _model is not None:
            return True
        try:
            from simple_lama_inpainting import SimpleLama

            logger.info("Loading LaMa (~200 MB) for region-removal inpainting …")
            _model = SimpleLama()
            return True
        except Exception as exc:
            logger.warning("LaMa load failed — inpainting disabled: %s", exc)
            _load_error = str(exc)
            return False


class InpaintRequest(BaseModel):
    image: str  # b64 PNG/JPEG, the full citation page/frame image
    bbox: list[float]  # [x, y, w, h], normalized 0-1, page-relative
    mask: list[list[float]] | None = None  # normalized [x, y] polygon points, page-relative


def _build_mask(w: int, h: int, bbox: list[float], mask: list[list[float]] | None):
    from PIL import Image, ImageDraw

    m = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(m)
    if mask and len(mask) >= 3:
        draw.polygon([(px * w, py * h) for px, py in mask], fill=255)
    else:
        bx, by, bw, bh = bbox
        # Dilate ~4% of the box's own size so the fill fully covers the
        # object's real edges, not just its detector-reported bbox — a bbox
        # commonly clips a few pixels of the object it's drawn around.
        pad_x, pad_y = bw * 0.04, bh * 0.04
        x0, y0 = max(0, (bx - pad_x) * w), max(0, (by - pad_y) * h)
        x1, y1 = min(w, (bx + bw + pad_x) * w), min(h, (by + bh + pad_y) * h)
        draw.rectangle([x0, y0, x1, y1], fill=255)
    return m


@router.post("/mm-inpaint")
def inpaint_region(body: InpaintRequest):
    """Removes the given region from the image, filling it via LaMa. Returns
    {"image": <b64 PNG>} — a disposable edit, never persisted server-side."""
    if not _ensure_loaded():
        raise HTTPException(status_code=503, detail=f"Inpainting unavailable: {_load_error}")
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(base64.b64decode(body.image))).convert("RGB")
        w, h = img.size
        if w == 0 or h == 0 or len(body.bbox) != 4:
            raise HTTPException(status_code=400, detail="Invalid image or bbox.")

        mask = _build_mask(w, h, body.bbox, body.mask)
        result = _model(img, mask)

        buf = io.BytesIO()
        result.save(buf, format="PNG")
        return {"image": base64.b64encode(buf.getvalue()).decode()}
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Inpainting failed: %s", exc)
        raise HTTPException(status_code=500, detail="Inpainting failed.")
