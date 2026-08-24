"""Non-generator helpers for the RAG query endpoint: schema, key resolution,
type-boost detection, small-corpus tuning, answer-source/confidence scoring,
and small SSE/IP utilities."""
from __future__ import annotations

import json
import os
from typing import Any, Optional

from fastapi import Request
from pydantic import BaseModel

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


# Many phrasings ("what's this about", "what is he saying", "summarize",
# "did she say anything about X"...) have no single chunk that's
# semantically "the answer" — ordinary relevance-based rerank filtering
# rejects everything, including genuinely relevant content (observed live,
# twice: a real video transcript scored 0.007 for "what is the person
# talking about?", then got dropped again for "what is he saying?" because
# that phrasing wasn't on a keyword list). A keyword list for this is
# inherently a losing game — there's no bounded set of ways to ask a broad
# question. Instead: for a SMALL uploaded corpus, always send everything to
# the LLM regardless of query wording. There's no real cost (the pool is
# tiny) and it removes this whole class of bug rather than growing a list
# one missed phrasing at a time.
_SMALL_CORPUS_MAX_CANDIDATES = 15  # cap so this doesn't dump an unbounded
                                   # amount of context for a LARGER uploaded
                                   # corpus (multi-document Q&A)


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
    provider: str = "groq"
    model: str = "groq/compound"
    user_key: Optional[str] = None
    embedding_model: str = "minilm"  # "minilm" | "jina"
    session_id: str = ""
    force_web: bool = False
    restrict_to_uploads: bool = False  # answer ONLY from this session's uploads — no KB, no web
    answer_length: str = "normal"  # "concise" | "normal" | "detailed"
    chunk_type_filter: Optional[list[str]] = None  # e.g. ["table"] — restrict retrieval to these chunk_type(s)
    entity_type_filter: Optional[list[str]] = None  # e.g. ["money", "date"] — restrict to chunks containing these
    share_token: Optional[str] = None  # resolves to the owning session_id if valid, not revoked, not expired


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


# ── Endpoints ──────────────────────────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""
