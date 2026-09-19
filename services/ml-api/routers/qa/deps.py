"""
Testwright (QA Automation) — the single coupling point to the host app.

This is the ONLY module in routers/qa/ that reaches into the rest of ML-Unified.
Every QA route imports its shared infrastructure (LLM completion, server key
resolution, budget accounting, rate limiting) from here and nowhere else.

To extract QA into a standalone microservice later: copy the routers/qa/ folder
and reimplement just this file against vendored/standalone equivalents (an LLM
client, a budget guard, a limiter). No route or logic file changes.
"""

from routers.rag.llm import complete as _complete
from routers.rag.query_helpers import _resolve_key
from security.rate_limit import limiter, LLM_LIMIT
from security.budget import check_and_record_call as _check_and_record_call

# Re-exported for the route decorator (@limiter.limit(LLM_LIMIT)).
__all__ = ["complete", "resolve_key", "record_call", "limiter", "LLM_LIMIT"]


def complete(provider: str, model: str, key: str, messages: list[dict], system: str = "") -> str:
    """Non-streaming LLM completion. Returns "" on any provider failure."""
    return _complete(provider, model, key, messages, system=system)


def resolve_key(provider: str) -> str:
    """The fixed server key for a provider, or "" if unset."""
    return _resolve_key(provider, None)


def record_call(feature: str, pool: str, daily_cap_env: str) -> None:
    """Budget guard — raises if the daily cap for this pool is exceeded."""
    _check_and_record_call(feature, pool=pool, daily_cap_env=daily_cap_env)
