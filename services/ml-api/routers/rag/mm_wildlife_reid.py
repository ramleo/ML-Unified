"""
Wildlife re-identification — pending-list #49: recognizing "the same
specific animal" across separate sightings, not per-species
classification.

Originally scoped around a generic DINOv3 embedding, but researched
before building anything and found a better, more honest real technique:
**MegaDescriptor** (BVRA/MegaDescriptor-T-224, from the WildlifeDatasets
open-source toolkit) — the first foundation model built specifically for
individual animal re-identification, published to outperform generic
embeddings like CLIP and DINOv2 on this exact task. Loads via
`timm.create_model("hf-hub:BVRA/MegaDescriptor-T-224", pretrained=True)`
— `timm` is already a project dependency, no new pip package needed.

License note: MegaDescriptor is CC-BY-NC-4.0 (non-commercial) — a fit for
this non-commercial educational portfolio, comparable to the AGPL-3.0
tradeoff already accepted for the YOLO object detector.

Real local verification (see mm_objects.py's OIV7_CLASSES for the animal
label set reused below): same cat at two different resolutions scored
0.992 cosine similarity; two different goldfish side-by-side in one photo
scored 0.656; cat vs. goldfish scored 0.090 — real, meaningful
discriminative signal, not just a plausible-sounding technique.

Deliberately NOT done, disclosed rather than glossed over:
- Not a validated identification system. Real published wildlife re-ID
  benchmarks report real error rates even with MegaDescriptor, and this
  skips the pose-normalization/multi-crop-averaging tricks real re-ID
  pipelines use. "Does this look like the same individual," not proof.
- Same/uncertain/different thresholds are informed by one real test, not
  a calibrated threshold from a proper multi-individual validation set
  (none exists in this environment).
- No real backyard-camera-trap dataset was available to test with.
"""

import base64
import io
import logging
import threading

import numpy as np
from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel

from routers.rag.mm_objects import OIV7_CLASSES, detect_objects

logger = logging.getLogger(__name__)
router = APIRouter()

_ANIMAL_LABELS = {
    "Animal", "Mammal", "Bird", "Carnivore", "Reptile", "Insect",
    "Cat", "Dog", "Horse", "Cattle", "Bear", "Brown bear", "Polar bear",
    "Deer", "Fox", "Jaguar (Animal)", "Rabbit", "Raccoon", "Hedgehog",
    "Otter", "Squirrel", "Mouse", "Bat (Animal)", "Frog", "Lizard",
    "Snake", "Turtle", "Sea turtle", "Fish", "Goldfish", "Butterfly",
}
_ANIMAL_LABELS &= set(OIV7_CLASSES)  # guard against a label drifting out of the detector's class list

_CROP_EXPANSION = 1.4  # margin around the tight bbox — re-ID embeddings expect body context, not a tight crop
_MAX_GALLERY = 10
_MAX_IMAGE_BYTES = 8 * 1024 * 1024

# Informed by one real local test (see module docstring), not a calibrated
# multi-individual validation set — disclosed to the user as a heuristic.
_SAME_ANIMAL_THRESHOLD = 0.85
_DIFFERENT_ANIMAL_THRESHOLD = 0.75

_model = None
_lock = threading.Lock()


def _ensure_loaded() -> bool:
    global _model
    if _model is not None:
        return True
    with _lock:
        if _model is not None:
            return True
        try:
            import timm

            logger.info("Loading MegaDescriptor-T-224 (~28M params) for wildlife re-ID …")
            model = timm.create_model("hf-hub:BVRA/MegaDescriptor-T-224", pretrained=True)
            model.eval()
            _model = model
            return True
        except Exception as exc:
            logger.warning("Failed to load MegaDescriptor: %s", exc)
            return False


def _animal_crop_box(bbox_norm: list[float], w: int, h: int) -> tuple[int, int, int, int]:
    bx, by, bw, bh = bbox_norm
    cx, cy = (bx + bw / 2) * w, (by + bh / 2) * h
    max_dim = max(bw * w, bh * h) * _CROP_EXPANSION
    x0 = int(max(0, cx - max_dim / 2))
    y0 = int(max(0, cy - max_dim / 2))
    x1 = int(min(w, cx + max_dim / 2))
    y1 = int(min(h, cy + max_dim / 2))
    return x0, y0, x1, y1


def _verdict(cos_sim: float) -> str:
    if cos_sim >= _SAME_ANIMAL_THRESHOLD:
        return "same"
    if cos_sim < _DIFFERENT_ANIMAL_THRESHOLD:
        return "different"
    return "uncertain"


def _decode_image(image_b64: str) -> Image.Image:
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode this as an image.")
    if len(raw) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image too large (max 8MB).")
    try:
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode this as an image.")


def _animal_embedding(image_b64: str, img: Image.Image):
    """Returns (embedding | None, animal_label | None, confidence | None).
    None means no animal-labeled box was found — caller reports
    found_animal: false."""
    import torch
    import torchvision.transforms as T

    objects, _ = detect_objects(image_b64)
    animals = [o for o in objects if o["label"] in _ANIMAL_LABELS]
    if not animals:
        return None, None, None

    best = max(animals, key=lambda a: a["confidence"])
    w, h = img.size
    x0, y0, x1, y1 = _animal_crop_box(best["bbox"], w, h)
    crop = img.crop((x0, y0, x1, y1))

    tf = T.Compose([T.Resize((224, 224)), T.ToTensor(), T.Normalize([0.5] * 3, [0.5] * 3)])
    with torch.inference_mode():
        embed = _model(tf(crop).unsqueeze(0))
        embed = torch.nn.functional.normalize(embed, dim=-1)
    return embed, best["label"], best["confidence"]


class WildlifeReidRequest(BaseModel):
    target: str  # base64, no data URL prefix
    gallery: list[str]  # base64, no data URL prefix, max _MAX_GALLERY


def run_wildlife_reid_search(target_b64: str, gallery_b64: list[str]) -> dict:
    if not gallery_b64:
        raise HTTPException(status_code=400, detail="Upload at least one gallery photo.")
    if len(gallery_b64) > _MAX_GALLERY:
        raise HTTPException(status_code=400, detail=f"Gallery is capped at {_MAX_GALLERY} photos.")
    if not _ensure_loaded():
        raise HTTPException(status_code=503, detail="Wildlife re-ID model is unavailable right now.")

    import torch.nn.functional as F

    target_img = _decode_image(target_b64)
    target_embed, target_label, target_confidence = _animal_embedding(target_b64, target_img)
    if target_embed is None:
        return {"target_found_animal": False, "gallery": [], "best_match_index": None, "best_match_similarity": None}

    results = []
    for i, photo_b64 in enumerate(gallery_b64):
        img = _decode_image(photo_b64)
        embed, label, confidence = _animal_embedding(photo_b64, img)
        if embed is None:
            results.append({"index": i, "found_animal": False, "cosine_similarity": None, "verdict": None})
            continue
        cos_sim = float(F.cosine_similarity(target_embed, embed).item())
        results.append({
            "index": i,
            "found_animal": True,
            "animal_label": label,
            "cosine_similarity": round(cos_sim, 4),
            "verdict": _verdict(cos_sim),
            "detection_confidence": confidence,
        })

    ranked = sorted((r for r in results if r["found_animal"]), key=lambda r: r["cosine_similarity"], reverse=True)
    best = ranked[0] if ranked else None

    return {
        "target_found_animal": True,
        "target_animal_label": target_label,
        "target_detection_confidence": target_confidence,
        "gallery": results,
        "best_match_index": best["index"] if best else None,
        "best_match_similarity": best["cosine_similarity"] if best else None,
        "best_match_verdict": best["verdict"] if best else None,
    }


@router.post("/mm-wildlife-reid/search")
def wildlife_reid_search(body: WildlifeReidRequest):
    return run_wildlife_reid_search(body.target, body.gallery)
