"""PDF page extraction for multimodal RAG — text/table/figure chunking, split
into prepare-once + process-one-page so the SSE stream in mm_ingest.py can
yield a real "page X of N" progress event between pages, instead of one
opaque call that blocks until the whole document is done. Split out of
mm_ingest.py to stay under the project's file-length limit.
"""
from __future__ import annotations

from routers.document._vision import _vision_cascade_raw, mistral_ocr_pages
from routers.rag.blur import blur_score
from routers.rag.ingest import chunk_document
from routers.rag.mm_caption import clean_ocr_text, extract_caption, numbers_disagree

_OCR_TEXT_CAP = 2000  # chars; dedicated OCR reads exact text (e.g. every date
                      # in a dense timeline graphic) that a short prose caption
                      # would otherwise summarize away

MAX_PAGES = 8
_RENDER_ZOOM = 2.0          # fitz zoom factor (~144 DPI, since PDF base is 72 DPI) —
                            # higher than Document Intelligence's 1.2x preview renders
                            # since this feeds the vision cascade, not just a thumbnail
_MIN_VISUAL_AREA_RATIO = 0.02  # a raster image must cover ≥2% of the page area
                               # to count as "worth captioning" — filters small
                               # decorative marks (icons, small logos) that
                               # aren't actually a chart/photo/diagram.
                               # Was 0.05 until a real resume's "Soft Skills"
                               # donut infographic (labels baked into the raster
                               # image, invisible to get_text()) measured only
                               # ~2.96% of the page and was silently dropped
                               # entirely — neither extracted as text nor
                               # captioned. Confirmed decorative icons on the
                               # same page measure ~0.06%, so 0.02 sits with
                               # wide margin above real noise and below a real,
                               # content-bearing graphic.


def _render_page(page, zoom: float = _RENDER_ZOOM) -> str:
    import base64
    import fitz
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    return base64.b64encode(pix.tobytes("png")).decode()


def _norm_box(page, x0: float, y0: float, x1: float, y1: float) -> list[float]:
    """Page-relative [x, y, w, h], each 0-1 — resolution-independent so the
    frontend can draw it over a page thumbnail of any rendered size."""
    w, h = page.rect.width, page.rect.height
    return [round(x0 / w, 4), round(y0 / h, 4),
            round((x1 - x0) / w, 4), round((y1 - y0) / h, 4)]


def _visual_bbox(page) -> list[float] | None:
    """Bbox (normalized) of the largest raster image large enough to be an
    actual chart/photo/diagram — None if the page has nothing qualifying.
    Also doubles as "is this page visually dense" (a page is captioned only
    when this returns non-None) — even a text-heavy page (e.g. a resume with
    a text sidebar plus a timeline graphic) gets captioned, since get_text()
    extracts nothing from the image region. Deliberately checks ONLY
    get_images() (real embedded raster images), not get_drawings() (vector
    paths) — a plain color-fill rectangle used as a section-header
    banner/divider is a vector drawing that can easily exceed the area
    threshold while being pure decoration; real timeline/chart graphics come
    in as raster images. Observed live: a resume's solid-color "PERSONAL
    DETAILS" banner was triggering a "figure" caption that said "this is a
    text document, not a visual" — dropping get_drawings() removes that
    false positive."""
    try:
        page_area = page.rect.width * page.rect.height
        if page_area <= 0:
            return None

        best_bbox, best_area = None, 0.0
        for img in page.get_images(full=True):
            try:
                bbox = page.get_image_bbox(img)
            except Exception:
                continue
            if not bbox:
                continue
            area = bbox.width * bbox.height
            if area / page_area >= _MIN_VISUAL_AREA_RATIO and area > best_area:
                best_bbox, best_area = bbox, area

        if best_bbox is None:
            return None
        return _norm_box(page, best_bbox.x0, best_bbox.y0, best_bbox.x1, best_bbox.y1)
    except Exception:
        return None


def _caption_prompt() -> str:
    return (
        "This is a page from a document, shown because it appears to be a "
        "chart, diagram, photo, or other visual content rather than plain text. "
        "Write a factual 2-4 sentence description for someone who cannot see "
        "it: what type of visual it is, what it shows, and transcribe any "
        "axis labels, legend values, or numbers that are visible. "
        'Return JSON only: {"caption": "<your description>"}.'
    )


def _caption_page(b64: str) -> tuple[str, bool]:
    """Returns (chunk_text, number_mismatch) — mismatch flags when the
    caption and the OCR pass cite disjoint numbers for the same figure, a
    real sign one of the two misread a value rather than a generic caveat."""
    caption = extract_caption(_vision_cascade_raw(b64, _caption_prompt()), 500)
    ocr_md, _ = mistral_ocr_pages([b64])
    ocr_text = clean_ocr_text(ocr_md)[:_OCR_TEXT_CAP]
    mismatch = numbers_disagree(caption, ocr_text)
    if not ocr_text:
        return caption, False
    if not caption:
        return ocr_text, False
    return f"{caption}\n\nExact text from image (OCR):\n{ocr_text}", mismatch


# ── Per-page (streaming path) ───────────────────────────────────────────────────

def prepare_pdf(file_bytes: bytes):
    """Open the PDF. Returns (doc, n_pages)."""
    import fitz
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    n_pages = min(MAX_PAGES, len(doc))
    return doc, n_pages


def _table_markdown(rows: list[list]) -> str:
    lines: list[str] = []
    for j, row in enumerate(rows):
        cells = [str(c or "").strip().replace("|", " ") for c in row]
        lines.append("| " + " | ".join(cells) + " |")
        if j == 0:
            lines.append("|" + "|".join(["---"] * len(row)) + "|")
    return "\n".join(lines)


def process_page(doc, page_num: int, source: str) -> tuple[list[dict], str, dict]:
    """Extract chunks for ONE page. Returns (chunks, page_b64, page_summary).

    Tables are found here directly (page.find_tables(), same call
    extract_tables_markdown() used to make in a separate whole-doc pre-pass)
    so each table's own bbox is available right where its chunk is built —
    MMRAG-07 visual grounding for citations."""
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

    for tab in page.find_tables():
        rows = tab.extract()
        if not rows:
            continue
        # tab.bbox is a plain 4-tuple in some PyMuPDF versions, a Rect-like
        # object with .x0/.y0/.x1/.y1 in others — index access works for both.
        x0, y0, x1, y1 = tab.bbox[0], tab.bbox[1], tab.bbox[2], tab.bbox[3]
        page_chunks.append({"text": _table_markdown(rows), "source": source, "chunk_index": len(page_chunks),
                            "chunk_type": "table", "page": page_num,
                            "bbox": _norm_box(page, x0, y0, x1, y1)})
        page_summary["table"] += 1

    visual_bbox = _visual_bbox(page)
    if visual_bbox is not None:
        caption, mismatch = _caption_page(b64)
        if caption:
            chunk = {"text": caption, "source": source, "chunk_index": len(page_chunks),
                     "chunk_type": "figure", "page": page_num, "quality": blur_score(b64),
                     "bbox": visual_bbox}
            if mismatch:
                chunk["number_mismatch"] = True
            page_chunks.append(chunk)
            page_summary["figure"] = 1

    return page_chunks, b64, page_summary


# ── Whole-file (used by evaluate_mm.py, which doesn't need live progress) ──────

def build_multimodal_chunks(file_bytes: bytes, source: str,
                            progress_cb=None) -> tuple[list[dict], list[str], dict]:
    """Returns (chunks, page_images, chunk_summary). chunks carry chunk_type/page/bbox."""
    doc, n_pages = prepare_pdf(file_bytes)

    chunks: list[dict] = []
    page_images: list[str] = []
    summary = {"text": 0, "table": 0, "figure": 0}

    for page_num in range(1, n_pages + 1):
        if progress_cb:
            progress_cb({"step": "extract", "page": page_num, "pages": n_pages})
        page_chunks, b64, page_summary = process_page(doc, page_num, source)
        chunks.extend(page_chunks)
        page_images.append(b64)
        for k in summary:
            summary[k] += page_summary[k]

    doc.close()
    return chunks, page_images, summary
