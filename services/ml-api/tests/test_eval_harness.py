"""The golden-set harness, tested without a golden set run.

A nightly eval is only worth having if a green result means something, and
that depends entirely on this scoring code. If `score()` were lenient in
the wrong place, the nightly job would report PASS through the exact
regression it was built to catch — worse than having no job at all, since
somebody is now trusting it.

So the harness gets the same treatment as the rest of the deterministic
shell: fabricated results, hard assertions, no network, run on every push.
The golden set's own shape is checked here too, because a typo in a field
name would silently miss forever and read as a model getting worse.
"""
from __future__ import annotations

import pytest

from evals import _check
from evals._client import Result
from evals._score import PAID_PROVIDERS, score
from evals.goldens import GOLDENS
from routers.document._schema import DOC_TYPES


def result_for(golden: dict, *, provider="cohere", doc_type=None,
               overrides=None, flag=(), cached=False) -> Result:
    """A Result that answers `golden` perfectly, then applies overrides."""
    overrides = overrides or {}
    res = Result()
    res.done = {"done": True, "doc_type": doc_type or golden["doc_type"],
                "provider": provider, "cached": cached}
    for name, (_kind, expected) in golden["values"].items():
        res.fields.append({
            "name": name,
            "value": overrides.get(name, expected),
            "validation": {"status": "flagged" if name in flag else "ok", "note": ""},
        })
    return res


CLEAN = GOLDENS[0]  # invoice_consistent
BAD_SUM = GOLDENS[1]  # invoice_total_does_not_add_up


# -- Value comparison ----------------------------------------------------------

@pytest.mark.parametrize("actual", ["1180", "1180.00", "1,180.00", "$1,180.00", "USD 1180.00"])
def test_an_amount_is_right_however_it_is_written(actual):
    """Five spellings of the same correct answer. A test that accepts one
    of them fails on correct extractions and gets ignored."""
    assert _check.matches("amount", "1180.00", actual)[0]


@pytest.mark.parametrize("actual", ["1181.00", "118.00", "0", "eleven eighty"])
def test_a_wrong_amount_is_caught(actual):
    assert not _check.matches("amount", "1180.00", actual)[0]


@pytest.mark.parametrize(
    "actual", ["2026-03-04", "04/03/2026", "4 March 2026", "March 4, 2026", "04-03-2026"]
)
def test_a_date_is_right_however_it_is_formatted(actual):
    assert _check.matches("date", "2026-03-04", actual)[0]


def test_a_date_in_the_wrong_month_is_caught():
    assert not _check.matches("date", "2026-03-04", "2026-04-03")[0]


@pytest.mark.parametrize(
    "actual", ["Northwind Trading", "Northwind Trading Ltd.", "NORTHWIND TRADING LTD"]
)
def test_text_matches_in_either_direction(actual):
    """A model returning the vendor with or without its suffix is right
    both times. Choosing one as canonical would be a judgement about
    phrasing, not correctness."""
    assert _check.matches("text", "Northwind Trading", actual)[0]


@pytest.mark.parametrize("actual", ["Calder Robotics", "", "   ", None])
def test_text_that_is_not_the_answer_is_caught(actual):
    assert not _check.matches("text", "Northwind Trading", actual)[0]


def test_a_failure_reason_names_both_values():
    """This line is what somebody reads when the nightly job mails them.
    "mismatch" would send them to run it again by hand."""
    _ok, why = _check.matches("amount", "1180.00", "1500.00")
    assert "1180" in why and "1500" in why


# -- Hard rules ----------------------------------------------------------------

def test_a_perfect_answer_passes_with_a_full_score():
    verdict = score(CLEAN, result_for(CLEAN))
    assert not verdict.failed
    assert not verdict.inconclusive
    assert verdict.score == 1.0


@pytest.mark.parametrize("paid", PAID_PROVIDERS)
def test_the_paid_provider_serving_is_a_hard_failure(paid):
    """The whole reason this suite runs against the live cascade. Every
    value can be perfect and the run still fails, because a correct answer
    from the billed key means the two free providers ahead of it are dead
    and nobody has noticed."""
    verdict = score(CLEAN, result_for(CLEAN, provider=paid))

    assert verdict.failed
    assert verdict.score == 1.0, "the answers were right; that is not the problem"
    assert "PAID" in " ".join(verdict.hard_failures)


def test_a_cached_answer_is_a_hard_failure():
    """The cache keys on the file bytes. If it ever answers, the run
    exercised no model and its green result means nothing."""
    verdict = score(CLEAN, result_for(CLEAN, provider="cohere (cached)", cached=True))

    assert verdict.failed
    assert "cache" in " ".join(verdict.hard_failures)


def test_the_cached_suffix_alone_is_enough_to_catch_it():
    """Belt and braces: the flag and the provider string are set by
    different lines of the router."""
    res = result_for(CLEAN, provider="cohere (cached)")
    res.done["cached"] = False

    assert score(CLEAN, res).failed


def test_the_wrong_document_type_is_a_hard_failure():
    """Eight types, a closed set, chosen from the document's own words.
    A model gets no vote on whether a receipt is an invoice."""
    verdict = score(CLEAN, result_for(CLEAN, doc_type="receipt"))

    assert verdict.failed
    assert "receipt" in " ".join(verdict.hard_failures)


def test_a_total_that_does_not_add_up_but_was_not_flagged_fails():
    """The check that catches a padded invoice. If the validator passes
    1000 + 180 = 1500, the tool is telling the user a lie."""
    verdict = score(BAD_SUM, result_for(BAD_SUM))  # nothing flagged

    assert verdict.failed
    assert "does not add up" in " ".join(verdict.hard_failures)


def test_a_total_that_does_not_add_up_and_was_flagged_passes():
    verdict = score(BAD_SUM, result_for(BAD_SUM, flag=("total",)))
    assert not verdict.failed


def test_flagging_a_correct_total_fails():
    """A false alarm on every clean invoice is how a useful warning turns
    into one people click past."""
    verdict = score(CLEAN, result_for(CLEAN, flag=("total",)))

    assert verdict.failed
    assert "flagged it" in " ".join(verdict.hard_failures)


def test_an_arithmetic_rule_is_skipped_when_the_field_was_never_extracted():
    """No total means no sum to check. Failing here would report a missing
    field twice, once as a value miss and once as a phantom rule break."""
    res = result_for(BAD_SUM)
    res.fields = [f for f in res.fields if f["name"] != "total"]

    assert not score(BAD_SUM, res).failed


# -- Scored, not hard ----------------------------------------------------------

def test_a_wrong_value_lowers_the_score_without_failing_the_document():
    """One missed field on one night is noise. The run is judged on the
    aggregate, which is what the threshold in run.py is for."""
    verdict = score(CLEAN, result_for(CLEAN, overrides={"bill_to": "somebody else"}))

    assert not verdict.failed
    assert verdict.matched == verdict.total - 1
    assert [name for name, _ in verdict.misses] == ["bill_to"]


def test_a_field_the_model_never_returned_counts_as_a_miss():
    res = result_for(CLEAN)
    res.fields = [f for f in res.fields if f["name"] != "tax"]

    verdict = score(CLEAN, res)

    assert not verdict.failed
    assert ("tax", "expected '180.00', got nothing") in [
        (n, w) for n, w in verdict.misses
    ]


# -- Inconclusive, not failed --------------------------------------------------

def test_a_provider_outage_is_inconclusive_rather_than_a_regression():
    """A free tier out of capacity is not a bug in this repo. Reporting it
    as one is how a suite becomes noise people mute."""
    res = Result()
    res.done = {"done": True, "provider": "", "doc_type": "invoice"}
    res.warning = "No fields extracted — AI providers may be temporarily unavailable."

    verdict = score(CLEAN, res)

    assert verdict.inconclusive
    assert not verdict.failed


def test_a_network_failure_is_inconclusive():
    res = Result()
    res.error = "ConnectTimeout: the Space did not answer"

    verdict = score(CLEAN, res)

    assert verdict.inconclusive
    assert "ConnectTimeout" in verdict.inconclusive_reason


def test_fields_with_no_named_provider_is_inconclusive_not_silent():
    res = result_for(CLEAN, provider="")

    assert score(CLEAN, res).inconclusive


# -- The golden set's own shape ------------------------------------------------

def test_golden_ids_are_unique():
    ids = [g["id"] for g in GOLDENS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("golden", GOLDENS, ids=[g["id"] for g in GOLDENS])
def test_a_golden_expects_a_document_type_the_app_supports(golden):
    assert golden["doc_type"] in DOC_TYPES


@pytest.mark.parametrize("golden", GOLDENS, ids=[g["id"] for g in GOLDENS])
def test_every_expected_field_exists_in_that_types_schema(golden):
    """A typo'd field name can never match anything, so it would show up
    as the model getting quietly worse and nobody would find the cause."""
    schema_names = {f["name"] for f in DOC_TYPES[golden["doc_type"]]["fields"]}
    for name in list(golden["values"]) + golden["must_flag"] + golden["must_not_flag"]:
        assert name in schema_names, f"{golden['id']} expects unknown field {name!r}"


@pytest.mark.parametrize("golden", GOLDENS, ids=[g["id"] for g in GOLDENS])
def test_every_expected_value_declares_how_to_compare_it(golden):
    for name, (kind, expected) in golden["values"].items():
        assert kind in {"amount", "date", "text"}, f"{golden['id']}.{name}"
        assert str(expected).strip(), f"{golden['id']}.{name} expects nothing"


@pytest.mark.parametrize("golden", GOLDENS, ids=[g["id"] for g in GOLDENS])
def test_a_golden_actually_contains_the_text_it_expects_to_find(golden):
    """The document has to say the answer somewhere, or the eval is asking
    a model to invent it and calling the invention correct."""
    body = " ".join(golden["lines"]).lower()
    for name, (kind, expected) in golden["values"].items():
        if kind != "text":
            continue
        assert expected.lower() in body, f"{golden['id']} expects {name}={expected!r}, absent from the document"
