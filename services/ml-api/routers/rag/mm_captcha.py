"""
CAPTCHA hardening research demo — educational/defensive, same spirit as
mm_adversarial.py: shows a real, published concern (modern vision-language
models read plain text CAPTCHAs far more easily than classic OCR ever
could) and demonstrates what actually degrades that.

Scope boundary, same as every other tool in this codebase: this only ever
operates on a CAPTCHA image the caller uploads. There is no live scraping
or automation against a real reCAPTCHA/hCaptcha/website challenge, and no
bulk-solving — a single user-supplied image in, a single read-attempt out.

Why the hardening here is classic/non-gradient rather than FGSM/PGD like
mm_adversarial.py: that demo attacks a local torchvision classifier it has
full gradient access to. The VLM here is called through a hosted API
(Mistral/Gemini, via `_vision_cascade_raw`) — a genuine black box with no
gradient access, which mirrors reality: a real CAPTCHA vendor doesn't know
or control which solver (human or automated) is thrown at it, so real
CAPTCHA hardening already relies on classic, model-agnostic perturbations
(noise, occlusion lines, distortion, contrast/color jitter) rather than an
attack tailored to one specific model. `_harden_image` reproduces exactly
that, at one scalar "intensity" the caller controls.

This is a read-attempt comparison, not a scored benchmark: with no ground
truth supplied, the endpoint just returns both raw VLM answers side by
side. When the caller does supply what the CAPTCHA actually says, a simple
case-insensitive match adds a correct/incorrect verdict on each attempt —
still just one image, not a statistical claim about CAPTCHAs in general.
"""
from __future__ import annotations

import base64
import io
import logging

import numpy as np
from fastapi import APIRouter
from PIL import Image, ImageDraw, ImageEnhance
from pydantic import BaseModel

from routers.document._vision import _vision_cascade_raw

logger = logging.getLogger(__name__)
router = APIRouter()

_READ_PROMPT = (
    "This image is a CAPTCHA. Reply with ONLY the exact text or characters "
    "shown in the image, nothing else — no punctuation, no explanation. If "
    "you genuinely cannot make out any characters, reply with exactly: none."
)


def _decode(b64: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")


def _encode(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _harden_image(img: Image.Image, intensity: float) -> Image.Image:
    """Stacks three classic, model-agnostic perturbations, all scaled by the
    same 0-100 intensity: Gaussian pixel noise, a sinusoidal occlusion wave,
    and a contrast/color reduction. Deliberately NOT gradient-based — see
    module docstring for why that's the honest choice against a hosted VLM.
    """
    t = max(0.0, min(100.0, intensity)) / 100.0
    out = img.copy()

    # Contrast/color jitter first (whole-image tone shift) — real CAPTCHA
    # backgrounds often desaturate/muddy the text this way.
    out = ImageEnhance.Contrast(out).enhance(1.0 - 0.5 * t)
    out = ImageEnhance.Color(out).enhance(1.0 - 0.4 * t)

    # Sinusoidal occlusion wave — a classic CAPTCHA distortion line, drawn
    # thicker and more frequent as intensity rises.
    if t > 0:
        draw = ImageDraw.Draw(out)
        w, h = out.size
        amplitude = 2 + 10 * t
        thickness = max(1, round(1 + 3 * t))
        for phase_offset, color in ((0, (60, 60, 60)), (np.pi, (200, 200, 200))):
            points = [
                (x, h / 2 + amplitude * np.sin(x / max(w, 1) * 4 * np.pi + phase_offset))
                for x in range(0, w, 2)
            ]
            draw.line(points, fill=color, width=thickness)

    # Gaussian pixel noise last, on top of everything else.
    if t > 0:
        arr = np.asarray(out).astype(np.float32)
        sigma = 45 * t
        noisy = arr + np.random.default_rng().normal(0, sigma, arr.shape)
        out = Image.fromarray(np.clip(noisy, 0, 255).astype(np.uint8))

    return out


def _read_captcha(img: Image.Image) -> str:
    answer = _vision_cascade_raw(_encode(img), _READ_PROMPT)
    return answer.strip()


class CaptchaSolveRequest(BaseModel):
    image: str  # base64, no data-URL prefix
    intensity: float = 50.0
    ground_truth: str | None = None


def _matches(answer: str, ground_truth: str) -> bool:
    norm = lambda s: "".join(s.lower().split())
    return norm(answer) == norm(ground_truth)


@router.post("/mm-captcha/solve")
def solve_captcha(req: CaptchaSolveRequest):
    original_img = _decode(req.image)
    hardened_img = _harden_image(original_img, req.intensity)

    original_answer = _read_captcha(original_img)
    perturbed_answer = _read_captcha(hardened_img)

    result: dict = {
        "original_answer": original_answer or "(no answer)",
        "perturbed_answer": perturbed_answer or "(no answer)",
        "perturbed_image": _encode(hardened_img),
    }
    gt = (req.ground_truth or "").strip()
    if gt:
        result["original_correct"] = _matches(original_answer, gt)
        result["perturbed_correct"] = _matches(perturbed_answer, gt)
    return result
