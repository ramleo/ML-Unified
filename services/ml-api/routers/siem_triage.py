"""
SIEM Alert Triage Agent — cybersecurity shortlist pick #3.

Real SOC-analyst workflow: "alert fatigue" is a well-known problem (too
many raw alerts for a human to triage one-by-one). Alert deduplication/
grouping by normalized template happens entirely client-side (see
ml-portfolio's alertGrouping.ts) — this backend only adds a second,
independent LLM opinion on the already-grouped alerts, using the same
fixed-server-key pattern as routers/ai_code_detector.py and
routers/prompt_injection_check.py. Advisory only: the system prompt
explicitly instructs the model to phrase actions as suggestions, never as
something this tool did or will do — there is no real firewall/AD/EDR
integration here to actually act on anything.
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

router = APIRouter(prefix="/siem-triage")

_MAX_GROUPS = 20
_MAX_EXAMPLE_LEN = 500

_JUDGE_PROVIDER = "mistral"
_JUDGE_MODEL = "mistral-small-latest"

_JUDGE_SYSTEM = (
    "You are a SOC analyst assistant. You are shown a list of already-"
    "deduplicated alert groups (each with a normalized template, how many "
    "raw alerts matched it, one real example line, and any IP addresses "
    "involved). For EACH group, assign a priority and suggest what a human "
    "analyst should do next. You are advisory only — you do not take any "
    "action yourself, and must never phrase a suggestion as something "
    "already done (say \"investigate the source IP\", never \"blocked the "
    "IP\"). Reply with ONLY a JSON array, no other text, one object per "
    "input group in the same order: [{\"priority\": \"critical\"|\"high\"|"
    "\"medium\"|\"low\"|\"noise\", \"reasoning\": \"one short sentence\", "
    "\"suggested_action\": \"one short sentence, phrased as a suggestion\"}]"
)


class AlertGroupIn(BaseModel):
    template: str = Field(..., max_length=300)
    count: int = Field(..., ge=1)
    example: str = Field(..., max_length=_MAX_EXAMPLE_LEN)
    unique_ips: list[str] = Field(default_factory=list, max_length=100)


class SiemTriageRequest(BaseModel):
    groups: list[AlertGroupIn] = Field(..., min_length=1, max_length=_MAX_GROUPS)


class TriageVerdict(BaseModel):
    priority: str
    reasoning: str
    suggested_action: str


def _parse_judge_response(raw: str, expected_count: int) -> list[TriageVerdict] | None:
    """Best-effort JSON-array extraction — reasoning models occasionally
    wrap the JSON in prose or a markdown fence despite the system prompt."""
    if not raw:
        return None
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return None
    try:
        arr = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(arr, list) or len(arr) != expected_count:
        return None
    verdicts = []
    for item in arr:
        if not isinstance(item, dict) or "priority" not in item:
            return None
        verdicts.append(TriageVerdict(
            priority=str(item["priority"]),
            reasoning=str(item.get("reasoning", "")).strip(),
            suggested_action=str(item.get("suggested_action", "")).strip(),
        ))
    return verdicts


def run_triage(groups: list[AlertGroupIn]) -> list[TriageVerdict] | None:
    key = _resolve_key(_JUDGE_PROVIDER, None)
    if not key:
        return None
    payload = [
        {
            "template": g.template,
            "count": g.count,
            "example": g.example[:_MAX_EXAMPLE_LEN],
            "unique_ips": g.unique_ips[:20],
        }
        for g in groups
    ]
    raw = complete(
        _JUDGE_PROVIDER, _JUDGE_MODEL, key,
        [{"role": "user", "content": json.dumps(payload)}],
        system=_JUDGE_SYSTEM,
    )
    return _parse_judge_response(raw, len(groups))


@router.post("/judge", response_model=list[TriageVerdict] | None)
@limiter.limit(LLM_LIMIT)
def judge_alerts(request: Request, req: SiemTriageRequest):
    check_and_record_call("siem-triage", pool="siem_triage", daily_cap_env="SIEM_TRIAGE_DAILY_CAP")
    return run_triage(req.groups)
