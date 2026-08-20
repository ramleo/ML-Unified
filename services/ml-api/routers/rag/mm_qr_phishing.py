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
2. Google Safe Browsing reputation lookup (optional — only runs if
   SAFE_BROWSING_API_KEY is set): checks whether the URL is already known
   malicious/phishing in Google's own threat database. This catches sites
   the structural heuristics fundamentally can't — a freshly-registered
   domain with a perfectly clean-looking name — but degrades gracefully to
   heuristics-only if the key isn't configured or the lookup fails, rather
   than failing the whole scan.
3. Domain-age lookup via RDAP (free, no API key — WHOIS's structured,
   ICANN-mandated successor as of Jan 2025), plugging the exact gap Safe
   Browsing has: a brand-new phishing domain that hasn't been indexed yet.
   A domain registered days ago is a real, well-established phishing signal
   even with an otherwise clean-looking URL and no reputation hit. Best-
   effort only — many TLDs/registries don't expose RDAP, so a failed or
   unsupported lookup is silently skipped, never treated as a red flag
   itself.

This intentionally reports SIGNALS, not a verdict — same honesty pattern as
this codebase's tampering detector and signature-verification tools: when
detection is heuristic rather than ground-truth, surface what was found and
let a human weigh it, rather than claim "safe" or "malicious" outright.
"""

import base64
import logging
import os
import time
from datetime import datetime, timezone
from ipaddress import ip_address
from urllib.parse import urlparse

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_IMAGE_BYTES = 10 * 1024 * 1024

_SAFE_BROWSING_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
_SAFE_BROWSING_TIMEOUT = 8.0
_THREAT_TYPE_LABELS = {
    "MALWARE": "malware distribution",
    "SOCIAL_ENGINEERING": "phishing/social engineering",
    "UNWANTED_SOFTWARE": "unwanted software",
    "POTENTIALLY_HARMFUL_APPLICATION": "a potentially harmful application",
}

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

_RDAP_URL = "https://rdap.org/domain/{domain}"
_RDAP_TIMEOUT = 6.0
_DOMAIN_AGE_HIGH_RISK_DAYS = 30
_DOMAIN_AGE_MEDIUM_RISK_DAYS = 180
_DOMAIN_AGE_CACHE_TTL_SECONDS = 3600
_domain_age_cache: dict[str, tuple[float, int | None]] = {}


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


def _check_safe_browsing(urls: list[str]) -> dict[str, list[str]] | None:
    """Looks up each URL against Google Safe Browsing's known-threat lists —
    a hash-prefix lookup, not a fetch of the page itself, preserving the
    "never actually visits the link" property. Returns None (not {}) if the
    check couldn't run at all (no key configured, network/API error) so the
    caller can distinguish "checked, nothing found" from "didn't check"."""
    key = os.environ.get("SAFE_BROWSING_API_KEY", "")
    if not key or not urls:
        return None
    import httpx

    try:
        with httpx.Client(timeout=_SAFE_BROWSING_TIMEOUT) as client:
            res = client.post(
                _SAFE_BROWSING_URL,
                params={"key": key},
                json={
                    "client": {"clientId": "ml-unified-qr-phishing", "clientVersion": "1.0.0"},
                    "threatInfo": {
                        "threatTypes": list(_THREAT_TYPE_LABELS.keys()),
                        "platformTypes": ["ANY_PLATFORM"],
                        "threatEntryTypes": ["URL"],
                        "threatEntries": [{"url": u} for u in urls],
                    },
                },
            )
            res.raise_for_status()
            matches = res.json().get("matches", [])
    except Exception as exc:
        logger.warning("Safe Browsing lookup failed: %s", exc)
        return None

    flagged: dict[str, list[str]] = {}
    for m in matches:
        url = m.get("threat", {}).get("url")
        threat_type = m.get("threatType")
        if url and threat_type:
            flagged.setdefault(url, []).append(threat_type)
    return flagged


def _check_domain_age(host: str) -> int | None:
    """Looks up a domain's registration date via RDAP — free, no API key,
    no signup (WHOIS's structured successor, ICANN-mandated for gTLD
    registries since Jan 2025; rdap.org bootstraps to the right registry).
    Returns age in days, or None if the lookup didn't produce a usable
    answer — many TLDs/registries don't support RDAP, or the domain wasn't
    found, and that's just "no signal," never treated as suspicious itself.
    Small in-memory TTL cache since the same domain can recur across scans
    within one process's lifetime and this is a courtesy to a free service."""
    now = time.time()
    cached = _domain_age_cache.get(host)
    if cached and now - cached[0] < _DOMAIN_AGE_CACHE_TTL_SECONDS:
        return cached[1]

    import httpx

    age_days: int | None = None
    try:
        with httpx.Client(timeout=_RDAP_TIMEOUT, follow_redirects=True) as client:
            res = client.get(_RDAP_URL.format(domain=host))
            if res.status_code == 200:
                for event in res.json().get("events", []):
                    if event.get("eventAction") == "registration" and event.get("eventDate"):
                        reg_date = datetime.fromisoformat(event["eventDate"].replace("Z", "+00:00"))
                        age_days = (datetime.now(timezone.utc) - reg_date).days
                        break
    except Exception as exc:
        logger.info("RDAP lookup failed for %s: %s", host, exc)

    _domain_age_cache[host] = (now, age_days)
    return age_days


def scan_qr_codes(image_b64: str) -> dict:
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except Exception:
        return {"found": False, "qr_codes": [], "reputation_checked": False, "error": "Could not decode image data."}

    if len(raw) > _MAX_IMAGE_BYTES:
        return {"found": False, "qr_codes": [], "reputation_checked": False, "error": "Image too large (max 10MB)."}

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

    def _lookup_form(data: str) -> str:
        return data if "://" in data else f"http://{data}"

    lookup_urls = [_lookup_form(r["data"]) for r in results if r["is_url"]]
    flagged = _check_safe_browsing(lookup_urls)
    reputation_checked = flagged is not None
    if flagged:
        for r in results:
            if not r["is_url"]:
                continue
            threats = flagged.get(_lookup_form(r["data"]))
            if threats:
                labels = ", ".join(_THREAT_TYPE_LABELS.get(t, t) for t in threats)
                r["reasons"].insert(0, f"Flagged by Google Safe Browsing as {labels} — a known-bad site in Google's own database, not just a structural guess.")
                r["risk_level"] = "high"

    for r in results:
        if not r["is_url"] or not r["host"]:
            continue
        try:
            ip_address(r["host"])
            continue  # already flagged as an IP-literal host; no domain to look up
        except ValueError:
            pass
        if _registrable_domain(r["host"]) in _KNOWN_BRAND_DOMAINS:
            continue  # obviously long-established, not worth a lookup
        age_days = _check_domain_age(r["host"])
        if age_days is None:
            continue
        if age_days < _DOMAIN_AGE_HIGH_RISK_DAYS:
            r["reasons"].insert(0, f"Domain was registered only {age_days} day{'s' if age_days != 1 else ''} ago — freshly-registered domains are commonly used for short-lived phishing/scam campaigns.")
            r["risk_level"] = "high"
        elif age_days < _DOMAIN_AGE_MEDIUM_RISK_DAYS:
            r["reasons"].append(f"Domain is relatively new (registered about {age_days} days ago).")
            if r["risk_level"] == "low":
                r["risk_level"] = "medium"

    return {"found": len(results) > 0, "qr_codes": results, "reputation_checked": reputation_checked}


class QrScanRequest(BaseModel):
    image: str


@router.post("/mm-qr-phishing/scan")
def qr_phishing_scan(body: QrScanRequest):
    if not body.image.strip():
        raise HTTPException(status_code=400, detail="image is required")
    return scan_qr_codes(body.image)
