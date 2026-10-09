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

from security.trace import current_trace_id

logger = logging.getLogger(__name__)

_SERVICE = "ml-api"
_DEFAULT_SINK = "https://ml-portfolio-rho.vercel.app/api/llm-log"
_TIMEOUT_S = 4.0

# Prices in USD per 1,000,000 tokens. **As of 2026-10-08**, mirrored from the
# frontend's src/lib/llmTelemetry.ts so a backend row and a frontend row for the
# same model agree. ESTIMATES for the cost dashboard, not a bill — update the
# date when refreshed. Only the paid models appear; free-tier providers (groq,
# cohere, mistral) are absent and resolve to $0 in _estimate_cost.
_PRICE_PER_MTOK = {
    "claude": {"in": 1.0, "out": 5.0},   # claude-haiku-4-5
    "gemini": {"in": 0.3, "out": 2.5},   # gemini-2.5-flash
}


def _estimate_cost(provider: str, input_tokens: Optional[int],
                   output_tokens: Optional[int]) -> Optional[float]:
    """USD cost for a call, or None when tokens are unknown. A provider absent
    from the price table (free tier) is a real, known 0.0 — not None."""
    if input_tokens is None and output_tokens is None:
        return None
    rate = _PRICE_PER_MTOK.get(provider.lower())
    if not rate:
        return 0.0
    return ((input_tokens or 0) * rate["in"] + (output_tokens or 0) * rate["out"]) / 1_000_000

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
                error_message: str = "", latency_ms: int = 0,
                usage: Optional[dict] = None, operation: str = "chat") -> None:
    """Queue one row. Returns immediately; never raises.

    `usage` is the mutable dict filled by an instrumented stream_* generator —
    {"input": int|None, "output": int|None}. When absent or unknown, tokens and
    cost are sent as None (a free provider still resolves to a known $0).
    """
    _, token = _sink()
    if not token:
        return  # fail closed — no secret configured, nothing leaves the Space
    ctx = get_call_context()
    u = usage or {}
    input_tokens = u.get("input")
    output_tokens = u.get("output")
    # run_id is the trace id spine (O1). Prefer an explicit set_call_context
    # value; otherwise fall back to the request's trace id so every backend LLM
    # call joins the same story as the frontend action, with no per-site change.
    run_id = ctx.get("run_id", "") or current_trace_id()
    payload = {
        "service": _SERVICE, "tool": ctx.get("tool", ""),
        "provider": provider, "model": model,
        "status": status, "http_status": http_status,
        "error_code": error_code, "error_message": str(error_message)[:400],
        "latency_ms": latency_ms,
        "session_id": ctx.get("session_id", ""), "run_id": run_id,
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "cost_usd": _estimate_cost(provider, input_tokens, output_tokens),
        "operation": operation,
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


def instrument(provider: str, model: str, gen: Iterator[Any],
               usage: Optional[dict] = None) -> Iterator[Any]:
    """Wrap a provider's streaming generator so its outcome is recorded.

    Timed to completion rather than to first token: a stream that starts and
    then dies mid-answer is a different failure from one that never started,
    and only the end tells them apart.

    `usage` is a dict shared with the raw generator, which fills it from the
    provider's terminal usage chunk as the stream drains. It is read here only
    after the generator is exhausted, so by then it holds the final counts (or
    stays empty when the provider reports none).
    """
    t0 = time.monotonic()
    try:
        for chunk in gen:
            yield chunk
    except BaseException as exc:
        status, code, msg = describe_error(exc)
        record_call(provider, model, "error", http_status=status, error_code=code,
                    error_message=msg, latency_ms=int((time.monotonic() - t0) * 1000),
                    usage=usage)
        raise
    else:
        record_call(provider, model, "ok", http_status=200,
                    latency_ms=int((time.monotonic() - t0) * 1000), usage=usage)
