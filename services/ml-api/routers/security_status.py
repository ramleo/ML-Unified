"""
Security-event status endpoint — the free "someone is watching" mechanism.
Before this, `security/events.py` logged real events (blocked origins, rate
limit hits, YARA flags) to stdout, but nothing ever read that stream; a
real attack in progress would only surface if someone manually opened the
Space's logs. A scheduled GitHub Action (`.github/workflows/security-watch.yml`)
polls this endpoint every 30 minutes and fails (triggering GitHub's free,
built-in failure-email to the repo owner) if any event type spikes past a
threshold — zero new paid infrastructure.

Gated by a shared-secret header, not real auth (this project has none) —
`SECURITY_STATUS_TOKEN` must be set for the endpoint to respond at all; if
unset, it 404s as if it doesn't exist, so an accidental deploy without the
secret configured fails closed (hidden) rather than open (unguarded).

Swap-in point for later: point a paid log drain / SIEM (Datadog, Sentry,
Better Stack) at the same underlying event stream instead of polling this
endpoint — `get_recent_event_counts()` in events.py stays the same either
way, only the poller changes.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException

from security.events import get_recent_event_counts

router = APIRouter()


@router.get("/security/status")
def security_status(x_admin_token: str | None = Header(default=None), window_seconds: int = 3600):
    expected = os.environ.get("SECURITY_STATUS_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=404, detail="Not found")
    if x_admin_token != expected:
        raise HTTPException(status_code=404, detail="Not found")
    counts = get_recent_event_counts(window_seconds)
    return {"window_seconds": window_seconds, "counts": counts, "total": sum(counts.values())}
