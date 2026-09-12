"""
QR code phishing/malicious-link risk scanner. The decoded URL is never
actually fetched by this tool — only its text is analyzed, and the optional
reputation check below is a hash-prefix lookup against Google's database,
not a page load — so scanning a link here can't itself visit the
destination or trigger a live payload.

Decodes QR code(s) in an uploaded image via OpenCV's built-in QRCodeDetector
(already a dependency — no pyzbar/libzbar needed), then scores each decoded
URL two ways:

1. Structural heuristics (pure local, always run, no API key needed):
   IP-literal host, punycode/homograph domain, "@" auth-trick URLs, known
   URL-shortener domains (they hide the real destination), suspicious TLDs,
   plain HTTP, and typosquatting against a small curated list of
   frequently-impersonated brand domains.
2. Google Safe Browsing reputation lookup and 3. RDAP domain-age lookup —
   both in mm_qr_phishing_reputation.py, see that module's docstring.

A QR payload that isn't a URL at all (Wi-Fi credentials, a contact card, a
phone/SMS/email/geo link, or plain text) skips the URL analysis entirely and
is instead labeled by type (_detect_payload_type) so the UI can say what it
actually is rather than a flat "nothing to check" — a Wi-Fi QR code in
particular gets a caution note, since scanning one auto-joins a network.

This intentionally reports SIGNALS, not a verdict — same honesty pattern as
this codebase's tampering detector and signature-verification tools: when
detection is heuristic rather than ground-truth, surface what was found and
let a human weigh it, rather than claim "safe" or "malicious" outright.
"""

import base64
import logging
import re
from ipaddress import ip_address
from urllib.parse import urlparse

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routers.rag.mm_qr_phishing_reputation import (
    _KNOWN_BRAND_DOMAINS,
    _enrich_with_reputation_and_age,
    _registrable_domain,
)
from security.file_gate import scan_upload_bytes

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


_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$")


def _looks_like_hostname(host: str) -> bool:
    """`urlparse` will happily treat arbitrary text ("just some random
    text") as a hostname if it's handed a scheme-less string with a
    fabricated http:// prefix — it doesn't validate the result actually
    looks like a domain. Real QR payloads and free-text URL input both need
    this: a QR code can encode arbitrary text, not just links, and a user
    typing into "check a URL directly" can type anything."""
    try:
        ip_address(host)
        return True
    except ValueError:
        pass
    return bool(_HOSTNAME_RE.match(host))


_PAYLOAD_TYPE_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("wifi", "Wi-Fi network credentials", re.compile(r"^WIFI:", re.IGNORECASE)),
    ("contact", "Contact card", re.compile(r"^(BEGIN:VCARD|MECARD:)", re.IGNORECASE)),
    ("email", "Email address", re.compile(r"^mailto:", re.IGNORECASE)),
    ("phone", "Phone number", re.compile(r"^tel:", re.IGNORECASE)),
    ("sms", "SMS/text message", re.compile(r"^(sms|smsto):", re.IGNORECASE)),
    ("location", "Geographic coordinates", re.compile(r"^geo:", re.IGNORECASE)),
    ("calendar", "Calendar event", re.compile(r"^BEGIN:VEVENT", re.IGNORECASE)),
]


def _detect_payload_type(raw: str) -> tuple[str, str]:
    """Best-effort label for a QR payload that isn't a URL, so the result
    card can say what it actually is instead of a flat "nothing to check".
    Falls back to "text" for anything unrecognized — still useful, since it
    tells the user their photo decoded fine and simply isn't a link."""
    stripped = raw.strip()
    for payload_type, label, pattern in _PAYLOAD_TYPE_PATTERNS:
        if pattern.match(stripped):
            return payload_type, label
    return "text", "Plain text"


def _non_url_result(raw: str, payload_type: str, payload_label: str) -> dict:
    reasons: list[str] = []
    risk_level = "unknown"
    if payload_type == "wifi":
        risk_level = "medium"
        reasons.append(
            "This QR code configures your device to join a Wi-Fi network automatically — "
            "only scan Wi-Fi QR codes from a source you trust, since a malicious one could "
            "connect you to an attacker-controlled network that can intercept your traffic."
        )
    return {
        "data": raw,
        "is_url": False,
        "host": None,
        "risk_level": risk_level,
        "reasons": reasons,
        "payload_type": payload_type,
        "payload_label": payload_label,
    }


def _analyze_url(raw: str) -> dict:
    stripped = raw.strip()
    # Check known non-web schemes (mailto:/tel:/sms:/geo:/WIFI:/vCard/vEvent) BEFORE attempting
    # URL parsing. mailto: in particular breaks the "no scheme -> assume http://" fallback below:
    # urlparse("http://mailto:x@example.com") misreads "mailto:x" as URL userinfo and "example.com"
    # as a real host, wrongly triggering the "@" auth-trick heuristic on an ordinary email QR code.
    for payload_type, label, pattern in _PAYLOAD_TYPE_PATTERNS:
        if pattern.match(stripped):
            return _non_url_result(raw, payload_type, label)

    try:
        parsed = urlparse(raw if "://" in raw else f"http://{raw}")
    except ValueError:
        parsed = None

    host = parsed.hostname if parsed else ""
    if not parsed or not host or not _looks_like_hostname(host):
        payload_type, payload_label = _detect_payload_type(raw)
        return _non_url_result(raw, payload_type, payload_label)

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
        "payload_type": "url",
        "payload_label": "Web link",
    }


def scan_qr_codes(image_b64: str) -> dict:
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except Exception:
        return {"found": False, "qr_codes": [], "reputation_checked": False, "error": "Could not decode image data."}

    if len(raw) > _MAX_IMAGE_BYTES:
        return {"found": False, "qr_codes": [], "reputation_checked": False, "error": "Image too large (max 10MB)."}

    scan_upload_bytes(raw, path="/rag/mm-qr-phishing/scan")
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return {"found": False, "qr_codes": [], "reputation_checked": False, "error": "Could not read this as an image."}

    decoded_texts: tuple = ()
    try:
        ok, decoded_texts, _points, _straight = cv2.QRCodeDetector().detectAndDecodeMulti(img)
        if not ok:
            decoded_texts = ()
    except Exception as exc:
        logger.warning("QR detectAndDecodeMulti failed: %s", exc)
        decoded_texts = ()

    results = [_analyze_url(text) for text in decoded_texts if text]
    reputation_checked = _enrich_with_reputation_and_age(results)
    return {"found": len(results) > 0, "qr_codes": results, "reputation_checked": reputation_checked}


def scan_url(raw_url: str) -> dict:
    """Same three-signal analysis as scan_qr_codes, entered directly with a
    URL instead of a QR photo — for a link received some other way (email,
    text) that you want checked without a QR code involved."""
    result = _analyze_url(raw_url)
    reputation_checked = _enrich_with_reputation_and_age([result]) if result["is_url"] else False
    return {"result": result, "reputation_checked": reputation_checked}


class QrScanRequest(BaseModel):
    image: str


class UrlScanRequest(BaseModel):
    url: str


@router.post("/mm-qr-phishing/scan")
def qr_phishing_scan(body: QrScanRequest):
    if not body.image.strip():
        raise HTTPException(status_code=400, detail="image is required")
    return scan_qr_codes(body.image)


@router.post("/mm-qr-phishing/scan-url")
def qr_phishing_scan_url(body: UrlScanRequest):
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")
    if len(url) > 2048:
        raise HTTPException(status_code=400, detail="url is too long (max 2048 characters)")
    return scan_url(url)
