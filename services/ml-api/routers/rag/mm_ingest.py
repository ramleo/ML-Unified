"""Multimodal RAG ingestion — PDFs with tables/figures, or standalone images,
→ typed chunks.

PDF page extraction lives in mm_pdf.py (own module — kept this file under the
project's file-length limit); this file owns the SSE endpoint/streaming
orchestration, the standalone-image path, and the ingestion cache.
Feeds the same chunk_document()/index_chunks() pipeline the plain-text RAG
upload uses — same Chroma collection, same hybrid retrieval, same citations.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid as _uuid
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from routers.document._vision import _vision_cascade_raw
from routers.rag.ingest import index_chunks
from routers.rag.mm_caption import extract_caption
from routers.rag.mm_pdf import prepare_pdf, process_page

logger = logging.getLogger(__name__)

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=2)

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB

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


# ── Standalone image captioning ─────────────────────────────────────────────────

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
        "Be factual, 3-4 sentences. "
        'Return JSON only: {"caption": "<your description>"}.'
    )


def _looks_like_image(file_bytes: bytes, content_type: str = "") -> bool:
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

    caption = extract_caption(_vision_cascade_raw(b64, _image_prompt()), 800)
    if not caption:
        # First attempt likely got cut off mid-reasoning before reaching the
        # JSON — one bounded retry with a terser ask that leaves less room
        # for a reasoning model to exhaust its token budget before answering.
        caption = extract_caption(_vision_cascade_raw(b64, _image_prompt(terse=True)), 400)

    summary = {"text": 0, "table": 0, "figure": 0, "image": 1 if caption else 0}
    if not caption:
        return [], [b64], summary

    # No embedded "[Image: source]" prefix — citations.py's build_system_prompt
    # already labels this chunk with source/page/type when building the LLM's
    # context, so baking it into the stored text would only be redundant
    # noise in the citation UI's raw-text preview.
    chunk = {"text": caption, "source": source, "chunk_index": 0,
             "chunk_type": "image", "page": 1}
    return [chunk], [b64], summary


# ── Standalone CSV ────────────────────────────────────────────────────────────

MAX_CSV_ROWS = 500   # bounds cost/latency the same way MAX_PAGES bounds PDFs
_CSV_CHUNK_ROWS = 50  # rows per chunk — keeps each chunk's embedding focused


def _looks_like_csv(filename: str, content_type: str) -> bool:
    return filename.lower().endswith(".csv") or content_type in ("text/csv", "application/csv")


def _rows_to_markdown(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(c).replace("|", " ") for c in row) + " |")
    return "\n".join(lines)


def build_csv_chunks(file_bytes: bytes, source: str) -> tuple[list[dict], list[str], dict]:
    """A standalone CSV upload — same 'table' chunk_type as a PDF's embedded
    tables, so it flows through the identical retrieval/citation path.
    No page_images (there's nothing to render as a thumbnail)."""
    import io
    import pandas as pd

    df = pd.read_csv(io.BytesIO(file_bytes))
    df = df.head(MAX_CSV_ROWS)
    header = [str(c) for c in df.columns]

    chunks: list[dict] = []
    for i in range(0, len(df), _CSV_CHUNK_ROWS):
        rows = df.iloc[i:i + _CSV_CHUNK_ROWS].astype(str).values.tolist()
        md = _rows_to_markdown(header, rows)
        chunks.append({"text": md, "source": source, "chunk_index": len(chunks),
                       "chunk_type": "table", "page": len(chunks) + 1})

    return chunks, [], {"text": 0, "table": len(chunks), "figure": 0}


# ── SSE endpoint ────────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _stream(file_bytes: bytes, filename: str, embedding_mode: str,
                  save_scope: str, session_id: str, content_type: str = "") -> AsyncGenerator[str, None]:
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
        loop = asyncio.get_event_loop()
        is_csv = file_bytes[:4] != b"%PDF" and _looks_like_csv(filename, content_type)
        is_image = not is_csv and file_bytes[:4] != b"%PDF" and _looks_like_image(file_bytes, content_type)

        if is_csv:
            yield _sse({"step": "extract", "status": "running", "indeterminate": True})
            try:
                chunks, page_images, summary = await loop.run_in_executor(
                    _executor, lambda: build_csv_chunks(file_bytes, source)
                )
            except Exception as exc:
                logger.error("Multimodal ingestion failed: %s", exc)
                yield _sse({"error": f"Failed to process file: {exc}"})
                return
        elif is_image:
            # One atomic vision call — no sub-steps to report, so the
            # frontend shows an indeterminate (not percentage) bar.
            yield _sse({"step": "extract", "status": "running", "indeterminate": True})
            try:
                chunks, page_images, summary = await loop.run_in_executor(
                    _executor, lambda: build_image_chunk(file_bytes, source)
                )
            except Exception as exc:
                logger.error("Multimodal ingestion failed: %s", exc)
                yield _sse({"error": f"Failed to process file: {exc}"})
                return
        else:
            # Page-by-page, awaiting each one individually so a real
            # "page X of N" event can be yielded between pages, instead of
            # one opaque executor call for the whole document.
            try:
                doc, n_pages, tables_by_page = await loop.run_in_executor(
                    _executor, lambda: prepare_pdf(file_bytes)
                )
            except Exception as exc:
                logger.error("Multimodal ingestion failed: %s", exc)
                yield _sse({"error": f"Failed to process file: {exc}"})
                return

            yield _sse({"step": "extract", "status": "running", "page": 0, "pages": n_pages})
            chunks = []
            page_images = []
            summary = {"text": 0, "table": 0, "figure": 0}
            try:
                for page_num in range(1, n_pages + 1):
                    page_chunks, b64, page_summary = await loop.run_in_executor(
                        _executor, lambda pn=page_num: process_page(doc, pn, tables_by_page, source)
                    )
                    chunks.extend(page_chunks)
                    page_images.append(b64)
                    for k in summary:
                        summary[k] += page_summary[k]
                    yield _sse({"step": "extract", "status": "running", "page": page_num, "pages": n_pages})
            except Exception as exc:
                logger.error("Multimodal ingestion failed: %s", exc)
                yield _sse({"error": f"Failed to process file: {exc}"})
                return
            finally:
                await loop.run_in_executor(_executor, doc.close)

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
    """Ingest a PDF (tables/figures), a standalone image (PNG/JPG/GIF/WEBP),
    or a CSV into the multimodal RAG index. Streams progress as SSE; final
    event carries page_images for citation thumbnails (empty for CSV — no
    page to render). Pass the same session_id your /rag/query calls use so
    the upload is retrievable from that chat session; a fresh one is
    generated if omitted."""
    file_bytes = await file.read()
    content_type = file.content_type or ""
    filename = file.filename or "document.pdf"
    if len(file_bytes) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")
    if not file_bytes or not (file_bytes[:4] == b"%PDF" or _looks_like_image(file_bytes, content_type)
                              or _looks_like_csv(filename, content_type)):
        raise HTTPException(status_code=400,
                            detail="Only PDF, image (PNG/JPG/GIF/WEBP/BMP/TIFF), or CSV files are supported.")

    return StreamingResponse(
        _stream(file_bytes, filename, embedding_mode, save_scope, session_id, content_type),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
