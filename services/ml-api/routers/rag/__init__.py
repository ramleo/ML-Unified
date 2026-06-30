"""RAG package — singleton state + initialization."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class RagState:
    collection: object = None          # chromadb.Collection
    embedding_fn: Optional[Callable] = None
    bm25: object = None                # BM25Okapi
    reranker: object = None            # sentence_transformers.CrossEncoder
    corpus_chunks: list[str] = field(default_factory=list)
    chunk_sources: list[str] = field(default_factory=list)
    initialized: bool = False


_state = RagState()


def get_rag_state() -> RagState:
    if not _state.initialized:
        raise RuntimeError("RAG not initialized. Call initialize_rag() first.")
    return _state


def initialize_rag(kb_dir: str) -> None:
    """Initialize ChromaDB, SentenceTransformer, BM25, and index any existing KB docs.

    Safe to call from a background thread. Marks state.initialized=True on completion
    regardless of whether kb_dir exists — callers can always ingest later via /rag/ingest.
    """
    global _state

    try:
        import chromadb
        from sentence_transformers import SentenceTransformer, CrossEncoder
        from rank_bm25 import BM25Okapi
    except ImportError as exc:
        logger.error("RAG deps missing: %s — pip install sentence-transformers chromadb rank-bm25 pypdf", exc)
        _state.initialized = True
        return

    # ── Embedding model ────────────────────────────────────────────────────────
    logger.info("Loading SentenceTransformer all-MiniLM-L6-v2 …")
    model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    _state.embedding_fn = lambda texts: model.encode(
        texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True
    ).tolist()

    # ── Reranker (cross-encoder) ───────────────────────────────────────────────
    logger.info("Loading CrossEncoder ms-marco-MiniLM-L-6-v2 …")
    try:
        _state.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")
    except Exception as exc:
        logger.warning("Reranker load failed, falling back to RRF-only ranking: %s", exc)
        _state.reranker = None

    # ── ChromaDB ───────────────────────────────────────────────────────────────
    persist_dir = "data/chroma_db"
    os.makedirs(persist_dir, exist_ok=True)
    client = chromadb.PersistentClient(path=persist_dir)
    _state.collection = client.get_or_create_collection(
        name="rag_kb",
        metadata={"hnsw:space": "cosine"},
    )

    # ── Index existing KB documents ────────────────────────────────────────────
    if not os.path.isdir(kb_dir):
        logger.warning("KB dir '%s' not found — starting with empty index.", kb_dir)
    else:
        try:
            from routers.rag.ingest import load_kb_documents, chunk_document, index_chunks

            docs = load_kb_documents(kb_dir)
            logger.info("Found %d documents in '%s'", len(docs), kb_dir)

            chunks: list[dict] = []
            for doc in docs:
                chunks.extend(chunk_document(doc["text"], doc["source"]))

            if chunks:
                index_chunks(chunks, _state)
                logger.info("Indexed %d chunks from KB dir.", len(chunks))
            else:
                logger.info("No chunks produced from KB dir.")
        except Exception as exc:
            logger.exception("Failed to index KB dir: %s", exc)

    # ── Ensure BM25 is initialized (even if corpus is empty) ──────────────────
    if _state.bm25 is None:
        _state.bm25 = BM25Okapi([[""]])  # dummy so it's never None

    _state.initialized = True
    logger.info(
        "RAG initialized — %d chunks in corpus, %d in ChromaDB.",
        len(_state.corpus_chunks),
        _state.collection.count(),
    )