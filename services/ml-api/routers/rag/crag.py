"""CRAG — web search fallback for the agentic RAG pipeline.

Primary:  Tavily API (TAVILY_API_KEY env var) — works from any server/cloud env.
Fallback: DuckDuckGo Instant Answer (no key, encyclopedic topics only).
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 10
_MAX_RESULTS = 3
_USER_AGENT = "Mozilla/5.0 (compatible; RAGBot/1.0)"


def _tavily_search(query: str) -> list[dict]:
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        return []
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        resp = client.search(query, max_results=_MAX_RESULTS, search_depth="basic")
        results: list[dict] = []
        for r in resp.get("results", [])[:_MAX_RESULTS]:
            text = (r.get("content") or "").strip()
            url  = r.get("url", "")
            if len(text) > 30:
                results.append(_chunk(text, url, score=0.70))
        return results
    except Exception as exc:
        logger.warning("Tavily search error: %s", exc)
        return []


def _ddg_instant(query: str) -> list[dict]:
    """DuckDuckGo Instant Answer — no key, encyclopedic topics only."""
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                headers={"User-Agent": _USER_AGENT},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("DDG instant answer error: %s", exc)
        return []

    results: list[dict] = []
    abstract = data.get("AbstractText", "").strip()
    if len(abstract) > 50:
        url = data.get("AbstractURL", "") or "duckduckgo.com"
        results.append(_chunk(abstract, url, score=0.50))

    for topic in data.get("RelatedTopics", []):
        if len(results) >= _MAX_RESULTS:
            break
        if "Topics" in topic:
            for sub in topic["Topics"]:
                text = sub.get("Text", "").strip()
                url  = sub.get("FirstURL", "") or "duckduckgo.com"
                if len(text) > 40:
                    results.append(_chunk(text, url, score=0.35))
                    if len(results) >= _MAX_RESULTS:
                        break
        else:
            text = topic.get("Text", "").strip()
            url  = topic.get("FirstURL", "") or "duckduckgo.com"
            if len(text) > 40:
                results.append(_chunk(text, url, score=0.35))

    return results[:_MAX_RESULTS]


def _chunk(text: str, url: str, score: float) -> dict:
    return {"text": text, "source": f"web:{url}", "score": score, "display_score": score}


def web_search_fallback(query: str) -> list[dict]:
    """Return up to _MAX_RESULTS web chunks. Tavily first, DDG instant answer fallback."""
    try:
        results = _tavily_search(query)
        if not results:
            results = _ddg_instant(query)
        logger.info("CRAG web search: query=%r returned %d results", query, len(results))
        return results
    except Exception as exc:
        logger.warning("web_search_fallback unexpected error: %s", exc)
        return []
