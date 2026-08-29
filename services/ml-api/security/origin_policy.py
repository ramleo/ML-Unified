"""
CORS origin policy — replaces the previous `allow_origins=["*"]` wildcard
(a real, confirmed gap: any origin could call every one of this backend's
~50 public routers) with an explicit allowlist plus a regex covering Vercel
preview-deployment subdomains (which get random names per branch/PR, so a
fixed list alone would break preview testing).

Also enforces a hard block via `enforce_origin` middleware, not just
`CORSMiddleware` headers: a real, confirmed gap is that Hugging Face
Spaces' own front-door proxy injects its own permissive CORS headers on
top of whatever this app sends, so a disallowed browser origin could still
read the response — CORS is a header-negotiation mechanism a proxy can
override, not a real access-control gate. `enforce_origin` instead
outright rejects (403) any request carrying a disallowed `Origin` header
before it reaches any router, which the proxy cannot undo since it isn't
a header the proxy negotiates around, it's the app refusing to serve the
request at all. Requests with no `Origin` header (curl, server-to-server
calls, HF's own healthcheck) are not blocked here — only a browser sends
`Origin` on a cross-site request, so its absence carries no signal either
way and blocking it would break legitimate non-browser API consumers.

Swap-in point for later: a paid edge WAF (Cloudflare, AWS WAF) sitting in
front of this Space would enforce origin/bot policy before requests even
reach this app — at that point this module can stay as a defense-in-depth
fallback rather than being removed, since it costs nothing to keep.
"""
import os
import re

from fastapi import Request
from fastapi.responses import JSONResponse

from security.events import log_security_event
from security.rate_limit import get_client_ip

_DEFAULT_ORIGINS = [
    "https://ml-portfolio-rho.vercel.app",
    "http://localhost:3000",
    "http://localhost:3300",
]

# Comma-separated env override, e.g. "https://example.com,https://foo.com"
_env_origins = os.environ.get("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [o.strip() for o in _env_origins.split(",") if o.strip()] or _DEFAULT_ORIGINS

# Vercel preview deployments get a random subdomain per branch/PR
# (project-git-branch-user.vercel.app) — matched separately from the exact
# allowlist above rather than trying to enumerate every preview URL.
ALLOWED_ORIGIN_REGEX = os.environ.get("ALLOWED_ORIGIN_REGEX", r"https://.*\.vercel\.app")
_origin_regex = re.compile(ALLOWED_ORIGIN_REGEX)


def get_cors_kwargs() -> dict:
    """Kwargs for FastAPI's CORSMiddleware — one call site in app.py."""
    return {
        "allow_origins": ALLOWED_ORIGINS,
        "allow_origin_regex": ALLOWED_ORIGIN_REGEX,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }


def is_allowed_origin(origin: str) -> bool:
    return origin in ALLOWED_ORIGINS or bool(_origin_regex.fullmatch(origin))


async def enforce_origin(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and not is_allowed_origin(origin):
        log_security_event("origin_blocked", request.url.path, get_client_ip(request), detail=f"origin={origin}")
        return JSONResponse(status_code=403, content={"detail": "Origin not allowed."})
    return await call_next(request)
