"""
Structured security-event logging — one JSON line per event to stdout,
which HF Spaces already captures as logs (free today, no new
infrastructure). Before this existed, the backend only had generic
per-request timing logs (`app.py`'s `_monitor` middleware) with nothing
specific to security events (rate-limit hits, blocked origins, oversized
requests, YARA/prompt-injection flags).

The fixed schema below is the actual swap-in mechanism: point any paid log
drain (Datadog, Sentry, Better Stack, Axiom) at this same stdout stream
later and it will parse every event without this emission code changing at
all — the field names are the contract, not the destination.
"""
from __future__ import annotations

import json
import logging
import time

logger = logging.getLogger("security_events")


def log_security_event(event_type: str, path: str, client_ip: str, detail: str = "") -> None:
    """event_type is a short fixed tag, e.g. 'rate_limit_exceeded',
    'origin_blocked', 'oversized_request', 'file_gate_flagged',
    'budget_exceeded' — keep this vocabulary small and stable, since it's
    what a future log-drain/SIEM would filter and alert on."""
    line = {
        "event_type": event_type,
        "ts": time.time(),
        "path": path,
        "ip": client_ip,
        "detail": detail,
    }
    logger.warning(json.dumps(line))
