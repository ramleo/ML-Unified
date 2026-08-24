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


def stream_groq_openai(provider: str, model: str, key: str, messages: list[dict]):
    import openai
    base_url = OPENAI_COMPAT_BASES.get(provider)  # None => real OpenAI's own API
    client = openai.OpenAI(api_key=key, **({"base_url": base_url} if base_url else {}))
    with client.chat.completions.create(
        model=model, messages=messages, stream=True
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
        logger.error("Gemini HTTP error: %s", exc.response.status_code)
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
        logger.error("Cohere HTTP error: %s", exc.response.status_code)
        raise


def complete(provider: str, model: str, key: str, messages: list[dict], system: str = "") -> str:
    """Non-streaming convenience wrapper — collects a streaming call into one string.

    Best-effort: returns "" on any failure rather than raising, since callers
    (e.g. query expansion) treat this as an optional quality boost.
    """
    try:
        if provider in ("groq", "openai", "mistral", "perplexity"):
            full_messages = ([{"role": "system", "content": system}] if system else []) + messages
            return "".join(stream_groq_openai(provider, model, key, full_messages))
        elif provider == "claude":
            return "".join(stream_claude(model, key, messages, system))
        elif provider == "gemini":
            return "".join(stream_gemini(model, key, messages, system))
        elif provider == "cohere":
            return "".join(stream_cohere(model, key, messages, system))
    except Exception as exc:
        logger.warning("llm.complete() failed for provider=%s: %s", provider, exc)
    return ""
