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


_ID_COL_RE = re.compile(
    r"(^id$|_id$|Id$|^id_|_key$|Key$|_no$|No$|_code$|Code$|_num$|Num$)",
    re.IGNORECASE,
)


def _is_id_col(col: str) -> bool:
    """True for columns that are IDs/keys — numeric but not meaningful metrics."""
    return bool(_ID_COL_RE.search(col))


def detect_visualization(columns: list[str], rows: list[list]) -> dict | None:
    """Return chart spec dict or None if no suitable chart detected.

    Chart type priority:
      stat      — single aggregate row (1 numeric value)
      donut     — 1 text + 1 numeric, ≤ 7 rows
      bar_h     — 1 text + 1 numeric, avg label length > 12
      area      — 2 cols, time pattern + numeric
      scatter   — 2 numeric cols
      multibar  — 1 text + 2-4 numeric cols
      bar       — 1 text + 1 numeric (default)
    """
    if not rows or not columns:
        return None

    col_vals = {col: [row[i] for row in rows] for i, col in enumerate(columns)}
    # Exclude ID/key columns from metric detection — they're numeric but not chart-worthy
    numeric_cols = [c for c in columns if _is_numeric(col_vals[c]) and not _is_id_col(c)]
    text_cols    = [c for c in columns if c not in numeric_cols]

    def sf(v):
        try:
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    # 1. Single aggregate row → stat card
    if len(rows) == 1 and numeric_cols:
        return {
            "chart_type": "stat",
            "value": str(col_vals[numeric_cols[0]][0]),
            "label": numeric_cols[0],
            "x_label": numeric_cols[0], "y_label": "",
        }

    if len(rows) < 2:
        return None

    if len(columns) == 2:
        if text_cols and numeric_cols:
            labels = [str(v) for v in col_vals[text_cols[0]][:50]]
            values = [sf(v) for v in col_vals[numeric_cols[0]][:50]]
            avg_len = sum(len(l) for l in labels) / max(len(labels), 1)

            if len(rows) <= 7:
                return {"chart_type": "donut", "labels": labels, "values": values,
                        "x_label": numeric_cols[0], "y_label": text_cols[0]}
            if len(rows) > 12:
                return {"chart_type": "treemap", "labels": labels, "values": values,
                        "x_label": text_cols[0], "y_label": numeric_cols[0]}
            if avg_len > 12:
                return {"chart_type": "bar_h", "labels": labels[:20], "values": values[:20],
                        "x_label": numeric_cols[0], "y_label": text_cols[0]}
            return {"chart_type": "bar", "labels": labels[:20], "values": values[:20],
                    "x_label": text_cols[0], "y_label": numeric_cols[0]}

        if len(numeric_cols) == 2:
            sample = [str(v) for v in col_vals[columns[0]][:5]]
            # Match YYYY-MM, YYYY/MM, or plain YYYY (years 1900-2099)
            if any(re.search(r"\b(19|20)\d{2}([-/]\d{1,2})?\b", v) for v in sample):
                return {"chart_type": "area",
                        "labels": [str(v) for v in col_vals[columns[0]][:50]],
                        "values": [sf(v) for v in col_vals[columns[1]][:50]],
                        "x_label": columns[0], "y_label": columns[1]}
            return {"chart_type": "scatter",
                    "x": [sf(v) for v in col_vals[columns[0]][:100]],
                    "y": [sf(v) for v in col_vals[columns[1]][:100]],
                    "x_label": columns[0], "y_label": columns[1]}

    # 3-col time series: year + month + value → area with combined "YYYY-MM" labels
    if len(columns) == 3 and not text_cols:
        year_sample  = [str(v) for v in col_vals[columns[0]][:5] if v is not None]
        month_sample = [str(v) for v in col_vals[columns[1]][:5] if v is not None]
        try:
            year_ok  = all(re.match(r"^(19|20)\d{2}$", y) for y in year_sample)
            month_ok = all(re.match(r"^\d{1,2}$", m) and 1 <= int(m) <= 12
                           for m in month_sample)
        except (ValueError, TypeError):
            year_ok = month_ok = False
        if year_ok and month_ok:
            combined = [f"{y}-{str(m).zfill(2)}"
                        for y, m in zip(col_vals[columns[0]][:50], col_vals[columns[1]][:50])]
            return {"chart_type": "area", "labels": combined,
                    "values": [sf(v) for v in col_vals[columns[2]][:50]],
                    "x_label": f"{columns[0]}-{columns[1]}", "y_label": columns[2]}

    # Multi-column
    if text_cols and numeric_cols:
        labels = [str(v) for v in col_vals[text_cols[0]][:50]]

        # 2 text + 1 numeric → heatmap grid (e.g. Genre × Country → Sales)
        if len(text_cols) == 2 and len(numeric_cols) == 1:
            row_vals = [str(v) for v in col_vals[text_cols[0]]]
            col_vals2 = [str(v) for v in col_vals[text_cols[1]]]
            unique_rows = list(dict.fromkeys(row_vals))[:20]
            unique_cols = list(dict.fromkeys(col_vals2))[:15]
            # Skip heatmap when every (row, col) pair is unique — 1:1 mapping
            # (e.g. FirstName × LastName per customer), not a real cross-tab.
            # Use set of pairs (not capped unique_rows/cols) to avoid false negatives
            # when len(rows) > 20 (the cap on unique_rows/unique_cols).
            pairs = set(zip(row_vals, col_vals2))
            is_one_to_one = len(pairs) == len(rows)
            if len(unique_rows) >= 2 and len(unique_cols) >= 2 and not is_one_to_one:
                data = [
                    {"row": row_vals[i], "col": col_vals2[i],
                     "value": sf(col_vals[numeric_cols[0]][i])}
                    for i in range(len(rows))
                ]
                return {"chart_type": "heatmap",
                        "rows": unique_rows, "cols": unique_cols, "data": data,
                        "x_label": text_cols[1], "y_label": text_cols[0],
                        "v_label": numeric_cols[0]}
            # Fallback: concatenate the two text cols as one label → bar_h
            labels = [f"{r} {c}" for r, c in zip(row_vals, col_vals2)]

        if len(numeric_cols) == 2:
            # If the two numeric columns have wildly different scales (e.g. milliseconds
            # vs unit price), a scatter plot is more honest than a grouped bar chart.
            vals0 = [sf(v) for v in col_vals[numeric_cols[0]][:20]]
            vals1 = [sf(v) for v in col_vals[numeric_cols[1]][:20]]
            m0, m1 = max(vals0, default=1), max(vals1, default=1)
            scale_ratio = max(m0, m1) / max(min(m0, m1), 1e-6)
            if scale_ratio > 10:
                return {"chart_type": "scatter",
                        "x": vals0, "y": vals1, "labels": labels,
                        "x_label": numeric_cols[0], "y_label": numeric_cols[1]}
            return {"chart_type": "multibar", "labels": labels,
                    "series": [{"name": nc, "values": [sf(v) for v in col_vals[nc][:20]]}
                                for nc in numeric_cols[:4]],
                    "x_label": text_cols[0], "y_label": ""}
        if len(numeric_cols) > 2:
            return {"chart_type": "multibar", "labels": labels,
                    "series": [{"name": nc, "values": [sf(v) for v in col_vals[nc][:20]]}
                                for nc in numeric_cols[:4]],
                    "x_label": text_cols[0], "y_label": ""}
        values = [sf(v) for v in col_vals[numeric_cols[0]][:50]]
        # Treemap for large label sets (crowded bar chart becomes unreadable)
        if len(rows) > 12:
            return {"chart_type": "treemap", "labels": labels, "values": values,
                    "x_label": text_cols[0], "y_label": numeric_cols[0]}
        avg_len = sum(len(l) for l in labels) / max(len(labels), 1)
        if avg_len > 12:
            return {"chart_type": "bar_h", "labels": labels[:20], "values": values[:20],
                    "x_label": numeric_cols[0], "y_label": text_cols[0]}
        return {"chart_type": "bar", "labels": labels[:20], "values": values[:20],
                "x_label": text_cols[0], "y_label": numeric_cols[0]}

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