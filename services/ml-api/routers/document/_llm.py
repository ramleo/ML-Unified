"""LLM provider cascade for document field extraction.
Zero imports from other ml-api routers — self-contained for microservice extraction.
Cascade order: Groq (llama-3.3-70b) → Gemini 2.0 Flash → Cohere command-r-plus
"""
from __future__ import annotations

import json
import logging
import os
import re
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
            model="llama-3.3-70b-versatile", messages=full, max_tokens=2000,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        logger.warning("Groq failed: %s", exc)
        return ""


def _gemini_text(messages: list[dict], system: str) -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return ""
    try:
        import httpx
        contents = []
        if system:
            contents += [
                {"role": "user", "parts": [{"text": f"[System]: {system}"}]},
                {"role": "model", "parts": [{"text": "Understood."}]},
            ]
        for m in messages:
            role = "model" if m["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        url = ("https://generativelanguage.googleapis.com/v1beta/models"
               "/gemini-2.0-flash:generateContent")
        with httpx.Client(timeout=60) as client:
            r = client.post(url, params={"key": key}, json={"contents": contents})
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:
        logger.warning("Gemini text failed: %s", exc)
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
                json={"model": "command-r-plus", "messages": fmt},
            )
            r.raise_for_status()
            return r.json()["message"]["content"][0]["text"]
    except Exception as exc:
        logger.warning("Cohere failed: %s", exc)
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
    doc_type = data.get("doc_type", known_types[0])
    confidence = float(data.get("confidence", 0.7))
    if doc_type not in known_types:
        doc_type = known_types[0]
    return doc_type, max(0.0, min(1.0, confidence))


def extract_fields_from_text(text: str, doc_type: str, schema_fields: list[dict]) -> list[dict]:
    """Extract fields from document text using the LLM cascade."""
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
        f"Document text:\n{text[:4000]}"
    )
    raw = _cascade([{"role": "user", "content": prompt}], system)
    data = _parse_json(raw)
    return _normalize_fields(data.get("fields", []), field_meta)


def extract_visual_sections(image_b64: str, existing_names: set[str]) -> list[dict]:
    """Send a rendered page image to Gemini to extract visual-only content
    (embedded timelines, charts, image-based tables) missed by text extraction."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return []
    already = json.dumps(sorted(existing_names))
    user_parts = [
        {"inline_data": {"mime_type": "image/png", "data": image_b64}},
        {"text": (
            "This PDF page was already processed with text extraction. "
            f"Fields already extracted: {already}. "
            "Now look ONLY at visual elements — embedded images, graphical timelines, "
            "image-based tables, charts, or any section whose content is rendered as a graphic "
            "rather than selectable text. "
            "Extract the content of each such visual section. "
            'Return JSON: {"fields": [{"name": "<snake_case>", "label": "<Section Name as it appears>", '
            '"value": "<full extracted content>", "confidence": <0.0-1.0>}]}. '
            "Return an empty fields list if no visual-only content is found. "
            "Do NOT re-extract fields already listed above."
        )},
    ]
    try:
        import httpx
        url = ("https://generativelanguage.googleapis.com/v1beta/models"
               "/gemini-2.0-flash:generateContent")
        with httpx.Client(timeout=90) as client:
            r = client.post(url, params={"key": key},
                            json={"contents": [{"role": "user", "parts": user_parts}]})
            r.raise_for_status()
            raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        data = _parse_json(raw)
        return _normalize_fields(data.get("fields", []), {})
    except Exception as exc:
        logger.warning("Visual section extraction failed: %s", exc)
        return []


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


def _normalize_fields(raw_fields: list[dict], field_meta: dict, allow_bbox: bool = False) -> list[dict]:
    result = []
    seen = set()
    for f in raw_fields:
        name = f.get("name", "").strip()
        value = f.get("value")
        if not name or value is None or name in seen:
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
