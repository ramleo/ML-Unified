# Conversation_2026-06-26_MLUnified_Part124

Continuation from Part 123.

---

## Fixes Implemented

### 1. Learning Curve — Y-axis line touching labels (commit `4ca7e43`, ml-portfolio)
- **Root cause**: First data point at `toX(trainSizes[0])` = `PL = 34px`. Circle radius = 4px. Y-axis labels at `x = PL - 4 = 30px` (right-anchored). They touched at x=30.
- **Fix**: Added `xInset = 10` — all data points inset 10px from both edges: `toX(s) = PL + xInset + ((s - xMin) / xRange) * (cw - 2 * xInset)`. Chart width unchanged.

### 2. Regression "stuck at Evaluating on test set" (commits `1b0d8d6`, `1bf8f27`, ML-Unified + HF)
- **Root cause chain**:
  1. `p.finish(error=str(exc))` sends `{"done": true, "error": "...", "pct": -1}` — frontend receives but ignores `evt.error`, shows `-1%` only
  2. Actual crash: `name 'opt_metric' is not defined` — `_fill_automl_reg_metrics` used `opt_metric` on line 154 but it wasn't a parameter
  3. Secondary metric for regression was using `StratifiedKFold` (requires classification targets) instead of `KFold`
- **Fixes**:
  - Frontend: added `if (evt.error) setError(\`Server error: ${evt.error}\`)` to SSE event handler (commit `fc3a60c`)
  - Backend: added `opt_metric="auto"` to `_fill_automl_reg_metrics` signature + passed it at call site (commit `1bf8f27`)
  - Backend: secondary CV uses `KFold` when `task == "regression"`, `StratifiedKFold` only for classification (commit `1b0d8d6`)
  - Backend: wrapped feature importance + explanation block in `_fill_automl_reg_metrics` in try/except

### 3. Learning Curve chart — Y-axis clamped to [0,1] (commit `683582e`, ml-portfolio)
- **Root cause**: `yMax = Math.min(1, rawMax + pad)` and `yMin = Math.max(0, rawMin - pad)` — correct for classification metrics but wrong for regression. RMSE val score of 4.6 was clamped to 1.0 → validation line rendered off-screen above chart.
- **Fix**: Removed both clamps: `yMin = rawMin - pad`, `yMax = rawMax + pad`.

### 4. Learning Curve gap interpretation — wrong for regression (commit `683582e`, ml-portfolio)
- **Root cause**: `gap = lastTrain - lastVal` is positive when train > val (classification overfitting). For RMSE (lower=better), overfitting is val > train, so gap is negative → triggered "generalizes well" at -459%.
- Also: `gap * 100` assumed [0,1] scores; for raw RMSE values this gives meaningless large numbers.
- **Fix**:
  - Detect lower-is-better from `metricLabel`: `/rmse|mae|error/i`
  - `rawGap = lowerIsBetter ? lastVal - lastTrain : lastTrain - lastVal` (always positive when overfitting)
  - `gapPct = (rawGap / max(|train|, |val|)) * 100` — relative percentage, works for any scale

### 5. Per-column categorical encoding in AutoML wizard (commits `e02015d` ML-Unified, `fef938c` ml-portfolio)
- **New file**: `automl_preprocess_helpers.py` — added `build_cat_transformers(cat_cols, col_enc)` function with `_FreqEnc` (frequency encoding class), OrdinalEncoder, OneHotEncoder grouped by user selection
- **Backend** (`automl.py`): added `col_encoding_json: str = Form("{}")` parameter; replaced single hardcoded OHE block with `build_cat_transformers`
- **Frontend** (`Step2Configure.tsx`): "Categorical encoding" section between SMOTE toggle and Model name — per-column dropdown (One-Hot / Ordinal / Frequency)
- **Frontend** (`AutoMLModal.tsx`): state + prop wiring + `fd.append("col_encoding_json", JSON.stringify(colEncodings))`

### 6. Drop columns in AutoML wizard Step 2 (commit `6354a5f`, ml-portfolio)
- Backend already accepted `drop_cols_json` form field; frontend had no UI for it in AutoML wizard (only in Optuna tool)
- **Fix**: Added checkbox list "Drop columns" section in Step2Configure between categorical encoding and model name; max-height 180px scrollable; checked columns highlighted; wired state in AutoMLModal

---

## Commits

### ML-Unified (backend, GitHub + HF Space)
| Hash | Description | HF |
|------|-------------|-----|
| `fc3a60c` | fix(optuna): show server error in frontend when backend crashes | — (frontend) |
| `1b0d8d6` | fix(automl): regression secondary metric uses KFold; wrap explanation in try/except | ✓ |
| `1bf8f27` | fix(automl): pass opt_metric to _fill_automl_reg_metrics — NameError on regression | ✓ |
| `e02015d` | feat(automl): per-column categorical encoding (onehot/ordinal/frequency) | ✓ |

### ml-portfolio (frontend → Vercel)
| Hash | Description |
|------|-------------|
| `4ca7e43` | fix(optuna): xInset so LC chart points don't touch Y-axis labels |
| `fc3a60c` | fix(optuna): show server error message when backend crashes |
| `683582e` | fix(optuna): remove [0,1] Y-axis clamp; fix gap% direction and relative calculation |
| `fef938c` | feat(automl): per-column categorical encoding UI in Step 2 |
| `6354a5f` | feat(automl): drop columns checkbox list in Step 2 Configure |

---

## Key Technical Lessons

1. **SSE error events**: `p.finish(error=str(exc))` sends `pct=-1`. Frontend must explicitly handle `evt.error` — it is NOT surfaced by default.
2. **Regression metrics are unbounded**: RMSE/MAE can be any positive number — never clamp chart Y-axis to [0,1] for regression.
3. **Gap interpretation needs metric direction**: lower-is-better (RMSE/MAE) vs higher-is-better (F1/AUC) require opposite sign conventions. Use `metricLabel` regex to detect.
4. **StratifiedKFold for regression**: always fails with "Supported target types: binary, multiclass. Got continuous." Use `KFold` for regression.

---

## Pending Test Cases
| File | Coverage | Status |
|------|----------|--------|
| TC-P3.md | Parts 31–50 (content in Testing_Complete_Guide.md) | ❌ Not extracted |
| TC-P5.md | Parts 66–90 | ❌ Not written |
| TC-P6.md | Parts 91–110 | ❌ Not written |
| TC-P7.md | Parts 111–124 (AutoML wizard + Optuna tool) | ❌ Not written |

## Pending Backlog
- Verify drop-columns fix (user reported Ticket/PassengerId still appearing — likely timing issue with Vercel deploy)
- #19–22 Pipeline Builder
- #23 Drift detection
- #24 RAG AI
- #25 Ensemble/stacking
- #45 E2E Playwright CI
- #47 Dockerize
- #50 Batch predictions
- n_trials cap increase 50 → 200
