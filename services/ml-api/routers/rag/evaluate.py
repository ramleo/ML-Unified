"""RAG evaluation — POST /rag/evaluate endpoint.

Computes retrieval and generation quality metrics without external deps:
  context_relevance  — avg cosine(embed(question), embed(chunk)) for retrieved chunks
  answer_coverage    — keyword recall of answer against ground_truth
  faithfulness_proxy — cosine(embed(answer), mean(embed(top-4 chunks)))

All metrics are in [0, 1]. Higher is better.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import numpy as np
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from routers.rag import get_rag_state
from routers.rag.retrieve import hybrid_retrieve, embed_query
from routers.rag.rerank import rerank
from routers.rag.llm import complete
from routers.rag.text import tokenize

logger = logging.getLogger(__name__)
router = APIRouter()

_DEFAULT_PROVIDER = "groq"
_DEFAULT_MODEL = "llama-3.3-70b-versatile"
_ENV_KEYS = {
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "cohere": "COHERE_API_KEY",
}


# ── Request schema ─────────────────────────────────────────────────────────────

class QAPair(BaseModel):
    question: str
    ground_truth: str


class EvalRequest(BaseModel):
    qa_pairs: list[QAPair]
    provider: str = _DEFAULT_PROVIDER
    model: str = _DEFAULT_MODEL
    user_key: Optional[str] = None
    generate_answers: bool = True


# ── Metric helpers ─────────────────────────────────────────────────────────────

def _cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom > 0 else 0.0


def _keyword_recall(answer: str, ground_truth: str) -> float:
    """Fraction of ground_truth tokens that appear in the answer (case-insensitive)."""
    gt_tokens = set(tokenize(ground_truth.lower()))
    ans_tokens = set(tokenize(answer.lower()))
    if not gt_tokens:
        return 1.0
    return len(gt_tokens & ans_tokens) / len(gt_tokens)


def _context_relevance(question: str, chunks: list[dict], state) -> float:
    """Avg cosine similarity between question embedding and each retrieved chunk."""
    if not chunks:
        return 0.0
    q_emb = embed_query(question, state)
    sims = [_cosine(q_emb, state.embedding_fn([c["text"]])[0]) for c in chunks]
    return float(np.mean(sims))


def _faithfulness_proxy(answer: str, chunks: list[dict], state) -> float:
    """Cosine similarity between answer embedding and mean of top-4 chunk embeddings."""
    if not answer or not chunks:
        return 0.0
    ans_emb = state.embedding_fn([answer])[0]
    ctx_embs = state.embedding_fn([c["text"] for c in chunks[:4]])
    ctx_mean = np.mean(ctx_embs, axis=0).tolist()
    return _cosine(ans_emb, ctx_mean)


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post("/evaluate")
def rag_evaluate(req: EvalRequest) -> JSONResponse:
    """Evaluate retrieval + generation quality on held-out QA pairs.

    Returns per-question metrics and aggregate averages.
    Set generate_answers=false to skip LLM calls and measure retrieval only.
    """
    try:
        state = get_rag_state()
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)

    if not req.qa_pairs:
        return JSONResponse({"error": "qa_pairs must not be empty."}, status_code=400)

    provider = req.provider.lower()
    key = req.user_key or os.environ.get(_ENV_KEYS.get(provider, ""), "")

    if req.generate_answers and not key:
        return JSONResponse(
            {"error": f"No API key for provider '{provider}'. Pass user_key or set env var."},
            status_code=400,
        )

    results = []
    for pair in req.qa_pairs:
        t0 = time.time()
        chunks = hybrid_retrieve(pair.question, state, top_k=8)
        chunks = rerank(pair.question, chunks, state, top_k=8)

        ctx_rel = _context_relevance(pair.question, chunks, state)

        answer = ""
        if req.generate_answers:
            ctx_text = "\n\n".join(c["text"] for c in chunks[:6])
            answer = complete(
                provider, req.model, key,
                [{"role": "user", "content": pair.question}],
                system=(
                    "Use the following retrieved context to answer concisely and factually.\n\n"
                    + ctx_text
                ),
            )

        coverage = _keyword_recall(answer, pair.ground_truth) if answer else None
        faith = _faithfulness_proxy(answer, chunks, state) if answer else None

        results.append({
            "question": pair.question,
            "answer": answer,
            "ground_truth": pair.ground_truth,
            "sources": sorted({c.get("source", "") for c in chunks}),
            "chunks_retrieved": len(chunks),
            "metrics": {
                "context_relevance": round(ctx_rel, 4),
                "answer_coverage": round(coverage, 4) if coverage is not None else None,
                "faithfulness_proxy": round(faith, 4) if faith is not None else None,
            },
            "latency_ms": round((time.time() - t0) * 1000),
        })

    ctx_scores = [r["metrics"]["context_relevance"] for r in results]
    cov_scores = [r["metrics"]["answer_coverage"] for r in results if r["metrics"]["answer_coverage"] is not None]
    faith_scores = [r["metrics"]["faithfulness_proxy"] for r in results if r["metrics"]["faithfulness_proxy"] is not None]

    aggregate = {
        "n": len(results),
        "avg_context_relevance": round(float(np.mean(ctx_scores)), 4) if ctx_scores else 0.0,
        "avg_answer_coverage": round(float(np.mean(cov_scores)), 4) if cov_scores else None,
        "avg_faithfulness_proxy": round(float(np.mean(faith_scores)), 4) if faith_scores else None,
    }

    return JSONResponse({"aggregate": aggregate, "results": results})
