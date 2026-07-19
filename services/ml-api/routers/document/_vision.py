"""Vision + OCR extraction for scanned/image documents.
Vision cascade: Groq Qwen3.6-27B → Mistral medium → Gemini 2.0 Flash.
OCR-first path: mistral-ocr-latest converts pages to markdown so scanned
docs can use the same text cascade as digital PDFs.
"""
from __future__ import annotations

import json
import logging
import os
import time

from ._llm import _parse_json, _normalize_fields

logger = logging.getLogger(__name__)


# ── OCR (Mistral) ─────────────────────────────────────────────────────────────

def mistral_ocr_pages(page_images: list[str]) -> tuple[str, list[dict]]:
    """Convert page images to markdown via mistral-ocr-latest.

    Returns (markdown, page_meta) where page_meta has one entry per uploaded
    page: {"width", "height", "blocks": [{bbox px coords, "content", "type"}]}.
    Both empty on failure.
    """
    key = os.environ.get("MISTRAL_API_KEY", "")
    if not key or not page_images:
        return "", []
    md_parts: list[str] = []
    page_meta: list[dict] = []
    try:
        import httpx
        with httpx.Client(timeout=90) as client:
            for b64 in page_images[:4]:
                r = client.post(
                    "https://api.mistral.ai/v1/ocr",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"model": "mistral-ocr-latest",
                          "document": {"type": "image_url",
                                       "image_url": f"data:image/png;base64,{b64}"}},
                )
                r.raise_for_status()
                for page in r.json().get("pages", []):
                    md = page.get("markdown", "")
                    if md:
                        md_parts.append(md)
                    dims = page.get("dimensions") or {}
                    page_meta.append({
                        "width": dims.get("width", 0),
                        "height": dims.get("height", 0),
                        "blocks": page.get("blocks") or [],
                    })
    except Exception as exc:
        logger.error("Mistral OCR failed: %s", exc)
    return "\n\n".join(md_parts), page_meta


def _ocr_norm_text(s: str) -> str:
    """Normalize text for block matching: lowercase, strip markdown noise."""
    import re
    s = re.sub(r"[#*_|`>\-]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def locate_fields_from_ocr(fields: list[dict], page_meta: list[dict]) -> None:
    """Set bbox + page on fields by matching values against OCR blocks in place.

    For each field: build candidate strings (JSON string values for structured
    fields, the value + comma-chunks for scalars), find blocks whose content
    contains a candidate, and take the union bbox of matches on the best page.
    """
    from ._extract import build_bbox_candidates

    for field in fields:
        if field.get("bbox") is not None or not field.get("value"):
            continue
        _, tier4, scalar_candidates = build_bbox_candidates(str(field["value"]))
        candidates = [_ocr_norm_text(c) for c in (tier4 or scalar_candidates[:6])]
        candidates = [c for c in candidates if len(c) >= 3]
        if not candidates:
            continue

        best_idx, best_boxes = -1, []
        for pi, meta in enumerate(page_meta):
            w, h = meta.get("width", 0), meta.get("height", 0)
            if not w or not h:
                continue
            boxes = []
            for blk in meta["blocks"]:
                content = _ocr_norm_text(blk.get("content", ""))
                if content and any(c in content for c in candidates):
                    boxes.append(blk)
            if len(boxes) > len(best_boxes):
                best_idx, best_boxes = pi, boxes
        if not best_boxes:
            continue

        meta = page_meta[best_idx]
        w, h = meta["width"], meta["height"]
        x0 = min(b["top_left_x"] for b in best_boxes)
        y0 = min(b["top_left_y"] for b in best_boxes)
        x1 = max(b["bottom_right_x"] for b in best_boxes)
        y1 = max(b["bottom_right_y"] for b in best_boxes)
        field["bbox"] = [round(x0 / w, 4), round(y0 / h, 4),
                         round((x1 - x0) / w, 4), round((y1 - y0) / h, 4)]
        field["page"] = best_idx + 1


# ── Vision providers (raw response) ───────────────────────────────────────────

def _groq_vision_raw(b64: str, prompt: str) -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return ""
    try:
        import httpx
        messages = [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": prompt},
        ]}]
        with httpx.Client(timeout=90) as client:
            r = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": "qwen/qwen3.6-27b",
                      "messages": messages, "max_tokens": 4096},
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"] or ""
    except Exception as exc:
        logger.error("Groq vision failed: %s", exc)
        return ""


def _mistral_vision_raw(b64: str, prompt: str) -> str:
    key = os.environ.get("MISTRAL_API_KEY", "")
    if not key:
        return ""
    try:
        import httpx
        messages = [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": prompt},
        ]}]
        with httpx.Client(timeout=90) as client:
            r = client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": "mistral-medium-latest", "messages": messages,
                      "max_tokens": 4096, "response_format": {"type": "json_object"},
                      "temperature": 0},
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"] or ""
    except Exception as exc:
        logger.error("Mistral vision failed: %s", exc)
        return ""


def _gemini_vision_raw(b64: str, prompt: str) -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return ""
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
                return r.json()["candidates"][0]["content"]["parts"][0]["text"] or ""
    except Exception as exc:
        logger.warning("Gemini vision failed: %s", exc)
    return ""


def _vision_cascade_raw(b64: str, prompt: str) -> str:
    from . import _llm as _llm_state
    for name, fn in (("groq", _groq_vision_raw), ("mistral", _mistral_vision_raw),
                     ("gemini", _gemini_vision_raw)):
        raw = fn(b64, prompt)
        if raw.strip():
            _llm_state.last_provider = f"{name} vision"
            return raw
    return ""


# ── Public API ────────────────────────────────────────────────────────────────

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


def extract_visual_sections(page_images: list[str], existing_names: set[str],
                            missing_names: set[str] | None = None) -> list[dict]:
    """Extract visual content via the vision cascade, page by page."""
    if not page_images:
        return []
    already = json.dumps(sorted(existing_names))
    missing = json.dumps(sorted(missing_names or []))
    prompt = _visual_prompt(already, missing)
    all_fields: list[dict] = []
    seen: set[str] = set()
    for b64 in page_images[:4]:
        raw = _vision_cascade_raw(b64, prompt)
        fields = _normalize_fields(_parse_json(raw).get("fields", []), {})
        for f in fields:
            if f["name"] not in seen:
                seen.add(f["name"])
                all_fields.append(f)
        time.sleep(1)
    return all_fields


def extract_fields_from_image(image_b64: str, doc_type: str, schema_fields: list[dict]) -> list[dict]:
    """One-shot field extraction from a document image via the vision cascade."""
    field_names = [f["name"] for f in schema_fields]
    field_meta = {f["name"]: f for f in schema_fields}
    prompt = (
        f'Extract data from this {doc_type} document image.\n'
        f'Return JSON: {{"fields": [{{"name": "<snake_case_name>", "label": "<Human Readable Label>", '
        f'"value": "<value or null>", "confidence": <0.0-1.0>, '
        f'"bbox": [left, top, width, height] normalized 0-1 or null}}]}}\n\n'
        f'First extract these predefined fields: {json.dumps(field_names)}\n\n'
        f'Then append ANY additional sections or headers you find that are not in the predefined list. '
        f'Use the section heading as the label and snake_case as the name.'
    )
    raw = _vision_cascade_raw(image_b64, prompt)
    return _normalize_fields(_parse_json(raw).get("fields", []), field_meta, allow_bbox=True)
