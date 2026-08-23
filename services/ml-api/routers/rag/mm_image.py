"""Standalone image ingestion for multimodal RAG — one thorough caption +
OCR pass per upload, same 'image' chunk_type/retrieval path a PDF's
figures use. Split out of mm_ingest.py to stay under the project's
file-length limit.
"""
from __future__ import annotations

from routers.document._vision import _vision_cascade_raw, mistral_ocr_pages
from routers.rag.blur import blur_score
from routers.rag.mm_caption import (build_table_markdown, clean_ocr_text, extract_caption,
                                    extract_chart_data, is_junk_table_block, split_pipe_tables)
from routers.rag.mm_duplicates import describe_duplicates, detect_duplicates
from routers.rag.mm_objects import describe_objects, detect_objects
from routers.rag.mm_jpeg_ghost import detect_jpeg_ghosts
from routers.rag.mm_noise_forensics import detect_noise_regions
from routers.rag.mm_segment import refine_masks
from routers.rag.mm_signatures import describe_signatures, detect_signatures
from routers.rag.mm_tables import detect_table_regions
from routers.rag.mm_tampering import combine_tampering_detections, describe_tampering, detect_tampering
from routers.rag.mm_steganography import describe_steganography, detect_steganography
from routers.rag.mm_moire import describe_moire, detect_moire

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


def build_image_chunk(file_bytes: bytes, source: str, session_id: str = "") -> tuple[list[dict], list[str], dict]:
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
    # Discard a "table" that's actually just a wrapped image-reference
    # placeholder with no real tabular content — a genuine live false
    # positive: an ordinary face photo produced a bogus table chunk whose
    # only content was the placeholder text itself. See is_junk_table_block.
    table_blocks = [b for b in table_blocks if not is_junk_table_block(b)]
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
    objects, person_count = detect_objects(b64)
    obj_desc = describe_objects(objects)
    if obj_desc:
        # Baked into the stored text itself (not just the LLM prompt) so a
        # "where is the X" answer stays backed by groundedness/citation
        # scoring, both of which only ever read chunk["text"] — see
        # mm_objects.describe_objects for why.
        caption = f"{caption}\n\n{obj_desc}" if caption else obj_desc

    # Signature detection (backlog item 1) — same "compute once at ingest,
    # free metadata lookup later" rationale as object detection above, own
    # model/vocabulary so kept as a separate field rather than merged into
    # `objects` (mixing would corrupt the OIV7 label-based "Detect faces"
    # filter and the "Detect objects (N)" count elsewhere).
    signatures = detect_signatures(b64)
    sig_desc = describe_signatures(signatures)
    if sig_desc:
        caption = f"{caption}\n\n{sig_desc}" if caption else sig_desc

    # Tampering detection (backlog item 2) — three independent signals (ELA
    # + jpeg-ghost: JPEG-only; noise-residual: format-agnostic) merged into
    # one field, so a PNG/WebP/BMP upload still gets real coverage instead
    # of only ever working on JPEGs. See mm_tampering.py's module docstring.
    tampering = combine_tampering_detections(
        detect_tampering(b64), detect_noise_regions(b64), detect_jpeg_ghosts(b64))
    tamper_desc = describe_tampering(tampering)
    if tamper_desc:
        caption = f"{caption}\n\n{tamper_desc}" if caption else tamper_desc

    # Steganography detection — whole-image verdict (no bbox, see
    # mm_steganography.py's module docstring for why), so a separate field
    # from tampering rather than merged into it.
    steganography = detect_steganography(b64)
    stego_desc = describe_steganography(steganography)
    if stego_desc:
        caption = f"{caption}\n\n{stego_desc}" if caption else stego_desc

    # Moire/scan-line detection — whole-image verdict, same shape as
    # steganography above, see mm_moire.py's module docstring.
    moire = detect_moire(b64)
    moire_desc = describe_moire(moire)
    if moire_desc:
        caption = f"{caption}\n\n{moire_desc}" if caption else moire_desc

    # Pixel-accurate mask refinement (backlog item 5, final CV backlog item)
    # — signatures/tampering are the two detector types whose rectangular
    # bbox most understates the real shape (ink strokes, irregular edited
    # regions); a face or a generic object's bbox is already close to its
    # own shape, so left at plain rectangles. Purely additive — see
    # mm_segment.py's module docstring.
    signatures = refine_masks(b64, signatures)
    tampering = refine_masks(b64, tampering)

    # Near-duplicate detection (backlog item 3) — same "compute once at
    # ingest" rationale as everything above; needs session_id since a match
    # is only meaningful against this caller's own earlier uploads.
    duplicates = detect_duplicates(b64, source, 1, session_id)
    dup_desc = describe_duplicates(duplicates)
    if dup_desc:
        caption = f"{caption}\n\n{dup_desc}" if caption else dup_desc

    chunks: list[dict] = []
    if caption:
        chunks.append({"text": caption, "source": source, "chunk_index": 0,
                       "chunk_type": "image", "page": 1, "quality": quality, "objects": objects,
                       "person_count": person_count,
                       "signatures": signatures, "tampering": tampering,
                       "steganography": steganography, "moire": moire, "duplicates": duplicates})
    # Table-region detection (backlog item 4) — only worth the model-load
    # cost when OCR actually found at least one pipe-table to attach a bbox
    # to; positional pairing (both lists already top-to-bottom) since
    # neither an OCR-reconstructed markdown block nor Table Transformer's
    # own output carries an ID linking them together. See mm_tables.py.
    table_regions = detect_table_regions(b64) if table_blocks else []
    for i, tbl in enumerate(table_blocks):
        chunk = {"text": tbl, "source": source, "chunk_index": len(chunks), "chunk_type": "table", "page": 1}
        if i < len(table_regions):
            chunk["bbox"] = table_regions[i]["bbox"]
        chunks.append(chunk)
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
