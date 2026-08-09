"""AI-generated fill for a region already removed by mm_inpaint.py — describe
what should go there and a model fills it in matching the surrounding photo.

No usable free image-generation path exists among the providers already
wired into this project (verified live, not assumed): Gemini's free tier is
hard-capped at 0 requests for its image model, and Groq/Mistral have no
image-generation model at all. Self-hosting an open editing model (FLUX
Kontext, Qwen-Image-Edit) is ruled out the same way this project already
ruled out Stable Diffusion inpainting — too large for the free CPU-only
Space. What works: calling FLUX.1 Kontext [dev]'s PUBLIC Hugging Face Space
(black-forest-labs/FLUX.1-Kontext-Dev) via gradio_client — free, no API key,
since inference runs on that Space's own (shared, free) GPU quota, not ours.
This is a best-effort call to someone else's community infrastructure, not a
guaranteed SLA — failures must degrade to a clear error, never a crash.
"""
from __future__ import annotations

import base64
import io
import logging
import os
import re
import tempfile
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

_client = None
_lock = threading.Lock()
_load_error: Optional[str] = None

_SPACE = "black-forest-labs/FLUX.1-Kontext-Dev"

# ZeroGPU's own quota-exceeded message looks like: "You have exceeded your
# free ZeroGPU quota (90s requested vs. 80s left). Try again in 15:31:36." —
# this is a genuine daily cap (observed live, see mm_ai_fill session notes),
# not a random blip, so it's worth relaying the actual countdown instead of
# the generic "try again in a moment" that implies otherwise.
_QUOTA_RESET_RE = re.compile(r"exceeded your (?:free )?ZeroGPU quota.*?Try again in ([\d:]+)", re.DOTALL)


def _quota_reset_eta(exc: Exception) -> Optional[str]:
    match = _QUOTA_RESET_RE.search(str(exc))
    return match.group(1) if match else None


def _ensure_client():
    """Lazily construct the gradio_client.Client — its constructor does its
    own schema fetch (~1-2s), so it's cached like every other mm_*.py
    lazy-loaded resource rather than rebuilt per request.

    Passing an HF token authenticates the call — anonymous callers get a
    much smaller ZeroGPU quota (observed live: exhausted after a handful of
    calls, failing with "You have exceeded your ZeroGPU runs limit").
    Falls back to anonymous if no token is configured (Space secret
    HF_TOKEN, same account this Space itself deploys under) — degrades to
    the old low-quota behavior rather than failing outright."""
    global _client, _load_error
    if _client is not None:
        return _client
    with _lock:
        if _client is not None:
            return _client
        try:
            from gradio_client import Client

            _client = Client(_SPACE, token=os.environ.get("HF_TOKEN"))
            return _client
        except Exception as exc:
            logger.warning("Could not connect to %s: %s", _SPACE, exc)
            _load_error = str(exc)
            return None


class AiFillRequest(BaseModel):
    image: str  # b64 PNG/JPEG, the full citation page/frame image (post-removal)
    bbox: list[float]  # [x, y, w, h], normalized 0-1 — unused by the remote model
    # itself (it edits the whole image), kept for parity with mm_inpaint.py and
    # room to crop/re-composite client-side later; not sent to the Space.
    prompt: Optional[str] = None  # what the user typed, e.g. "a wicker basket"


@router.post("/mm-ai-fill")
def ai_fill_region(body: AiFillRequest):
    """Fills the blank (white) region of `image` via FLUX.1 Kontext, guided
    by `prompt`. Returns {"image": <b64 PNG>} — best-effort, never persisted
    server-side, same disposable-edit contract as /mm-inpaint."""
    client = _ensure_client()
    if client is None:
        raise HTTPException(status_code=502, detail=f"AI fill is temporarily unavailable ({_load_error}).")

    try:
        from gradio_client import handle_file
        from PIL import Image

        img_bytes = base64.b64decode(body.image)
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            tmp.write(img_bytes)
            tmp.flush()

            instruction = (
                "Fill in the blank white area in this image realistically and "
                "seamlessly, matching the surrounding photo's style, lighting, "
                f"and content. {body.prompt or ''}. Keep everything else in the "
                "image exactly the same."
            )
            result_path, _seed = client.predict(
                input_image=handle_file(tmp.name),
                prompt=instruction,
                seed=0,
                randomize_seed=True,
                guidance_scale=2.5,
                steps=28,
                api_name="/infer",
            )

        result_img = Image.open(result_path).convert("RGB")
        buf = io.BytesIO()
        result_img.save(buf, format="PNG")
        return {"image": base64.b64encode(buf.getvalue()).decode()}
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("AI fill failed: %s", exc)
        reset_eta = _quota_reset_eta(exc)
        if reset_eta:
            raise HTTPException(
                status_code=429,
                detail=f"Daily AI-fill limit reached on the free shared model — resets in about {reset_eta} (hh:mm:ss).",
            )
        raise HTTPException(status_code=502, detail="AI fill is temporarily unavailable — try again in a moment.")