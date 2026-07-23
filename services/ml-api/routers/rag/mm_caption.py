"""Vision-response caption extraction — shared by mm_pdf.py (PDF figures),
mm_ingest.py (standalone images), and mm_video.py (video frames). Split out
on its own since none of those callers own it exclusively."""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

_IMG_REF_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


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


def clean_ocr_text(md: str) -> str:
    """Mistral OCR returns markdown image-reference placeholders (e.g.
    "![img-0.jpeg](img-0.jpeg)") — sometimes ONLY that, no real transcribed
    text — when a page/frame has nothing on it worth transcribing (observed
    live: video frames with no on-screen text). Strip those placeholders;
    if what's left isn't substantive, return "" so callers skip the OCR
    line entirely rather than show garbage like a bare "A" or an empty
    image reference."""
    text = _IMG_REF_RE.sub("", md).strip()
    if len(text) < 3:
        return ""
    return text


_SIG_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?%?")


def numbers_disagree(caption: str, ocr_text: str) -> bool:
    """True when the caption and OCR read of the SAME figure cite completely
    disjoint numbers — e.g. the vision model's caption says "revenue grew to
    $42M" while OCR transcribed "$24M" off the same chart. Only "significant"
    numbers count (2+ digits, a decimal, or a percent sign) so incidental
    single digits (list markers, "a 2-bar chart") don't cause false flags.
    Silent when either side has no significant numbers at all — nothing to
    compare, not a disagreement."""
    def sig_numbers(text: str) -> set[str]:
        return {t for t in _SIG_NUMBER_RE.findall(text) if len(t.rstrip("%")) >= 2 or "." in t}

    cap_nums, ocr_nums = sig_numbers(caption), sig_numbers(ocr_text)
    if not cap_nums or not ocr_nums:
        return False
    return cap_nums.isdisjoint(ocr_nums)
