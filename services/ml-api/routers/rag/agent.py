"""LangGraph agentic RAG — POST /rag/agent (SSE streaming).

Graph: router → retriever → grader → (rewriter → retriever)* → generator
Node functions and meta-LLM helper live in agent_nodes.py.
Max 2 rewrite loops bound latency; generator streams via existing llm.py helpers.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional, List, TypedDict

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from routers.rag.llm import stream_groq_openai, stream_claude, stream_gemini, stream_cohere
from routers.rag.query import _build_system_prompt, _resolve_key
from routers.rag.agent_nodes import (
    node_router, node_retrieve, node_grade, node_rewrite,
    edge_after_retrieve, edge_after_grade,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Agent state ────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    query:        str
    final_query:  str
    tool_context: str
    history:      list
    chunks:       list
    loop_count:   int
    route:        str
    grade:        str
    provider:     str
    model:        str
    user_key:     str

# ── Compile graph (once at import) ────────────────────────────────────────────

_compiled = None
_LANGGRAPH_OK = False

try:
    from langgraph.graph import StateGraph, END as _END

    _g = StateGraph(AgentState)
    _g.add_node("router",   node_router)
    _g.add_node("retrieve", node_retrieve)
    _g.add_node("grade",    node_grade)
    _g.add_node("rewrite",  node_rewrite)
    _g.set_entry_point("router")
    _g.add_edge("router",  "retrieve")
    _g.add_conditional_edges("retrieve", edge_after_retrieve,
                             {"grade": "grade", "generate": _END})
    _g.add_conditional_edges("grade",    edge_after_grade,
                             {"generate": _END, "rewrite": "rewrite"})
    _g.add_edge("rewrite", "retrieve")
    _compiled = _g.compile()
    _LANGGRAPH_OK = True
    logger.info("LangGraph agent compiled successfully")
except ImportError:
    logger.warning("langgraph not installed — /rag/agent uses direct retrieval")
except Exception as exc:
    logger.error("LangGraph compile error: %s", exc)

# ── SSE helper ─────────────────────────────────────────────────────────────────

_STEP_MAP = {
    "router":   "routing",
    "retrieve": "retrieving",
    "grade":    "grading",
    "rewrite":  "rewriting",
}

_OPENAI_COMPAT_BASES = {
    "groq":       "https://api.groq.com/openai/v1",
    "mistral":    "https://api.mistral.ai/v1",
    "perplexity": "https://api.perplexity.ai",
}

_SERVER_KEY_ENVS = {
    "gemini":  "GEMINI_API_KEY",
    "claude":  "ANTHROPIC_API_KEY",
    "openai":  "OPENAI_API_KEY",
    "groq":    "GROQ_API_KEY",
    "cohere":  "COHERE_API_KEY",
}


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"

# ── SSE generator ──────────────────────────────────────────────────────────────

def _agent_generator(
    query: str, tool_context: str, history: list,
    provider: str, model: str, user_key: str,
):
    t0 = time.time()

    initial: AgentState = {
        "query":        query,
        "final_query":  query,
        "tool_context": tool_context,
        "history":      history,
        "chunks":       [],
        "loop_count":   0,
        "route":        "complex",
        "grade":        "good",
        "provider":     provider,
        "model":        model,
        "user_key":     user_key,
    }
    final_state: dict = dict(initial)

    # ── Run LangGraph ─────────────────────────────────────────────────────────
    if _LANGGRAPH_OK and _compiled:
        try:
            for event in _compiled.stream(initial, stream_mode="updates"):
                for node_name, state_update in event.items():
                    step = _STEP_MAP.get(node_name, node_name)
                    yield _sse({
                        "type":  "agent_step",
                        "step":  step,
                        "loop":  state_update.get("loop_count",
                                                  final_state.get("loop_count", 0)),
                        "query": state_update.get("final_query",
                                                  final_state["final_query"]),
                    })
                    final_state.update(state_update)
        except Exception as exc:
            logger.error("LangGraph stream error: %s", exc)
            yield _sse({"type": "warning",
                        "message": f"Agent loop error: {exc}. Using direct retrieval."})
            final_state = dict(initial)
            yield _sse({"type": "agent_step", "step": "retrieving", "loop": 0,
                        "query": query})
            final_state.update(node_retrieve(final_state))
    else:
        yield _sse({"type": "agent_step", "step": "retrieving", "loop": 0, "query": query})
        final_state.update(node_retrieve(final_state))

    # ── Web fallback (no chunks or grader said websearch) ─────────────────────
    kb_chunks = final_state.get("chunks", [])
    web_used = False
    web_fallback_tried = False
    chunks = kb_chunks
    if not kb_chunks or final_state.get("grade") == "websearch":
        web_fallback_tried = True
        try:
            from routers.rag.crag import web_search_fallback
            web_chunks = web_search_fallback(
                final_state.get("final_query") or query
            )
            if web_chunks:
                chunks = web_chunks
                web_used = True
        except Exception as exc:
            logger.warning("web fallback failed: %s", exc)
        if not web_used:
            # Web blocked/failed — only keep KB chunks that cleared the original floor
            chunks = [c for c in kb_chunks if float(c.get("score", 0)) >= 0.01]

    # ── Emit sources ──────────────────────────────────────────────────────────
    seen_sources: list[str] = []
    for c in chunks:
        src = c.get("source", "")
        yield _sse({"type": "source", "doc": {
            "source":        src,
            "text":          c.get("text", "")[:300],
            "score":         round(float(c.get("score", 0)), 4),
            "display_score": round(float(c.get("display_score",
                                               c.get("score", 0))), 4),
        }})
        if src and src not in seen_sources:
            seen_sources.append(src)

    yield _sse({"type": "agent_step", "step": "generating"})

    if not user_key:
        yield _sse({"type": "error", "message": "No API key available for generation."})
        yield _sse({"type": "done", "sources": seen_sources,
                    "loops": final_state.get("loop_count", 0),
                    "rewritten": final_state.get("final_query") != query,
                    "web_fallback_used": web_used,
                    "latency_ms": round((time.time() - t0) * 1000)})
        return

    # ── Stream LLM response ───────────────────────────────────────────────────
    system_prompt = _build_system_prompt(tool_context, chunks)
    messages: list[dict] = list(history or [])[-6:]
    messages.append({"role": "user",
                     "content": final_state.get("final_query") or query})

    try:
        if provider in ("groq", "openai", "mistral", "perplexity"):
            import openai as _oai
            client = _oai.OpenAI(
                api_key=user_key,
                **({"base_url": _OPENAI_COMPAT_BASES[provider]}
                   if provider in _OPENAI_COMPAT_BASES else {}),
                timeout=60,
            )
            with client.chat.completions.create(
                model=model, messages=messages, stream=True
            ) as stream:
                for chunk in stream:
                    token = getattr(chunk.choices[0].delta, "content", None)
                    if token:
                        yield _sse({"type": "token", "text": token})

        elif provider == "claude":
            for token in stream_claude(model, user_key, messages, system_prompt):
                if token:
                    yield _sse({"type": "token", "text": token})

        elif provider == "gemini":
            for token in stream_gemini(model, user_key, messages, system_prompt):
                if token:
                    yield _sse({"type": "token", "text": token})

        elif provider == "cohere":
            for token in stream_cohere(model, user_key, messages, system_prompt):
                if token:
                    yield _sse({"type": "token", "text": token})

        else:
            yield _sse({"type": "error",
                        "message": f"Unsupported provider '{provider}'."})
            return

    except Exception as exc:
        logger.error("LLM generation error provider=%s model=%s: %s",
                     provider, model, exc)
        yield _sse({"type": "error",
                    "message": f"Generation failed ({provider}/{model}): {exc}"})
        return

    yield _sse({
        "type":             "done",
        "sources":          seen_sources,
        "loops":            final_state.get("loop_count", 0),
        "rewritten":        final_state.get("final_query") != query,
        "web_fallback_used": web_used,
        "low_confidence":   web_fallback_tried and not web_used,
        "latency_ms":       round((time.time() - t0) * 1000),
    })

# ── Request schema + endpoint ──────────────────────────────────────────────────

class AgentRequest(BaseModel):
    query:        str
    tool_context: str = ""
    history:      List[dict] = []
    provider:     str = "gemini"
    model:        str = "gemini-2.5-flash"
    user_key:     Optional[str] = None


@router.post("/agent")
def rag_agent(req: AgentRequest):
    """LangGraph agentic RAG: route → retrieve → grade → (rewrite)* → stream."""
    if not req.query.strip():
        return StreamingResponse(
            iter([_sse({"type": "error", "message": "query is required"})]),
            media_type="text/event-stream",
        )

    user_key = (req.user_key or "").strip()
    if not user_key:
        env = _SERVER_KEY_ENVS.get(req.provider.lower(), "")
        user_key = os.environ.get(env, "") if env else ""

    return StreamingResponse(
        _agent_generator(
            query=req.query.strip(),
            tool_context=req.tool_context.strip(),
            history=req.history,
            provider=req.provider.lower(),
            model=req.model,
            user_key=user_key,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
