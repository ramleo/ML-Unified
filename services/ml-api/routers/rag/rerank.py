"""RAG reranking — cross-encoder scoring over RRF-fused candidates."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def rerank(query: str, chunks: list[dict], state, top_k: int = 8) -> list[dict]:
    """Re-score candidate chunks with a cross-encoder and return the top_k.

    Falls back to the input order (already RRF-ranked) if no reranker is loaded.
    Each output dict keeps {text, source, id} and overwrites score with the
    cross-encoder's relevance score.
    """
    if not chunks:
        return []

    if state.reranker is None:
        return chunks[:top_k]

    pairs = [(query, c["text"]) for c in chunks]

    try:
        scores = state.reranker.predict(pairs)
    except Exception as exc:
        logger.warning("Rerank failed, falling back to RRF order: %s", exc)
        return chunks[:top_k]

    scored = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)

    reranked: list[dict] = []
    for chunk, score in scored[:top_k]:
        entry = dict(chunk)
        entry["score"] = float(score)
        reranked.append(entry)

    return reranked
