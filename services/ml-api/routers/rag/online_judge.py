"""Q4 M3 — online (live-traffic) judge-scoring, reference-free + content-free.

The offline eval (eval_run.py) scores a FIXED golden set on demand. This scores a
SAMPLE of REAL answers users actually received, so the dashboard shows live quality,
not just a canned test. Live traffic has no reference answer, so the judge is
reference-free: it rates the answer against the question + retrieved context —
  faithful: the answer's claims are supported by the context (no made-up facts),
  relevant: the answer actually addresses the question.
It never rates "correct" (no ground truth exists online).

Privacy: the question/answer/context go to the judge LLM transiently (exactly as the
offline judge does) but are NEVER stored. Only the numeric verdict is posted to the
frontend — same Space→Vercel trust as rag_log (AIRAML_LOG_TOKEN; unset → nothing runs).

Cost control (all env-tunable): judge the TAIL (low-confidence / low-groundedness,
where problems hide) always, plus a small random sample of the rest, under a hard
per-day cap on judge calls.
"""
from __future__ import annotations

import datetime as _dt
import logging
import os
import random
import threading

logger = logging.getLogger(__name__)

_INGEST_URL = os.environ.get("EVAL_ONLINE_URL", "https://ml-portfolio-rho.vercel.app/api/eval/online-ingest")
_SAMPLE_RATE = float(os.environ.get("EVAL_ONLINE_SAMPLE_RATE", "0.08"))
_DAILY_CAP = int(os.environ.get("EVAL_ONLINE_DAILY_CAP", "200"))
_TAIL_GROUNDEDNESS = float(os.environ.get("EVAL_ONLINE_TAIL_GROUNDEDNESS", "0.5"))
_TIMEOUT_S = 12.0

_JUDGE_PROVIDER = "gemini"
_JUDGE_MODEL = "gemini-3.6-flash"
_JUDGE_SYSTEM = (
    "You judge a help assistant's answer against the retrieved context it was given. "
    "No reference answer exists. Reply with ONLY a compact JSON object: "
    '{"faithful": bool, "relevant": bool, "rationale": "<=1 sentence"}.\n'
    "faithful: every claim in the answer is supported by the context; it invents nothing "
    "beyond it (an honest 'I don't know' when the context lacks the answer is faithful).\n"
    "relevant: the answer actually addresses the question asked."
)

# Hard per-day cap on judge calls, counted in-process (the Space is the only judge).
_lock = threading.Lock()
_day = ""
_count = 0


def _under_cap() -> bool:
    """Reserve one judge call for today if the cap allows. Resets at UTC midnight."""
    global _day, _count
    today = _dt.date.today().isoformat()
    with _lock:
        if today != _day:
            _day, _count = today, 0
        if _count >= max(_DAILY_CAP, 0):
            return False
        _count += 1
        return True


def _gfloat(g) -> float | None:
    if isinstance(g, dict):
        v = g.get("score")
        return float(v) if isinstance(v, (int, float)) else None
    return float(g) if isinstance(g, (int, float)) else None


def _parse(raw: str) -> dict | None:
    import json
    import re
    m = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except Exception:
        return None
    return {"faithful": bool(d.get("faithful")), "relevant": bool(d.get("relevant")),
            "rationale": str(d.get("rationale", ""))[:200]}


def _judge_and_post(*, question: str, answer: str, context: str, reason: str,
                    provider: str, model: str, answer_source: str, groundedness, surface: str) -> None:
    try:
        from routers.rag.llm import complete
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            return
        user = (f"QUESTION:\n{question}\n\nCONTEXT (retrieved):\n{context}\n\n"
                f"ANSWER TO JUDGE:\n{answer or '(empty)'}")
        raw = complete(_JUDGE_PROVIDER, _JUDGE_MODEL, key,
                       [{"role": "user", "content": user}], system=_JUDGE_SYSTEM, tool="eval-online-judge")
        v = _parse(raw) if raw else None
        if not v:
            return
        payload = {
            "surface": surface, "faithful": v["faithful"], "relevant": v["relevant"],
            "passed": v["faithful"] and v["relevant"], "sampled_reason": reason,
            "provider": provider or "", "model": model or "",
            "answer_source": answer_source or "", "groundedness": _gfloat(groundedness),
        }
        token = os.environ.get("AIRAML_LOG_TOKEN", "")
        if not token:
            return
        import httpx
        httpx.post(_INGEST_URL, json=payload, headers={"x-log-token": token}, timeout=_TIMEOUT_S)
    except Exception as exc:  # never affect the live request
        logger.debug("online judge failed: %s", exc)


def maybe_judge(*, question: str, answer: str, chunks: list, groundedness,
                low_confidence: bool, confidence: str = "", provider: str = "",
                model: str = "", answer_source: str = "", surface: str = "rag") -> None:
    """Decide whether to judge this live answer, and if so judge it in the background.
    Returns immediately and never raises — safe to call on the hot answer path."""
    try:
        if not os.environ.get("GEMINI_API_KEY", "") or not os.environ.get("AIRAML_LOG_TOKEN", ""):
            return  # fail closed
        if not (answer or "").strip() or not chunks:
            return  # nothing to judge faithfulness against

        g = _gfloat(groundedness)
        is_tail = bool(low_confidence) or (g is not None and g < _TAIL_GROUNDEDNESS)
        if is_tail:
            reason = "tail"
        elif random.random() < _SAMPLE_RATE:
            reason = "random"
        else:
            return
        if not _under_cap():
            return

        context = "\n\n".join((c.get("text", "") or "") for c in chunks)[:6000]
        threading.Thread(
            target=_judge_and_post,
            kwargs=dict(question=question, answer=answer, context=context, reason=reason,
                        provider=provider, model=model, answer_source=answer_source,
                        groundedness=groundedness, surface=surface),
            daemon=True,
        ).start()
    except Exception as exc:
        logger.debug("maybe_judge skipped: %s", exc)
