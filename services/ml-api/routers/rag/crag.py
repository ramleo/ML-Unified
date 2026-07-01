"""CRAG (Corrective RAG) — DuckDuckGo web search fallback via httpx.

Triggered when reranker confidence is low (top score < 0.05 or no chunks).
Returns up to 3 web result chunks with source prefixed "web:".
No API key required — uses DDG Instant Answer JSON API with HTML fallback.
"""
from __future__ import annotations

import logging
import re

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 10
_MAX_RESULTS = 3
_DDG_INSTANT = "https://api.duckduckgo.com/"
_DDG_HTML = "https://html.duckduckgo.com/html/"
_USER_AGENT = "Mozilla/5.0 (compatible; RAGBot/1.0)"


def _instant_answer(query: str) -> list[dict]:
    """DuckDuckGo Instant Answer API — zero-key, works for encyclopedia topics."""
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(
                _DDG_INSTANT,
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
        # RelatedTopics can be nested {"Topics": [...]}
        if "Topics" in topic:
            for subtopic in topic["Topics"]:
                text = subtopic.get("Text", "").strip()
                url = subtopic.get("FirstURL", "") or "duckduckgo.com"
                if len(text) > 40:
                    results.append(_chunk(text, url, score=0.35))
                    if len(results) >= _MAX_RESULTS:
                        break
        else:
            text = topic.get("Text", "").strip()
            url = topic.get("FirstURL", "") or "duckduckgo.com"
            if len(text) > 40:
                results.append(_chunk(text, url, score=0.35))

    return results[:_MAX_RESULTS]


def _html_search(query: str) -> list[dict]:
    """DDG HTML search — scrapes result snippets as fallback."""
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(
                _DDG_HTML,
                params={"q": query},
                headers={"User-Agent": _USER_AGENT},
            )
            resp.raise_for_status()
            html = resp.text
    except Exception as exc:
        logger.warning("DDG HTML search error: %s", exc)
        return []

    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
    urls = re.findall(r'class="result__url"[^>]*>\s*(.*?)\s*</a>', html, re.DOTALL)

    results: list[dict] = []
    for i, raw in enumerate(snippets[:_MAX_RESULTS]):
        text = re.sub(r"<[^>]+>", "", raw).strip()
        url = re.sub(r"<[^>]+>", "", urls[i]).strip() if i < len(urls) else "duckduckgo.com"
        if len(text) > 30:
            results.append(_chunk(text, url, score=0.40))

    return results


def _chunk(text: str, url: str, score: float) -> dict:
    return {
        "text": text,
        "source": f"web:{url}",
        "score": score,
        "display_score": score,
    }


def web_search_fallback(query: str) -> list[dict]:
    """Return up to _MAX_RESULTS web chunks for a query.

    Tries DDG Instant Answer first; falls back to DDG HTML scrape if empty.
    Never raises — returns [] on any failure.
    """
    try:
        results = _instant_answer(query)
        if not results:
            results = _html_search(query)
        logger.info("CRAG web search: query=%r returned %d results", query, len(results))
        return results
    except Exception as exc:
        logger.warning("web_search_fallback unexpected error: %s", exc)
        return []
