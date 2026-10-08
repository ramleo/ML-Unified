"""Request correlation id (trace id) — O1 of the observability roadmap
(docs/OBSERVABILITY_PLAN.md).

The frontend mints a trace id per user action (ml-portfolio `src/lib/trace.ts`)
and sends it as the `x-trace-id` header on every call that passes through
`trackedFetch`. This middleware reads it — or mints one when a caller sends none
(a direct curl, a server-to-server call) — and holds it in a contextvar for the
life of the request, so any code can read it (a log line, the error reporter)
without threading an argument through every signature. It echoes the id back on
the response header so one click can be followed across the browser and this
backend.

Content-free per LOGGING_SPEC §6: a trace id is a random opaque token, never user
data. The id arrives over the wire from a client we do not control, so it is
bounded to an opaque-token shape before it is ever stored or logged.
"""
from __future__ import annotations

import contextvars
import re
import uuid

TRACE_HEADER = "x-trace-id"

# An incoming id is untrusted: cap its length and strip it to an opaque-token
# charset so it cannot smuggle control characters or newlines into a log line.
_SAFE = re.compile(r"[^A-Za-z0-9._-]")

_TRACE_ID: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


def _clean(raw: str) -> str:
    return _SAFE.sub("", (raw or "")[:64])


def new_trace_id() -> str:
    return uuid.uuid4().hex


def current_trace_id() -> str:
    """The current request's trace id, or "" outside a request."""
    return _TRACE_ID.get()


async def trace_id_dispatch(request, call_next):
    tid = _clean(request.headers.get(TRACE_HEADER, "")) or new_trace_id()
    token = _TRACE_ID.set(tid)
    try:
        response = await call_next(request)
    finally:
        _TRACE_ID.reset(token)
    # Echo so a caller can confirm the id the backend actually used (it minted
    # one if the caller sent none). The browser already knows the id it sent, so
    # this is for debugging, not correlation — no Expose-Headers change needed.
    response.headers[TRACE_HEADER] = tid
    return response
