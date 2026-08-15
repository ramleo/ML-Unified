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

Style/aspect-ratio/negative-prompt are pure prompt-text engineering, not a
new request shape — still one text-only Gemini call, just a longer prompt
string built server-side (never trust the client to have assembled it
correctly/safely). No live-call verification needed for this addition, the
model call itself is byte-for-byte the same shape Phase B already verified.
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
_MAX_NEGATIVE_PROMPT_LEN = 500

# Fixed, server-validated set (not free text) so the appended instruction is
# always a known-good phrase — a client can only pick a key, never inject
# arbitrary text into this part of the prompt.
_STYLES = {
    "photorealistic": "in a photorealistic photographic style",
    "watercolor": "in a soft watercolor painting style",
    "anime": "in a vibrant anime/manga art style",
    "cyberpunk": "in a neon-lit cyberpunk art style",
    "oil-painting": "in a classical oil painting style, visible brushstrokes",
    "3d-render": "as a polished 3D render, studio lighting",
    "sketch": "as a detailed pencil sketch, black and white",
}
_ASPECT_RATIOS = {
    "square": "composed for a 1:1 square aspect ratio",
    "landscape": "composed for a 16:9 widescreen landscape aspect ratio",
    "portrait": "composed for a 9:16 tall portrait aspect ratio",
}


class TextToImageRequest(BaseModel):
    prompt: str
    style: str | None = None
    aspect_ratio: str | None = None
    negative_prompt: str | None = None
    # EXPERIMENTAL, unverified as of this commit: the Generative Language API
    # supports `generationConfig.seed` on some Gemini models for deterministic
    # output, but nobody has confirmed gemini-3.1-flash-lite-image (an image-
    # gen model, not a text model) actually honors it rather than silently
    # ignoring it. Sent through as-is when provided; None omits the field
    # entirely so every existing caller is unaffected. Do NOT build frontend
    # seed UI on top of this until a live same-seed/same-prompt pair has been
    # compared and found to actually reproduce.
    seed: int | None = None


class EnhancePromptRequest(BaseModel):
    prompt: str


# Same fallback order as generation.py's FALLBACK_CANDIDATES (Groq -> Mistral
# -> Gemini -> Cohere), each using its own server-side key — this is a plain
# text completion, not the billed image model, so it deliberately does NOT
# go through check_and_record_call/the text2img budget pool.
_ENHANCE_CASCADE = [
    ("groq", "llama-3.3-70b-versatile", "GROQ_API_KEY"),
    ("mistral", "mistral-small-latest", "MISTRAL_API_KEY"),
    ("gemini", "gemini-3.6-flash", "GEMINI_API_KEY"),
    ("cohere", "command-a-03-2025", "COHERE_API_KEY"),
]

_ENHANCE_SYSTEM_PROMPT = (
    "You are a prompt engineer for a text-to-image AI model. Rewrite the "
    "user's short prompt into a single vivid, detailed paragraph (2-4 "
    "sentences) describing the subject, setting, lighting, and mood, while "
    "preserving their original intent exactly. Do not invent a different "
    "subject. Do not add style names or commentary. Return ONLY the "
    "rewritten prompt text, nothing else."
)


@router.post("/mm-text-to-image/enhance-prompt")
def enhance_prompt(body: EnhancePromptRequest):
    """Best-effort prompt expansion via the same free-tier LLM cascade used
    elsewhere in this codebase (see generation.py) — not the paid image
    model, so no budget check. Returns the original prompt unexpanded (with
    ok=False) rather than a hard error if every provider is unavailable, so
    a flaky free-tier provider never blocks the user from generating with
    what they already typed."""
    from routers.rag.llm import complete

    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required.")
    if len(prompt) > _MAX_PROMPT_LEN:
        raise HTTPException(status_code=400, detail=f"Prompt is too long (max {_MAX_PROMPT_LEN} characters).")

    for provider, model, env_key in _ENHANCE_CASCADE:
        key = os.environ.get(env_key, "")
        if not key:
            continue
        result = complete(provider, model, key, [{"role": "user", "content": prompt}], system=_ENHANCE_SYSTEM_PROMPT)
        result = result.strip()
        if result:
            return {"enhanced_prompt": result[:_MAX_PROMPT_LEN], "ok": True}

    return {"enhanced_prompt": prompt, "ok": False}


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

    if body.style is not None and body.style not in _STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown style. Choose one of: {', '.join(_STYLES)}.")
    if body.aspect_ratio is not None and body.aspect_ratio not in _ASPECT_RATIOS:
        raise HTTPException(status_code=400, detail=f"Unknown aspect_ratio. Choose one of: {', '.join(_ASPECT_RATIOS)}.")
    negative_prompt = (body.negative_prompt or "").strip()
    if len(negative_prompt) > _MAX_NEGATIVE_PROMPT_LEN:
        raise HTTPException(status_code=400, detail=f"Negative prompt is too long (max {_MAX_NEGATIVE_PROMPT_LEN} characters).")

    full_prompt = prompt
    if body.style:
        full_prompt += f", {_STYLES[body.style]}"
    if body.aspect_ratio:
        full_prompt += f", {_ASPECT_RATIOS[body.aspect_ratio]}"
    if negative_prompt:
        full_prompt += f". Do not include: {negative_prompt}."

    try:
        import httpx

        check_and_record_call("text-to-image", pool="text2img")
        payload: dict = {"contents": [{"role": "user", "parts": [{"text": full_prompt}]}]}
        if body.seed is not None:
            payload["generationConfig"] = {"seed": body.seed}
        with httpx.Client(timeout=60) as client:
            res = client.post(_URL, params={"key": key}, json=payload)
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
