"""Store of human field corrections (HITL feedback loop), persisted to a JSON
file on disk.

When a user edits an extracted field in the UI, the (original → corrected)
pair is recorded per document type. Recent pairs are injected into future
extraction prompts as few-shot guidance, so the model "learns" from human
corrections with zero training infrastructure. File-backed so corrections
survive a plain process restart; a rebuild/redeploy that recreates the
container resets the file. Swap for a real DB (e.g. SQLite) if this needs to
survive redeploys or scale beyond one instance — the add()/guidance() API
would not need to change.
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from pathlib import Path

logger = logging.getLogger(__name__)

_MAX_PER_TYPE = 12   # corrections kept per document type
_MAX_IN_PROMPT = 8   # most recent pairs injected into the prompt
_TTL_SECONDS = 7 * 24 * 3600

_STORE_PATH = Path(os.environ.get("CORRECTIONS_STORE_PATH",
                                  Path(__file__).parent / "_corrections_store.json"))


def _load() -> dict[str, deque]:
    try:
        raw = json.loads(_STORE_PATH.read_text())
        return {dt: deque(entries, maxlen=_MAX_PER_TYPE) for dt, entries in raw.items()}
    except FileNotFoundError:
        return {}
    except Exception as exc:
        logger.warning("Corrections store unreadable, starting fresh: %s", exc)
        return {}


def _save() -> None:
    try:
        _STORE_PATH.write_text(json.dumps({dt: list(dq) for dt, dq in _store.items()}))
    except Exception as exc:
        logger.warning("Corrections store save failed: %s", exc)


_store: dict[str, deque] = _load()


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
    _save()
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
