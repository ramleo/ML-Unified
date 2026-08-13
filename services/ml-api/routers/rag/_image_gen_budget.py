"""Shared daily call cap for Gemini's paid image-editing model
(gemini-3.1-flash-lite-image, ~$0.04/image), used by both mm_deblur.py
(whole-image + region sharpen, up to 2 Gemini calls per region request) and
mm_ai_fill.py (1 call per request) — the ONLY two callers of that specific
model in this app. Built after a real incident: repeated live-testing across
a short debugging session (each individual call reasonable on its own, never
totalled up) ran the Gemini billing account down toward its limit with no
guardrail in place. In-memory only, resets on restart — same honest
ephemeral-state tradeoff as everything else on this Space (no external DB) —
but a same-day burst is exactly the failure mode this guards against, so a
restart resetting the count is an acceptable gap, not a defeat of the point.
"""
from __future__ import annotations

import datetime
import os
import threading

from fastapi import HTTPException

_DAILY_CALL_CAP = int(os.environ.get("GEMINI_IMAGE_DAILY_CAP", "40"))

_lock = threading.Lock()
_counts: dict[str, int] = {}


def check_and_record_call(feature: str) -> None:
    """Raises HTTPException(429) BEFORE the caller makes its Gemini request
    if today's count is already at the cap — a rejected call here costs
    nothing, unlike one that reaches Gemini and fails some other way.
    `feature` is just for the log-visible error message (e.g. "deblur",
    "ai-fill"), both draw from the same shared daily total since they hit
    the same billed model."""
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    with _lock:
        count = _counts.get(today, 0)
        if count >= _DAILY_CALL_CAP:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Daily AI image-edit budget reached ({_DAILY_CALL_CAP} calls "
                    f"across sharpen + AI-fill) — resets at UTC midnight. This "
                    f"protects against runaway Gemini API cost, not a per-user limit."
                ),
            )
        _counts[today] = count + 1