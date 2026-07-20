"""RAG package — singleton state + initialization."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = os.environ.get("DATA_DIR", "data")


@dataclass
class RagState:
    collection: object = None          # chromadb.Collection (MiniLM)
    embedding_fn: Optional[Callable] = None
    bm25: object = None                # BM25Okapi
    reranker: object = None            # sentence_transformers.CrossEncoder
    corpus_chunks: list[str] = field(default_factory=list)
    chunk_sources: list[str] = field(default_factory=list)
    chunk_meta: list[dict] = field(default_factory=list)  # parallel to corpus_chunks; {chunk_type, page, bbox}
    uploaded_sources: set[str] = field(default_factory=set)
    source_sessions: dict[str, str] = field(default_factory=dict)  # source → session_id
    initialized: bool = False
    # Jina v3 — lazy-loaded on first user request
    jina_collection: object = None
    jina_query_fn: Optional[Callable] = None
    jina_passage_fn: Optional[Callable] = None
    jina_ready: bool = False
    jina_loading: bool = False
    jina_error: Optional[str] = None
    init_error: Optional[str] = None
    # Semantic cache — list of {embedding, full_text, sources, chunks}
    semantic_cache: list[dict] = field(default_factory=list)


_state = RagState()


def initialize_jina(state: RagState) -> None:
    """Lazy-load Jina v3 and re-index all corpus chunks in a separate ChromaDB collection.

    Designed to run in a background thread. Sets state.jina_ready=True on success.
    """
    if state.jina_ready or state.jina_loading:
        return
    state.jina_loading = True
    try:
        from sentence_transformers import SentenceTransformer
        import chromadb

        # Use persistent volume for cache so model survives Space restarts.
        # Fall back to home dir if /data isn't mounted/writable.
        _persistent_cache = os.path.join(_DATA_DIR, "hf_cache")
        try:
            os.makedirs(_persistent_cache, exist_ok=True)
            os.environ["HF_HOME"] = _persistent_cache
            logger.info("Jina cache dir: %s", _persistent_cache)
        except Exception:
            logger.info("Jina cache dir: falling back to default (~/.cache)")

        logger.info("Loading jinaai/jina-embeddings-v3 (~570 MB) …")
        model = SentenceTransformer("jinaai/jina-embeddings-v3", trust_remote_code=True, device="cpu")
        state.jina_query_fn = lambda texts: model.encode(
            texts, task="retrieval.query", batch_size=16,
            show_progress_bar=False, convert_to_numpy=True,
        ).tolist()
        state.jina_passage_fn = lambda texts: model.encode(
            texts, task="retrieval.passage", batch_size=16,
            show_progress_bar=False, convert_to_numpy=True,
        ).tolist()
        persist_dir = os.path.join(_DATA_DIR, "chroma_db")
        client = chromadb.PersistentClient(path=persist_dir)
        try:
            client.delete_collection("rag_kb_jina")
        except Exception:
            pass
        state.jina_collection = client.create_collection(
            name="rag_kb_jina",
            metadata={"hnsw:space": "cosine"},
        )
        if state.corpus_chunks:
            logger.info("Re-indexing %d chunks with Jina v3 …", len(state.corpus_chunks))
            embeddings = state.jina_passage_fn(state.corpus_chunks)
            state.jina_collection.add(
                documents=state.corpus_chunks,
                embeddings=embeddings,
                ids=[f"jina_{i}" for i in range(len(state.corpus_chunks))],
                metadatas=[{
                    "source": src,
                    "uploaded": src in state.uploaded_sources,
                    "session_id": state.source_sessions.get(src, ""),
                    **{k: v for k, v in (state.chunk_meta[i] if i < len(state.chunk_meta) else {}).items()
                       if v is not None},
                } for i, src in enumerate(state.chunk_sources)],
            )
            logger.info("Jina collection ready — %d chunks indexed.", len(state.corpus_chunks))
        state.jina_ready = True
    except Exception as exc:
        logger.exception("Jina initialization failed: %s", exc)
        state.jina_error = str(exc)
    finally:
        state.jina_loading = False


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
        _initialize_rag_inner(kb_dir)
    except Exception as exc:
        logger.exception("initialize_rag failed: %s", exc)
        _state.init_error = str(exc)
        _state.initialized = True  # unblock health checks so error is visible


def _initialize_rag_inner(kb_dir: str) -> None:
    global _state

    try:
        import chromadb
        from sentence_transformers import SentenceTransformer, CrossEncoder
        from rank_bm25 import BM25Okapi
    except ImportError as exc:
        logger.error("RAG deps missing: %s — pip install sentence-transformers chromadb rank-bm25 pypdf", exc)
        _state.init_error = str(exc)
        _state.initialized = True
        return

    # ── Embedding model ────────────────────────────────────────────────────────
    logger.info("Loading SentenceTransformer all-MiniLM-L6-v2 …")
    model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    _state.embedding_fn = lambda texts: model.encode(
        texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True
    ).tolist()

    # ── Reranker (cross-encoder) ───────────────────────────────────────────────
    logger.info("Loading CrossEncoder ms-marco-MiniLM-L-12-v2 …")
    try:
        _state.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-12-v2", device="cpu")
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