"""
Generic daily-call budget cap — the same proven shape as
`routers/rag/_image_gen_budget.py` (built after a real incident: repeated
live-testing ran a Gemini billing account down with no guardrail), applied
here to a real, confirmed gap: several LLM-judge routers
(`siem_triage.py`, `prompt_injection_check.py`, `ai_code_detector.py`,
`contradictions.py`) fall back to this project's OWN server-side
`MISTRAL_API_KEY` when a caller doesn't supply their own key — meaning any
anonymous visitor could otherwise run up the project owner's Mistral bill
with zero limit, the exact failure mode `_image_gen_budget.py` already
guards against for Gemini image generation.

In-memory, resets on restart — same honest ephemeral-state tradeoff as
`_image_gen_budget.py` (no external DB on this Space) — a same-day cost
spike is exactly the failure mode this guards against, so a restart
resetting the count is an acceptable gap, not a defeat of the point.

Swap-in point for later: if a persistent counter is ever needed (surviving
restarts, shared across instances), swap this module's in-memory dict for
Redis (`INCR` + `EXPIRE`) — the `check_and_record_call()` signature stays
identical, so no call site changes. A paid provider's own spend-cap/alert
feature (most LLM providers offer one) can also sit alongside this as a
second line of defense without removing this module.
"""
from __future__ import annotations

import datetime
import logging
import os
import threading

from fastapi import HTTPException

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_counts: dict[tuple[str, str], int] = {}


def check_and_record_call(feature: str, pool: str, daily_cap_env: str, default_cap: int = 20) -> None:
    """Raises HTTPException(429) BEFORE the caller makes its LLM request if
    today's count for `pool` is already at that pool's cap — a rejected
    call here costs nothing, unlike one that reaches the LLM provider.
    `feature` is just for the log-visible message (e.g. "siem-triage");
    `pool` selects which independent daily counter applies; `daily_cap_env`
    names the env var controlling that pool's cap (falls back to
    `default_cap` if unset)."""
    cap = int(os.environ.get(daily_cap_env, str(default_cap)))
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    with _lock:
        key = (pool, today)
        count = _counts.get(key, 0)
        if count >= cap:
            logger.warning("Daily budget exceeded: pool=%s feature=%s cap=%d", pool, feature, cap)
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Daily usage budget for this feature reached ({cap} calls) — "
                    "resets at UTC midnight. This protects against runaway API cost "
                    "on a shared demo, not a per-user limit."
                ),
            )
        _counts[key] = count + 1
        if _counts[key] == cap:
            logger.warning("Daily budget pool=%s reached cap (%d) on this call (feature=%s)", pool, cap, feature)
