"""Every dependency with a compiled extension must import under this numpy.

A C extension built against the numpy 1 ABI does not fail to install under
numpy 2 — it installs happily and then raises on import:

    ValueError: numpy.dtype size changed, may indicate binary incompatibility.
    Expected 96 from C header, got 88 from PyObject

That is what took the Space down when its requirements were brought up to
numpy 2.4.6. spacy 3.7.x caps thinc below 8.3, every thinc 8.2.x pins
numpy<2, and thinc's numpy_ops extension is built against the old ABI. Pip
resolved it without complaint and the Docker build died on the first import.

CI stayed green through all of it, because nothing in the suite imported
spacy. That is the gap this file closes: an import is the only thing that
exercises a binary interface, so the packages that have one get imported
here. It is a deliberately boring test — the assertion is that the import
statement completes.
"""
import importlib

import numpy as np
import pytest

# Only packages that ship compiled extensions linked against numpy's C API.
# A pure-Python dependency cannot fail this way and does not belong here.
NATIVE = [
    "spacy",        # via thinc.backends.numpy_ops — the one that actually broke
    "thinc",
    "cv2",          # opencv-python-headless, now on 5.x
    "scipy",
    "sklearn",
    "pandas",
    "numba",        # via shap
    "catboost",
    "xgboost",
    "lightgbm",
    "onnxruntime",
]


@pytest.mark.parametrize("name", NATIVE)
def test_it_imports(name):
    """Import, and let the ABI error surface as a failure rather than a 503."""
    try:
        importlib.import_module(name)
    except ImportError as exc:
        # Not installed in this job is a different fact from broken, and this
        # suite runs in more than one environment.
        pytest.skip(f"{name} is not installed here: {exc}")


def test_numpy_is_the_major_version_the_pins_declare():
    """A guard on the guard.

    Every import above passes trivially under numpy 1, which is exactly the
    situation this file exists to stop being invisible. If the pins ever slip
    back, this says so instead of the suite quietly proving nothing.
    """
    assert np.__version__.startswith("2."), (
        f"requirements pin numpy 2.x but this environment has {np.__version__}; "
        "the import checks above are not testing what they claim to"
    )
