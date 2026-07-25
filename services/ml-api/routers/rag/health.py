"""RAG health/status endpoints — split out of query.py to stay under the
project's file-length limit."""
from __future__ import annotations

import os
import threading

from fastapi import APIRouter

from routers.rag import get_rag_state, initialize_jina

router = APIRouter()


@router.get("/health")
def rag_health():
    """Return RAG subsystem status."""
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
