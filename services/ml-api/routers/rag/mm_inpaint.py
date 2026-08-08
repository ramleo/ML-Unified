"""Region removal — cover a detected region (object, face, signature,
tampering hit) on an image/video-frame citation with a plain white fill.

Deliberately reuses whatever region data already exists rather than adding a
new region-selection UI: a SAM-refined polygon mask (see mm_segment.py, only
ever present on signature/tampering detections) when available, else a
dilated rectangle built from the detection's own bbox. Every input here is
already normalized [x,y,w,h]/[[x,y],...] page-relative, same convention as
every other mm_*.py endpoint.

Plain white rather than a content-aware model (e.g. LaMa) — a flat fill was
the explicit choice over a blended/inpainted result. No model to load, so
this endpoint has no lazy-load step, unlike every other mm_*.py module.
"""
from __future__ import annotations

import base64
import io
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class InpaintRequest(BaseModel):
    image: str  # b64 PNG/JPEG, the full citation page/frame image
    bbox: list[float]  # [x, y, w, h], normalized 0-1, page-relative
    mask: list[list[float]] | None = None  # normalized [x, y] polygon points, page-relative


@router.post("/mm-inpaint")
def inpaint_region(body: InpaintRequest):
    """Covers the given region with plain white. Returns {"image": <b64 PNG>}
    — a disposable edit, never persisted server-side."""
    try:
        from PIL import Image, ImageDraw

        img = Image.open(io.BytesIO(base64.b64decode(body.image))).convert("RGB")
        w, h = img.size
        if w == 0 or h == 0 or len(body.bbox) != 4:
            raise HTTPException(status_code=400, detail="Invalid image or bbox.")

        draw = ImageDraw.Draw(img)
        if body.mask and len(body.mask) >= 3:
            draw.polygon([(px * w, py * h) for px, py in body.mask], fill=(255, 255, 255))
        else:
            bx, by, bw, bh = body.bbox
            # Dilate ~4% of the box's own size so the fill fully covers the
            # object's real edges, not just its detector-reported bbox — a
            # bbox commonly clips a few pixels of the object it's drawn
            # around.
            pad_x, pad_y = bw * 0.04, bh * 0.04
            x0, y0 = max(0, (bx - pad_x) * w), max(0, (by - pad_y) * h)
            x1, y1 = min(w, (bx + bw + pad_x) * w), min(h, (by + bh + pad_y) * h)
            draw.rectangle([x0, y0, x1, y1], fill=(255, 255, 255))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return {"image": base64.b64encode(buf.getvalue()).decode()}
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Region removal failed: %s", exc)
        raise HTTPException(status_code=500, detail="Region removal failed.")
