# Conversation — 2026-06-13 — ML-Unified — AutoML Improvements Part 73

---

## Session Summary

Multiple AutoML improvements: separate missing value imputation for numeric/categorical, improved task type detection, high-cardinality column fixes, preprocessing UI improvements, and AI explanation dashboard redesign.

---

## Features & Fixes This Session

### Fix 1 — High-Cardinality Numeric Column Fix (from Part 71 backlog)

**Problem:** Age, Fare (numeric) incorrectly appeared in the "drop high-cardinality" list.

**Fix:** Added `!c.is_numeric` to the filter in `_renderAutoMLStep1b()`:
```javascript
const highCardCols = a.columns.filter(c =>
  c.name !== effectiveTarget && !c.is_numeric && (c.nunique || 0) > 20
);
```
**Commit:** `cbd34d1`

---

### Feature 2 — Separate Missing Value Imputation for Numeric vs Categorical

**Problem:** Single dropdown applied one strategy to all columns. User wanted independent control over numeric vs categorical imputation.

**Frontend:** Replaced single `amlPrepMissingMethod` select with two selects:
- `amlPrepMissingNum`: Median · Mean · Mode · KNN · MICE · Forward fill · Backward fill · Constant (0) · Drop rows
- `amlPrepMissingCat`: Most frequent · Constant ("Unknown") · Forward fill · Backward fill · Drop rows

**Backend:** Refactored imputation block to use `mv_num` and `mv_cat` options. Nested functions `_impute_num()` and `_impute_cat()` apply strategies independently. Full backward compatibility with old `missing_values` field.

**Commit:** `b90d54b`

---

### Feature 3 — Improved Task Type Detection

**Problem:** `nunique <= 10` threshold too low; no hint shown to user.

**Fix:** Smarter `_amlSuggestTask()` using `col.dtype`:
- Text column → always Classification
- Integer column, nunique ≤ 20 → Classification; > 20 → Regression
- Float column, nunique ≤ 2 → Classification (binary 0.0/1.0); otherwise → Regression

**Added:** `id="amlTaskHint"` div below radio buttons showing e.g. "Auto-detected: Integer column · 2 unique values → Classification"

**Commit:** `b90d54b`

---

### Fix 4 — Numeric ID Columns in Drop List (PassengerId regression fix)

**Problem:** The `!c.is_numeric` fix excluded ALL numeric columns from the drop list, including PassengerId (a numeric ID column that should be dropped).

**Fix:** Added a second category `likelyIdCols` — numeric columns where `nunique / rows >= 0.9`:
```javascript
const likelyIdCols = a.columns.filter(c =>
  c.name !== effectiveTarget && c.is_numeric && (c.nunique || 0) / (a.rows || 1) >= 0.9
);
```
Shown with label "numeric ID · 891 unique" vs text columns "text · 500 unique". Both pre-checked in the drop section.

**Commit:** `002ce42` / `ed59f71`

---

### Fix 5 — Column Count Breakdown After Preprocessing

**Problem:** "Columns: 12 → 11" was confusing after OHE — user expected more columns but didn't understand the net effect of drops + OHE expansion.

**Backend:** Added to preprocess response:
- `user_cols_dropped`: count of columns dropped by user selection
- `ohe_cols_added`: net columns added by OHE (`len(after) - len(before)`)

**Frontend:** Shows inline note: `Columns: 12 → 11 (−4 dropped, +5 OHE)`

**Commit:** `002ce42`

---

### Fix 6 — Configure Stepper Turns Green on Preprocessing Complete

**Problem:** When preprocessing completes, the Configure step (step 2) stayed purple (active) instead of turning green.

**Fix:** After showing "Preprocessing complete" card, update the stepper element:
```javascript
const stepsEl = document.querySelector('.wizard-steps');
if (stepsEl) stepsEl.outerHTML = _automlStepsHTML(3, false);
```
This marks Upload ✓ and Configure ✓ in green, leaving Results as next.

**Commit:** `002ce42`

---

### Fix 7 — AI Explanation Dashboard Only Shows After LLM Use

**Problem:** Full 2-column dashboard (Model CV Scores + Feature Importance) was always visible even without clicking "Get AI Explanation", confusing users.

**Fix:** Initial render shows only auto-generated rule-based text. Full dashboard (left: AI text panels, right: training results) only renders after LLM generates content.

```javascript
// Before: always showed full dashboard
<div id="amlExplanation">${_renderExplanationDashboard(...)}</div>

// After: plain text until AI is clicked
<div id="amlExplanation">${isAI
  ? _renderExplanationDashboard(...)
  : `<p class="aml-exp-text">${explanation?.why_won || explanation || ''}</p>`
}</div>
```

Right column also gets a "TRAINING RESULTS" label to clarify the section origin.

**Commit:** `ed59f71`

---

## All Commits This Session

| Hash | Description | Where |
|------|-------------|-------|
| `cbd34d1` | fix(automl): exclude numeric columns from high-cardinality drop list | GitHub |
| `b90d54b` | feat(automl): separate numeric/categorical imputation + improved task type detection | GitHub |
| `002ce42` | fix(automl): column breakdown, numeric ID detection, stepper green, training results label | GitHub |
| `ed59f71` | fix(automl): AI dashboard only on LLM use; column breakdown; numeric ID; stepper green | GitHub |
| `2917dee` | Same (latest) | HF Space |

---

## HF Space Discovery (From Part 72 — now in memory)

**CRITICAL:** HF Space uses `frontend/index.html` at repo root, NOT `services/ml-api/frontend/index.html`.

Always upload with:
```python
upload_file(
    path_or_fileobj='<local path to services/ml-api/frontend/index.html>',
    path_in_repo='frontend/index.html',   # ← HF root path
    repo_id='wram1708/ml-unified',
    repo_type='space',
    token='<REDACTED_HF_TOKEN>',
)
```

---

## Pending Items (Agreed Order)

| Phase | Item | Status |
|-------|------|--------|
| 2 | Task type detection improvement | ✅ Done (this session) |
| 3 | Validation set split visibility | Not started |
| 4 | Resource estimation (RAM/time warning) | Not started |
| 5 | Feature Engineering step | Not started |
| 6 | SHAP values | Not started |
| 7 | Regression confidence intervals | Not started |
| 8 | Optuna hyperparameter tuning | Not started |
| 9 | Ensemble / stacking | Not started |
| 10 | Pipeline export | Not started |
| 11 | Encoding per-column | Not started |
| 12 | GPU toggle | Not started |
| 13 | SMOTE | Not started |

---

## Key Technical Notes

- `col.dtype` from backend (e.g. `int64`, `float64`, `object`) is used in frontend for integer vs float task detection
- `a.rows` from `/analyze` response is used to compute ID column ratio (`nunique / rows >= 0.9`)
- `nonlocal df_feat, target_series` needed inside nested `_impute_num`/`_impute_cat` functions to allow row drops
- OHE col count tracking: save `len(df_feat.columns)` before `pd.get_dummies`, compare after
- Stepper updates dynamically via `stepsEl.outerHTML = _automlStepsHTML(3, false)` after preprocessing
