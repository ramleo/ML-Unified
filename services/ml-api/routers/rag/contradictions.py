"""Cross-document contradiction detection (MMRAG-02) — flags when two of a
session's uploaded documents say conflicting things about the same fact.

Two-stage, cost-bounded pipeline: (1) a cheap embedding-similarity pass
(reusing the already-loaded embedder — same trick as groundedness.py) narrows
a session's cross-document chunk pairs down to ones plausibly about the same
topic; (2) only THAT small candidate set gets one fast LLM judge call each,
using the same fixed, server-key-only provider expand.py uses for query
rewriting — a background quality check must not spend the same rate-limit
budget the user's actual chat answer needs (see query.py's
_EXPANSION_PROVIDER comment for the original incident this avoids repeating).

find_contradictions() takes embed_fn and judge_fn as injected dependencies
(DIP) rather than importing state/provider internals directly — it depends
only on their (texts) -> embeddings and (text_a, text_b) -> verdict
contracts, so a stronger judge model or a different embedder can be swapped
in later without touching this function or its caller.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Callable, Optional

from fastapi import APIRouter, HTTPException, Request

from security.rate_limit import limiter, LLM_LIMIT
from security.budget import check_and_record_call
from pydantic import BaseModel

from routers.rag.cache import cosine_sim
from routers.rag.entities import decode_entities

logger = logging.getLogger(__name__)

router = APIRouter()

# Below this, two chunks are about different topics — nothing to judge.
# Above this, they're near-duplicate text — trivially agree, not worth a
# judge call. Calibrated the same way as groundedness.py: real
# all-MiniLM-L6-v2 embeddings, not guessed.
_SIM_FLOOR = 0.45
_SIM_CEILING = 0.93

_MAX_PAIRS_TO_JUDGE = 6  # bounds LLM calls regardless of corpus size

# Groq dropped from the default path entirely (2026-08-24) — no free
# replacement that actually worked reliably was found (see query.py's
# _DEFAULT_PROVIDER comment for the full history). Mistral is the
# proven-reliable fallback used throughout this app.
_JUDGE_PROVIDER = "mistral"
_JUDGE_MODEL = "mistral-small-latest"

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


def _collect_session_chunks(state, session_id: str) -> list[dict]:
    """All chunks uploaded by this session, across all its source documents,
    each tagged with its source/page. Skips KB and other-session chunks
    entirely — a contradiction check only compares a user's OWN uploaded
    documents against each other."""
    chunks = []
    for idx, src in enumerate(state.chunk_sources):
        if src not in state.uploaded_sources:
            continue
        if state.source_sessions.get(src) != session_id:
            continue
        text = state.corpus_chunks[idx]
        if not text.strip():
            continue
        meta = state.chunk_meta[idx] if idx < len(state.chunk_meta) else {}
        # entities (MMRAG-03: money/date/percent) ride along unused by
        # find_contradictions() — MMRAG-20's reconciliation pairing reads
        # this to prioritize which candidate pairs are worth an LLM call.
        chunks.append({"text": text, "source": src, "page": meta.get("page"),
                       "entities": decode_entities(meta.get("entities"))})
    return chunks


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


def find_contradictions(
    state, session_id: str, embed_fn: Callable[[list[str]], list],
    judge_fn: Callable[[str, str], Optional[dict]],
) -> dict:
    """Returns {"checked_pairs": int, "sources": list[str], "contradictions": [...]}.
    Empty contradictions list (not an error) when fewer than 2 source
    documents exist for this session — nothing to compare yet."""
    chunks = _collect_session_chunks(state, session_id)
    sources = sorted({c["source"] for c in chunks})
    if len(sources) < 2:
        return {"checked_pairs": 0, "sources": sources, "contradictions": []}

    embeddings = embed_fn([c["text"] for c in chunks])

    candidates: list[tuple[float, int, int]] = []
    for i in range(len(chunks)):
        for j in range(i + 1, len(chunks)):
            if chunks[i]["source"] == chunks[j]["source"]:
                continue
            sim = cosine_sim(embeddings[i], embeddings[j])
            if _SIM_FLOOR <= sim <= _SIM_CEILING:
                candidates.append((sim, i, j))

    candidates.sort(key=lambda x: x[0], reverse=True)
    candidates = candidates[:_MAX_PAIRS_TO_JUDGE]

    contradictions = []
    judge_failures = 0  # same distinction as the reconciliation path below
    for sim, i, j in candidates:
        verdict = judge_fn(chunks[i]["text"], chunks[j]["text"])
        if verdict is None:
            judge_failures += 1
            continue
        if verdict["contradicts"]:
            contradictions.append({
                "similarity": round(sim, 3),
                "explanation": verdict["explanation"],
                "chunk_a": {"text": chunks[i]["text"], "source": chunks[i]["source"], "page": chunks[i]["page"]},
                "chunk_b": {"text": chunks[j]["text"], "source": chunks[j]["source"], "page": chunks[j]["page"]},
            })

    return {"checked_pairs": len(candidates), "judge_failures": judge_failures,
            "sources": sources, "contradictions": contradictions}


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
        raw = complete(provider, model, key,
                       [{"role": "user", "content": f"Passage A: {text_a}\n\nPassage B: {text_b}"}],
                       system=system)
        return _parse_judge_response(raw)

    return judge


def find_reconciliation(
    state, session_id: str, contract_source: str, invoice_sources: list[str],
    embed_fn: Callable[[list[str]], list], judge_fn: Callable[[str, str], Optional[dict]],
    confirm_fn: Optional[Callable[[str, str], Optional[dict]]] = None,
) -> dict:
    """MMRAG-20: like find_contradictions(), but pairs are restricted to
    (contract chunk, invoice chunk) ONLY — never invoice-vs-invoice, never
    contract-vs-contract. Different invoices are SUPPOSED to differ from
    each other (different vendors/dates/amounts); flagging that as a
    "contradiction" the way the generic endpoint would is noise, not a
    finding. Pairs where either side has a money/date entity (MMRAG-03,
    already computed at ingest) are judged before pairs that don't, since
    those are far more likely to be a genuine reconciliation-relevant
    discrepancy — still capped at the same _MAX_PAIRS_TO_JUDGE budget.

    `confirm_fn`, when given, re-checks any pair `judge_fn` flags as a
    discrepancy with a second, independently-worded question before it's
    reported — a single small-model judge call was observed live to
    false-positive on two passages that state the SAME value in different
    wording (see _RECONCILE_JUDGE_SYSTEM's comment). Only re-checks the
    rare flagged candidates, not the whole judged set, so it doesn't
    meaningfully change the LLM-call budget."""
    chunks = _collect_session_chunks(state, session_id)
    contract_chunks = [c for c in chunks if c["source"] == contract_source]
    invoice_chunks = [c for c in chunks if c["source"] in invoice_sources]
    if not contract_chunks or not invoice_chunks:
        return {"checked_pairs": 0, "contract_source": contract_source,
                "invoice_sources": invoice_sources, "discrepancies": []}

    texts = [c["text"] for c in contract_chunks] + [c["text"] for c in invoice_chunks]
    embeddings = embed_fn(texts)
    n_contract = len(contract_chunks)

    def has_numeric_entity(chunk: dict) -> bool:
        return any(e.get("type") in ("money", "date") for e in chunk.get("entities") or [])

    candidates: list[tuple[bool, float, int, int]] = []
    for i, c_chunk in enumerate(contract_chunks):
        for j, inv_chunk in enumerate(invoice_chunks):
            sim = cosine_sim(embeddings[i], embeddings[n_contract + j])
            if _SIM_FLOOR <= sim <= _SIM_CEILING:
                numeric = has_numeric_entity(c_chunk) or has_numeric_entity(inv_chunk)
                candidates.append((numeric, sim, i, j))

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    candidates = candidates[:_MAX_PAIRS_TO_JUDGE]

    discrepancies = []
    # A judge call that never answered — rate-limited, timed out, unparseable
    # — used to fall into the same branch as one that answered "these agree",
    # so a provider outage produced a confident empty report. On a tool whose
    # entire job is catching a discrepancy before you pay it, "I could not
    # check" must never render as "nothing found". Counted and returned so
    # the caller can say which of the two happened.
    judge_failures = 0
    for _, sim, i, j in candidates:
        c_chunk, inv_chunk = contract_chunks[i], invoice_chunks[j]
        verdict = judge_fn(c_chunk["text"], inv_chunk["text"])
        if verdict is None:
            judge_failures += 1
            continue
        if not verdict["contradicts"]:
            continue
        # Never silently drop a flagged pair on confirm_fn's say-so alone —
        # live testing showed BOTH calls can independently miss the same
        # real discrepancy (the small judge model is noisy in both
        # directions, not just toward false positives), and this report
        # exists for a human to review, not to act on unattended. A
        # disagreement is surfaced as `confirmed: false` instead, so the
        # reader can weigh it themselves rather than have it vanish.
        confirmed = True
        if confirm_fn is not None:
            confirmation = confirm_fn(c_chunk["text"], inv_chunk["text"])
            confirmed = bool(confirmation and confirmation["contradicts"])
        discrepancies.append({
            "similarity": round(sim, 3),
            "explanation": verdict["explanation"],
            "confirmed": confirmed,
            "contract_chunk": {"text": c_chunk["text"], "source": c_chunk["source"], "page": c_chunk["page"]},
            "invoice_chunk": {"text": inv_chunk["text"], "source": inv_chunk["source"], "page": inv_chunk["page"]},
        })

    return {"checked_pairs": len(candidates), "judge_failures": judge_failures,
            "contract_source": contract_source,
            "invoice_sources": invoice_sources, "discrepancies": discrepancies}


# ── Endpoints ──────────────────────────────────────────────────────────────────

class ContradictionsRequest(BaseModel):
    session_id: str


@router.post("/contradictions")
@limiter.limit(LLM_LIMIT)
def check_contradictions(request: Request, req: ContradictionsRequest):
    """Scan this session's uploaded documents for cross-document factual
    contradictions. Always uses a fixed server-key-only provider (never the
    caller's selected/BYOK provider) — same reasoning as query expansion."""
    check_and_record_call("contradictions", pool="contradictions", daily_cap_env="CONTRADICTIONS_DAILY_CAP")
    from routers.rag import get_rag_state
    from routers.rag.query import _resolve_key

    try:
        state = get_rag_state()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    key = _resolve_key(_JUDGE_PROVIDER, None)
    judge_fn = make_llm_judge(_JUDGE_PROVIDER, _JUDGE_MODEL, key)
    return find_contradictions(state, req.session_id, state.embedding_fn, judge_fn)


class ReconciliationRequest(BaseModel):
    session_id: str
    contract_source: str
    invoice_sources: list[str]


@router.post("/reconciliation")
@limiter.limit(LLM_LIMIT)
def check_reconciliation(request: Request, req: ReconciliationRequest):
    """MMRAG-20: scan one contract against one or more invoices (all from
    this session's own uploads) for amount/date/term discrepancies. Same
    fixed server-key-only judge provider as /rag/contradictions."""
    check_and_record_call("reconciliation", pool="contradictions", daily_cap_env="CONTRADICTIONS_DAILY_CAP")
    from routers.rag import get_rag_state
    from routers.rag.query import _resolve_key

    try:
        state = get_rag_state()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    key = _resolve_key(_JUDGE_PROVIDER, None)
    judge_fn = make_llm_judge(_JUDGE_PROVIDER, _JUDGE_MODEL, key, system=_RECONCILE_JUDGE_SYSTEM)
    confirm_fn = make_llm_judge(_JUDGE_PROVIDER, _JUDGE_MODEL, key, system=_RECONCILE_CONFIRM_SYSTEM)
    return find_reconciliation(state, req.session_id, req.contract_source,
                               req.invoice_sources, state.embedding_fn, judge_fn, confirm_fn)
