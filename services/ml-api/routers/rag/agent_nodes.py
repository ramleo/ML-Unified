"""LangGraph node functions and meta-LLM helper for the agentic RAG loop.

Meta-calls (router, grader, rewriter) use the cheapest available model to
minimise token spend. Priority: server GEMINI_API_KEY → user key + cheap model.
"""
from __future__ import annotations

import json
import logging
import os

from routers.rag.query import _resolve_key

logger = logging.getLogger(__name__)

# ── Cheapest model per provider ────────────────────────────────────────────────

_CHEAP: dict[str, tuple[str, str | None]] = {
    "gemini":     ("gemini-3.6-flash",         None),
    "claude":     ("claude-haiku-4-5-20251001", None),
    "openai":     ("gpt-4o-mini",               None),
    "groq":       ("llama-3.1-8b-instant",      "https://api.groq.com/openai/v1"),
    "cohere":     ("command-a-03-2025",         None),
    "mistral":    ("mistral-small-latest",      "https://api.mistral.ai/v1"),
    "perplexity": ("sonar",                     "https://api.perplexity.ai"),
}


def _gemini_one_shot(api_key: str, model: str, prompt: str) -> str:
    import urllib.request as _ur
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 24, "temperature": 0},
    }).encode()
    req = _ur.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with _ur.urlopen(req, timeout=12) as r:
        data = json.loads(r.read())
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def _meta_call(prompt: str, user_key: str, provider: str,
               *, preserve_case: bool = False) -> str:
    """One-shot LLM call for routing/grading/rewriting. Raises on failure."""
    server_key = os.environ.get("GEMINI_API_KEY", "")
    if server_key:
        text = _gemini_one_shot(server_key, "gemini-3.6-flash", prompt)
        return text if preserve_case else text.lower()

    api_key = user_key or _resolve_key(provider, None)
    if not api_key:
        raise RuntimeError(f"No API key available for meta call (provider={provider})")

    model, base_url = _CHEAP.get(provider, ("gemini-3.6-flash", None))

    if provider == "gemini":
        text = _gemini_one_shot(api_key, model, prompt)
        return text if preserve_case else text.lower()

    if provider == "claude":
        import anthropic as _ant
        client = _ant.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model, max_tokens=24, temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        return text if preserve_case else text.lower()

    # openai-compatible (openai, groq, mistral, perplexity, cohere)
    import openai as _oai
    client = _oai.OpenAI(
        api_key=api_key,
        **({"base_url": base_url} if base_url else {}),
        timeout=12,
    )
    resp = client.chat.completions.create(
        model=model, max_tokens=24, temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content.strip()
    return text if preserve_case else text.lower()

# ── Node functions ─────────────────────────────────────────────────────────────

def node_router(state: dict) -> dict:
    """Classify query as 'simple' (direct) or 'complex' (needs grading loop)."""
    try:
        prompt = (
            "Classify this ML knowledge-base query.\n"
            "simple = single fact (e.g. 'what is XGBoost', 'what does SMOTE do')\n"
            "complex = comparison, multi-concept, dataset-specific, or open-ended\n"
            "Reply with ONLY one word: simple or complex\n"
            f"Query: {state['query']}"
        )
        result = _meta_call(prompt, state["user_key"], state["provider"])
        route = "complex" if "complex" in result else "simple"
    except Exception as exc:
        logger.warning("router node failed, defaulting to complex: %s", exc)
        route = "complex"
    logger.debug("router: %r → %s", state["query"][:50], route)
    return {"route": route}


def node_decompose(state: dict) -> dict:
    """Split a compound query (comparison / multi-part) into 2-3 standalone
    search queries. Simple single-fact queries pass through unchanged — this
    only runs on the 'complex' route, so the common case pays no extra cost.
    """
    query = state.get("final_query") or state["query"]
    try:
        prompt = (
            "If this query asks about multiple distinct things that need separate "
            "lookups (e.g. comparing two documents, or asking two unrelated questions "
            "in one sentence), split it into 2-3 standalone search queries, one per "
            "line, no numbering. If it's really just one question, reply with the "
            "query unchanged and nothing else.\n"
            f"Query: {query}"
        )
        result = _meta_call(prompt, state["user_key"], state["provider"], preserve_case=True)
        sub_queries = [s.strip("-•* ").strip() for s in result.splitlines() if s.strip()]
        sub_queries = sub_queries[:3] or [query]
    except Exception as exc:
        logger.warning("decompose node failed, using original query: %s", exc)
        sub_queries = [query]
    logger.debug("decompose: %r → %d sub-queries", query[:50], len(sub_queries))
    return {"sub_queries": sub_queries}


def node_retrieve(state: dict) -> dict:
    """Hybrid BM25 + dense retrieval, cross-encoder reranked to top-6.

    Runs one retrieval pass per sub-query (from node_decompose, if any) and
    RRF-merges them via multi_query_retrieve's existing multi-query support
    — no new retrieval logic needed for decomposition.
    """
    try:
        from routers.rag import get_rag_state
        from routers.rag.retrieve import multi_query_retrieve
        from routers.rag.rerank import rerank
        rs = get_rag_state()
        q = state.get("final_query") or state["query"]
        sub_queries = state.get("sub_queries") or [q]
        raw = multi_query_retrieve(sub_queries, rs, top_k=20, session_id=state.get("session_id", ""))
        chunks = rerank(q, raw, rs, top_k=5)
        logger.debug("retrieve: %r (%d sub-queries) → %d chunks", q[:50], len(sub_queries), len(chunks))
        return {"chunks": chunks}
    except Exception as exc:
        logger.error("retrieve node failed: %s", exc)
        return {"chunks": state.get("chunks", [])}


def node_grade(state: dict) -> dict:
    """Grade chunk relevance — good | rewrite | websearch."""
    chunks = state.get("chunks", [])
    if not chunks:
        return {"grade": "websearch"}
    try:
        # Truncate to 200 chars each — saves ~400 tokens vs full text
        excerpts = "\n".join(
            f"[{i+1}] {c.get('text','')[:200]}"
            for i, c in enumerate(chunks[:5])
        )
        prompt = (
            "Do the retrieved chunks help answer the query?\n"
            "Reply with ONLY one word: good | rewrite | websearch\n"
            "good = at least 1 chunk is clearly relevant\n"
            "rewrite = mostly off-topic, try rephrasing the query\n"
            "websearch = topic is outside this knowledge base\n"
            f"Query: {state.get('final_query') or state['query']}\n"
            f"Chunks:\n{excerpts}"
        )
        result = _meta_call(prompt, state["user_key"], state["provider"])
        grade = ("websearch" if "websearch" in result
                 else "rewrite" if "rewrite" in result
                 else "good")
    except Exception as exc:
        logger.warning("grader node failed, defaulting to good: %s", exc)
        grade = "good"
    logger.debug("grader: → %s (loop=%d)", grade, state.get("loop_count", 0))
    return {"grade": grade}


def node_rewrite(state: dict) -> dict:
    """Reformulate query to improve retrieval quality."""
    try:
        prompt = (
            "Rewrite this ML knowledge-base search query to be more specific and "
            "retrieval-friendly. Return ONLY the rewritten query, nothing else.\n"
            f"Original: {state['query']}"
        )
        rewritten = _meta_call(
            prompt, state["user_key"], state["provider"], preserve_case=True
        ).strip() or state["query"]
    except Exception as exc:
        logger.warning("rewriter node failed, using original: %s", exc)
        rewritten = state["query"]
    logger.debug("rewriter: %r → %r",
                 state["query"][:40], rewritten[:40])
    return {
        "final_query": rewritten,
        "loop_count":  state.get("loop_count", 0) + 1,
    }

# ── Conditional edges ──────────────────────────────────────────────────────────

def edge_after_router(state: dict) -> str:
    return "decompose" if state.get("route") == "complex" else "retrieve"


def edge_after_retrieve(state: dict) -> str:
    return "generate" if state.get("route") == "simple" else "grade"


def edge_after_grade(state: dict) -> str:
    grade = state.get("grade", "good")
    if grade == "rewrite" and state.get("loop_count", 0) < 2:
        return "rewrite"
    return "generate"
