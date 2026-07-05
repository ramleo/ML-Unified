"""POST /eda/suggest — LLM-powered feature engineering suggestions (SSE stream)."""
from __future__ import annotations

import json
import os
from typing import AsyncGenerator

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()

_GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = "llama-3.3-70b-versatile"


class SuggestRequest(BaseModel):
    overview:      dict
    columns:       list
    stats:         dict
    correlations:  dict | None = None
    insights:      list        = []
    readiness:     list        = []
    narrative:     str         = ""
    low_variance_cols: list    = []


def _build_prompt(req: SuggestRequest) -> str:
    num_cols = [c for c in req.columns if c["is_numeric"]]
    cat_cols = [c for c in req.columns if not c["is_numeric"]]

    skewed   = [c["name"] for c in req.columns if c["is_numeric"]
                and c["name"] in req.stats and abs(req.stats[c["name"]]["skew"]) > 1.5]
    outlier_cols = [col for col, s in req.stats.items()
                    if req.overview["rows"] > 0 and s["outliers"] / req.overview["rows"] > 0.05]
    high_card = [c["name"] for c in req.columns if not c["is_numeric"] and c["nunique"] > 20]
    corr_pairs = []
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
        f"Data quality score: {req.overview.get('missing_pct', 0):.1f}% missing overall",
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
        "Format each suggestion as a numbered item. Be concrete and dataset-specific — no generic advice.",
    ]
    return "\n".join(lines)


async def _stream_groq(prompt: str) -> AsyncGenerator[str, None]:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        yield f"data: {json.dumps({'type': 'error', 'text': 'GROQ_API_KEY not configured on server.'})}\n\n"
        return

    payload = {
        "model":  _GROQ_MODEL,
        "stream": True,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
        "temperature": 0.4,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", _GROQ_URL, json=payload, headers=headers) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                yield f"data: {json.dumps({'type': 'error', 'text': body.decode()})}\n\n"
                return
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return
                try:
                    delta = json.loads(chunk)["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield f"data: {json.dumps({'type': 'token', 'text': delta})}\n\n"
                except Exception:
                    continue


@router.post("/eda/suggest")
async def suggest_features(req: SuggestRequest):
    prompt = _build_prompt(req)
    return StreamingResponse(
        _stream_groq(prompt),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
