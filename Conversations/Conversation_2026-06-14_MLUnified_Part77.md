# Conversation — 2026-06-14 — ML-Unified — Feature Engineering Redesign Part 77

---

## Session Summary

Full Feature Engineering redesign: replaced `_apply_feature_engineering` with proper sklearn `FeatureEngineeringTransformer`, redesigned FE UI with 4 sections, fixed What-If sweep, fixed wizard order, fixed back navigation, added per-column polynomial selection.

---

## Features & Fixes This Session

### Feature 1 — Full FE Design Discussion

Agreed design before implementation:

**Stateless transforms** (no fitting needed — formula is fixed):
- log1p, sqrt, date extraction, cyclical encoding, ratio/difference, missing indicators, text features

**Stateful transforms** (fit on train only):
- Binning (bin edges), Yeo-Johnson (lambda), outlier flags (IQR bounds), rank (training percentiles), polynomial (feature names), days_since_min (min date)

**Pipeline change:** `FeatureEngineeringTransformer` as sklearn step 0 — `fit()` learns params from X_train, `transform()` applies to any X.

**fe_config structure:**
```json
{
  "numeric": { "age": { "log1p": false, "sqrt": false, "yeo_johnson": false, "rank": false, "outlier_flag": false, "missing_flag": false, "bin": "none"/"quantile"/"equal_width"/"custom", "bin_n": 5, "bin_custom": "" } },
  "dates": { "col": { "year": true, "month": true, "day": false, "dow": false, "quarter": false, "is_weekend": false, "days_since_min": false, "cyclical": false, "keep_original": false } },
  "derived": [ { "op": "ratio"/"diff", "col_a": "...", "col_b": "..." } ],
  "poly_cols": ["Age", "Fare"]
}
```

---

### Feature 2 — FeatureEngineeringTransformer (Backend)

**Replaced** `_apply_feature_engineering()` with proper sklearn class at line ~1111.

**`fit(X_train)`** learns:
- Bin edges (quantile via `pd.qcut`, equal-width via `pd.cut`, or custom breakpoints)
- Yeo-Johnson `PowerTransformer` per column
- IQR bounds (Q1, Q3) for outlier flags
- Sorted training values for rank transform (`np.searchsorted`)
- Min date per column for `days_since_min`
- `PolynomialFeatures` on selected columns

**`transform(X)`** applies in order:
1. Missing indicators (`{col}_was_missing`) — before anything else
2. Numeric transforms (log1p, sqrt, Yeo-J, rank)
3. Binning (using fitted edges) → `{col}_bin`
4. Outlier flags (using fitted IQR) → `{col}_is_outlier`
5. Date extraction + cyclical sin/cos encoding
6. Derived features (ratio, difference)
7. Polynomial interactions (user-selected columns only)

**Applied** to full X before X/y split (MVP — slight leakage for stateful transforms, acceptable for teaching tool).

**Stored** with model: `MODELS[model_id]['fe'] = fe_transformer`; saved to `{model_id}_fe.pkl`.

**`/predict`** calls `fe.transform(df)` before `pipeline.predict(df)`.

**Commits:** `0902f96`, `0ed805a` (ruff lint fixes)

---

### Feature 3 — FE UI Redesign (Frontend)

`_renderAutoMLStep1c()` redesigned with 4 sections:

**Section 1 — Numeric Transforms:**
- Per-column chip toggles: log1p, sqrt, Yeo-J, rank, outlier ⚑, missing ⚑
- Binning method buttons per column: None / Quantile ✓ (default) / Equal-width / Custom
- Bin count input (default 5) + custom breakpoints text field (shown only for Custom)

**Section 2 — Date Columns:**
- Lists all non-numeric columns; user checks to mark as date
- When marked: shows checkboxes for year, month, day, dow, quarter, is_weekend, days_since_min, cyclical encoding toggle, keep original option
- Default when marked: year=true, month=true (rest false)

**Section 3 — Derived Features:**
- Dynamic list of ratio/diff pairs (col_a ÷/− col_b)
- "+ Add pair" button; ✕ to remove

**Section 4 — Polynomial Interactions:**
- Per-column chip toggles for each numeric column
- All / None quick-select buttons
- Live count: "X interaction terms will be added"
- Warning when > 8 cols selected

**Helper functions:** `_toggleFEChipNum`, `_setBinMethod`, `_markAsDate`, `_toggleDateComp`, `_addDerivedFeature`, `_togglePolyCol`, `_polySelectAll`, `_polySelectNone`

**Commits:** `0902f96`, `7f1b0bb`

---

### Fix 4 — Ruff Lint Errors

8 ruff errors in `FeatureEngineeringTransformer`:
- E701: single-line `if x: y = z` date extraction lines → expanded to two lines
- E702: semicolon-separated assignments in derived features → separate lines

**Commit:** `0ed805a`

---

### Fix 5 — What-If Sweep Broken

**Root cause:** After FE, `schema.fields` was built from post-FE columns (including `Age_rank`, `Pclass Fare`, etc.). What-If sent a row with ALL schema columns to `/predict`. `fe.transform()` tried to add FE columns again — polynomial `pd.concat` created duplicate column names → pipeline failed.

**Fix:**
- Capture `_pre_fe_cols = list(X.columns)` before FE is applied
- Build `schema.fields` from `_pre_fe_cols` only — What-If chips show only original features
- Store `pre_fe_cols` in schema JSON
- In `/predict`, strip input to `pre_fe_cols` before calling `fe.transform()`

**Commit:** `5b891c9`

---

### Fix 6 — Wizard Order Reorder

**Old order:** Upload → Data Quality & Preprocessing → Feature Engineering → Configure

**New order:** Upload → Feature Engineering → Data Quality & Preprocessing → Configure

**Rationale:** FE creates new features; preprocessing feature selection should operate on post-FE features.

**Changes:**
- `_amlStep0Next()` / `_amlStep0Skip()` → call `_renderAutoMLStep1c()` instead of `_renderAutoMLStep1b()`
- FE step Skip/Apply buttons → go to `_renderAutoMLStep1b()` (preprocessing)
- FE step Back button → goes to `_renderAutoMLStep1b()` (DQ page, not upload)
- Preprocessing "No, skip →" → goes to `_renderAutoMLStep2()` (was `_renderAutoMLStep1c()`)
- Preprocessing complete → "Yes, Configure AutoML →" → `_renderAutoMLStep2()`
- Added "← Back to FE" button in preprocessing step

**Commits:** `5b891c9`, `3dc0fa8`

---

### Feature 7 — Per-Column Polynomial Selection

**Old:** Single checkbox — applied to ALL numeric columns.

**New:**
- Chip toggles per numeric column — select which columns to include
- All / None buttons
- `poly_cols: ["Age", "Fare"]` replaces `poly: bool` in `fe_config`
- Backend uses only selected columns in `PolynomialFeatures`

**Commit:** `7f1b0bb`

---

## All Commits This Session

| Hash | Description | GitHub | HF |
|------|-------------|--------|-----|
| `0902f96` | feat(automl): Phase 5 redesign — full FE step with FeatureEngineeringTransformer | ✓ | ✓ |
| `0ed805a` | fix(lint): ruff E701/E702 in FeatureEngineeringTransformer | ✓ | ✓ |
| `5b891c9` | fix(automl): What-If sweep + wizard order reorder | ✓ | ✓ |
| `3dc0fa8` | fix(automl): FE back button goes to DQ/Preprocessing, not upload | ✓ | ✓ |
| `7f1b0bb` | feat(automl): per-column selection for polynomial interactions | ✓ | ✓ |

---

## Key Technical Notes

- `FeatureEngineeringTransformer` uses `BaseEstimator, TransformerMixin` — sklearn-compatible
- Rank transform: `np.searchsorted(train_sorted_vals, test_vals)` — maps test values to training percentile
- Binning `transform()` always uses `pd.cut(bins=fitted_edges, include_lowest=True)` regardless of method (quantile/equal_width/custom — all store edge arrays)
- `_pre_fe_cols` must be captured BEFORE `_fe_transformer.fit_transform(X)` — after that X has new columns
- `poly_cols` replaces `poly: bool` — empty list = no polynomial; backend uses only those cols in `PolynomialFeatures`
- What-If: `schema.fields` built from `_pre_fe_cols_` only — FE-derived columns never appear as sweepable features
- FE is applied to full X (before train/test split) — slight leakage for stateful transforms, accepted as MVP trade-off
- Missing indicators must be created before imputation — FE as step 0 ensures this
- `_markAsDate()` re-renders the full step (needed to show/hide component checkboxes)
- `_togglePolyCol()` re-renders the full step (needed to update term count and chip highlights)

---

## Pending Items

| Phase | Item | Status |
|-------|------|--------|
| 6 | SHAP values | Not started |
| 7 | Regression confidence intervals | Not started |
| 8 | Optuna hyperparameter tuning | Not started |
| 9 | Ensemble / stacking | Not started |
| 10 | Pipeline export | Not started |
| 11 | Encoding per-column | Not started |
| 12 | GPU toggle | Not started |
| 13 | SMOTE | Not started |

