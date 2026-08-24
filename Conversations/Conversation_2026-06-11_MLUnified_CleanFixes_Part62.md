# Conversation — 2026-06-11 — ML-Unified — Clean & Export Fixes — Part 62

---

## Session Summary

Three bugs fixed in the Clean & Export panel. Commit `0bf7a89`.

---

## Bug 1 — 404 Not Found on Clean & Download CSV

**Symptom:** Clicking "Clean & Download CSV" shows a "Not Found" error. Network tab shows POST to `https://ml-eda-tkn4.onrender.com/eda/clean` returning HTTP 404.

**Root Cause:** The `/eda/clean` endpoint exists in the code (`@router.post("/eda/clean")` in `services/ml-eda/routers/eda.py`), but ml-eda was never added to the CI pipeline or `render.yaml`. Every push to `main` auto-deploys ml-api and ml-vision, but ml-eda was never triggered — so the Render deployment was running stale code that predated the `/eda/clean` route.

**Fix:** Added ml-eda to `.github/workflows/ci.yml`:
- `pip install -r services/ml-eda/requirements.txt`
- `ruff check services/ml-eda/app.py` (lint)
- `pytest services/ml-eda/tests/` (35 tests)
- Deploy step using `RENDER_EDA_DEPLOY_HOOK_URL` secret (optional, skips if not set — same pattern as ml-vision)

**Action required:** Add `RENDER_EDA_DEPLOY_HOOK_URL` to GitHub Secrets (Render dashboard → ml-eda service → Settings → Deploy Hook). Once set, every push will redeploy ml-eda automatically.

---

## Bug 2 — Single Imputation Dropdown Applied to All Column Types

**Symptom:** One dropdown for imputation method. Selecting "Median" would attempt to apply it to categorical columns (like Cabin, Embarked), where median is meaningless. Selecting "Mode" would apply to numeric columns where mean/median is more appropriate.

**Root Cause:** Original design had one `sc-impute` dropdown covering all column types with a single `method` key sent to the backend.

**Fix — Frontend (`services/ml-api/frontend/index.html`):**

The imputation section now detects which missing columns are numeric vs categorical (using `c.is_numeric` from the EDA analysis response) and renders separate dropdowns only when that type has missing values:

- **Numeric columns** dropdown (`sc-impute-num`): None / Median (default) / Mean / KNN (k=5) / MICE / Interpolate / Forward fill / Backward fill / Constant
- **Categorical columns** dropdown (`sc-impute-cat`): None / Mode (default) / Constant / Forward fill / Backward fill
- KNN opts, numeric constant input, slow-warn tied to numeric dropdown
- Categorical constant input tied to categorical dropdown

Config sent to backend:
```json
{
  "imputation": {
    "numeric_method": "median",
    "cat_method": "mode",
    "cols": [...],
    "knn_k": 5,
    "constant_value": "0",
    "cat_constant_value": "Unknown"
  }
}
```

**Fix — Backend (`services/ml-eda/routers/eda.py`):**

Imputation block now handles `numeric_method` and `cat_method` as separate operations:
- `numeric_method`: mean, median, knn, mice, interpolate, ffill, bfill, constant, miceforest, fancyimpute — all applied only to numeric columns
- `cat_method`: mode, constant, ffill, bfill — applied only to categorical columns
- Legacy `method` key still works as fallback (backward compatible)

---

## Bug 3 — "Processing…" Text Instead of Progress Bar

**Symptom:** Clicking "Clean & Download CSV" shows a small spinner and "Processing…" text. No visual indication of how far along the operation is.

**Fix — Frontend (`services/ml-api/frontend/index.html`):**

Replaced `sc-spinner` with `sc-progress` — an animated progress bar matching the style of the upload progress bar:

- Appears below the button when submit is clicked
- Animates through stages at 600ms intervals:
  - 5% → Uploading…
  - 15% → Uploading…
  - 35% → Cleaning…
  - 55% → Imputing…
  - 72% → Removing outliers…
  - 85% → Finalising…
  - 95% → Preparing download… (when response arrives)
  - 100% → Done
- Hides and resets after 800ms once complete or on error
- Error message still shown below the button on failure

---

## Commit Log

| Hash | Description | Pushed |
|------|-------------|--------|
| `0bf7a89` | fix(clean): split imputation by type, progress bar on submit, add ml-eda to CI | Yes — `429544b..0bf7a89` |
| `429544b` | test(e2e): add Playwright E2E suite — 13 tests across inference, drift, home, clean | Yes |
| `437a12f` | fix(clean): left-anchor outlier/missing bars with normalization | Yes |

---

## Files Changed in `0bf7a89`

| File | Change |
|------|--------|
| `services/ml-eda/routers/eda.py` | Split imputation into `numeric_method` + `cat_method` with backward compat |
| `services/ml-api/frontend/index.html` | Dual imputation dropdowns + progress bar |
| `.github/workflows/ci.yml` | Add ml-eda lint, test, deploy steps |

---

## What Happens After Push (`0bf7a89`)

CI pipeline now runs three services on every push to `main`:

```
push to main
  ├─ ruff lint        ml-api, ml-vision, ml-eda   ← ml-eda newly added
  ├─ pytest           ml-api (30), ml-vision (22), ml-eda (35)
  └─ deploy
       ├─ ml-api      (RENDER_DEPLOY_HOOK_URL)
       ├─ ml-vision   (RENDER_VISION_DEPLOY_HOOK_URL — skips if not set)
       └─ ml-eda      (RENDER_EDA_DEPLOY_HOOK_URL  — skips if not set)
```

ml-eda tests: **35 passed** locally before push.

---

## Pending

| # | Item | Status |
|---|------|--------|
| **Action** | Add `RENDER_EDA_DEPLOY_HOOK_URL` to GitHub Secrets | Required to fix the 404 on live site — Render dashboard → ml-eda → Settings → Deploy Hook |
| **#22** | Dockerize full app | Not started |
| **#21** | Batch predict | Deferred |
| **#5** | Proxy page | Deferred |
