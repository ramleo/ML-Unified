# Session 2026-06-24 — Optuna Tuning Fix + Results UI

## Summary

Full debugging and fix session for Optuna tuning on HF Space, plus UI improvements to Optuna results page.

---

## Key Bugs Fixed

### 1. HF Space Upload Wrong Path (Root Cause of Everything)
- **Bug:** All backend file uploads used `services/ml-api/routers/core/foo.py` as the HF path
- **Reality:** HF Space repo has flat root structure — files must be at `routers/core/foo.py`
- **Impact:** Every code change since the refactor was silently going to a dead folder the container never read
- **Fix:** Strip `services/ml-api/` prefix on all HF uploads

### 2. Pydantic v2 Bool Form Coercion Bug
- **Bug:** `tune: bool = Form(False)` — FastAPI 0.136.3 + Pydantic v2 doesn't coerce string `"true"` to `True`
- **Impact:** `tune` was always `False`, so Optuna tuning never ran (used default params every time)
- **Fix:** Changed to `tune: str = Form("false")` and manually convert: `tune.lower() in ("true", "1", "yes")`
- **Same fix applied to:** `use_smote`

### 3. Optuna Not Installed on HF Space
- **Bug:** `ModuleNotFoundError: No module named 'optuna'`
- **Root cause:** HF Space `requirements.txt` (at root) was missing `optuna` and `imbalanced-learn`
- **Fix:** Uploaded updated `requirements.txt` with `optuna>=3.6.0` and `imbalanced-learn>=0.12.0`

### 4. _optuna_tune Return Value Mismatch
- **Bug:** Changed `_optuna_tune` to return 4 values but callers still unpacked 2
- **Fix:** Updated `automl_clf.py` and `automl_reg.py` to unpack `best_params, best_val, optuna_trials, param_importance`

---

## Features Added

### Optuna Results Page (OptunaResults.tsx)
- **Bayesian Optimization Summary** — TPE sampler badge, n_trials, best trial #, improvement %
- **Trial History** — SVG line chart (dots + running best dashed line, best trial glowing dot)
- **Hyperparameter Importance** — horizontal bars
- **Best Tuned Parameters** — param/value table
- **Winner Metrics** — accuracy, F1, precision, recall, ROC-AUC grid
- **Feature Importance** — top 10 bars
- Layout: Trial History (left) | HP Importance + Best Params stacked (right)

### Optuna Backend Improvements
- `multivariate=True` in TPESampler — models parameter correlations jointly
- `MedianPruner` — kills bad trials early
- Wider XGBoost search space: added `min_child_weight`, `gamma`
- Wider LightGBM search space: added `min_child_samples`
- Both now support `n_estimators` up to 500, `learning_rate` down to 0.005

### Keep-Alive Ping
- `KeepAlive.tsx` component added to root layout
- Pings `/health` on load and every 4 minutes to prevent HF Space sleep

---

## Commits

### ml-portfolio
| Hash | Description |
|------|-------------|
| `4570f80` | SVG line chart for trial history |
| `33b099e` | Side-by-side layout for trial history + HP importance + best params |
| `626874a` | KeepAlive ping every 4min |
| `0ea282d` | Defensive tuningRan check |
| `3a08a89` | OptunaResults full rebuild with 6 sections |
| `90652e4` | Remove static sections from Optuna/SHAP/Ensemble pages |

### ML-Unified
| Hash | Description |
|------|-------------|
| `87d972c` | Wider search spaces + multivariate TPE + MedianPruner |
| `70ee4a1` | Fix tune/use_smote Pydantic v2 bool bug |
| `3160bbd` | _optuna_tune returns 4 values |

---

## HF Space Upload Rule (CRITICAL)

The HF Space repo root is flat. Always strip `services/ml-api/` prefix:

| Local | HF Space |
|-------|----------|
| `services/ml-api/routers/core/foo.py` | `routers/core/foo.py` |
| `services/ml-api/app.py` | `app.py` |
| `services/ml-api/requirements.txt` | `requirements.txt` |
| `services/ml-api/frontend/index.html` | `frontend/index.html` |

Git push to `hf` remote is blocked by `.pkl` binaries — always use `upload_file` API.

---

## Pending (Optuna Page)
- [ ] Metric selection (optimize for Accuracy vs F1 vs ROC-AUC vs Precision)
- [ ] Drop columns option in Step 2 Configure
- [ ] AI explanation of results
- [ ] Raise n_trials cap from 50 to 200

## Pending (Broader Backlog)
- #19–22: Pipeline Builder
- #23: Drift detection
- #24: RAG-enhanced AI explanation
- #25: Ensemble/stacking backend
- #27–28: Per-column encoding, GPU toggle
- #39–44: MLOps items
- #45: E2E Playwright CI
- TC files: TC-P3, TC-P5, TC-P6, TC-P7 not written
