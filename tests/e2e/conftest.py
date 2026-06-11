"""
Shared fixtures for Playwright E2E tests.

Starts ml-api on localhost:8765 once per session, waits until models are
loaded (health endpoint reports >= 4 models), then tears down when done.
"""
import os
import subprocess
import sys
import textwrap
import time

import pytest
import requests
from playwright.sync_api import Page, sync_playwright

# ── Paths ────────────────────────────────────────────────────────────────────
REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
ML_API_DIR = os.path.join(REPO_ROOT, "services", "ml-api")
VENV_PYTHON = os.path.join(REPO_ROOT, ".venv", "bin", "python3")
PORT = 8765
BASE_URL = f"http://localhost:{PORT}"


# ── Server lifecycle ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def ml_api_server():
    """Start ml-api and wait until all 4 models are loaded."""
    python = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
    env = os.environ.copy()
    env["PORT"] = str(PORT)

    proc = subprocess.Popen(
        [python, "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", str(PORT)],
        cwd=ML_API_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for server to accept connections (models load in background)
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            requests.get(f"{BASE_URL}/health", timeout=2)
            break
        except Exception:
            time.sleep(0.5)
    else:
        proc.terminate()
        raise RuntimeError("ml-api did not start within 30 seconds")

    # Wait for models to finish loading (background thread)
    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            data = requests.get(f"{BASE_URL}/health", timeout=5).json()
            if len(data.get("models", [])) >= 4:
                break
        except Exception:
            pass
        time.sleep(2)
    else:
        proc.terminate()
        raise RuntimeError("Models did not load within 120 seconds")

    yield BASE_URL

    proc.terminate()
    proc.wait(timeout=10)


# ── Playwright page fixture ──────────────────────────────────────────────────

@pytest.fixture(scope="session")
def browser_session(ml_api_server, pytestconfig):
    """One Playwright browser for the whole session."""
    headed = pytestconfig.getoption("--headed", default=False)
    slow_mo = pytestconfig.getoption("--slowmo", default=0)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed, slow_mo=float(slow_mo))
        yield browser
        browser.close()


@pytest.fixture()
def page(browser_session, ml_api_server):
    """Fresh page per test, navigated to the app root."""
    context = browser_session.new_context()
    pg = context.new_page()
    pg.goto(ml_api_server, wait_until="networkidle")
    yield pg
    context.close()


# ── CSV fixtures ─────────────────────────────────────────────────────────────

IRIS_CSV = textwrap.dedent("""\
    Id,SepalLengthCm,SepalWidthCm,PetalLengthCm,PetalWidthCm
    1,5.1,3.5,1.4,0.2
    2,4.9,3.0,1.4,0.2
    3,6.4,3.2,4.5,1.5
    4,5.8,2.7,5.1,1.9
    5,6.3,3.3,6.0,2.5
""")

TITANIC_CSV = textwrap.dedent("""\
    PassengerId,Pclass,Name,Sex,Age,SibSp,Parch,Ticket,Fare,Cabin,Embarked
    1,3,Braund Mr. Owen Harris,male,22.0,1,0,A/5 21171,7.25,,S
    2,1,Cumings Mrs. John Bradley,female,38.0,1,0,PC 17599,71.2833,C85,C
    3,3,Heikkinen Miss. Laina,female,26.0,0,0,STON/O2. 3101282,7.925,,S
    4,2,Futrelle Mrs. Jacques Heath,female,35.0,1,0,113803,53.1,C123,S
    5,3,Allen Mr. William Henry,male,35.0,0,0,373450,8.05,,S
""")


@pytest.fixture()
def iris_csv(tmp_path):
    f = tmp_path / "iris.csv"
    f.write_text(IRIS_CSV)
    return str(f)


@pytest.fixture()
def titanic_csv(tmp_path):
    f = tmp_path / "titanic.csv"
    f.write_text(TITANIC_CSV)
    return str(f)
