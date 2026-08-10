"""Sharpen/deblur a citation image (or just one region of it) via Gemini
image editing — same paid model and call pattern as mm_ai_fill.py
(gemini-3.1-flash-lite-image, GEMINI_API_KEY). This is generative, not true
deconvolution: it can invent plausible-but-wrong detail on content that's
genuinely lost to blur, rather than admitting it can't tell. Verified live
before shipping: a synthetic Gaussian-blurred test image (invoice number,
amount, date) came back sharp and byte-correct. A public discriminative
alternative (NAFNet, no hallucination risk) was also tested live and barely
improved legibility — not good enough to ship on its own. The frontend must
label the result "AI-enhanced — verify against original" and let the user
compare against the original rather than silently replacing it.

The hallucination risk isn't hypothetical — caught live on a real photo of
a car with a deliberately blurred logo/plate: whole-image sharpen correctly
restored the "NISSAN" logo (present elsewhere in sharp detail across the
same photo, e.g. the grille badge, so the model had real evidence to work
from) but invented text on the plate, which was blurred with genuinely no
legible content underneath for the model to recover — two separate whole-
image runs invented two DIFFERENT plate readings (once in Devanagari
script, once Latin-alphanumeric), proving neither was a real recovery.

`bbox`-scoped sharpening narrows the blast radius: cropping to just the
region of interest and pasting the result back pixel-exact everywhere
outside that box means a hallucination in one region can never silently
alter unrelated parts of the image.

Region-scoped requests also get a corroboration check (`_sharpen_region`),
modeled on how real forensic recovery actually works — investigators trust
agreement between independent sources (multiple frames, cross-referenced
records), never a single generative guess. Gemini is called TWICE
independently on the same crop; OCR (Mistral, already used elsewhere in
this app's ingest path) reads the region out of each result; if the two
readings agree, that's real corroboration (confidence "high", the read text
is returned); if they disagree, that's the signal neither can be trusted
(confidence "low", no text asserted). The two whole-image plate runs above
are exactly the disagreement case this is designed to catch.
"""
from __future__ import annotations

import base64
import difflib
import io
import logging
import os

from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel

from routers.document._vision import mistral_ocr_pages

logger = logging.getLogger(__name__)

router = APIRouter()

_MODEL = "gemini-3.1-flash-lite-image"
_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL}:generateContent"

_INSTRUCTION = (
    "This image is blurry or out of focus. Sharpen it and remove the blur "
    "so any text and fine detail becomes clearly legible. Do not add, "
    "remove, or change any content, composition, colors, or layout — only "
    "restore clarity and focus. If any specific area is too blurry to "
    "determine its real content with genuine confidence (e.g. small printed "
    "text or a label), render that area as a plausible sharpened texture "
    "WITHOUT inventing specific readable text, numbers, or symbols you "
    "cannot actually make out — leaving it a bit soft is better than "
    "confidently guessing wrong."
)

# Extra margin (as a fraction of the selected box's own size) cropped around
# a region-scoped request before sending to Gemini — pure model context so
# it can match surrounding lighting/style/texture, never part of what gets
# pasted back. Only the caller's exact bbox is written into the result.
_CONTEXT_PAD = 0.25

# How similar the two independent OCR readings need to be (difflib ratio,
# 0-1) to count as agreement. Calibrated loose on purpose — real OCR of the
# same true text across two slightly-different renders still varies in
# spacing/case/minor misreads; this only needs to catch the case where the
# two readings are substantively DIFFERENT content (a real disagreement),
# not cosmetic OCR noise.
_AGREEMENT_THRESHOLD = 0.7


class DeblurRequest(BaseModel):
    image: str  # b64 PNG, the current citation page/frame image (post-edit if any)
    # [x, y, w, h], normalized 0-1, page-relative — same convention as every
    # other bbox in this app (see Bbox in the frontend's _types.ts). When
    # given, only this region is sent to the model and pasted back; every
    # other pixel in the returned image is byte-identical to the input.
    # None means whole-image sharpen, the original behavior.
    bbox: list[float] | None = None


def _call_gemini(key: str, image_b64: str) -> str:
    import httpx

    with httpx.Client(timeout=60) as client:
        res = client.post(
            _URL,
            params={"key": key},
            json={"contents": [{"role": "user", "parts": [
                {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                {"text": _INSTRUCTION},
            ]}]},
        )
        res.raise_for_status()
        parts = res.json()["candidates"][0]["content"]["parts"]

    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return inline["data"]
    raise ValueError("Gemini response had no image part")


def _pil_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _ocr_text(img: Image.Image) -> str:
    md, _ = mistral_ocr_pages([_pil_to_b64(img)])
    return md.strip()


def _sharpen_region(key: str, image_b64: str, bbox: list[float]) -> dict:
    """Crops bbox (+ context padding) out of `image_b64`, sharpens it via TWO
    independent Gemini calls, and pastes ONE of the results back into the
    full original image at the exact same pixel rect — every pixel outside
    bbox stays byte-identical to the input, by construction. OCR-reads each
    independent result and compares them: agreement -> confidence "high"
    plus the corroborated text; disagreement -> confidence "low", no text
    asserted (see module docstring for why this is the actual mechanism,
    not just a disclaimer)."""
    base = Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")
    w, h = base.size
    x, y, bw, bh = bbox
    px, py, pw, ph = x * w, y * h, bw * w, bh * h
    pad_x, pad_y = pw * _CONTEXT_PAD, ph * _CONTEXT_PAD
    left, top = max(0, int(px - pad_x)), max(0, int(py - pad_y))
    right, bottom = min(w, int(px + pw + pad_x)), min(h, int(py + ph + pad_y))
    if right <= left or bottom <= top:
        raise ValueError("Selected region is empty")

    crop = base.crop((left, top, right, bottom))
    crop_b64 = _pil_to_b64(crop)

    rel_left, rel_top = int(px) - left, int(py) - top
    rel_right, rel_bottom = rel_left + int(pw), rel_top + int(ph)

    def _attempt() -> tuple[Image.Image, str]:
        result_b64 = _call_gemini(key, crop_b64)
        result_crop = Image.open(io.BytesIO(base64.b64decode(result_b64))).convert("RGB")
        # The model doesn't necessarily return the crop at its exact input
        # resolution — force it back so the paste-back coordinates line up
        # with the ORIGINAL crop's pixel grid.
        result_crop = result_crop.resize((right - left, bottom - top))
        region = result_crop.crop((rel_left, rel_top, rel_right, rel_bottom))
        return region, _ocr_text(region)

    region_a, text_a = _attempt()
    region_b, text_b = _attempt()

    similarity = difflib.SequenceMatcher(None, text_a.lower(), text_b.lower()).ratio()
    agrees = bool(text_a) and similarity >= _AGREEMENT_THRESHOLD
    confidence = "high" if agrees else "low"

    base.paste(region_a, (int(px), int(py)))
    return {
        "image": _pil_to_b64(base),
        "confidence": confidence,
        "text": text_a if agrees else None,
    }


@router.post("/mm-deblur")
def deblur_image(body: DeblurRequest):
    """Returns {"image": <b64>} for a whole-image sharpen, or
    {"image", "confidence", "text"} for a region-scoped one — best-effort,
    never persisted server-side, same disposable-edit contract as
    /mm-inpaint and /mm-ai-fill."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise HTTPException(status_code=502, detail="Sharpen is not configured (missing GEMINI_API_KEY).")

    try:
        if body.bbox:
            return _sharpen_region(key, body.image, body.bbox)
        return {"image": _call_gemini(key, body.image)}
    except Exception as exc:
        logger.warning("Deblur failed: %s", exc)
        raise HTTPException(status_code=502, detail="Sharpen is temporarily unavailable — try again in a moment.")