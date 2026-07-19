"""In-memory result cache for document analysis, keyed by file-content hash.

Re-uploading the same file re-runs the whole LLM pipeline and burns provider
quota. Cache the finished result and replay it instantly instead. Bounded and
TTL'd; lives in process memory so a Space restart clears it — acceptable.
"""
from __future__ import annotations

import hashlib
import threading
import time

_TTL_SECONDS = 6 * 3600
_MAX_ENTRIES = 10  # page_images make entries heavy (~1-2 MB each)

_lock = threading.Lock()
_store: dict[str, tuple[float, dict]] = {}


def make_key(file_bytes: bytes, doc_type_hint: str, provider: str) -> str:
    digest = hashlib.sha256(file_bytes).hexdigest()
    return f"{digest}:{doc_type_hint}:{provider}"


def get(key: str) -> dict | None:
    with _lock:
        item = _store.get(key)
        if not item:
            return None
        ts, payload = item
        if time.time() - ts > _TTL_SECONDS:
            del _store[key]
            return None
        return payload


def put(key: str, payload: dict) -> None:
    with _lock:
        _store[key] = (time.time(), payload)
        while len(_store) > _MAX_ENTRIES:
            oldest = min(_store, key=lambda k: _store[k][0])
            del _store[oldest]
