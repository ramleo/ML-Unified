"""Phase 3: the daily spend caps, tested at the boundary.

Both budget modules exist because of the same real incident: a debugging
session made a long run of individually reasonable paid calls that nobody
totalled up until the bill did. A cap that is off by one at the boundary,
or that counts rejected calls, or that shares a counter between two pools
that were meant to be independent, fails in exactly the situation it was
written for and in no other — which is why it needs a test rather than a
careful read.

Both modules hold their counters in a module-level dict, so every test here
clears it first. That is also the honest limit of these tests: they prove
the arithmetic, not that the count survives a Space restart. It does not,
deliberately, and both modules say so.
"""
from __future__ import annotations

import datetime

import pytest
from fastapi import HTTPException

from routers.rag import _image_gen_budget as img_budget
from security import budget

TODAY = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
YESTERDAY = (datetime.datetime.now(datetime.timezone.utc).date()
             - datetime.timedelta(days=1)).isoformat()


@pytest.fixture(autouse=True)
def _clean_counters():
    """These counters are process-global. Without this, the first test to
    run decides what every later one sees."""
    budget._counts.clear()
    img_budget._counts.clear()
    yield
    budget._counts.clear()
    img_budget._counts.clear()


def _call(n: int, cap_env: str = "TEST_CAP", pool: str = "p") -> None:
    for _ in range(n):
        budget.check_and_record_call("test-feature", pool=pool, daily_cap_env=cap_env)


# -- The boundary -------------------------------------------------------------

def test_calls_up_to_the_cap_are_allowed(monkeypatch):
    monkeypatch.setenv("TEST_CAP", "3")
    _call(3)  # the third call is the cap, not one past it


def test_the_call_after_the_cap_is_refused(monkeypatch):
    monkeypatch.setenv("TEST_CAP", "3")
    _call(3)

    with pytest.raises(HTTPException) as exc:
        _call(1)

    assert exc.value.status_code == 429


def test_the_refusal_says_what_the_cap_was(monkeypatch):
    """A 429 with no number reads as "you are going too fast". This one
    means "this demo has spent its day", and the message has to carry the
    difference or the caller retries in a minute forever."""
    monkeypatch.setenv("TEST_CAP", "2")
    _call(2)

    with pytest.raises(HTTPException) as exc:
        _call(1)

    assert "2" in exc.value.detail
    assert "midnight" in exc.value.detail.lower()


def test_a_refused_call_does_not_count_against_tomorrow(monkeypatch):
    """If the counter kept climbing on rejection, a burst of blocked
    requests would leave the pool far past its cap, and nothing about that
    is visible in the log line."""
    monkeypatch.setenv("TEST_CAP", "1")
    _call(1)
    for _ in range(5):
        with pytest.raises(HTTPException):
            _call(1)

    assert budget._counts[("p", TODAY)] == 1


def test_a_cap_of_zero_refuses_the_very_first_call(monkeypatch):
    """The kill switch. Setting the env var to 0 has to actually stop the
    feature, not let one call through."""
    monkeypatch.setenv("TEST_CAP", "0")

    with pytest.raises(HTTPException):
        _call(1)


# -- Pools and days -----------------------------------------------------------

def test_two_pools_do_not_share_a_counter(monkeypatch):
    """text-to-image was given its own pool precisely so casual re-rolling
    could not starve sharpen and AI-fill for the rest of the day."""
    monkeypatch.setenv("TEST_CAP", "1")
    _call(1, pool="first")

    _call(1, pool="second")  # must not raise

    assert budget._counts[("first", TODAY)] == 1
    assert budget._counts[("second", TODAY)] == 1


def test_yesterdays_spend_does_not_block_today(monkeypatch):
    monkeypatch.setenv("TEST_CAP", "1")
    budget._counts[("p", YESTERDAY)] = 99

    _call(1)  # must not raise

    assert budget._counts[("p", TODAY)] == 1


# -- Configuration ------------------------------------------------------------

def test_an_unset_env_var_falls_back_to_a_cap_not_to_unlimited(monkeypatch):
    """A renamed or mistyped env var must degrade to the default cap. The
    dangerous version of this bug is the one where a missing setting means
    no limit at all."""
    monkeypatch.delenv("NO_SUCH_CAP", raising=False)

    budget._counts[("p", TODAY)] = 19  # one below the documented default of 20
    _call(1, cap_env="NO_SUCH_CAP")

    with pytest.raises(HTTPException):
        _call(1, cap_env="NO_SUCH_CAP")


def test_the_cap_is_read_per_call_not_frozen_at_import(monkeypatch):
    """The env var is read inside the function, which is what lets the cap
    be raised on a live Space by restarting with a new value rather than
    by editing code."""
    monkeypatch.setenv("TEST_CAP", "1")
    _call(1)
    with pytest.raises(HTTPException):
        _call(1)

    monkeypatch.setenv("TEST_CAP", "5")
    _call(1)  # the same pool, same day, now under a higher cap


# -- The image-generation pools ------------------------------------------------

def test_every_image_pool_has_a_cap_and_a_message():
    """A pool present in one dict and missing from the other raises a
    KeyError from inside the guard — turning a spend limit into a 500."""
    assert set(img_budget._CAPS) == set(img_budget._MESSAGES)
    for pool, cap in img_budget._CAPS.items():
        assert cap > 0, f"pool {pool} has a non-positive cap"
        assert "{cap}" in img_budget._MESSAGES[pool], f"pool {pool} never states its cap"


def test_an_unknown_image_pool_fails_loudly(monkeypatch):
    """Deliberate: a typo'd pool name must not quietly mean "no cap". This
    asserts the current behaviour so that changing it is a decision."""
    with pytest.raises(KeyError):
        img_budget.check_and_record_call("test", pool="not-a-pool")


def test_the_image_budget_enforces_its_own_boundary(monkeypatch):
    monkeypatch.setitem(img_budget._CAPS, "text2img", 2)

    img_budget.check_and_record_call("text-to-image", pool="text2img")
    img_budget.check_and_record_call("text-to-image", pool="text2img")

    with pytest.raises(HTTPException) as exc:
        img_budget.check_and_record_call("text-to-image", pool="text2img")

    assert exc.value.status_code == 429
    assert "2" in exc.value.detail


def test_the_image_pools_are_independent(monkeypatch):
    monkeypatch.setitem(img_budget._CAPS, "text2img", 1)
    monkeypatch.setitem(img_budget._CAPS, "shared", 1)

    img_budget.check_and_record_call("text-to-image", pool="text2img")
    img_budget.check_and_record_call("deblur", pool="shared")  # must not raise

    with pytest.raises(HTTPException):
        img_budget.check_and_record_call("text-to-image", pool="text2img")
