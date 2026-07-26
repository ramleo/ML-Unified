"""Ingestion diffing — flag a likely revision of an existing session doc.

Split out of mm_ingest.py to keep that file under the project's line
limit. Deliberately conservative: only ever informational (surfaced to the
user to decide), never auto-replaces anything. Matches on same filename OR
high content-similarity so a rename doesn't slip past detection, at the
cost of comparing text against every other doc still in this session
(small in practice — session uploads, not the whole KB).
"""
from __future__ import annotations

import difflib
import re

_SOURCE_SUFFIX_RE = re.compile(r":[0-9a-f]{8}$")
_REVISION_SIMILARITY_THRESHOLD = 0.65
_REVISION_COMPARE_CHARS = 4000


def display_filename(source: str) -> str:
    name = source[len("user:"):] if source.startswith("user:") else source
    return _SOURCE_SUFFIX_RE.sub("", name)


def find_revision_candidate(source: str, session_id: str, chunks: list[dict], state) -> dict | None:
    if not session_id:
        return None
    new_name = display_filename(source).lower()
    new_text = " ".join(c.get("text", "") for c in chunks)[:_REVISION_COMPARE_CHARS]

    best: dict | None = None
    for other_source in state.uploaded_sources:
        if other_source == source or state.source_sessions.get(other_source) != session_id:
            continue
        same_filename = display_filename(other_source).lower() == new_name
        old_text = " ".join(
            text for text, src in zip(state.corpus_chunks, state.chunk_sources) if src == other_source
        )[:_REVISION_COMPARE_CHARS]
        similarity = (
            difflib.SequenceMatcher(None, new_text, old_text).ratio() if new_text and old_text else 0.0
        )
        if not same_filename and similarity < _REVISION_SIMILARITY_THRESHOLD:
            continue
        reason = "same_filename" if same_filename else "similar_content"
        candidate = {
            "source": other_source, "filename": display_filename(other_source),
            "reason": reason, "similarity": round(similarity, 2),
        }
        if best is None or (reason == "same_filename" and best["reason"] != "same_filename") \
                or (reason == best["reason"] and similarity > best["similarity"]):
            best = candidate
    return best
