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


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
# Loosely matches a `"caption": "..."` value even when the surrounding JSON
# is otherwise broken (unescaped quote inside the value, or the response got
# cut off mid-string before ever reaching a closing brace) — the trailing
# quote is optional specifically for that truncation case, so a caption that
# was 95% generated is still usable instead of being thrown away entirely.
_CAPTION_FIELD_RE = re.compile(r'"caption"\s*:\s*"((?:[^"\\]|\\.)*)"?')


def extract_caption(raw: str, fallback_len: int) -> str:
    """Pull {"caption": "..."} out of a vision response. Falls back to a
    looser regex extraction when strict JSON parsing fails (a reasoning
    model's JSON commonly breaks via truncation or an unescaped quote inside
    the description — not because the caption itself is unusable), and only
    as a last resort to the raw text — a valid-but-differently-shaped JSON
    response should not discard an otherwise-good description."""
    raw = strip_thinking(raw)
    if not raw.strip():
        return ""
    fenced = _FENCE_RE.sub("", raw.strip()).strip()

    start, end = fenced.find("{"), fenced.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            parsed = json.loads(fenced[start:end]).get("caption", "")
            if str(parsed).strip():
                return str(parsed).strip()
        except Exception as exc:
            logger.warning("Caption JSON parse failed (%s), trying regex fallback: %r", exc, raw[:200])

    # Reached whenever strict parsing didn't yield a caption — including when
    # there's no closing brace at all (severe truncation), which the block
    # above never even attempts to json.loads. A response cut off mid-string
    # still has a real, usable partial description worth pulling out here.
    m = _CAPTION_FIELD_RE.search(fenced)
    if m:
        value = m.group(1).replace('\\"', '"').replace("\\n", " ").replace("\\\\", "\\").strip()
        if value:
            return value[:fallback_len]
    return fenced[:fallback_len]


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


def split_pipe_tables(md: str) -> tuple[list[str], str]:
    """Splits OCR markdown into (table_blocks, remaining_text). Mistral OCR
    reconstructs a real pipe-table (`| a | b |`) when the source image has a
    visibly tabular layout — even for a flat photo/PNG with no PDF structure
    behind it (e.g. a screenshotted invoice). A contiguous run of 2+ such
    lines is treated as a genuine table, mirroring the PDF ingestion path's
    table detection; everything else stays as plain OCR text."""
    lines = md.split("\n")
    tables: list[str] = []
    remaining: list[str] = []
    current: list[str] = []
    for line in lines:
        if line.strip().startswith("|"):
            current.append(line)
            continue
        if len(current) >= 2:
            tables.append("\n".join(current))
        else:
            remaining.extend(current)
        current = []
        remaining.append(line)
    if len(current) >= 2:
        tables.append("\n".join(current))
    else:
        remaining.extend(current)
    return tables, "\n".join(remaining)


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
