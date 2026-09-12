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
import threading
import time
from collections import deque

logger = logging.getLogger("security_events")

# In-memory rolling event buffer — the free "someone is watching this"
# mechanism until a paid log drain (Datadog/Sentry/Better Stack) exists.
# Before this, security events only ever reached stdout: real, but nobody
# was actually looking unless they manually opened the Space's logs.
# `get_recent_event_counts()` below is the swap-in seam a scheduled check
# (see .github/workflows/security-watch.yml) polls; a paid log drain later
# would replace the poller, not this recorder — `log_security_event`'s call
# sites never change either way.
_MAX_EVENTS = 5000
_events: deque[tuple[float, str]] = deque(maxlen=_MAX_EVENTS)
_lock = threading.Lock()


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
    with _lock:
        _events.append((line["ts"], event_type))


def get_recent_event_counts(window_seconds: int = 3600) -> dict[str, int]:
    """Counts per event_type in the last `window_seconds`. Capped at the
    last `_MAX_EVENTS` regardless of window — a real burst larger than that
    within the window would undercount, but that itself means the app is
    already well past any sane alert threshold."""
    cutoff = time.time() - window_seconds
    counts: dict[str, int] = {}
    with _lock:
        for ts, event_type in _events:
            if ts >= cutoff:
                counts[event_type] = counts.get(event_type, 0) + 1
    return counts
