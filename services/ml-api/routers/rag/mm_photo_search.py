"""
Photo library visual search — "find the photo with the red backpack" over an
uploaded batch of photos, no captions or tags needed.

Stateless, one-shot: a single request carries the whole photo batch AND the
query together, gets embedded with CLIP (sentence-transformers'
clip-ViT-B-32 — already a dependency for mm_similar.py's figure-similarity
feature, same model, but this module owns its own lazy singleton rather than
sharing mm_similar.py's, to keep the two features decoupled), ranked by
cosine similarity against each photo's image embedding, and returned sorted
best-match-first. No database, no persistence — this isn't a searchable
corpus that outlives one request, just a batch job over whatever photos were
uploaded this time.

The query is either TEXT ("a red backpack") or IMAGE (a reference photo from
the same uploaded batch, base64 — "find more like this one"). Both land in
the same CLIP embedding space, so ranking logic is identical either way;
only which encoder call produces the query vector differs. When the
reference photo is itself one of the uploaded batch, the caller passes its
filename as `exclude_filename` so the trivial, uninteresting 100%
self-match doesn't show up in its own results.

Also exposes duplicate detection over the same embeddings — no separate
model or query needed, since "does this batch contain near-identical
photos" is just "are any two embeddings almost the same vector," a byproduct
of embedding the batch that search already does anyway.

An optional `exclude_query` steers ranking away from a second concept
("beach photos" excluding "people") via standard CLIP embedding-space
vector arithmetic (query direction minus exclude direction) — see
search_photos()'s inline comment for why this is steering, not a hard
filter.
"""

import base64
import io
import logging
import threading

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from security.file_gate import scan_upload_bytes

logger = logging.getLogger(__name__)
router = APIRouter()

_model = None
_lock = threading.Lock()

_MAX_PHOTOS = 40
_MAX_IMAGE_BYTES = 8 * 1024 * 1024


def _ensure_loaded() -> bool:
    """Lazy-load CLIP on first use — most sessions never open this tool."""
    global _model
    if _model is not None:
        return True
    with _lock:
        if _model is not None:
            return True
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading clip-ViT-B-32 (~350 MB) for photo search …")
            _model = SentenceTransformer("clip-ViT-B-32", device="cpu")
            return True
        except Exception as exc:
            logger.warning("CLIP load failed — photo search disabled: %s", exc)
            return False


class PhotoItem(BaseModel):
    filename: str
    image: str  # base64, no data URL prefix


class SearchRequest(BaseModel):
    photos: list[PhotoItem]
    query: str | None = None
    query_image: str | None = None  # base64 of a reference photo — mutually exclusive with query
    exclude_filename: str | None = None  # the reference photo's own filename, if query_image is one of `photos`
    exclude_query: str | None = None  # text to steer AWAY from, e.g. "people" for "beach, but not people"


class DuplicatesRequest(BaseModel):
    photos: list[PhotoItem]
    threshold: float = 0.97


def _decode_and_embed(photos: list[PhotoItem], path: str = "/rag/mm-photo-search") -> tuple[list, list[str], int]:
    """Shared by search and duplicate-detection: decode each photo, drop
    anything invalid/oversized, and CLIP-embed the rest in one batched call.
    Returns (embeddings, filenames-in-the-same-order, skipped-count)."""
    if not photos:
        raise HTTPException(status_code=400, detail="at least one photo is required")
    if len(photos) > _MAX_PHOTOS:
        raise HTTPException(status_code=400, detail=f"max {_MAX_PHOTOS} photos per request")
    if not _ensure_loaded():
        raise HTTPException(status_code=503, detail="Photo search model is unavailable right now.")

    from PIL import Image

    images = []
    filenames = []
    skipped = 0
    for p in photos:
        try:
            raw = base64.b64decode(p.image, validate=True)
            if len(raw) > _MAX_IMAGE_BYTES:
                skipped += 1
                continue
            scan_upload_bytes(raw, path=path)
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            images.append(img)
            filenames.append(p.filename)
        except Exception:
            skipped += 1

    if not images:
        raise HTTPException(status_code=400, detail="No valid images could be decoded from the upload.")

    image_embeds = _model.encode(images, batch_size=8, convert_to_numpy=True, show_progress_bar=False)
    return image_embeds, filenames, skipped


def search_photos(
    photos: list[PhotoItem],
    query: str | None = None,
    query_image: str | None = None,
    exclude_filename: str | None = None,
    exclude_query: str | None = None,
) -> dict:
    query = (query or "").strip()
    if not query and not query_image:
        raise HTTPException(status_code=400, detail="query or query_image is required")

    image_embeds, filenames, skipped = _decode_and_embed(photos, path="/rag/mm-photo-search/search")

    from PIL import Image

    if query_image:
        try:
            raw = base64.b64decode(query_image, validate=True)
            scan_upload_bytes(raw, path="/rag/mm-photo-search/search")
            ref_img = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception:
            raise HTTPException(status_code=400, detail="Could not decode the reference image.")
        query_embed = _model.encode([ref_img], convert_to_numpy=True, show_progress_bar=False)[0]
    else:
        query_embed = _model.encode([query], convert_to_numpy=True, show_progress_bar=False)[0]

    exclude_query = (exclude_query or "").strip()
    if exclude_query:
        # Standard CLIP "vector arithmetic" exclusion technique: normalize
        # both the query and exclude-term embeddings, then subtract the
        # exclude direction out of the query direction before re-normalizing
        # below. This steers ranking AWAY from the excluded concept rather
        # than literally filtering it out — a photo strongly matching both
        # ("a red car" excluding "vehicles") can still rank low, since the
        # subtraction weakens the whole query direction, not just the
        # excluded part. Applies after either a text or image query, since
        # by this point it's just a vector regardless of source.
        exclude_embed = _model.encode([exclude_query], convert_to_numpy=True, show_progress_bar=False)[0]
        q_unit = query_embed / np.linalg.norm(query_embed)
        e_unit = exclude_embed / np.linalg.norm(exclude_embed)
        query_embed = q_unit - e_unit

    img_norms = image_embeds / np.linalg.norm(image_embeds, axis=1, keepdims=True)
    query_norm = query_embed / np.linalg.norm(query_embed)
    scores = img_norms @ query_norm

    results = sorted(
        [{"filename": f, "score": round(float(s), 4)} for f, s in zip(filenames, scores) if f != exclude_filename],
        key=lambda r: r["score"], reverse=True,
    )
    return {"results": results, "skipped": skipped}


def find_duplicates(photos: list[PhotoItem], threshold: float = 0.97) -> dict:
    """Groups near-identical photos in the batch by CLIP embedding cosine
    similarity — no query needed. threshold=0.97 sits inside the commonly
    cited range for CLIP-based image dedup (~0.95 for "same shot, different
    moment", ~0.99 for stricter exact-duplicate filtering) — not a value
    tuned against this specific tool's traffic, since no labeled
    duplicate-photo dataset exists here. Confirmed during development that
    synthetic test images (flat solid colors, random noise) are a poor
    proxy for calibrating this — CLIP embeds those out-of-distribution
    inputs unnaturally close together regardless of real content, so a
    batch of near-blank or textureless real photos (a plain white wall,
    a screenshot of solid UI) could still over-group here; real photos with
    normal visual complexity are the case this threshold is meant for.
    Greedy union-find, deliberately simple for a batch capped at
    _MAX_PHOTOS. Singleton "groups" (nothing similar enough to any other
    photo) are dropped — they're not duplicates of anything, not worth
    reporting."""
    image_embeds, filenames, skipped = _decode_and_embed(photos, path="/rag/mm-photo-search/duplicates")

    n = len(filenames)
    norms = image_embeds / np.linalg.norm(image_embeds, axis=1, keepdims=True)
    sim_matrix = norms @ norms.T

    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i in range(n):
        for j in range(i + 1, n):
            if sim_matrix[i][j] >= threshold:
                union(i, j)

    clusters: dict[int, list[str]] = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(filenames[i])

    groups = [members for members in clusters.values() if len(members) > 1]
    return {"groups": groups, "skipped": skipped}


@router.post("/mm-photo-search/search")
def photo_search(body: SearchRequest):
    return search_photos(body.photos, body.query, body.query_image, body.exclude_filename, body.exclude_query)


@router.post("/mm-photo-search/duplicates")
def photo_duplicates(body: DuplicatesRequest):
    return find_duplicates(body.photos, body.threshold)
