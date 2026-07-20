"""Optional CLIP image-similarity add-on for multimodal RAG figures.

Isolated from the Q&A path entirely: figure chunks always get an AI caption
that's embedded through the normal text pipeline (see mm_ingest.py) — that's
what answers chat questions. This module ADDITIONALLY encodes figure images
with sentence-transformers' clip-ViT-B-32 (same library already a dependency
for MiniLM/Jina — no new package) into a separate collection, purely to power
a "find visually similar figures" button. Never read by rag/query.py.
"""
from __future__ import annotations

import base64
import logging
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()

_model = None
_collection = None
_lock = threading.Lock()
_load_error: Optional[str] = None


def _ensure_loaded() -> bool:
    """Lazy-load CLIP on first use — most sessions never opt into this."""
    global _model, _collection, _load_error
    if _model is not None and _collection is not None:
        return True
    with _lock:
        if _model is not None and _collection is not None:
            return True
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            logger.info("Loading clip-ViT-B-32 (~350 MB) for figure similarity …")
            _model = SentenceTransformer("clip-ViT-B-32", device="cpu")
            client = chromadb.PersistentClient(path="data/chroma_db")
            _collection = client.get_or_create_collection(
                name="rag_mm_image_kb", metadata={"hnsw:space": "cosine"},
            )
            return True
        except Exception as exc:
            logger.warning("CLIP load failed — similarity feature disabled: %s", exc)
            _load_error = str(exc)
            return False


def index_figures_clip(source: str, figure_pages: list[tuple[int, str]]) -> None:
    """Encode and index each (page, base64 PNG) figure image. Best-effort —
    failures here never block the main caption-based ingestion path."""
    if not figure_pages or not _ensure_loaded():
        return
    from PIL import Image
    import io

    images, ids, metas = [], [], []
    for page, b64 in figure_pages:
        try:
            img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
            images.append(img)
            ids.append(f"{source}:p{page}")
            metas.append({"source": source, "page": page})
        except Exception as exc:
            logger.warning("Skipping figure page %d for CLIP indexing: %s", page, exc)

    if not images:
        return
    embeddings = _model.encode(images, batch_size=8, show_progress_bar=False,
                               convert_to_numpy=True).tolist()
    _collection.add(ids=ids, embeddings=embeddings,
                    documents=[f"figure page {m['page']}" for m in metas], metadatas=metas)
    logger.info("Indexed %d figure image(s) for CLIP similarity (%s).", len(images), source)


@router.get("/mm-similar-figures")
def similar_figures(source: str, page: int, top_k: int = 4):
    """Find figures visually similar to the one at (source, page). Returns an
    empty list (not an error) if CLIP was never opted into for this document."""
    if not _ensure_loaded() or _collection is None:
        return {"results": [], "available": False}

    chunk_id = f"{source}:p{page}"
    existing = _collection.get(ids=[chunk_id], include=["embeddings"])
    embeddings = existing.get("embeddings")
    if embeddings is None or len(embeddings) == 0:
        raise HTTPException(status_code=404, detail="No indexed figure at this source/page.")

    hits = _collection.query(
        query_embeddings=[embeddings[0]], n_results=top_k + 1,
        include=["metadatas", "distances"],
    )
    results = []
    for meta, dist, hid in zip(hits.get("metadatas", [[]])[0], hits.get("distances", [[]])[0],
                               hits.get("ids", [[]])[0]):
        if hid == chunk_id:
            continue
        results.append({"source": meta.get("source"), "page": meta.get("page"),
                        "similarity": round(1.0 - dist, 4)})
    return {"results": results[:top_k], "available": True}
