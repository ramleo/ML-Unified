"""RAG ingest — KB loading, chunking, indexing, and /ingest endpoint."""
from __future__ import annotations

import logging
import os
import re
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from routers.rag.text import tokenize

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Supported extensions ───────────────────────────────────────────────────────
_TEXT_EXTS = {".md", ".txt"}
_ALL_EXTS = _TEXT_EXTS | {".pdf"}


# ── Document loading ───────────────────────────────────────────────────────────

def load_kb_documents(kb_dir: str) -> list[dict]:
    """Walk kb_dir and read all .md / .txt files.

    Returns a list of dicts: {text: str, source: str}.
    """
    docs: list[dict] = []
    if not os.path.isdir(kb_dir):
        logger.warning("load_kb_documents: directory not found: %s", kb_dir)
        return docs

    for root, _, files in os.walk(kb_dir):
        for fname in sorted(files):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _TEXT_EXTS:
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, encoding="utf-8", errors="replace") as f:
                    text = f.read().strip()
                if text:
                    docs.append({"text": text, "source": fname})
            except Exception as exc:
                logger.warning("Skipping %s: %s", fpath, exc)

    logger.info("load_kb_documents: loaded %d documents from %s", len(docs), kb_dir)
    return docs


# ── Chunking ───────────────────────────────────────────────────────────────────

def chunk_document(
    text: str,
    source: str,
    chunk_size: int = 450,
    overlap: int = 45,
) -> list[dict]:
    """Split text into word-based overlapping chunks.

    Returns list of dicts: {text, source, chunk_index}.
    """
    words = text.split()
    if not words:
        return []

    chunks: list[dict] = []
    start = 0
    idx = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_text = " ".join(words[start:end]).strip()
        if chunk_text:
            chunks.append({
                "text": chunk_text,
                "source": source,
                "chunk_index": idx,
            })
        idx += 1
        if end >= len(words):
            break
        start = end - overlap  # slide back by overlap

    return chunks


# ── Indexing ───────────────────────────────────────────────────────────────────

def _rebuild_bm25(state) -> None:
    from rank_bm25 import BM25Okapi
    tokenized = [tokenize(t) for t in state.corpus_chunks] or [[""]]
    state.bm25 = BM25Okapi(tokenized)


def index_chunks(chunks: list[dict], state, uploaded: bool = False) -> None:
    """Embed chunks, add to ChromaDB collection, rebuild BM25 index in-place.

    uploaded=True tags chunks as user-uploaded (deletable via /rag/uploads);
    pre-seeded KB docs indexed at startup leave this False so they can't be
    removed through the same path.
    """
    if not chunks:
        return

    texts = [c["text"] for c in chunks]
    sources = [c["source"] for c in chunks]
    ids = [str(uuid.uuid4()) for _ in chunks]

    # Embed
    embeddings = state.embedding_fn(texts)

    # Add to ChromaDB (batch to avoid large payloads)
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        state.collection.add(
            ids=ids[i : i + batch_size],
            embeddings=embeddings[i : i + batch_size],
            documents=texts[i : i + batch_size],
            metadatas=[{"source": s, "uploaded": uploaded} for s in sources[i : i + batch_size]],
        )

    # Extend in-memory corpus
    state.corpus_chunks.extend(texts)
    state.chunk_sources.extend(sources)
    if uploaded:
        state.uploaded_sources.update(sources)

    _rebuild_bm25(state)

    logger.info("index_chunks: added %d chunks; corpus now %d", len(chunks), len(state.corpus_chunks))


def delete_source(source: str, state) -> int:
    """Remove all chunks for a given uploaded source from ChromaDB + BM25 corpus.

    Returns the number of chunks removed. Only intended for sources in
    state.uploaded_sources — callers should check membership before calling.
    """
    state.collection.delete(where={"source": source})

    keep_idx = [i for i, s in enumerate(state.chunk_sources) if s != source]
    removed = len(state.chunk_sources) - len(keep_idx)
    state.corpus_chunks = [state.corpus_chunks[i] for i in keep_idx]
    state.chunk_sources = [state.chunk_sources[i] for i in keep_idx]
    state.uploaded_sources.discard(source)

    _rebuild_bm25(state)

    logger.info("delete_source: removed %d chunks for '%s'; corpus now %d", removed, source, len(state.corpus_chunks))
    return removed


# ── /ingest endpoint ───────────────────────────────────────────────────────────

def _extract_pdf_text(data: bytes) -> str:
    """Extract text from PDF bytes using pypdf."""
    import io
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n".join(pages)


@router.post("/ingest")
async def ingest_document(file: UploadFile = File(...)) -> JSONResponse:
    """Upload a .md, .txt, or .pdf file and index its contents."""
    from routers.rag import get_rag_state

    fname = file.filename or ""
    ext = os.path.splitext(fname)[1].lower()

    if ext not in _ALL_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(_ALL_EXTS)}",
        )

    data = await file.read()

    if ext == ".pdf":
        try:
            text = _extract_pdf_text(data)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"PDF parse error: {exc}") from exc
    else:
        try:
            text = data.decode("utf-8", errors="replace").strip()
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Decode error: {exc}") from exc

    if not text.strip():
        raise HTTPException(status_code=422, detail="File is empty or contains no extractable text.")

    try:
        state = get_rag_state()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if fname in state.uploaded_sources:
        raise HTTPException(
            status_code=409,
            detail=f"'{fname}' is already uploaded. Remove it first (manage documents) before re-uploading.",
        )

    chunks = chunk_document(text, source=fname)
    index_chunks(chunks, state, uploaded=True)

    return JSONResponse({"status": "ok", "chunks_added": len(chunks), "source": fname})


# ── Manage uploaded documents ───────────────────────────────────────────────────

@router.get("/uploads")
def list_uploads() -> JSONResponse:
    """List user-uploaded document filenames (excludes the pre-seeded KB)."""
    from routers.rag import get_rag_state

    try:
        state = get_rag_state()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return JSONResponse({"sources": sorted(state.uploaded_sources)})


@router.delete("/uploads/{source}")
def delete_upload(source: str) -> JSONResponse:
    """Remove a previously uploaded document and its chunks from the knowledge base."""
    from routers.rag import get_rag_state

    try:
        state = get_rag_state()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if source not in state.uploaded_sources:
        raise HTTPException(status_code=404, detail=f"No uploaded document named '{source}'.")

    removed = delete_source(source, state)
    return JSONResponse({"status": "ok", "removed": removed, "source": source})
