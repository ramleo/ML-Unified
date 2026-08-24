# Conversation — 2026-06-15 — ML-Unified — SHAP/What-If Fix + FE UI Bugs Part 80

---

## Session Summary

Continued fixing SHAP/What-If column mismatch errors. Diagnosed root cause as feature-selected-away source columns (Pclass, SibSp) not being available at inference time for FE-derived column creation. Implemented correct fix: store real sample values for ALL pre_fe_cols in schema, use them at inference time instead of NaN. Also fixed FE UI scroll-to-top bug and added +N derived column badge.

---

## Fixes This Session

### Fix 1 — Missing pre_fe_cols filled with NaN (commit `9bef7be`)

**What it did:** At inference time, any `pre_fe_cols` column not provided by the user (because feature selection dropped the source column from schema.fields) was filled with `NaN` before calling `fe.transform()`.

**Why it was wrong:**
- `Pclass_was_missing = 1` — tells the model "Pclass was missing" but Pclass was never actually missing in training data
- `Pclass_rank = NaN` → imputed to training mean (0.5) — inaccurate
- `SibSp = NaN → fillna(0)` in polynomial step → `Fare SibSp = Fare × 0 = 0` — wrong if SibSp was non-zero

### Fix 2 — Polynomial `get_feature_names_out()` fails on deserialized objects (commit `0649fa6`)

**Root cause:** `self._poly_transformer_.get_feature_names_out(avail)` fails on deserialized sklearn objects in some versions (feature_names_in_ may not be stored or version mismatch).

**Fix:** Replaced with `combinations(avail, 2)` to compute interaction names directly:
```python
inter_names = [f"{a} {b}" for a, b in _comb(avail, 2)]
n_inter = len(inter_names)
inter_vals = poly_out[:, -n_inter:]  # last C(n,2) cols of poly output
```
No sklearn API dependency. Guaranteed layout for `interaction_only=True, include_bias=False, degree=2`.

### Fix 3 — Fill missing pre_fe_cols with real sample values (commit `a8051e7`) ← CORRECT FIX

**Root cause confirmed:** Feature selection drops source columns (e.g. Pclass, SibSp) from schema.fields but the ColumnTransformer expects their FE-derived columns (Pclass_rank, Pclass_was_missing, Fare SibSp). At inference, source columns are not in the user's input. FE can't create derived columns without them.

**Correct approach:**
- At preprocessing time: compute `pre_fe_sample` = median/mode for ALL pre_fe_cols (before FE or feature selection removes any)
- Store in schema: `"pre_fe_sample": {...}`
- At inference time: fill missing pre_fe_cols from `pre_fe_sample` (real values) instead of NaN

**Changes made:**

`/automl/preprocess` (app.py):
```python
pre_fe_cols = list(df_feat.columns)
# NEW: sample values for all pre_fe_cols before FE/feature-selection
_pre_fe_sample_out = {}
for _pfc in pre_fe_cols:
    if pd.api.types.is_numeric_dtype(df_feat[_pfc]):
        _pre_fe_sample_out[_pfc] = round(float(df_feat[_pfc].median()), 4)
    else:
        _m = df_feat[_pfc].mode()
        _pre_fe_sample_out[_pfc] = str(_m[0]) if not _m.empty else ""
```
Return: added `"pre_fe_sample": _pre_fe_sample_out`

`/train` (app.py):
- New Form field: `pre_fe_sample_json: str = Form("{}")`
- Preprocessing path: parses from `pre_fe_sample_json`
- Legacy path (no fe_b64): computes from X before FE is applied
- Captures: `_pre_fe_sample_ = _pre_fe_sample` for worker thread
- Schema: `"pre_fe_sample": _pre_fe_sample_`

`/predict` (app.py) and `shap.py`:
```python
_pfs = schema.get("pre_fe_sample", {})
for _c in pre_fe:
    if _c not in df.columns:
        df[_c] = _pfs.get(_c, float("nan"))  # real value, NaN as fallback
```

Frontend:
- New global: `let automlPreFeSample = {}`
- Cleared in: `_startFreshAutoML()` and `_amlRevertPreprocessing()`
- Saved from: preprocessing result `result.pre_fe_sample || {}`
- Passed to `/train` as: `form.append('pre_fe_sample_json', JSON.stringify(automlPreFeSample || {}))`

**Backward compatibility:** Existing models without `pre_fe_sample` in schema fall back to `float("nan")` — same as commit `9bef7be` behavior.

**Note:** Existing trained Titanic model still has old schema (no `pre_fe_sample`). Must retrain after this commit for full fix.

---

### Fix 4 — FE UI Scroll-to-top on Polynomial Checkbox (commit `def4832`)

**Root cause:** `_togglePolyCol()`, `_markAsDate()`, `_addDerivedFeature()`, `_polySelectAll()`, `_polySelectNone()`, delete-derived button all called `_renderAutoMLStep1c()` which sets `innerHTML` → browser resets scroll to top.

**Fix:** Added `preserveScroll` parameter to `_renderAutoMLStep1c(preserveScroll)`:
```javascript
const _feScr = preserveScroll ? document.getElementById('main').scrollTop : 0;
// ... innerHTML set ...
if (preserveScroll) document.getElementById('main').scrollTop = _feScr;
```

All within-step callers now pass `true`. Navigation calls (Back to FE buttons) keep no arg → scroll to top as expected.

### Fix 5 — Numeric Transforms show +N derived badge (commit `def4832`)

Per-column numeric transform row now shows `+N derived` badge (grey, next to dtype):
```javascript
const _nDerived = ['log1p','sqrt','yeo_johnson','rank','outlier_flag','missing_flag']
  .filter(k => fe[k]).length + (fe.bin && fe.bin !== 'none' ? 1 : 0);
const _derivedBadge = _nDerived > 0
  ? `<span style="...">+${_nDerived} derived</span>` : '';
```

---

## OHE vs FE Order Analysis

User asked: "should OHE be before or after FE?"

Current order in `/automl/preprocess`:
```
Missing → Outliers → Skewness → OHE (step 4) → Standardize → FE (step 7) → Feature selection
```

`pre_fe_cols` captured AFTER OHE. Pclass is numeric (not OHE'd) so it stays in pre_fe_cols. Categorical columns (Sex, Embarked) are OHE'd first → `Sex_female`, `Sex_male` etc. appear in pre_fe_cols.

**OHE order is NOT the cause of the SHAP error.** The error was purely the polynomial inference code + missing source columns at inference time. Changing OHE order would break existing models (their schemas reference OHE column names like `Sex_female`) and is not needed.

---

## Root Cause of Entire SHAP/What-If Issue (Summary)

```
Training:
  pre_fe_cols = [Pclass, Age, SibSp, Fare, Sex_female, ...]  ← before FE
  FE creates:  Pclass_rank, Pclass_was_missing, Fare SibSp, ...
  Feature selection: drops Pclass (raw), keeps Pclass_rank, Pclass_was_missing
                     drops SibSp (raw), keeps Fare SibSp
  ColumnTransformer trained on: [Age, Fare, ..., Pclass_rank, Pclass_was_missing, Fare SibSp]
  schema.fields = [c for c in pre_fe_cols if c in X] = [Age, Fare, Sex_female, ...]
                  ↑ No Pclass, no SibSp — they were feature-selected away

Inference (before fix):
  User provides: Age, Fare, Sex_female, ...  (from schema.fields, no Pclass, no SibSp)
  fe.transform(): Pclass not in input → Pclass_rank NOT created ✗
                  SibSp not in input → Fare SibSp NOT created ✗
  ColumnTransformer: columns missing → crash 💥

Inference (after a8051e7):
  User provides: Age, Fare, Sex_female, ...
  Fill from pre_fe_sample: Pclass = 3.0 (median), SibSp = 0.0 (median)
  fe.transform(): Pclass=3.0 → Pclass_rank=0.72, Pclass_was_missing=0 ✓
                  SibSp=0.0 → Fare SibSp = Fare × 0 = 0 ✓ (if SibSp median=0)
  ColumnTransformer: all columns present → works ✓
```

---

## All Commits This Session

| Hash | Description | GitHub | HF |
|------|-------------|--------|----|
| `9bef7be` | fix(predict/shap): fill missing pre_fe_cols with NaN before fe.transform | ✓ | ✓ |
| `f666567` | fix(fe): use to_numpy() + no-arg get_feature_names_out() in poly transform | ✓ | ✓ |
| `0649fa6` | fix(fe): compute poly interaction names from combinations — removes get_feature_names_out() dependency | ✓ | ✓ |
| `def4832` | fix(fe-ui): preserve scroll on poly/chip changes; add +N derived badge per numeric column | ✓ | ✓ |
| `a8051e7` | fix(fe): store pre_fe_sample in schema; fill missing pre_fe_cols with real defaults instead of NaN | ✓ | HF partial (index.html pending) |

---

## Pending Items

| Phase | Item | Status |
|-------|------|--------|
| — | Upload index.html to HF for commit a8051e7 | **Next** |
| — | Retrain Titanic model to get pre_fe_sample in schema | **Next** |
| — | Verify SHAP and What-If work after retrain | **Next** |
| — | Show all 15 SHAP bars (FE-derived labelled separately) | Planned |
| 7 | Regression confidence intervals | Not started |
| 8 | Optuna hyperparameter tuning | Not started |
| 9 | Ensemble / stacking | Not started |
| 10 | Pipeline export | Not started |
| 11 | Encoding per-column | Not started |
| 12 | GPU toggle | Not started |
| 13 | SMOTE | Not started |
