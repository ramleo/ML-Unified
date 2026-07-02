"""RAG evaluation — POST /rag/evaluate with LLM-judged RAGAS-style metrics.

Metrics (all 0–1, higher is better):
  faithfulness        — LLM judges: does answer only contain claims in context?
  answer_relevancy    — LLM judges: is answer relevant and complete?
  context_precision   — fraction of chunks the LLM deems relevant to the question
  context_recall      — LLM judges: fraction of ground-truth info covered by contexts
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from routers.rag import get_rag_state
from routers.rag.retrieve import hybrid_retrieve, embed_query
from routers.rag.rerank import rerank
from routers.rag.llm import complete

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


# ── LLM judge helpers ──────────────────────────────────────────────────────────

def _parse_score(text: str) -> float:
    """Extract first number from LLM response; normalize to [0, 1]."""
    m = re.search(r'\d+(?:\.\d+)?', text or "")
    if not m:
        return 0.5
    v = float(m.group())
    return min(v / 10.0, 1.0) if v > 1 else v


def _judge(prompt: str, provider: str, model: str, key: str) -> str:
    try:
        return complete(provider, model, key, [{"role": "user", "content": prompt}])
    except Exception as exc:
        logger.warning("eval judge call failed: %s", exc)
        return ""


def _faithfulness(question: str, answer: str, chunks: list[dict],
                  provider: str, model: str, key: str) -> float:
    ctx = "\n\n".join(c["text"][:400] for c in chunks[:5])
    prompt = (
        f"Context:\n{ctx}\n\n"
        f"Answer: {answer}\n\n"
        "Score 0-10: how faithful is the answer to the context only? "
        "10 = every claim is grounded in the context, 0 = pure hallucination. "
        "Reply with only a number."
    )
    return _parse_score(_judge(prompt, provider, model, key))


def _answer_relevancy(question: str, answer: str,
                      provider: str, model: str, key: str) -> float:
    prompt = (
        f"Question: {question}\nAnswer: {answer}\n\n"
        "Score 0-10: how relevant and complete is the answer to the question? "
        "10 = perfectly answers the question, 0 = completely off-topic. "
        "Reply with only a number."
    )
    return _parse_score(_judge(prompt, provider, model, key))


def _context_precision(question: str, chunks: list[dict],
                       provider: str, model: str, key: str) -> float:
    if not chunks:
        return 0.0
    relevant = 0
    for c in chunks:
        prompt = (
            f"Question: {question}\n"
            f"Chunk: {c['text'][:300]}\n"
            "Is this chunk useful for answering the question? Reply Yes or No."
        )
        resp = _judge(prompt, provider, model, key).lower()
        if "yes" in resp:
            relevant += 1
    return relevant / len(chunks)


def _context_recall(question: str, chunks: list[dict], ground_truth: str,
                    provider: str, model: str, key: str) -> float:
    ctx = "\n\n".join(c["text"][:300] for c in chunks[:5])
    prompt = (
        f"Ground truth answer: {ground_truth}\n\n"
        f"Retrieved contexts:\n{ctx}\n\n"
        "Score 0-10: what fraction of the ground truth information is present in "
        "the retrieved contexts? 10 = all key facts covered, 0 = nothing covered. "
        "Reply with only a number."
    )
    return _parse_score(_judge(prompt, provider, model, key))


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post("/evaluate")
def rag_evaluate(req: EvalRequest) -> JSONResponse:
    """Evaluate retrieval + generation with LLM-judged RAGAS-style metrics.

    Set generate_answers=false to evaluate retrieval only (skips faithfulness,
    answer_relevancy, and generation calls).
    """
    try:
        state = get_rag_state()
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)

    if not req.qa_pairs:
        return JSONResponse({"error": "qa_pairs must not be empty."}, status_code=400)

    provider = req.provider.lower()
    key = req.user_key or os.environ.get(_ENV_KEYS.get(provider, ""), "")

    if not key:
        return JSONResponse(
            {"error": f"No API key for provider '{provider}'."},
            status_code=400,
        )

    results = []
    for pair in req.qa_pairs:
        t0 = time.time()
        chunks = hybrid_retrieve(pair.question, state, top_k=8)
        chunks = rerank(pair.question, chunks, state, top_k=5)

        ctx_prec = _context_precision(pair.question, chunks, provider, req.model, key)
        ctx_rec  = _context_recall(pair.question, chunks, pair.ground_truth, provider, req.model, key)

        answer = ""
        faith = None
        ans_rel = None

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
            if answer:
                faith   = _faithfulness(pair.question, answer, chunks, provider, req.model, key)
                ans_rel = _answer_relevancy(pair.question, answer, provider, req.model, key)

        results.append({
            "question":       pair.question,
            "answer":         answer,
            "ground_truth":   pair.ground_truth,
            "sources":        sorted({c.get("source", "") for c in chunks}),
            "chunks_retrieved": len(chunks),
            "metrics": {
                "context_precision":  round(ctx_prec, 4),
                "context_recall":     round(ctx_rec, 4),
                "faithfulness":       round(faith, 4) if faith is not None else None,
                "answer_relevancy":   round(ans_rel, 4) if ans_rel is not None else None,
            },
            "latency_ms": round((time.time() - t0) * 1000),
        })

    def _avg(key: str):
        vals = [r["metrics"][key] for r in results if r["metrics"][key] is not None]
        return round(float(np.mean(vals)), 4) if vals else None

    aggregate = {
        "n": len(results),
        "avg_context_precision":  _avg("context_precision"),
        "avg_context_recall":     _avg("context_recall"),
        "avg_faithfulness":       _avg("faithfulness"),
        "avg_answer_relevancy":   _avg("answer_relevancy"),
    }

    return JSONResponse({"aggregate": aggregate, "results": results})


# ── Held-out eval-run endpoint ─────────────────────────────────────────────────

_QA_PATH  = Path("/data/rag_eval_qa.json")
_LOG_PATH = Path("/data/rag_eval_log.jsonl")
_QA_LOCAL = Path(__file__).parent.parent.parent / "data" / "rag_eval_qa.json"


class EvalRunRequest(BaseModel):
    provider: str = _DEFAULT_PROVIDER
    model: str = _DEFAULT_MODEL
    user_key: Optional[str] = None
    generate_answers: bool = True


@router.post("/eval-run")
def rag_eval_run(req: EvalRunRequest) -> JSONResponse:
    """Run evaluation against the held-out QA set and append results to the log.

    Loads rag_eval_qa.json from /data/ (HF Space) or falls back to the local
    data/ directory. Appends a timestamped aggregate to rag_eval_log.jsonl.
    """
    qa_path = _QA_PATH if _QA_PATH.exists() else _QA_LOCAL
    if not qa_path.exists():
        return JSONResponse({"error": "rag_eval_qa.json not found."}, status_code=404)

    try:
        raw = json.loads(qa_path.read_text())
        qa_pairs = [QAPair(**item) for item in raw]
    except Exception as exc:
        return JSONResponse({"error": f"Failed to load QA file: {exc}"}, status_code=500)

    inner_req = EvalRequest(
        qa_pairs=qa_pairs,
        provider=req.provider,
        model=req.model,
        user_key=req.user_key,
        generate_answers=req.generate_answers,
    )
    result: JSONResponse = rag_evaluate(inner_req)
    data = json.loads(result.body)

    log_entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "provider": req.provider,
        "model": req.model,
        "generate_answers": req.generate_answers,
        **data.get("aggregate", {}),
    }
    try:
        log_path = _LOG_PATH if _LOG_PATH.parent.exists() else (
            _QA_LOCAL.parent / "rag_eval_log.jsonl"
        )
        with open(log_path, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as exc:
        logger.warning("Could not write eval log: %s", exc)

    return JSONResponse({"aggregate": data.get("aggregate"), "logged": log_entry["ts"]})
