"""Vision-native image retrieval add-on (MMRAG-24), Cohere Embed v4.

Every figure/image chunk in this tool is normally only searchable through its
AI-generated caption (see mm_pdf.py/mm_image.py) — that caption is what gets
embedded (MiniLM) and is what the cross-encoder reranker/citation UI read.
This module ADDITIONALLY embeds the raw image itself via Cohere's multimodal
Embed v4 API into a separate Chroma collection, purely as a third retrieval
signal fused in at query time (see retrieve.py:hybrid_retrieve) alongside the
existing dense+BM25 lists — never a replacement for the caption path. This
mirrors mm_similar.py's CLIP side-index pattern (separate collection, own
embedding space, dense_retrieve never touches it directly), except the
embedding here comes from an API call, not a locally hosted model, since this
Space has no GPU/torch to run ColPali-style models directly.

Gated entirely on a server-side COHERE_API_KEY (no BYOK — a user's chosen chat
provider has no fixed relationship to whether they'd want to pay for Cohere
embeddings too). Every public function here is best-effort: with no key, or
on any request failure, it silently no-ops rather than blocking ingestion or
retrieval.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "rag_mm_cohere_kb"
_EMBED_URL = "https://api.cohere.ai/v2/embed"
_MODEL = "embed-v4.0"
# Conservative per-call cap — Cohere's v2 embed endpoint documents a 96-input
# limit per request regardless of input_type; batch defensively rather than
# assume unlimited.
_MAX_BATCH = 96

_collection = None
_lock = threading.Lock()


def _resolve_key() -> str:
    return os.environ.get("COHERE_API_KEY", "")


def _ensure_loaded() -> bool:
    """Lazy Chroma collection handle — most sessions never have a Cohere key."""
    global _collection
    if _collection is not None:
        return True
    with _lock:
        if _collection is not None:
            return True
        if not _resolve_key():
            return False
        try:
            import chromadb

            client = chromadb.PersistentClient(path="data/chroma_db")
            _collection = client.get_or_create_collection(
                name=_COLLECTION_NAME, metadata={"hnsw:space": "cosine"},
            )
            return True
        except Exception as exc:
            logger.warning("Cohere vision collection init failed — feature disabled: %s", exc)
            return False


def _cohere_embed(inputs: list[str], input_type: str, key: str) -> list[list[float]]:
    """Raw REST call — no cohere SDK, same no-dependency style as
    llm.py:stream_cohere. input_type is "image" (base64 data-URI strings) or
    "search_query" (plain text)."""
    import httpx

    vectors: list[list[float]] = []
    for i in range(0, len(inputs), _MAX_BATCH):
        batch = inputs[i : i + _MAX_BATCH]
        payload = {
            "model": _MODEL,
            "input_type": input_type,
            "embedding_types": ["float"],
            **({"images": batch} if input_type == "image" else {"texts": batch}),
        }
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                _EMBED_URL,
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        vectors.extend(data["embeddings"]["float"])
    return vectors


def index_figures_vision(source: str, session_id: str, figure_pages: list[tuple[int, str]]) -> None:
    """Encode and index each (page, base64 PNG) figure/image. Best-effort —
    failures here never block the main caption-based ingestion path."""
    if not figure_pages or not _ensure_loaded():
        return
    key = _resolve_key()
    if not key:
        return

    pages = [p for p, _ in figure_pages]
    b64s = [f"data:image/png;base64,{b64}" for _, b64 in figure_pages]
    try:
        embeddings = _cohere_embed(b64s, "image", key)
    except Exception as exc:
        logger.warning("Cohere vision indexing skipped for %s: %s", source, exc)
        return

    ids = [f"{source}:p{page}" for page in pages]
    metas = [{"source": source, "page": page, "session_id": session_id} for page in pages]
    _collection.upsert(
        ids=ids, embeddings=embeddings,
        documents=[f"page {p}" for p in pages], metadatas=metas,
    )
    logger.info("Indexed %d image(s) for vision retrieval (%s).", len(pages), source)


def vision_retrieve(query: str, state, session_id: str, top_k: int = 20) -> list[dict]:
    """Query the Cohere image-vector collection, then join each hit back to
    its real caption/text chunk in the main collection so it can be returned
    in the exact dense_retrieve() shape — no downstream code (fusion, rerank,
    citations) needs to know this hit came from image similarity, not text.

    Returns [] (never raises) with no key, an empty collection, or any
    request failure — this is a pure retrieval-quality add-on.
    """
    if not query or not _ensure_loaded():
        return []
    key = _resolve_key()
    if not key or _collection.count() == 0:
        return []

    try:
        query_vec = _cohere_embed([query], "search_query", key)[0]
    except Exception as exc:
        logger.warning("Cohere vision query embed failed: %s", exc)
        return []

    n_results = min(top_k, _collection.count())
    hits = _collection.query(
        query_embeddings=[query_vec], n_results=n_results,
        where={"session_id": session_id}, include=["metadatas", "distances"],
    )
    metas = hits.get("metadatas", [[]])[0]
    dists = hits.get("distances", [[]])[0]

    results: list[dict] = []
    for meta, dist in zip(metas, dists):
        source, page = meta.get("source"), meta.get("page")
        record = state.collection.get(
            where={"$and": [{"source": source}, {"page": page}, {"session_id": session_id}]},
            limit=1, include=["documents", "metadatas"],
        )
        if not record.get("ids"):
            continue  # chunk since removed — nothing to join to
        doc = record["documents"][0]
        rmeta = record["metadatas"][0]
        rid = record["ids"][0]
        results.append({
            "text": doc,
            "source": rmeta.get("source", ""),
            "score": float(1.0 - dist),
            "id": rid,
            "uploaded": bool(rmeta.get("uploaded", False)),
            "chunk_type": rmeta.get("chunk_type"),
            "page": rmeta.get("page"),
            "timestamp_s": rmeta.get("timestamp_s"),
            "bbox": rmeta.get("bbox"),
            "objects": rmeta.get("objects"),
            "number_mismatch": rmeta.get("number_mismatch"),
            "pii_types": rmeta.get("pii_types"),
            "blurry": rmeta.get("blurry"),
            "entities": rmeta.get("entities"),
        })
    return results
