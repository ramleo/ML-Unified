"""Public-API key auth (Q1 M2).

A FastAPI dependency that guards the `/v1/` routes. The Space holds NO Supabase
key, so it validates a caller's `X-API-Key` against a token-gated frontend route
(`/api/keys/verify`) that reads the `api_keys` table, checks revoked/expired/quota
/budget, and meters the use. We verify on EVERY request so the monthly quota count
stays accurate; a cheap in-memory per-key burst limit protects that hop from spam.

Fail-closed: if `API_KEYS_VERIFY_TOKEN` is unset, every `/v1/` call is rejected.

Kept as a SYNC `def` on purpose — FastAPI runs sync dependencies in a threadpool,
so the blocking httpx call never stalls the event loop.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import deque

from fastapi import Header, HTTPException, Request

_VERIFY_URL = os.environ.get(
    "API_KEYS_VERIFY_URL", "https://ml-portfolio-rho.vercel.app/api/keys/verify"
)
_VERIFY_TOKEN = os.environ.get("API_KEYS_VERIFY_TOKEN", "")
_TIMEOUT_S = 6.0

# Per-key burst guard (per process, best-effort). The real volume cap is the
# monthly quota enforced by the verify route; this just blunts rapid spam.
_BURST_MAX = 120
_BURST_WINDOW_S = 60
_hits: dict[str, deque[float]] = {}
_lock = threading.Lock()


def _rate_ok(key_hash: str) -> bool:
    now = time.time()
    with _lock:
        dq = _hits.setdefault(key_hash, deque())
        while dq and dq[0] <= now - _BURST_WINDOW_S:
            dq.popleft()
        if len(dq) >= _BURST_MAX:
            return False
        dq.append(now)
        return True


def _verify(key_hash: str) -> dict:
    import httpx

    r = httpx.post(
        _VERIFY_URL,
        json={"key_hash": key_hash},
        headers={"x-verify-token": _VERIFY_TOKEN},
        timeout=_TIMEOUT_S,
    )
    if r.status_code == 200:
        return r.json()
    # Non-200 (e.g. our token rejected) → treat as invalid, fail closed.
    return {"valid": False, "reason": "verify_failed"}


def require_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> dict:
    if not _VERIFY_TOKEN:
        raise HTTPException(status_code=503, detail="Public API is not configured.")
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header.")

    key_hash = hashlib.sha256(x_api_key.encode("utf-8")).hexdigest()

    if not _rate_ok(key_hash):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Slow down.")

    try:
        result = _verify(key_hash)
    except Exception:
        # Verification service unreachable → fail closed.
        raise HTTPException(status_code=503, detail="Key verification unavailable.")

    if not result.get("valid"):
        reason = result.get("reason", "invalid")
        if reason in ("quota_exceeded", "budget_exceeded"):
            raise HTTPException(status_code=429, detail=reason)
        raise HTTPException(status_code=401, detail=f"Invalid API key ({reason}).")

    request.state.api_key = result
    return result
