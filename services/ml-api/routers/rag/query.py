"""RAG query router — /health and /query (streaming SSE) endpoints."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from routers.rag import get_rag_state
from routers.rag.retrieve import multi_query_retrieve
from routers.rag.rerank import rerank
from routers.rag.expand import expand_query
from routers.rag.llm import stream_groq_openai, stream_claude, stream_gemini, stream_cohere

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


# ── SSE generator ──────────────────────────────────────────────────────────────

def _sse_generator(req: QueryRequest):
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

    # 1. Expand the query into a couple of alternate phrasings, retrieve
    #    top-50 candidates per variant (RRF-merged across variants), then
    #    rerank against the ORIGINAL query down to top-8
    queries = expand_query(req.query, provider, model, key)
    candidates = multi_query_retrieve(queries, state, top_k=50)
    chunks = rerank(req.query, candidates, state, top_k=8)

    # 2. Stream source events
    seen_sources: list[str] = []
    for chunk in chunks:
        yield _sse({
            "type": "source",
            "doc": {
                "text": chunk["text"],
                "source": chunk.get("source", ""),
                "score": round(chunk.get("score", 0.0), 4),
            },
        })
        src = chunk.get("source", "")
        if src and src not in seen_sources:
            seen_sources.append(src)

    # 3. Build prompt
    system_prompt = _build_system_prompt(req.tool_context, chunks)
    messages: list[dict] = list(req.history or [])
    messages.append({"role": "user", "content": req.query})

    # 4. Stream token events
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
                yield _sse({"type": "token", "text": token})

    except Exception as exc:
        logger.exception("LLM streaming error: %s", exc)
        yield _sse({"type": "error", "message": f"LLM error: {exc}"})
        return

    # 5. Done event
    yield _sse({"type": "done", "sources": seen_sources})


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/health")
def rag_health():
    """Return RAG subsystem status."""
    try:
        state = get_rag_state()
        return {
            "status": "ok",
            "chunks_indexed": state.collection.count(),
            "embedding_model": "all-MiniLM-L6-v2",
            "initialized": state.initialized,
        }
    except RuntimeError:
        return {
            "status": "initializing",
            "chunks_indexed": 0,
            "embedding_model": "all-MiniLM-L6-v2",
            "initialized": False,
        }


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