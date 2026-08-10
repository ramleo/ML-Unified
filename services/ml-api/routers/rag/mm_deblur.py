"""Sharpen/deblur a citation image via Gemini image editing — same paid
model and call pattern as mm_ai_fill.py (gemini-3.1-flash-lite-image,
GEMINI_API_KEY). This is generative, not true deconvolution: it can invent
plausible-but-wrong detail on content that's genuinely lost to blur, rather
than admitting it can't tell. Verified live before shipping: a synthetic
Gaussian-blurred test image (invoice number, amount, date) came back sharp
and byte-correct. A public discriminative alternative (NAFNet, no
hallucination risk) was also tested live and barely improved legibility —
not good enough to ship on its own. The frontend must label the result
"AI-enhanced — verify against original" and let the user compare against
the original rather than silently replacing it, since a wrong digit on a
financial document is worse than staying blurry.
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

_MODEL = "gemini-3.1-flash-lite-image"
_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL}:generateContent"

_INSTRUCTION = (
    "This image is blurry or out of focus. Sharpen it and remove the blur "
    "so any text and fine detail becomes clearly legible. Do not add, "
    "remove, or change any content, composition, colors, or layout — only "
    "restore clarity and focus."
)


class DeblurRequest(BaseModel):
    image: str  # b64 PNG, the current citation page/frame image (post-edit if any)


@router.post("/mm-deblur")
def deblur_image(body: DeblurRequest):
    """Returns {"image": <b64>} — best-effort, never persisted server-side,
    same disposable-edit contract as /mm-inpaint and /mm-ai-fill."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise HTTPException(status_code=502, detail="Sharpen is not configured (missing GEMINI_API_KEY).")

    try:
        import httpx

        with httpx.Client(timeout=60) as client:
            res = client.post(
                _URL,
                params={"key": key},
                json={"contents": [{"role": "user", "parts": [
                    {"inline_data": {"mime_type": "image/png", "data": body.image}},
                    {"text": _INSTRUCTION},
                ]}]},
            )
            res.raise_for_status()
            parts = res.json()["candidates"][0]["content"]["parts"]

        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return {"image": inline["data"]}
        raise ValueError("Gemini response had no image part")
    except Exception as exc:
        logger.warning("Deblur failed: %s", exc)
        raise HTTPException(status_code=502, detail="Sharpen is temporarily unavailable — try again in a moment.")