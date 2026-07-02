"""RAG reranking — cross-encoder scoring over RRF-fused candidates."""
from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)

# Real calibration data (RERANK DEBUG logs) showed genuinely relevant chunks
# scoring as low as 0.028 absolute sigmoid, while noise scored 0.000 — an
# absolute floor like 0.3 rejected the correct answer outright. This model's
# scores for our content (long technical chunks vs. casual questions) don't
# map onto an intuitive 0-100% scale, so filtering uses the RELATIVE gap
# between the top match and the rest instead of a fixed absolute cutoff.
_ABS_FLOOR = 0.01     # top chunk must clear this bare minimum, or return nothing
_RELATIVE_RATIO = 0.5  # keep additional chunks scoring >= 50% of the top score


def _sigmoid(x: float) -> float:
    """Squash a cross-encoder logit into a 0-1 relevance probability."""
    return 1.0 / (1.0 + math.exp(-x))


def rerank(query: str, chunks: list[dict], state, top_k: int = 8, abs_floor: float | None = None) -> list[dict]:
    """Re-score candidate chunks with a cross-encoder, drop irrelevant ones, return top_k.

    Falls back to the input order (already RRF-ranked) if no reranker is loaded.
    Each output dict keeps {text, source, id}; "score" becomes the raw 0-1
    sigmoid relevance, "display_score" becomes that score relative to the top
    match (top match = 1.0) — display_score is what the UI should render as a
    percentage, since absolute scores for this model rarely look intuitive.
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

    top_debug = ", ".join(f"{c.get('source','?')}={s:.3f}" for c, s in scored[:10])
    logger.info("RERANK DEBUG query=%r top10=[%s]", query, top_debug)

    floor = _ABS_FLOOR if abs_floor is None else abs_floor
    if not scored or scored[0][1] < floor:
        return []

    top_score = scored[0][1]
    min_keep = top_score * _RELATIVE_RATIO

    reranked: list[dict] = []
    for chunk, score in scored[:top_k]:
        if score < min_keep:
            break  # scored is sorted descending — everything after this is worse
        entry = dict(chunk)
        entry["score"] = score
        entry["display_score"] = score / top_score
        reranked.append(entry)

    return reranked
