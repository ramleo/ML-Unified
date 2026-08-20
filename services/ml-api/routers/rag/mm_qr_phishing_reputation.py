"""
QR Phishing Detector — reputation/age enrichment signals.

Split out of mm_qr_phishing.py to keep that file under the project's
400-line cap as the tool grew a third input surface (direct URL) and a
non-URL payload-type feature. Owns the two "does someone else already know
something about this domain" checks — Google Safe Browsing (already known
malicious) and RDAP domain age (freshly registered) — plus the small
brand-domain list and root-domain helper both checks share with
mm_qr_phishing.py's structural typosquat check.
"""

import logging
import os
import time
from datetime import datetime, timezone
from ipaddress import ip_address

logger = logging.getLogger(__name__)

_SAFE_BROWSING_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
_SAFE_BROWSING_TIMEOUT = 8.0
_THREAT_TYPE_LABELS = {
    "MALWARE": "malware distribution",
    "SOCIAL_ENGINEERING": "phishing/social engineering",
    "UNWANTED_SOFTWARE": "unwanted software",
    "POTENTIALLY_HARMFUL_APPLICATION": "a potentially harmful application",
}

_RDAP_URL = "https://rdap.org/domain/{domain}"
_RDAP_TIMEOUT = 12.0  # rdap.org bootstraps via a redirect to the actual
# registry's RDAP server — a two-hop round trip that can run past 6s under
# real deployed-network latency even though it's fast on a local machine
# (found via a real timeout on the deployed HF Space, not assumed upfront).
_DOMAIN_AGE_HIGH_RISK_DAYS = 30
_DOMAIN_AGE_MEDIUM_RISK_DAYS = 180
_DOMAIN_AGE_CACHE_TTL_SECONDS = 3600
_domain_age_cache: dict[str, tuple[float, int | None]] = {}

# A handful of frequently-impersonated brand domains, for the typosquat
# check (mm_qr_phishing.py) and to skip a pointless age lookup on an
# obviously long-established domain — NOT a claim of exhaustive brand
# coverage.
_KNOWN_BRAND_DOMAINS = {
    "paypal.com", "amazon.com", "apple.com", "microsoft.com", "google.com",
    "chase.com", "bankofamerica.com", "wellsfargo.com", "netflix.com",
    "facebook.com", "instagram.com", "whatsapp.com", "dhl.com", "fedex.com",
    "ups.com", "usps.com", "irs.gov", "linkedin.com", "dropbox.com",
    "docusign.com", "coinbase.com", "binance.com",
}


def _registrable_domain(host: str) -> str:
    """Best-effort eTLD+1 without a public-suffix-list dependency — sufficient
    for the small curated brand list above (all plain .com/.gov), not a
    general-purpose PSL implementation."""
    parts = host.lower().split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()


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


def _check_domain_age(root_domain: str) -> int | None:
    """Looks up a domain's registration date via RDAP — free, no API key,
    no signup (WHOIS's structured successor, ICANN-mandated for gTLD
    registries since Jan 2025; rdap.org bootstraps to the right registry).
    Takes the REGISTRABLE root domain (e.g. "wikipedia.org"), not a full
    hostname with subdomains ("en.wikipedia.org") — registries reject
    subdomain queries with a 400, confirmed via real Space logs, not
    assumed. Returns age in days, or None if the lookup didn't produce a
    usable answer — many TLDs/registries don't support RDAP, or the domain
    wasn't found, and that's just "no signal," never treated as suspicious
    itself. Small in-memory TTL cache since the same domain can recur
    across scans within one process's lifetime and this is a courtesy to a
    free service."""
    now = time.time()
    cached = _domain_age_cache.get(root_domain)
    if cached and now - cached[0] < _DOMAIN_AGE_CACHE_TTL_SECONDS:
        return cached[1]

    import httpx

    age_days: int | None = None
    try:
        with httpx.Client(timeout=_RDAP_TIMEOUT, follow_redirects=True) as client:
            res = client.get(_RDAP_URL.format(domain=root_domain))
            if res.status_code == 200:
                for event in res.json().get("events", []):
                    if event.get("eventAction") == "registration" and event.get("eventDate"):
                        reg_date = datetime.fromisoformat(event["eventDate"].replace("Z", "+00:00"))
                        age_days = (datetime.now(timezone.utc) - reg_date).days
                        break
    except Exception as exc:
        logger.info("RDAP lookup failed for %s: %s", root_domain, exc)

    _domain_age_cache[root_domain] = (now, age_days)
    return age_days


def _lookup_form(data: str) -> str:
    return data if "://" in data else f"http://{data}"


def _enrich_with_reputation_and_age(results: list[dict]) -> bool:
    """Runs the Safe Browsing + domain-age checks over already
    structurally-analyzed results, mutating each result's risk_level/reasons
    in place. Shared by both the QR-image path and the direct-URL path so
    the two entry points can never drift out of sync with each other.
    Returns whether the Safe Browsing check actually ran (reputation_checked)."""
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
        root = _registrable_domain(r["host"])
        if root in _KNOWN_BRAND_DOMAINS:
            continue  # obviously long-established, not worth a lookup
        age_days = _check_domain_age(root)
        if age_days is None:
            continue
        if age_days < _DOMAIN_AGE_HIGH_RISK_DAYS:
            r["reasons"].insert(0, f"Domain was registered only {age_days} day{'s' if age_days != 1 else ''} ago — freshly-registered domains are commonly used for short-lived phishing/scam campaigns.")
            r["risk_level"] = "high"
        elif age_days < _DOMAIN_AGE_MEDIUM_RISK_DAYS:
            r["reasons"].append(f"Domain is relatively new (registered about {age_days} days ago).")
            if r["risk_level"] == "low":
                r["risk_level"] = "medium"

    return reputation_checked
