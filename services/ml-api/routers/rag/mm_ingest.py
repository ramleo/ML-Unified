"""Multimodal RAG ingestion — PDFs with tables/figures, or standalone images,
→ typed chunks.

PDF page extraction lives in mm_pdf.py, standalone images in mm_image.py
(own modules — kept this file under the project's file-length limit); this
file owns the SSE endpoint/streaming orchestration and the ingestion cache.
Feeds the same chunk_document()/index_chunks() pipeline the plain-text RAG
upload uses — same Chroma collection, same hybrid retrieval, same citations.
"""
from __future__ import annotations

import json
import logging
import uuid as _uuid
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from routers.rag.ingest import index_chunks
from routers.rag.mm_csv import build_csv_chunks, looks_like_csv
from routers.rag.mm_image import build_image_chunk, looks_like_image
from routers.rag.mm_pdf import prepare_pdf, process_page
from routers.rag.mm_video import (close_video, generate_chapters, looks_like_video, prepare_video,
                                  process_frame, reduced_frame_count, transcribe_video)
from routers.rag.mm_audio import looks_like_audio, transcribe_audio_upload
from routers.rag.mm_revision import find_revision_candidate
from routers.rag.mm_ingest_cache import cache_get, cache_key, cache_put
from routers.rag.mm_ingest_payload import build_done_event

logger = logging.getLogger(__name__)

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=2)

MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB — video audio now chunks past
                                    # Groq Whisper's own 25MB-per-call cap
                                    # (see mm_video.py's _transcribe_long_audio),
                                    # so this ceiling is about upload/ingestion
                                    # cost, not a transcription hard limit


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

    # Keep the raw bytes (small in-memory cap, evicted on document removal)
    # so the frontend can play the actual video with click-to-seek, not
    # just show static frame thumbnails. Stored unconditionally here —
    # unlike the chunk cache below, this doesn't depend on a cache hit/miss,
    # since file_bytes is fresh from THIS upload call either way.
    if looks_like_video(filename, content_type) or looks_like_audio(filename, content_type):
        # store_video()/its /rag/video/{source} endpoint are generic byte+
        # content_type serving — reused as-is for audio playback, no new
        # storage/serving code needed.
        from routers.rag.mm_video_store import store_video
        store_video(source, file_bytes, content_type)

    # Cache only the EXPENSIVE-to-produce artifacts (vision captioning is the
    # slow/costly step). Indexing is always redone fresh per call — cheap,
    # and required so re-uploads land under the caller's own session_id
    # instead of replaying a stale one no query would ever match again.
    ckey = cache_key(file_bytes, embedding_mode)
    cached = cache_get(ckey)
    transcript_text = ""
    transcript_segments: list[dict] = []
    chapters: list[dict] = []
    if file_bytes[:4] == b"%PDF":
        file_type = "pdf"
    elif looks_like_csv(filename, content_type):
        file_type = "csv"
    elif looks_like_video(filename, content_type):
        file_type = "video"
    elif looks_like_audio(filename, content_type):
        file_type = "audio"
    elif looks_like_image(file_bytes, content_type):
        file_type = "image"
    else:
        file_type = "unknown"
    if cached:
        chunks = [dict(c, source=source) for c in cached["chunks"]]
        page_images = cached["page_images"]
        summary = cached["chunk_summary"]
        transcript_text = cached.get("transcript_text", "")
        transcript_segments = cached.get("transcript_segments", [])
        chapters = cached.get("chapters", [])
        yield _sse({"step": "extract", "status": "done", "chunk_summary": summary, "cached": True})
    else:
        loop = asyncio.get_event_loop()
        is_csv = file_bytes[:4] != b"%PDF" and looks_like_csv(filename, content_type)
        is_video = not is_csv and looks_like_video(filename, content_type)
        is_audio = not is_csv and not is_video and looks_like_audio(filename, content_type)
        is_image = (not is_csv and not is_video and not is_audio and file_bytes[:4] != b"%PDF"
                   and looks_like_image(file_bytes, content_type))

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
        elif is_audio:
            # One atomic call (like the image branch) — no sub-steps to
            # report, so the frontend shows an indeterminate progress bar.
            yield _sse({"step": "extract", "status": "running", "indeterminate": True})
            page_images = []
            try:
                chunks, summary, transcript_text, transcript_segments, chapters = await loop.run_in_executor(
                    _executor, lambda: transcribe_audio_upload(file_bytes, filename, source)
                )
            except Exception as exc:
                logger.error("Multimodal ingestion failed: %s", exc)
                yield _sse({"error": f"Failed to process file: {exc}"})
                return
        elif is_video:
            # Frame-by-frame, same "page X of N" progress pattern as the PDF
            # path — N here is the number of SAMPLED frames, not video frames.
            try:
                cap, tmp_path, n_frames, duration_s = await loop.run_in_executor(
                    _executor, lambda: prepare_video(file_bytes)
                )
            except Exception as exc:
                logger.error("Multimodal ingestion failed: %s", exc)
                yield _sse({"error": f"Failed to process file: {exc}"})
                return

            chunks = []
            page_images = []
            summary = {"text": 0, "table": 0, "figure": 0, "video": 0}
            try:
                # Audio transcript FIRST — for a talking-head video, this is
                # what actually carries the content. Whether it succeeds (and
                # how much it has to say) decides how many visual frames are
                # still worth sampling (see reduced_frame_count).
                yield _sse({"step": "transcribe", "status": "running"})
                transcript_chunks, transcript_count, transcript_text, transcript_segments = await loop.run_in_executor(
                    _executor, lambda: transcribe_video(tmp_path, source)
                )
                chunks.extend(transcript_chunks)
                summary["text"] += transcript_count
                yield _sse({"step": "transcribe", "status": "done", "chunks": transcript_count})

                if transcript_segments:
                    chapters = await loop.run_in_executor(
                        _executor, lambda: generate_chapters(transcript_segments)
                    )

                n_frames = reduced_frame_count(n_frames, transcript_chunks)

                yield _sse({"step": "extract", "status": "running", "page": 0, "pages": n_frames})
                for frame_idx in range(1, n_frames + 1):
                    frame_chunks, b64, page_summary = await loop.run_in_executor(
                        _executor, lambda fi=frame_idx: process_frame(cap, fi, n_frames, duration_s, source)
                    )
                    chunks.extend(frame_chunks)
                    if b64:
                        page_images.append(b64)
                    for k in summary:
                        summary[k] += page_summary[k]
                    yield _sse({"step": "extract", "status": "running", "page": frame_idx, "pages": n_frames})
            except Exception as exc:
                logger.error("Multimodal ingestion failed: %s", exc)
                yield _sse({"error": f"Failed to process file: {exc}"})
                return
            finally:
                await loop.run_in_executor(_executor, lambda: close_video(cap, tmp_path))
        else:
            # Page-by-page, awaiting each one individually so a real
            # "page X of N" event can be yielded between pages, instead of
            # one opaque executor call for the whole document.
            try:
                doc, n_pages = await loop.run_in_executor(
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
                        _executor, lambda pn=page_num: process_page(doc, pn, source)
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
            cache_put(ckey, {"chunks": chunks, "page_images": page_images, "chunk_summary": summary,
                                   "transcript_text": transcript_text, "transcript_segments": transcript_segments,
                                   "chapters": chapters})

    if not chunks:
        yield _sse({"error": "No extractable content found (text, tables, figures, a describable image, or speech)."})
        return

    from routers.rag.analytics import record_upload
    record_upload(file_type)

    yield _sse({"step": "embed", "status": "running"})
    uploaded = save_scope != "shared"
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        _executor,
        lambda: index_chunks(chunks, state, uploaded=uploaded,
                             session_id=session_id if uploaded else ""),
    )
    yield _sse({"step": "embed", "status": "done"})

    revision_candidate = find_revision_candidate(source, session_id, chunks, state) if uploaded else None

    if "clip" in embedding_mode:
        try:
            from routers.rag.mm_similar import index_figures_clip
            figure_pages = [(c["page"], page_images[c["page"] - 1]) for c in chunks
                            if c["chunk_type"] in ("figure", "image")]
            await loop.run_in_executor(_executor, lambda: index_figures_clip(source, figure_pages))
        except Exception as exc:
            logger.warning("CLIP figure indexing skipped: %s", exc)

    yield _sse(build_done_event(
        source=source, session_id=session_id, save_scope=save_scope, chunks=chunks,
        summary=summary, file_type=file_type, page_images=page_images,
        revision_candidate=revision_candidate, transcript_text=transcript_text,
        transcript_segments=transcript_segments, chapters=chapters,
    ))


@router.post("/mm-ingest")
async def mm_ingest(
    file: UploadFile = File(...),
    embedding_mode: str = Form(default="caption"),   # "caption" | "caption+clip"
    save_scope: str = Form(default="session"),        # "session" | "shared"
    session_id: str = Form(default=""),               # reuse the caller's chat session_id
):
    """Ingest a PDF (tables/figures), a standalone image (PNG/JPG/GIF/WEBP), a
    CSV, a short video (MP4/MOV/WEBM/AVI/MKV), or a standalone audio file
    (MP3/WAV/M4A/OGG/FLAC/AAC — transcribed the same way as a video's audio
    track, just with no frames to sample) into the multimodal RAG index.
    Streams progress as SSE; final event carries page_images for citation
    thumbnails (empty for CSV/audio — no page to render). Pass the same
    session_id your /rag/query calls use so the upload is retrievable from
    that chat session; a fresh one is generated if omitted."""
    file_bytes = await file.read()
    content_type = file.content_type or ""
    filename = file.filename or "document.pdf"
    if len(file_bytes) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 20 MB)")
    if not file_bytes or not (file_bytes[:4] == b"%PDF" or looks_like_image(file_bytes, content_type)
                              or looks_like_csv(filename, content_type)
                              or looks_like_video(filename, content_type)
                              or looks_like_audio(filename, content_type)):
        raise HTTPException(status_code=400,
                            detail="Only PDF, image (PNG/JPG/GIF/WEBP/BMP/TIFF), CSV, video "
                                   "(MP4/MOV/WEBM/AVI/MKV), or audio (MP3/WAV/M4A/OGG/FLAC/AAC) "
                                   "files are supported.")

    return StreamingResponse(
        _stream(file_bytes, filename, embedding_mode, save_scope, session_id, content_type),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
