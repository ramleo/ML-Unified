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
"""

import base64
import io
import logging
import threading

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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


def search_photos(
    photos: list[PhotoItem],
    query: str | None = None,
    query_image: str | None = None,
    exclude_filename: str | None = None,
) -> dict:
    query = (query or "").strip()
    if not query and not query_image:
        raise HTTPException(status_code=400, detail="query or query_image is required")
    if not photos:
        raise HTTPException(status_code=400, detail="at least one photo is required")
    if len(photos) > _MAX_PHOTOS:
        raise HTTPException(status_code=400, detail=f"max {_MAX_PHOTOS} photos per search")
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
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            images.append(img)
            filenames.append(p.filename)
        except Exception:
            skipped += 1

    if not images:
        raise HTTPException(status_code=400, detail="No valid images could be decoded from the upload.")

    image_embeds = _model.encode(images, batch_size=8, convert_to_numpy=True, show_progress_bar=False)

    if query_image:
        try:
            raw = base64.b64decode(query_image, validate=True)
            ref_img = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception:
            raise HTTPException(status_code=400, detail="Could not decode the reference image.")
        query_embed = _model.encode([ref_img], convert_to_numpy=True, show_progress_bar=False)[0]
    else:
        query_embed = _model.encode([query], convert_to_numpy=True, show_progress_bar=False)[0]

    img_norms = image_embeds / np.linalg.norm(image_embeds, axis=1, keepdims=True)
    query_norm = query_embed / np.linalg.norm(query_embed)
    scores = img_norms @ query_norm

    results = sorted(
        [{"filename": f, "score": round(float(s), 4)} for f, s in zip(filenames, scores) if f != exclude_filename],
        key=lambda r: r["score"], reverse=True,
    )
    return {"results": results, "skipped": skipped}


@router.post("/mm-photo-search/search")
def photo_search(body: SearchRequest):
    return search_photos(body.photos, body.query, body.query_image, body.exclude_filename)
