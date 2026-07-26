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

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routers.rag.cache import cosine_sim

logger = logging.getLogger(__name__)

router = APIRouter()

# Below this, two chunks are about different topics — nothing to judge.
# Above this, they're near-duplicate text — trivially agree, not worth a
# judge call. Calibrated the same way as groundedness.py: real
# all-MiniLM-L6-v2 embeddings, not guessed.
_SIM_FLOOR = 0.45
_SIM_CEILING = 0.93

_MAX_PAIRS_TO_JUDGE = 6  # bounds LLM calls regardless of corpus size

_JUDGE_PROVIDER = "groq"
_JUDGE_MODEL = "llama-3.1-8b-instant"

_JUDGE_SYSTEM = (
    "You are given two short passages from two different documents. Decide "
    "whether they make a factual claim about the same specific thing (e.g. "
    "same date, amount, name, or status) but DISAGREE with each other. "
    "Passages that are simply about different topics, that agree, or that "
    "are just differently worded but consistent, are NOT a contradiction. "
    "Reply with ONLY a JSON object, no other text: "
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
        chunks.append({"text": text, "source": src, "page": meta.get("page")})
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
    for sim, i, j in candidates:
        verdict = judge_fn(chunks[i]["text"], chunks[j]["text"])
        if verdict and verdict["contradicts"]:
            contradictions.append({
                "similarity": round(sim, 3),
                "explanation": verdict["explanation"],
                "chunk_a": {"text": chunks[i]["text"], "source": chunks[i]["source"], "page": chunks[i]["page"]},
                "chunk_b": {"text": chunks[j]["text"], "source": chunks[j]["source"], "page": chunks[j]["page"]},
            })

    return {"checked_pairs": len(candidates), "sources": sources, "contradictions": contradictions}


def make_llm_judge(provider: str, model: str, key: str) -> Callable[[str, str], Optional[dict]]:
    """Builds a judge_fn bound to one provider/model/key — the concrete
    implementation find_contradictions() is deliberately kept ignorant of
    (OCP: swap in a different judge later without touching that function)."""
    from routers.rag.llm import complete

    def judge(text_a: str, text_b: str) -> Optional[dict]:
        if not key:
            return None
        raw = complete(provider, model, key,
                       [{"role": "user", "content": f"Passage A: {text_a}\n\nPassage B: {text_b}"}],
                       system=_JUDGE_SYSTEM)
        return _parse_judge_response(raw)

    return judge


# ── Endpoint ───────────────────────────────────────────────────────────────────

class ContradictionsRequest(BaseModel):
    session_id: str


@router.post("/contradictions")
def check_contradictions(req: ContradictionsRequest):
    """Scan this session's uploaded documents for cross-document factual
    contradictions. Always uses a fixed server-key-only provider (never the
    caller's selected/BYOK provider) — same reasoning as query expansion."""
    from routers.rag import get_rag_state
    from routers.rag.query import _resolve_key

    try:
        state = get_rag_state()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    key = _resolve_key(_JUDGE_PROVIDER, None)
    judge_fn = make_llm_judge(_JUDGE_PROVIDER, _JUDGE_MODEL, key)
    return find_contradictions(state, req.session_id, state.embedding_fn, judge_fn)
