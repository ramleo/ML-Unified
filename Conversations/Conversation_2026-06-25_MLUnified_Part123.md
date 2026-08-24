# Conversation_2026-06-25_MLUnified_Part123

Continuation from Part 122.

---

## Fixes Implemented

### 1. Optuna — roc_auc "All trials failed" root cause found
- **Root cause**: sklearn 1.4 changed `cross_val_score` default `error_score` from `'raise'` to `np.nan`. When `roc_auc_score` failed on a fold (e.g. "Only one class present"), sklearn silently returned NaN instead of raising. All trials got NaN score → NaN filter (from Part 122) removed them → `trial_history` empty → RuntimeError.
- Before Part 122: NaN values included in `trial_history` → `{"value": NaN}` in SSE → invalid JSON → UI freeze at 97% (the original bug).

### 2. Optuna objective — error capture (commit `c7f4a5a`)
- Added `_first_error: list = []` to capture first exception from `cross_val_score`
- `try/except` around `cross_val_score` → catches exception → logs it → raises `optuna.TrialPruned()`
- NaN guard: if score is NaN → raises `TrialPruned()`
- RuntimeError now includes actual cause: `f"Cause: {err_detail}"`

### 3. Optuna objective — sklearn 1.4 `is_classifier()` bypass for roc_auc (commit `e69605d`)
- **Error**: `"Pipeline should either be a classifier... Got a regressor with response_method=predict_proba instead."`
- **Cause**: sklearn 1.4 `roc_auc` scorer calls `_get_response_values()` which runs `is_classifier()` type detection. CatBoost/XGBoost don't register `_estimator_type` correctly in some versions → sklearn treats pipeline as regressor.
- **Fix**: For `roc_auc`/`roc_auc_ovr`, skip the scorer entirely. Use `cross_val_predict(..., method='predict_proba')` directly (no type check), then compute `roc_auc_score` manually on OOF probabilities.

### 4. Optuna objective — minority class fold adjustment (commit `b7a2222`)
- Before calling objective, detect minority class count vs n_splits
- If `minority_count < n_splits`: reduce `StratifiedKFold` to `max(2, minority_count)` so every test fold has both classes
- Added `error_score='raise'` explicitly to `cross_val_score` so sklearn 1.4 NaN-silencing doesn't apply

### 5. Learning curve — same sklearn 1.4 roc_auc fix (commit `acf419a`)
- `learning_curve(scoring="roc_auc")` had same `is_classifier()` issue
- Fix: replace string scorer with raw callable `(estimator, X, y) → float` that calls `predict_proba` directly

### 6. Learning curve chart — responsive sizing (multiple commits)
- **Root cause of all chart sizing issues**: SVG with `width="100%"` and a fixed viewBox uses `preserveAspectRatio="xMidYMid meet"` by default — scales to fit height, centers horizontally → empty space on sides. `preserveAspectRatio="none"` stretches everything, distorting circles and text.
- **Final fix** (`c7b657d`): `useRef` measures actual SVG pixel width after mount. Coordinates computed in real pixels. No viewBox, no preserveAspectRatio. Fixed `height={160}`. Circles stay circular, text stays normal at any container width.
- Added Y-axis padding (15% of range, min 0.05) and null/NaN guards for scores.

---

## Commits

### ML-Unified (backend)
| Hash | Description | HF |
|------|-------------|-----|
| `c7f4a5a` | fix(optuna): capture actual CV error in RuntimeError | ✓ |
| `b7a2222` | fix(optuna): roc_auc NaN from sklearn 1.4 error_score default | ✓ |
| `e69605d` | fix(optuna): bypass sklearn 1.4 is_classifier() for roc_auc | ✓ |
| `acf419a` | fix(automl): same is_classifier() bypass in learning curve | ✓ |

### ml-portfolio (frontend)
| Hash | Description |
|------|-------------|
| `bc95dfa` | fix(optuna): Y-axis padding + null score guards in LC chart |
| `1a380fe` | fix(optuna): reduce chart size/font (partial) |
| `000ac16` | fix(optuna): maxWidth 300px (wrong approach) |
| `a839ac5` | fix(optuna): overflow:hidden + PL/PR adjustments |
| `db82ded` | fix(optuna): fill column width, fixed 140px height |
| `12c4a85` | fix(optuna): preserveAspectRatio=none (wrong — distorts) |
| `c7b657d` | fix(optuna): useRef pixel measurement — final correct fix |

---

## Key Technical Lessons

1. **SVG responsive sizing**: `width="100%"` with viewBox = proportional scaling (distorts if aspect ratio forced). Correct approach: `useRef` to measure actual pixel width, compute coordinates in real pixels, use fixed `height` attribute only.
2. **sklearn 1.4 breaking change**: `cross_val_score` default `error_score` changed from `'raise'` to `np.nan`. Always pass `error_score='raise'` explicitly.
3. **sklearn 1.4 roc_auc scorer**: Uses `is_classifier()` type detection before calling `predict_proba`. Some third-party models (CatBoost, XGBoost) don't register correctly. Use `cross_val_predict(method='predict_proba')` + manual `roc_auc_score` to bypass.

---

## Pending

- TC-P3, TC-P5, TC-P6, TC-P7 test cases
- #19-22 Pipeline Builder, #23 Drift, #24 RAG AI, #25 Ensemble, #27 Per-column encoding, #45 E2E Playwright CI, #47 Dockerize, #50 Batch predictions
