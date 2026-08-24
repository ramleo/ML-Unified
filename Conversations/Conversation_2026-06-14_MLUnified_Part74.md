# Conversation — 2026-06-14 — ML-Unified — AutoML Dashboard & Accent Colors Part 74

---

## Session Summary

Complete `_renderExplanationDashboard` redesign replacing CV Fold Stability + Feature Importance with Confusion Matrix / Predicted vs Actual scatter, expanded Winner Model Metrics, and Learning Curve. Fixed accent color consistency across entire AutoML UI. Discovered and fixed that `app.py` was never being uploaded to HF Space.

---

## Features & Fixes This Session

### Feature 1 — AI Explanation Dashboard Redesign

**Replaced:**
- CV Fold Stability (5 bars)
- Feature Importance section

**With:**
- **Left column:** AI explanation panels (as before)
- **Right column top:** Confusion Matrix (classification) OR Predicted vs Actual scatter (regression)
- **Right column middle:** Winner Model Metrics (expanded)
- **Right column bottom:** Learning Curve

**`_renderExplanationDashboard` new signature:**
```javascript
function _renderExplanationDashboard(explanation, cv_results, feature_importance, accent, winner, can_upgrade, isReg, selection_metric, winner_metrics, vizData)
```

`vizData` carries: `{confusion_matrix, class_names, scatter_actual, scatter_predicted, learning_curve}`

**Commit:** `bcd7a4e`

---

### Feature 2 — Inline SVG Charts

Three helper functions inside `_renderExplanationDashboard`:

**Confusion Matrix (classification):**
```javascript
function _confusionMatrixSVG(cm, classNames, ac) {
  const W = 320, pad = 50, cell = (W - pad) / show;
  // diagonal cells in accent color with intensity, off-diagonal muted
  return `<svg viewBox="0 0 ${W} ${H}" style="width:100%">...`;
}
```

**Scatter Plot (regression):**
```javascript
function _scatterSVG(actual, predicted, ac) {
  const W = 320, H = 240, pad = 40;
  // ±1 RMSE shaded band, perfect diagonal line, scatter points
  return `<svg viewBox="0 0 ${W} ${H}" style="width:100%">...`;
}
```

**Learning Curve (both):**
```javascript
function _learningCurveSVG(lc, ac, reg) {
  const W = 320, H = 200, padL = 40, padR = 8, padT = 12, padB = 26;
  // solid train line, dashed val line, shaded gap between
  return `<svg viewBox="0 0 ${W} ${H}" style="width:100%">...`;
}
```

**Commits:** `bcd7a4e`, `dd354c5` (larger SVGs)

---

### Feature 3 — Expanded Winner Model Metrics

**Classification (5 metrics + ROC-AUC full-width):**
- Accuracy, F1 Score, Precision, Recall (2×2 grid)
- ROC-AUC full-width below

**Regression (up to 6):**
- MAE, RMSE, MAPE, Max Error, Median AE (always shown)
- R² (only shown if ≥ 0.60)

**Commit:** `bcd7a4e`

---

### Feature 4 — Backend: New Fields in `/automl` Response

**New imports:**
```python
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold, KFold, learning_curve
from sklearn.base import clone
from sklearn.metrics import (accuracy_score, mean_absolute_error, mean_squared_error,
                             silhouette_score, f1_score, roc_auc_score, r2_score,
                             precision_score, recall_score, confusion_matrix as sk_confusion_matrix,
                             median_absolute_error, mean_absolute_percentage_error)
```

**Classification additions:**
```python
cm = sk_confusion_matrix(y_test, y_pred)
automl_result["confusion_matrix"] = cm.tolist()
automl_result["class_names"] = [str(c) for c in le.classes_]
# learning_curve with StratifiedKFold, scoring=sel_metric
```

**Regression additions (expanded winner_metrics + scatter + learning curve):**
```python
wm_reg = { "mae": ..., "rmse": ..., "mape": ..., "max_error": ..., "median_ae": ... }
if r2 >= 0.60: wm_reg["r2"] = round(float(r2), 4)
# scatter: 300 random sample points from y_test vs y_pred
# learning_curve with KFold, scoring="neg_mean_absolute_error" (negated when stored)
```

**CRITICAL DISCOVERY:** `app.py` was never being uploaded to HF Space. Fixed by adding a second `upload_file()` call with `path_in_repo='app.py'`.

---

### Fix 5 — Column Height Equalisation

**Problem:** Left column was shorter than right column, leaving empty space at bottom.

**Fix:**
```css
.aml-exp-dashboard { align-items: stretch; }
.aml-exp-left .aml-exp-panel:last-child { flex: 1; }
```

**Commit:** `a7e5aa2`

---

### Fix 6 — Accent Color Consistency (Full AutoML)

Systematically applied `var(--active-accent, #818cf8)` / `${_acc}` across all AutoML elements:

| Element | Old | New |
|---------|-----|-----|
| `.aml-stat-val` | `var(--text1)` | `var(--active-accent, var(--accent-from))` |
| `.aml-algo-val` | `var(--text2)` | `var(--active-accent, var(--accent-from))` |
| SHAP bar fill | hardcoded | `var(--active-accent, var(--accent-from))` |
| SHAP negative | separate | `var(--active-accent, var(--accent-from))` |
| What-If chart | `activeModel?.accent` | reads `--active-accent` CSS variable |
| Preprocessing complete card | white | reads `--active-accent` at runtime |
| "PREPROCESSING COMPLETE" text | white | `${acc}` |
| Preprocessing SVG checkmark | accent | `stroke="${acc}"` |
| "Columns to consider dropping" | default | `${_acc}` border + title |
| FEATURES stat card | `var(--text1)` | `${_acc}` |
| Data quality badges | hardcoded colors | `${_acc}` |
| ID column label | default | `${_acc}` |
| Dataset icon circle | default | `${_acc}` |
| "✓ No major issues detected" | default | `${_acc}` |
| Subtitle "X rows · Y columns" | white `<strong>` | `color:var(--active-accent,#818cf8)` |

**Key pattern for JS template literals:**
```javascript
const _acc = document.documentElement.style.getPropertyValue('--active-accent') || '#818cf8';
// used as: ${_acc} in inline styles
```

**Commits:** `826d391`, `562d0a9`, `22c148b`, `870cf69`, `c43c0bf`, `e1909d9`

---

## Critical HF Deployment Fix

**Problem:** `app.py` backend changes silently never deployed to HF Space.

**Root cause:** Upload script only uploaded `frontend/index.html` — never `app.py`.

**Fix:** Added second upload call:
```python
upload_file(
    path_or_fileobj='services/ml-api/app.py',
    path_in_repo='app.py',
    repo_id='wram1708/ml-unified',
    repo_type='space',
    token='<REDACTED_HF_TOKEN>',
)
```

Going forward: any backend change requires uploading BOTH `frontend/index.html` AND `app.py`.

---

## All Commits This Session

| Hash | Description | Where |
|------|-------------|-------|
| `b3a7876` | AI explanation dashboard redesign (fold stability + key metrics + actionable insights) | GitHub |
| `826d391` | accent for preprocessing stat cards, SHAP bars, What-If chart | GitHub |
| `562d0a9` | preprocessing complete card border/title/icon uses active accent | GitHub |
| `bcd7a4e` | confusion matrix, scatter plot, learning curve, expanded metrics in AI explanation | GitHub |
| `dd354c5` | larger SVGs for confusion matrix, scatter, learning curve | GitHub |
| `a7e5aa2` | stretch left column to match right column height | GitHub |
| `22c148b` | "Columns to consider dropping" card uses active accent | GitHub |
| `870cf69` | FEATURES stat card uses active accent | GitHub |
| `c43c0bf` | full data quality card accent consistency | GitHub |
| `e1909d9` | stat cards, algo scores, row/col numbers use active accent | GitHub |

---

## Pending Items (Agreed Order)

| Phase | Item | Status |
|-------|------|--------|
| 3 | Validation set split visibility | Not started |
| 4 | Resource estimation (RAM/time/CPU warning) | Not started |
| 5 | Feature Engineering step | Not started |
| 6 | SHAP values | Not started |
| 7 | Regression confidence intervals | Not started |
| 8 | Optuna hyperparameter tuning | Not started |
| 9 | Ensemble / stacking | Not started |
| 10 | Pipeline export | Not started |
| 11 | Encoding per-column | Not started |
| 12 | GPU toggle | Not started |
| 13 | SMOTE | Not started |

---

## Key Technical Notes

- `clone(pipeline)` from `sklearn.base` creates unfitted copy — required for `learning_curve()` which needs to fit fresh estimators
- `learning_curve` for regression uses `scoring="neg_mean_absolute_error"` — negate scores before storing
- SVG charts use `style="width:100%"` only (no `max-height`) — viewBox drives aspect ratio naturally
- `align-items: stretch` on dashboard container + `flex: 1` on last left panel = even column heights
- Cannot append hex alpha to CSS variable: `var(--accent)44` is invalid — must use `color-mix()` or hardcode
- Preprocessing complete card reads accent at runtime (JS): `document.documentElement.style.getPropertyValue('--active-accent')`
