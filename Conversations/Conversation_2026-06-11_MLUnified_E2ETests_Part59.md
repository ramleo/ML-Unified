# Conversation — 2026-06-11 — ML-Unified — Part 59

---

## Session Summary

Two features implemented this session:
1. Left-anchor bars for outlier/missing sections in Clean & Export (commit `437a12f`)
2. Playwright E2E test suite (#20) — 10/17 passing, 4 skipped (Clean needs ml-eda), 3 failing

---

## Left-Anchor Bars Fix — commit `437a12f`

**Problem:** Center-anchored bars (SHAP style) were used for outlier % and missing % which are purely positive metrics. This wasted 50% of the bar track as dead space on the left.

**Fix:**
- Added `leftAnchor = false` optional param to `colRow` helper
- When `leftAnchor=true`: removes `.shap-bar-center` divider, pins fill at `left:0%` instead of `left:50%`
- Outlier section: `colRow(..., true)` — left-anchor, already normalized
- Imputation/missing section: `colRow(..., c.missing_pct / maxMissingPct * 100, ..., true)` — left-anchor + normalization added
- Skew section: unchanged — center-anchor correct for bidirectional values

**User note:** Revertable via `git revert 437a12f`

---

## E2E Tests — #20

### Setup
- Playwright Python installed in `.venv` via `pip`
- Chromium browser installed via `.venv/bin/playwright install chromium`
- Test location: `tests/e2e/`
- Run command: `.venv/bin/python3 -m pytest tests/e2e/ -v`

### Files created

| File | Purpose |
|------|---------|
| `tests/e2e/conftest.py` | Session-scoped server fixture, sample CSV fixtures |
| `tests/e2e/test_home.py` | Page load, sidebar model buttons |
| `tests/e2e/test_inference.py` | Single-row predict for iris/titanic/diabetes + SHAP |
| `tests/e2e/test_drift.py` | Drift upload flow for iris |
| `tests/e2e/test_clean.py` | Clean & Export (skipped when ML_EDA_URL not set) |
| `pytest.ini` | Root config pointing testpaths to tests/e2e/ |
| `requirements-dev.txt` | Added playwright>=1.44, pytest-playwright>=0.5 |

### conftest.py key details
- `ml_api_server` fixture (session-scoped): starts uvicorn on port 8765
- Waits for `/health` to return `models` list with >= 4 entries (models load in background thread)
- `page` fixture (function-scoped): fresh browser context per test, navigated to root
- `iris_csv` + `titanic_csv` fixtures: minimal sample CSVs in tmp_path
- VENV_PYTHON used to start server: `.venv/bin/python3`

### Current test results

```
10 passed, 4 skipped, 3 failed (in ~65s)
```

#### Passing (10)
- `test_clean.*` — 4 SKIPPED (ML_EDA_URL not configured)
- `test_drift_tab_opens`
- `test_drift_upload_renders_metrics`
- `test_home.*` — 4 passed (page title, supervised models, unsupervised tools, data tools, empty state)
- `test_iris_predict_returns_result`
- `test_iris_predict_shows_species`
- `test_titanic_predict_returns_result`

#### Failing (3) — under investigation

**1. `test_drift_upload_shows_column_metrics`**
- Drift body renders but shows diabetes field names ("Pregnancies", "Glucose") not iris fields
- Root cause: drift "predictions" history loaded first, shows stored diabetes predictions
- Fix needed: assert against text that IS present (drift output content), or check Upload mode response

**2. `test_iris_predict_shows_shap`**
- `#shapBody .shap-bar-fill` never appears (30s timeout)
- SHAP panel shows `.visible` immediately (spinner), bars appear after SSE completes
- Root cause: Iris uses Logistic Regression — SHAP computation may fail server-side
- Fix needed: check if iris SHAP endpoint actually returns bars or "unavailable" message

**3. `test_diabetes_predict_returns_result`**
- `#resultState` stays hidden after 15s even in isolation
- Confirmed: errState has error text (but not captured yet)
- Root cause under investigation — predict might be failing for diabetes model
- Fix needed: capture errState text to diagnose, then fix root cause

---

## Debugging in Progress

At time of conversation save, was about to run a debug script to capture `#errState` text for the diabetes failure.

---

## Commit Log (this session)

| Hash | Description |
|------|-------------|
| `437a12f` | fix(clean): left-anchor outlier/missing bars with normalization |

---

## Pending Items

| # | Item | Notes |
|---|------|-------|
| **#20** | E2E tests | 10/17 passing — 3 failures to fix |
| **#22** | Dockerize full app | Not started |
| **#21** | Batch predict | Deferred |
| **#5**  | Proxy page | Deferred |
