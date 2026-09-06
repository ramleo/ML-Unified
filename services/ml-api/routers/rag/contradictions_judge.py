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



# A reconciliation scan makes up to six judge calls plus a confirm call per
# flagged pair, in a loop with no gap, so without spacing every call after
# the first was guaranteed a 429 — and the SDK's own retries land 0.4-1.0s
# later, inside the same window, so they 429 too. A faster retry cannot
# outrun a per-second limit; spacing our own calls is the only fix.
#
# The interval is per-provider because the limits are: Mistral allows 1.00
# request/second on mistral-small (its org limits page), while Cohere's free
# trial keys are capped per MINUTE (20/min on v2/chat) — a Mistral-shaped
# 1.15s gap would trip that on the fourth call. Slightly over the exact
# figure in both cases, because the limiter's window and ours are not
# aligned and a call landing on the boundary is a wasted round trip.
#
# If the Cohere key is ever upgraded from trial to production (500/min),
# 3.1 here is pure waiting and should come down to ~0.15.
_MIN_CALL_INTERVAL = {
    "cohere": 3.1,    # 20 req/min trial limit
    "mistral": 1.15,  # 1.00 req/s
}
_DEFAULT_CALL_INTERVAL = 1.15
_pace_lock = threading.Lock()
_last_call_at: dict[str, float] = {}


def _pace(provider: str) -> None:
    """Block until this provider's own minimum interval has passed since the
    last call made to it. Tracked per-provider: falling back from a paced-out
    provider to a fresh one should not inherit the previous one's wait."""
    interval = _MIN_CALL_INTERVAL.get(provider, _DEFAULT_CALL_INTERVAL)
    with _pace_lock:
        wait = interval - (time.monotonic() - _last_call_at.get(provider, 0.0))
        if wait > 0:
            time.sleep(wait)
        _last_call_at[provider] = time.monotonic()


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
        _pace(provider)
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
# silence, so judging runs down a cascade rather than a single provider.
#
# Order set 2026-09-06, matching generation.py's answer cascade and for the
# same reasons:
#   1. Cohere  — free and, unlike Mistral, dependable. Verified serving.
#   2. Mistral — free, but Mistral support confirmed free Studio access has
#      no reserved capacity: it is rejected whenever paid traffic is using
#      the model, however far under the published limits the caller is. Worth
#      one round trip before reaching for the paid key, not worth being first.
#   3. Gemini  — LAST, because it is the only PAID key in this project. It
#      used to be second, which meant a scan billed Gemini for every pair the
#      moment Mistral hiccuped. That is what this ordering exists to stop.
#
# The pairing is not invented here — evaluate_mm.py already treats these
# models as equivalents for judging.
JUDGE_CANDIDATES = [
    ("cohere", "command-a-03-2025"),
    ("mistral", "mistral-small-latest"),
    ("gemini", "gemini-3.6-flash"),
]


def new_chain_state() -> dict:
    """A cursor shared between chains built for the same request.

    `index` is how far down JUDGE_CANDIDATES the scan has been forced. It only
    ever moves forward: once a provider has failed, every remaining pair in
    the same scan would fail on it the same way, and each attempt costs a
    paced second or three. The point is to finish the report, not to keep
    proving a provider is down.

    A reconciliation scan builds two chains — judge and confirm — off the same
    candidates. With a cursor each, a dead provider is rediscovered twice per
    scan instead of once. Callers building more than one chain should make a
    single state here and hand it to all of them.
    """
    return {"index": 0}


def make_judge_chain(resolve_key: Callable[[str, Optional[str]], str],
                     system: str = _JUDGE_SYSTEM,
                     state: Optional[dict] = None,
                     candidates: Optional[list[tuple[str, str]]] = None,
                     ) -> Callable[[str, str], Optional[dict]]:
    """A judge that walks JUDGE_CANDIDATES until one answers.

    Keys come from `resolve_key(provider, None)` — the server-side env key for
    each provider, never a caller-supplied one, since this endpoint takes no
    user key. Candidates with no configured key are dropped at build time.

    Returns None only when every remaining candidate is unavailable, which the
    callers count as a judge failure rather than a clean pair.
    """
    candidates = JUDGE_CANDIDATES if candidates is None else candidates
    judges: list[tuple[str, Callable[[str, str], Optional[dict]]]] = []
    for provider, model in candidates:
        key = resolve_key(provider, None)
        if key:
            judges.append((provider, make_llm_judge(provider, model, key, system)))
        else:
            logger.warning("judge: no key configured for %s, skipping it", provider)
    if not judges:
        logger.error("judge: no provider has a key — every pair will be a judge failure")
    state = new_chain_state() if state is None else state

    def judge(text_a: str, text_b: str) -> Optional[dict]:
        for i in range(state["index"], len(judges)):
            provider, fn = judges[i]
            verdict = fn(text_a, text_b)
            if verdict is not None:
                state["index"] = i  # never go back to one that already failed
                return verdict
            if i + 1 < len(judges):
                logger.warning("judge: %s failed, falling back to %s for the rest of this scan",
                               provider, judges[i + 1][0])
            else:
                logger.warning("judge: %s failed and it was the last candidate", provider)
        state["index"] = len(judges)
        return None

    return judge
