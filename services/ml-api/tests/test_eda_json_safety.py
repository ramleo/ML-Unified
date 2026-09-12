"""The bug that made the deployed EDA service useless.

`services/ml-eda` ran as its own Space, answered /health with "ok", and
returned HTTP 500 for any CSV containing a numeric column with fewer than
four non-null values. Pandas gives NaN for the kurtosis of three points,
JSON has no NaN, and Starlette's encoder raises while serialising the
response — so the failure arrived as a bare 500 with nothing in the body.

Its own 35 tests passed the whole time. Every one of them used a dataset
large enough to have a defined kurtosis, which is the only reason the shape
that breaks it never appeared.

Nothing in the site referenced the service, so no user hit it either. It
was found by calling the deployed endpoint once with a five-row CSV.
"""
from __future__ import annotations

import io
import math

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import app
from routers.eda._utils import json_safe

client = TestClient(app)


def post(df: pd.DataFrame):
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return client.post("/eda", files={"file": ("t.csv", buf.getvalue(), "text/csv")})


def numbers_in(obj) -> list[float]:
    """Every float anywhere in the response, however deeply nested."""
    if isinstance(obj, float):
        return [obj]
    if isinstance(obj, dict):
        return [n for v in obj.values() for n in numbers_in(v)]
    if isinstance(obj, list):
        return [n for v in obj for n in numbers_in(v)]
    return []


# -- The exact shape that returned 500 -----------------------------------------

def test_a_column_with_three_values_does_not_crash_the_endpoint():
    """Three points have no defined kurtosis. This is the reproduction of
    the live failure, and it fails without json_safe."""
    df = pd.DataFrame({"a": [1, 2, 3, 4, 3], "b": [2.5, 3.5, None, 5.5, None]})

    res = post(df)

    assert res.status_code == 200, res.text
    assert res.json()["stats"]["b"]["kurtosis"] is None


@pytest.mark.parametrize(
    "values,undefined",
    [
        ([1.0], {"std", "skew", "kurtosis"}),          # one point: no spread
        ([1.0, 2.0], {"skew", "kurtosis"}),            # two: no shape
        ([1.0, 2.0, 3.0], {"kurtosis"}),               # three: no tail weight
    ],
)
def test_each_statistic_that_needs_more_points_comes_back_as_null(values, undefined):
    """Not one guard on kurtosis: standard deviation and skew have the same
    property at their own thresholds, and a fix that only covered the
    statistic someone happened to hit would leave the other two."""
    df = pd.DataFrame({"x": values + [None] * 4, "y": list(range(len(values) + 4))})

    res = post(df)

    assert res.status_code == 200, res.text
    stats = res.json()["stats"]["x"]
    for name in undefined:
        assert stats[name] is None, f"{name} should be null for {len(values)} point(s)"


def test_a_constant_column_does_not_crash():
    """Zero variance. Skew and kurtosis are undefined rather than zero."""
    df = pd.DataFrame({"same": [7.0] * 6, "idx": list(range(6))})

    assert post(df).status_code == 200


def test_an_all_empty_numeric_column_does_not_crash():
    df = pd.DataFrame({"empty": [None] * 6, "idx": list(range(6))})

    assert post(df).status_code == 200


def test_a_single_row_does_not_crash():
    assert post(pd.DataFrame({"a": [1], "b": [2.0], "c": ["x"]})).status_code == 200


def test_a_single_column_does_not_crash():
    assert post(pd.DataFrame({"only": [1.0, 2.0, 3.0, 4.0]})).status_code == 200


def test_no_response_anywhere_contains_a_value_json_cannot_carry():
    """The general statement of the bug. Any non-finite float anywhere in
    the tree is a 500, not a wrong number, so the assertion sweeps the whole
    response rather than the field that happened to break."""
    df = pd.DataFrame({
        "tiny": [1.0, None, None, None, None],
        "const": [3.0] * 5,
        "cat": ["a", "b", "a", "c", "b"],
        "idx": [1, 2, 3, 4, 5],
    })

    res = post(df)

    assert res.status_code == 200, res.text
    bad = [n for n in numbers_in(res.json()) if math.isnan(n) or math.isinf(n)]
    assert bad == [], f"non-finite values reached the response: {bad}"


# -- The sanitiser itself ------------------------------------------------------

@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"),
                                   np.float64("nan"), np.float64("inf")])
def test_a_non_finite_number_becomes_null(value):
    assert json_safe(value) is None


@pytest.mark.parametrize("value", [0.0, -1.5, 1e300, 3])
def test_an_ordinary_number_is_left_alone(value):
    assert json_safe(value) == value


def test_numpy_types_become_plain_python():
    """Not cosmetic — the JSON encoder refuses a numpy integer outright."""
    out = json_safe({"i": np.int64(3), "f": np.float64(1.5)})

    assert out == {"i": 3, "f": 1.5}
    assert isinstance(out["i"], int) and isinstance(out["f"], float)


def test_it_reaches_all_the_way_down():
    """A guard applied only at the top level would miss the place the bug
    actually lived, three dicts deep under stats."""
    nested = {"a": [{"b": {"c": [float("nan"), 1.0]}}]}

    assert json_safe(nested) == {"a": [{"b": {"c": [None, 1.0]}}]}


def test_a_tuple_becomes_a_list():
    assert json_safe((1.0, float("nan"))) == [1.0, None]


def test_strings_and_none_pass_through():
    assert json_safe({"s": "text", "n": None, "b": True}) == {"s": "text", "n": None, "b": True}


# -- Config validation on /eda/clean -------------------------------------------

def clean(config: str):
    # Rows 1 and 3 are identical, so dedup has exactly one row to remove.
    # An earlier version repeated a value in one column and expected that to
    # count, which it correctly does not.
    df = pd.DataFrame({"a": [1, 2, 1], "b": [1.0, None, 1.0]})
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return client.post("/eda/clean",
                       files={"file": ("t.csv", buf.getvalue(), "text/csv")},
                       data={"config": config})


def test_a_valid_config_cleans_the_file():
    res = clean('{"dedup": true, "imputation": {"numeric_method": "median"}}')

    assert res.status_code == 200, res.text
    assert res.json()["summary"]["rows_removed"] == 1


@pytest.mark.parametrize(
    "config,key",
    [
        ('{"outliers": "iqr"}', "outliers"),
        ('{"imputation": "median"}', "imputation"),
    ],
)
def test_a_config_key_of_the_wrong_type_is_a_400_not_a_500(config, key):
    """This one cost real debugging time. Passing a string where an object
    was expected reached `.get("enabled")` on a str and raised. FastAPI turns
    an unhandled exception into a 500 produced OUTSIDE the CORS middleware,
    so the browser reported a CORS failure and the actual cause never left
    the server. A 400 naming the key is the difference between a minute and
    an hour."""
    res = clean(config)

    assert res.status_code == 400, res.text
    assert key in res.json()["detail"]


def test_a_config_that_is_not_an_object_is_rejected():
    assert clean('"just a string"').status_code == 400


def test_drop_cols_must_be_a_list():
    res = clean('{"drop_cols": "a"}')

    assert res.status_code == 400
    assert "drop_cols" in res.json()["detail"]


def test_invalid_json_is_still_a_400():
    assert clean("{not json").status_code == 400
