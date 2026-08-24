# Conversation — 2026-06-11 — ML-Unified — E2E Tests — Part 61

---

## Session Summary

Single fix: `--headed` mode was broken because `browser_session` fixture hardcoded `headless=True`. Fixed to read pytest-playwright's CLI options. All tests now pass in headed mode (browser window visible).

---

## Fix: Headed Mode Not Working

**Problem:** Running `pytest --headed` never opened a browser window — tests ran silently in headless mode regardless of the flag.

**Root Cause:** `conftest.py` line 80 had `pw.chromium.launch(headless=True)` hardcoded, which completely overrides pytest-playwright's `--headed` CLI argument.

**Fix applied to `tests/e2e/conftest.py`:**

```python
# Before
@pytest.fixture(scope="session")
def browser_session(ml_api_server):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)  # ← hardcoded, ignores --headed
        yield browser
        browser.close()

# After
@pytest.fixture(scope="session")
def browser_session(ml_api_server, pytestconfig):
    headed = pytestconfig.getoption("--headed", default=False)
    slow_mo = pytestconfig.getoption("--slowmo", default=0)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed, slow_mo=float(slow_mo))
        yield browser
        browser.close()
```

Also wired up `--slowmo` so users can slow down interactions for visual debugging.

---

## Test Results (after fix)

```
.venv/bin/python3 -m pytest tests/e2e/ -v --headed --slowmo 800 -x

13 passed, 4 skipped in 67.66s
```

| Test | Result |
|------|--------|
| `test_clean.*` (4 tests) | SKIPPED (ML_EDA_URL not set) |
| `test_drift_tab_opens` | PASSED |
| `test_drift_upload_renders_metrics` | PASSED |
| `test_drift_upload_shows_column_metrics` | PASSED |
| `test_home_page_title` | PASSED |
| `test_sidebar_has_supervised_models` | PASSED |
| `test_sidebar_has_unsupervised_tools` | PASSED |
| `test_sidebar_has_data_tools` | PASSED |
| `test_empty_state_shown_on_load` | PASSED |
| `test_iris_predict_returns_result` | PASSED |
| `test_iris_predict_shows_species` | PASSED |
| `test_iris_predict_shows_shap` | PASSED |
| `test_titanic_predict_returns_result` | PASSED |
| `test_diabetes_predict_returns_result` | PASSED |

---

## How to Run

```bash
# Headless (CI-style)
.venv/bin/python3 -m pytest tests/e2e/ -v

# Headed (see browser)
.venv/bin/python3 -m pytest tests/e2e/ -v --headed

# Headed + slow (visual debugging)
.venv/bin/python3 -m pytest tests/e2e/ -v --headed --slowmo 800

# Single test
.venv/bin/python3 -m pytest tests/e2e/test_inference.py::test_iris_predict_shows_shap -v --headed
```

---

## E2E Test Suite Overview (current state)

| File | Tests | Notes |
|------|-------|-------|
| `tests/e2e/conftest.py` | — | Server lifecycle, browser, CSV fixtures |
| `tests/e2e/test_home.py` | 5 | Page load, sidebar buttons |
| `tests/e2e/test_inference.py` | 5 | Iris/Titanic/Diabetes predict + SHAP |
| `tests/e2e/test_drift.py` | 3 | Drift upload flow |
| `tests/e2e/test_clean.py` | 4 | Skipped unless ML_EDA_URL set |

**Key design decisions:**
- `ml_api_server` fixture: starts uvicorn on port 8765, waits for `/health` to report ≥4 models
- `browser_session`: session-scoped, one browser for all tests
- `page`: function-scoped, fresh context per test, navigated to app root
- `_select_model` uses `page.wait_for_function(f"activeModel?.id === '{model_id}'")`  — NOT `wait_for_selector("#predictBtn")` — because page auto-selects diabetes on load, so `#predictBtn` already exists before the target model loads

---

## Commit Log (this session)

| Hash | Description |
|------|-------------|
| `437a12f` | fix(clean): left-anchor outlier/missing bars with normalization |

*(E2E tests not yet committed — waiting for user confirmation)*

---

## Pending

| # | Item | Status |
|---|------|--------|
| **#20** | E2E tests — commit | Ready, awaiting commit approval |
| **#22** | Dockerize full app | Not started |
| **#21** | Batch predict | Deferred |
| **#5** | Proxy page | Deferred |
