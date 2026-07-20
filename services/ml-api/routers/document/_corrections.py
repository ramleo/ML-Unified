"""In-memory store of human field corrections (HITL feedback loop).

When a user edits an extracted field in the UI, the (original → corrected)
pair is recorded per document type. Recent pairs are injected into future
extraction prompts as few-shot guidance, so the model "learns" from human
corrections with zero training infrastructure. In-memory only: resets on
Space restart, entries expire after 7 days.
"""
from __future__ import annotations

import logging
import time
from collections import deque

logger = logging.getLogger(__name__)

_MAX_PER_TYPE = 12   # corrections kept per document type
_MAX_IN_PROMPT = 8   # most recent pairs injected into the prompt
_TTL_SECONDS = 7 * 24 * 3600

_store: dict[str, deque] = {}


def add(doc_type: str, name: str, label: str, original: str, corrected: str) -> bool:
    """Record one human correction. Returns True if stored."""
    doc_type, name = doc_type.strip(), name.strip()
    original, corrected = str(original).strip(), str(corrected).strip()
    if not (doc_type and name and corrected) or original == corrected:
        return False
    dq = _store.setdefault(doc_type, deque(maxlen=_MAX_PER_TYPE))
    for e in list(dq):  # a re-edit of the same mistake replaces the old entry
        if e["name"] == name and e["original"] == original:
            dq.remove(e)
    dq.append({
        "name": name[:60],
        "label": (label or name).strip()[:80],
        "original": original[:120],
        "corrected": corrected[:120],
        "at": time.time(),
    })
    logger.info("Correction stored: %s.%s (%d for this type)", doc_type, name, len(dq))
    return True


def guidance(doc_type: str) -> str:
    """Few-shot prompt block of recent corrections for this doc type, or ""."""
    dq = _store.get(doc_type)
    if not dq:
        return ""
    now = time.time()
    fresh = [e for e in dq if now - e["at"] < _TTL_SECONDS]
    if not fresh:
        return ""
    lines = [
        f'- "{e["label"]}" ({e["name"]}): AI previously extracted "{e["original"]}" '
        f'but a human corrected it to "{e["corrected"]}"'
        for e in fresh[-_MAX_IN_PROMPT:]
    ]
    return (
        "PAST HUMAN CORRECTIONS on this document type. Infer the pattern behind "
        "each correction and apply the pattern — do NOT copy a corrected value "
        "into a different document; extract this document's own values:\n"
        + "\n".join(lines)
    )
