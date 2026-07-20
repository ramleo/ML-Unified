"""Multimodal RAG ingestion — PDFs with tables/figures, or standalone images,
→ typed chunks.

Reuses document/_extract.py (table extraction) and document/_vision.py (the
provider-agnostic vision cascade) as library calls rather than duplicating
PDF/vision logic. Per PDF page: text chunk (if substantial), table chunk(s)
(via find_tables()), figure chunk (AI caption, only for visually-dense
pages). A standalone image upload gets one "image" chunk_type — the same
vision cascade, described thoroughly rather than as a document page's figure.
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


def _cache_key(file_bytes: bytes, embedding_mode: str) -> str:
    digest = hashlib.sha256(file_bytes).hexdigest()
    return f"{digest}:{embedding_mode}"


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


def _extract_caption(raw: str, fallback_len: int) -> str:
    """Pull {"caption": "..."} out of a vision response. Falls back to the raw
    text whenever JSON parsing fails OR succeeds without a usable caption —
    a valid-but-differently-shaped JSON response should not discard an
    otherwise-good description."""
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


def _caption_page(b64: str) -> str:
    return _extract_caption(_vision_cascade_raw(b64, _caption_prompt()), 500)


def _image_prompt() -> str:
    return (
        "Describe this image thoroughly for someone who cannot see it. Cover: "
        "what the main subject(s) are, any people/objects/animals and what "
        "they're doing, the setting or background, colors, and any visible "
        "text, numbers, or signage — transcribe text exactly as shown. If it "
        "is a chart, diagram, or screenshot, describe its data/content in "
        "detail rather than just its visual style. Be factual, 4-6 sentences. "
        'Return JSON only: {"caption": "<your description>"}.'
    )


def _looks_like_image(file_bytes: bytes) -> bool:
    sigs = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF")  # PNG, JPEG, GIF, WEBP(RIFF)
    return any(file_bytes.startswith(s) for s in sigs)


def build_image_chunk(file_bytes: bytes, source: str) -> tuple[list[dict], list[str], dict]:
    """A standalone image upload — one 'image' chunk_type, described thoroughly
    (not the terser 'figure on a document page' framing used for PDF pages)."""
    from PIL import Image
    import io, base64

    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()

    caption = _extract_caption(_vision_cascade_raw(b64, _image_prompt()), 800)

    summary = {"text": 0, "table": 0, "figure": 0, "image": 1 if caption else 0}
    if not caption:
        return [], [b64], summary

    chunk = {"text": f"[Image: {source}] {caption}", "source": source, "chunk_index": 0,
             "chunk_type": "image", "page": 1}
    return [chunk], [b64], summary


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
                  save_scope: str, session_id: str) -> AsyncGenerator[str, None]:
    import asyncio
    from routers.rag import get_rag_state

    try:
        state = get_rag_state()
    except RuntimeError as exc:
        yield _sse({"error": str(exc)})
        return

    # UUID suffix avoids the process-global "already uploaded" 409 that would
    # otherwise block repeated test/demo uploads of the same fixture file.
    # Minted fresh on every call — even a cache hit — so two different chat
    # sessions uploading the same bytes never collide over one source string.
    source = f"user:{filename}:{_uuid.uuid4().hex[:8]}"
    if not session_id:
        session_id = str(_uuid.uuid4())

    # Cache only the EXPENSIVE-to-produce artifacts (vision captioning is the
    # slow/costly step). Indexing is always redone fresh per call — cheap,
    # and required so re-uploads land under the caller's own session_id
    # instead of replaying a stale one no query would ever match again.
    cache_key = _cache_key(file_bytes, embedding_mode)
    cached = _cache_get(cache_key)
    if cached:
        chunks = [dict(c, source=source) for c in cached["chunks"]]
        page_images = cached["page_images"]
        summary = cached["chunk_summary"]
        yield _sse({"step": "extract", "status": "done", "chunk_summary": summary, "cached": True})
    else:
        yield _sse({"step": "extract", "status": "running"})
        loop = asyncio.get_event_loop()
        is_image = _looks_like_image(file_bytes)
        events: list[dict] = []
        try:
            if is_image:
                chunks, page_images, summary = await loop.run_in_executor(
                    _executor, lambda: build_image_chunk(file_bytes, source)
                )
            else:
                chunks, page_images, summary = await loop.run_in_executor(
                    _executor, lambda: build_multimodal_chunks(file_bytes, source, events.append)
                )
        except Exception as exc:
            logger.error("Multimodal ingestion failed: %s", exc)
            yield _sse({"error": f"Failed to process file: {exc}"})
            return
        yield _sse({"step": "extract", "status": "done", "chunk_summary": summary})
        if chunks:
            _cache_put(cache_key, {"chunks": chunks, "page_images": page_images, "chunk_summary": summary})

    if not chunks:
        yield _sse({"error": "No extractable content found (text, tables, figures, or a describable image)."})
        return

    yield _sse({"step": "embed", "status": "running"})
    uploaded = save_scope != "shared"
    loop = asyncio.get_event_loop()
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
                            if c["chunk_type"] in ("figure", "image")]
            await loop.run_in_executor(_executor, lambda: index_figures_clip(source, figure_pages))
        except Exception as exc:
            logger.warning("CLIP figure indexing skipped: %s", exc)

    yield _sse({
        "done": True,
        "source": source,
        "session_id": session_id,
        "save_scope": save_scope,
        "chunks_added": len(chunks),
        "chunk_summary": summary,
        "page_images": page_images,
    })


@router.post("/mm-ingest")
async def mm_ingest(
    file: UploadFile = File(...),
    embedding_mode: str = Form(default="caption"),   # "caption" | "caption+clip"
    save_scope: str = Form(default="session"),        # "session" | "shared"
    session_id: str = Form(default=""),               # reuse the caller's chat session_id
):
    """Ingest a PDF (tables/figures) or a standalone image (PNG/JPG/GIF/WEBP)
    into the multimodal RAG index. Streams progress as SSE; final event
    carries page_images for citation thumbnails. Pass the same session_id
    your /rag/query calls use so the upload is retrievable from that chat
    session; a fresh one is generated if omitted."""
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")
    if not file_bytes or not (file_bytes[:4] == b"%PDF" or _looks_like_image(file_bytes)):
        raise HTTPException(status_code=400,
                            detail="Only PDF or image files (PNG/JPG/GIF/WEBP) are supported.")

    return StreamingResponse(
        _stream(file_bytes, file.filename or "document.pdf", embedding_mode, save_scope, session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
