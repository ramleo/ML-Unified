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
    "meaning but vary the wording and phrasing. Reply with exactly 2 lines, "
    "one rewrite per line. No numbering, no bullets, no extra commentary."
)

_MAX_VARIANTS = 2


def expand_query(query: str, provider: str, model: str, key: str) -> list[str]:
    """Return [original_query, variant1, variant2, ...] (best-effort).

    Falls back to [query] alone if the LLM call fails or returns nothing
    usable — expansion is a quality boost, never a hard requirement.
    """
    if not key:
        return [query]

    text = complete(provider, model, key, [{"role": "user", "content": query}], system=_EXPANSION_SYSTEM)
    if not text:
        return [query]

    variants = [
        line.strip(" -•\t")
        for line in text.strip().splitlines()
        if line.strip()
    ][:_MAX_VARIANTS]
    variants = [v for v in variants if v and v != query]

    return [query] + variants
