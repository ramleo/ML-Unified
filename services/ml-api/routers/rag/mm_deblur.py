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
region of interest and pasting the result back (bbox + a small paste margin,
see `_PASTE_MARGIN`) means a hallucination in one region can never silently
alter unrelated parts of the image. The margin exists because a box drawn
pixel-tight around text can otherwise clip a character at its own edge even
when the model reconstructed it correctly — caught live testing a properly
recovered "INVOICE #4471": the model's own output had the full text, but a
too-tight test bbox meant the paste-back cut it off before the final "1".

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
import re
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel

from routers.document._vision import mistral_ocr_pages
from routers.rag._image_gen_budget import check_and_record_call
from routers.rag.mm_caption import clean_ocr_text
from routers.rag.mm_deblur_classify import classify_and_describe

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

# Implicit margin (as a fraction of the drawn box's own size) added to what
# actually gets pasted back, beyond the caller's literal bbox — NOT the same
# as _CONTEXT_PAD (model-context-only, never pasted). Found necessary live:
# a box drawn pixel-tight around text can clip a character at its own edge
# even though the model reconstructed it correctly just outside that edge,
# because the paste-back honored the literal box exactly. A person drawing a
# box around text almost always draws it a little tight, not generous, so a
# margin removes that papercut for most real boxes while staying well short
# of whole-image risk. Raised from an initial 0.08 to 0.20 after 0.08 still
# clipped a real, only-moderately-tight drawn box live (right edge landed at
# 0.646 of image width when the text needed ~0.67) — 0.08 rescued a slightly
# looser box but wasn't enough margin for a realistic freehand drag.
_PASTE_MARGIN = 0.20

# How similar the two independent OCR readings need to be (difflib ratio,
# 0-1) to count as agreement. Calibrated loose on purpose — real OCR of the
# same true text across two slightly-different renders still varies in
# spacing/case/minor misreads; this only needs to catch the case where the
# two readings are substantively DIFFERENT content (a real disagreement),
# not cosmetic OCR noise.
_AGREEMENT_THRESHOLD = 0.7

# Minimum stripped-character length an OCR reading needs before it counts as
# a real reading at all, for the purposes of the agreement check above. OCR
# can spuriously "read" a couple of characters out of pure visual noise (a
# grille's mesh pattern, a reflection) even on a region with no real text —
# a too-short reading isn't meaningful signal either way, so both sides must
# clear this before disagreement is treated as a real finding.
_MIN_TEXT_LEN = 4

# Tie-breaker for a genuine disagreement (both readings pass _MIN_TEXT_LEN
# but still don't match) — found live that a length threshold alone isn't
# enough: OCR can hallucinate a full FAKE sentence (not just a few noise
# characters) out of a pure graphic. One real case: the same car-grille crop
# read as "- 2017年" on one attempt and "- *The New York Times* (1995)" on
# the other — both well past _MIN_TEXT_LEN, both completely fabricated. This
# asks directly whether it's actually text at all, rather than continuing to
# infer that indirectly from OCR's own output. See mm_deblur_classify.py for
# the classification/description call itself.


class DeblurRequest(BaseModel):
    image: str  # b64 PNG, the current citation page/frame image (post-edit if any)
    # [x, y, w, h], normalized 0-1, page-relative — same convention as every
    # other bbox in this app (see Bbox in the frontend's _types.ts). When
    # given, only this region (plus a small paste margin, see _PASTE_MARGIN)
    # is sent to the model and pasted back; every pixel further out stays
    # byte-identical to the input. None means whole-image sharpen.
    bbox: list[float] | None = None


def _call_gemini(key: str, image_b64: str) -> str:
    import httpx

    check_and_record_call("deblur")
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


_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_TABLE_SEP_RE = re.compile(r"^[\s|:-]+$")


def _strip_markdown_table(text: str) -> str:
    """Mistral OCR sometimes wraps a short bordered snippet — a license
    plate, a small label or logo box — in pipe-table markdown syntax even
    though it isn't really tabular data (observed live on a plate crop:
    "| LXI7 PYD |\\n| --- |"). Left as-is, that raw markdown leaks into the
    corroboration message shown to the user. Flattens any pipe-table rows
    down to their plain cell text and drops separator rows entirely."""
    out_lines = []
    for line in text.split("\n"):
        m = _TABLE_ROW_RE.match(line)
        if not m:
            out_lines.append(line)
            continue
        if _TABLE_SEP_RE.match(m.group(1)):
            continue
        cells = [c.strip() for c in m.group(1).split("|") if c.strip()]
        if cells:
            out_lines.append(" ".join(cells))
    return "\n".join(l for l in out_lines if l.strip())


def _ocr_text(img: Image.Image) -> str:
    md, _ = mistral_ocr_pages([_pil_to_b64(img)])
    return _strip_markdown_table(clean_ocr_text(md))


def _sharpen_region(key: str, image_b64: str, bbox: list[float]) -> dict:
    """Crops bbox (+ context padding) out of `image_b64`, sharpens it via TWO
    independent Gemini calls, and pastes ONE of the results back into the
    full original image at (bbox + a small paste margin, see _PASTE_MARGIN)
    — every pixel further out than that stays byte-identical to the input,
    by construction. OCR-reads each independent result and compares them:
    agreement -> confidence "high" plus the corroborated text; disagreement
    -> confidence "low", no text asserted (see module docstring for why this
    is the actual mechanism, not just a disclaimer)."""
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

    # The actual paste-back rect: bbox expanded by _PASTE_MARGIN, clamped to
    # the padded crop above (can never exceed what was actually sent to the
    # model) and to the image bounds.
    margin_x, margin_y = pw * _PASTE_MARGIN, ph * _PASTE_MARGIN
    paste_left = max(left, int(px - margin_x))
    paste_top = max(top, int(py - margin_y))
    paste_right = min(right, int(px + pw + margin_x))
    paste_bottom = min(bottom, int(py + ph + margin_y))
    rel_left, rel_top = paste_left - left, paste_top - top
    rel_right, rel_bottom = paste_right - left, paste_bottom - top

    def _attempt() -> tuple[Image.Image, str, Image.Image]:
        result_b64 = _call_gemini(key, crop_b64)
        result_crop = Image.open(io.BytesIO(base64.b64decode(result_b64))).convert("RGB")
        # The model doesn't necessarily return the crop at its exact input
        # resolution — force it back so the paste-back coordinates line up
        # with the ORIGINAL crop's pixel grid. LANCZOS (high-quality, not
        # PIL's NEAREST default) matters here specifically: this crop was
        # JUST sharpened, so a low-quality downsample here would throw away
        # exactly the fine detail the whole point of this call was to
        # recover. Whole-image sharpen never hits this path (it returns
        # Gemini's output directly, no resize), which is why it could look
        # crisper for the same blur despite going through the same model.
        result_crop = result_crop.resize((right - left, bottom - top), Image.LANCZOS)
        region = result_crop.crop((rel_left, rel_top, rel_right, rel_bottom))
        # `region` (just the paste rect) is what OCR reads and what gets
        # pasted back — kept tight on purpose (see _PASTE_MARGIN). But it's
        # a poor input for brand/logo recognition: a badge cropped down to
        # almost nothing loses exactly the surrounding context (grille
        # shape, position on the car) a vision model needs to recognize it,
        # the same reason whole-image sharpen could correctly read "NISSAN"
        # elsewhere in a full photo. `result_crop` (the full _CONTEXT_PAD'd
        # crop actually sent to Gemini) keeps that context — used ONLY for
        # classification below, never for OCR or the paste-back itself.
        return region, _ocr_text(region), result_crop

    region_a, text_a, context_a = _attempt()
    region_b, text_b, context_b = _attempt()

    similarity = difflib.SequenceMatcher(None, text_a.lower(), text_b.lower()).ratio()
    # Classify BOTH independent regions concurrently (ThreadPoolExecutor, not
    # sequential) — same corroboration philosophy as the OCR check above,
    # applied here after two real bugs on a single-call classification:
    # (1) real text on an invoice occasionally misclassified as GRAPHIC
    # (~1/3 runs), silently suppressing a legitimate "high" confidence
    # result; (2) TYPE flip-flopping on a genuinely ambiguous image, at the
    # mercy of whichever single answer happened to come back. Requiring BOTH
    # calls to agree GRAPHIC before suppressing confidence means a flip
    # (TEXT then GRAPHIC, or vice versa) now resolves to the safer TEXT
    # default instead of hinging on one call. Running them concurrently
    # (not one-after-the-other) keeps the added wall-clock cost to roughly
    # ONE classify call, not two — sequential would risk reintroducing the
    # exact 60s-timeout regression this file already fixed once (see
    # _CLASSIFY_DESCRIBE_PROMPT's comment above).
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(classify_and_describe, key, _pil_to_b64(context_a))
        future_b = pool.submit(classify_and_describe, key, _pil_to_b64(context_b))
        is_text_a, desc_a = future_a.result()
        is_text_b, desc_b = future_b.result()
    # Deliberately NOT the OCR-agreement-overrides-classification approach
    # (i.e. trusting OCR agreement over a GRAPHIC verdict) — that was tried
    # and rejected: a pure graphic can make OCR hallucinate the SAME fake
    # reading twice (shared bias from one input image), which would produce
    # a false "high" asserting fabricated text as CONFIRMED, strictly worse
    # than the current false "low". Corroborating the classification call
    # itself, not overriding it with a different signal, avoids that trap.
    is_graphic = not is_text_a and not is_text_b
    description = desc_a or desc_b
    if len(text_a.strip()) < _MIN_TEXT_LEN or len(text_b.strip()) < _MIN_TEXT_LEN:
        # Neither/one reading cleared the length floor — see _MIN_TEXT_LEN.
        confidence = None
    elif is_graphic:
        # Checked BEFORE looking at agreement, on purpose — an earlier
        # version only ran this tie-breaker on disagreement, which missed a
        # worse case caught live: on a pure graphic, OCR can hallucinate the
        # SAME fake reading twice (shared bias from the same input image),
        # producing a false "high" that asserts fabricated text as
        # CONFIRMED — strictly worse than a false "low", which at least
        # doesn't assert anything. Confirming it's really text has to gate
        # both branches, not just the disagreement one.
        confidence = None
    elif similarity >= _AGREEMENT_THRESHOLD:
        confidence = "high"
    else:
        confidence = "low"

    # Description is only surfaced for the graphic branch — text regions
    # already have a real corroborated reading (or a real disagreement) from
    # OCR, which is a stronger signal than one uncorroborated description
    # would be.
    description = description if is_graphic else None

    base.paste(region_a, (paste_left, paste_top))
    return {
        "image": _pil_to_b64(base),
        "confidence": confidence,
        "text": text_a if confidence == "high" else None,
        "description": description,
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
    except HTTPException:
        # Preserve a deliberate error (e.g. the daily budget cap in
        # _image_gen_budget.py) as-is — only genuinely unexpected failures
        # below get flattened into the generic message.
        raise
    except Exception as exc:
        logger.warning("Deblur failed: %s", exc)
        raise HTTPException(status_code=502, detail="Sharpen is temporarily unavailable — try again in a moment.")