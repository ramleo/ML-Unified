"""Standalone image ingestion for multimodal RAG — one thorough caption +
OCR pass per upload, same 'image' chunk_type/retrieval path a PDF's
figures use. Split out of mm_ingest.py to stay under the project's
file-length limit.
"""
from __future__ import annotations

from routers.document._vision import _vision_cascade_raw, mistral_ocr_pages
from routers.rag.blur import blur_score
from routers.rag.mm_caption import (build_table_markdown, clean_ocr_text, extract_caption,
                                    extract_chart_data, split_pipe_tables)
from routers.rag.mm_objects import describe_objects, detect_objects

_OCR_TEXT_CAP = 2000


def _image_prompt(terse: bool = False) -> str:
    if terse:
        # Fallback for reasoning models that exhaust their token budget
        # thinking before answering a more demanding ask — short and direct
        # leaves it little room to ramble before the JSON is due.
        return (
            "In 2-3 short sentences, describe this image and transcribe any "
            'visible text or numbers exactly. Return JSON only: {"caption": "..."}.'
        )
    return (
        "Describe this image for someone who cannot see it: main subject, "
        "setting, colors, and any visible text/numbers (transcribe exactly). "
        "Be factual, 3-4 sentences. If this is a bar, line, or pie chart with "
        "genuinely identifiable numeric values — whether printed as data "
        "labels, or readable by judging bar heights/point positions against "
        "the axis scale — ALSO extract them as rows: one [category, value] "
        "pair per bar/point/slice. "
        'Return JSON only: {"caption": "<your description>", "chart_type": '
        '"bar"|"line"|"pie"|"none", "chart_data": [["<category>", "<value>"], '
        '...] (empty list if not a chart with extractable values)}.'
    )


def looks_like_image(file_bytes: bytes, content_type: str = "") -> bool:
    if content_type.startswith("image/"):
        return True
    sigs = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF",  # PNG, JPEG, GIF, WEBP(RIFF)
            b"BM", b"II*\x00", b"MM\x00*")                    # BMP, TIFF (little/big-endian)
    if any(file_bytes.startswith(s) for s in sigs):
        return True
    # Last resort: let PIL make the call — covers real image files whose exact
    # header a fixed signature list doesn't anticipate (e.g. unusual PNG/TIFF
    # variants exported by some invoice/office tools).
    try:
        from PIL import Image
        import io
        Image.open(io.BytesIO(file_bytes)).verify()
        return True
    except Exception:
        return False


def build_image_chunk(file_bytes: bytes, source: str) -> tuple[list[dict], list[str], dict]:
    """A standalone image upload — one 'image' chunk_type, described thoroughly
    (not the terser 'figure on a document page' framing used for PDF pages)."""
    from PIL import Image
    import io, base64

    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()

    raw = _vision_cascade_raw(b64, _image_prompt())
    caption = extract_caption(raw, 800)
    # MMRAG-14: chart-data extraction only from the main (non-terse) prompt
    # — the terser fallback below drops the ask entirely to keep leaving a
    # token-exhausted reasoning model as little to do as possible, same
    # reasoning that ask is terse in the first place.
    chart = extract_chart_data(raw)
    if not caption:
        # First attempt likely got cut off mid-reasoning before reaching the
        # JSON — one bounded retry with a terser ask that leaves less room
        # for a reasoning model to exhaust its token budget before answering.
        caption = extract_caption(_vision_cascade_raw(b64, _image_prompt(terse=True)), 400)

    ocr_md, _ = mistral_ocr_pages([b64])
    # A flat image can still have a real tabular layout (e.g. a photographed
    # or screenshotted invoice) — Mistral OCR reconstructs that as markdown
    # pipe-table syntax even with no PDF structure behind it. Surface that as
    # its own "table" chunk instead of only ever a flattened caption/OCR blob.
    table_blocks, remaining_md = split_pipe_tables(ocr_md)
    ocr_text = clean_ocr_text(remaining_md)[:_OCR_TEXT_CAP]
    if ocr_text:
        caption = f"{caption}\n\nExact text from image (OCR):\n{ocr_text}" if caption else ocr_text

    # No embedded "[Image: source]" prefix — citations.py's build_system_prompt
    # already labels this chunk with source/page/type when building the LLM's
    # context, so baking it into the stored text would only be redundant
    # noise in the citation UI's raw-text preview.
    quality = blur_score(b64)

    # Closed-vocabulary object detection (MMRAG-07 follow-up) — precomputed
    # here so a later "where is the X" chat question is a free metadata
    # lookup, not a fresh vision call. See mm_objects.py for scope/rationale.
    objects = detect_objects(b64)
    obj_desc = describe_objects(objects)
    if obj_desc:
        # Baked into the stored text itself (not just the LLM prompt) so a
        # "where is the X" answer stays backed by groundedness/citation
        # scoring, both of which only ever read chunk["text"] — see
        # mm_objects.describe_objects for why.
        caption = f"{caption}\n\n{obj_desc}" if caption else obj_desc

    chunks: list[dict] = []
    if caption:
        chunks.append({"text": caption, "source": source, "chunk_index": 0,
                       "chunk_type": "image", "page": 1, "quality": quality, "objects": objects})
    for tbl in table_blocks:
        chunks.append({"text": tbl, "source": source, "chunk_index": len(chunks),
                       "chunk_type": "table", "page": 1})
    chart_table_count = 0
    if chart:
        # MMRAG-14: same shape a real extracted table gets — RagTableView.tsx
        # already renders/plots/exports any "table"-typed chunk, no frontend
        # change needed to treat this differently from an in-document table.
        chart_type, rows = chart
        table_md = build_table_markdown([["Category", "Value"], *rows])
        chunks.append({"text": f"Data extracted from a {chart_type} chart:\n\n{table_md}",
                       "source": source, "chunk_index": len(chunks),
                       "chunk_type": "table", "page": 1})
        chart_table_count = 1

    summary = {"text": 0, "table": len(table_blocks) + chart_table_count, "figure": 0,
              "image": 1 if caption else 0}
    return chunks, [b64], summary
