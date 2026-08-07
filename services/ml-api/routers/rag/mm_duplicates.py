"""Perceptual-hash near-duplicate detection for standalone image/video-frame
uploads (backlog item 3). Flags when a newly ingested photo is the same or a
lightly modified (resized/recompressed/cropped) copy of one already seen
earlier in the SAME session — e.g. the same receipt or ID photo submitted
twice under different filenames. Pure PIL (dHash), no new dependency and no
model to load — unlike mm_similar.py's CLIP-based *semantic* similarity,
which finds images that merely look alike, not the same source photo.

Registry is in-memory, scoped per session_id (never global) — a match only
ever compares against images the SAME caller already uploaded this session,
so two different users/sessions uploading the same fixture file never cross-
report a "duplicate" of each other's upload.
"""
from __future__ import annotations

import base64
import io
import logging
import threading

logger = logging.getLogger(__name__)

_HASH_SIZE = 8         # 8x8 -> 64-bit dHash, the standard size for this algorithm
_DUP_THRESHOLD = 10    # Hamming distance out of 64 bits; empirically survives a
                       # resave/recompress/moderate resize/crop of the same photo
_MAX_MATCHES = 4
_MAX_PER_SESSION = 300  # bounds unbounded memory growth over a very long session

_registry: dict[str, list[tuple[int, str, int]]] = {}  # session_id -> [(hash, source, page)]
_lock = threading.Lock()


def _dhash(b64: str) -> int | None:
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("L")
        img = img.resize((_HASH_SIZE + 1, _HASH_SIZE), Image.LANCZOS)
        pixels = list(img.getdata())
        bits = 0
        for row in range(_HASH_SIZE):
            row_start = row * (_HASH_SIZE + 1)
            for col in range(_HASH_SIZE):
                bits = (bits << 1) | (1 if pixels[row_start + col] > pixels[row_start + col + 1] else 0)
        return bits
    except Exception as exc:
        logger.warning("Perceptual hash failed: %s", exc)
        return None


def detect_duplicates(b64: str, source: str, page: int, session_id: str) -> list[dict]:
    """Hashes the image, compares against every image already registered for
    this session_id, registers itself, and returns up to _MAX_MATCHES
    {source, page, similarity} matches sorted best-first. [] the first time
    this hash (or anything close to it) has been seen this session."""
    if not session_id:
        return []
    digest = _dhash(b64)
    if digest is None:
        return []

    with _lock:
        seen = _registry.setdefault(session_id, [])
        matches = [
            {"source": other_source, "page": other_page, "similarity": round(1 - distance / 64, 3)}
            for other_hash, other_source, other_page in seen
            if (distance := bin(digest ^ other_hash).count("1")) <= _DUP_THRESHOLD
        ]
        seen.append((digest, source, page))
        if len(seen) > _MAX_PER_SESSION:
            del seen[0]

    matches.sort(key=lambda m: -m["similarity"])
    return matches[:_MAX_MATCHES]


def evict_duplicates(source: str) -> None:
    """Drops every registered hash for a removed document, across all
    sessions — cheap full scan, called only on the rare explicit-delete
    path (routers/rag/ingest.py's DELETE /uploads/{source}), which doesn't
    otherwise know which session_id a given source belongs to."""
    with _lock:
        for seen in _registry.values():
            seen[:] = [entry for entry in seen if entry[1] != source]


def describe_duplicates(matches: list[dict] | None) -> str:
    """Same rationale as mm_tampering.describe_tampering — baked into the
    stored chunk text (not just the LLM prompt) so groundedness/citation
    scoring, which only ever reads chunk['text'], can back a "have I seen
    this before" answer."""
    if not matches:
        return ""
    n = len(matches)
    return (f"Possible duplicate: this image closely matches {n} other page"
            f"{'s' if n != 1 else ''} already uploaded this session — may be "
            "a repeated or reused image.")


def refresh_duplicates_for_chunks(chunks: list[dict], page_images: list[str], session_id: str) -> None:
    """Re-runs duplicate detection against THIS caller's session registry for
    chunks pulled from mm_ingest's expensive-artifact cache. That cache is
    keyed only by file bytes (not session_id) — on a hit, detect_duplicates()
    is never called at all, which would silently make the single most
    obvious duplicate case (uploading the exact same file twice in one
    session) undetectable. Mutates chunks in place; cheap (dhash only, no
    vision call), safe to always run on a cache hit."""
    for chunk in chunks:
        if chunk.get("chunk_type") not in ("image", "video"):
            continue
        page = chunk.get("page") or 1
        idx = page - 1
        if idx < 0 or idx >= len(page_images):
            continue
        matches = detect_duplicates(page_images[idx], chunk["source"], page, session_id)
        chunk["duplicates"] = matches
        desc = describe_duplicates(matches)
        if desc and desc not in (chunk.get("text") or ""):
            chunk["text"] = f"{chunk['text']}\n\n{desc}" if chunk.get("text") else desc
