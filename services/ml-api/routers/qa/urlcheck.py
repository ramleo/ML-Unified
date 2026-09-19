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

_BLOCKED_HOSTNAMES = {"localhost", "ip6-localhost", "ip6-loopback"}


def validate_target_url(url: str, *, required: bool = False) -> None:
    """Raise HTTPException(400) if the URL is not a usable public http(s) URL.
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

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # A hostname (not an IP literal) — require something that looks routable.
        if "." not in host:
            raise HTTPException(status_code=400, detail="Enter a full public URL, e.g. https://example.com.")
        return

    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
        raise HTTPException(status_code=400, detail="Private or internal addresses are not allowed.")
