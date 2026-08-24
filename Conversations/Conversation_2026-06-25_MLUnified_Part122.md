# Conversation_2026-06-25_MLUnified_Part122

## Session Summary

Continuation from Part 121. Focused on Optuna backlog items, progress bar bugs, and a root-cause investigation into the "stuck" and "all trials failed" issues.

---

## Features / Fixes Implemented

### 1. Metric Label Formatting (Frontend)
- Added `METRIC_DISPLAY` map: `f1_weighted` → "F1 Weighted", `roc_auc` → "ROC-AUC", `r2` → "R²" etc.
- Applied to winner metric cards, trial history legend, secondary metric legend
- Removed `textTransform: uppercase` from card labels (was causing F1_WEIGHTED style)
- `metricLabel(k)` helper used everywhere metric keys are displayed

### 2. Learning Curve Gap Interpretation (Frontend)
- After LearningCurveChart, a colored note appears:
  - Red ⚠ if train-val gap > 10% → overfitting warning
  - Green ✓ if gap < 3% → "generalizes well"
  - Gray if in between → "moderate variance"
- Computed from last train_size's scores

### 3. mdToHtml Extracted (Frontend)
- `OptunaResults.tsx` was 408 lines after additions → extracted `mdToHtml` to `OptunaCharts.tsx`
- `OptunaResults.tsx`: 395 lines, `OptunaCharts.tsx`: 197 lines — both under 400

### 4. Progress Bar Backwards Jump Fix (Backend)
- CV model testing steps changed from `[12, 26, 40, 55, 70]` to `[12, 26, 40, 48, 55]`
- Optuna tuning now starts at 58% (was 65%) — no more backwards jump from 70→65
- Optuna range expanded: 58-80% (was 65-78%)
- nan guard in callback: shows `n/a` instead of `nan` if score is NaN

### 5. Granular Save Steps Fix (Backend)
- Old: single `p.update(93, "Saving model to disk…")` then long joblib.dump
- New: 92% → schema, 94% → pipeline, 97% → finalizing
- Prevents UI appearing frozen during large model serialization

### 6. Learning Curve Performance Fix (Backend)
- Both clf and reg: reduced train_sizes from 5 to 3: `[0.4, 0.7, 1.0]`
- Always 3 folds (was 5 for small datasets) — 9 fits total vs 25
- **Regression bug fixed**: was using full `X, y_enc` (no row cap) → switched to `X_cv, y_cv` (max 5000 rows)
- Secondary metric inside Optuna: reduced from 5-fold to 2-fold (display-only)

### 7. LLM Explanation Timeout (Backend)
- Added `timeout=45` to all OpenAI/Groq SDK clients
- Wrapped Anthropic SDK call in `ThreadPoolExecutor` with 45s timeout

### 8. NaN in SSE Payload Fix (Backend — `progress.py`)
- Root cause: `json.dumps({"value": float("nan")})` outputs `{"value": NaN}` — invalid JSON
- Browser's `JSON.parse` throws SyntaxError → frontend stuck at whatever % the final event was sent
- Fix: `_sanitize()` function in `progress.py` recursively replaces NaN/Inf with None and coerces numpy types before `json.dumps` on every SSE event
- Also filters NaN from `trial_history` and `secondary_trials` in `automl_helpers.py`

### 9. roc_auc Multiclass Fix (Backend — `automl_helpers.py`)
- Root cause: `scoring="roc_auc"` in sklearn only works for **binary** classification
- For multiclass, it raises `ValueError: multi_class must be in ('ovo', 'ovr')`
- StratifiedKFold already handles class balance — this was purely a scorer config bug
- Fix: detect binary vs multiclass at Optuna objective time:
  ```python
  scoring = "roc_auc" if len(np.unique(y_cv)) == 2 else "roc_auc_ovr"
  ```
- Matches how winner_metrics computes auc (binary: `proba[:, 1]`, multiclass: `multi_class="ovr"`)

---

## Bugs Investigated and Root Causes

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| 65% at Optuna trial 2/30 | CV steps went to 70%, then Optuna reset to 65% (backwards) | Capped CV steps at 55%, Optuna starts at 58% |
| Stuck at 93% | Single joblib.dump of large model with no intermediate updates | Split into 3 granular updates (92/94/97) |
| Stuck at 97% / "Finalizing" freeze | NaN float in SSE payload → `JSON.parse` throws → frontend never receives `done:true` | `_sanitize()` in progress.py |
| "All Optuna trials failed" error | All trials had NaN value → after NaN filter trial_history empty → RuntimeError | Better error message with guidance |
| roc_auc fails in Optuna tuning | `scoring="roc_auc"` is binary-only in sklearn; multiclass raises ValueError | Use `"roc_auc_ovr"` for multiclass |

---

## Key Insight: roc_auc Worked Before

User correctly noted roc_auc worked in Part 121 testing. Reason:
- **Winner metrics roc_auc**: computed once on test set after training — always worked
- **Optuna objective roc_auc**: used `scoring="roc_auc"` inside cross_val_score — only worked on binary datasets
- Part 121 test dataset was binary → no failure
- Current test dataset is multiclass → raises ValueError in every trial

---

## Commits

### ML-Unified (GitHub + HF Space)
| Hash | Description | HF |
|------|-------------|-----|
| `7fcd284` | fix(automl): progress bar backwards jump, stuck-at-93 granular saves | ✓ |
| `7cf31d4` | perf(automl): learning curve 9 fits, reg X_cv fix, secondary 2-fold, LLM timeout | ✓ |
| `17b1fb4` | fix(sse): NaN in payload breaks JSON.parse, freezing UI at 97% | ✓ |
| `58e117f` | fix(optuna): fake 0.0 score fallback (REVERTED — wrong approach) | ✗ |
| `30eea21` | fix(optuna): no fake scores, clear error message when all trials fail | ✗ |
| `731c8e7` | fix(optuna): use roc_auc_ovr for multiclass — roc_auc scorer is binary-only | pending |

### ml-portfolio (GitHub → Vercel)
| Hash | Description |
|------|-------------|
| `226ab42` | fix(optuna): clean metric display names, learning curve gap interpretation |

---

## Pending

### Immediate
- Upload `731c8e7` (`automl_helpers.py`) to HF Space (user interrupted upload)

### Optuna tool
- Learning curve gap overfitting warning (done in frontend, backend `[0.4, 0.7, 1.0]` now)

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
