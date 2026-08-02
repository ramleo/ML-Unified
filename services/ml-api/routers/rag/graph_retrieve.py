"""GraphRAG-lite: shared-entity cross-document retrieval (MMRAG-25).

Not a real knowledge graph — entities.py extracts exactly three types
(money/date/percent) via regex with no person/organization extraction and no
cross-chunk identity, and there's no graph library or persistent per-session
object anywhere in this codebase to build one on top of (see the MMRAG-25
plan for the full audit). What this module actually does: when a question
names a specific dollar amount, date, or percentage, find every chunk across
the SAME session's documents that mentions that same value — regardless of
how it ranks by embedding similarity. That's a real, cheap, deterministic
cross-document link (an invoice line and the contract clause restating the
same figure) that plain vector search can miss when the surrounding wording
differs enough. No LLM calls, no new dependency (plain dict adjacency, not
networkx — the graph here is small and per-query, a library is unwarranted),
no persistent state — rebuilt fresh from data already computed at ingest
time (entities.py, MMRAG-03).
"""
from __future__ import annotations

import re

from routers.rag.entities import decode_entities, extract_entities

_MONEY_STRIP_RE = re.compile(r"[$€£¥,\s]")


def _normalize_entity_value(etype: str, value: str) -> str:
    """Best-effort exact-value key — NOT semantic matching. Dates are only
    case/whitespace-normalized (no date parsing), so "03/15/2026" and
    "March 15, 2026" will NOT be linked — a known, documented limitation,
    not an oversight."""
    v = value.strip().lower()
    if etype == "money":
        v = _MONEY_STRIP_RE.sub("", v)
        if v.endswith(".00"):
            v = v[:-3]
    elif etype == "percent":
        v = v.replace("%", "").strip()
    return v


def _session_entity_index(session_id: str, state) -> dict[str, list[int]]:
    """entity key -> chunk indices, scoped to this session's own uploads —
    same filter contradictions.py:_collect_session_chunks uses."""
    index: dict[str, list[int]] = {}
    for idx, src in enumerate(state.chunk_sources):
        if src not in state.uploaded_sources:
            continue
        if state.source_sessions.get(src) != session_id:
            continue
        meta = state.chunk_meta[idx] if idx < len(state.chunk_meta) else {}
        for ent in decode_entities(meta.get("entities")):
            key = f"{ent['type']}:{_normalize_entity_value(ent['type'], ent['value'])}"
            index.setdefault(key, []).append(idx)
    return index


def graph_retrieve(query: str, state, session_id: str, top_k: int = 20) -> list[dict]:
    """[] immediately if the query names no money/date/percent value — most
    questions won't, so this is a cheap early exit before touching state."""
    if not session_id:
        return []
    query_entities = extract_entities(query)
    if not query_entities:
        return []

    index = _session_entity_index(session_id, state)
    if not index:
        return []

    shared_counts: dict[int, int] = {}
    for ent in query_entities:
        key = f"{ent['type']}:{_normalize_entity_value(ent['type'], ent['value'])}"
        for idx in index.get(key, []):
            shared_counts[idx] = shared_counts.get(idx, 0) + 1

    ranked = sorted(shared_counts.items(), key=lambda kv: kv[1], reverse=True)[:top_k]

    hits: list[dict] = []
    for idx, shared in ranked:
        meta = state.chunk_meta[idx] if idx < len(state.chunk_meta) else {}
        # Heuristic confidence, not a cosine similarity — an exact shared
        # value is strong evidence, but there's no vector behind this score.
        score = min(1.0, 0.6 + 0.15 * min(shared - 1, 2))
        hits.append({
            "text": state.corpus_chunks[idx],
            "source": state.chunk_sources[idx],
            "score": score,
            "id": f"graph-{idx}",
            "uploaded": True,
            "chunk_type": meta.get("chunk_type"),
            "page": meta.get("page"),
            "timestamp_s": meta.get("timestamp_s"),
            "bbox": meta.get("bbox"),
            "objects": meta.get("objects"),
            "number_mismatch": meta.get("number_mismatch"),
            "pii_types": meta.get("pii_types"),
            "blurry": meta.get("blurry"),
            "entities": meta.get("entities"),
        })
    return hits
