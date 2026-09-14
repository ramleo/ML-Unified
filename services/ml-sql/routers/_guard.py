"""Abuse protection for ml-sql — the same three guards ml-api has in
`security/`, sized for this service (OPEN_ISSUES E16).

Before this, ml-sql allowed every origin, and its only limit was one GLOBAL
30-per-minute counter on /sql/query: one caller could lock every visitor out,
while /sql/explain, /sql/reason, /sql/filter and /sql/sample-questions called
an LLM on the server's keys with no limit at all.

1. Origin. A browser request from a site not on the list is refused (403)
   before any route runs. CORS headers alone are not a gate: the HF proxy
   adds its own. Requests with no Origin (curl, scripts) pass here, as in
   ml-api — the next two guards are what bound those.
2. Per-IP rate limits, keyed on X-Forwarded-For (HF's proxy rotates the TCP
   peer address, so that address is useless as a key). LLM routes get a
   strict limit, everything else a generous one.
3. A daily cap on LLM-route calls across all callers, so a patient abuser
   rotating IPs still cannot run up an unbounded bill in one day.

In-memory and single-process, like ml-api's: ml-sql runs as one Space
instance, and a restart resetting the counters is an accepted gap.
"""
from __future__ import annotations

import datetime
import logging
import os
import re
import threading
import time
from collections import deque

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# ── 1. Origin ────────────────────────────────────────────────────────────────

_DEFAULT_ORIGINS = [
    "https://ml-portfolio-rho.vercel.app",
    "http://localhost:3000",
    "http://localhost:3300",
]
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()
] or _DEFAULT_ORIGINS
# Vercel previews; host characters only, so "https://evil.com/?x=.vercel.app" fails.
ALLOWED_ORIGIN_REGEX = os.environ.get("ALLOWED_ORIGIN_REGEX", r"https://[A-Za-z0-9.-]+\.vercel\.app")
_origin_re = re.compile(ALLOWED_ORIGIN_REGEX)


def cors_kwargs() -> dict:
    return {"allow_origins": ALLOWED_ORIGINS, "allow_origin_regex": ALLOWED_ORIGIN_REGEX,
            "allow_methods": ["*"], "allow_headers": ["*"]}


def is_allowed_origin(origin: str) -> bool:
    return origin in ALLOWED_ORIGINS or bool(_origin_re.fullmatch(origin))


# ── 2. Per-IP limits ─────────────────────────────────────────────────────────

LLM_ROUTES = {"/sql/query", "/sql/explain", "/sql/reason", "/sql/filter", "/sql/sample-questions"}
LLM_PER_MIN = int(os.environ.get("SQL_RATE_LLM_PER_MIN", "10"))
OTHER_PER_MIN = int(os.environ.get("SQL_RATE_OTHER_PER_MIN", "60"))
_WINDOW_S = 60.0

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque[float]] = {}


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _over_limit(ip: str, tier: str, limit: int, now: float) -> bool:
    with _lock:
        q = _hits.setdefault((ip, tier), deque())
        while q and now - q[0] > _WINDOW_S:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        if len(_hits) > 10_000:  # crude memory bound: drop idle buckets
            for k in [k for k, v in _hits.items() if not v]:
                del _hits[k]
        return False


# ── 3. Daily cap on LLM routes ───────────────────────────────────────────────

LLM_DAILY_CAP = int(os.environ.get("SQL_LLM_DAILY_CAP", "300"))
_daily: dict[str, int] = {}


def _over_daily_cap() -> bool:
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    with _lock:
        n = _daily.get(today, 0)
        if n >= LLM_DAILY_CAP:
            return True
        _daily.clear()
        _daily[today] = n + 1
        return False


# ── Middleware ───────────────────────────────────────────────────────────────

async def guard(request: Request, call_next):
    path = request.url.path
    ip = client_ip(request)

    origin = request.headers.get("origin")
    if origin and not is_allowed_origin(origin):
        logger.warning("origin blocked: %s %s", origin, path)
        return JSONResponse({"error": "Origin not allowed."}, status_code=403)

    if request.method == "OPTIONS":  # CORS preflight: never counted
        return await call_next(request)

    is_llm = path in LLM_ROUTES
    limit = LLM_PER_MIN if is_llm else OTHER_PER_MIN
    if _over_limit(ip, "llm" if is_llm else "other", limit, time.monotonic()):
        logger.warning("rate limited: ip=%s path=%s", ip, path)
        return JSONResponse({"error": "Too many requests. Please wait a minute and try again."},
                            status_code=429, headers={"Retry-After": "60"})

    if is_llm and _over_daily_cap():
        logger.warning("daily LLM cap reached (%d): path=%s", LLM_DAILY_CAP, path)
        return JSONResponse({"error": "Today's usage limit for this demo is reached. It resets at midnight UTC."},
                            status_code=429)

    return await call_next(request)
