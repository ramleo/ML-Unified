"""Phase 3: the schema, and the shape of what comes back from a model.

The lesson behind this file is narrow and expensive: a claim produced by a
model does not belong in a fixed script. A demo narration said the invoice
extractor returns 15 fields; it returned 13 on one provider and 18 on
another, because a model decides how many extra sections it volunteers.

The field COUNT is not a fact. The SCHEMA is — it is a constant in
`_schema.py`, and it is the only part of that sentence anything should ever
be asserted about. So this file pins the schema hard, and pins the
normaliser that stands between a model's output and the rest of the app,
and asserts nothing whatsoever about how many fields a model returns.
"""
from __future__ import annotations

import json

import pytest

from routers.document import _llm
from routers.document._schema import DOC_TYPES

ALL_TYPES = sorted(DOC_TYPES)


# -- The schema is a constant --------------------------------------------------

def test_the_invoice_schema_is_the_nine_fields_the_narration_names():
    """The one field list a script is allowed to quote out loud."""
    assert [f["name"] for f in DOC_TYPES["invoice"]["fields"]] == [
        "vendor", "invoice_no", "date", "due_date", "bill_to",
        "subtotal", "tax", "total", "payment_terms",
    ]


def test_all_eight_document_types_are_present():
    assert len(DOC_TYPES) == 8


@pytest.mark.parametrize("doc_type", ALL_TYPES)
def test_a_type_declares_a_label_a_description_and_fields(doc_type):
    spec = DOC_TYPES[doc_type]
    assert spec["label"].strip()
    assert spec["description"].strip()
    assert spec["fields"], f"{doc_type} has no fields"


@pytest.mark.parametrize("doc_type", ALL_TYPES)
def test_field_names_are_unique_within_a_type(doc_type):
    """A duplicate name is silently dropped by the normaliser's `seen` set,
    so the second one just never appears and nothing says why."""
    names = [f["name"] for f in DOC_TYPES[doc_type]["fields"]]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("doc_type", ALL_TYPES)
def test_every_field_is_fully_specified(doc_type):
    """A missing `field_type` reaches the UI as an untyped text box and a
    missing `label` reaches it as a raw snake_case name."""
    for field in DOC_TYPES[doc_type]["fields"]:
        assert field["name"] == field["name"].lower().strip()
        assert " " not in field["name"]
        assert field["label"].strip()
        assert field["field_type"] in {"text", "date", "currency"}


# -- Classification falls back rather than failing -----------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("Invoice #4410 — amount due, payment terms Net 30, subtotal", "invoice"),
        ("Work experience, LinkedIn, GitHub, soft skills, career summary", "resume"),
        ("Opening balance, closing balance, account statement", "bank_statement"),
    ],
)
def test_the_keyword_classifier_recognises_an_obvious_document(text, expected):
    """This runs when every provider has failed. It is not meant to be
    good, but a wrong answer here is what the user sees, so the easy cases
    have to work."""
    doc_type, confidence = _llm._keyword_classify(text, ALL_TYPES)
    assert doc_type == expected
    assert 0.0 <= confidence <= 1.0


def test_the_keyword_classifier_always_returns_a_known_type():
    """Given nothing it recognises, it must still name a type the app has a
    schema for — a type nobody defined crashes the extraction step."""
    doc_type, confidence = _llm._keyword_classify("zzz qqq", ALL_TYPES)
    assert doc_type in ALL_TYPES
    assert confidence < 0.55, "a guess must not be reported as a confident answer"


# -- Reading a model's JSON ----------------------------------------------------

@pytest.mark.parametrize(
    "raw",
    [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        '```\n{"a": 1}\n```',
        'Sure! Here is the JSON you asked for:\n{"a": 1}\nLet me know if...',
    ],
    ids=["bare", "fenced-json", "fenced-plain", "wrapped-in-prose"],
)
def test_json_is_recovered_from_the_ways_models_actually_return_it(raw):
    assert _llm._parse_json(raw) == {"a": 1}


@pytest.mark.parametrize("raw", ["", "   ", "no json here", "{not valid", "[1, 2, 3]"])
def test_unparseable_output_becomes_an_empty_dict_not_an_exception(raw):
    """The caller does `.get("fields", [])` on this. Raising here would
    turn a bad model response into a 500 on a route that has a keyword
    fallback ready to run."""
    assert _llm._parse_json(raw) == {}


# -- The normaliser ------------------------------------------------------------

META = {"total": {"name": "total", "label": "Total Amount", "field_type": "currency"}}


def _norm(fields, **kw):
    return _llm._normalize_fields(fields, META, **kw)


@pytest.mark.parametrize(
    "value",
    ["null", "None", "N/A", "na", "not found", "Not Available", "unknown", "-", "", "   "],
)
def test_a_model_saying_it_found_nothing_is_dropped(value):
    """Every one of these has been returned by some provider as the value
    of a field it could not find. Rendering the literal string "N/A" as an
    extracted value is worse than showing the field as missing."""
    assert _norm([{"name": "total", "value": value}]) == []


def test_a_real_none_is_dropped_too():
    assert _norm([{"name": "total", "value": None}]) == []


def test_a_field_with_no_name_is_dropped():
    assert _norm([{"name": "", "value": "100"}]) == []


def test_the_first_of_a_duplicated_field_wins():
    out = _norm([{"name": "total", "value": "100"}, {"name": "total", "value": "999"}])
    assert [f["value"] for f in out] == ["100"]


def test_the_schema_label_beats_the_one_the_model_invented():
    """The model is free to call it "Grand Total Amount Due". The UI column
    heading is not."""
    out = _norm([{"name": "total", "value": "100", "label": "Grand Total Amount Due"}])
    assert out[0]["label"] == "Total Amount"
    assert out[0]["field_type"] == "currency"


def test_a_field_the_schema_never_declared_is_kept_and_prettified():
    """The extractor deliberately asks for extra sections beyond the
    schema. They must survive, typed as text, with a readable label."""
    out = _norm([{"name": "shipping_notes", "value": "Leave at door"}])
    assert out[0]["label"] == "Shipping Notes"
    assert out[0]["field_type"] == "text"


@pytest.mark.parametrize("given,expected", [(1.7, 1.0), (-0.5, 0.0), (0.42, 0.42)])
def test_confidence_is_clamped_to_a_real_probability(given, expected):
    """A confidence over 1 renders as a progress bar past the end of its
    track, and a negative one renders as an empty bar on a correct value."""
    out = _norm([{"name": "total", "value": "100", "confidence": given}])
    assert out[0]["confidence"] == expected


def test_a_missing_confidence_gets_a_default_not_a_crash():
    assert _norm([{"name": "total", "value": "100"}])[0]["confidence"] == 0.7


def test_a_structured_value_serialises_as_valid_json():
    """`str()` on a Python dict emits single quotes, which `json.loads`
    downstream in the validator and the bbox search cannot read. The
    line-items sum check silently skips every invoice when that happens."""
    out = _norm([{"name": "line_items", "value": [{"amount": 10}, {"amount": 20}]}])
    assert json.loads(out[0]["value"]) == [{"amount": 10}, {"amount": 20}]


def test_single_quoted_pseudo_json_from_a_model_is_repaired():
    """Some models return the structure as a string already, in Python
    repr form. Same failure downstream, different cause."""
    out = _norm([{"name": "line_items", "value": "[{'amount': 10}]"}])
    assert json.loads(out[0]["value"]) == [{"amount": 10}]


def test_a_bbox_is_ignored_unless_the_caller_asked_for_one():
    """The text path has no page coordinates to give. A bbox arriving from
    a model that invented it would draw a highlight box over the wrong part
    of the page — a confident, wrong citation."""
    out = _norm([{"name": "total", "value": "100", "bbox": [1, 2, 3, 4]}])
    assert out[0]["bbox"] is None


@pytest.mark.parametrize("bbox", [[1, 2, 3], "1,2,3,4", {"x": 1}, [1, 2, 3, 4, 5]])
def test_a_malformed_bbox_is_discarded_rather_than_passed_on(bbox):
    out = _norm([{"name": "total", "value": "100", "bbox": bbox}], allow_bbox=True)
    assert out[0]["bbox"] is None


def test_a_well_formed_bbox_survives_when_allowed():
    out = _norm([{"name": "total", "value": "100", "bbox": [1, 2, 3, 4]}], allow_bbox=True)
    assert out[0]["bbox"] == [1, 2, 3, 4]


def test_every_returned_field_has_the_full_shape_the_ui_reads():
    out = _norm([{"name": "total", "value": "100"}])
    assert set(out[0]) == {"name", "label", "value", "confidence", "field_type", "bbox", "page"}
