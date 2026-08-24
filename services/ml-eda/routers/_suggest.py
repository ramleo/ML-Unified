"""POST /eda/suggest — LLM-powered feature engineering suggestions (SSE stream)."""
from __future__ import annotations

import json
import os
from typing import AsyncGenerator

import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()

# Groq dropped as the default (2026-08-24) — llama-3.3-70b-versatile was
# already dead (404 model_not_found in production, see ML-Unified's
# EDGECASES.md EC-008 for the full history) and no free replacement that
# actually worked reliably was found. Mistral is the default instead; groq
# still selectable explicitly (BYOK-style), using groq/compound — its own
# story is mixed (connects but has hit real rate-limit/payload errors under
# this app's typical request sizes), so don't assume it's reliable either.
_PROVIDERS = {
    "mistral": {"env": "MISTRAL_API_KEY", "model": "mistral-small-latest"},
    "groq":    {"env": "GROQ_API_KEY",    "model": "groq/compound"},
    "gemini":  {"env": "GEMINI_API_KEY",  "model": "gemini-3.6-flash"},
    "cohere":  {"env": "COHERE_API_KEY",  "model": "command-r-plus-08-2024"},
}


class SuggestRequest(BaseModel):
    overview:          dict
    columns:           list
    stats:             dict
    correlations:      dict | None = None
    insights:          list        = []
    readiness:         list        = []
    narrative:         str         = ""
    low_variance_cols: list        = []
    provider:          str         = "mistral"


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
                yield _sse({"type": "error", "text": (await resp.aread()).decode()})
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
                        yield _sse({"type": "token", "text": delta})
                except Exception:
                    continue
    yield _sse({"type": "done"})


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
                yield _sse({"type": "error", "text": (await resp.aread()).decode()})
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
                        yield _sse({"type": "token", "text": delta})
                except Exception:
                    continue
    yield _sse({"type": "done"})


async def _stream_gemini(prompt: str, model: str, key: str) -> AsyncGenerator[str, None]:
    url      = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:streamGenerateContent?key={key}&alt=sse")
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", url, json={"contents": contents}) as resp:
            if resp.status_code != 200:
                yield _sse({"type": "error", "text": (await resp.aread()).decode()})
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
                                yield _sse({"type": "token", "text": part["text"]})
                except Exception:
                    continue
    yield _sse({"type": "done"})


async def _stream_cohere(prompt: str, model: str, key: str) -> AsyncGenerator[str, None]:
    messages = [{"role": "user", "content": prompt}]
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST", "https://api.cohere.ai/v2/chat",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "stream": True},
        ) as resp:
            if resp.status_code != 200:
                yield _sse({"type": "error", "text": (await resp.aread()).decode()})
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
                            yield _sse({"type": "token", "text": text})
                except Exception:
                    continue
    yield _sse({"type": "done"})


async def _stream(req: SuggestRequest) -> AsyncGenerator[str, None]:
    provider = req.provider if req.provider in _PROVIDERS else "mistral"
    cfg      = _PROVIDERS[provider]
    key      = os.environ.get(cfg["env"], "")
    if not key:
        yield _sse({"type": "error", "text": f"{cfg['env']} not configured on server."})
        return
    prompt = _build_prompt(req)
    if provider == "mistral":
        async for chunk in _stream_mistral(prompt, cfg["model"], key):
            yield chunk
    elif provider == "groq":
        async for chunk in _stream_groq(prompt, cfg["model"], key):
            yield chunk
    elif provider == "gemini":
        async for chunk in _stream_gemini(prompt, cfg["model"], key):
            yield chunk
    elif provider == "cohere":
        async for chunk in _stream_cohere(prompt, cfg["model"], key):
            yield chunk


@router.post("/eda/suggest")
async def suggest_features(req: SuggestRequest):
    return StreamingResponse(
        _stream(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
