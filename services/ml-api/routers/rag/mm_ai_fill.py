"""AI-generated fill for a region already removed by mm_inpaint.py — describe
what should go there and a model fills it in matching the surrounding photo.

Previously called FLUX.1 Kontext's free public Hugging Face Space via
gradio_client — no API key, but shared ZeroGPU infrastructure with a small
daily quota per HF account (observed live: exhausted after a handful of
real calls, no way to raise it without a paid HF PRO subscription). Switched
to Gemini's paid image-editing model (gemini-3.1-flash-lite-image, aka
"Nano Banana 2 Lite") instead — same GEMINI_API_KEY already used everywhere
else in this project, ~$0.04/image, no shared-infrastructure quota wall.
Verified live before switching: a real edit (adding an object) and the
actual production scenario (filling a blank removed region to match
surroundings) both produced clean, correctly localized results.
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

_MODEL = "gemini-3.1-flash-lite-image"
_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL}:generateContent"


class AiFillRequest(BaseModel):
    image: str  # b64 PNG, the full citation page/frame image (post-removal)
    bbox: list[float]  # [x, y, w, h], normalized 0-1 — unused by the remote model
    # itself (it edits the whole image), kept for parity with mm_inpaint.py and
    # room to crop/re-composite client-side later; not sent to the API.
    prompt: Optional[str] = None  # what the user typed, e.g. "a wicker basket"


@router.post("/mm-ai-fill")
def ai_fill_region(body: AiFillRequest):
    """Fills the blank (white) region of `image` via Gemini image editing,
    guided by `prompt`. Returns {"image": <b64>} — best-effort, never
    persisted server-side, same disposable-edit contract as /mm-inpaint."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise HTTPException(status_code=502, detail="AI fill is not configured (missing GEMINI_API_KEY).")

    instruction = (
        "Fill in the blank white area in this image realistically and "
        "seamlessly, matching the surrounding photo's style, lighting, "
        f"and content. {body.prompt or ''}. Keep everything else in the "
        "image exactly the same."
    )
    try:
        import httpx

        with httpx.Client(timeout=60) as client:
            res = client.post(
                _URL,
                params={"key": key},
                json={"contents": [{"role": "user", "parts": [
                    {"inline_data": {"mime_type": "image/png", "data": body.image}},
                    {"text": instruction},
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
        logger.warning("AI fill failed: %s", exc)
        raise HTTPException(status_code=502, detail="AI fill is temporarily unavailable — try again in a moment.")