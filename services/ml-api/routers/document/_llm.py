"""LLM provider cascade for document field extraction (text path).
Zero imports from other ml-api routers — self-contained for microservice extraction.
Cascade order: Mistral (medium→large) → Gemini → Cohere → Cerebras. Groq
dropped from the automatic cascade (2026-08-24) — no free replacement model
that actually worked reliably for this app's request pattern was found (see
routers/rag/query.py's _DEFAULT_PROVIDER comment for the full history).
Still selectable manually via BYOK (provider="groq"), just never tried
automatically. Vision/OCR lives in _vision.py.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)


# ── Provider implementations ──────────────────────────────────────────────────

def _groq(messages: list[dict], system: str,
          model: str = "groq/compound", max_tokens: int = 4096) -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return ""
    try:
        import openai
        full = ([{"role": "system", "content": system}] if system else []) + messages
        client = openai.OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
        resp = client.chat.completions.create(
            model=model, messages=full, max_tokens=max_tokens,
            response_format={"type": "json_object"}, temperature=0,
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        logger.error("Groq failed: %s", exc)
        return ""


def _mistral(messages: list[dict], system: str) -> str:
    """Mistral: medium first; large only if medium errors or returns invalid JSON."""
    key = os.environ.get("MISTRAL_API_KEY", "")
    if not key:
        return ""
    import openai
    full = ([{"role": "system", "content": system}] if system else []) + messages
    client = openai.OpenAI(api_key=key, base_url="https://api.mistral.ai/v1")
    for model in ("mistral-medium-latest", "mistral-large-latest"):
        try:
            resp = client.chat.completions.create(
                model=model, messages=full, max_tokens=4096,
                response_format={"type": "json_object"}, temperature=0,
            )
            out = resp.choices[0].message.content or ""
            if out.strip() and _parse_json(out):
                return out
            logger.warning("Mistral %s returned empty/invalid JSON, trying next", model)
        except Exception as exc:
            logger.error("Mistral %s failed: %s", model, exc)
    return ""


def _cerebras(messages: list[dict], system: str) -> str:
    key = os.environ.get("CEREBRAS_API_KEY", "")
    if not key:
        return ""
    try:
        import openai
        full = ([{"role": "system", "content": system}] if system else []) + messages
        client = openai.OpenAI(api_key=key, base_url="https://api.cerebras.ai/v1")
        resp = client.chat.completions.create(
            model="gpt-oss-120b", messages=full, max_tokens=4096,
            response_format={"type": "json_object"}, temperature=0,
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        logger.error("Cerebras failed: %s", exc)
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
               "/gemini-3.6-flash:generateContent")
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


# Name of the provider that served the most recent successful call.
# Read by the router right after extraction to attribute results in the UI.
last_provider: str = ""

# Gemini is the only PAID key here, so it goes last — this endpoint is public
# and unauthenticated, and a visitor who never signs in should not be able to
# spend money by uploading a document.
#
# It used to sit second, behind Mistral. Mistral's free tier has no reserved
# capacity and 429s essentially every request (Part 276 §15), so "second" was
# in practice FIRST: the paid key served the public endpoint by default while
# free Cohere sat third and was almost never reached.
#
# Order now matches routers/rag/generation.py's FALLBACK_CANDIDATES, which was
# reasoned through for the same trade-off: Cohere first (free and reliable),
# Mistral next (free, works whenever capacity exists, costs one ~0.5s round
# trip when it does not), then Cerebras, and the paid key only once every free
# option has actually been tried.
_CASCADE_ORDER = (("cohere", _cohere), ("mistral", _mistral),
                  ("cerebras", _cerebras), ("gemini", _gemini_text))


def _cascade(messages: list[dict], system: str) -> str:
    global last_provider
    for i, (name, fn) in enumerate(_CASCADE_ORDER):
        result = fn(messages, system)
        if result.strip():
            if i > 0:
                logger.warning("Document LLM cascade fell back to %s after %d failed attempt(s)", name, i)
            last_provider = name
            return result
    last_provider = ""
    logger.error("Document LLM cascade exhausted — all providers failed or returned empty")
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


def classify_document(text_sample: str, known_types: list[str],
                      descriptions: dict[str, str] | None = None) -> tuple[str, float]:
    """Classify doc type from a text sample. Returns (doc_type, confidence 0–1)."""
    types_str = ", ".join(f'"{t}"' for t in known_types)
    if descriptions:
        types_block = "\n".join(f'- "{t}": {descriptions.get(t, "")}' for t in known_types)
    else:
        types_block = types_str
    system = "You are a document classification expert. Respond only with valid JSON."
    prompt = (
        f"Classify this document into one of these types:\n{types_block}\n\n"
        f"Respond with JSON only: "
        f'{{\"doc_type\": <one of {types_str}>, \"confidence\": <0.0-1.0>}}\n\n'
        f"Document excerpt:\n{text_sample[:600]}"
    )
    raw = _cascade([{"role": "user", "content": prompt}], system)
    data = _parse_json(raw)
    doc_type = data.get("doc_type", "")
    confidence = float(data.get("confidence", 0.7))
    if not doc_type or doc_type not in known_types:
        logger.warning(
            "Document classification: LLM cascade gave no usable doc_type, "
            "falling back to keyword classifier"
        )
        doc_type, confidence = _keyword_classify(text_sample, known_types)
    return doc_type, max(0.0, min(1.0, confidence))


def extract_fields_from_text(text: str, doc_type: str, schema_fields: list[dict],
                             provider: str = "auto", tier: str = "complex",
                             hints: str = "") -> list[dict]:
    """Extract fields from document text using the LLM cascade (or a forced provider).
    tier="simple" routes to a small fast model first (complexity-based routing);
    any failure falls through to the normal cascade.
    hints: optional few-shot guidance block (e.g. past human corrections)."""
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
        f'For total experience / duration fields: NEVER compute "latest date minus earliest date" — '
        f'employment histories contain gaps. Sum each listed period individually (per-role start to end) '
        f'and show the working in the value, e.g. "~11 years (sum of listed roles; gaps excluded)". '
        f'If per-role dates are not stated, use null.\n\n'
        + (f"{hints}\n\n" if hints else "")
        + f"Document text:\n{text[:14000]}"
    )
    global last_provider
    _provider_map = {"groq": _groq, "mistral": _mistral, "gemini": _gemini_text, "cohere": _cohere}
    fn = _provider_map.get(provider)
    messages = [{"role": "user", "content": prompt}]
    if fn:
        raw = fn(messages, system)
        if raw.strip():
            last_provider = provider
    else:
        raw = ""
        if tier == "simple":
            # Simple doc → fast path, tried before the full cascade below.
            # Previously used Groq specifically for its free-tier speed;
            # Groq dropped from the automatic path entirely (2026-08-24, see
            # module docstring) with no equivalent small/fast free model
            # found elsewhere, so this now just tries Mistral directly —
            # still faster than the full cascade when it succeeds, since
            # cascade order already puts Mistral first anyway.
            raw = _mistral(messages, system)
            if raw.strip() and _parse_json(raw).get("fields"):
                last_provider = "mistral · fast"
            else:
                logger.warning(
                    "Field extraction: fast-tier model returned empty/invalid JSON, "
                    "falling back to full cascade"
                )
                raw = ""
        if not raw:
            raw = _cascade(messages, system)
    data = _parse_json(raw)
    return _normalize_fields(data.get("fields", []), field_meta)


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
        # Structured values must serialize as valid JSON (double quotes) — str()
        # would emit Python repr with single quotes, breaking json.loads in the
        # bbox search and validator downstream. Models may also return the value
        # as a string that is itself single-quoted pseudo-JSON — normalize both.
        value_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        s = value_str.strip()
        if s[:1] in ("{", "["):
            try:
                json.loads(s)
            except json.JSONDecodeError:
                try:
                    import ast
                    value_str = json.dumps(ast.literal_eval(s))
                except Exception:
                    pass
        result.append({
            "name": name,
            "label": label,
            "value": value_str,
            "confidence": max(0.0, min(1.0, float(f.get("confidence", 0.7)))),
            "field_type": meta.get("field_type", "text") if meta else "text",
            "bbox": bbox,
            "page": 1,
        })
    return result
