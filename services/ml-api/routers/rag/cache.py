"""Semantic response cache for /rag/query — split out of query.py to stay
under the project's file-length limit."""
from __future__ import annotations

import numpy as np

_CACHE_THRESHOLD = 0.95
_CACHE_MAX = 100


def cosine_sim(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom > 0 else 0.0


def ctx_hash(tool_context: str, session_id: str = "") -> str:
    """Short hash of tool_context + session_id so cache entries are both
    dataset- and session-specific. tool_context alone isn't enough for tools
    whose context string is a fixed constant (e.g. Multimodal RAG) — without
    session_id, every session/uploaded-document would share one cache slot."""
    import hashlib
    key = f"{tool_context.strip()}::{session_id.strip()}"
    return hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()[:8] if key.strip(":") else ""


def cache_lookup(query_emb: list[float], state, provider: str, hash_: str) -> dict | None:
    best_score, best = 0.0, None
    for entry in state.semantic_cache:
        if entry.get("provider") != provider:
            continue
        if entry.get("ctx_hash", "") != hash_:
            continue
        sim = cosine_sim(query_emb, entry["embedding"])
        if sim > best_score:
            best_score, best = sim, entry
    return best if best_score >= _CACHE_THRESHOLD else None


def cache_store(query_emb: list[float], full_text: str, sources: list[str], chunks: list[dict], state,
                provider: str, hash_: str = "", answer_source: str = "knowledge_base",
                confidence: str = "medium") -> None:
    if len(state.semantic_cache) >= _CACHE_MAX:
        state.semantic_cache.pop(0)
    state.semantic_cache.append({
        "embedding": query_emb,
        "full_text": full_text,
        "sources": sources,
        "chunks": chunks,
        "provider": provider,
        "ctx_hash": hash_,
        "answer_source": answer_source,
        "confidence": confidence,
    })
