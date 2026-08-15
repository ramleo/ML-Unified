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
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routers.rag._image_gen_budget import check_and_record_call

logger = logging.getLogger(__name__)

router = APIRouter()

_MODEL = "gemini-3.1-flash-lite-image"
_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL}:generateContent"


class AiFillRequest(BaseModel):
    image: str  # b64 PNG, the full citation page/frame image (post-removal)
    bbox: list[float] | None = None  # [x, y, w, h], normalized 0-1 — unused by
    # the remote model itself (it edits the whole image), kept for parity with
    # mm_inpaint.py and room to crop/re-composite client-side later; not sent
    # to the API. None is fine too (e.g. mode="edit" has no removed region).
    prompt: Optional[str] = None  # what the user typed, e.g. "a wicker basket"
    # "fill" (default) = existing citation-inpainting behavior: the image has
    # a blank white region (from mm_inpaint.py) that needs realistic content.
    # "edit" = free-form edit of an image with NO blank region (e.g. Text-to-
    # Image's "edit this" button) — a DIFFERENT instruction is required here
    # because "fill in the blank white area" is nonsensical on an image that
    # was never masked; sending it anyway would confuse the model about what
    # change is actually wanted. Existing callers never send this field, so
    # they keep getting "fill" unchanged.
    mode: Literal["fill", "edit"] = "fill"


@router.post("/mm-ai-fill")
def ai_fill_region(body: AiFillRequest):
    """Fills the blank (white) region of `image` (mode="fill", the citation-
    inpainting case) or applies a free-form edit to the whole image
    (mode="edit"), via Gemini image editing, guided by `prompt`. Returns
    {"image": <b64>} — best-effort, never persisted server-side, same
    disposable-edit contract as /mm-inpaint."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise HTTPException(status_code=502, detail="AI fill is not configured (missing GEMINI_API_KEY).")

    if body.mode == "edit":
        if not (body.prompt or "").strip():
            raise HTTPException(status_code=400, detail="A description of the edit is required.")
        instruction = (
            f"Edit this image as follows: {body.prompt}. Keep the rest of "
            "the image's style, composition, and content consistent except "
            "for the requested change."
        )
    else:
        instruction = (
            "Fill in the blank white area in this image realistically and "
            "seamlessly, matching the surrounding photo's style, lighting, "
            f"and content. {body.prompt or ''}. Keep everything else in the "
            "image exactly the same."
        )
    try:
        import httpx

        check_and_record_call("ai-fill")
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
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("AI fill failed: %s", exc)
        raise HTTPException(status_code=502, detail="AI fill is temporarily unavailable — try again in a moment.")