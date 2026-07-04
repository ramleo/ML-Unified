"""RAG query router — /health and /query (streaming SSE) endpoints."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Optional

import numpy as np
import threading

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from routers.rag import get_rag_state, initialize_jina
from routers.rag.retrieve import multi_query_retrieve
from routers.rag.rerank import rerank
from routers.rag.expand import expand_query
from routers.rag.llm import stream_groq_openai, stream_claude, stream_gemini, stream_cohere
from routers.rag.crag import web_search_fallback

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Default model ──────────────────────────────────────────────────────────────
_DEFAULT_PROVIDER = "groq"
_DEFAULT_MODEL = "llama-3.3-70b-versatile"

# ── Env var fallbacks ──────────────────────────────────────────────────────────
_ENV_KEYS = {
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "cohere": "COHERE_API_KEY",
}


# ── Schemas ────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    tool_context: str = ""
    history: list[dict] = []
    provider: str = _DEFAULT_PROVIDER
    model: str = _DEFAULT_MODEL
    user_key: Optional[str] = None
    embedding_model: str = "minilm"  # "minilm" | "jina"
    session_id: str = ""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _resolve_key(provider: str, user_key: Optional[str]) -> str:
    if user_key:
        return user_key
    env = _ENV_KEYS.get(provider, "")
    return os.environ.get(env, "")


def _sse(obj: Any) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def _build_system_prompt(tool_context: str, chunks: list[dict]) -> str:
    parts: list[str] = []
    if tool_context:
        parts.append(tool_context.strip())

    if chunks:
        parts.append("Use the following retrieved knowledge to answer the user's question:")
        parts.append("---")
        for c in chunks:
            src = c.get("source", "unknown")
            text = c.get("text", "")
            parts.append(f"[{src}]\n{text}")
            parts.append("---")

    return "\n\n".join(parts) if parts else "You are a helpful AI assistant."


# ── Semantic cache ─────────────────────────────────────────────────────────────

_CACHE_THRESHOLD = 0.95
_CACHE_MAX = 100


def _cosine_sim(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom > 0 else 0.0


def _cache_lookup(query_emb: list[float], state) -> dict | None:
    best_score, best = 0.0, None
    for entry in state.semantic_cache:
        sim = _cosine_sim(query_emb, entry["embedding"])
        if sim > best_score:
            best_score, best = sim, entry
    return best if best_score >= _CACHE_THRESHOLD else None


def _cache_store(query_emb: list[float], full_text: str, sources: list[str], chunks: list[dict], state) -> None:
    if len(state.semantic_cache) >= _CACHE_MAX:
        state.semantic_cache.pop(0)
    state.semantic_cache.append({
        "embedding": query_emb,
        "full_text": full_text,
        "sources": sources,
        "chunks": chunks,
    })


# ── SSE generator ──────────────────────────────────────────────────────────────

def _sse_generator(req: QueryRequest):
    t0 = time.time()

    try:
        state = get_rag_state()
    except RuntimeError as exc:
        yield _sse({"type": "error", "message": str(exc)})
        return

    provider = (req.provider or _DEFAULT_PROVIDER).lower()
    model = req.model or _DEFAULT_MODEL
    key = _resolve_key(provider, req.user_key)

    if not key:
        yield _sse({"type": "error", "message": f"No API key for provider '{provider}'."})
        return

    # 0. Semantic cache check (embed with MiniLM regardless of embedding_model setting)
    try:
        query_emb = state.embedding_fn([req.query])[0]
        cached = _cache_lookup(query_emb, state)
    except Exception:
        query_emb = None
        cached = None

    if cached:
        for chunk in cached["chunks"]:
            yield _sse({
                "type": "source",
                "doc": {
                    "text": chunk["text"],
                    "source": chunk.get("source", ""),
                    "score": round(chunk.get("score", 0.0), 4),
                    "display_score": round(chunk.get("display_score", chunk.get("score", 0.0)), 4),
                },
            })
        yield _sse({"type": "token", "text": cached["full_text"]})
        jina_status = "ready" if state.jina_ready else ("loading" if state.jina_loading else "idle")
        yield _sse({
            "type": "done",
            "sources": cached["sources"],
            "low_confidence": False,
            "jina_status": jina_status,
            "embedding_used": "cache",
            "latency_ms": round((time.time() - t0) * 1000),
            "chunks_retrieved": len(cached["chunks"]),
            "rerank_scores": [round(c.get("score", 0.0), 4) for c in cached["chunks"]],
            "cache_hit": True,
        })
        return

    # 1. Expand query, retrieve top-50 candidates per variant (RRF-merged), rerank to top-8
    use_jina = req.embedding_model == "jina" and state.jina_ready
    queries = expand_query(req.query, provider, model, key)
    candidates = multi_query_retrieve(queries, state, top_k=20, use_jina=use_jina, session_id=req.session_id)
    chunks = rerank(req.query, candidates, state, top_k=5)

    top_raw = chunks[0].get("score", 0.0) if chunks else 0.0
    low_confidence = not chunks or top_raw < 0.05

    # 2a. CRAG: if confidence is low, supplement with web search before streaming
    web_fallback_used = False
    if low_confidence:
        web_chunks = web_search_fallback(req.query)
        if web_chunks:
            chunks = chunks + web_chunks
            web_fallback_used = True
            low_confidence = False  # we now have something to work with

    # 2b. Stream source events
    seen_sources: list[str] = []
    for chunk in chunks:
        yield _sse({
            "type": "source",
            "doc": {
                "text": chunk["text"],
                "source": chunk.get("source", ""),
                "score": round(chunk.get("score", 0.0), 4),
                "display_score": round(chunk.get("display_score", chunk.get("score", 0.0)), 4),
            },
        })
        src = chunk.get("source", "")
        if src and src not in seen_sources:
            seen_sources.append(src)

    # 3. Build prompt
    system_prompt = _build_system_prompt(req.tool_context, chunks)
    messages: list[dict] = list(req.history or [])
    messages.append({"role": "user", "content": req.query})

    # 4. Stream token events; collect full text for cache
    full_text_parts: list[str] = []
    generation_failed = False
    try:
        if provider in ("groq", "openai"):
            token_iter = stream_groq_openai(provider, model, key, messages)
        elif provider == "claude":
            token_iter = stream_claude(model, key, messages, system_prompt)
        elif provider == "gemini":
            token_iter = stream_gemini(model, key, messages, system_prompt)
        elif provider == "cohere":
            token_iter = stream_cohere(model, key, messages, system_prompt)
        else:
            yield _sse({"type": "error", "message": f"Unknown provider '{provider}'."})
            return

        for token in token_iter:
            if token:
                # Provider error strings (e.g. "[Cohere error 429]") must not be cached
                if token.startswith("[") and "error" in token.lower():
                    generation_failed = True
                full_text_parts.append(token)
                yield _sse({"type": "token", "text": token})

    except Exception as exc:
        logger.exception("LLM streaming error: %s", exc)
        yield _sse({"type": "error", "message": f"Generation failed ({provider}/{model}): {exc}"})
        return

    # 5. Store in semantic cache — skip on provider errors to avoid caching error strings
    full_text = "".join(full_text_parts)
    if query_emb is not None and full_text and not generation_failed:
        try:
            _cache_store(query_emb, full_text, seen_sources, chunks, state)
        except Exception as exc:
            logger.warning("Cache store failed: %s", exc)

    # 6. Done event with metadata
    jina_status = "ready" if state.jina_ready else ("loading" if state.jina_loading else "idle")
    yield _sse({
        "type": "done",
        "sources": seen_sources,
        "low_confidence": low_confidence,
        "jina_status": jina_status,
        "embedding_used": "jina" if use_jina else "minilm",
        "latency_ms": round((time.time() - t0) * 1000),
        "chunks_retrieved": len(chunks),
        "rerank_scores": [round(c.get("score", 0.0), 4) for c in chunks],
        "cache_hit": False,
        "web_fallback_used": web_fallback_used,
        "expanded_queries": queries[1:],
        "candidates_retrieved": len(candidates),
    })


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/health")
def rag_health():
    """Return RAG subsystem status."""
    import os
    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    tavily_status = "not_set"
    if tavily_key:
        try:
            from tavily import TavilyClient
            TavilyClient(api_key=tavily_key).search("test", max_results=1)
            tavily_status = "ok"
        except Exception as exc:
            tavily_status = f"error: {exc}"
    try:
        state = get_rag_state()
        return {
            "status": "ok" if not state.init_error else "error",
            "chunks_indexed": state.collection.count() if state.collection is not None else 0,
            "embedding_model": "all-MiniLM-L6-v2",
            "jina_ready": state.jina_ready,
            "jina_loading": state.jina_loading,
            "jina_error": state.jina_error,
            "init_error": state.init_error,
            "initialized": state.initialized,
            "tavily": tavily_status,
        }
    except RuntimeError:
        return {
            "status": "initializing",
            "chunks_indexed": 0,
            "embedding_model": "all-MiniLM-L6-v2",
            "jina_ready": False,
            "jina_loading": False,
            "initialized": False,
            "tavily": tavily_status,
        }


@router.post("/prepare-jina")
def prepare_jina():
    """Trigger lazy loading of Jina v3 in a background thread."""
    try:
        state = get_rag_state()
    except RuntimeError as exc:
        return {"status": "error", "message": str(exc)}
    if state.jina_ready:
        return {"status": "ready"}
    if state.jina_loading:
        return {"status": "loading"}
    threading.Thread(target=initialize_jina, args=(state,), daemon=True).start()
    return {"status": "loading"}


@router.post("/query")
def rag_query(req: QueryRequest):
    """Hybrid-retrieve relevant chunks then stream an LLM response as SSE."""
    return StreamingResponse(
        _sse_generator(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )