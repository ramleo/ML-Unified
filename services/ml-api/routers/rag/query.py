"""RAG query router — /health and /query (streaming SSE) endpoints."""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from routers.rag import get_rag_state
from routers.rag.retrieve import multi_query_retrieve
from routers.rag.rerank import rerank
from routers.rag.expand import expand_query
from routers.rag.crag import web_search_fallback
from routers.rag.citations import build_system_prompt, build_source_doc, likely_used_indices
from routers.rag.generation import build_provider_candidates, stream_with_fallback
from routers.rag.cache import ctx_hash as _ctx_hash, cache_lookup as _cache_lookup, cache_store as _cache_store
from routers.rag.groundedness import score_groundedness
from routers.rag.query_helpers import (
    QueryRequest,
    _resolve_key,
    _detect_type_boost,
    _sse,
    _determine_answer_source,
    _determine_confidence,
    _client_ip,
    _SMALL_CORPUS_MAX_CANDIDATES,
)

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


# ── SSE generator ──────────────────────────────────────────────────────────────

def _sse_generator(req: QueryRequest, client_ip: str = ""):
    t0 = time.time()

    try:
        state = get_rag_state()
    except RuntimeError as exc:
        yield _sse({"type": "error", "message": str(exc)})
        return

    # A shared-link viewer (share_token set) never sees the raw session_id
    # and gets PII redacted from both the LLM's context and the citation
    # text itself — the owner's own requests (no share_token) are untouched.
    redact = bool(req.share_token)
    if req.share_token:
        from routers.rag.share import resolve_share_token
        resolved = resolve_share_token(req.share_token, state, client_ip)
        if not resolved:
            yield _sse({"type": "error", "message": "This shared link has expired or been revoked."})
            return
        req.session_id = resolved

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
    ctx_hash = _ctx_hash(req.tool_context, req.session_id, req.answer_length)
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
            yield _sse({"type": "source", "doc": build_source_doc(chunk, redact=redact)})
        yield _sse({"type": "token", "text": cached["full_text"]})
        jina_status = "ready" if state.jina_ready else ("loading" if state.jina_loading else "idle")
        cached_latency_ms = round((time.time() - t0) * 1000)
        from routers.rag.analytics import record_query
        record_query(cached_latency_ms, cache_hit=True, provider=None)
        yield _sse({
            "type": "done",
            "sources": cached["sources"],
            "low_confidence": False,
            "jina_status": jina_status,
            "embedding_used": "cache",
            "latency_ms": cached_latency_ms,
            "chunks_retrieved": len(cached["chunks"]),
            "rerank_scores": [round(c.get("score", 0.0), 4) for c in cached["chunks"]],
            "cache_hit": True,
            "answer_source": cached.get("answer_source", "knowledge_base"),
            "confidence": cached.get("confidence", "medium"),
            "groundedness": cached.get("groundedness"),
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
                                      type_boost=type_boost, chunk_type_filter=req.chunk_type_filter,
                                      entity_type_filter=req.entity_type_filter)
    # The default absolute floor is tuned to filter noise out of a large,
    # mixed general corpus. In restrict_to_uploads mode, tier-1 retrieval has
    # already scoped candidates to just the user's own small uploaded
    # document — the same floor can discard the ONLY relevant candidate that
    # exists (observed directly: candidates_retrieved=1, chunks_retrieved=0).
    is_small_corpus = req.restrict_to_uploads and len(candidates) <= _SMALL_CORPUS_MAX_CANDIDATES
    chunks = rerank(req.query, candidates, state,
                    top_k=len(candidates) if is_small_corpus else 5,
                    abs_floor=0.0 if req.restrict_to_uploads else None,
                    keep_all=is_small_corpus)

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
        yield _sse({"type": "source", "doc": build_source_doc(chunk, redact=redact)})
        src = chunk.get("source", "")
        if src and src not in seen_sources:
            seen_sources.append(src)

    # 3. Build prompt
    system_prompt = build_system_prompt(req.tool_context, chunks, restrict_to_uploads=req.restrict_to_uploads,
                                        answer_length=req.answer_length, redact=redact)
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

    # 4b. Groundedness (MMRAG-04) — cheap, reuses the already-loaded embedder,
    # so it's computed unconditionally rather than gated behind a flag.
    full_text = "".join(full_text_parts)
    groundedness = None
    if full_text and not generation_failed:
        try:
            groundedness = score_groundedness(full_text, chunks, state.embedding_fn)
        except Exception as exc:
            logger.warning("Groundedness scoring failed: %s", exc)

    # 4c. Self-correction retry — groundedness (4b) is computed on every
    # answer but historically only ever displayed as a badge. When it comes
    # back "low", broaden retrieval (drop the relevance floor, pull more
    # candidates already fetched in step 1 — no extra retrieval call) and
    # regenerate once. A single retry only, and only on the rare low-
    # confidence case, so the common already-grounded answer streams exactly
    # as before with no added latency. The retry's own tokens stream as a
    # fresh "retry" + "source"/"token" sequence so the client can swap out
    # the first attempt rather than appending onto it.
    self_corrected = False
    if full_text and not generation_failed and candidates and groundedness and groundedness.get("level") == "low" and not web_fallback_used:
        broadened = rerank(req.query, candidates, state,
                           top_k=min(len(candidates), 10), abs_floor=0.0, keep_all=False)
        if broadened and broadened != chunks:
            yield _sse({"type": "retry", "reason": "low_groundedness"})
            for chunk in broadened:
                yield _sse({"type": "source", "doc": build_source_doc(chunk, redact=redact)})

            retry_system_prompt = build_system_prompt(req.tool_context, broadened, restrict_to_uploads=req.restrict_to_uploads,
                                                       answer_length=req.answer_length, redact=redact)
            retry_parts: list[str] = []
            retry_meta: dict = {}
            retry_failed = False
            for token in stream_with_fallback(provider_candidates, messages, retry_system_prompt, retry_meta):
                if token.startswith("[") and "error" in token.lower():
                    retry_failed = True
                retry_parts.append(token)
                yield _sse({"type": "token", "text": token})

            if not retry_meta.get("mid_stream_error") and not retry_failed and retry_parts:
                retry_text = "".join(retry_parts)
                try:
                    retry_groundedness = score_groundedness(retry_text, broadened, state.embedding_fn)
                except Exception as exc:
                    logger.warning("Retry groundedness scoring failed: %s", exc)
                    retry_groundedness = None
                # Only keep the retry if it's actually no worse — never trade
                # a complete (if imperfectly grounded) answer for a worse one.
                if not retry_groundedness or retry_groundedness.get("score", 0) >= groundedness.get("score", 0):
                    chunks = broadened
                    full_text = retry_text
                    groundedness = retry_groundedness or groundedness
                    served_provider = retry_meta.get("served_provider", provider)
                    served_model = retry_meta.get("served_model", model)
                    seen_sources = []
                    for chunk in broadened:
                        src = chunk.get("source", "")
                        if src and src not in seen_sources:
                            seen_sources.append(src)
                    self_corrected = True

    # 5. Store in semantic cache — skip on provider errors, and skip entirely
    # for restrict_to_uploads (correctness over latency for single-doc Q&A).
    if query_emb is not None and full_text and not generation_failed and not req.restrict_to_uploads:
        try:
            _cache_store(query_emb, full_text, seen_sources, chunks, state, provider, ctx_hash, answer_source,
                        confidence, groundedness)
        except Exception as exc:
            logger.warning("Cache store failed: %s", exc)

    # 6. Done event with metadata
    jina_status = "ready" if state.jina_ready else ("loading" if state.jina_loading else "idle")
    likely_used = likely_used_indices(chunks, full_text)
    final_latency_ms = round((time.time() - t0) * 1000)
    from routers.rag.analytics import record_query
    record_query(final_latency_ms, cache_hit=False, provider=served_provider)
    yield _sse({
        "type": "done",
        "sources": seen_sources,
        "likely_used_sources": likely_used,
        "low_confidence": low_confidence,
        "jina_status": jina_status,
        "embedding_used": "jina" if use_jina else "minilm",
        "latency_ms": final_latency_ms,
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
        "groundedness": groundedness,
        "self_corrected": self_corrected,
    })


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/query")
def rag_query(req: QueryRequest, request: Request):
    """Hybrid-retrieve relevant chunks then stream an LLM response as SSE."""
    return StreamingResponse(
        _sse_generator(req, client_ip=_client_ip(request)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )