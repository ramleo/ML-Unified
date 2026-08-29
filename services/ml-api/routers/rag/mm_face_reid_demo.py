"""
Face deanonymization risk demo: the "shows the attack" counterpart to
Face Cloak's "shows the defense" (mm_face_cloak.py). Given a target photo
and a small gallery of other photos, embeds every detected face with the
same InceptionResnetV1 (VGGFace2) model face-cloak already uses and ranks
the gallery by cosine similarity to the target — a real, measured
demonstration of the embedding-similarity search that Clearview-style
re-identification systems rely on.

Reuses face-cloak's own private helpers directly (`_ensure_loaded`,
`_face_crop_box`, `_embed`, and its same/different-person thresholds) via
a plain import from `mm_face_cloak` — this module adds zero new face-
embedding code and shares the one loaded model singleton, rather than
duplicating it.

Honest scope, matching this project's established disclosure pattern: this
does NOT search the real internet or any actual person database. It
demonstrates the real underlying mechanism (embedding similarity ranking)
using only photos the user supplies in the one request — nothing is stored,
nothing is looked up anywhere else. The countermeasure demo (pairing this
with Face Cloak's existing `/mm-face-cloak/run` endpoint) is the point: run
a search, cloak the target, re-run the same search, see the match break.
"""

import base64
import io
import logging

import numpy as np
from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel

from routers.rag.mm_face_cloak import (
    _DIFFERENT_PERSON_THRESHOLD,
    _FACE_LABELS,
    _SAME_PERSON_THRESHOLD,
    _embed,
    _ensure_loaded,
    _face_crop_box,
)
from routers.rag.mm_objects import detect_objects
from security.file_gate import scan_upload_bytes

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_GALLERY = 10
_MAX_IMAGE_BYTES = 8 * 1024 * 1024


def _verdict(cos_sim: float) -> str:
    if cos_sim >= _SAME_PERSON_THRESHOLD:
        return "same"
    if cos_sim < _DIFFERENT_PERSON_THRESHOLD:
        return "different"
    return "uncertain"


def _decode_image(image_b64: str) -> Image.Image:
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode this as an image.")
    if len(raw) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image too large (max 8MB).")
    scan_upload_bytes(raw, path="/rag/mm-face-reid-demo/search")
    try:
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode this as an image.")


def _face_embedding(image_b64: str, img: Image.Image):
    """Returns (embedding | None, face_confidence | None). None means no
    face was detected in this photo — caller reports found_face: false."""
    import torch

    objects, _ = detect_objects(image_b64)
    faces = [o for o in objects if o["label"] in _FACE_LABELS]
    if not faces:
        return None, None

    best_face = max(faces, key=lambda f: f["confidence"])
    w, h = img.size
    box = _face_crop_box(best_face["bbox"], w, h)

    full_tensor = torch.from_numpy(np.asarray(img).astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0)
    with torch.no_grad():
        embed = _embed(full_tensor, box)
    return embed, best_face["confidence"]


class ReidSearchRequest(BaseModel):
    target: str  # base64, no data URL prefix
    gallery: list[str]  # base64, no data URL prefix, max _MAX_GALLERY


def run_reid_search(target_b64: str, gallery_b64: list[str]) -> dict:
    if not gallery_b64:
        raise HTTPException(status_code=400, detail="Upload at least one gallery photo.")
    if len(gallery_b64) > _MAX_GALLERY:
        raise HTTPException(status_code=400, detail=f"Gallery is capped at {_MAX_GALLERY} photos.")
    if not _ensure_loaded():
        raise HTTPException(status_code=503, detail="Face embedding model is unavailable right now.")

    import torch.nn.functional as F

    target_img = _decode_image(target_b64)
    target_embed, target_confidence = _face_embedding(target_b64, target_img)
    if target_embed is None:
        return {"target_found_face": False, "gallery": [], "best_match_index": None, "best_match_similarity": None}

    results = []
    for i, photo_b64 in enumerate(gallery_b64):
        img = _decode_image(photo_b64)
        embed, confidence = _face_embedding(photo_b64, img)
        if embed is None:
            results.append({"index": i, "found_face": False, "cosine_similarity": None, "verdict": None})
            continue
        cos_sim = float(F.cosine_similarity(target_embed, embed).item())
        results.append({
            "index": i,
            "found_face": True,
            "cosine_similarity": round(cos_sim, 4),
            "verdict": _verdict(cos_sim),
            "face_confidence": confidence,
        })

    ranked = sorted((r for r in results if r["found_face"]), key=lambda r: r["cosine_similarity"], reverse=True)
    best = ranked[0] if ranked else None

    return {
        "target_found_face": True,
        "target_face_confidence": target_confidence,
        "gallery": results,
        "best_match_index": best["index"] if best else None,
        "best_match_similarity": best["cosine_similarity"] if best else None,
        "best_match_verdict": best["verdict"] if best else None,
    }


@router.post("/mm-face-reid-demo/search")
def face_reid_search(body: ReidSearchRequest):
    return run_reid_search(body.target, body.gallery)
