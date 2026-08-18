"""Species identification and visible disease/pest signs for a plant crop,
via Gemini vision (gemini-3.6-flash, plain image-understanding — same model
mm_deblur_classify.py already uses for its TEXT-vs-GRAPHIC call, different
from mm_deblur.py's image-EDITING model). The only paid-API feature in the
Plant Growth Quantification tool; everything else in mm_plant_growth*.py is
local HSV/CV, zero cost.

This is a single, uncorroborated AI opinion — there's no independent-
agreement check the way mm_deblur.py's region-sharpen has for OCR'd text, so
both fields are surfaced labeled as an identification to verify, not an
asserted fact. Species misidentification is a real, disclosed risk: many
ornamental/houseplant lookalikes (e.g. Monstera vs. Philodendron cultivars)
are genuinely hard even for a real botanist from a single photo, and a
disease/pest read from leaf discoloration alone can be confused with the
plant's own greenness_index-flagged stress (mm_plant_growth_metrics.py) —
this feature does NOT cross-reference that signal, it's an independent
opinion from the image alone.
"""
from __future__ import annotations

import logging
import os
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routers.rag._image_gen_budget import check_and_record_call

logger = logging.getLogger(__name__)

router = APIRouter()

_VISION_MODEL = "gemini-3.6-flash"
_VISION_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{_VISION_MODEL}:generateContent"

_PROMPT = (
    "You are looking at a photo of a plant. Answer in exactly this format:\n"
    "SPECIES: <common name, and scientific name in parentheses if you know it; "
    "write \"Uncertain\" if you cannot identify it with reasonable confidence>\n"
    "HEALTH: <a short phrase describing any visible signs of disease, pest damage, "
    "nutrient deficiency, or stress (e.g. yellowing, leaf spots, wilting, holes); "
    "write \"No visible issues\" if the foliage looks healthy>\n"
    "Only describe what is visibly in the photo. Do not guess at anything you "
    "cannot actually see."
)

_SPECIES_RE = re.compile(r"SPECIES:\s*(.+)", re.IGNORECASE)
_HEALTH_RE = re.compile(r"HEALTH:\s*(.+)", re.IGNORECASE)


def _call_gemini_vision(key: str, image_b64: str) -> str:
    import httpx

    with httpx.Client(timeout=30) as client:
        res = client.post(
            _VISION_URL,
            params={"key": key},
            json={"contents": [{"role": "user", "parts": [
                {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                {"text": _PROMPT},
            ]}]},
        )
        res.raise_for_status()
        parts = res.json()["candidates"][0]["content"]["parts"]
    for part in parts:
        text = part.get("text")
        if text:
            return text
    return ""


def identify_species(key: str, image_b64: str) -> dict:
    """Returns {"species": str | None, "health": str | None}. Both None on
    any failed/unparseable answer — an empty result is a more honest failure
    mode here than guessing, since this feature has no fallback signal to
    fall back to (unlike e.g. _detect_plant_boxes' detector->blob fallback)."""
    answer = _call_gemini_vision(key, image_b64).strip()
    if not answer:
        return {"species": None, "health": None}

    species_m = _SPECIES_RE.search(answer)
    health_m = _HEALTH_RE.search(answer)
    species = species_m.group(1).strip() if species_m else None
    health = health_m.group(1).strip() if health_m else None

    # Guard against a malformed/truncated answer (same defensive check
    # mm_deblur_classify.py uses) — no letters at all means nothing worth
    # showing rather than an empty or punctuation-only fragment.
    if species is not None and not re.search(r"[A-Za-z]", species):
        species = None
    if health is not None and not re.search(r"[A-Za-z]", health):
        health = None
    return {"species": species, "health": health}


class SpeciesIdRequest(BaseModel):
    image: str  # b64 image, any common format — a plant crop or whole photo


@router.post("/mm-plant-growth-species")
def plant_growth_species_endpoint(body: SpeciesIdRequest):
    if not body.image.strip():
        raise HTTPException(status_code=400, detail="missing an image")
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise HTTPException(status_code=502, detail="Species ID is not configured (missing GEMINI_API_KEY).")

    check_and_record_call("plant-species-id", pool="species_id")
    try:
        return identify_species(key, body.image)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Plant species ID failed: %s", exc)
        raise HTTPException(status_code=502, detail="Species ID is temporarily unavailable — try again in a moment.")
