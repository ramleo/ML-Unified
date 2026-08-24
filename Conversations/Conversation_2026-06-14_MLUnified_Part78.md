# Conversation — 2026-06-14 — ML-Unified — FE in Preprocessing + Bug Fixes Part 78

---

## Session Summary

Fixed 4 FE/preprocessing UI bugs, broke and re-fixed auto-detected drop columns, moved Feature Engineering from training time into the preprocessing step (Option A), fixed a ruff F821 lint error, and diagnosed SHAP/What-If column mismatch (session ended before fix).

---

## Fixes & Features This Session

### Fix 1 — Four FE/Preprocessing Issues (commit `db610e0`)

1. **Polynomial chips → scrollable checklist**: replaced flex-wrap chip buttons with a fixed-height (140px) scrollable checkbox list — no overflow regardless of column count.

2. **FE column count**: added info banner in FE step: "FE-derived columns are added at training time, not during preprocessing." If FE configured, preprocessing COMPLETE card shows "Feature engineering is active — additional columns will be added at training time."

3. **Missing values checkbox `onchange`**: added `onchange="_onMissingMethodChange()"` to the Handle Missing checkbox so toggling it shows/hides Numeric/Categorical sub-dropdowns immediately.

4. **OHE shows 0 new columns**: when `hasCat = false`, added "ℹ No text/categorical columns detected — encoding will have no effect." note next to encoding dropdown.

---

### Fix 2 — Auto-detected Drop Columns Disappeared After Revert (commit `1a7bd7f`)

**Root cause:** After preprocessing, `automlAnalysis = result` (preprocessed). On Revert, `_renderAutoMLStep1b` used updated `automlAnalysis` (PassengerId already dropped → `likelyIdCols` empty → no auto-detected columns shown).

**Fix:**
- Added `_automlOrigFile = null` global
- `_amlRevertPreprocessing()` restores BOTH `automlAnalysis` and `automlFile` to originals
- `likelyIdCols`, `highCardCols`, `catCols`, `numCols`, `manualCols`, header counts all use `aOrig` (`_automlOrigAnalysis || a`)

---

### Feature 3 — FE Moved into Preprocessing Step (Option A) (commits `de70bfd`, `7542fc9`)

**Problem:** FE was applied at training time (AFTER feature selection). Polynomial interactions were never subject to feature selection — could explode uncontrolled.

**Correct order:**
```
/automl/preprocess:
  missing → encoding → FE (log/sqrt/rank/poly…) → feature selection → CSV

/automl/train:
  if fe_b64 → deserialise pre-fit transformer (no re-apply, CSV already FE'd)
  else      → apply FE in training (legacy / skip-preprocessing path)
```

**Backend changes (`app.py`):**
- `/automl/preprocess`: accepts `fe_config`, runs `FeatureEngineeringTransformer.fit_transform()` on `df_feat` before feature selection, serialises transformer as `fe_b64_out` (base64 joblib), returns `fe_b64`, `pre_fe_cols`, `fe_cols_added`
- `/train`: new Form fields `fe_b64: str = Form("")` and `pre_fe_cols_json: str = Form("[]")`; if `fe_b64` present → deserialise transformer, skip re-applying FE; else → legacy path

**Frontend changes:**
- `_applyAutoMLPreprocessing()`: adds `fe_config: _automlFeatureEng` to JSON body
- Saves `automlFEB64` and `automlPreFeCols` from result
- `_amlRevertPreprocessing()`: clears `automlFEB64` and `automlPreFeCols`
- `runAutoML()`: appends `fe_b64` and `pre_fe_cols_json` to FormData
- COLUMNS stat card sub-text shows `+N FE` if `fe_cols_added > 0`

**Ruff fix (commit `7542fc9`):** `base64` was only imported inside `automl_preprocess`; used without import in `/train` handler. Fixed with local `import base64 as _b64_train  # noqa: PLC0415`. **Ruff binary:** `.venv/bin/ruff` — must be used before every `app.py` commit.

---

### Diagnosed (not yet fixed) — SHAP/What-If Column Mismatch

**Error:** "SHAP computation failed: columns are missing: {'Fare_rank', 'Age_rank', 'Age SibSp', 'Age Fare', 'Fare_bin', 'Fare SibSp'}"

**Root cause (identified):** SHAP router (`routers/shap.py`) calls `_prep_df(data, schema)` which builds a DataFrame from schema fields only (pre-FE columns). Then calls `preprocessor.transform(_df)` directly on this raw data — bypassing the FE transformer entirely. The ColumnTransformer was trained on FE-derived columns but receives data without them → column mismatch.

Same issue for What-If "Sweep failed" — `/predict` has the FE path but something is breaking it.

**Fix needed:** SHAP router must apply `fe.transform()` before calling `preprocessor.transform()`, mirroring what `/predict` does. Session ended before fix was implemented.

---

## Key Technical Notes

- `_automlOrigAnalysis` and `_automlOrigFile` are saved ONCE (first preprocessing run). `_amlRevertPreprocessing()` restores both before re-rendering.
- FE transformer serialised via joblib → base64 → passed through frontend as a string → deserialised in `/train`. This ensures predict uses EXACT same fit parameters as preprocessing.
- `remainder='drop'` in ColumnTransformer means unrecognised columns are silently dropped at predict time — this is how feature selection is "enforced" at prediction.
- Ruff binary path: `/Users/wrks/Downloads/Claude-documentation/Projects/ML-Unified/.venv/bin/ruff`

---

## All Commits This Session

| Hash | Description | GitHub | HF |
|------|-------------|--------|----|
| `db610e0` | fix(fe): poly checklist, missing onchange, orig analysis, OHE no-cat note | ✓ | ✓ |
| `1a7bd7f` | fix(preprocessing): revert restores original file+analysis; auto-detected drop cols use aOrig | ✓ | ✓ |
| `de70bfd` | feat(fe): move FE into preprocessing so feature selection sees FE-derived columns | ✓ | ✓ |
| `7542fc9` | fix(train): import base64 locally in /train handler — resolves ruff F821 | ✓ | ✓ |

---

## Pending Items

| Phase | Item | Status |
|-------|------|--------|
| — | Fix SHAP/What-If column mismatch (FE columns not applied in shap.py) | **Next** |
| 6 | SHAP values (full phase) | Not started |
| 7 | Regression confidence intervals | Not started |
| 8 | Optuna hyperparameter tuning | Not started |
| 9 | Ensemble / stacking | Not started |
| 10 | Pipeline export | Not started |
| 11 | Encoding per-column | Not started |
| 12 | GPU toggle | Not started |
| 13 | SMOTE | Not started |
