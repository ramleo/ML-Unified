# Conversation — 2026-06-11 — ML-Unified — Part 60

---

## Session Summary

Continuing E2E test fixes. Still 5-6 tests failing. Root causes identified.

---

## Current Test Status

```
8 passed, 4 skipped (ML_EDA_URL), 5 failing
```

### Failing tests and root causes

#### 1. All inference tests (`test_iris_*`, `test_titanic_*`, `test_diabetes_*`)
- **Symptom**: `#resultState` stays hidden after 15s
- **Root cause**: `page.evaluate(fn, dict)` sets form values via JS, but values are read as empty when `runPredict()` fires. `page.fill()` bypasses this issue — it was working for iris/titanic in earlier runs.
- **Theory**: `page.evaluate`-set values may be sanitized by browser's async number input validation (step constraints), clearing them before predict reads them
- **Fix**: Revert ALL tests to `page.fill()` + `page.select_option()` (Playwright-native fill methods)
- **For diabetes**: original failure was using `"1"` for BMI (below min 18.2). With correct sample values, `page.fill` should work for all fields

#### 2. `test_drift_upload_shows_column_metrics`
- **Symptom**: Drift result shows diabetes field labels ("Pregnancies", "Glucose") instead of iris field labels
- **Root cause**: `/drift/iris/upload` endpoint is returning data that contains diabetes field labels. This is because the DRIFT HISTORY stored in `drift_buffer.json` was created by diabetes model tests. The drift response includes historical field stats with labels.
- **Investigation needed**: Check what `/drift/iris/upload` actually returns when iris CSV is uploaded

#### 3. `test_iris_predict_shows_shap`  
- **Symptom**: `#shapBody .shap-bar-fill` never appears / SHAP SSE times out
- **Root cause**: Wait condition `includes('unavailable')` but the actual text might differ. Need to verify what text appears when SHAP fails.

---

## What Was Working (Run 2, headless, no slowmo)

```
test_drift_tab_opens PASSED
test_drift_upload_renders_metrics PASSED
test_home.* PASSED (4/4)
test_iris_predict_returns_result PASSED
test_iris_predict_shows_species PASSED
test_titanic_predict_returns_result PASSED
```

Using `page.fill()` for iris + titanic fields. The 4 clean tests skipped.

---

## Fix Plan

1. **Revert _fill_form to page.fill()** — use Playwright native methods, not JS evaluate
2. **Diabetes**: fill all 8 fields with schema sample values via `page.fill()`:
   - `Pregnancies: 6`, `Glucose: 148`, `BloodPressure: 72`, `SkinThickness: 35`
   - `Insulin: 0`, `BMI: 33.6`, `DiabetesPedigreeFunction: 0.627`, `Age: 50`
3. **Drift**: investigate actual API response for `/drift/iris/upload` to find correct assertion
4. **SHAP**: fix wait condition to match actual error text

---

## Commits This Session

| Hash | Description |
|------|-------------|
| `437a12f` | fix(clean): left-anchor outlier/missing bars with normalization |

*(E2E tests not yet committed — in progress)*

---

## Pending

| # | Item | Status |
|---|------|--------|
| **#20** | E2E tests | 8/17 passing — fixing remaining 5 |
| **#22** | Dockerize | Not started |
