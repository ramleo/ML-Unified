# Conversation_2026-06-25_MLUnified_Part121

## Session Summary

Continuation from Part 120. Focused on Optuna improvements, bug fixes, and UI polish.

---

## Features Implemented

### 1. Sampler Selection
- **Dropdown in Step 2**: TPE (Tree Parzen Estimator) and QMC (Quasi-Monte Carlo / Sobol)
- GP Sampler attempted → failed (requires `torch`), replaced with CMA-ES → failed (requires `cmaes` package), finally settled on QMC (bundled with Optuna, no extra deps)
- AutoSampler removed (can pull torch internally)
- Backend: `_optuna_tune` in `automl_helpers.py` accepts `sampler` param
- Result stores `optuna_sampler` for frontend badge display

### 2. Secondary Metric Tracking
- **Dropdown in Step 2** (task-aware): Classification: accuracy/f1_weighted/f1_macro; Regression: mae/rmse/r²
- Resets to "none" when task changes
- Backend: per-trial secondary `cross_val_score` stored as `trial.user_attr("secondary_score")`
- Result stores `optuna_secondary_metric` + `optuna_secondary_trials`
- **Trial History chart**: green dashed overlay line for secondary metric with legend entry

### 3. Learning Curve Chart
- New `LearningCurveChart` component in `OptunaCharts.tsx`
- Displays train (solid) vs validation (dashed) score across training set sizes
- Metric label now reflects actual Optuna primary metric (ROC-AUC if selected, not always F1)

### 4. Error Surfacing — /optuna-explain
- `_llm_explanation_raw` returns `(text, error)` tuple
- Endpoint returns `{"explanation": ..., "error": ...}`
- Frontend shows actual LLM error instead of generic message

### 5. OptunaResults.tsx Split
- Was 435 lines → split into `OptunaResults.tsx` (391→399 lines) + new `OptunaCharts.tsx` (182 lines)
- `TrialHistoryChart` and `LearningCurveChart` exported from `OptunaCharts.tsx`

### 6. Winner Metrics Fixes
- `f1_macro` now always included in classification `winner_metrics` (was computed but never stored)
- Regression: mae/rmse/r2 all always present (r2 was conditional on >= 0.60 before)
- `METRIC_KEYS` filter fixed: precision/recall now correctly matched
- **Primary metric card**: purple tint + border + ★ label + hover tooltip
- **Secondary metric card**: green border + ◆ label + hover tooltip

### 7. Dynamic Sampler Description
- Section A description text changes based on sampler used (QMC vs TPE explanation)

### 8. Trial History Legend — Primary Metric Label
- "Trial scores" replaced with actual metric name (e.g. "ROC-AUC") based on `optuna_primary_metric`

### 9. CLAUDE.md Rule Added
- Rule #4: HF Space upload mandatory after every backend commit

---

## Bugs Fixed

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| GP Sampler error: `No module named 'torch'` | GPSampler requires PyTorch | Replaced with QMC |
| CMA-ES error: `No module named 'cmaes'` | CmaEsSampler requires separate `cmaes` package; ImportError fires at optimize time not instantiation | Replaced with QMCSampler |
| Learning curve always showed F1 weighted | `sel_metric` hardcoded, not respecting `opt_metric` | Fixed to use opt_metric-derived scoring |
| QMC badge showed TPE description text | Hardcoded string | Made dynamic based on `optuna_sampler` |
| "Trial scores" legend not descriptive | No primary metric passed to chart | Added `primaryMetricLabel` prop |
| f1_macro missing from winner metrics | Computed but not added to `wm` dict | Added to dict |
| precision/recall not showing | METRIC_KEYS used `precision_weighted` which never matched | Fixed to `precision`/`recall` |

---

## Commits

### ML-Unified (GitHub + HF Space)
| Hash | Description |
|------|-------------|
| `3a66b60` | feat(optuna): sampler selection, secondary metric, learning curve, error surfacing |
| `8d792a6` | fix(optuna): replace CMA-ES/Auto with QMC sampler |
| `ab883f3` | fix(optuna): use opt_metric for learning curve scoring; add optuna_primary_metric |
| `da7e89c` | fix(optuna): add f1_macro to clf winner_metrics; always include mae/rmse/r2 in reg |
| `c718bda` | fix(optuna): replace GPSampler with CmaEsSampler (intermediate, superseded) |

### ml-portfolio (GitHub → Vercel)
| Hash | Description |
|------|-------------|
| `1215462` | feat(optuna): sampler/secondary dropdowns, learning curve, error surfacing |
| `a87c485` | fix(optuna): replace GP sampler with CMA-ES in UI (intermediate) |
| `a0e5701` | fix(optuna): replace CMA-ES/Auto with QMC in UI |
| `1d695b3` | fix(optuna): dynamic sampler description, primary metric legend label |
| `411adc5` | fix(optuna): primary/secondary indicators on winner cards; METRIC_KEYS fix |

---

## API Contracts

### New FormData fields sent by OptunaRunner.tsx to /train
- `sampler` — "tpe" | "qmc"
- `secondary_metric` — "none" | "accuracy" | "f1_weighted" | "f1_macro" | "mae" | "rmse" | "r2"

### New fields in automl_result (backend → frontend)
- `optuna_sampler: string` — "tpe" | "qmc"
- `optuna_primary_metric: string` — e.g. "roc_auc" or "auto"
- `optuna_secondary_metric: string` — e.g. "f1_macro" or "none"
- `optuna_secondary_trials: Array<{trial: number, value: number}>`
- `learning_curve: { train_sizes, train_scores, val_scores, metric_label, cv_folds }`

### /optuna-explain response (updated)
- `{"explanation": string | null, "error": string | null}`

---

## Rules Added to CLAUDE.md
- **Rule #4**: HF Space upload mandatory after every backend commit — upload changed `.py` files to `wram1708/ml-unified` (repo_type="space") in same response as git push

---

## Pending / Backlog

### Optuna tool
- Metric label formatting: shows `F1_WEIGHTED`, `ROC_AUC` with underscores — needs clean display names
- Learning curve gap interpretation: overfitting warning if train/val gap > threshold

### Broader project
- #19-22 Pipeline Builder
- #23 Drift detection
- #24 RAG AI
- #25 Ensemble/stacking backend
- #27 Per-column encoding
- #45 E2E Playwright CI
- #47 Dockerize
- #50 Batch predictions
- TC-P3, TC-P5, TC-P6, TC-P7 test cases not yet written
