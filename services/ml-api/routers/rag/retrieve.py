"""RAG retrieval — dense (ChromaDB), sparse (BM25), and hybrid via RRF."""
from __future__ import annotations

import logging
from collections import defaultdict

from routers.rag.text import tokenize

logger = logging.getLogger(__name__)


# ── Query embedding ────────────────────────────────────────────────────────────

def embed_query(query: str, state, use_jina: bool = False) -> list[float]:
    """Embed a single query string; uses Jina query encoder when available and requested."""
    fn = state.jina_query_fn if (use_jina and state.jina_ready) else state.embedding_fn
    return fn([query])[0]


# ── Dense retrieval ────────────────────────────────────────────────────────────

def dense_retrieve(query_embedding: list[float], state, k: int = 50, use_jina: bool = False, where: dict | None = None) -> list[dict]:
    """Query ChromaDB for the top-k nearest neighbours.

    Returns list of {text, source, score, id}.
    score is cosine similarity (1 - distance for cosine space).
    """
    collection = state.jina_collection if (use_jina and state.jina_ready) else state.collection
    n_results = min(k, max(collection.count(), 1))

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
        **({"where": where} if where else {}),
    )

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]
    ids = results.get("ids", [[]])[0]

    hits: list[dict] = []
    for doc, meta, dist, rid in zip(docs, metas, dists, ids):
        hits.append({
            "text": doc,
            "source": meta.get("source", ""),
            "score": float(1.0 - dist),   # cosine similarity
            "id": rid,
        })

    return hits


# ── Sparse retrieval ───────────────────────────────────────────────────────────

def bm25_retrieve(query: str, state, k: int = 50, session_id: str = "") -> list[dict]:
    """Score all corpus chunks with BM25Okapi and return top-k.

    Returns list of {text, source, score, id}.
    """
    if not state.corpus_chunks:
        return []

    tokenized_query = tokenize(query)
    scores = state.bm25.get_scores(tokenized_query)

    # Pair with index for ranking
    indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    top = indexed[:k]

    hits: list[dict] = []
    for idx, score in top:
        if idx < len(state.corpus_chunks):
            src = state.chunk_sources[idx] if idx < len(state.chunk_sources) else ""
            if session_id and src in state.uploaded_sources:
                if state.source_sessions.get(src, "") != session_id:
                    continue
            hits.append({
                "text": state.corpus_chunks[idx],
                "source": src,
                "score": float(score),
                "id": f"bm25_{idx}",
            })

    return hits


# ── Reciprocal Rank Fusion ─────────────────────────────────────────────────────

def reciprocal_rank_fusion(
    ranked_lists: list[list[dict]],
    k: int = 60,
) -> list[dict]:
    """Merge multiple ranked lists using Reciprocal Rank Fusion.

    Formula: score(d) = sum over lists of 1 / (rank + k)
    Deduplication key: (text, source).
    Returns list sorted by descending RRF score.
    """
    rrf_scores: dict[tuple, float] = defaultdict(float)
    doc_store: dict[tuple, dict] = {}

    for ranked in ranked_lists:
        for rank, doc in enumerate(ranked, start=1):
            key = (doc["text"], doc["source"])
            rrf_scores[key] += 1.0 / (rank + k)
            if key not in doc_store:
                doc_store[key] = doc

    merged: list[dict] = []
    for key, rrf_score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
        entry = dict(doc_store[key])
        entry["score"] = rrf_score
        merged.append(entry)

    return merged


# ── Hybrid retrieval ───────────────────────────────────────────────────────────

def hybrid_retrieve(query: str, state, top_k: int = 8, use_jina: bool = False, session_id: str = "") -> list[dict]:
    """Run dense + BM25 retrieval, fuse with RRF, return top_k results.

    Returns list of {text, source, score, id}.
    """
    if not state.initialized:
        return []

    query_embedding = embed_query(query, state, use_jina=use_jina)
    collection = state.jina_collection if (use_jina and state.jina_ready) else state.collection

    where = None
    if session_id:
        where = {"$or": [
            {"uploaded": {"$eq": False}},
            {"session_id": {"$eq": session_id}},
        ]}

    dense_hits = []
    if collection.count() > 0:
        dense_hits = dense_retrieve(query_embedding, state, k=50, use_jina=use_jina, where=where)

    bm25_hits = bm25_retrieve(query, state, k=50, session_id=session_id)

    if not dense_hits and not bm25_hits:
        return []

    ranked_lists: list[list[dict]] = []
    if dense_hits:
        ranked_lists.append(dense_hits)
    if bm25_hits:
        ranked_lists.append(bm25_hits)

    fused = reciprocal_rank_fusion(ranked_lists)
    return fused[:top_k]


def multi_query_retrieve(queries: list[str], state, top_k: int = 50, use_jina: bool = False, session_id: str = "") -> list[dict]:
    """Run hybrid_retrieve for each query variant, then RRF-merge across all
    variants' result lists. A chunk surfaced by multiple phrasings of the
    same question ranks higher than one found by only the original wording.
    """
    if not state.initialized or not queries:
        return []

    per_query_lists = [hybrid_retrieve(q, state, top_k=top_k, use_jina=use_jina, session_id=session_id) for q in queries]
    per_query_lists = [lst for lst in per_query_lists if lst]

    if not per_query_lists:
        return []
    if len(per_query_lists) == 1:
        return per_query_lists[0]

    return reciprocal_rank_fusion(per_query_lists)[:top_k]