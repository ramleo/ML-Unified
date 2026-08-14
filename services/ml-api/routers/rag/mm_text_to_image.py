"""Text-to-image generation via Gemini's paid image model
(gemini-3.1-flash-lite-image, same model + GEMINI_API_KEY as mm_deblur.py
and mm_ai_fill.py, ~$0.04/image) — but unlike those two, this call sends
NO input image, just a text prompt. Every existing caller of this model in
this codebase always attached an inline_data image part; whether the model
accepts a request with only a text part was unverified until this file was
built. Verified live 2026-08-14 (one call, "a red apple on a white
background") — the model accepts a text-only request and returns a real
image. One real surprise from that response worth recording: it came back
as `mimeType: "image/jpeg"`, NOT PNG — unlike the editing calls (which send
PNG in and get PNG back), a pure generation call apparently defaults to
JPEG. The response's actual mimeType is therefore returned alongside the
image data below rather than assumed to be PNG.

No content-policy pre-check here, deliberately: mm_ai_fill.py/mm_deblur.py
already pass arbitrary user text into this same model with zero filtering,
and a safety refusal already falls into the same "no image part" -> 502
path below. Adding a custom pre-check would itself be a second billed call,
working against the exact cost discipline check_and_record_call exists
for.

Uses its own daily budget pool ("text2img", see _image_gen_budget.py) —
deliberately NOT the shared pool mm_deblur.py/mm_ai_fill.py use, since free
prompt experimentation would otherwise be able to exhaust that shared
budget and block sharpen/AI-fill for the rest of the day.
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routers.rag._image_gen_budget import check_and_record_call

logger = logging.getLogger(__name__)

router = APIRouter()

_MODEL = "gemini-3.1-flash-lite-image"
_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL}:generateContent"

_MAX_PROMPT_LEN = 2000


class TextToImageRequest(BaseModel):
    prompt: str


@router.post("/mm-text-to-image")
def generate_image(body: TextToImageRequest):
    """Returns {"image": <b64>, "mime_type": <e.g. "image/jpeg">} for a
    prompt-only Gemini generation — best-effort, never persisted
    server-side, same disposable-result contract as /mm-deblur and
    /mm-ai-fill. mime_type is whatever Gemini actually returned (observed
    "image/jpeg" for pure generation, not PNG — see module docstring), not
    assumed, so the frontend can build a correct data URI."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise HTTPException(status_code=502, detail="Text-to-image is not configured (missing GEMINI_API_KEY).")

    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required.")
    if len(prompt) > _MAX_PROMPT_LEN:
        raise HTTPException(status_code=400, detail=f"Prompt is too long (max {_MAX_PROMPT_LEN} characters).")

    try:
        import httpx

        check_and_record_call("text-to-image", pool="text2img")
        with httpx.Client(timeout=60) as client:
            res = client.post(
                _URL,
                params={"key": key},
                json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
            )
            res.raise_for_status()
            parts = res.json()["candidates"][0]["content"]["parts"]

        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                mime_type = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                return {"image": inline["data"], "mime_type": mime_type}
        raise ValueError("Gemini response had no image part")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Text-to-image failed: %s", exc)
        raise HTTPException(status_code=502, detail="Text-to-image is temporarily unavailable — try again in a moment.")
