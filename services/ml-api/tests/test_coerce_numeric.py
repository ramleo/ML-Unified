"""The numeric coercion that /predict and /shap put every request through.

`df.apply(pd.to_numeric, errors="ignore")` was deprecated in pandas 2.2 and
removed in 3.0, where it raises ValueError("invalid error value specified").
The Dependabot bump to pandas 3 turned seven prediction tests red on that one
line, in two files.

These tests exist because the obvious replacement is wrong in a way no
integration test would notice quickly: `errors="coerce"` also stops raising,
but it turns every unconvertible value into NaN, so a passenger's cabin letter
or an insurance region becomes a blank on the way into the pipeline and the
model quietly predicts from nothing. `test_a_text_column_is_left_alone` fails
against that version and passes against this one.
"""
import numpy as np
import pandas as pd
import pytest

from routers.core.shared import coerce_numeric


def test_numeric_strings_become_numbers():
    df = coerce_numeric(pd.DataFrame([{"age": "22", "fare": "7.25"}]))
    assert pd.api.types.is_numeric_dtype(df["age"])
    assert pd.api.types.is_numeric_dtype(df["fare"])
    assert df["age"].iloc[0] == 22
    assert df["fare"].iloc[0] == pytest.approx(7.25)


def test_a_text_column_is_left_alone():
    """The whole point. `errors="coerce"` would make this NaN."""
    df = coerce_numeric(pd.DataFrame([{"embarked": "S", "sex": "female"}]))
    assert df["embarked"].iloc[0] == "S"
    assert df["sex"].iloc[0] == "female"


def test_one_bad_value_keeps_the_whole_column_as_text():
    """All-or-nothing per column, which is what the removed option did.

    A column of mostly-numbers with one "n/a" stays text rather than becoming
    numbers with a hole in it. Half-converting would change what the model is
    given depending on a single row's typo.
    """
    df = coerce_numeric(pd.DataFrame({"fare": ["7.25", "n/a", "8.05"]}))
    assert not pd.api.types.is_numeric_dtype(df["fare"])
    assert list(df["fare"]) == ["7.25", "n/a", "8.05"]


def test_missing_values_do_not_block_conversion():
    """A None in an otherwise numeric column is NaN, not a reason to give up.

    Every /predict request goes through `ensure_cols`, which sets absent
    fields to None, and id columns are set to NaN outright — so this is the
    common case, not an edge one.
    """
    df = coerce_numeric(pd.DataFrame({"age": ["22", None, "31"]}))
    assert pd.api.types.is_numeric_dtype(df["age"])
    assert df["age"].iloc[0] == 22
    assert np.isnan(df["age"].iloc[1])


def test_already_numeric_columns_are_unchanged():
    before = pd.DataFrame({"age": [22, 31], "fare": [7.25, 8.05]})
    after = coerce_numeric(before.copy())
    pd.testing.assert_frame_equal(before, after)


def test_an_empty_frame_is_not_an_error():
    assert coerce_numeric(pd.DataFrame()).empty
