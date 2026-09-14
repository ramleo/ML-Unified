"""Refuse requests from blocked IPs (OPEN_ISSUES E17).

Browsers call this Space directly, and Hugging Face has no IP firewall, so an
abusive address cannot be stopped at the edge the way Vercel's firewall stops
one for ml-portfolio. This is that missing control: a `BLOCKED_IPS` Space
variable, and every request from a listed address is refused before any router
runs.

`BLOCKED_IPS` is comma-separated single IPs and/or CIDR ranges, e.g.
`203.0.113.4, 198.51.100.0/24`. Unset or empty means nothing is blocked.
Editing the variable restarts the Space (~2 min); a block is not instant.

The client IP comes from `X-Forwarded-For` (HF's proxy rotates the TCP peer
address), the same source the rate limiter uses.
"""
from __future__ import annotations

import ipaddress
import logging
import os

from fastapi import Request
from fastapi.responses import JSONResponse

from security.rate_limit import get_client_ip

logger = logging.getLogger(__name__)


def _parse(raw: str) -> list:
    nets = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            logger.warning("BLOCKED_IPS: ignoring invalid entry %r", part)
    return nets


_BLOCKED = _parse(os.environ.get("BLOCKED_IPS", ""))
if _BLOCKED:
    logger.info("IP blocklist active: %d entr%s", len(_BLOCKED), "y" if len(_BLOCKED) == 1 else "ies")


def _is_blocked(ip: str) -> bool:
    if not _BLOCKED:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in _BLOCKED)


async def enforce_ip_block(request: Request, call_next):
    if _BLOCKED and _is_blocked(get_client_ip(request)):
        return JSONResponse(status_code=403, content={"detail": "Forbidden."})
    return await call_next(request)
