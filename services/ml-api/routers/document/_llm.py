"""LLM provider cascade for document field extraction.
Zero imports from other ml-api routers — self-contained for microservice extraction.
Cascade order: Groq (llama-3.3-70b) → Gemini 2.0 Flash → Cohere command-r-plus
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

logger = logging.getLogger(__name__)


# ── Provider implementations ──────────────────────────────────────────────────

def _groq(messages: list[dict], system: str) -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return ""
    try:
        import openai
        full = ([{"role": "system", "content": system}] if system else []) + messages
        client = openai.OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=full, max_tokens=4096,
            response_format={"type": "json_object"}, temperature=0,
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        logger.error("Groq failed: %s", exc)
        return ""


def _gemini_text(messages: list[dict], system: str) -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return ""
    try:
        import httpx
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user",
             "parts": [{"text": m["content"]}]}
            for m in messages
        ]
        body: dict = {
            "contents": contents,
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}
        url = ("https://generativelanguage.googleapis.com/v1beta/models"
               "/gemini-2.0-flash:generateContent")
        with httpx.Client(timeout=60) as client:
            r = client.post(url, params={"key": key}, json=body)
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:
        logger.error("Gemini text failed: %s", exc)
        return ""


def _cohere(messages: list[dict], system: str) -> str:
    key = os.environ.get("COHERE_API_KEY", "")
    if not key:
        return ""
    try:
        import httpx
        fmt = ([{"role": "system", "content": system}] if system else [])
        for m in messages:
            role = "assistant" if m["role"] == "assistant" else "user"
            fmt.append({"role": role, "content": m.get("content", "")})
        with httpx.Client(timeout=60) as client:
            r = client.post(
                "https://api.cohere.ai/v2/chat",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": "command-r-plus", "messages": fmt, "temperature": 0,
                      "response_format": {"type": "json_object"}},
            )
            r.raise_for_status()
            return r.json()["message"]["content"][0]["text"]
    except Exception as exc:
        logger.error("Cohere failed: %s", exc)
        return ""


def _cascade(messages: list[dict], system: str) -> str:
    for fn in (_groq, _gemini_text, _cohere):
        result = fn(messages, system)
        if result.strip():
            return result
    return ""


def _parse_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if m:
        text = m.group(1).strip()
    start, end = text.find("{"), text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return {}


# ── Public API ────────────────────────────────────────────────────────────────

def _keyword_classify(text: str, known_types: list[str]) -> tuple[str, float]:
    """Keyword-based fallback when all LLM providers fail."""
    t = text.lower()
    patterns: dict[str, list[str]] = {
        "resume":         ["resume", "curriculum vitae", " cv ", "work experience", "linkedin", "github", "employment history", "soft skills", "career"],
        "invoice":        ["invoice", "bill to", "amount due", "payment terms", "subtotal", "line items"],
        "receipt":        ["receipt", "thank you for your purchase", "cashier", "store #"],
        "contract":       ["agreement", "contract", "clause", "whereas", "hereinafter", "party"],
        "medical_report": ["patient", "diagnosis", "physician", "lab result", "clinical", "specimen"],
        "bank_statement": ["account statement", "opening balance", "closing balance", "transaction history"],
        "id_card":        ["date of birth", "nationality", "id number", "expiry date", "issued by"],
        "purchase_order": ["purchase order", "ship to", "delivery date", "po number", "supplier"],
    }
    scores = {dt: sum(1 for kw in patterns.get(dt, []) if kw in t) for dt in known_types}
    best = max(scores, key=scores.get)
    return (best, 0.55) if scores[best] > 0 else (known_types[0], 0.3)


def classify_document(text_sample: str, known_types: list[str]) -> tuple[str, float]:
    """Classify doc type from a text sample. Returns (doc_type, confidence 0–1)."""
    types_str = ", ".join(f'"{t}"' for t in known_types)
    system = "You are a document classification expert. Respond only with valid JSON."
    prompt = (
        f"Classify this document. Respond with JSON only: "
        f'{{\"doc_type\": <one of {types_str}>, \"confidence\": <0.0-1.0>}}\n\n'
        f"Document excerpt:\n{text_sample[:600]}"
    )
    raw = _cascade([{"role": "user", "content": prompt}], system)
    data = _parse_json(raw)
    doc_type = data.get("doc_type", "")
    confidence = float(data.get("confidence", 0.7))
    if not doc_type or doc_type not in known_types:
        doc_type, confidence = _keyword_classify(text_sample, known_types)
    return doc_type, max(0.0, min(1.0, confidence))


def extract_fields_from_text(text: str, doc_type: str, schema_fields: list[dict],
                             provider: str = "auto") -> list[dict]:
    """Extract fields from document text using the LLM cascade (or a forced provider)."""
    field_names = [f["name"] for f in schema_fields]
    field_meta = {f["name"]: f for f in schema_fields}
    system = "You are a document data extraction expert. Respond only with valid JSON."
    prompt = (
        f'Extract data from this {doc_type} document. Return JSON:\n'
        f'{{"fields": [{{"name": "<snake_case_name>", "label": "<Human Readable Label>", "value": "<value or null>", "confidence": <0.0-1.0>}}]}}\n\n'
        f'First extract these predefined fields (use null if not found): {json.dumps(field_names)}\n\n'
        f'Then append ANY additional sections, headers, or structured data you find in the document '
        f'that are not in the predefined list — use the section heading as the label and a snake_case version as the name. '
        f'Do not skip any section that has meaningful content.\n\n'
        f"Document text:\n{text[:14000]}"
    )
    _provider_map = {"groq": _groq, "gemini": _gemini_text, "cohere": _cohere}
    fn = _provider_map.get(provider)
    raw = fn([{"role": "user", "content": prompt}], system) if fn else _cascade(
        [{"role": "user", "content": prompt}], system
    )
    data = _parse_json(raw)
    return _normalize_fields(data.get("fields", []), field_meta)


def _visual_prompt(already: str, missing: str) -> str:
    return (
        "This is a rendered page from a PDF document. "
        f"Fields ALREADY extracted from text (skip these): {already}. "
        f"PRIORITY: find these MISSING fields which may be in visual/image format: {missing}. "
        "Also extract any other visual section not in the already-extracted list. "
        "Pay special attention to: career timelines (bars/charts showing job history), "
        "soft skills (pie charts, icons, ratings), work experience tables, certifications. "
        "For career timelines: list each role with company, title, and dates. "
        'Return JSON only: {"fields": [{"name": "<snake_case>", "label": "<Section Name>", '
        '"value": "<full content as a string>", "confidence": <0.0-1.0>}]}. '
        "If a visual section has content, include it — never return empty value for a section you can see."
    )


def _groq_vision_page(b64: str, prompt: str) -> list[dict]:
    """Extract fields from one page image using Groq vision (llama-3.2-11b-vision)."""
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return []
    try:
        import httpx
        messages = [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": prompt},
        ]}]
        with httpx.Client(timeout=60) as client:
            r = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": "llama-3.2-11b-vision-preview", "messages": messages,
                      "max_tokens": 2000},
            )
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"]
            return _normalize_fields(_parse_json(raw).get("fields", []), {})
    except Exception as exc:
        logger.warning("Groq vision page failed: %s", exc)
        return []


def _gemini_vision_page(b64: str, prompt: str) -> list[dict]:
    """Extract fields from one page image using Gemini Vision (fallback)."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return []
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    parts = [
        {"inline_data": {"mime_type": "image/png", "data": b64}},
        {"text": prompt},
    ]
    try:
        import httpx
        with httpx.Client(timeout=90) as client:
            for attempt in range(2):
                r = client.post(url, params={"key": key},
                                json={"contents": [{"role": "user", "parts": parts}]})
                if r.status_code == 429:
                    time.sleep(5 * (attempt + 1))
                    continue
                r.raise_for_status()
                raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                return _normalize_fields(_parse_json(raw).get("fields", []), {})
    except Exception as exc:
        logger.warning("Gemini vision page failed: %s", exc)
    return []


def extract_visual_sections(page_images: list[str], existing_names: set[str], missing_names: set[str] | None = None) -> list[dict]:
    """Extract visual content using Groq Vision (primary) → Gemini Vision (fallback)."""
    if not page_images:
        return []
    already = json.dumps(sorted(existing_names))
    missing = json.dumps(sorted(missing_names or []))
    prompt = _visual_prompt(already, missing)
    all_fields: list[dict] = []
    seen: set[str] = set()
    for b64 in page_images[:4]:
        fields = _groq_vision_page(b64, prompt) or _gemini_vision_page(b64, prompt)
        for f in fields:
            if f["name"] not in seen:
                seen.add(f["name"])
                all_fields.append(f)
        time.sleep(1)
    return all_fields


def extract_fields_from_image(image_b64: str, doc_type: str, schema_fields: list[dict]) -> list[dict]:
    """Extract fields from a scanned/image document using Gemini Vision."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        logger.warning("No GEMINI_API_KEY — cannot process scanned document")
        return []

    field_names = [f["name"] for f in schema_fields]
    field_meta = {f["name"]: f for f in schema_fields}

    user_parts: list[dict] = [
        {"inline_data": {"mime_type": "image/png", "data": image_b64}},
        {"text": (
            f'Extract data from this {doc_type} document image.\n'
            f'Return JSON: {{"fields": [{{"name": "<snake_case_name>", "label": "<Human Readable Label>", '
            f'"value": "<value or null>", "confidence": <0.0-1.0>, '
            f'"bbox": [left, top, width, height] normalized 0-1 or null}}]}}\n\n'
            f'First extract these predefined fields: {json.dumps(field_names)}\n\n'
            f'Then append ANY additional sections or headers you find that are not in the predefined list. '
            f'Use the section heading as the label and snake_case as the name.'
        )},
    ]
    try:
        import httpx
        url = ("https://generativelanguage.googleapis.com/v1beta/models"
               "/gemini-2.0-flash:generateContent")
        contents = [{"role": "user", "parts": user_parts}]
        with httpx.Client(timeout=90) as client:
            r = client.post(url, params={"key": key}, json={"contents": contents})
            r.raise_for_status()
            raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:
        logger.error("Gemini Vision failed: %s", exc)
        return []

    data = _parse_json(raw)
    return _normalize_fields(data.get("fields", []), field_meta, allow_bbox=True)


_NULL_VALUES = {"null", "none", "n/a", "na", "not found", "not available", "unknown", "-", "–", ""}

def _normalize_fields(raw_fields: list[dict], field_meta: dict, allow_bbox: bool = False) -> list[dict]:
    result = []
    seen = set()
    for f in raw_fields:
        name = f.get("name", "").strip()
        value = f.get("value")
        if not name or value is None or name in seen:
            continue
        if str(value).strip().lower() in _NULL_VALUES:
            continue
        seen.add(name)
        meta = field_meta.get(name)
        # Use schema label if known; otherwise use LLM-provided label or prettify the name
        label = (meta["label"] if meta else
                 f.get("label") or name.replace("_", " ").title())
        bbox = f.get("bbox") if allow_bbox else None
        if bbox is not None and (not isinstance(bbox, list) or len(bbox) != 4):
            bbox = None
        result.append({
            "name": name,
            "label": label,
            "value": str(value),
            "confidence": max(0.0, min(1.0, float(f.get("confidence", 0.7)))),
            "field_type": meta.get("field_type", "text") if meta else "text",
            "bbox": bbox,
            "page": 1,
        })
    return result
