"""POST /eda/suggest — LLM-powered feature engineering suggestions (SSE stream)."""
from __future__ import annotations

import json
import os
from typing import AsyncGenerator

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from security.budget import check_and_record_call
from security.rate_limit import LLM_LIMIT, limiter

router = APIRouter()

# Model names and order, matching routers/document/_llm.py and
# routers/rag/generation.py. Three things were wrong here while this module
# sat unmounted, and all three are the shapes that have cost this project
# real money or real silence:
#
#   * Cohere was pinned to command-r-plus-08-2024. The undated sibling of
#     that name is retired and 404s on v2/chat; command-a-03-2025 is what
#     every other Cohere call site here uses and what is verified on this
#     Space.
#   * The default was Mistral, which has no reserved free capacity and 429s
#     a large share of requests. A default that usually fails is not a
#     default.
#   * There was no cascade at all. One provider was tried, and if it failed
#     the user got an error — with a paid Gemini key sitting right there,
#     selectable, with no budget cap in front of it.
_PROVIDERS = {
    "cohere":  {"env": "COHERE_API_KEY",  "model": "command-a-03-2025"},
    "mistral": {"env": "MISTRAL_API_KEY", "model": "mistral-small-latest"},
    "gemini":  {"env": "GEMINI_API_KEY",  "model": "gemini-3.6-flash"},
    "groq":    {"env": "GROQ_API_KEY",    "model": "groq/compound"},
}

# Free and reliable, then free and best-effort, then the only paid key.
# Groq stays selectable by name but out of the automatic path — see the
# module history in routers/document/_llm.py.
_CASCADE_ORDER = ("cohere", "mistral", "gemini")

PAID_PROVIDERS = ("gemini",)


class SuggestRequest(BaseModel):
    overview:          dict
    columns:           list
    stats:             dict
    correlations:      dict | None = None
    insights:          list        = []
    readiness:         list        = []
    narrative:         str         = ""
    low_variance_cols: list        = []
    provider:          str         = "auto"


def _build_prompt(req: SuggestRequest) -> str:
    num_cols     = [c for c in req.columns if c["is_numeric"]]
    cat_cols     = [c for c in req.columns if not c["is_numeric"]]
    skewed       = [c["name"] for c in req.columns if c["is_numeric"]
                    and c["name"] in req.stats and abs(req.stats[c["name"]]["skew"]) > 1.5]
    outlier_cols = [col for col, s in req.stats.items()
                    if req.overview["rows"] > 0 and s["outliers"] / req.overview["rows"] > 0.05]
    high_card    = [c["name"] for c in req.columns if not c["is_numeric"] and c["nunique"] > 20]
    corr_pairs   = []
    if req.correlations:
        lbls, mat = req.correlations["labels"], req.correlations["matrix"]
        for i in range(len(lbls)):
            for j in range(i + 1, len(lbls)):
                v = mat[i][j]
                if v is not None and abs(v) >= 0.7:
                    corr_pairs.append(f"{lbls[i]} × {lbls[j]} ({v:.2f})")
    readiness_warns = [r["name"] + ": " + r["reason"] for r in req.readiness if r["verdict"] != "pass"]

    lines = [
        "You are an expert ML feature engineer. Analyze this dataset and suggest specific, actionable feature engineering steps.",
        "",
        f"Dataset: {req.overview['rows']:,} rows × {req.overview['cols']} columns",
        f"Numeric columns ({len(num_cols)}): {', '.join(c['name'] for c in num_cols) or 'none'}",
        f"Categorical columns ({len(cat_cols)}): {', '.join(c['name'] for c in cat_cols) or 'none'}",
        f"Missing values: {req.overview.get('missing_pct', 0):.1f}% overall",
    ]
    if skewed:
        lines.append(f"Highly skewed columns (|skew| > 1.5): {', '.join(skewed)}")
    if outlier_cols:
        lines.append(f"Columns with >5% outliers: {', '.join(outlier_cols)}")
    if high_card:
        lines.append(f"High-cardinality categoricals (>20 unique): {', '.join(high_card)}")
    if corr_pairs:
        lines.append(f"Strongly correlated pairs (|r| ≥ 0.7): {'; '.join(corr_pairs)}")
    if req.low_variance_cols:
        lines.append(f"Low-variance columns: {', '.join(req.low_variance_cols)}")
    if readiness_warns:
        lines.append(f"ML readiness issues: {'; '.join(readiness_warns[:6])}")
    if req.narrative:
        lines.append(f"\nAuto-narrative: {req.narrative}")
    lines += [
        "",
        "Suggest 6–8 specific feature engineering steps. For each:",
        "- Name the transformation and which column(s) it applies to",
        "- Explain WHY it would improve model performance",
        "- Note any risk or caveat",
        "",
        "Format each suggestion as a numbered item with a bold title. Be concrete and dataset-specific.",
    ]
    return "\n".join(lines)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def _stream_groq(prompt: str, model: str, key: str) -> AsyncGenerator[str, None]:
    payload = {
        "model": model, "stream": True,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024, "temperature": 0.4,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", "https://api.groq.com/openai/v1/chat/completions",
                                 json=payload, headers=headers) as resp:
            if resp.status_code != 200:
                yield ({"type": "error", "text": (await resp.aread()).decode()})
                return
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    delta = json.loads(chunk)["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield ({"type": "token", "text": delta})
                except Exception:
                    continue
    yield ({"type": "done"})


async def _stream_mistral(prompt: str, model: str, key: str) -> AsyncGenerator[str, None]:
    payload = {
        "model": model, "stream": True,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024, "temperature": 0.4,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", "https://api.mistral.ai/v1/chat/completions",
                                 json=payload, headers=headers) as resp:
            if resp.status_code != 200:
                yield ({"type": "error", "text": (await resp.aread()).decode()})
                return
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    delta = json.loads(chunk)["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield ({"type": "token", "text": delta})
                except Exception:
                    continue
    yield ({"type": "done"})


async def _stream_gemini(prompt: str, model: str, key: str) -> AsyncGenerator[str, None]:
    url      = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:streamGenerateContent?key={key}&alt=sse")
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", url, json={"contents": contents}) as resp:
            if resp.status_code != 200:
                yield ({"type": "error", "text": (await resp.aread()).decode()})
                return
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload in ("", "[DONE]"):
                    continue
                try:
                    obj = json.loads(payload)
                    for cand in obj.get("candidates", []):
                        for part in cand.get("content", {}).get("parts", []):
                            if "text" in part:
                                yield ({"type": "token", "text": part["text"]})
                except Exception:
                    continue
    yield ({"type": "done"})


async def _stream_cohere(prompt: str, model: str, key: str) -> AsyncGenerator[str, None]:
    messages = [{"role": "user", "content": prompt}]
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST", "https://api.cohere.ai/v2/chat",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "stream": True},
        ) as resp:
            if resp.status_code != 200:
                yield ({"type": "error", "text": (await resp.aread()).decode()})
                return
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload in ("", "[DONE]"):
                    continue
                try:
                    obj = json.loads(payload)
                    if obj.get("type") == "content-delta":
                        text = (obj.get("delta", {}).get("message", {})
                                .get("content", {}).get("text", ""))
                        if text:
                            yield ({"type": "token", "text": text})
                except Exception:
                    continue
    yield ({"type": "done"})


_STREAMERS = {
    "cohere":  _stream_cohere,
    "mistral": _stream_mistral,
    "gemini":  _stream_gemini,
    "groq":    _stream_groq,
}


def _short_reason(text: str) -> str:
    """A user-facing reason for a provider failure. The raw body carries
    status codes and full URLs and is not fit to show."""
    low = text.lower()
    if "429" in low or "rate limit" in low or "capacity" in low:
        return "rate limited"
    if "401" in low or "403" in low or "unauthorized" in low or "invalid api key" in low:
        return "invalid or unauthorized key"
    if "404" in low or "not_found" in low or "model_not_found" in low:
        return "model not found"
    if "timeout" in low or "timed out" in low:
        return "timed out"
    return "unavailable"


def _candidates(asked: str) -> list[str]:
    """The caller's pick first if it is a real provider, then the cascade,
    never repeating one. A typo falls through to the cascade rather than
    becoming an error, and the paid key stays last either way."""
    asked = (asked or "").lower()
    first = [asked] if asked in _PROVIDERS and asked != "auto" else []
    return first + [p for p in _CASCADE_ORDER if p != asked]


async def _stream(req: SuggestRequest) -> AsyncGenerator[str, None]:
    prompt = _build_prompt(req)
    tried: list[str] = []

    for name in _candidates(req.provider):
        cfg = _PROVIDERS[name]
        key = os.environ.get(cfg["env"], "")
        if not key:
            tried.append(f"{name} (no key configured)")
            continue

        started = False
        failure = ""
        try:
            async for event in _STREAMERS[name](prompt, cfg["model"], key):
                if event["type"] == "error" and not started:
                    failure = event.get("text", "")
                    break
                if event["type"] == "token" and not started:
                    started = True
                    # Name the provider that actually answered, not the one
                    # that was asked for. Reporting the request instead of
                    # the result is how a silent fallback stays silent.
                    yield _sse({"type": "provider", "name": name, "model": cfg["model"]})
                yield _sse(event)
        except Exception as exc:  # noqa: BLE001
            if started:
                # Switching provider mid-answer would garble the text, so
                # say what happened and stop rather than restarting.
                yield _sse({"type": "error", "text": f"{name} stopped mid-answer."})
                yield _sse({"type": "done"})
                return
            failure = str(exc)

        if started:
            return
        tried.append(f"{name} ({_short_reason(failure)})")

    yield _sse({"type": "error",
                "text": "No provider could answer. Tried " + ", ".join(tried) + "."})
    yield _sse({"type": "done"})


@router.post("/eda/suggest")
@limiter.limit(LLM_LIMIT)
async def suggest_features(request: Request, req: SuggestRequest):
    # Before the request is opened, not after: a rejected call costs nothing,
    # unlike one that reaches a provider. This route had no cap at all while
    # offering a paid key to any anonymous visitor.
    check_and_record_call("eda-suggest", pool="eda_suggest",
                          daily_cap_env="EDA_SUGGEST_DAILY_CAP")
    return StreamingResponse(
        _stream(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
