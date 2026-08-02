"""Adaptive query routing (MMRAG-27) — classifies a query's intent and
returns per-retrieval-signal weight multipliers so reciprocal_rank_fusion
can tilt toward whichever of dense/bm25/vision/graph is most likely to hold
the answer, instead of always trusting all four equally.

Weights are mild tilts, never hard filters — a wrong classification should
degrade gracefully, not blind the pipeline to a signal that actually
mattered (same "additive, never replace" pattern as every other MMRAG
signal in this codebase).
"""
from __future__ import annotations

import re

from routers.rag.entities import extract_entities

INTENT_SIGNAL_WEIGHTS: dict[str, dict[str, float]] = {
    "visual":      {"vision": 1.5, "dense": 1.0, "bm25": 0.8, "graph": 1.0},
    "exact_value": {"graph": 1.6, "bm25": 1.1, "dense": 0.9, "vision": 0.7},
    "keyword":     {"bm25": 1.4, "dense": 0.9, "vision": 0.8, "graph": 1.0},
    "conceptual":  {"dense": 1.3, "bm25": 0.9, "vision": 0.8, "graph": 0.9},
}

_VISUAL_KEYWORDS = (
    "chart", "photo", "image", "picture", "color", "colour", "diagram",
    "logo", "shown", "highlighted", "drawn", "graph", "figure", "visual",
)
_QUESTION_WORDS = ("why", "how", "explain", "summarize", "summarise", "compare", "what is", "who is")
_QUOTED_RE = re.compile(r'"[^"]+"|\'[^\']+\'')


def classify_query_heuristic(query: str) -> str:
    """Keyword/regex pass — same style as query_helpers._detect_type_boost.
    Checked in priority order (most specific signal wins) since a query can
    trip more than one bucket."""
    if extract_entities(query):
        return "exact_value"

    q = query.lower()
    if any(kw in q for kw in _VISUAL_KEYWORDS):
        return "visual"

    if _QUOTED_RE.search(query) or (len(query.split()) <= 4 and not any(w in q for w in _QUESTION_WORDS)):
        return "keyword"

    return "conceptual"


def classify_query(query: str, expansion_intent: str | None = None) -> dict[str, float]:
    """Single entry point retrieve.py calls. Runs the heuristic always;
    expansion_intent (parsed from the LLM query-expansion call, when it ran)
    only overrides the heuristic's guess when the heuristic itself wasn't
    already confident (i.e. it fell back to "conceptual", the least
    specific default) — a more specific heuristic classification wins over
    a less specific LLM one. Never raises."""
    heuristic = classify_query_heuristic(query)

    if heuristic == "conceptual" and expansion_intent in INTENT_SIGNAL_WEIGHTS:
        heuristic = expansion_intent

    return INTENT_SIGNAL_WEIGHTS.get(heuristic, INTENT_SIGNAL_WEIGHTS["conceptual"])
