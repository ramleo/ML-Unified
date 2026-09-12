"""The EDA suggestion route's provider handling.

This route was written before the provider discipline the rest of the app
now follows, and it sat unmounted long enough to miss every correction. All
three of the following were true when it was folded in:

  * Cohere was pinned to command-r-plus-08-2024. The undated sibling of
    that name is retired and 404s on v2/chat — the same failure that made
    the document extractor fall through to the paid key for weeks.
  * The default provider was Mistral, which has no reserved free capacity
    and rate limits a large share of requests.
  * There was no cascade. One provider was tried, and a paid Gemini key was
    selectable by any anonymous caller with no daily budget in front of it.

None of this needs a model to test. It is a lookup table and an ordering.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from routers.eda import _suggest
from security import budget


# -- Model names ---------------------------------------------------------------

def test_cohere_uses_the_model_this_space_has_actually_served():
    """command-a-03-2025 is what the other Cohere call sites here use. A
    dated command-r-plus variant is exactly the string that was silently
    404ing elsewhere in this codebase."""
    assert _suggest._PROVIDERS["cohere"]["model"] == "command-a-03-2025"


def test_no_provider_is_pinned_to_a_retired_command_r_name():
    for name, cfg in _suggest._PROVIDERS.items():
        assert "command-r-plus" not in cfg["model"], f"{name} uses a retired model name"


def test_every_provider_declares_a_key_variable_and_a_model():
    for name, cfg in _suggest._PROVIDERS.items():
        assert cfg["env"].endswith("_API_KEY"), name
        assert cfg["model"].strip(), name


def test_every_provider_in_the_cascade_has_a_streamer():
    """A name in the order with no implementation is a silent skip that
    looks like a provider outage."""
    for name in _suggest._CASCADE_ORDER:
        assert name in _suggest._STREAMERS
        assert name in _suggest._PROVIDERS


# -- Order ---------------------------------------------------------------------

def test_the_cascade_is_free_first_and_paid_last():
    assert _suggest._CASCADE_ORDER == ("cohere", "mistral", "gemini")


@pytest.mark.parametrize("paid", _suggest.PAID_PROVIDERS)
def test_the_paid_provider_is_last(paid):
    order = list(_suggest._CASCADE_ORDER)
    assert order[-1] == paid
    assert order.count(paid) == 1


def test_the_default_is_the_free_reliable_provider_not_the_rate_limited_one():
    """Mistral was the default and 429s often. A default that usually fails
    is not a default, it is a delay in front of the real one."""
    assert _suggest._candidates("auto")[0] == "cohere"
    assert _suggest.SuggestRequest.model_fields["provider"].default == "auto"


# -- Candidate list ------------------------------------------------------------

def test_the_callers_choice_comes_first_and_is_not_repeated():
    candidates = _suggest._candidates("mistral")

    assert candidates[0] == "mistral"
    assert candidates.count("mistral") == 1
    assert candidates[-1] == "gemini"


def test_asking_for_the_paid_provider_is_honoured_but_not_duplicated():
    """A deliberate choice is still the caller's to make. It just must not
    also appear as a fallback behind itself."""
    candidates = _suggest._candidates("gemini")

    assert candidates[0] == "gemini"
    assert candidates.count("gemini") == 1


def test_a_provider_outside_the_cascade_still_gets_the_cascade_behind_it():
    """Groq is selectable but deliberately not automatic. Choosing it must
    not mean losing the fallback."""
    candidates = _suggest._candidates("groq")

    assert candidates[0] == "groq"
    assert candidates[1:] == ["cohere", "mistral", "gemini"]


@pytest.mark.parametrize("asked", ["", "auto", "not-a-provider", "COHERE", None])
def test_an_unusable_provider_name_falls_back_to_the_cascade(asked):
    """A typo must not become an error page when three providers are ready
    to serve."""
    candidates = _suggest._candidates(asked)

    assert candidates[0] in ("cohere",)
    assert candidates[-1] == "gemini"


def test_the_paid_provider_is_last_whatever_was_asked_for():
    for asked in ["", "auto", "cohere", "mistral", "groq", "nonsense"]:
        assert _suggest._candidates(asked)[-1] == "gemini", asked


# -- Failure reasons -----------------------------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("429 Too Many Requests", "rate limited"),
        ("over capacity, try again", "rate limited"),
        ("401 Unauthorized", "invalid or unauthorized key"),
        ("invalid api key provided", "invalid or unauthorized key"),
        ("404 model_not_found", "model not found"),
        ("Read timed out", "timed out"),
        ("connection reset", "unavailable"),
    ],
)
def test_a_failure_is_named_not_guessed(text, expected):
    """"unavailable" for a retired model name sends somebody hunting a
    network problem that does not exist."""
    assert _suggest._short_reason(text) == expected


# -- Budget --------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_budget():
    budget._counts.clear()
    yield
    budget._counts.clear()


def test_the_route_is_behind_a_daily_budget(monkeypatch):
    """This route offers a paid key to any anonymous visitor. Before it was
    folded in there was no cap at all."""
    monkeypatch.setenv("EDA_SUGGEST_DAILY_CAP", "2")

    for _ in range(2):
        budget.check_and_record_call("eda-suggest", pool="eda_suggest",
                                     daily_cap_env="EDA_SUGGEST_DAILY_CAP")

    with pytest.raises(HTTPException) as exc:
        budget.check_and_record_call("eda-suggest", pool="eda_suggest",
                                     daily_cap_env="EDA_SUGGEST_DAILY_CAP")
    assert exc.value.status_code == 429


def test_the_endpoint_checks_the_budget_before_opening_a_stream():
    """Order matters: a cap checked after the request has been sent has
    already spent the money it exists to save."""
    import inspect

    src = inspect.getsource(_suggest.suggest_features)
    assert src.index("check_and_record_call") < src.index("StreamingResponse")


def test_the_endpoint_carries_a_rate_limit():
    import inspect

    src = inspect.getsource(_suggest)
    assert "@limiter.limit(LLM_LIMIT)" in src
