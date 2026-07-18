"""LLM provider registry and non-streaming call helpers."""
from __future__ import annotations

import httpx


class RateLimitError(Exception):
    """Raised when all attempted providers return HTTP 429."""

_PROVIDERS: dict[str, dict] = {
    "groq":    {"env": "GROQ_API_KEY",    "model": "llama-3.3-70b-versatile"},
    "mistral": {"env": "MISTRAL_API_KEY", "model": "codestral-latest"},
    "gemini":  {"env": "GEMINI_API_KEY",  "model": "gemini-2.0-flash"},
    "cohere":  {"env": "COHERE_API_KEY",  "model": "command-r-plus-08-2024"},
}


def get_provider_cfg(provider: str) -> dict:
    return _PROVIDERS.get(provider, _PROVIDERS["groq"])


async def _call_groq(prompt: str, model: str, key: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "max_tokens": 512,
                "temperature": 0.1,
            },
        )
        if resp.status_code == 429: raise RateLimitError("groq")
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _call_gemini(prompt: str, model: str, key: str) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 512, "temperature": 0.1},
            },
        )
        if resp.status_code == 429: raise RateLimitError("gemini")
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


async def _call_mistral(prompt: str, model: str, key: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "max_tokens": 512,
                "temperature": 0.1,
            },
        )
        if resp.status_code == 429: raise RateLimitError("mistral")
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _call_cohere(prompt: str, model: str, key: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.cohere.ai/v2/chat",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "max_tokens": 512,
                "temperature": 0.1,
            },
        )
        if resp.status_code == 429: raise RateLimitError("cohere")
        resp.raise_for_status()
        return resp.json()["message"]["content"][0]["text"]


_CALLERS = {
    "groq": _call_groq,
    "mistral": _call_mistral,
    "gemini": _call_gemini,
    "cohere": _call_cohere,
}


async def call_provider(provider: str, prompt: str, model: str, key: str) -> str:
    """Dispatch a prompt to the named provider (unknown names fall back to groq)."""
    fn = _CALLERS.get(provider, _call_groq)
    return await fn(prompt, model, key)
