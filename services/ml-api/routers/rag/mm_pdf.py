"""PDF page extraction for multimodal RAG — text/table/figure chunking, split
into prepare-once + process-one-page so the SSE stream in mm_ingest.py can
yield a real "page X of N" progress event between pages, instead of one
opaque call that blocks until the whole document is done. Split out of
mm_ingest.py to stay under the project's file-length limit.
"""
from __future__ import annotations

import re

from routers.document._extract import extract_tables_markdown
from routers.document._vision import _vision_cascade_raw
from routers.rag.ingest import chunk_document
from routers.rag.mm_caption import extract_caption

MAX_PAGES = 8
_DENSE_TEXT_THRESHOLD = 80  # chars; below this + has images/drawings → caption it
_RENDER_ZOOM = 2.0          # fitz zoom factor (~144 DPI, since PDF base is 72 DPI) —
                            # higher than Document Intelligence's 1.2x preview renders
                            # since this feeds the vision cascade, not just a thumbnail


def _render_page(page, zoom: float = _RENDER_ZOOM) -> str:
    import base64
    import fitz
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    return base64.b64encode(pix.tobytes("png")).decode()


def _is_visually_dense(page, text: str) -> bool:
    if len(text.strip()) >= _DENSE_TEXT_THRESHOLD:
        return False
    try:
        return bool(page.get_images()) or bool(page.get_drawings())
    except Exception:
        return False


def _split_tables_by_page(tables_md: str) -> dict[int, list[str]]:
    """extract_tables_markdown() prefixes each table with '### Table (Page N)'
    — split its whole-doc output back into per-page blocks without re-parsing
    the PDF a second time."""
    if not tables_md.strip():
        return {}
    blocks = re.split(r"(?=### Table \(Page \d+\))", tables_md)
    by_page: dict[int, list[str]] = {}
    for block in blocks:
        m = re.match(r"### Table \(Page (\d+)\)", block.strip())
        if m:
            by_page.setdefault(int(m.group(1)), []).append(block.strip())
    return by_page


def _caption_prompt() -> str:
    return (
        "This is a page from a document, shown because it appears to be a "
        "chart, diagram, photo, or other visual content rather than plain text. "
        "Write a factual 2-4 sentence description for someone who cannot see "
        "it: what type of visual it is, what it shows, and transcribe any "
        "axis labels, legend values, or numbers that are visible. "
        'Return JSON only: {"caption": "<your description>"}.'
    )


def _caption_page(b64: str) -> str:
    return extract_caption(_vision_cascade_raw(b64, _caption_prompt()), 500)


# ── Per-page (streaming path) ───────────────────────────────────────────────────

def prepare_pdf(file_bytes: bytes):
    """Open the PDF and extract table markdown once. Returns (doc, n_pages, tables_by_page)."""
    import fitz
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    n_pages = min(MAX_PAGES, len(doc))
    tables_by_page = _split_tables_by_page(extract_tables_markdown(file_bytes, max_pages=n_pages))
    return doc, n_pages, tables_by_page


def process_page(doc, page_num: int, tables_by_page: dict, source: str) -> tuple[list[dict], str, dict]:
    """Extract chunks for ONE page. Returns (chunks, page_b64, page_summary)."""
    page = doc[page_num - 1]
    text = page.get_text()
    b64 = _render_page(page)
    page_chunks: list[dict] = []
    page_summary = {"text": 0, "table": 0, "figure": 0}

    if len(text.strip()) >= 20:
        for c in chunk_document(text, source):
            c["chunk_type"] = "text"
            c["page"] = page_num
            page_chunks.append(c)
        page_summary["text"] = 1

    for table_md in tables_by_page.get(page_num, []):
        page_chunks.append({"text": table_md, "source": source, "chunk_index": len(page_chunks),
                            "chunk_type": "table", "page": page_num})
        page_summary["table"] += 1

    if _is_visually_dense(page, text):
        caption = _caption_page(b64)
        if caption:
            page_chunks.append({"text": caption, "source": source, "chunk_index": len(page_chunks),
                                "chunk_type": "figure", "page": page_num})
            page_summary["figure"] = 1

    return page_chunks, b64, page_summary


# ── Whole-file (used by evaluate_mm.py, which doesn't need live progress) ──────

def build_multimodal_chunks(file_bytes: bytes, source: str,
                            progress_cb=None) -> tuple[list[dict], list[str], dict]:
    """Returns (chunks, page_images, chunk_summary). chunks carry chunk_type/page."""
    doc, n_pages, tables_by_page = prepare_pdf(file_bytes)

    chunks: list[dict] = []
    page_images: list[str] = []
    summary = {"text": 0, "table": 0, "figure": 0}

    for page_num in range(1, n_pages + 1):
        if progress_cb:
            progress_cb({"step": "extract", "page": page_num, "pages": n_pages})
        page_chunks, b64, page_summary = process_page(doc, page_num, tables_by_page, source)
        chunks.extend(page_chunks)
        page_images.append(b64)
        for k in summary:
            summary[k] += page_summary[k]

    doc.close()
    return chunks, page_images, summary
