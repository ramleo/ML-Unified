"""
Testwright (QA Automation) — the single coupling point to the host app.

This is the ONLY module in routers/qa/ that reaches into the rest of ML-Unified.
Every QA route imports its shared infrastructure (LLM completion, server key
resolution, budget accounting, rate limiting) from here and nowhere else.

To extract QA into a standalone microservice later: copy the routers/qa/ folder
and reimplement just this file against vendored/standalone equivalents (an LLM
client, a budget guard, a limiter). No route or logic file changes.
"""

import os
import secrets

from routers.rag.llm import complete as _complete
from routers.rag.query_helpers import _resolve_key
from security.rate_limit import limiter, LLM_LIMIT
from security.budget import check_and_record_call as _check_and_record_call
from routers.qa import config

# Re-exported for the route decorator (@limiter.limit(LLM_LIMIT)).
__all__ = ["complete", "resolve_key", "owner_allowed", "select_candidates",
           "record_call", "limiter", "LLM_LIMIT"]


def complete(provider: str, model: str, key: str, messages: list[dict], system: str = "") -> str:
    """Non-streaming LLM completion. Returns "" on any provider failure."""
    return _complete(provider, model, key, messages, system=system)


def resolve_key(provider: str, user_key: str | None = None) -> str:
    """The key to use for a provider: the caller's own key (BYOK) when given,
    else the fixed server key, else "" if unset."""
    return _resolve_key(provider, user_key)


def owner_allowed(token: str | None) -> bool:
    """True only when `token` matches the server's QA_OWNER_TOKEN secret. Lets the
    owner unlock the server's PAID provider keys (e.g. Gemini) on these public
    endpoints. Constant-time compare; False when the secret is unset (no unlock)."""
    secret = os.environ.get(config.OWNER_TOKEN_ENV, "")
    if not secret or not token:
        return False
    return secrets.compare_digest(str(token), secret)


def select_candidates(provider: str | None, model: str | None,
                      user_key: str | None, owner_token: str | None
                      ) -> list[tuple[str, str, str]]:
    """Resolve the ordered (provider, model, key) list to try for a generation call:
      - BYOK: a single caller-chosen provider using the caller's OWN key (no fallback).
      - Owner (valid token) + a chosen provider: the server's key for it (e.g. the
        paid Gemini key) — owner-only.
      - Otherwise: the free server cascade (GEN_CANDIDATES), everyone's default.
    A visitor who names a paid provider WITHOUT a key or the owner token falls back
    to the free cascade — the server's paid key is never spent by a visitor."""
    p = (provider or "").strip().lower()
    m = (model or "").strip()
    # BYOK — caller's own key, their single choice, no cascade.
    if user_key and p in config.BYOK_PROVIDERS and m:
        return [(p, m, user_key)]
    # Owner unlocks the server's paid key for an explicitly chosen provider.
    if p and owner_allowed(owner_token):
        key = resolve_key(p)
        if key:
            return [(p, m or config.PROVIDER_DEFAULT_MODEL.get(p, ""), key)]
    # Default: the free server cascade.
    return [(cp, cm, resolve_key(cp)) for (cp, cm) in config.GEN_CANDIDATES]


def record_call(feature: str, pool: str, daily_cap_env: str) -> None:
    """Budget guard — raises if the daily cap for this pool is exceeded."""
    _check_and_record_call(feature, pool=pool, daily_cap_env=daily_cap_env)
