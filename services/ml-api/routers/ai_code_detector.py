"""
AI-Generated Code Detector — pending-list #55.

No peer-reviewed benchmark validates a reliable general-purpose AI-vs-human
code detector — disclosed explicitly, not glossed over. This is deliberately
NOT a classifier with a confidence score: it surfaces stylistic signals a
human can inspect themselves. Stylometric heuristics (comment density,
generic naming, docstring format, exception-handling style, etc.) run
entirely client-side and never reach this backend. The only server-side
piece is a second, independent LLM opinion, using the same fixed-server-key
pattern as routers/rag/contradictions.py and routers/prompt_injection_check.py
— its system prompt is written to actively resist overclaiming, instructing
the model to answer "inconclusive" unless there's a genuinely clear tell.
"""

import json
import logging
import re

from fastapi import APIRouter, Request

from security.rate_limit import limiter, LLM_LIMIT
from security.budget import check_and_record_call
from pydantic import BaseModel, Field

from routers.rag.llm import complete
from routers.rag.query_helpers import _resolve_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-code-detect")

_MAX_CODE_LEN = 20_000

# Judge cascade, tried in order. Mistral alone was the whole judge until
# 2026-09-17, when the Space log showed it 429ing every call (free-tier
# capacity contention). The endpoint answered 200 with a null body, so the
# "Independent LLM opinion" panel read "unavailable" for real users while
# the client-side stylometry still ran. Same fix as prompt_injection_check
# and siem_triage: cohere first (free, reliable), mistral second. Gemini is
# absent on purpose — the only paid key, on a public endpoint.
_JUDGE_CANDIDATES = [
    ("cohere", "command-a-03-2025"),
    ("mistral", "mistral-small-latest"),
]

_JUDGE_SYSTEM = (
    "You are shown a code snippet. There is no reliable, published way to "
    "determine with confidence whether code was written by an AI or a "
    "human — style alone is not proof, since a careful human can write "
    "clean, well-documented code, and an AI can be prompted to write messy "
    "code. Only answer \"ai_leaning\" or \"human_leaning\" if there is a "
    "genuinely distinctive tell (e.g. an artifact of an LLM chat response "
    "leaking into the code, like a trailing \"Let me know if...\" comment). "
    "Otherwise answer \"inconclusive\" — this is the expected, correct "
    "answer for most ordinary code and is not a failure to decide. Reply "
    "with ONLY a JSON object, no other text: {\"assessment\": \"ai_leaning\""
    "|\"human_leaning\"|\"inconclusive\", \"confidence\": \"low\"|\"medium\""
    "|\"high\", \"explanation\": \"one short sentence\"}"
)


class AiCodeJudgeRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=_MAX_CODE_LEN)


class AiCodeJudgeVerdict(BaseModel):
    assessment: str
    confidence: str
    explanation: str


def _parse_judge_response(raw: str) -> AiCodeJudgeVerdict | None:
    """Best-effort JSON extraction — reasoning models occasionally wrap the
    JSON in prose or a markdown fence despite the system prompt."""
    if not raw:
        return None
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if "assessment" not in obj:
        return None
    return AiCodeJudgeVerdict(
        assessment=str(obj["assessment"]),
        confidence=str(obj.get("confidence", "low")),
        explanation=str(obj.get("explanation", "")).strip(),
    )


def run_judge(code: str) -> AiCodeJudgeVerdict | None:
    for provider, model in _JUDGE_CANDIDATES:
        key = _resolve_key(provider, None)
        if not key:
            continue
        try:
            raw = complete(provider, model, key,
                           [{"role": "user", "content": code}], system=_JUDGE_SYSTEM)
        except Exception as exc:
            logger.warning("ai-code judge: %s failed: %s", provider, exc)
            continue
        verdict = _parse_judge_response(raw)
        if verdict is not None:
            return verdict
        logger.warning("ai-code judge: %s returned unparseable output", provider)
    logger.error("ai-code judge: every candidate failed (%s)",
                 ", ".join(p for p, _ in _JUDGE_CANDIDATES))
    return None


@router.post("/judge", response_model=AiCodeJudgeVerdict | None)
@limiter.limit(LLM_LIMIT)
def judge_code(request: Request, req: AiCodeJudgeRequest):
    check_and_record_call("ai-code-detector", pool="ai_code_detector", daily_cap_env="AI_CODE_DETECTOR_DAILY_CAP")
    return run_judge(req.code)
