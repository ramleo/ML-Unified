"""RAG query router — /health and /query (streaming SSE) endpoints."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Optional

import threading

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from routers.rag import get_rag_state, initialize_jina
from routers.rag.retrieve import multi_query_retrieve
from routers.rag.rerank import rerank
from routers.rag.expand import expand_query
from routers.rag.crag import web_search_fallback
from routers.rag.citations import build_system_prompt, build_source_doc
from routers.rag.generation import build_provider_candidates, stream_with_fallback
from routers.rag.cache import ctx_hash as _ctx_hash, cache_lookup as _cache_lookup, cache_store as _cache_store

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Default model ──────────────────────────────────────────────────────────────
_DEFAULT_PROVIDER = "groq"
_DEFAULT_MODEL = "llama-3.3-70b-versatile"

# Query expansion always uses its own fixed, fast, server-key-only provider —
# NEVER the user's selected/BYOK provider. It's an optional quality boost
# (expand.py degrades to [query] alone on any failure), so it must not spend
# the same rate-limit budget the user's actual answer generation needs right
# after it. Found live: selecting Cohere fired two real Cohere calls per
# question (expansion + generation) against the same limit, both 429ing.
_EXPANSION_PROVIDER = "groq"
_EXPANSION_MODEL = "llama-3.1-8b-instant"

# A flat boost on every restrict_to_uploads query would over-promote a figure
# caption even on a purely textual question. Instead, only boost the specific
# chunk_type(s) the question itself seems to be asking about.
_TYPE_KEYWORDS = {
    "table": ("table", "row", "column", "spreadsheet", "cell"),
    "figure": ("chart", "graph", "diagram", "figure", "plot", "trend", "visual"),
    "image": ("image", "photo", "picture", "photograph"),
}


def _detect_type_boost(query: str) -> dict[str, float] | None:
    q = query.lower()
    boost = {t: 1.3 for t, kws in _TYPE_KEYWORDS.items() if any(kw in q for kw in kws)}
    return boost or None


# ── Env var fallbacks ──────────────────────────────────────────────────────────
_ENV_KEYS = {
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "cohere": "COHERE_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    # perplexity intentionally has no server default — BYOK only, matching
    # its frontend envKeyNote ("Paste your Perplexity API key").
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
    force_web: bool = False
    restrict_to_uploads: bool = False  # answer ONLY from this session's uploads — no KB, no web


# ── Helpers ────────────────────────────────────────────────────────────────────

def _resolve_key(provider: str, user_key: Optional[str]) -> str:
    if user_key:
        return user_key
    env = _ENV_KEYS.get(provider, "")
    return os.environ.get(env, "")


def _sse(obj: Any) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def _determine_answer_source(chunks: list[dict], web_fallback_used: bool, has_dataset: bool) -> str:
    if web_fallback_used:
        return "web"
    if not chunks:
        return "dataset" if has_dataset else "none"
    if chunks[0].get("uploaded"):
        return "uploaded_doc"
    if has_dataset:
        return "dataset"
    return "knowledge_base"


def _determine_confidence(chunks: list[dict], answer_source: str, has_dataset: bool = False) -> str:
    if answer_source in ("dataset", "none"):
        return "high"
    top_score = chunks[0].get("score", 0.0) if chunks else 0.0
    # When dataset is also loaded, LLM has extra grounding — bump one tier
    if has_dataset:
        if top_score >= 0.3:
            return "high"
        if top_score >= 0.05:
            return "medium"
        return "medium"
    if top_score >= 0.5:
        return "high"
    if top_score >= 0.15:
        return "medium"
    return "low"


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

    has_dataset = bool(req.tool_context.strip())

    # 0. Semantic cache check (embed with MiniLM regardless of embedding_model setting).
    # ctx_hash previously derived only from tool_context, which is a FIXED
    # constant for tools like Multimodal RAG — every session/document shared
    # one cache slot, so one user's uploaded-document answer could leak into
    # a different session's differently-uploaded document if the two
    # questions happened to embed as similar enough. Folding session_id in
    # fixes that for every tool that sets one; restrict_to_uploads mode
    # additionally skips the cache outright, since correctness for a
    # single-document Q&A tool matters more than the latency savings.
    ctx_hash = _ctx_hash(req.tool_context, req.session_id)
    try:
        query_emb = state.embedding_fn([req.query])[0]
        cached = None if req.restrict_to_uploads else _cache_lookup(query_emb, state, provider, ctx_hash)
    except Exception:
        query_emb = None
        cached = None

    # Discard stale error entries or bypass cache when force_web is active
    if cached and cached.get("full_text", "").startswith("[") and "error" in cached.get("full_text", "").lower():
        cached = None
    if req.force_web:
        cached = None

    if cached:
        for chunk in cached["chunks"]:
            yield _sse({"type": "source", "doc": build_source_doc(chunk)})
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
            "answer_source": cached.get("answer_source", "knowledge_base"),
            "confidence": cached.get("confidence", "medium"),
        })
        return

    # 1. Expand query, retrieve top-50 candidates per variant (RRF-merged), rerank to top-8
    use_jina = req.embedding_model == "jina" and state.jina_ready
    expansion_key = _resolve_key(_EXPANSION_PROVIDER, None)
    queries = expand_query(req.query, _EXPANSION_PROVIDER, _EXPANSION_MODEL, expansion_key)
    # Table/figure/image chunks are short (a caption, a table's own text) and so
    # structurally weaker dense/BM25 matches than verbose prose — without a
    # boost they can lose the RRF fusion race even when they hold the answer
    # (observed: a resume's short timeline caption losing to a longer prose
    # chunk). Only applied in restrict_to_uploads mode (Multimodal RAG) AND
    # only for the chunk_type(s) the question actually seems to be about.
    type_boost = _detect_type_boost(req.query) if req.restrict_to_uploads else None
    candidates = multi_query_retrieve(queries, state, top_k=20, use_jina=use_jina,
                                      session_id=req.session_id, kb_fallback=not req.restrict_to_uploads,
                                      type_boost=type_boost)
    # The default absolute floor is tuned to filter noise out of a large,
    # mixed general corpus. In restrict_to_uploads mode, tier-1 retrieval has
    # already scoped candidates to just the user's own small uploaded
    # document — the same floor can discard the ONLY relevant candidate that
    # exists (observed directly: candidates_retrieved=1, chunks_retrieved=0).
    chunks = rerank(req.query, candidates, state, top_k=5,
                    abs_floor=0.0 if req.restrict_to_uploads else None)

    top_raw = chunks[0].get("score", 0.0) if chunks else 0.0
    low_confidence = not chunks or top_raw < 0.05

    # 2a. CRAG: fire when confidence is low and no dataset, OR when user forces web override.
    # Never for restrict_to_uploads — a tool answering from one specific
    # document must not quietly answer from the open web instead.
    web_fallback_used = False
    if not req.restrict_to_uploads and ((low_confidence and not has_dataset) or req.force_web):
        web_chunks = web_search_fallback(req.query)
        if web_chunks:
            chunks = web_chunks if req.force_web else chunks + web_chunks
            web_fallback_used = True
            low_confidence = False  # we now have something to work with

    answer_source = _determine_answer_source(chunks, web_fallback_used, has_dataset)
    confidence = _determine_confidence(chunks, answer_source, has_dataset)

    # 2b. Stream source events
    seen_sources: list[str] = []
    for chunk in chunks:
        yield _sse({"type": "source", "doc": build_source_doc(chunk)})
        src = chunk.get("source", "")
        if src and src not in seen_sources:
            seen_sources.append(src)

    # 3. Build prompt
    system_prompt = build_system_prompt(req.tool_context, chunks, restrict_to_uploads=req.restrict_to_uploads)
    messages: list[dict] = list(req.history or [])
    messages.append({"role": "user", "content": req.query})

    # 4. Stream token events; collect full text for cache. Provider fallback
    # cascade lives in generation.py — if the selected provider fails before
    # any token is produced, it silently retries with another provider
    # rather than surfacing a raw API error; a failure AFTER tokens have
    # started streaming is not retried (would garble the response) and comes
    # back via meta['mid_stream_error'] instead.
    full_text_parts: list[str] = []
    generation_failed = False
    meta: dict = {}

    provider_candidates = build_provider_candidates(provider, model, key, _resolve_key)
    for token in stream_with_fallback(provider_candidates, messages, system_prompt, meta):
        if token.startswith("[") and "error" in token.lower():  # e.g. "[Cohere error 429]" — must not be cached
            generation_failed = True
        full_text_parts.append(token)
        yield _sse({"type": "token", "text": token})

    if meta.get("mid_stream_error"):
        yield _sse({"type": "error", "message": meta["mid_stream_error"]})
        return
    if meta.get("error") and not full_text_parts:
        yield _sse({"type": "error", "message": meta["error"]})
        return

    served_provider = meta.get("served_provider", provider)
    served_model = meta.get("served_model", model)

    # 5. Store in semantic cache — skip on provider errors, and skip entirely
    # for restrict_to_uploads (correctness over latency for single-doc Q&A).
    full_text = "".join(full_text_parts)
    if query_emb is not None and full_text and not generation_failed and not req.restrict_to_uploads:
        try:
            _cache_store(query_emb, full_text, seen_sources, chunks, state, provider, ctx_hash, answer_source, confidence)
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
        "answer_source": answer_source,
        "confidence": confidence,
        "served_provider": served_provider,
        "served_model": served_model,
        "primary_provider": meta.get("primary_provider"),
        "primary_failure": meta.get("primary_failure"),
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