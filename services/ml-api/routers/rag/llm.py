"""Shared LLM clients — one streaming generator per provider, plus a
non-streaming convenience wrapper. Used by both answer generation
(query.py) and query expansion (expand.py)."""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


# Providers whose API is Chat-Completions-compatible with the openai SDK —
# same request/response shape, different base_url. Matches agent.py's
# _OPENAI_COMPAT_BASES (kept in sync manually; agent.py has its own inline
# copy rather than importing this, to avoid coupling the two call paths).
OPENAI_COMPAT_BASES = {
    "groq":       "https://api.groq.com/openai/v1",
    "mistral":    "https://api.mistral.ai/v1",
    "perplexity": "https://api.perplexity.ai",
}


def stream_groq_openai(provider: str, model: str, key: str, messages: list[dict],
                       max_retries: int | None = None, max_tokens: int | None = None):
    """`max_retries` overrides the SDK's own retry count (default 2). Pass 0
    from callers that already pace themselves: a 429 from a per-second limit
    cannot be outrun by a retry landing 0.4s later, so the SDK's two extra
    attempts only triple the round trips before the caller learns it failed."""
    import openai
    base_url = OPENAI_COMPAT_BASES.get(provider)  # None => real OpenAI's own API
    client = openai.OpenAI(
        api_key=key,
        **({"base_url": base_url} if base_url else {}),
        **({"max_retries": max_retries} if max_retries is not None else {}),
    )
    with client.chat.completions.create(
        model=model, messages=messages, stream=True,
        **({"max_tokens": max_tokens} if max_tokens is not None else {}),
    ) as stream:
        for chunk in stream:
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield content


def stream_claude(model: str, key: str, messages: list[dict], system: str):
    import anthropic
    client = anthropic.Anthropic(api_key=key)
    with client.messages.stream(
        model=model,
        max_tokens=2048,
        system=system,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text


def stream_gemini(model: str, key: str, messages: list[dict], system: str):
    import httpx

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:streamGenerateContent?key={key}&alt=sse"
    )
    contents = []
    if system:
        contents.append({"role": "user", "parts": [{"text": f"[System]: {system}"}]})
        contents.append({"role": "model", "parts": [{"text": "Understood."}]})
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    try:
        with httpx.Client(timeout=120) as client:
            with client.stream("POST", url, json={"contents": contents}) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload in ("", "[DONE]"):
                        continue
                    try:
                        obj = json.loads(payload)
                        for cand in obj.get("candidates", []):
                            for part in cand.get("content", {}).get("parts", []):
                                if "text" in part:
                                    yield part["text"]
                    except json.JSONDecodeError:
                        continue
    except httpx.HTTPStatusError as exc:
        # The status alone says almost nothing: a 429 from Google can mean the
        # per-minute quota, the per-day one, a project with no billing, or an
        # API that was never enabled, and the body names which. Logging only
        # the code cost a day of guessing. The body is streamed, so it has to
        # be read before it can be looked at, and read() on an already-closed
        # response raises — hence the inner guard.
        try:
            exc.response.read()
            detail = exc.response.text[:400]
        except Exception:
            detail = "<body unavailable>"
        logger.error("Gemini HTTP %s: %s", exc.response.status_code, detail)
        raise


def stream_cohere(model: str, key: str, messages: list[dict], system: str):
    import httpx

    formatted = []
    if system:
        formatted.append({"role": "system", "content": system})
    for m in messages:
        role = "assistant" if m["role"] == "assistant" else "user"
        formatted.append({"role": role, "content": m["content"]})

    try:
        with httpx.Client(timeout=120) as client:
            with client.stream(
                "POST",
                "https://api.cohere.ai/v2/chat",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "messages": formatted, "stream": True},
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload in ("", "[DONE]"):
                        continue
                    try:
                        obj = json.loads(payload)
                        if obj.get("type") == "content-delta":
                            text = (
                                obj.get("delta", {})
                                .get("message", {})
                                .get("content", {})
                                .get("text", "")
                            )
                            if text:
                                yield text
                    except json.JSONDecodeError:
                        continue
    except httpx.HTTPStatusError as exc:
        # Same lesson as the Gemini branch above: a bare status code cost a
        # day of guessing there. Cohere's 429 body distinguishes the trial
        # key's per-minute cap from a monthly one, and its 400 names the
        # retired model — neither is inferable from the number alone. Now
        # load-bearing: Cohere is the first judge in JUDGE_CANDIDATES.
        try:
            exc.response.read()
            detail = exc.response.text[:400]
        except Exception:
            detail = "<body unavailable>"
        logger.error("Cohere HTTP %s: %s", exc.response.status_code, detail)
        raise


def complete(provider: str, model: str, key: str, messages: list[dict], system: str = "",
             max_retries: int | None = None) -> str:
    """Non-streaming convenience wrapper — collects a streaming call into one string.

    Best-effort: returns "" on any failure rather than raising, since callers
    (e.g. query expansion) treat this as an optional quality boost.
    """
    try:
        if provider in ("groq", "openai", "mistral", "perplexity"):
            full_messages = ([{"role": "system", "content": system}] if system else []) + messages
            return "".join(stream_groq_openai(provider, model, key, full_messages, max_retries))
        elif provider == "claude":
            return "".join(stream_claude(model, key, messages, system))
        elif provider == "gemini":
            return "".join(stream_gemini(model, key, messages, system))
        elif provider == "cohere":
            return "".join(stream_cohere(model, key, messages, system))
    except Exception as exc:
        logger.warning("llm.complete() failed for provider=%s: %s", provider, exc)
    return ""
