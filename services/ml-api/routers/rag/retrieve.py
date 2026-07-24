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
            "uploaded": bool(meta.get("uploaded", False)),
            "chunk_type": meta.get("chunk_type"),
            "page": meta.get("page"),
            "bbox": meta.get("bbox"),
            "number_mismatch": meta.get("number_mismatch"),
            "pii_types": meta.get("pii_types"),
        })

    return hits


# ── Sparse retrieval ───────────────────────────────────────────────────────────

def bm25_retrieve(
    query: str, state, k: int = 50, session_id: str = "",
    uploaded_only: bool = False, kb_only: bool = False,
) -> list[dict]:
    """Score all corpus chunks with BM25Okapi and return top-k.

    uploaded_only=True  → only session-uploaded chunks.
    kb_only=True        → only KB (non-uploaded) chunks.
    Default             → KB + session's own uploaded chunks.
    Returns list of {text, source, score, id, uploaded}.
    """
    if not state.corpus_chunks:
        return []

    tokenized_query = tokenize(query)
    scores = state.bm25.get_scores(tokenized_query)

    indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    top = indexed[:k]

    hits: list[dict] = []
    for idx, score in top:
        if idx >= len(state.corpus_chunks):
            continue
        src = state.chunk_sources[idx] if idx < len(state.chunk_sources) else ""
        is_uploaded = src in state.uploaded_sources

        if uploaded_only:
            if not is_uploaded or state.source_sessions.get(src, "") != session_id:
                continue
        elif kb_only:
            if is_uploaded:
                continue
        elif session_id and is_uploaded:
            if state.source_sessions.get(src, "") != session_id:
                continue

        meta = state.chunk_meta[idx] if idx < len(state.chunk_meta) else {}
        hits.append({
            "text": state.corpus_chunks[idx],
            "source": src,
            "score": float(score),
            "id": f"bm25_{idx}",
            "uploaded": is_uploaded,
            "chunk_type": meta.get("chunk_type"),
            "page": meta.get("page"),
            "bbox": meta.get("bbox"),
            "number_mismatch": meta.get("number_mismatch"),
            "pii_types": meta.get("pii_types"),
        })

    return hits


# ── Reciprocal Rank Fusion ─────────────────────────────────────────────────────

def reciprocal_rank_fusion(
    ranked_lists: list[list[dict]],
    k: int = 60,
    type_boost: dict[str, float] | None = None,
) -> list[dict]:
    """Merge multiple ranked lists using Reciprocal Rank Fusion.

    Formula: score(d) = sum over lists of boost(chunk_type) / (rank + k)
    type_boost multiplies each contribution by the doc's chunk_type (default
    1.0 for unlisted types) — corrects for table/figure/image chunks being
    short (a caption or a table's own text) and so structurally weaker
    dense/BM25 matches than verbose prose, even when they're the right answer.
    None (default) preserves today's unweighted behavior.
    Deduplication key: (text, source).
    Returns list sorted by descending RRF score.
    """
    rrf_scores: dict[tuple, float] = defaultdict(float)
    doc_store: dict[tuple, dict] = {}

    for ranked in ranked_lists:
        for rank, doc in enumerate(ranked, start=1):
            key = (doc["text"], doc["source"])
            boost = (type_boost or {}).get(doc.get("chunk_type"), 1.0)
            rrf_scores[key] += boost / (rank + k)
            if key not in doc_store:
                doc_store[key] = doc

    merged: list[dict] = []
    for key, rrf_score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
        entry = dict(doc_store[key])
        entry["score"] = rrf_score
        merged.append(entry)

    return merged


# ── Hybrid retrieval ───────────────────────────────────────────────────────────

def hybrid_retrieve(query: str, state, top_k: int = 8, use_jina: bool = False, session_id: str = "",
                    type_boost: dict[str, float] | None = None) -> list[dict]:
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

    fused = reciprocal_rank_fusion(ranked_lists, type_boost=type_boost)
    return fused[:top_k]


def tiered_hybrid_retrieve(
    query: str, state, top_k: int = 8, use_jina: bool = False, session_id: str = "",
    kb_fallback: bool = True, type_boost: dict[str, float] | None = None,
) -> list[dict]:
    """Two-tier retrieval: session-uploaded docs first, KB fallback if weak match.

    Tier 1 — uploaded docs for this session only.
    If top score ≥ 0.15 → return those.
    Tier 2 — KB-only retrieval; merge with any tier-1 results via RRF.
    Falls through to standard hybrid_retrieve when no uploads exist for session.

    kb_fallback=False confines results to the session's own uploads only —
    for tools (e.g. Multimodal RAG) whose whole point is answering from a
    specific uploaded document, where silently blending in the general
    knowledge base would be a wrong answer, not a helpful fallback.
    """
    has_uploads = session_id and any(
        state.source_sessions.get(s) == session_id for s in state.uploaded_sources
    )
    if not has_uploads:
        return hybrid_retrieve(query, state, top_k=top_k, use_jina=use_jina, session_id=session_id,
                               type_boost=type_boost) if kb_fallback else []

    query_emb = embed_query(query, state, use_jina=use_jina)
    collection = state.jina_collection if (use_jina and state.jina_ready) else state.collection
    count = collection.count() if collection else 0

    # Tier 1: uploaded docs for this session
    where_up = {"$and": [{"uploaded": {"$eq": True}}, {"session_id": {"$eq": session_id}}]}
    dense_up = dense_retrieve(query_emb, state, k=20, use_jina=use_jina, where=where_up) if count > 0 else []
    bm25_up = bm25_retrieve(query, state, k=20, session_id=session_id, uploaded_only=True)
    tier1 = reciprocal_rank_fusion([l for l in [dense_up, bm25_up] if l], type_boost=type_boost) if (dense_up or bm25_up) else []
    for c in tier1:
        c["uploaded"] = True

    if not kb_fallback:
        return tier1[:top_k]

    if tier1 and tier1[0].get("score", 0.0) >= 0.15:
        return tier1[:top_k]

    # Tier 2: KB-only
    where_kb = {"uploaded": {"$eq": False}}
    dense_kb = dense_retrieve(query_emb, state, k=50, use_jina=use_jina, where=where_kb) if count > 0 else []
    bm25_kb = bm25_retrieve(query, state, k=50, kb_only=True)
    tier2 = reciprocal_rank_fusion([l for l in [dense_kb, bm25_kb] if l]) if (dense_kb or bm25_kb) else []

    if not tier1:
        return tier2[:top_k]
    return reciprocal_rank_fusion([tier1, tier2])[:top_k]


def multi_query_retrieve(queries: list[str], state, top_k: int = 50, use_jina: bool = False,
                         session_id: str = "", kb_fallback: bool = True,
                         type_boost: dict[str, float] | None = None) -> list[dict]:
    """Run hybrid_retrieve for each query variant, then RRF-merge across all
    variants' result lists. A chunk surfaced by multiple phrasings of the
    same question ranks higher than one found by only the original wording.
    """
    if not state.initialized or not queries:
        return []

    retrieve_fn = tiered_hybrid_retrieve if session_id else hybrid_retrieve
    per_query_lists = [
        retrieve_fn(q, state, top_k=top_k, use_jina=use_jina, session_id=session_id, kb_fallback=kb_fallback,
                    type_boost=type_boost)
        if session_id else retrieve_fn(q, state, top_k=top_k, use_jina=use_jina, session_id=session_id,
                                       type_boost=type_boost)
        for q in queries
    ]
    per_query_lists = [lst for lst in per_query_lists if lst]

    if not per_query_lists:
        return []
    if len(per_query_lists) == 1:
        return per_query_lists[0]

    return reciprocal_rank_fusion(per_query_lists, type_boost=type_boost)[:top_k]