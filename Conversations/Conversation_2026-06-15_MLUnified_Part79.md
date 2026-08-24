# Conversation — 2026-06-15 — ML-Unified — SHAP/WhatIf Fixes + FE UX Clarity Part 79

---

## Session Summary

Fixed SHAP column mismatch, What-If sweep failures, stale FE selections on new analysis, and incorrect Features count. Added learning curve dynamic interpretation and Features tooltip. Had deep UX discussions on FE-derived feature visibility in SHAP/What-If.

---

## Fixes & Features This Session

### Fix 1 — SHAP Column Mismatch (commit `8cd02e0`)

**Root cause:** `routers/shap.py` called `preprocessor.transform(_df)` directly without applying the FE transformer first. `_df` was built from `schema.fields` (pre-FE columns). The ColumnTransformer expected FE-derived columns (Fare_rank, Age_rank, etc.) that weren't present → "columns are missing" error.

**Fix:** In `_work()`, apply `fe.transform()` on `_df` before `preprocessor.transform()`, mirroring what `/predict` already does:
```python
_df_fe = _df.copy()
_fe = _m.get("fe")
if _fe is not None and _fe.fe_config:
    try:
        _pre_fe = _schema.get("pre_fe_cols")
        if _pre_fe:
            _df_fe = _df_fe[[c for c in _pre_fe if c in _df_fe.columns]]
        _df_fe = _fe.transform(_df_fe)
    except Exception as _fe_err:
        print(f"FE transform in SHAP failed (skipped): {_fe_err}", flush=True)
X_prep = preprocessor.transform(_df_fe)
```

---

### Fix 2 — Numeric Coercion Bug (commit `c1dba11`)

**Root cause (deeper):** Even after Fix 1, SHAP/What-If still failed. Schema columns with `nunique() ≤ 15` (e.g. Pclass with 3 values, SibSp with 7, Sex_female with 2) are classified as `is_cat = True` → their sample values stored as **strings** (`str(mode[0])`). When sent to `/predict` or SHAP:
- `fe.transform()` rank step: `np.searchsorted(numeric_array, ["3"])` fails silently on string input → `Pclass_rank` not added
- Polynomial step: `PolynomialFeatures.transform()` fails on mixed string/float dtypes → all poly interaction terms (`Age SibSp`, `Age Fare`, `Fare SibSp`) not added
- ColumnTransformer then sees missing columns → same "columns are missing" error

**Fix:** In `/predict` (app.py) and `_prep_df` (shap.py), coerce all columns to numeric where possible immediately after building the DataFrame:
```python
df = df.apply(pd.to_numeric, errors='ignore')
```
`pd.to_numeric(errors='ignore')` converts `"3"→3.0`, `"0"→0.0`, `"1"→1.0` while leaving `"male"`, `"C"`, `"S"` unchanged. Safe for all future models.

---

### Fix 3 — Stale FE Selections on New Analysis (commit `c1dba11`)

**Root cause:** `_startFreshAutoML()` only cleared `automlFile`, `automlAnalysis`, `_automlDatasetName`, `_automlTargetCol`. All 5 FE globals persisted across sessions.

**Fix:** Clear all FE globals in `_startFreshAutoML()`:
```javascript
_automlFeatureEng    = { numeric: {}, dates: {}, derived: [], poly_cols: [] };
_automlOrigAnalysis  = null;
_automlOrigFile      = null;
automlFEB64          = '';
automlPreFeCols      = [];
```

---

### Fix 4 — Features Count Shows Actual Trained Features (commit `c1dba11`)

**Root cause:** Training Info showed `(aml.feature_importance || []).length` = number of original schema fields (e.g. 10), not actual post-FE column count.

**Backend fix:** Added `"n_input_cols": len(X.columns)` to both classification and regression `automl_result` dicts (at point after FE is applied, before pipeline fit).

**Frontend fix:** `nFeat = aml.n_input_cols ?? (aml.feature_importance || []).length`

---

### Feature 5 — Features Tooltip (commit `2ebc481`)

Added ⓘ icon next to the Features count in Training Info. On hover:
- If FE was used: *"11 original columns + 4 auto-created by feature engineering (rank transforms, bins, interactions). At prediction time your inputs are automatically expanded to 15 before the model predicts."*
- If no FE: *"15 columns the model was trained on."*

**Logic:**
```javascript
const nOrig    = (aml.feature_importance || []).length;  // schema fields count
const nDerived = aml.n_input_cols != null ? (aml.n_input_cols - nOrig) : 0;
```

---

### Feature 6 — Dynamic Learning Curve Interpretation (commit `2ebc481`)

Added `_lcInterpret(lc, isReg)` function that reads the curve data and generates a plain-English description below the chart.

**Logic:**
- **Gap** (relative difference between train and val): `gap = (vLast - tLast) / |vLast|` for regression (MAE); `gap = (tLast - vLast) / |tLast|` for classification
- **Overfitting**: `gap > 0.25` (25% relative difference)
- **Still improving**: val score changed >0.5% from second-to-last to last point, in the improving direction
- **Metric direction**: regression = lower MAE is better; classification = higher accuracy/F1 is better

**4 cases:**
| Overfitting | Still improving | Message |
|---|---|---|
| Yes | Yes | "Overfitting. Adding more data should help close the gap." |
| Yes | No | "Overfitting. Adding more data unlikely to fix — try simpler features." |
| No | Yes | "Generalises well. More data could push performance higher." |
| No | No | "Generalises well. Adding more data will not significantly improve — model converged." |

**Known limitation:** Gap threshold (25%) may be too lenient for small datasets. Plan to improve with better thresholds and small-dataset warnings.

---

## Key UX Discussion — Why SHAP/What-If Show Fewer Features Than Training

### The Numbers Explained (Titanic Example)

| Stage | Columns | Count |
|-------|---------|-------|
| Original dataset (post-drop-ID-and-target, post-OHE) | Pclass, Age, SibSp, Fare, Sex_female, Sex_male, Cabin_B96 B98, Embarked_S | 8 |
| After FE (rank transforms, bins, polynomial terms) | + Age_rank, Fare_rank, Age_bin, Age×Fare, Age×SibSp, Fare×SibSp, Fare_bin | +7 |
| **Total trained on** | | **15** |

`schema.fields` = 8 (pre-FE columns that survived feature selection)  
`n_input_cols` = 15 (all columns post-FE)  
`n_input_cols - schema.fields.length` = 7 (FE-derived, auto-created)

### Why What-If Shows Only 8 (Correct Behaviour)

FE-derived columns are NOT independent inputs — they are computed FROM the original columns. `Age_rank` is always derived from `Age`.

**The critical concept:** If What-If allowed sweeping `Age_rank` independently while keeping `Age=25` fixed, it would send the model a row that **could never exist in reality**:
- `Age_rank = 0.95` means the person is older than 95% of all passengers (near-maximum age)
- But `Age = 25` is a young person
- These two values **contradict each other** — they cannot co-exist in real data

The model was never trained on such contradictory data → its prediction would be meaningless noise.

**What actually happens when you sweep Age in What-If:**
1. You set `Age = 70`
2. `fe.transform()` automatically computes `Age_rank ≈ 0.95` from Age=70
3. Both Age=70 and Age_rank=0.95 go into the model together — consistent, realistic
4. You see how the prediction changes

So What-If correctly shows only the 8 real inputs you control. The 7 FE-derived columns update automatically in the background.

### Why SHAP Shows Only 8 (Can Be Improved)

Currently SHAP aggregates FE-derived contributions into their parent bars:
- `Age_rank`'s SHAP value is added to `Age`'s bar
- `Fare_rank`'s SHAP value is added to `Fare`'s bar
- `Age×Fare` poly term's SHAP value is split between `Age` and `Fare`

This is done via `_aggregate()` in `routers/shap.py` which matches `col_rank` → `col` via `startswith(col + "_")`.

**Could show all 15:** Unlike What-If, SHAP CAN show all 15 individually since it's just displaying values, not taking user input. The FE-derived bars would show how much the transformed version of a feature contributed SEPARATELY from the raw value. This is planned but not yet implemented.

### Planned Display Improvement

Collapsible "Why only X features?" link inside each tab:

**What-If version:**
> Your original dataset had 8 input columns. Feature engineering created 7 additional columns from them (e.g. Age_rank, Fare_rank, Age×Fare). These derived columns cannot be swept independently — Age_rank is always computed from Age. If you change Age, Age_rank updates automatically. Showing them as separate sweep targets would create physically impossible data (Age=25 but rank=0.95 — which only happens when Age is near the maximum). So What-If only exposes the 8 real inputs you control.

**SHAP version:**
> Your original dataset had 8 input columns. Feature engineering created 7 additional columns (e.g. Age_rank, Fare_rank, Age×Fare) — all 15 went into the model. In SHAP, each derived column's contribution is merged into its parent bar — Age_rank's impact is added to Age's bar, Fare_rank's to Fare's bar. This gives you the total influence of each original feature including all its transforms combined.

---

## The Age_rank Explanation (Save for Reference)

### What is Age_rank?

`Age_rank` is NOT a raw measurement from the dataset. It is a **percentile score** computed from `Age` during the Feature Engineering step.

**How it is computed:**
During training, the FE transformer sees all Age values in the dataset and sorts them. For each row, `Age_rank` = (position of that row's Age in the sorted list) / (total number of rows). Result: a value between 0 and 1.

**Examples (Titanic dataset):**
- Age = 5 → Age_rank ≈ 0.02 (near the bottom — very young, younger than 98% of passengers)
- Age = 28 → Age_rank ≈ 0.50 (middle of the distribution — median age)
- Age = 70 → Age_rank ≈ 0.95 (near the top — older than 95% of passengers)

**Why it helps the model:**
The rank transform removes the effect of outliers and skewness. Instead of the model learning "Age=70 matters because 70 is a big number", it learns "being in the top 5% of ages matters". The relationship becomes about relative position, not absolute value.

### Why Age_rank Cannot Be Set Independently (What-If Context)

Age_rank is always derived from Age. They are linked by a mathematical relationship:
- High Age → High Age_rank
- Low Age → Low Age_rank

If a What-If tool allowed you to set `Age=25` AND `Age_rank=0.95` simultaneously:
- `Age=25` says: this person is young (25 years old)
- `Age_rank=0.95` says: this person is older than 95% of all passengers

These two statements **directly contradict each other**. A 25-year-old cannot simultaneously have a 0.95 age rank in a typical adult population. This combination never appeared in the training data, so the model has no reliable way to make a prediction from it — any output would be noise.

If What-If allowed you to sweep Age_rank from 0 to 1 independently while keeping Age=25 fixed, the model would receive a row that could never exist in reality — a young person (25) who simultaneously has the rank of a very old person (0.95). The model was never trained on such contradictory data, so its prediction would be meaningless noise.

**What correctly happens during a What-If sweep of Age:**
1. User sweeps Age from 5 → 70
2. For each Age value, `fe.transform()` recomputes Age_rank correctly: Age=5→0.02, Age=28→0.50, Age=70→0.95
3. Both Age and Age_rank go into the model together — always consistent, always realistic
4. The prediction curve reflects the true relationship

This is why What-If only exposes the original 8 input columns — the 7 FE-derived columns are always kept consistent automatically.

### Same Logic Applies to Other FE Transforms

- `Fare_rank` is always derived from `Fare` → cannot sweep independently
- `Age_bin` is always derived from `Age` → cannot sweep independently  
- `Age×Fare` (polynomial interaction) is always `Age × Fare` → cannot sweep independently (it moves whenever Age OR Fare moves)

---

## All Commits This Session

| Hash | Description | GitHub | HF |
|------|-------------|--------|----|
| `8cd02e0` | fix(shap): apply FE transformer before preprocessor.transform — resolves column mismatch | ✓ | ✓ |
| `c1dba11` | fix(predict/shap): coerce string numerics before FE transform; clear FE globals on new analysis; show actual trained feature count | ✓ | ✓ |
| `2ebc481` | feat(ui): features tooltip with FE explanation; dynamic learning curve interpretation | ✓ | ✓ |

---

## Pending Items

| Phase | Item | Status |
|-------|------|--------|
| — | Add "Why only X features?" collapsible in SHAP and What-If tabs | **Next** |
| — | Fix learning curve interpretation accuracy (small datasets, better thresholds) | **Next** |
| — | Show all 15 SHAP bars (FE-derived separately labelled) | Planned |
| 6 | SHAP values (full phase) | Partial |
| 7 | Regression confidence intervals | Not started |
| 8 | Optuna hyperparameter tuning | Not started |
| 9 | Ensemble / stacking | Not started |
| 10 | Pipeline export | Not started |
| 11 | Encoding per-column | Not started |
| 12 | GPU toggle | Not started |
| 13 | SMOTE | Not started |
