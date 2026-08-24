"""Multimodal RAG eval — reuses evaluate.py's RAGAS-style judge metrics against
a fixture PDF (data/fixtures/mm_rag_sample.pdf) + QA set (data/rag_eval_mm_qa.json)
that specifically requires reading a table and a figure caption, not just prose.
Kept separate from evaluate.py (already near the file-length cap) and requires
its own precondition (ingesting the fixture first), unlike the always-loaded
static KB the main eval runs against.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from routers.rag import get_rag_state
from routers.rag.retrieve import tiered_hybrid_retrieve
from routers.rag.rerank import rerank
from routers.rag.mm_pdf import build_multimodal_chunks
from routers.rag.ingest import index_chunks, delete_source
from routers.rag.evaluate import _faithfulness, _answer_relevancy, _context_precision, _context_recall
from routers.rag.llm import complete

logger = logging.getLogger(__name__)
router = APIRouter()

# Groq dropped from this automatic (no user choice at all) key-priority list
# entirely (2026-08-24, see routers/rag/query.py's _DEFAULT_PROVIDER comment
# for the full history) — Mistral is the proven-reliable default instead.
_ENV_KEYS = {"mistral": "MISTRAL_API_KEY", "gemini": "GEMINI_API_KEY", "cohere": "COHERE_API_KEY"}
_MODELS = {"mistral": "mistral-small-latest", "gemini": "gemini-3.6-flash", "cohere": "command-a-03-2025"}
_QA_PATH = "data/rag_eval_mm_qa.json"


def _resolve_key() -> tuple[str, str, str]:
    for provider, env in _ENV_KEYS.items():
        key = os.environ.get(env, "")
        if key:
            return provider, _MODELS[provider], key
    return "", "", ""


def run_mm_eval(qa_path: str = _QA_PATH) -> dict:
    """Ingest the fixture PDF, run each QA pair, return per-question + aggregate
    metrics. Cleans up the ingested test chunks afterward regardless of outcome."""
    spec = json.loads(Path(qa_path).read_text())
    fixture_pdf = spec["fixture_pdf"]
    qa_pairs = spec["qa"]

    provider, model, key = _resolve_key()
    if not key:
        return {"error": "No LLM API key available in environment for eval judging."}

    state = get_rag_state()
    file_bytes = Path(fixture_pdf).read_bytes()
    source = "user:mm_eval_fixture:eval"
    session_id = "mm_eval_session"

    chunks, _page_images, chunk_summary = build_multimodal_chunks(file_bytes, source)
    index_chunks(chunks, state, uploaded=True, session_id=session_id)
    logger.info("mm eval: ingested fixture — %s", chunk_summary)

    results = []
    try:
        for qa in qa_pairs:
            question = qa["question"]
            expected_type = qa.get("expected_chunk_type")
            ground_truth = qa.get("expected_answer")

            candidates = tiered_hybrid_retrieve(question, state, top_k=8, session_id=session_id)
            retrieved = rerank(question, candidates, state, top_k=5)
            top_type = retrieved[0].get("chunk_type") if retrieved else None

            if ground_truth is None:
                # Intentionally-unanswerable check: correct behavior is a weak/empty
                # retrieval, not a confident wrong citation.
                top_score = retrieved[0].get("score", 0.0) if retrieved else 0.0
                results.append({
                    "question": question, "type": "unanswerable_check",
                    "top_score": round(top_score, 4),
                    "passed": top_score < 0.2,
                })
                continue

            ctx = "\n\n".join(c["text"][:400] for c in retrieved[:5])
            prompt = f"Context:\n{ctx}\n\nQuestion: {question}\nAnswer concisely using only the context."
            answer = complete(provider, model, key, [{"role": "user", "content": prompt}])

            results.append({
                "question": question,
                "answer": answer,
                "expected_answer": ground_truth,
                "chunk_type_match": top_type == expected_type,
                "top_chunk_type": top_type,
                "expected_chunk_type": expected_type,
                "faithfulness": _faithfulness(question, answer, retrieved, provider, model, key),
                "answer_relevancy": _answer_relevancy(question, answer, provider, model, key),
                "context_precision": _context_precision(question, retrieved, provider, model, key),
                "context_recall": _context_recall(question, retrieved, ground_truth, provider, model, key),
            })
    finally:
        delete_source(source, state)

    scored = [r for r in results if "faithfulness" in r]
    aggregate = {
        "chunk_summary": chunk_summary,
        "n_questions": len(results),
        "citation_type_accuracy": round(
            sum(1 for r in scored if r["chunk_type_match"]) / len(scored), 3) if scored else None,
        "avg_faithfulness": round(sum(r["faithfulness"] for r in scored) / len(scored), 3) if scored else None,
        "avg_answer_relevancy": round(sum(r["answer_relevancy"] for r in scored) / len(scored), 3) if scored else None,
        "avg_context_precision": round(sum(r["context_precision"] for r in scored) / len(scored), 3) if scored else None,
        "avg_context_recall": round(sum(r["context_recall"] for r in scored) / len(scored), 3) if scored else None,
    }
    return {"results": results, "aggregate": aggregate}


@router.post("/mm-eval-run")
def rag_mm_eval_run() -> JSONResponse:
    """Run the multimodal QA fixture through the full ingest → retrieve →
    generate → judge pipeline once. Not gating the build — a baseline number."""
    try:
        return JSONResponse(run_mm_eval())
    except Exception as exc:
        logger.exception("mm eval run failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)
