"""PDF page extraction for multimodal RAG — text/table/figure chunking, split
into prepare-once + process-one-page so the SSE stream in mm_ingest.py can
yield a real "page X of N" progress event between pages, instead of one
opaque call that blocks until the whole document is done. Split out of
mm_ingest.py to stay under the project's file-length limit.
"""
from __future__ import annotations

import logging

from routers.document._vision import _vision_cascade_raw, mistral_ocr_pages
from routers.rag.blur import blur_score
from routers.rag.ingest import chunk_document
from routers.rag.mm_caption import (build_table_markdown, clean_ocr_text, extract_caption,
                                    extract_chart_data, numbers_disagree)

logger = logging.getLogger(__name__)

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


_REGION_OVERLAP_MERGE_RATIO = 0.5  # two raster images overlapping more than
                                    # this fraction of the smaller one's area
                                    # are the same real region (duplicate/
                                    # layered embedded images at the same
                                    # spot) — merged into one, not captioned twice
_MAX_REGIONS_PER_PAGE = 3           # bounds vision-call cost on a page with
                                    # many qualifying images
_CLUSTER_GAP_PT = 30.0              # max edge-to-edge gap between two
                                    # images for them to count as one visual
                                    # group (e.g. a chart with a column of
                                    # small skill icons right beside it, or
                                    # a row of small logos in a career
                                    # timeline) — small enough that unrelated
                                    # icons/bullets scattered far down a
                                    # page (typically 100+pt apart) never get
                                    # pulled together. Tuned against a real
                                    # resume: a donut chart and its adjacent
                                    # skill-icon column, clearly one section,
                                    # measured a 21pt real gap — 20pt missed
                                    # it, 30pt covers it with margin
_MIN_CLUSTER_SIZE = 3               # need at least this many small images
                                    # grouped together before treating the
                                    # group as one meaningful region — 2
                                    # nearby small icons could still just be
                                    # decoration, not a real graphic


def _rect_overlap_ratio(a, b) -> float:
    ix0, iy0 = max(a.x0, b.x0), max(a.y0, b.y0)
    ix1, iy1 = min(a.x1, b.x1), min(a.y1, b.y1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    smaller = min(a.width * a.height, b.width * b.height)
    return inter / smaller if smaller > 0 else 0.0


def _rect_gap(a, b) -> float:
    """Real edge-to-edge gap between two rects — 0 if they overlap on both
    axes. (An expand-one-side-then-check-intersects approach undercounts:
    expanding only `a` by `gap` and checking against raw `b` only actually
    tolerates a `gap`-sized separation, not `gap`-or-less as intended —
    caught live: a real 21pt gap wasn't merging under a 20pt threshold.)"""
    dx = max(a.x0 - b.x1, b.x0 - a.x1, 0.0)
    dy = max(a.y0 - b.y1, b.y0 - a.y1, 0.0)
    return max(dx, dy)


def _cluster_images(rects: list, gap: float) -> list[list]:
    """Union-find via pairwise proximity, not a fixed grid — handles
    irregular layouts: groups rects into connected components where any
    two members within `gap` of each other end up in the same cluster,
    including transitively through a chain of others."""
    clusters: list[list] = []
    for r in rects:
        target = next((c for c in clusters if any(_rect_gap(r, m) <= gap for m in c)), None)
        if target is not None:
            target.append(r)
        else:
            clusters.append([r])

    merged = True
    while merged:
        merged = False
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                if any(_rect_gap(a, b) <= gap for a in clusters[i] for b in clusters[j]):
                    clusters[i].extend(clusters[j])
                    del clusters[j]
                    merged = True
                    break
            if merged:
                break
    return clusters


def _visual_regions(page, max_regions: int = _MAX_REGIONS_PER_PAGE) -> list:
    """Distinct, meaningful visual regions on the page (real Rect objects),
    largest-first, capped at max_regions. A single unified proximity
    clustering pass over EVERY raster image on the page (not two separate
    passes for "big" vs. "small" images) — a qualifying big image and a
    small image sitting right next to it (e.g. a donut chart with a
    column of small skill icons beside it, part of the same visual) merge
    into ONE region, not two; a cluster of nearby small images with
    nothing large nearby (e.g. a career-timeline row of ~6 small company
    logos, each individually below _MIN_VISUAL_AREA_RATIO) still forms its
    own region if there are enough of them. Observed live: doing this as
    two separate passes (big images alone, small images alone) wrongly
    split a resume's donut chart and its adjacent skill-icon column into
    two separately-captioned regions, even though they're clearly one
    section — unifying the clustering fixed it, merging them back into one.
    A cluster qualifies as a region if it contains any single image
    ≥_MIN_VISUAL_AREA_RATIO on its own, OR has ≥_MIN_CLUSTER_SIZE members.

    Deliberately checks ONLY get_images() (real embedded raster images),
    not get_drawings() (vector paths) — a plain color-fill rectangle used
    as a section-header banner/divider is a vector drawing that can easily
    exceed the area threshold while being pure decoration; real
    chart/timeline graphics come in as raster images. Observed live: a
    resume's solid-color "PERSONAL DETAILS" banner was triggering a
    "figure" caption that said "this is a text document, not a visual" —
    dropping get_drawings() removes that false positive."""
    try:
        page_area = page.rect.width * page.rect.height
        if page_area <= 0:
            return []
        rects = []
        for img in page.get_images(full=True):
            try:
                bbox = page.get_image_bbox(img)
            except Exception:
                continue
            if bbox:
                rects.append(bbox)

        candidates = []
        for cluster in _cluster_images(rects, _CLUSTER_GAP_PT):
            has_big = any(r.width * r.height / page_area >= _MIN_VISUAL_AREA_RATIO for r in cluster)
            if not has_big and len(cluster) < _MIN_CLUSTER_SIZE:
                continue
            import fitz
            candidates.append(fitz.Rect(
                min(r.x0 for r in cluster), min(r.y0 for r in cluster),
                max(r.x1 for r in cluster), max(r.y1 for r in cluster),
            ))

        candidates.sort(key=lambda r: -(r.width * r.height))
        regions: list = []
        for c in candidates:
            if any(_rect_overlap_ratio(c, r) >= _REGION_OVERLAP_MERGE_RATIO for r in regions):
                continue
            regions.append(c)
            if len(regions) >= max_regions:
                break
        return regions
    except Exception as exc:
        logger.warning("Visual-region detection failed for page, treating as no regions: %s", exc)
        return []


def _crop_region_b64(page, rect, zoom: float = _RENDER_ZOOM) -> str:
    import base64
    import fitz
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, clip=rect)
    return base64.b64encode(pix.tobytes("png")).decode()


def _caption_prompt() -> str:
    return (
        "This is a page from a document, shown because it appears to be a "
        "chart, diagram, photo, or other visual content rather than plain text. "
        "Write a factual 2-4 sentence description for someone who cannot see "
        "it: what type of visual it is, what it shows, and transcribe any "
        "axis labels, legend values, or numbers that are visible. If this is "
        "a bar, line, or pie chart with genuinely identifiable numeric "
        "values — whether printed as data labels, or readable by judging bar "
        "heights/point positions against the axis scale — ALSO extract them "
        "as rows: one [category, value] pair per bar/point/slice. "
        'Return JSON only: {"caption": "<your description>", "chart_type": '
        '"bar"|"line"|"pie"|"none", "chart_data": [["<category>", "<value>"], '
        '...] (empty list if not a chart with extractable values)}.'
    )


def _caption_page(b64: str, scoped: bool = False) -> tuple[str, bool, tuple[str, list[list[str]]] | None]:
    """Returns (chunk_text, number_mismatch, chart) — mismatch flags when
    the caption and the OCR pass cite disjoint numbers for the same
    figure, a real sign one of the two misread a value rather than a
    generic caveat. chart is (chart_type, rows) when the vision model
    identified genuine extractable chart values (MMRAG-14), else None.

    scoped=True means b64 is a CROP of one visual, so caption and OCR
    describe the same thing and disagreeing numbers mean one of them
    misread. scoped=False means b64 is a whole page: the caption may
    describe the chart while the OCR is dominated by an unrelated table
    beside it, and disjoint numbers are then the normal case, not a
    misread. Only the scoped call can flag."""
    raw = _vision_cascade_raw(b64, _caption_prompt())
    caption = extract_caption(raw, 500)
    chart = extract_chart_data(raw)
    ocr_md, _ = mistral_ocr_pages([b64])
    ocr_text = clean_ocr_text(ocr_md)[:_OCR_TEXT_CAP]
    mismatch = numbers_disagree(caption, ocr_text) if scoped else False
    if not ocr_text:
        return caption, False, chart
    if not caption:
        return ocr_text, False, chart
    return f"{caption}\n\nExact text from image (OCR):\n{ocr_text}", mismatch, chart


# ── Per-page (streaming path) ───────────────────────────────────────────────────

def prepare_pdf(file_bytes: bytes):
    """Open the PDF. Returns (doc, n_pages)."""
    import fitz
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    n_pages = min(MAX_PAGES, len(doc))
    return doc, n_pages


def _chart_table_chunk(chart, source: str, page_num: int, bbox, chunk_index: int) -> dict:
    """MMRAG-14: a chart's extracted numeric values as their own 'table'
    chunk (not folded into the figure's prose text) — same chunk_type real
    PDF-extracted tables use, so it gets the exact same citation treatment
    for free: RagTableView.tsx's CSV download and mini bar-chart plot,
    with no frontend change needed to recognize this came from a chart
    rather than an actual in-document table."""
    chart_type, rows = chart
    table_md = build_table_markdown([["Category", "Value"], *rows])
    return {"text": f"Data extracted from a {chart_type} chart:\n\n{table_md}",
            "source": source, "chunk_index": chunk_index,
            "chunk_type": "table", "page": page_num, "bbox": bbox}


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
        page_chunks.append({"text": build_table_markdown(rows), "source": source, "chunk_index": len(page_chunks),
                            "chunk_type": "table", "page": page_num,
                            "bbox": _norm_box(page, x0, y0, x1, y1)})
        page_summary["table"] += 1

    regions = _visual_regions(page)
    if len(regions) >= 2:
        # MMRAG-13: 2+ distinct regions (e.g. a chart AND a separate photo
        # or logo) — caption each on its own cropped region instead of one
        # blended whole-page description.
        for rect in regions:
            region_b64 = _crop_region_b64(page, rect)
            caption, mismatch, chart = _caption_page(region_b64, scoped=True)
            if not caption:
                continue
            bbox = _norm_box(page, rect.x0, rect.y0, rect.x1, rect.y1)
            chunk = {"text": caption, "source": source, "chunk_index": len(page_chunks),
                     "chunk_type": "figure", "page": page_num, "quality": blur_score(region_b64),
                     "bbox": bbox}
            if mismatch:
                chunk["number_mismatch"] = True
            page_chunks.append(chunk)
            page_summary["figure"] += 1
            if chart:
                page_chunks.append(_chart_table_chunk(chart, source, page_num, bbox, len(page_chunks)))
                page_summary["table"] += 1
    elif len(regions) == 1:
        # Exactly one qualifying visual (whether a single standalone image
        # or one cluster of small ones, e.g. a timeline row with nothing
        # else competing for attention on the page) — caption the WHOLE
        # page, not a tight crop, so real surrounding context (a chart's
        # title sitting just outside its own raster bbox, or date labels
        # near a timeline) isn't lost. Unchanged from this feature's
        # original single-figure behavior.
        rect = regions[0]
        caption, mismatch, chart = _caption_page(b64)
        if caption:
            bbox = _norm_box(page, rect.x0, rect.y0, rect.x1, rect.y1)
            chunk = {"text": caption, "source": source, "chunk_index": len(page_chunks),
                     "chunk_type": "figure", "page": page_num, "quality": blur_score(b64),
                     "bbox": bbox}
            if mismatch:
                chunk["number_mismatch"] = True
            page_chunks.append(chunk)
            page_summary["figure"] = 1
            if chart:
                page_chunks.append(_chart_table_chunk(chart, source, page_num, bbox, len(page_chunks)))
                page_summary["table"] += 1

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
