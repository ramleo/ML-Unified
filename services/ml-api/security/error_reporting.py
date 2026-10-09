"""Optional Sentry error reporting for the backend — DORMANT unless SENTRY_DSN
is set in the Space environment. With no DSN this is a complete no-op, so local
dev and any un-provisioned deploy behave exactly as before.

Why this exists: FastAPI had no global exception handler — an unhandled error in
any of the ~50 routers only ever reached stdout, which on a Hugging Face Space
is an ephemeral buffer wiped on every restart. Sentry's FastAPI integration (auto
-enabled once `sentry_sdk.init()` runs) captures every unhandled exception with a
full, durable stack trace, grouped and searchable, so "why did it 500 at <time>"
is answerable after the fact.

Content-free per LOGGING_SPEC §6: `send_default_pii=False` (no IP/cookies/
headers), no performance tracing, and `before_send` hard-strips any request body
and the user object before anything leaves the process. Exception *messages* are
kept (they are what makes a trace debuggable) — the same trade-off agreed for the
frontend.

Swap-in note: the same DSN mechanism points at any Sentry-compatible drain later;
call sites never change.
"""
from __future__ import annotations

import os
import time
import traceback

# The DIY error store lives on the frontend (Vercel) which already holds the
# Supabase service-role key — the backend posts errors there rather than putting
# DB credentials on the public HF Space. Defaults to the prod site; override with
# SITE_URL. See ml-portfolio/docs or docs/ERROR_TRACKING.md.
_SITE_URL = os.environ.get("SITE_URL", "https://ml-portfolio-rho.vercel.app").rstrip("/")
_last_store_send = 0.0

# Whether sentry_sdk.init() actually succeeded at startup. A wrong or malformed
# SENTRY_DSN makes init raise, which init_error_reporting() swallows and returns
# False for — so the Space boots fine but Sentry stays dormant with no visible
# signal. This flag is what the admin status endpoint reads to tell a correct DSN
# from a silently-broken one.
_SENTRY_ACTIVE = False


def sentry_active() -> bool:
    """True only if sentry_sdk.init() ran successfully (valid DSN present)."""
    return _SENTRY_ACTIVE


async def _post_error_to_store(kind: str, message: str, route: str, stack: str) -> None:
    """Best-effort POST of one unhandled backend exception to the site's
    /api/error store. Never raises, 2s timeout, coalesced to ~1/s so an error
    storm can't hammer the endpoint or slow the 500 response."""
    global _last_store_send
    now = time.time()
    if now - _last_store_send < 1.0:
        return
    _last_store_send = now
    try:
        import httpx
        from security.trace import current_trace_id
        payload = {
            "source": "backend",
            "kind": kind,
            "message": (message or "")[:1000],
            "route": route,
            "stack": (stack or "")[:6000],
            # Correlation id (O1): lands in errors.meta.trace_id — no schema
            # change — so a backend 500 links to the frontend action that caused
            # it. Empty when the caller sent no id and none was minted.
            "meta": {"trace_id": current_trace_id()},
        }
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(f"{_SITE_URL}/api/error", json=payload)
    except Exception:
        pass


async def error_capture_dispatch(request, call_next):
    """Middleware: report an unhandled exception to the DIY store, then re-raise
    so Sentry (if active) and Starlette's default 500 handling still apply. Only
    genuine unhandled 500s reach here — HTTPException / validation errors are
    handled by FastAPI upstream and never hit this."""
    try:
        return await call_next(request)
    except Exception as exc:
        # O4: tag the Sentry event with the request's trace id. This must happen
        # here, not in before_send: the trace middleware is OUTER, so its finally
        # resets the trace contextvar before the exception reaches Sentry's outer
        # auto-capture. Here the contextvar is still live (same reason the store
        # POST below can read it). Mutating the request scope now carries the tag
        # into that later capture. No-op when Sentry is dormant (no DSN).
        try:
            import sentry_sdk
            from security.trace import current_trace_id
            tid = current_trace_id()
            if tid:
                sentry_sdk.set_tag("trace_id", tid)
        except Exception:
            pass
        try:
            await _post_error_to_store(
                kind=type(exc).__name__,
                message=str(exc),
                route=getattr(getattr(request, "url", None), "path", ""),
                stack=traceback.format_exc(),
            )
        except Exception:
            pass
        raise


def _scrub(event, _hint):
    """Drop anything that could carry user content or PII before send."""
    event.pop("user", None)
    req = event.get("request")
    if isinstance(req, dict):
        for k in ("data", "cookies", "headers"):
            req.pop(k, None)
    return event


def init_error_reporting() -> bool:
    """Initialise Sentry if SENTRY_DSN is present. Returns True if active, and
    records that result in _SENTRY_ACTIVE for the status endpoint to read.
    Safe to call unconditionally at startup; never raises."""
    global _SENTRY_ACTIVE
    _SENTRY_ACTIVE = False
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        return False
    try:
        sentry_sdk.init(
            dsn=dsn,
            send_default_pii=False,
            traces_sample_rate=0.0,
            before_send=_scrub,
        )
    except Exception:
        return False
    _SENTRY_ACTIVE = True
    return True
