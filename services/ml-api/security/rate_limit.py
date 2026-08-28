"""
Rate limiting — wraps `slowapi` (the standard FastAPI/Starlette
rate-limiting library, verified installable as a pure-Python wheel with no
native compile step, and verified at runtime: a 3/minute-limited route
correctly returned 200 for the first 3 requests and 429 for the 4th/5th in
a real local test before this was wired in).

A real, currently-exploitable gap this closes: this backend had ZERO rate
limiting on any of its ~50 routers before this module existed — anyone
could hit any endpoint at any rate.

Two limit tiers, applied per-route via the `@limiter.limit(...)` decorator
(never a single global number, since a heuristic-only route and an
LLM-backed route have very different real cost/abuse profiles):
- `HEURISTIC_LIMIT` — generous, for pure local-compute routes.
- `LLM_LIMIT` — strict, for routes that call out to a paid LLM provider.

Storage backend is in-memory by default (`RATE_LIMIT_BACKEND=memory`) — the
only sane global option for the current architecture (a single Space
instance, MULTIPLE requests can safely share one process's memory here).
Swap-in point for later: `RATE_LIMIT_BACKEND=redis` (with `REDIS_URL` set)
switches slowapi's own `storage_uri`, confirmed supported directly by the
installed `limits` package (`limits.storage.RedisStorage`) — needed if this
ever runs as multiple instances behind a load balancer, since in-memory
counts don't share across processes. A paid edge WAF (Cloudflare/AWS WAF)
placed in front of the Space later would enforce its own limits upstream of
this; this module would remain as a fallback, not be removed.
"""
import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def get_client_ip(request: Request) -> str:
    """Real bug found via live testing on the deployed HF Space: raw
    `request.client.host` (what `get_remote_address` reads) is just the last
    TCP hop before uvicorn — on this platform that's a ROTATING pool of
    Hugging Face's own internal proxy IPs, not the real caller. Confirmed
    directly from the Space's own request logs: 65 rapid requests to the
    same route from one client showed ~8 different `request.client.host`
    values, scattering what should have been one rate-limit bucket across
    several and letting every request through. Reading the real client IP
    from `X-Forwarded-For` (the standard header any reverse proxy sets,
    first entry = original client) is the correct fix on any platform
    fronted by a proxy — not specific to HF Spaces. Falls back to the raw
    peer address only if the header is absent (e.g. direct local testing)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


_BACKEND = os.environ.get("RATE_LIMIT_BACKEND", "memory")
_REDIS_URL = os.environ.get("REDIS_URL", "")

_storage_uri = _REDIS_URL if (_BACKEND == "redis" and _REDIS_URL) else "memory://"

HEURISTIC_LIMIT = os.environ.get("RATE_LIMIT_HEURISTIC", "60/minute")
LLM_LIMIT = os.environ.get("RATE_LIMIT_LLM", "10/minute")

# default_limits applies HEURISTIC_LIMIT to every route that has no explicit
# @limiter.limit(...) decorator — this is what gives blanket coverage across
# all ~50 existing routers without editing each one individually. Routes
# needing a stricter limit (the LLM-judge routers) add their own
# @limiter.limit(LLM_LIMIT) decorator, which overrides the default for that
# route only. Requires SlowAPIMiddleware (added in app.py) to actually
# enforce default_limits on undecorated routes.
limiter = Limiter(key_func=get_client_ip, storage_uri=_storage_uri, default_limits=[HEURISTIC_LIMIT])
