"""Query expansion — ask the LLM for alternate phrasings of the user's
question before retrieval, to improve recall on vague or oddly-worded
queries. Variants are merged with the original via RRF in retrieve.py,
not used in place of it."""
from __future__ import annotations

import logging

from routers.rag.llm import complete

logger = logging.getLogger(__name__)

_EXPANSION_SYSTEM = (
    "Rewrite the user's question in 2 different ways that preserve its exact "
    "meaning but vary the wording and phrasing. Then, on a third line, name "
    "the question's intent as exactly one of: visual, exact_value, keyword, "
    "conceptual (visual = asks about an image/chart/color/diagram; "
    "exact_value = asks about a specific number/date/percentage/name; "
    "keyword = a short phrase lookup; conceptual = anything broader). "
    "Reply with exactly 3 lines: rewrite 1, rewrite 2, intent label. "
    "No numbering, no bullets, no extra commentary."
)

_MAX_VARIANTS = 2
_VALID_INTENTS = {"visual", "exact_value", "keyword", "conceptual"}


def expand_query(query: str, provider: str, model: str, key: str) -> tuple[list[str], str | None]:
    """Return ([original_query, variant1, variant2, ...], intent) (best-effort).

    Falls back to ([query], None) if the LLM call fails or returns nothing
    usable — expansion is a quality boost, never a hard requirement, and a
    missing/malformed intent label never raises, it's just treated as
    unclassified (the caller's heuristic classifier stands alone instead).
    """
    if not key:
        return [query], None

    # max_retries=0: expansion is optional — this function degrades to
    # [query] alone on any failure — so a dead provider must cost one round
    # trip, not the SDK's three. Observed 2026-09-06: with Mistral refusing
    # every call, every question on the site opened with three doomed
    # requests and ~2s of latency before retrieval even started.
    text = complete(provider, model, key, [{"role": "user", "content": query}],
                    system=_EXPANSION_SYSTEM, max_retries=0)
    if not text:
        return [query], None

    lines = [line.strip(" -•\t") for line in text.strip().splitlines() if line.strip()]

    intent = None
    if lines and lines[-1].lower() in _VALID_INTENTS:
        intent = lines.pop().lower()

    variants = [v for v in lines[:_MAX_VARIANTS] if v and v != query]

    return [query] + variants, intent
