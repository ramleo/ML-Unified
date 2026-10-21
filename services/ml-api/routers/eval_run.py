"""Q4 M2 — offline quality scoring run (golden set + Gemini judge).

The frontend owns the control plane (it creates the eval_runs row and reads the
results); this endpoint is the stateless compute. A run does real LLM work for
every golden item — a fresh RAG answer plus a judge call — which is far too long
for one HTTP request, so /internal/eval/run returns immediately and does the work
in a background thread, then posts the finished scores back to an authenticated
frontend route (the same Space→Vercel pattern as call_log). The Space holds no
Supabase key.

Auth reuses the two secrets that already exist:
  * x-internal-token == TENANT_INTERNAL_TOKEN gates this endpoint (frontend→Space).
  * x-log-token == AIRAML_LOG_TOKEN gates the callback (Space→frontend), like
    call_log's /api/llm-log sink. With either unset the run fails closed.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from routers.eval_golden import GOLDEN, VERSION

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/eval", tags=["eval"])

_INTERNAL_TOKEN = os.environ.get("TENANT_INTERNAL_TOKEN", "")
_JUDGE_PROVIDER = "gemini"
_JUDGE_MODEL = "gemini-3.6-flash"
_INGEST_URL = os.environ.get("EVAL_INGEST_URL", "https://ml-portfolio-rho.vercel.app/api/eval/ingest")
_INGEST_TIMEOUT_S = 15.0

_JUDGE_SYSTEM = (
    "You are a strict evaluator of a website help-assistant's answers. Judge ONLY "
    "the answer given, against the reference, on three independent yes/no criteria. "
    "Return RAW JSON only (no markdown), exactly: "
    '{"correct": bool, "faithful": bool, "relevant": bool, "rationale": "<=1 sentence"}.\n'
    "correct: the answer conveys the reference's key points. For an out-of-scope "
    "question (reference says it should decline), correct=true ONLY if the answer "
    "declines / says it cannot help / redirects, and does NOT fabricate an answer.\n"
    "faithful: the answer makes no claims that contradict or go beyond the reference "
    "(no invented tools, facts, or figures).\n"
    "relevant: the answer actually addresses the question asked."
)


def _require_internal(token: str) -> None:
    if not _INTERNAL_TOKEN or token != _INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


# Neutral, general framing so the eval measures the real site assistant — NOT a
# narrow "Eval tool". The backend _SCOPE_RULE already allows "this website" + ML;
# a tool-specific identity here made the chat call itself "the Eval tool" and
# decline legitimate site questions, which is a harness artifact, not real quality.
_EVAL_CONTEXT = (
    "You are the AIRaML website assistant. Answer questions about the AIRaML "
    "website, its tools and features, and machine learning / data science, using "
    "the retrieved content."
)


def _answer_via_rag(question: str, provider: str, model: str) -> tuple[str, float | None]:
    """Run the real public RAG pipeline for one question with the given generation
    model; return (answer, groundedness)."""
    from routers.rag.query import _sse_generator
    from routers.rag.query_helpers import QueryRequest

    req = QueryRequest(query=question, tool_context=_EVAL_CONTEXT, session_id="eval",
                       provider=provider, model=model)
    parts: list[str] = []
    grounded: float | None = None
    for line in _sse_generator(req):
        if not line.startswith("data: "):
            continue
        try:
            ev = json.loads(line[6:])
        except Exception:
            continue
        if ev.get("type") == "token":
            parts.append(ev.get("text", ""))
        elif ev.get("type") == "done":
            g = ev.get("groundedness")
            if isinstance(g, dict):
                grounded = g.get("score")
            elif isinstance(g, (int, float)):
                grounded = float(g)
    return "".join(parts).strip(), grounded


def _parse_judge(raw: str) -> dict | None:
    s = raw.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s[:4].lower() == "json":
            s = s[4:]
    i, j = s.find("{"), s.rfind("}")
    if i == -1 or j == -1:
        return None
    try:
        d = json.loads(s[i:j + 1])
    except Exception:
        return None
    return {
        "correct": bool(d.get("correct")),
        "faithful": bool(d.get("faithful")),
        "relevant": bool(d.get("relevant")),
        "rationale": str(d.get("rationale", ""))[:400],
    }


def _judge(item: dict, answer: str) -> dict | None:
    from routers.rag.llm import complete
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return None
    user = (
        f"QUESTION:\n{item['question']}\n\n"
        f"REFERENCE (what a correct answer should contain):\n{item['reference']}\n\n"
        f"OUT_OF_SCOPE: {bool(item.get('expect_refusal'))}\n\n"
        f"ANSWER TO JUDGE:\n{answer or '(empty)'}"
    )
    raw = complete(_JUDGE_PROVIDER, _JUDGE_MODEL, key,
                   [{"role": "user", "content": user}], system=_JUDGE_SYSTEM, tool="eval-judge")
    return _parse_judge(raw) if raw else None


def _post(payload: dict, timeout: float) -> None:
    token = os.environ.get("AIRAML_LOG_TOKEN", "")
    if not token:
        logger.error("eval: AIRAML_LOG_TOKEN unset — cannot post results")
        return
    try:
        import httpx
        httpx.post(_INGEST_URL, json=payload, headers={"x-log-token": token}, timeout=timeout)
    except Exception as exc:
        logger.error("eval: post failed: %s", exc)


def _post_result(payload: dict) -> None:
    _post(payload, _INGEST_TIMEOUT_S)


def _post_progress(run_id: str, done: int) -> None:
    """Fire a lightweight n_scored update after each item so the dashboard can
    show a progress bar. Best-effort with a short timeout; a dropped progress
    ping never affects the run or the final result."""
    _post({"run_id": run_id, "kind": "progress", "n_scored": done}, 5.0)


def _run(run_id: str, provider: str, model: str) -> None:
    scores: list[dict] = []
    try:
        for item in GOLDEN:
            answer, grounded = _answer_via_rag(item["question"], provider, model)
            verdict = _judge(item, answer)
            scores.append({
                "item_id": item["id"],
                "question": item["question"],
                "answer": answer[:4000],
                "correct": verdict["correct"] if verdict else None,
                "faithful": verdict["faithful"] if verdict else None,
                "relevant": verdict["relevant"] if verdict else None,
                "groundedness": grounded,
                "rationale": (verdict or {}).get("rationale", "judge unavailable" if not verdict else ""),
            })
            _post_progress(run_id, len(scores))
        judged = [s for s in scores if s["correct"] is not None]
        n = len(judged)
        agg = {
            "pass_rate": (sum(1 for s in judged if s["correct"] and s["faithful"] and s["relevant"]) / n) if n else None,
            "avg_correct": (sum(1 for s in judged if s["correct"]) / n) if n else None,
            "avg_faithful": (sum(1 for s in judged if s["faithful"]) / n) if n else None,
            "avg_relevant": (sum(1 for s in judged if s["relevant"]) / n) if n else None,
        }
        _post_result({"run_id": run_id, "status": "done", "n_scored": n, "scores": scores, **agg})
    except Exception as exc:
        logger.exception("eval run %s failed", run_id)
        _post_result({"run_id": run_id, "status": "error", "error": str(exc)[:400], "scores": scores})


class RunReq(BaseModel):
    run_id: str
    provider: str = "cohere"
    model: str = "command-a-03-2025"


@router.post("/run")
def start_run(body: RunReq, x_internal_token: str = Header(default="")):
    _require_internal(x_internal_token)
    if not body.run_id:
        raise HTTPException(status_code=400, detail="run_id required")
    provider = (body.provider or "cohere").lower()
    model = body.model or "command-a-03-2025"
    threading.Thread(target=_run, args=(body.run_id, provider, model), daemon=True).start()
    return {"run_id": body.run_id, "status": "started", "n": len(GOLDEN),
            "golden_version": VERSION, "judge_model": _JUDGE_MODEL,
            "gen_provider": provider, "gen_model": model}
