"""
CORS origin policy — replaces the previous `allow_origins=["*"]` wildcard
(a real, confirmed gap: any origin could call every one of this backend's
~50 public routers) with an explicit allowlist plus a regex covering Vercel
preview-deployment subdomains (which get random names per branch/PR, so a
fixed list alone would break preview testing).

Swap-in point for later: a paid edge WAF (Cloudflare, AWS WAF) sitting in
front of this Space would enforce origin/bot policy before requests even
reach this app — at that point this module can stay as a defense-in-depth
fallback rather than being removed, since it costs nothing to keep.
"""
import os

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


def get_cors_kwargs() -> dict:
    """Kwargs for FastAPI's CORSMiddleware — one call site in app.py."""
    return {
        "allow_origins": ALLOWED_ORIGINS,
        "allow_origin_regex": ALLOWED_ORIGIN_REGEX,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
