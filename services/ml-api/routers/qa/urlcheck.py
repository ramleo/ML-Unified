"""
Testwright (QA Automation) — target-URL validation.

Tests run on GitHub's isolated runners, so any public site is fair game. We only
block malformed URLs and non-public addresses (localhost, LAN, link-local,
metadata IPs) as basic SSRF hygiene. Abuse is bounded separately by the per-stage
daily budget caps and rate limits.
"""

import ipaddress
from urllib.parse import urlparse

from fastapi import HTTPException

from routers.qa import config

_BLOCKED_HOSTNAMES = {"localhost", "ip6-localhost", "ip6-loopback"}


def validate_target_url(url: str, *, required: bool = False, authorized: bool = False) -> None:
    """Raise HTTPException if the URL is not a usable public http(s) URL, or if it
    is a third-party host the caller has not confirmed authorization for.
    An empty URL is allowed unless `required` (Run's base_url is optional)."""
    u = (url or "").strip()
    if not u:
        if required:
            raise HTTPException(status_code=400, detail="A URL is required.")
        return

    parsed = urlparse(u)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://.")

    host = (parsed.hostname or "").lower()
    if not host or host in _BLOCKED_HOSTNAMES:
        raise HTTPException(status_code=400, detail="That URL host is not allowed.")

    # Ownership gate: third-party hosts require an explicit authorization confirmation.
    if not config.is_first_party(host) and not authorized:
        raise HTTPException(
            status_code=403,
            detail="This is a third-party site. Confirm you own it or are authorized to test it.",
        )

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # A hostname (not an IP literal) — require something that looks routable.
        if "." not in host:
            raise HTTPException(status_code=400, detail="Enter a full public URL, e.g. https://example.com.")
        return

    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
        raise HTTPException(status_code=400, detail="Private or internal addresses are not allowed.")
