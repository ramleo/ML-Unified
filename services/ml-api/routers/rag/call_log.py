"""Fire-and-forget record of every outbound LLM call (LOGGING_SPEC.md §5).

Why this exists: on 2026-09-05 the reconciliation tool 429'd all day and
diagnosing it took hours, because the only record was the Hugging Face Space's
run buffer — a live tail that every file upload and every secret change wipes.
Nothing durable existed to answer "what happened at 15:09".

Two hard rules, both from §6:

  * Never block the user. Every call here is posted from a daemon thread with
    a short timeout, and every failure is swallowed. A logging outage must be
    invisible to a visitor, and must never slow a stream down.
  * No content. Provider, model, status, latency and the provider's own error
    text (truncated) — never the prompt, never the document.

The Space does NOT hold a Supabase key. It posts to an authenticated route on
Vercel which owns the key, because the Space's logs were found leaking a
Gemini key in plaintext on 2026-09-05 and a database key is far worse. Fails
closed: with AIRAML_LOG_TOKEN unset, nothing is sent at all.
"""
from __future__ import annotations

import contextvars
import logging
import os
import threading
import time
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

_SERVICE = "ml-api"
_DEFAULT_SINK = "https://ml-portfolio-rho.vercel.app/api/llm-log"
_TIMEOUT_S = 4.0

# Who the current request belongs to. A ContextVar rather than a parameter on
# every signature: the call sites are spread across a dozen routers, and the
# spec's whole point is that instrumentation lives at the funnel rather than
# being remembered at each site. Defaults are empty, so an uninstrumented
# caller logs a row with no join key instead of raising.
_ctx: contextvars.ContextVar[dict] = contextvars.ContextVar("llm_call_ctx", default={})


def set_call_context(session_id: str = "", run_id: str = "", tool: str = "") -> None:
    """Tag every LLM call made later in this request. Safe to call twice."""
    _ctx.set({"session_id": session_id or "", "run_id": run_id or "", "tool": tool or ""})


def get_call_context() -> dict:
    return dict(_ctx.get())


def _sink() -> tuple[str, str]:
    return os.environ.get("AIRAML_LOG_URL", _DEFAULT_SINK), os.environ.get("AIRAML_LOG_TOKEN", "")


def _post(payload: dict) -> None:
    url, token = _sink()
    try:
        import httpx
        httpx.post(url, json=payload, headers={"x-log-token": token}, timeout=_TIMEOUT_S)
    except Exception as exc:
        # Deliberately debug, not warning: a logging outage is not a user
        # problem, and an unreachable sink must not fill the run buffer with
        # noise that hides the errors we are actually trying to see.
        logger.debug("call_log post failed: %s", exc)


def record_call(provider: str, model: str, status: str, *,
                http_status: Optional[int] = None, error_code: str = "",
                error_message: str = "", latency_ms: int = 0) -> None:
    """Queue one row. Returns immediately; never raises."""
    _, token = _sink()
    if not token:
        return  # fail closed — no secret configured, nothing leaves the Space
    ctx = get_call_context()
    payload = {
        "service": _SERVICE, "tool": ctx.get("tool", ""),
        "provider": provider, "model": model,
        "status": status, "http_status": http_status,
        "error_code": error_code, "error_message": str(error_message)[:400],
        "latency_ms": latency_ms,
        "session_id": ctx.get("session_id", ""), "run_id": ctx.get("run_id", ""),
    }
    try:
        threading.Thread(target=_post, args=(payload,), daemon=True).start()
    except Exception as exc:
        logger.debug("call_log thread failed: %s", exc)


def describe_error(exc: BaseException) -> tuple[Optional[int], str, str]:
    """(http_status, error_code, message) from a provider exception.

    Every SDK spells this differently: httpx puts it on .response, the openai
    SDK on the exception itself. Reading whichever exists beats parsing the
    string, which is what made a 429 indistinguishable from a dead key.
    """
    status: Optional[int] = None
    code = ""
    resp = getattr(exc, "response", None)
    if resp is not None:
        status = getattr(resp, "status_code", None)
    if status is None:
        status = getattr(exc, "status_code", None)
    body = getattr(exc, "code", "") or getattr(exc, "type", "")
    if body:
        code = str(body)[:80]
    return status, code, str(exc)[:400]


def instrument(provider: str, model: str, gen: Iterator[Any]) -> Iterator[Any]:
    """Wrap a provider's streaming generator so its outcome is recorded.

    Timed to completion rather than to first token: a stream that starts and
    then dies mid-answer is a different failure from one that never started,
    and only the end tells them apart.
    """
    t0 = time.monotonic()
    try:
        for chunk in gen:
            yield chunk
    except BaseException as exc:
        status, code, msg = describe_error(exc)
        record_call(provider, model, "error", http_status=status, error_code=code,
                    error_message=msg, latency_ms=int((time.monotonic() - t0) * 1000))
        raise
    else:
        record_call(provider, model, "ok", http_status=200,
                    latency_ms=int((time.monotonic() - t0) * 1000))
