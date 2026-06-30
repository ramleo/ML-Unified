"""RAG reranking — cross-encoder scoring over RRF-fused candidates."""
from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)

# Below this sigmoid-normalized relevance score, a chunk is treated as noise
# (off-topic match pulled in by lexical overlap) and dropped — but only once
# _MIN_RESULTS chunks have already been kept. Meta-questions like "what is
# this document about?" score low against any single chunk via cross-encoder
# even when retrieval found the right document, so a hard floor with no
# minimum can zero out sources entirely and leave the LLM nothing to ground on.
_RELEVANCE_FLOOR = 0.3
_MIN_RESULTS = 2


def _sigmoid(x: float) -> float:
    """Squash a cross-encoder logit into a 0-1 relevance probability."""
    return 1.0 / (1.0 + math.exp(-x))


def rerank(query: str, chunks: list[dict], state, top_k: int = 8) -> list[dict]:
    """Re-score candidate chunks with a cross-encoder, drop irrelevant ones, return top_k.

    Falls back to the input order (already RRF-ranked) if no reranker is loaded.
    Each output dict keeps {text, source, id} and overwrites score with a
    sigmoid-normalized relevance probability (0-1). Chunks scoring below
    _RELEVANCE_FLOOR are excluded — better to return fewer, correct sources
    than pad out to top_k with off-topic noise.
    """
    if not chunks:
        return []

    if state.reranker is None:
        return chunks[:top_k]

    pairs = [(query, c["text"]) for c in chunks]

    try:
        raw_scores = state.reranker.predict(pairs)
    except Exception as exc:
        logger.warning("Rerank failed, falling back to RRF order: %s", exc)
        return chunks[:top_k]

    scored = sorted(
        ((chunk, _sigmoid(float(s))) for chunk, s in zip(chunks, raw_scores)),
        key=lambda x: x[1],
        reverse=True,
    )

    reranked: list[dict] = []
    for chunk, score in scored[:top_k]:
        if score < _RELEVANCE_FLOOR and len(reranked) >= _MIN_RESULTS:
            break  # scored is sorted descending — everything after this is worse
        entry = dict(chunk)
        entry["score"] = score
        reranked.append(entry)

    return reranked
