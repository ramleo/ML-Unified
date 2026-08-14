"""Daily call caps for Gemini's paid image-generation model
(gemini-3.1-flash-lite-image, ~$0.04/image). Two independent pools:

- "shared" (default, `GEMINI_IMAGE_DAILY_CAP`, 40/day): mm_deblur.py
  (whole-image + region sharpen, up to 2 Gemini calls per region request)
  and mm_ai_fill.py (1 call per request) — both edit an existing image, a
  deliberate user action with real reuse value per call.
- "text2img" (`GEMINI_TEXT2IMG_DAILY_CAP`, 15/day): mm_text_to_image.py —
  kept separate and lower on purpose, since a free-text generator invites
  casual re-rolling with zero reuse value per call, and sharing the shared
  pool would let that experimentation starve sharpen/AI-fill's budget for
  the rest of the day.

Built after a real incident: repeated live-testing across a short debugging
session (each individual call reasonable on its own, never totalled up) ran
the Gemini billing account down toward its limit with no guardrail in
place. In-memory only, resets on restart — same honest ephemeral-state
tradeoff as everything else on this Space (no external DB) — but a
same-day burst is exactly the failure mode this guards against, so a
restart resetting the count is an acceptable gap, not a defeat of the
point.
"""
from __future__ import annotations

import datetime
import os
import threading

from fastapi import HTTPException

_DAILY_CALL_CAP = int(os.environ.get("GEMINI_IMAGE_DAILY_CAP", "40"))
_TEXT2IMG_DAILY_CAP = int(os.environ.get("GEMINI_TEXT2IMG_DAILY_CAP", "15"))

_CAPS = {"shared": _DAILY_CALL_CAP, "text2img": _TEXT2IMG_DAILY_CAP}
_MESSAGES = {
    "shared": (
        "Daily AI image-edit budget reached ({cap} calls across sharpen + "
        "AI-fill) — resets at UTC midnight. This protects against runaway "
        "Gemini API cost, not a per-user limit."
    ),
    "text2img": (
        "Daily text-to-image budget reached ({cap} calls) — resets at UTC "
        "midnight. This protects against runaway Gemini API cost, not a "
        "per-user limit."
    ),
}

_lock = threading.Lock()
_counts: dict[tuple[str, str], int] = {}


def check_and_record_call(feature: str, pool: str = "shared") -> None:
    """Raises HTTPException(429) BEFORE the caller makes its Gemini request
    if today's count for `pool` is already at that pool's cap — a rejected
    call here costs nothing, unlike one that reaches Gemini and fails some
    other way. `feature` is just for the log-visible error message (e.g.
    "deblur", "ai-fill", "text-to-image"); `pool` selects which independent
    daily counter/cap applies (see module docstring)."""
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    cap = _CAPS[pool]
    with _lock:
        key = (pool, today)
        count = _counts.get(key, 0)
        if count >= cap:
            raise HTTPException(status_code=429, detail=_MESSAGES[pool].format(cap=cap))
        _counts[key] = count + 1
