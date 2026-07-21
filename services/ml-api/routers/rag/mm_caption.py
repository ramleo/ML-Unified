"""Vision-response caption extraction — shared by mm_pdf.py (PDF figures) and
mm_ingest.py (standalone images). Split out on its own since both callers
need it and neither owns it."""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def strip_thinking(text: str) -> str:
    """Some reasoning models (e.g. Qwen) prefix output with a <think>...</think>
    block even when only asked for JSON. Drop it — it's internal monologue,
    not a caption, and would otherwise pollute the retrievable chunk text."""
    if "<think>" not in text:
        return text
    if "</think>" in text:
        return text.split("</think>", 1)[1].strip()
    return ""  # unterminated — the whole response was reasoning, nothing usable


def extract_caption(raw: str, fallback_len: int) -> str:
    """Pull {"caption": "..."} out of a vision response. Falls back to the raw
    text whenever JSON parsing fails OR succeeds without a usable caption —
    a valid-but-differently-shaped JSON response should not discard an
    otherwise-good description."""
    raw = strip_thinking(raw)
    if not raw.strip():
        return ""
    try:
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(raw[start:end]).get("caption", "")
            if str(parsed).strip():
                return str(parsed).strip()
    except Exception as exc:
        logger.warning("Caption JSON parse failed (%s), using raw text: %r", exc, raw[:200])
    return raw.strip()[:fallback_len]
