"""Tiny ingestion cache for mm_ingest.py — separate from document/_cache.py
(own capacity/TTL). Caches only the EXPENSIVE-to-produce artifacts (vision
captioning); split out of mm_ingest.py to stay under the project's
file-length limit."""
from __future__ import annotations

import hashlib
import time

_CACHE_TTL = 24 * 3600
_CACHE_MAX = 4
_cache: dict[str, tuple[float, dict]] = {}


def cache_key(file_bytes: bytes, embedding_mode: str) -> str:
    digest = hashlib.sha256(file_bytes).hexdigest()
    return f"{digest}:{embedding_mode}"


def cache_get(key: str) -> dict | None:
    item = _cache.get(key)
    if not item:
        return None
    ts, payload = item
    if time.time() - ts > _CACHE_TTL:
        del _cache[key]
        return None
    return payload


def cache_put(key: str, payload: dict) -> None:
    _cache[key] = (time.time(), payload)
    while len(_cache) > _CACHE_MAX:
        oldest = min(_cache, key=lambda k: _cache[k][0])
        del _cache[oldest]
