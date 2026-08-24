# Conversation — 2026-06-13 — ML-Unified — AutoML Improvements Part 71

---

## Session Summary

Feature selection bug fixes + AutoML Phase 1 improvements + UI fixes.

---

## Bug Fixes This Session

### Fix 1 — Feature Selection Not Reducing to top_k
**Root cause 1:** `non_num_cols` were appended back after RFE (`df_feat[keep + non_num_cols]`), bypassing top_k entirely.
**Root cause 2:** Condition `len(num_X.columns) > k` used `>` not `>=`, silently skipping RFE when numeric cols == k.
**Root cause 3:** `except Exception: pass` hid all errors.
**Commit:** `52d3469` (GitHub) / `5c32194` (HF)

### Fix 2 — OHE Bool Columns Dropped as Non-Numeric
**Root cause:** pandas >=2.0 returns `bool` dtype from `get_dummies`. `select_dtypes(include="number")` excludes bool. My step 7 code treated all 67 OHE bool columns as non-numeric leftovers and dropped them, leaving only 5 original numeric columns. So top_k=10 was capped to 5.
**Fix:** Cast bool OHE columns to int8 immediately after `get_dummies`.
**Commit:** `3d8e0f4` (GitHub) / `4ac509f` (HF)

### Fix 3 — High-Cardinality Detection Including Numeric Columns
**Root cause:** `nunique > 20` filter applied to ALL columns including numeric ones. Age (88 unique) and Fare (248 unique) were flagged as high-cardinality — user dropped them thinking they were ID columns, losing important features.
**Fix needed (NOT YET IMPLEMENTED):** Add `!c.is_numeric` to frontend filter:
```javascript
const highCardCols = a.columns.filter(c =>
  c.name !== effectiveTarget && !c.is_numeric && (c.nunique || 0) > 20
);
```

---

## AutoML Phase 1 Improvements

### Changes Made
1. **StratifiedKFold 3→5 folds** for classification (more reliable CV estimates)
2. **KFold 3→5 folds** for regression
3. **CatBoost added to AutoML CV** for both classification and regression
4. **`class_weight="balanced"`** on RF and LightGBM when imbalance detected
5. **`stratify=y_enc`** on final `train_test_split` for classification
**Commit:** `40a1b6d` (GitHub) / `87328ec` (HF)

### UI Label Fixes
- "3-fold CV" → "5-fold CV" everywhere
- "RF · XGB · LGB" → dynamic from cv_results (now shows RF · XGB · LGB · CAT)
- Models Tested count: 3 → dynamic from cv_results.length
**Commit:** `91f322c` (GitHub) / `481e456` (HF)

### Stepper Bug Fix
- Results step showed purple (active) instead of green (done) when complete
- Fix: `allDone ? 'done' :` prepended to cls condition
**Commit:** `6d3d73d` (GitHub) / `71332aa` (HF)

---

## Pending Phases (Agreed Order)

| Phase | Item | Status |
|-------|------|--------|
| 1 | Stratified CV + class_weight + 5-fold + CatBoost | Done |
| 2 | Task type detection improvement (nunique threshold) | Not started |
| 3 | Validation set split visibility | Not started |
| 4 | Resource estimation (RAM/time warning) | Not started |
| 5 | Feature Engineering step | Not started (designed in Part 69) |
| 6 | SHAP values | Not started |
| 7 | Regression confidence intervals | Not started |
| 8 | Optuna hyperparameter tuning | Not started |
| 9 | Ensemble / stacking | Not started |
| 10 | Pipeline export | Not started |
| 11 | Encoding per-column | Not started |
| 12 | GPU toggle | Not started |
| 13 | SMOTE | Not started |

---

## AI Explanation Dashboard (Discussed, Not Started)

User wants the AI explanation section redesigned as a two-column dashboard:
- **Left panel:** Structured text — Why it won, Score analysis, Key drivers, Recommendations
- **Right panel:** Graphs — model CV scores bar chart, feature importance bars, win margin indicator
- **Backend change needed:** Change `_llm_explanation` prompt to return structured JSON instead of markdown
  - Fields: `why_won`, `score_analysis`, `key_drivers`, `recommendations`
- **Note:** User is using Gemini 2.5 (not Claude) for explanations
- **Provider support:** Already exists in `_llm_explanation(provider=)` — supports anthropic, openai, groq, gemini-3.5, gemini-2.5

---

## High-Cardinality Fix Still Needed

Frontend filter must be updated to exclude numeric columns:
```javascript
// In _renderAutoMLStep1b()
const highCardCols = a.columns.filter(c =>
  c.name !== effectiveTarget && !c.is_numeric && (c.nunique || 0) > 20
);
```
This prevents Age, Fare etc. from appearing in the "drop" list.

---

## All Commits This Session

| Hash | Description | Where |
|------|-------------|-------|
| `52d3469` | fix(automl): feature selection now actually trims to top_k | GitHub |
| `5c32194` | same | HF |
| `3d8e0f4` | fix(automl): cast OHE bool columns to int8 before feature selection | GitHub |
| `4ac509f` | same | HF |
| `40a1b6d` | fix(automl): 5-fold stratified CV + CatBoost + class_weight | GitHub |
| `87328ec` | same | HF |
| `91f322c` | fix(ui): update AutoML labels to 5-fold CV and 4 models | GitHub |
| `481e456` | same | HF |
| `6d3d73d` | fix(ui): Results step turns green when AutoML completes | GitHub |
| `71332aa` | same | HF |

---

## Key Technical Notes

- **pandas >=2.0:** `get_dummies` returns bool dtype, not uint8. Always cast to int8 after OHE.
- **Feature selection order:** impute → outliers → skewness → encode → standardize → feature_selection (top_k)
- **RFE runs on numeric only** — non-numeric (unencoded) columns are dropped before RFE
- **CatBoost in CV:** Now compared alongside RF/XGB/LGB in AutoML
- **Gemini 2.5:** User is using Gemini for AI explanations via `/automl/explain` endpoint with user_api_key

## HF Space Notes
- **HF Space URL:** https://huggingface.co/spaces/wram1708/ml-unified
- **Render reset:** July 1, 2026
