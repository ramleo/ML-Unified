"""
QR code phishing/malicious-link risk scanner. Pure local heuristics — no ML
model, no external API call, and the decoded URL is never actually fetched
(only its text is analyzed), so scanning a link here can't itself visit the
destination or trigger a live payload.

Decodes QR code(s) in an uploaded image via OpenCV's built-in QRCodeDetector
(already a dependency — no pyzbar/libzbar needed), then scores each decoded
URL against structural phishing/malicious-link signals: IP-literal host,
punycode/homograph domain, "@" auth-trick URLs, known URL-shortener domains
(they hide the real destination), suspicious TLDs, plain HTTP, and
typosquatting against a small curated list of frequently-impersonated brand
domains.

This intentionally reports SIGNALS, not a verdict — same honesty pattern as
this codebase's tampering detector and signature-verification tools: when
detection is heuristic rather than ground-truth, surface what was found and
let a human weigh it, rather than claim "safe" or "malicious" outright.
"""

import base64
import logging
from ipaddress import ip_address
from urllib.parse import urlparse

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_IMAGE_BYTES = 10 * 1024 * 1024

_SHORTENER_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "ow.ly", "buff.ly",
    "rebrand.ly", "cutt.ly", "shorturl.at", "rb.gy", "tiny.cc", "s.id",
    "qr.ae", "v.gd",
}

_SUSPICIOUS_TLDS = {
    "zip", "top", "xyz", "click", "country", "gq", "cf", "tk", "ml", "ga",
    "work", "support", "loan", "win", "review", "download", "stream",
}

# A handful of frequently-impersonated brand domains, for the typosquat
# check only — NOT a claim of exhaustive brand coverage. Compared against
# the registrable root domain so real subdomains of these brands never
# false-flag (e.g. "accounts.google.com" -> root "google.com" -> exact match).
_KNOWN_BRAND_DOMAINS = {
    "paypal.com", "amazon.com", "apple.com", "microsoft.com", "google.com",
    "chase.com", "bankofamerica.com", "wellsfargo.com", "netflix.com",
    "facebook.com", "instagram.com", "whatsapp.com", "dhl.com", "fedex.com",
    "ups.com", "usps.com", "irs.gov", "linkedin.com", "dropbox.com",
    "docusign.com", "coinbase.com", "binance.com",
}

_MAX_TYPOSQUAT_DISTANCE = 2


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[-1]


def _registrable_domain(host: str) -> str:
    """Best-effort eTLD+1 without a public-suffix-list dependency — sufficient
    for the small curated brand list above (all plain .com/.gov), not a
    general-purpose PSL implementation."""
    parts = host.lower().split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()


def _analyze_url(raw: str) -> dict:
    try:
        parsed = urlparse(raw if "://" in raw else f"http://{raw}")
    except ValueError:
        return {"data": raw, "is_url": False, "risk_level": "unknown", "reasons": []}

    host = parsed.hostname or ""
    if not host:
        return {"data": raw, "is_url": False, "risk_level": "unknown", "reasons": []}

    high: list[str] = []
    medium: list[str] = []

    try:
        ip_address(host)
        high.append(f"Links directly to an IP address ({host}) instead of a domain name — legitimate brands almost never do this.")
    except ValueError:
        pass

    if "@" in raw.split("://", 1)[-1].split("/", 1)[0]:
        high.append("Contains an \"@\" before the domain — everything before the @ is ignored by browsers, a classic trick to hide the real destination after it.")

    if any(label.startswith("xn--") for label in host.split(".")):
        high.append("Uses punycode (xn--) encoding — often used to disguise a lookalike domain with characters that visually resemble a trusted brand.")

    root = _registrable_domain(host)
    if root not in _KNOWN_BRAND_DOMAINS:
        for brand in _KNOWN_BRAND_DOMAINS:
            dist = _levenshtein(root, brand)
            if 0 < dist <= _MAX_TYPOSQUAT_DISTANCE:
                high.append(f"Domain \"{root}\" closely resembles \"{brand}\" ({dist} character{'s' if dist != 1 else ''} different) — possible typosquat.")
                break

    if host in _SHORTENER_DOMAINS:
        medium.append(f"Uses a URL shortener ({host}) — the real destination is hidden until you click through.")

    if parsed.scheme == "http":
        medium.append("Uses plain HTTP, not HTTPS — traffic isn't encrypted.")

    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    if tld in _SUSPICIOUS_TLDS:
        medium.append(f"Uses a top-level domain (.{tld}) commonly abused for throwaway phishing sites.")

    risk_level = "high" if high else "medium" if medium else "low"

    return {
        "data": raw,
        "is_url": True,
        "host": host,
        "risk_level": risk_level,
        "reasons": high + medium,
    }


def scan_qr_codes(image_b64: str) -> dict:
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except Exception:
        return {"found": False, "qr_codes": [], "error": "Could not decode image data."}

    if len(raw) > _MAX_IMAGE_BYTES:
        return {"found": False, "qr_codes": [], "error": "Image too large (max 10MB)."}

    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return {"found": False, "qr_codes": [], "error": "Could not read this as an image."}

    decoded_texts: tuple = ()
    try:
        ok, decoded_texts, _points, _straight = cv2.QRCodeDetector().detectAndDecodeMulti(img)
        if not ok:
            decoded_texts = ()
    except Exception as exc:
        logger.warning("QR detectAndDecodeMulti failed: %s", exc)
        decoded_texts = ()

    results = [_analyze_url(text) for text in decoded_texts if text]
    return {"found": len(results) > 0, "qr_codes": results}


class QrScanRequest(BaseModel):
    image: str


@router.post("/mm-qr-phishing/scan")
def qr_phishing_scan(body: QrScanRequest):
    if not body.image.strip():
        raise HTTPException(status_code=400, detail="image is required")
    return scan_qr_codes(body.image)
