"""TEXT-vs-GRAPHIC classification + brand/logo description for a sharpened
region, split out of mm_deblur.py to keep that file under the project's
400-line cap. Also asks for a description in the SAME call, used only on
the graphic branch — an earlier version made this a separate second
vision-cascade call, which caused a real regression caught live: Groq (that
cascade's first leg) is rate-limited/over-capacity on most calls in
production, and each failed Groq attempt costs ~30s before falling back to
Mistral; two such calls back to back pushed total region-sharpen latency to
~70s, past the frontend's 60s abort timeout, surfacing as a false
"temporarily unavailable" even though the backend was still working and did
eventually succeed. One combined call restores the original latency budget.

Calls Gemini directly (gemini-3.6-flash, a plain image-understanding model —
different from mm_deblur.py's gemini-3.1-flash-lite-image, which generates a
new image rather than just reading one) instead of _vision_cascade_raw's
Groq-first cascade: caught live giving a real Nissan-badge crop a wrong
answer ("black and white abstract pattern") — Groq's qwen3.6-27b and
Mistral's mistral-medium-latest are both meaningfully weaker at this than
Gemini, and since this whole feature is already Gemini-paid for the sharpen
call itself, routing identification through the free-tier cascade was
optimizing for the wrong thing (occasional cost savings on a call that's
small next to the image-generation cost already being paid regardless).

The description itself is a single, uncorroborated AI opinion (there's no
independent-agreement check for free-text description the way there is for
OCR'd text), so it's surfaced labeled as an identification to verify, never
as an asserted fact.
"""
from __future__ import annotations

import json
import re

_VISION_MODEL = "gemini-3.6-flash"
_VISION_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{_VISION_MODEL}:generateContent"

_CLASSIFY_DESCRIBE_PROMPT = (
    "Look at this image and answer in exactly this two-line format:\n"
    "TYPE: TEXT or GRAPHIC\n"
    "DESCRIPTION: <a short phrase describing what the image shows; name the "
    "specific object, brand, or logo if you recognize it>\n"
    "TYPE is TEXT if the image contains real, readable printed or "
    "handwritten text (a label, sign, plate, or document text). Otherwise "
    "it is GRAPHIC (a logo, emblem, icon, or pattern with no real readable "
    "text)."
)


def _call_gemini_vision(key: str, image_b64: str, prompt: str) -> str:
    import httpx

    with httpx.Client(timeout=30) as client:
        res = client.post(
            _VISION_URL,
            params={"key": key},
            json={"contents": [{"role": "user", "parts": [
                {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                {"text": prompt},
            ]}]},
        )
        res.raise_for_status()
        parts = res.json()["candidates"][0]["content"]["parts"]
    for part in parts:
        text = part.get("text")
        if text:
            return text
    return ""


def classify_and_describe(key: str, region_b64: str) -> tuple[bool, str | None]:
    """Returns (is_text, description). Defaults to (True, None) — assume
    real text, no description — on any failed/ambiguous answer: the safer
    default, since it keeps the existing "low confidence, disagreed"
    warning rather than silently downgrading a genuine disagreement to the
    softer generic caption."""
    try:
        answer = _call_gemini_vision(key, region_b64, _CLASSIFY_DESCRIBE_PROMPT).strip()
    except Exception:
        return True, None
    if not answer:
        return True, None

    type_val: str | None = None
    desc_val: str | None = None
    if answer.startswith("{"):
        try:
            parsed = json.loads(answer)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    if not isinstance(v, str) or not v.strip():
                        continue
                    if type_val is None and "type" in k.lower():
                        type_val = v
                    elif desc_val is None and "desc" in k.lower():
                        desc_val = v
        except ValueError:
            pass
    if type_val is None:
        m = re.search(r"TYPE:\s*(\w+)", answer, re.IGNORECASE)
        type_val = m.group(1) if m else None
    if desc_val is None:
        m = re.search(r"DESCRIPTION:\s*(.+)", answer, re.IGNORECASE)
        desc_val = m.group(1).strip() if m else None
    is_text = not (type_val and "GRAPHIC" in type_val.upper())
    # Guard against a malformed/truncated answer (caught live: "**" with no
    # actual words, likely stray markdown emphasis markers around content
    # the model cut short) — no letters at all means nothing worth showing.
    if desc_val is not None and not re.search(r"[A-Za-z]", desc_val):
        desc_val = None
    return is_text, (desc_val or None)