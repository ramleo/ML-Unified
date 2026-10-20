"""Fire-and-forget per-query RAG health log (LOGGING_SPEC-style, content-free).

The RAG query path computes signals the perf/cost log (llm_calls) can't see —
whether the semantic cache was hit (no LLM call at all), where the answer came
from (knowledge base / web / dataset), the confidence, and the groundedness of
the answer. Those live only in memory on the Space (routers/rag/analytics.py),
so the owner eval dashboard had no durable view of live RAG health.

This posts one content-free row per answered query to an authenticated frontend
route (same Space→Vercel trust as call_log: the Space holds no Supabase key and
authenticates with AIRAML_LOG_TOKEN; unset → nothing is sent). NEVER the query
text or the answer — only categorical/numeric signals.
"""
from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)

_URL = os.environ.get("RAG_LOG_URL", "https://ml-portfolio-rho.vercel.app/api/rag-log")
_TIMEOUT_S = 4.0


def _gscore(g) -> float | None:
    if isinstance(g, dict):
        v = g.get("score")
        return float(v) if isinstance(v, (int, float)) else None
    return float(g) if isinstance(g, (int, float)) else None


def _post(payload: dict) -> None:
    token = os.environ.get("AIRAML_LOG_TOKEN", "")
    if not token:
        return
    try:
        import httpx
        httpx.post(_URL, json=payload, headers={"x-log-token": token}, timeout=_TIMEOUT_S)
    except Exception as exc:
        logger.debug("rag_log post failed: %s", exc)


def record_rag_query(*, cache_hit: bool, answer_source: str, confidence: str,
                     groundedness, low_confidence: bool, provider: str,
                     latency_ms: float, web_fallback: bool) -> None:
    """Queue one content-free RAG-health row. Returns immediately; never raises."""
    if not os.environ.get("AIRAML_LOG_TOKEN", ""):
        return  # fail closed
    payload = {
        "cache_hit": bool(cache_hit),
        "answer_source": answer_source or "none",
        "confidence": confidence or "",
        "groundedness": _gscore(groundedness),
        "low_confidence": bool(low_confidence),
        "provider": provider or "",
        "latency_ms": int(latency_ms or 0),
        "web_fallback": bool(web_fallback),
    }
    try:
        threading.Thread(target=_post, args=(payload,), daemon=True).start()
    except Exception as exc:
        logger.debug("rag_log thread failed: %s", exc)
