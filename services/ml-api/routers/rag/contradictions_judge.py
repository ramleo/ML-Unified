"""The judge half of contradiction/reconciliation scanning: the prompts, the
JSON parsing, the per-second pacing, and the provider chain.

Split out of contradictions.py when adding the Gemini fallback pushed that
file past the 400-line limit. The seam is real rather than arbitrary: nothing
here knows what a chunk or a session is, and nothing in contradictions.py
knows which provider answers — that is the dependency the two scan functions
take as an injected judge_fn.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


_JUDGE_SYSTEM = (
    "You are given two short passages from two different documents. Decide "
    "whether they make a factual claim about the same specific thing (e.g. "
    "same date, amount, name, or status) but DISAGREE with each other. "
    "Passages that are simply about different topics, that agree, or that "
    "are just differently worded but consistent, are NOT a contradiction. "
    "Reply with ONLY a JSON object, no other text: "
    '{"contradicts": true|false, "explanation": "one short sentence"}'
)

# MMRAG-20: same judge, same JSON shape, narrower question — a contract and
# an invoice are EXPECTED to differ in most of their text (different
# structure, different boilerplate); only a same-amount/date/term
# disagreement actually matters here. The worked counter-example below is a
# real false positive caught in live testing: groq/compound-mini flagged
# "due within 30 days of invoice date" vs. "Due date: 30 days from issue" as
# disagreeing, even though both state the same 30-day term in different
# words — the model was pattern-matching on differing PHRASING, not
# comparing the actual VALUE. Spelling that exact failure mode out is doing
# real work here, not decorative.
_RECONCILE_JUDGE_SYSTEM = (
    "Passage A is a clause from a CONTRACT. Passage B is a line from an "
    "INVOICE. Decide whether they refer to the SAME amount, date, quantity, "
    "or term but state a DIFFERENT VALUE for it (e.g. contract says "
    "$50,000, invoice bills $52,500 — different values, IS a discrepancy). "
    "Two passages that state the SAME value in different wording are NOT a "
    "discrepancy — e.g. contract says 'due within 30 days of invoice date' "
    "and invoice says 'Due date: 30 days from issue' both mean 30 days: "
    "NOT a discrepancy, even though the sentences look different. Judge the "
    "underlying value, not the phrasing. If they're about unrelated "
    "matters, or state the same value, that is NOT a discrepancy. Reply "
    "with ONLY a JSON object, no other text: "
    '{"contradicts": true|false, "explanation": "one short sentence"}'
)

# A single small-model judge call is noisy enough that a real false positive
# was observed live (see comment above) — for reconciliation specifically
# (not the generic /rag/contradictions path, which keeps its original
# single-call behavior unchanged), a positive verdict gets ONE independent
# re-check with a differently-worded question before being reported. This
# only doubles LLM calls for the rare candidates that got flagged in the
# first place, not the whole judged set.
_RECONCILE_CONFIRM_SYSTEM = (
    "Passage A is a clause from a CONTRACT. Passage B is a line from an "
    "INVOICE. A first pass flagged these as stating DIFFERENT values for "
    "the same amount/date/quantity/term. Double-check carefully: do they "
    "actually state a different VALUE, or do they state the SAME value in "
    "different words (which is NOT a discrepancy)? Reply with ONLY a JSON "
    "object, no other text: "
    '{"contradicts": true|false, "explanation": "one short sentence"}'
)



def _parse_judge_response(raw: str) -> Optional[dict]:
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
    if "contradicts" not in obj:
        return None
    return {"contradicts": bool(obj["contradicts"]), "explanation": str(obj.get("explanation", "")).strip()}



# Mistral allows 1.00 requests/second on mistral-small (see the org's limits
# page). A reconciliation scan makes up to six judge calls plus a confirm
# call per flagged pair, in a loop with no gap, so every call after the first
# was guaranteed a 429 — and the SDK's own retries land 0.4-1.0s later, still
# inside the same one-second window, so they 429 too. Spacing our own calls
# is the only thing that fixes it; a faster retry cannot outrun a per-second
# limit. Slightly over one second, because the limiter's window and ours are
# not aligned and a call landing on the boundary is a wasted round trip.
_MIN_CALL_INTERVAL = 1.15
_pace_lock = threading.Lock()
_last_call_at = 0.0


def _pace() -> None:
    """Block until at least _MIN_CALL_INTERVAL has passed since the last call."""
    global _last_call_at
    with _pace_lock:
        wait = _MIN_CALL_INTERVAL - (time.monotonic() - _last_call_at)
        if wait > 0:
            time.sleep(wait)
        _last_call_at = time.monotonic()


def make_llm_judge(provider: str, model: str, key: str,
                   system: str = _JUDGE_SYSTEM) -> Callable[[str, str], Optional[dict]]:
    """Builds a judge_fn bound to one provider/model/key — the concrete
    implementation find_contradictions() is deliberately kept ignorant of
    (OCP: swap in a different judge later without touching that function).
    `system` defaults to the generic contradiction prompt so the existing
    /rag/contradictions endpoint is unaffected; MMRAG-20's reconciliation
    endpoint passes _RECONCILE_JUDGE_SYSTEM instead."""
    from routers.rag.llm import complete

    def judge(text_a: str, text_b: str) -> Optional[dict]:
        if not key:
            return None
        _pace()
        # max_retries=0: _pace() already guarantees the spacing the limit
        # wants, so a failure here is not transient congestion the SDK can
        # retry its way out of — it is the provider refusing. Its two extra
        # attempts land inside the same window, fail identically, and only
        # delay the fallback.
        raw = complete(provider, model, key,
                       [{"role": "user", "content": f"Passage A: {text_a}\n\nPassage B: {text_b}"}],
                       system=system, max_retries=0)
        return _parse_judge_response(raw)

    return judge


# One provider being down should not turn a reconciliation report into
# silence. Mistral is primary; Gemini answers when it cannot. The pairing is
# the project's own — evaluate_mm.py already treats mistral-small-latest and
# gemini-3.6-flash as equivalents for judging — not a model picked here.
_FALLBACK_PROVIDER = "gemini"
_FALLBACK_MODEL = "gemini-3.6-flash"


def new_chain_state() -> dict:
    """A latch shared between chains built for the same request.

    A reconciliation scan builds two chains — judge and confirm — off the same
    primary key. With a latch each, a dead primary is rediscovered twice per
    scan instead of once. Callers that build more than one chain should make
    a single state here and hand it to all of them."""
    return {"primary_down": False}


def make_judge_chain(primary_provider: str, primary_model: str, primary_key: str,
                     fallback_key: str, system: str = _JUDGE_SYSTEM,
                     state: Optional[dict] = None,
                     ) -> Callable[[str, str], Optional[dict]]:
    """A judge that tries `primary_provider`, then Gemini.

    The first failure latches: when the primary is rate-limited or its key is
    dead, every remaining pair in the same scan would fail the same way, and
    each attempt costs a paced second plus the SDK's retries. So after one
    failure the rest of the scan goes straight to the fallback — the point is
    to finish the report, not to keep proving the primary is down.

    Returns None only when both are unavailable, which the callers count as a
    judge failure rather than a clean pair.
    """
    primary = make_llm_judge(primary_provider, primary_model, primary_key, system) if primary_key else None
    fallback = make_llm_judge(_FALLBACK_PROVIDER, _FALLBACK_MODEL, fallback_key, system) if fallback_key else None
    if primary is None and fallback is not None:
        logger.warning("judge: no %s key, using %s", primary_provider, _FALLBACK_PROVIDER)
    state = new_chain_state() if state is None else state
    if primary is None:
        state["primary_down"] = True

    def judge(text_a: str, text_b: str) -> Optional[dict]:
        if not state["primary_down"] and primary is not None:
            verdict = primary(text_a, text_b)
            if verdict is not None:
                return verdict
            state["primary_down"] = True
            logger.warning("judge: %s failed, falling back to %s for the rest of this scan",
                           primary_provider, _FALLBACK_PROVIDER)
        return fallback(text_a, text_b) if fallback is not None else None

    return judge
