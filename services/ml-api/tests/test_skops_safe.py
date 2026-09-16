"""E18 regression: an uploaded model file cannot run code on the Space.

`/shap/custom/upload` used to `joblib.load` whatever was uploaded. joblib is
pickle, which runs embedded code the instant it loads, so one crafted file was
remote code execution — every env key and the HF write token. `load_model`
now accepts only skops files whose every type sits under an ML-library
allowlist, so a plain pickle, an evil pickle, or a skops file naming an
unlisted type are all refused before any object is built.

Proven here four ways: a genuine model round-trips and predicts identically;
a joblib/pickle `.pkl` is refused; an evil pickle is refused *and* a marker
file proves its payload never ran; a skops file naming a non-allowlisted type
is refused by the type check, not merely by the format check.
"""
from __future__ import annotations

import os
import pickle

import pytest

sklearn = pytest.importorskip("sklearn", reason="sklearn is in ml-api's requirements")
sio = pytest.importorskip("skops.io", reason="skops==0.14.0 is in ml-api's requirements")

import numpy as np
from routers.core.skops_safe import UnsafeModelFile, load_model
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


class _CustomTransformer(BaseEstimator, TransformerMixin):
    """A user-defined estimator — a legitimate sklearn API, but its type is not
    under the sklearn/numpy/scipy/xgboost/lightgbm allowlist, so skops lists it
    as untrusted and load_model must refuse it."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return X


def _genuine_pipeline() -> Pipeline:
    X = np.array([[0.0, 1.0], [1.0, 0.0], [2.0, 1.0], [3.0, 0.0]])
    y = np.array([0, 1, 0, 1])
    pipe = Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression())])
    pipe.fit(X, y)
    return pipe


def test_a_genuine_skops_model_loads_and_predicts_identically():
    original = _genuine_pipeline()
    X = np.array([[1.5, 0.5], [2.5, 0.5]])

    loaded = load_model(sio.dumps(original))

    assert np.array_equal(loaded.predict(X), original.predict(X))


def test_a_joblib_or_pickle_file_is_refused():
    """The old accepted format. A plain pickle is not a skops file, so it is
    refused at the format check before anything is unpickled."""
    raw = pickle.dumps(_genuine_pipeline())

    with pytest.raises(UnsafeModelFile):
        load_model(raw)


def test_an_evil_pickle_is_refused_and_its_payload_never_runs(tmp_path):
    marker = tmp_path / "pwned"

    class _Evil:
        def __reduce__(self):
            # Harmless (touch), but if load_model ever unpickled this it would run.
            return (os.system, (f"touch {marker}",))

    raw = pickle.dumps(_Evil())

    with pytest.raises(UnsafeModelFile):
        load_model(raw)

    assert not marker.exists(), "the evil pickle's payload executed — load_model ran code"


def test_a_skops_file_naming_an_unlisted_type_is_refused():
    """Distinct from the format check: this IS a valid skops file, refused only
    because it names a type outside the ML-library allowlist."""
    dangerous = Pipeline([("custom", _CustomTransformer()), ("clf", LogisticRegression())])

    with pytest.raises(UnsafeModelFile) as exc:
        load_model(sio.dumps(dangerous))

    # The message should point at the offending type, not just say "bad file".
    assert "not allowed" in str(exc.value).lower()


def test_garbage_bytes_are_refused_without_crashing():
    with pytest.raises(UnsafeModelFile):
        load_model(b"this is not a model file at all")
