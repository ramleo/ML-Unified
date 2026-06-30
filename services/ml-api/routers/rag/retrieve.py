"""RAG retrieval — dense (ChromaDB), sparse (BM25), and hybrid via RRF."""
from __future__ import annotations

import logging
from collections import defaultdict

from routers.rag.text import tokenize

logger = logging.getLogger(__name__)


# ── Query embedding ────────────────────────────────────────────────────────────

def embed_query(query: str, state) -> list[float]:
    """Embed a single query string using the state's embedding function."""
    result = state.embedding_fn([query])
    return result[0]


# ── Dense retrieval ────────────────────────────────────────────────────────────

def dense_retrieve(query_embedding: list[float], state, k: int = 50) -> list[dict]:
    """Query ChromaDB for the top-k nearest neighbours.

    Returns list of {text, source, score, id}.
    score is cosine similarity (1 - distance for cosine space).
    """
    n_results = min(k, max(state.collection.count(), 1))

    results = state.collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
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

def bm25_retrieve(query: str, state, k: int = 50) -> list[dict]:
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
            hits.append({
                "text": state.corpus_chunks[idx],
                "source": state.chunk_sources[idx] if idx < len(state.chunk_sources) else "",
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

def hybrid_retrieve(query: str, state, top_k: int = 8) -> list[dict]:
    """Run dense + BM25 retrieval, fuse with RRF, return top_k results.

    Returns list of {text, source, score, id}.
    """
    if not state.initialized:
        return []

    query_embedding = embed_query(query, state)

    dense_hits = []
    if state.collection.count() > 0:
        dense_hits = dense_retrieve(query_embedding, state, k=50)

    bm25_hits = bm25_retrieve(query, state, k=50)

    if not dense_hits and not bm25_hits:
        return []

    ranked_lists: list[list[dict]] = []
    if dense_hits:
        ranked_lists.append(dense_hits)
    if bm25_hits:
        ranked_lists.append(bm25_hits)

    fused = reciprocal_rank_fusion(ranked_lists)
    return fused[:top_k]