"""LLM generation with a provider fallback cascade — mirrors the
Groq → Mistral → Gemini cascade already used for vision captioning, so a
rate-limited/unavailable provider doesn't surface a raw error to chat users.
Split out of query.py to stay under the project's file-length limit.
"""
from __future__ import annotations

import logging
from typing import Callable, Generator, Optional

from routers.rag.llm import stream_groq_openai, stream_claude, stream_gemini, stream_cohere

logger = logging.getLogger(__name__)

# Fallback order, tried after the caller's selected provider using each
# provider's own server-side key.
FALLBACK_CANDIDATES = [
    ("groq", "openai/gpt-oss-120b"),
    ("mistral", "mistral-small-latest"),  # proven reliable fallback elsewhere in this codebase (vision captioning)
    ("gemini", "gemini-3.6-flash"),
    ("cohere", "command-a-03-2025"),
]


def classify_error(exc: object) -> str:
    """Short, user-facing reason for a provider failure — the raw exception
    text (status codes, full URLs) is logged in full server-side but isn't
    fit to show in the UI as "why did it fall back to X"."""
    text = str(exc).lower()
    if "429" in text or "rate limit" in text or "too many requests" in text:
        return "rate limited"
    if "401" in text or "403" in text or "unauthorized" in text or "invalid api key" in text or "incorrect api key" in text:
        return "invalid or unauthorized key"
    if "timeout" in text or "timed out" in text:
        return "timed out"
    return "unavailable"


def open_stream(provider: str, model: str, key: str, messages: list[dict], system_prompt: str):
    """Dispatch to the right streaming client. Raises ValueError for an
    unrecognized provider — caught by stream_with_fallback like any other
    failure, so a bad/typo'd provider still cascades to a known-good one."""
    if provider in ("groq", "openai", "mistral", "perplexity"):
        full_messages = [{"role": "system", "content": system_prompt}] + messages if system_prompt else messages
        return stream_groq_openai(provider, model, key, full_messages)
    if provider == "claude":
        return stream_claude(model, key, messages, system_prompt)
    if provider == "gemini":
        return stream_gemini(model, key, messages, system_prompt)
    if provider == "cohere":
        return stream_cohere(model, key, messages, system_prompt)
    raise ValueError(f"Unknown provider '{provider}'.")


def build_provider_candidates(provider: str, model: str, key: str,
                              resolve_key: Callable[[str, Optional[str]], str]) -> list[tuple[str, str, str]]:
    """The caller's selection first, then FALLBACK_CANDIDATES using each
    fallback provider's own server-side key (never the caller's user_key,
    which is provider-specific). Candidates with no configured key are
    skipped outright."""
    candidates = [(provider, model, key)]
    for fb_provider, fb_model in FALLBACK_CANDIDATES:
        if fb_provider == provider:
            continue
        fb_key = resolve_key(fb_provider, None)
        if fb_key:
            candidates.append((fb_provider, fb_model, fb_key))
    return candidates


def stream_with_fallback(provider_candidates: list[tuple[str, str, str]], messages: list[dict],
                         system_prompt: str, meta: dict) -> Generator[str, None, None]:
    """Yields text tokens. Tries each (provider, model, key) candidate in
    order, falling through to the next ONLY if the current one fails before
    producing any token (rate limit, timeout, bad key, unknown provider).
    Once a token has streamed, a later failure is NOT retried with a
    different provider — switching mid-answer would garble the response —
    it's recorded in meta['mid_stream_error'] instead.

    meta is populated with 'served_provider'/'served_model' as soon as the
    winning candidate starts producing tokens, and with 'error' if every
    candidate failed before any output. If the CALLER'S OWN selection (the
    first candidate) failed and a fallback served instead, meta also gets
    'primary_provider'/'primary_failure' (short, user-facing reason) so the
    UI can say *why* — e.g. "cohere unavailable: rate limited" — instead of
    silently showing a different provider than the one picked.
    """
    started = False
    last_error: object = "No provider candidates."
    for i, (cand_provider, cand_model, cand_key) in enumerate(provider_candidates):
        try:
            for token in open_stream(cand_provider, cand_model, cand_key, messages, system_prompt):
                if token:
                    started = True
                    meta["served_provider"] = cand_provider
                    meta["served_model"] = cand_model
                    yield token
            return
        except Exception as exc:
            if started:
                logger.exception("LLM streaming error mid-response (%s/%s): %s", cand_provider, cand_model, exc)
                meta["mid_stream_error"] = f"Generation failed ({cand_provider}/{cand_model}): {exc}"
                return
            if i == 0:
                meta["primary_provider"] = cand_provider
                meta["primary_failure"] = classify_error(exc)
            last_error = exc
            logger.warning("Provider %s/%s failed before any output, trying next: %s",
                           cand_provider, cand_model, exc)
    meta["error"] = f"All providers unavailable. Last error: {last_error}"
