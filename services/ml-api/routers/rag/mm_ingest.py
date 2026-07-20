"""Multimodal RAG ingestion — PDFs with tables/figures → typed chunks.

Reuses document/_extract.py (table extraction) and document/_vision.py (the
provider-agnostic vision cascade) as library calls rather than duplicating
PDF/vision logic. Per page: text chunk (if substantial), table chunk(s) (via
find_tables()), figure chunk (AI caption, only for visually-dense pages).
Feeds the same chunk_document()/index_chunks() pipeline the plain-text RAG
upload uses — same Chroma collection, same hybrid retrieval, same citations.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid as _uuid
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from routers.document._extract import extract_tables_markdown
from routers.document._vision import _vision_cascade_raw
from routers.rag.ingest import chunk_document, index_chunks

logger = logging.getLogger(__name__)

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=2)

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_PAGES = 8
_DENSE_TEXT_THRESHOLD = 80  # chars; below this + has images/drawings → caption it
_RENDER_DPI = 2.0           # ~144 DPI — higher than Document Intelligence's preview
                            # renders since this feeds the vision cascade, not just a thumbnail

# ── Tiny ingestion cache (separate from document/_cache.py — own capacity) ────
_CACHE_TTL = 24 * 3600
_CACHE_MAX = 4
_cache: dict[str, tuple[float, dict]] = {}


def _cache_key(file_bytes: bytes, embedding_mode: str, save_scope: str) -> str:
    digest = hashlib.sha256(file_bytes).hexdigest()
    return f"{digest}:{embedding_mode}:{save_scope}"


def _cache_get(key: str) -> dict | None:
    item = _cache.get(key)
    if not item:
        return None
    ts, payload = item
    if time.time() - ts > _CACHE_TTL:
        del _cache[key]
        return None
    return payload


def _cache_put(key: str, payload: dict) -> None:
    _cache[key] = (time.time(), payload)
    while len(_cache) > _CACHE_MAX:
        oldest = min(_cache, key=lambda k: _cache[k][0])
        del _cache[oldest]


# ── Page rendering + density heuristic ────────────────────────────────────────

def _render_page(page, dpi: float = _RENDER_DPI) -> str:
    import base64
    import fitz
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    return base64.b64encode(pix.tobytes("png")).decode()


def _is_visually_dense(page, text: str) -> bool:
    if len(text.strip()) >= _DENSE_TEXT_THRESHOLD:
        return False
    try:
        return bool(page.get_images()) or bool(page.get_drawings())
    except Exception:
        return False


# ── Table markdown, split per page ────────────────────────────────────────────

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


# ── Figure captioning ──────────────────────────────────────────────────────────

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
    raw = _vision_cascade_raw(b64, _caption_prompt())
    if not raw.strip():
        return ""
    try:
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start >= 0 and end > start:
            return str(json.loads(raw[start:end]).get("caption", "")).strip()
    except Exception:
        pass
    return raw.strip()[:500]  # non-JSON fallback — still usable as a caption


# ── Chunk builder ──────────────────────────────────────────────────────────────

def build_multimodal_chunks(file_bytes: bytes, source: str,
                            progress_cb=None) -> tuple[list[dict], list[str], dict]:
    """Returns (chunks, page_images, chunk_summary). chunks carry chunk_type/page."""
    import fitz
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    n_pages = min(_MAX_PAGES, len(doc))

    tables_by_page = _split_tables_by_page(extract_tables_markdown(file_bytes, max_pages=n_pages))

    chunks: list[dict] = []
    page_images: list[str] = []
    summary = {"text": 0, "table": 0, "figure": 0}

    for i in range(n_pages):
        page = doc[i]
        page_num = i + 1
        text = page.get_text()
        b64 = _render_page(page)
        page_images.append(b64)

        if progress_cb:
            progress_cb({"step": "extract", "page": page_num, "pages": n_pages})

        if len(text.strip()) >= 20:
            for c in chunk_document(text, source):
                c["chunk_type"] = "text"
                c["page"] = page_num
                chunks.append(c)
            summary["text"] += 1

        for table_md in tables_by_page.get(page_num, []):
            chunks.append({"text": table_md, "source": source, "chunk_index": len(chunks),
                            "chunk_type": "table", "page": page_num})
            summary["table"] += 1

        if _is_visually_dense(page, text):
            if progress_cb:
                progress_cb({"step": "caption", "page": page_num, "pages": n_pages})
            caption = _caption_page(b64)
            if caption:
                chunks.append({"text": f"[Figure, page {page_num}] {caption}", "source": source,
                                "chunk_index": len(chunks), "chunk_type": "figure", "page": page_num})
                summary["figure"] += 1

    doc.close()
    return chunks, page_images, summary


# ── SSE endpoint ────────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _stream(file_bytes: bytes, filename: str, embedding_mode: str,
                  save_scope: str) -> AsyncGenerator[str, None]:
    import asyncio
    from routers.rag import get_rag_state

    cache_key = _cache_key(file_bytes, embedding_mode, save_scope)
    cached = _cache_get(cache_key)
    if cached:
        yield _sse({"step": "ingest", "status": "done", "cached": True, **cached})
        return

    try:
        state = get_rag_state()
    except RuntimeError as exc:
        yield _sse({"error": str(exc)})
        return

    # UUID suffix avoids the process-global "already uploaded" 409 that would
    # otherwise block repeated test/demo uploads of the same fixture file.
    source = f"user:{filename}:{_uuid.uuid4().hex[:8]}"
    session_id = str(_uuid.uuid4())

    yield _sse({"step": "extract", "status": "running"})
    loop = asyncio.get_event_loop()
    events: list[dict] = []
    try:
        chunks, page_images, summary = await loop.run_in_executor(
            _executor, lambda: build_multimodal_chunks(file_bytes, source, events.append)
        )
    except Exception as exc:
        logger.error("Multimodal ingestion failed: %s", exc)
        yield _sse({"error": f"Failed to process file: {exc}"})
        return
    yield _sse({"step": "extract", "status": "done", "chunk_summary": summary})

    if not chunks:
        yield _sse({"error": "No extractable content found (text, tables, or figures)."})
        return

    yield _sse({"step": "embed", "status": "running"})
    uploaded = save_scope != "shared"
    await loop.run_in_executor(
        _executor,
        lambda: index_chunks(chunks, state, uploaded=uploaded,
                             session_id=session_id if uploaded else ""),
    )
    yield _sse({"step": "embed", "status": "done"})

    if "clip" in embedding_mode:
        try:
            from routers.rag.mm_similar import index_figures_clip
            figure_pages = [(c["page"], page_images[c["page"] - 1]) for c in chunks
                            if c["chunk_type"] == "figure"]
            await loop.run_in_executor(_executor, lambda: index_figures_clip(source, figure_pages))
        except Exception as exc:
            logger.warning("CLIP figure indexing skipped: %s", exc)

    done = {
        "done": True,
        "source": source,
        "session_id": session_id,
        "save_scope": save_scope,
        "chunks_added": len(chunks),
        "chunk_summary": summary,
        "page_images": page_images,
    }
    _cache_put(cache_key, {k: v for k, v in done.items() if k != "done"})
    yield _sse(done)


@router.post("/mm-ingest")
async def mm_ingest(
    file: UploadFile = File(...),
    embedding_mode: str = Form(default="caption"),   # "caption" | "caption+clip"
    save_scope: str = Form(default="session"),        # "session" | "shared"
):
    """Ingest a PDF with tables/figures into the multimodal RAG index.
    Streams progress as SSE; final event carries page_images for citation thumbnails."""
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")
    if not file_bytes or file_bytes[:4] != b"%PDF":
        raise HTTPException(status_code=400, detail="Only PDF is supported for multimodal ingestion.")

    return StreamingResponse(
        _stream(file_bytes, file.filename or "document.pdf", embedding_mode, save_scope),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
