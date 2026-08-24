# Conversation — 2026-06-16 — ML-Unified — Part 85

---

## Session Summary

Implemented Phase 8: Optuna hyperparameter tuning after AutoML winner selection. Then changed default trials from 20 → 10 to reduce wait time.

---

## Phase 8: Optuna Hyperparameter Tuning

### What it does
After AutoML picks the winning algorithm via 5-fold CV, an optional Optuna tuning phase runs N trials (TPE sampler) to find optimal hyperparameters for that specific algorithm. The tuned estimator replaces the default one before final training.

### Search spaces
| Algorithm | Parameters tuned |
|-----------|-----------------|
| Random Forest | n_estimators, max_depth, min_samples_split, min_samples_leaf, max_features |
| XGBoost | n_estimators, max_depth, learning_rate, subsample, colsample_bytree, reg_alpha, reg_lambda |
| LightGBM | n_estimators, num_leaves, learning_rate, subsample, colsample_bytree, reg_alpha, reg_lambda |
| CatBoost | iterations, learning_rate, depth, l2_leaf_reg |

### Progress flow with Optuna enabled (classification/regression)
- 12–58%: 4-model AutoML CV (unchanged)
- 65%: "Winner found. Tuning with Optuna (N trials)…"
- 65–78%: Per-trial progress updates
- 78%: "Tuning done. Training with best params…"
- 79%: Final model training (`train_pct = 79` vs 68 without Optuna)
- 82%+: Evaluation, learning curve, feature importances (unchanged)

### UI
- Checkbox "Tune hyperparameters with Optuna" in AutoML Step 2 (off by default)
- When checked: trial count pills appear (10 / 20 / 30, default **10**)
- Progress subtitle updates to mention Optuna when enabled
- Results card shows "Optuna Tuning — Best Params" section with param chips and best CV score

---

## Files Changed

### `services/ml-api/requirements.txt`
- Added `optuna>=3.6.0`

### `services/ml-api/app.py`
- Added `_optuna_tune()` helper function (after `_cv_sample`, before `_rule_explanation`)
- Added `_build_tuned_estimator()` helper function
- Added `tune: bool = Form(False)` and `n_trials: int = Form(10)` to `/train` endpoint
- Added `_tune` and `_n_trials` closure captures
- Classification AutoML: Optuna block inserted after winner selection
- Regression AutoML: Optuna block inserted after winner selection
- `train_pct` updated: `79 if (_tune and automl_result) else 68 if automl_result else 20`

### `services/ml-api/frontend/index.html`
- Added `_toggleOptunaTrials()` function
- Added Optuna toggle + trial picker section in `_renderAutoMLStep2()`
- Updated `runAutoML()` to read `doTune` and `nTrials`, include in FormData, update subtitle
- Added Optuna best params display in `_renderAutoMLReport()` (IIFE block)
- Destructured `optuna_params`, `optuna_best_score`, `optuna_n_trials` in report function

---

## Time Impact Discussion

Each Optuna trial = 1× 5-fold CV. AutoML comparison = 4 trials = 20 fits. 10 Optuna trials = 50 more fits = ~2.5× the comparison phase.

| Dataset size | 10 trials | 20 trials | 30 trials |
|---|---|---|---|
| Small (< 1K rows) | ~30s | ~1 min | ~2 min |
| Medium (2–5K rows) | ~1–2 min | ~3–5 min | ~5–8 min |
| Large (capped at 5K) | ~3–5 min | ~6–10 min | ~10–15 min |

Default changed from 20 → 10 trials to keep wait reasonable.

---

## All Commits This Session

| Hash | Description | GitHub | HF frontend | HF app.py |
|------|-------------|--------|-------------|-----------|
| `23abcef` | feat(automl): Phase 8 — Optuna hyperparameter tuning | ✓ | ✓ | ✓ |
| `4120ae7` | fix(automl): change Optuna default trials from 20 → 10 | ✓ | ✓ | ✓ |

---

## Pending Items

| Priority | Item | Status |
|----------|------|--------|
| Next | Phase 9: Ensemble / stacking | Not started |
| Low | Phase 10: Pipeline export | Not started |
| Low | Phase 11: Encoding per-column | Not started |
| Low | Phase 12: GPU toggle | Not started |
| Low | Phase 13: SMOTE | Not started |
