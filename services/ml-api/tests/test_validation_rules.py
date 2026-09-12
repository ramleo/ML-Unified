"""Phase 3: the deterministic half of validation.

`validate_and_correct` runs three passes. Two of them are arithmetic and
regex — free, instant, and completely predictable — and one asks a model.
Only the deterministic passes are tested here; the model pass is stubbed
out, because a test that asks a free-tier provider a question goes red on
capacity and teaches people to ignore the suite.

The rule that matters most is the precedence at the bottom of
`validate_and_correct`: arithmetic beats the model. A model told that a
total is wrong will often agree that it is right, and the sum is not a
matter of opinion.
"""
from __future__ import annotations

import pytest

from routers.document import _validate


@pytest.fixture(autouse=True)
def _no_model_calls(monkeypatch):
    """The third pass is not under test. Left live it would make these
    tests slow, non-deterministic and occasionally billed."""
    monkeypatch.setattr(_validate, "_llm_consistency_check", lambda fields, doc_type: {})


def field(name, value, confidence=0.9):
    return {"name": name, "value": value, "confidence": confidence}


def statuses(fields):
    return {f["name"]: f["validation"]["status"] for f in fields}


# -- Amount parsing ------------------------------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("1234.56", 1234.56),
        ("1,234.56", 1234.56),
        ("$1,234.56", 1234.56),
        ("USD 1,234.56", 1234.56),
        ("no digits at all", None),
        ("", None),
    ],
)
def test_amounts_are_read_out_of_the_strings_documents_actually_contain(text, expected):
    assert _validate._parse_amount(text) == expected


# -- Invoice arithmetic --------------------------------------------------------

def test_a_total_that_matches_subtotal_plus_tax_passes():
    fields = [field("subtotal", "1000.00"), field("tax", "180.00"), field("total", "1180.00")]

    assert statuses(_validate.validate_and_correct(fields, "invoice")) == {
        "subtotal": "ok", "tax": "ok", "total": "ok"
    }


def test_a_total_that_does_not_add_up_is_flagged_on_the_total():
    """Flagged on `total`, not on `subtotal` — the field the reviewer has
    to look at is the one carrying the note."""
    fields = [field("subtotal", "1000.00"), field("tax", "180.00"), field("total", "1500.00")]

    out = _validate.validate_and_correct(fields, "invoice")

    assert statuses(out)["total"] == "flagged"
    assert "1500" in out[2]["validation"]["note"]


def test_rounding_of_a_cent_or_two_is_not_an_error():
    """A 2% tolerance, not exact equality: real invoices round per line."""
    fields = [field("subtotal", "1000.00"), field("tax", "180.00"), field("total", "1180.01")]

    assert statuses(_validate.validate_and_correct(fields, "invoice"))["total"] == "ok"


def test_an_invoice_with_no_tax_line_still_gets_checked():
    fields = [field("subtotal", "1000.00"), field("total", "1400.00")]

    assert statuses(_validate.validate_and_correct(fields, "invoice"))["total"] == "flagged"


def test_a_check_with_nothing_to_compare_stays_silent():
    """No subtotal means no arithmetic. Flagging here would put a warning
    on every document that simply does not carry the field."""
    fields = [field("vendor", "Acme"), field("total", "1400.00")]

    assert statuses(_validate.validate_and_correct(fields, "invoice"))["total"] == "ok"


# -- Bank statement arithmetic -------------------------------------------------

def test_a_balance_that_reconciles_passes():
    fields = [field("opening_balance", "5000"), field("total_credits", "2000"),
              field("total_debits", "1500"), field("closing_balance", "5500")]

    assert set(statuses(_validate.validate_and_correct(fields, "bank_statement")).values()) == {"ok"}


def test_a_balance_that_does_not_reconcile_is_flagged_on_the_closing_figure():
    fields = [field("opening_balance", "5000"), field("total_credits", "2000"),
              field("total_debits", "1500"), field("closing_balance", "9000")]

    out = _validate.validate_and_correct(fields, "bank_statement")

    assert statuses(out)["closing_balance"] == "flagged"


def test_one_missing_figure_skips_the_equation_rather_than_guessing_zero():
    """Treating an absent `total_debits` as 0 would flag a perfectly
    correct statement."""
    fields = [field("opening_balance", "5000"), field("total_credits", "2000"),
              field("closing_balance", "5500")]

    assert statuses(_validate.validate_and_correct(fields, "bank_statement"))["closing_balance"] == "ok"


# -- Line items ----------------------------------------------------------------

def test_line_items_that_sum_to_the_subtotal_pass():
    items = '[{"amount": 600}, {"amount": 400}]'
    fields = [field("line_items", items), field("subtotal", "1000.00")]

    assert statuses(_validate.validate_and_correct(fields, "invoice"))["line_items"] == "ok"


def test_line_items_that_do_not_sum_to_the_subtotal_are_flagged():
    items = '[{"amount": 600}, {"amount": 100}]'
    fields = [field("line_items", items), field("subtotal", "1000.00")]

    out = _validate.validate_and_correct(fields, "invoice")

    assert statuses(out)["line_items"] == "flagged"
    assert "700" in out[0]["validation"]["note"]


def test_line_items_that_are_not_parseable_json_are_skipped_not_flagged():
    """This is why `_normalize_fields` has to emit real JSON. If the value
    arrives as Python repr, the check quietly does nothing — no error, no
    flag, no verification. Silence, on the check that catches padded
    invoices."""
    fields = [field("line_items", "[{'amount': 600}]"), field("subtotal", "1000.00")]

    assert statuses(_validate.validate_and_correct(fields, "invoice"))["line_items"] == "ok"


def test_line_items_with_no_amount_key_are_skipped():
    fields = [field("line_items", '[{"description": "widget"}]'), field("subtotal", "1000")]

    assert statuses(_validate.validate_and_correct(fields, "invoice"))["line_items"] == "ok"


# -- Format rules --------------------------------------------------------------

@pytest.mark.parametrize("value", ["2026-01-15", "15/01/2026", "15 January 2026", "January 15, 2026"])
def test_a_recognisable_date_passes(value):
    assert _validate._rule_check(field("date", value)) is None


def test_something_that_is_not_a_date_in_a_date_field_is_flagged():
    issue = _validate._rule_check(field("due_date", "upon receipt"))
    assert issue["status"] == "flagged"


@pytest.mark.parametrize("value", ["a@b.co", "first.last@example.co.uk"])
def test_a_valid_email_passes(value):
    assert _validate._rule_check(field("email", value)) is None


@pytest.mark.parametrize("value", ["not an email", "a@b", "@example.com"])
def test_an_invalid_email_is_flagged(value):
    assert _validate._rule_check(field("email", value))["status"] == "flagged"


def test_a_phone_number_too_short_to_dial_is_flagged():
    assert _validate._rule_check(field("phone", "12345"))["status"] == "flagged"


def test_low_confidence_outranks_every_format_check():
    """A field the model was unsure about gets sent for review as
    low_confidence, not argued with about its date format. The reviewer
    needs one reason, and the honest one is that the model was guessing."""
    issue = _validate._rule_check(field("due_date", "upon receipt", confidence=0.2))
    assert issue["status"] == "low_confidence"


# -- Date order ----------------------------------------------------------------

def test_an_invoice_dated_after_its_own_due_date_is_flagged():
    fields = [field("date", "2026-03-01"), field("due_date", "2026-01-01"), field("vendor", "Acme")]

    assert statuses(_validate.validate_and_correct(fields, "invoice"))["due_date"] == "flagged"


def test_dates_in_the_right_order_pass():
    fields = [field("date", "2026-01-01"), field("due_date", "2026-03-01"), field("vendor", "Acme")]

    assert statuses(_validate.validate_and_correct(fields, "invoice"))["due_date"] == "ok"


# -- Precedence and shape ------------------------------------------------------

def test_arithmetic_beats_the_model(monkeypatch):
    """The whole reason the arithmetic pass exists. A model asked whether
    1000 + 180 is 1500 will sometimes say yes."""
    monkeypatch.setattr(
        _validate, "_llm_consistency_check",
        lambda fields, doc_type: {"total": {"status": "ok", "note": "looks right to me"}},
    )
    fields = [field("subtotal", "1000.00"), field("tax", "180.00"), field("total", "1500.00")]

    assert statuses(_validate.validate_and_correct(fields, "invoice"))["total"] == "flagged"


def test_a_model_correction_never_overwrites_a_structured_value(monkeypatch):
    """Models flatten a JSON line-items array into prose when asked to
    "correct" it, destroying the only machine-readable field on the
    document."""
    original = '[{"amount": 600}]'
    monkeypatch.setattr(
        _validate, "_llm_consistency_check",
        lambda fields, doc_type: {
            "line_items": {"status": "corrected", "note": "tidied", "corrected_value": "600 for widgets"}
        },
    )
    fields = [field("line_items", original), field("subtotal", "600"), field("vendor", "Acme")]

    out = _validate.validate_and_correct(fields, "invoice")

    assert out[0]["value"] == original


def test_a_failing_model_pass_does_not_take_down_validation(monkeypatch):
    """The arithmetic result is worth returning on its own."""
    monkeypatch.setattr(
        _validate, "_llm_consistency_check",
        lambda fields, doc_type: (_ for _ in ()).throw(RuntimeError("provider down")),
    )
    fields = [field("subtotal", "1000"), field("tax", "180"), field("total", "1500")]

    assert statuses(_validate.validate_and_correct(fields, "invoice"))["total"] == "flagged"


def test_every_field_comes_back_carrying_a_verdict():
    """The UI reads `validation.status` unconditionally. A field without
    one is a crash, not a blank."""
    fields = [field("vendor", "Acme"), field("total", "100"), field("subtotal", "100")]

    for f in _validate.validate_and_correct(fields, "invoice"):
        assert set(f["validation"]) == {"status", "note"}


def test_an_empty_field_list_is_returned_untouched():
    assert _validate.validate_and_correct([], "invoice") == []
