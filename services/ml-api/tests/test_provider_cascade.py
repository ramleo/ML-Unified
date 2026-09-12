"""Phase 3: the provider cascade, tested without calling a provider.

Every bug this file guards against cost real money or real silence:

- Cohere sat at the head of the document cascade for weeks calling a
  RETIRED model name. Every call 404'd, `_cohere` swallowed it and returned
  "", and the cascade fell through to the only PAID key on the Space. The
  symptom was a Gemini bill, not an error. Nothing here can catch a retired
  model name — only a live call can — but the tests below do catch the two
  things that made it invisible: a paid provider that is not last, and a
  cascade that keeps going after a provider has already answered.
- Cerebras was missing from `_provider_map`, so the one thing that would
  have diagnosed its stale key — asking for it by name — was unreachable.

Nothing here makes a network request. Providers are replaced with plain
functions, which is the point: the ORDER and the FALLBACK RULES are
deterministic code, and deterministic code deserves hard assertions.
"""
from __future__ import annotations

import pytest

from routers.document import _llm
from routers.rag import generation

# The only paid key on this Space. Every cascade in the app must reach it
# last or not at all — see the module docstring.
PAID = "gemini"


# -- Cascade order ------------------------------------------------------------

def test_document_cascade_is_the_agreed_order():
    assert [name for name, _ in _llm._CASCADE_ORDER] == ["cohere", "mistral", "gemini"]


def test_rag_fallback_is_the_agreed_order():
    assert [p for p, _ in generation.FALLBACK_CANDIDATES] == ["cohere", "mistral", "gemini"]


@pytest.mark.parametrize(
    "order",
    [
        [name for name, _ in _llm._CASCADE_ORDER],
        [p for p, _ in generation.FALLBACK_CANDIDATES],
    ],
    ids=["document", "rag"],
)
def test_the_paid_provider_is_last(order):
    """The invariant, stated once, for whichever cascade is added next.

    A reordering that puts Gemini anywhere but the end is a decision to
    spend money by default, and it should have to argue with a failing
    test first."""
    assert order[-1] == PAID, f"{PAID} must be last in {order}"
    assert order.count(PAID) == 1


def test_no_duplicate_providers_in_a_cascade():
    names = [name for name, _ in _llm._CASCADE_ORDER]
    assert len(names) == len(set(names))


# -- Fallback behaviour -------------------------------------------------------

def _stub_cascade(monkeypatch, results: dict[str, str]) -> list[str]:
    """Replace every provider in the cascade with a recorder returning
    `results[name]`. Returns the list that records who was actually called,
    in order."""
    called: list[str] = []

    def make(name: str):
        def fn(messages, system):
            called.append(name)
            return results.get(name, "")
        return fn

    order = tuple((name, make(name)) for name, _ in _llm._CASCADE_ORDER)
    monkeypatch.setattr(_llm, "_CASCADE_ORDER", order)
    monkeypatch.setattr(_llm, "last_provider", "")
    return called


def test_first_provider_wins_and_the_paid_one_is_never_called(monkeypatch):
    called = _stub_cascade(monkeypatch, {"cohere": '{"ok": true}'})

    out = _llm._cascade([{"role": "user", "content": "x"}], "sys")

    assert out == '{"ok": true}'
    assert called == ["cohere"], "a later provider ran after one had already answered"
    assert _llm.last_provider == "cohere"


def test_an_empty_answer_falls_through_to_the_next_provider(monkeypatch):
    called = _stub_cascade(monkeypatch, {"cohere": "", "mistral": '{"ok": true}'})

    out = _llm._cascade([{"role": "user", "content": "x"}], "sys")

    assert out == '{"ok": true}'
    assert called == ["cohere", "mistral"]
    assert _llm.last_provider == "mistral"


def test_whitespace_is_not_an_answer(monkeypatch):
    """This is exactly how the retired Cohere model behaved: not an
    exception, not a refusal, just nothing. A cascade that treats "   " as
    success returns an empty extraction to the user and reports the wrong
    provider as the one that served it."""
    called = _stub_cascade(monkeypatch, {"cohere": "   \n ", "mistral": "{}"})

    assert _llm._cascade([], "") == "{}"
    assert called == ["cohere", "mistral"]
    assert _llm.last_provider == "mistral"


def test_every_provider_failing_is_reported_as_nobody_served(monkeypatch):
    called = _stub_cascade(monkeypatch, {})

    assert _llm._cascade([], "") == ""
    assert called == ["cohere", "mistral", "gemini"], "the cascade stopped early"
    assert _llm.last_provider == "", "a failed cascade must not leave a stale provider name"


def test_last_provider_is_not_left_over_from_a_previous_call(monkeypatch):
    """`last_provider` is module state the router reads right after
    extraction to attribute the result in the UI. A stale value means the
    UI names a provider that did not run — the same class of lie as
    reporting the provider asked for instead of the one that answered."""
    _stub_cascade(monkeypatch, {"mistral": "{}"})
    _llm._cascade([], "")
    assert _llm.last_provider == "mistral"

    _stub_cascade(monkeypatch, {})
    _llm._cascade([], "")
    assert _llm.last_provider == ""


# -- Missing keys -------------------------------------------------------------

@pytest.mark.parametrize(
    "fn,env",
    [
        (_llm._cohere, "COHERE_API_KEY"),
        (_llm._mistral, "MISTRAL_API_KEY"),
        (_llm._gemini_text, "GEMINI_API_KEY"),
        (_llm._cerebras, "CEREBRAS_API_KEY"),
        (_llm._groq, "GROQ_API_KEY"),
    ],
)
def test_a_provider_with_no_key_returns_empty_without_calling_out(monkeypatch, fn, env):
    """An unconfigured provider must cost a function call, not a round
    trip -- and must not raise, or one missing secret takes down a route
    that has three other providers ready to serve it."""
    monkeypatch.delenv(env, raising=False)
    assert fn([{"role": "user", "content": "x"}], "sys") == ""


# -- Manual provider selection ------------------------------------------------

def test_every_implemented_provider_can_be_asked_for_by_name():
    """Cerebras was implemented in this module but absent from the map the
    router selects on, so the only way to test its key directly did not
    exist and a 401 sat unnoticed. A provider you cannot address is a
    provider you cannot diagnose."""
    import inspect

    src = inspect.getsource(_llm.extract_fields_from_text)
    for name in ("groq", "mistral", "gemini", "cohere", "cerebras"):
        assert f'"{name}"' in src, f"{name} is implemented but not selectable by name"


def test_an_unknown_provider_name_falls_back_to_the_cascade(monkeypatch):
    """A typo in the provider field must not become a silent empty result."""
    called = _stub_cascade(monkeypatch, {"cohere": '{"fields": []}'})

    _llm.extract_fields_from_text("text", "invoice", [], provider="not-a-provider")

    assert called == ["cohere"]


# -- RAG candidate list -------------------------------------------------------

def test_the_callers_choice_comes_first_and_is_not_repeated():
    candidates = generation.build_provider_candidates(
        "mistral", "mistral-small-latest", "user-key", lambda p, _: f"{p}-key"
    )
    providers = [p for p, _, _ in candidates]

    assert providers[0] == "mistral"
    assert providers.count("mistral") == 1, "the caller's provider was retried as a fallback"
    assert providers[-1] == PAID


def test_a_fallback_with_no_configured_key_is_skipped():
    """Listing a keyless provider costs a guaranteed-failing round trip in
    front of one that would have worked."""
    candidates = generation.build_provider_candidates(
        "cohere", "command-a-03-2025", "k", lambda p, _: "" if p == "mistral" else f"{p}-key"
    )
    assert [p for p, _, _ in candidates] == ["cohere", "gemini"]


def test_the_callers_key_is_never_reused_for_another_provider():
    """A Cohere key sent to Gemini is a 401 at best and a leaked credential
    at worst."""
    candidates = generation.build_provider_candidates(
        "cohere", "m", "SECRET-COHERE-KEY", lambda p, _: f"server-{p}"
    )
    for provider, _, key in candidates[1:]:
        assert key == f"server-{provider}"


def test_an_unknown_provider_raises_rather_than_streaming_nothing():
    with pytest.raises(ValueError):
        generation.open_stream("not-a-provider", "m", "k", [], "")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("429 Too Many Requests", "rate limited"),
        ("401 Unauthorized", "invalid or unauthorized key"),
        ("Incorrect API key provided", "invalid or unauthorized key"),
        ("Read timed out", "timed out"),
        ("connection reset by peer", "unavailable"),
    ],
)
def test_a_failure_reason_is_named_not_guessed(text, expected):
    """The UI says *why* it fell back. "unavailable" for a rate limit sends
    someone hunting a dead key that is fine."""
    assert generation.classify_error(Exception(text)) == expected
