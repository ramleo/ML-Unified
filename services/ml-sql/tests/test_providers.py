"""E4: cover ml-sql's provider paths, which had no test at all.

Each provider unwraps a *different* response shape — Groq/Mistral read
`choices[0].message.content`, Gemini `candidates[0].content.parts[0].text`,
Cohere `message.content[0].text`. A wrong path is a silent empty answer, and
nothing caught it. These tests mock the HTTP layer (no network, no key spent)
and assert each parser extracts the text, that a 429 becomes RateLimitError,
and that an unknown provider name falls back to Groq rather than erroring.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest
from routers._providers import (
    RateLimitError,
    call_provider,
    get_provider_cfg,
)


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)


def _mock_post(monkeypatch, payload, status_code=200):
    """Replace the one network call every provider makes with a canned reply."""
    async def fake_post(self, url, **kwargs):
        return _FakeResponse(payload, status_code)
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)


# The reply shape each provider actually returns, and the text buried inside it.
_SHAPES = {
    "groq":    {"choices": [{"message": {"content": "SELECT 1"}}]},
    "mistral": {"choices": [{"message": {"content": "SELECT 1"}}]},
    "gemini":  {"candidates": [{"content": {"parts": [{"text": "SELECT 1"}]}}]},
    "cohere":  {"message": {"content": [{"text": "SELECT 1"}]}},
}


@pytest.mark.parametrize("provider", sorted(_SHAPES))
def test_each_provider_parses_its_own_response_shape(monkeypatch, provider):
    _mock_post(monkeypatch, _SHAPES[provider])
    cfg = get_provider_cfg(provider)

    out = asyncio.run(call_provider(provider, "give me sql", cfg["model"], "fake-key"))

    assert out == "SELECT 1"


@pytest.mark.parametrize("provider", sorted(_SHAPES))
def test_a_429_from_any_provider_becomes_rate_limit_error(monkeypatch, provider):
    _mock_post(monkeypatch, {}, status_code=429)
    cfg = get_provider_cfg(provider)

    with pytest.raises(RateLimitError):
        asyncio.run(call_provider(provider, "give me sql", cfg["model"], "fake-key"))


def test_an_unknown_provider_falls_back_to_groq():
    """call_provider and get_provider_cfg both default to groq rather than
    raising a KeyError on a name the UI has not heard of."""
    assert get_provider_cfg("nope")["model"] == get_provider_cfg("groq")["model"]


def test_unknown_provider_dispatches_to_the_groq_caller(monkeypatch):
    _mock_post(monkeypatch, _SHAPES["groq"])

    out = asyncio.run(call_provider("nope", "give me sql", "groq/compound", "fake-key"))

    assert out == "SELECT 1"
