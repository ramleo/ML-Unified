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
# Some providers (observed: Mistral under its forced JSON mode) ignore the
# requested {"caption": ...} shape and answer with their own key names
# instead — the JSON itself is perfectly valid, so a missing "caption" key
# shouldn't fall all the way to dumping the raw JSON when a plausible
# substitute is right there. "text" is deliberately last: in the observed
# case it just re-transcribed on-image text that the separate OCR pass
# already covers, so it's a worse pick than a real "description"/"summary".
_ALT_CAPTION_KEYS = ("description", "summary", "caption_text", "text")


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
            parsed = json.loads(fenced[start:end])
            value = parsed.get("caption", "")
            if not str(value).strip():
                for key in _ALT_CAPTION_KEYS:
                    alt = parsed.get(key, "")
                    if str(alt).strip():
                        value = alt
                        break
            if not str(value).strip() and isinstance(parsed, dict):
                # Last resort before giving up on the parsed JSON entirely:
                # a model can hallucinate its own key name outside even the
                # known _ALT_CAPTION_KEYS list (observed: {"cnotation": "..."}
                # instead of {"caption": "..."}) — the single LONGEST string
                # value in an otherwise-valid JSON object is almost certainly
                # that misnamed description, not a raw JSON dump.
                string_values = [v for v in parsed.values() if isinstance(v, str) and v.strip()]
                if string_values:
                    value = max(string_values, key=len)
            if str(value).strip():
                return str(value).strip()
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


# EC-007: a reasoning vision model (observed: Groq's Qwen) can complete its
# <think> block coherently but reason its way to a confidently WRONG
# conclusion — inventing a multi-panel collage/composite structure on a
# single plain photo (e.g. "a vertical collage of four cropped sections of
# a young man's face" for one ordinary headshot). Unlike a truncated <think>
# leak (already caught by strip_thinking above), there's no parsing signal
# that this text is wrong — it's a well-formed, on-topic sentence. The only
# way to catch it is a cross-check against an INDEPENDENTLY computed signal
# (object detection's bbox sizes), done by the caller — this just flags the
# caption text side of that check.
# Not a single bounded phrase — observed wording varies too much ("...four
# cropped sections..." vs "...close-up crops of a young man's face... The
# top section displays...", crop-word and structure-word can land in
# different sentences). Two independent word-groups anywhere in the text is
# enough: the object-detection contradiction check in mm_image.py (a single
# detection spanning most of the frame) is what actually guards against a
# false positive on a genuine multi-subject collage, not word proximity here.
_COLLAGE_WORD_RE = re.compile(r"\b(collage|composite)\b", re.IGNORECASE)
_CROP_STRUCTURE_WORD_RE = re.compile(
    r"\b(crops?|cropped|cropping|sections?|panels?|quadrants?|tiles?|views?)\b", re.IGNORECASE)


def looks_like_fabricated_collage(caption: str) -> bool:
    return bool(_COLLAGE_WORD_RE.search(caption) and _CROP_STRUCTURE_WORD_RE.search(caption))


def build_table_markdown(rows: list[list]) -> str:
    """A pipe-table string from a header row + data rows — shared by real
    PDF-extracted tables (mm_pdf.py) and MMRAG-14's chart-data extraction
    below, so both land on the exact markdown shape RagTableView.tsx
    already knows how to render/plot/export, without the frontend needing
    to know these came from two different places."""
    lines: list[str] = []
    for j, row in enumerate(rows):
        cells = [str(c or "").strip().replace("|", " ") for c in row]
        lines.append("| " + " | ".join(cells) + " |")
        if j == 0:
            lines.append("|" + "|".join(["---"] * len(row)) + "|")
    return "\n".join(lines)


# MMRAG-14: a chart's prose caption ("revenue grew steadily across quarters")
# is often not enough to actually answer a numeric question ("what was Q3
# revenue") — the vision model is asked (via _caption_prompt/_image_prompt)
# to ALSO read the chart's actual values, whether they're printed as data
# labels or have to be read off bar heights/positions against the axis
# scale, as a second field in the same JSON response (no extra vision
# call). Parsed independently of extract_caption above — a chart_data
# field breaking shouldn't cost the caption, and vice versa.
def extract_chart_data(raw: str) -> tuple[str, list[list[str]]] | None:
    """Returns (chart_type, rows) — rows as [[category, value], ...] — or
    None whenever there's nothing genuinely extractable (a photo/diagram/
    logo, a model that didn't include the field, or fewer than 2 usable
    rows). Never fabricates a table where the visual isn't actually a
    chart with real values."""
    raw = strip_thinking(raw)
    if not raw.strip():
        return None
    fenced = _FENCE_RE.sub("", raw.strip()).strip()
    start, end = fenced.find("{"), fenced.rfind("}") + 1
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(fenced[start:end])
    except Exception:
        return None
    raw_rows = parsed.get("chart_data")
    if not isinstance(raw_rows, list):
        return None
    clean_rows = [[str(r[0]).strip(), str(r[1]).strip()] for r in raw_rows
                  if isinstance(r, (list, tuple)) and len(r) >= 2]
    if len(clean_rows) < 2:
        return None
    chart_type = str(parsed.get("chart_type") or "chart").strip() or "chart"
    return chart_type, clean_rows


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


def is_junk_table_block(block: str) -> bool:
    """True when a "table" block found by split_pipe_tables isn't a real
    table at all — Mistral OCR sometimes wraps a lone image-reference
    placeholder (see clean_ocr_text's docstring) in pipe/separator syntax
    on a photo with nothing tabular on it (observed live: an ordinary face
    photo produced a bogus one-cell "table" whose only content was
    "![img-0.jpeg](img-0.jpeg)"), which split_pipe_tables' contiguous-pipe-
    lines heuristic can't distinguish from a genuine table. Strips each
    line's pipe/dash table syntax and any image-ref placeholder; if nothing
    substantive is left, this was never a real table."""
    stripped = re.sub(r"[|\-\s]", "", _IMG_REF_RE.sub("", block))
    return len(stripped) < 3


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
