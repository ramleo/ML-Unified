import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app import _load

@pytest.fixture(scope="session", autouse=True)
def _preload_models():
    """Populate MODELS before any test runs.

    _load() is now called inside the FastAPI lifespan (so Render's port scanner
    sees an open port before the slow joblib.load calls finish).  Tests use a
    bare TestClient without entering the lifespan context, so we call _load()
    explicitly here instead.
    """
    _load()
