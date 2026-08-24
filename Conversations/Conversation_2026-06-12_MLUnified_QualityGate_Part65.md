# Conversation — 2026-06-12 — ML-Unified — Model Quality Gate & Duplicate Rows Fix — Part 65

---

## Session Summary

Three features implemented: duplicate rows display in Clean & Export, model quality gate in CI, and CI restructure to non-blocking.

---

## Feature 1 — Display Duplicate Rows in Clean & Export

**Commit:** `1033417`

**What was built:**
- Backend (`services/ml-eda/routers/eda.py`): Added `duplicate_rows` field to `/eda` response — contains the extra copies of duplicate rows (up to 50), using `keep='first'` so only the rows that would be removed are included
- Frontend (`services/ml-api/frontend/index.html`): Collapsible "Show duplicate rows" link appears below the "X found" badge when duplicates exist. Clicking toggles a scrollable table showing the actual rows. Horizontally scrollable for wide datasets. Shows note if truncated (e.g. "showing first 50 of 120"). Null values render as italic grey `null`.

**Bug fixed in same session (`3ce3c17`):**
- Initial implementation used `keep=False` which marks ALL copies including originals — caused "6 found" badge but 11 rows in table
- Fixed to `keep='first'` so table shows exactly the rows that would be removed, matching the badge count exactly

---

## Feature 2 — Model Quality Gate in CI

**Commit:** `9eed714`

**What was built:**

### Script: `scripts/check_model_quality.py`
- Loads each pre-built pipeline from `services/ml-api/models/`
- Evaluates against holdout fixtures in `services/ml-api/tests/fixtures/`
- Reports PASS/FAIL per model
- Exits 1 if any model fails threshold

### Thresholds (observed score → threshold with ~7% slack):
| Model | Type | Observed | Threshold |
|-------|------|---------|-----------|
| iris | classification | 86.7% | ≥ 80% |
| diabetes | classification | 76.7% | ≥ 70% |
| titanic | classification | 76.7% | ≥ 70% |
| insurance | regression MAE | 0.0 | ≤ 100 |

### Holdout fixtures created:
| File | Source | Rows |
|------|--------|------|
| `iris_holdout.csv` | sklearn `load_iris()`, 10 per class | 30 |
| `diabetes_holdout.csv` | Pima Indian dataset (public benchmark), first 30 rows with true labels | 30 |
| `titanic_holdout.csv` | Titanic training set (public, Kaggle), rows 1–30 with true labels | 30 |
| `insurance_holdout.csv` | Representative inputs, baseline = current model predictions | 15 |

**Note on insurance:** Since the insurance dataset is custom (not public), the holdout uses current model predictions as baseline. This creates a regression test — catches if the model is replaced with a different one.

---

## Feature 3 — CI Restructure: Non-Blocking Quality Gate

**Commit:** `3ce3c17`

**Problem:** Quality gate was inside the `test` job, so a model failure would block ALL deploys (ml-eda, ml-vision, frontend changes).

**Fix:** Extracted quality gate into its own parallel job `model-quality` with `continue-on-error: true`.

**CI pipeline after restructure:**
```
push to main
  ├─ test (lint + pytest for all 3 services)    ← gates deploy
  ├─ model-quality (check_model_quality.py)     ← non-blocking, email on failure
  └─ deploy (needs: test only)
       ├─ ml-api
       ├─ ml-vision
       └─ ml-eda
```

**Notification behaviour:** GitHub sends an email when `model-quality` job fails. Deploy still runs. Quality gate failure is visible in GitHub Actions UI as a failed (yellow) check.

---

## Commit Log

| Hash | Description | Pushed |
|------|-------------|--------|
| `3ce3c17` | fix(ci+clean): non-blocking quality gate job + fix duplicate rows count mismatch | Yes |
| `9eed714` | feat(ci): model quality gate — score all 4 models against holdout fixtures before deploy | Yes |
| `1033417` | feat(clean): show duplicate rows in collapsible table in Clean & Export | Yes |

---

## Pending

| Priority | Item | Status |
|----------|------|--------|
| Next | **AutoML** — auto-try RF/XGBoost/LightGBM, pick best by CV | Not started |
| | **Model versioning + rollback** | Not started |
| | **Drift alerting** (email/Slack) | Not started |
| | **LLM-assisted feature suggestion** after EDA | Not started |
| | **Automated retraining pipeline** | Not started |
| | **Time series forecasting** | Not started |
| | **E2E tests in CI** | Not started |
| | **#21 Batch predictions** | Deferred |
| | **#5 Proxy page** | Deferred |
| Last | **#22 Dockerize** | Do last |
