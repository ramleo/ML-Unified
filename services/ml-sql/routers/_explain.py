"""Result explanation (SSE streaming) and auto-visualization detection."""
from __future__ import annotations

import json
import re
from typing import AsyncGenerator

import httpx

from ._generate import _PROVIDERS, get_provider_cfg


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# ── Visualization detection ───────────────────────────────────────────────────

def _is_numeric(vals: list) -> bool:
    try:
        for v in vals:
            if v is not None:
                float(v)
        return True
    except (TypeError, ValueError):
        return False


def detect_visualization(columns: list[str], rows: list[list]) -> dict | None:
    """Return chart spec dict or None if no suitable chart detected."""
    if len(rows) < 2 or len(columns) < 2:
        return None

    col_vals = {col: [row[i] for row in rows] for i, col in enumerate(columns)}
    numeric_cols = [c for c in columns if _is_numeric(col_vals[c])]
    text_cols    = [c for c in columns if c not in numeric_cols]

    def safe_float(v):
        try:
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    if len(columns) == 2:
        if len(text_cols) == 1 and len(numeric_cols) == 1:
            labels = [str(v) for v in col_vals[text_cols[0]][:20]]
            values = [safe_float(v) for v in col_vals[numeric_cols[0]][:20]]
            return {
                "chart_type": "bar",
                "x_label": text_cols[0], "y_label": numeric_cols[0],
                "labels": labels, "values": values,
            }

        if len(numeric_cols) == 2:
            first_vals = [str(v) for v in col_vals[columns[0]][:5]]
            is_time = any(re.search(r"\d{4}[-/]\d{2}", v) for v in first_vals)
            if is_time:
                labels = [str(v) for v in col_vals[columns[0]][:30]]
                values = [safe_float(v) for v in col_vals[columns[1]][:30]]
                return {
                    "chart_type": "line",
                    "x_label": columns[0], "y_label": columns[1],
                    "labels": labels, "values": values,
                }
            x_vals = [safe_float(v) for v in col_vals[columns[0]][:100]]
            y_vals = [safe_float(v) for v in col_vals[columns[1]][:100]]
            return {
                "chart_type": "scatter",
                "x_label": columns[0], "y_label": columns[1],
                "x": x_vals, "y": y_vals,
            }

    if text_cols and numeric_cols:
        labels = [str(v) for v in col_vals[text_cols[0]][:20]]
        values = [safe_float(v) for v in col_vals[numeric_cols[0]][:20]]
        return {
            "chart_type": "bar",
            "x_label": text_cols[0], "y_label": numeric_cols[0],
            "labels": labels, "values": values,
        }

    return None


# ── Explanation prompt ────────────────────────────────────────────────────────

def _safe_cell(value: object) -> str:
    """Truncate and flatten a cell value so it cannot carry multi-line injection."""
    s = str(value) if value is not None else "null"
    # Collapse newlines / control chars, cap at 80 chars
    s = re.sub(r"[\r\n\t]+", " ", s)
    return s[:80]


def build_explain_prompt(
    question: str, sql: str, columns: list[str], rows_preview: list[list]
) -> str:
    # Sanitize each cell — prevents prompt injection via malicious DB values
    rows_text = "\n".join(
        str({col: _safe_cell(val) for col, val in zip(columns, row)})
        for row in rows_preview[:10]
    )
    return (
        f"Question asked: {question}\n\n"
        f"SQL executed:\n{sql}\n\n"
        f"Result ({len(rows_preview)} rows shown, columns: {', '.join(columns)}):\n"
        f"{rows_text}\n\n"
        "In 2-3 sentences explain what the results show in plain English. "
        "Mention specific numbers or names from the data. Do not repeat the SQL."
    )


# ── Streaming providers ───────────────────────────────────────────────────────

async def _stream_groq(prompt: str, model: str, key: str) -> AsyncGenerator[str, None]:
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST", "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "stream": True,
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 256, "temperature": 0.5},
        ) as resp:
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
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:streamGenerateContent?key={key}&alt=sse")
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", url,
                                 json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                                       "generationConfig": {"maxOutputTokens": 256}}) as resp:
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
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST", "https://api.cohere.ai/v2/chat",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "stream": True,
                  "messages": [{"role": "user", "content": prompt}]},
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


async def stream_explanation(
    prompt: str, provider: str, key: str
) -> AsyncGenerator[str, None]:
    cfg = get_provider_cfg(provider)
    model = cfg["model"]
    if provider == "gemini":
        async for chunk in _stream_gemini(prompt, model, key):
            yield chunk
    elif provider == "cohere":
        async for chunk in _stream_cohere(prompt, model, key):
            yield chunk
    else:
        async for chunk in _stream_groq(prompt, model, key):
            yield chunk