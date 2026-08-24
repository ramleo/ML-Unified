# Conversation — 2026-06-12 — ML-Unified — AutoML Feature — Part 66

---

## Session Summary

Implemented AutoML as a dedicated section with full model selection report, plus UI polish across Predict and Drift sections.

---

## Feature: AutoML — Dedicated Section

### Commits
| Hash | Description | Pushed |
|------|-------------|--------|
| `2cfb4b0` | feat(automl): AutoML model selection with CV, feature importance, and AI explanation | Yes |
| `d17e279` | fix(automl): remove unused numpy import in regression AutoML branch | Yes |
| `e803ec9` | fix(automl): remove unused numpy import in classification AutoML branch | Yes |
| `7450b25` | feat(automl): dedicated AutoML section — separate wizard, sidebar button, full report | Yes |
| `a5a63dd` | fix(automl+ui): no emojis, bar animations, state persistence, explanation button feedback, Predict/Drift polish | Yes |

---

## Design Decisions

### What AutoML does
- Runs 3-fold cross-validation on **Random Forest**, **XGBoost**, and **LightGBM**
- Picks winner by: F1-macro (imbalanced classification) / accuracy (balanced) / MAE (regression)
- Subsamples to 5,000 rows for CV on large datasets; retrains winner on full data
- Feature importances aggregated back from OHE-expanded columns to original feature names

### Architecture
- **Separate section** (not inside Train New Model wizard) — own sidebar button, own 3-step wizard
- **Same `/train` endpoint** internally with `algorithm=AutoML` — no new backend service
- **3-tier LLM explanation**: app `ANTHROPIC_API_KEY` env var → user-supplied key → rule-based text
- `/explain` POST endpoint added for user-key upgrade path

### Regression metrics
- Always shows MAE + RMSE
- R² only included if R² ≥ 0.60 (below that it's misleading)

### Title
"AutoML: Model Selection Report" — not "best algorithm" (we only test 3, not all possible algorithms)

---

## Backend Changes (`services/ml-api/app.py`)

### New imports
```python
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold, KFold
from sklearn.metrics import (accuracy_score, mean_absolute_error, mean_squared_error,
                             silhouette_score, f1_score, roc_auc_score, r2_score)
```

### New helper functions (module-level, before `/train`)
- `_cv_sample(X, y, max_rows=5000)` — stratified subsample for large datasets
- `_extract_feature_importances(pipeline, num_cols, cat_cols)` — aggregates OHE columns back to originals
- `_rule_explanation(winner, cv_results, task, ...)` — always-available text summary
- `_llm_explanation(api_key, winner, cv_results, task, ...)` — calls `claude-haiku-4-5-20251001`, returns None on failure

### `/train` changes
- `automl_result = None` and `_effective_algorithm = _algorithm` initialised before task branches
- AutoML classification branch: detects imbalance (< 20% minority), runs 3-fold CV, picks winner, falls back to RF on exception
- AutoML regression branch: 3-fold CV with neg_mean_absolute_error scoring, winner = lowest MAE
- Schema `model` and `description` fields use `_effective_algorithm` (winner name, not "AutoML")
- Result dict includes `"automl": automl_result` when not None
- Regression: always includes RMSE; adds R² only if ≥ 0.60

### New `/explain` endpoint
```
POST /explain
Body: { "automl_data": {...}, "user_api_key": "sk-..." }
Response: { "explanation": "...", "source": "user_key" | "rule" }
```

### `requirements.txt`
Added `anthropic>=0.40.0`

---

## Frontend Changes (`services/ml-api/frontend/index.html`)

### Sidebar
- "AutoML" button added between "Train New Model" and "SHAP Analyzer"
- Sparkle icon, indigo colour (`#818cf8`)

### Train wizard
- `algorithmOptions()` unchanged — no AutoML option in Train New Model dropdown

### AutoML wizard (new functions)
- `_automlStepsHTML(active, allDone)` — 3 steps: Upload / Configure / Results
- `showAutoMLWizard()` — restores last result if available; otherwise starts fresh
- `_startFreshAutoML()` — resets state and shows step 1
- `_renderAutoMLStep1()` — file upload zone (matches train wizard style, indigo icon)
- `_handleAutoMLFile()` / `_setAutoMLFile()` — no emoji in file info display
- `_analyzeAutoMLCSV()` — calls `/analyze`, transitions to step 2
- `_renderAutoMLStep2()` — model name + target + task + accent (no algorithm selector)
- `_amlSuggestTask()` — auto-suggests task based on target column
- `_renderAutoMLResultsPage(result)` — renders results page; extracted for reuse on revisit
- `runAutoML()` — calls `/train` with algorithm=AutoML, saves `_lastAutoMLResult`, renders page

### AutoML report
- `_renderAutoMLReport(automl, accent)` — renders CV score bars + feature importance bars + explanation
- Bars start at `width:0%` with `data-target` and `data-delay` attributes
- `_animateAutoMLBars()` — uses `requestAnimationFrame` + staggered `setTimeout` delays
- `getAIExplanation()` — validates key is non-empty (shows error if blank), calls `/explain`, updates badge
- `_currentAutoMLData` — stored for the explain call; includes `task` field

### AutoML CSS (new)
- `.aml-report`, `.aml-title`, `.aml-subtitle`, `.aml-note`
- `.aml-grid` — 2-column responsive grid
- `.aml-card`, `.aml-card-title`, `.aml-metric-label`
- `.aml-bar-row`, `.aml-bar-label`, `.aml-bar-label.aml-winner`, `.aml-bar-track`, `.aml-bar-fill`, `.aml-bar-val`
- `.aml-explanation-card`, `.aml-explanation-header`, `.aml-source-badge`, `.aml-source-badge.aml-ai`
- `.aml-explanation-text`, `.aml-key-row`

---

## UI Polish (same commit `a5a63dd`)

### Predict — regression result card
- Added subtle accent-tinted background + border to `.result-reg-main`
- Increased font size of `.result-reg-value` to `3rem`

### Drift — mode toggle
- Restyled `.drift-mode-bar` + `.drift-mode-btn` from segmented-control to pill chips
- Matches the `whatif-chip` visual style (border-radius: 9999px, accent border/color on active/hover)

---

## Key Technical Details

### Imbalance detection
```python
cls_counts = pd.Series(y_enc).value_counts()
min_ratio  = float(cls_counts.min()) / len(y_enc)
is_imbal   = min_ratio < 0.20
sel_metric = "f1_macro" if is_imbal else "accuracy"
```

### Feature importance aggregation
OHE expands `cat_cols` into N columns per category. The `_extract_feature_importances()` function maps each OHE column back to its original feature by summing importances:
```python
all_feats = list(num_cols)  # numeric: 1:1
for i, col in enumerate(cat_cols):
    n_cats = len(ohe.categories_[i])
    all_feats.extend([col] * n_cats)  # cat: 1:N
# then sum importances by original feature name
```

### Subsampling
`_cv_sample()` uses `np.random.RandomState(42).choice(len(X), 5000, replace=False)` — handles both numpy arrays and pandas Series.

### LLM model
`claude-haiku-4-5-20251001` — fast and cheap for short explanations (max_tokens=300).

---

## Bugs Fixed This Session

| Bug | Cause | Fix |
|-----|-------|-----|
| Ruff F401: unused numpy import (regression branch) | `import numpy as _np` added defensively but `_cv_sample` handles numpy internally | Removed import |
| Ruff F401: unused numpy import (classification branch) | Same reason | Removed import |
| AutoML option in Train wizard dropdown | Misunderstood requirement — AutoML should be separate, not an algorithm option | Removed from dropdown; dedicated section instead |
| Emoji in AutoML wizard | Used 📄 and ✅ | Replaced with SVG icons and text |
| "Get AI Explanation" silently did nothing when no key | `if (!key) return;` with no feedback | Added error div that shows "Please enter your Anthropic API key first." |
| AutoML results lost on navigation | State not persisted | Added `_lastAutoMLResult`; restores on revisit with "New Analysis" button |

---

## Pending

| Priority | Item | Status |
|----------|------|--------|
| | Model versioning + rollback | Not started |
| | Drift alerting (email/Slack) | Not started |
| | LLM-assisted feature suggestion after EDA | Not started |
| | Automated retraining pipeline | Not started |
| | Time series forecasting | Not started |
| | E2E tests in CI | Not started |
| | #21 Batch predictions | Deferred |
| | #5 Proxy page | Deferred |
| Last | #22 Dockerize | Do last |
