# Conversation_2026-06-27_MLUnified_Part129

Continuation from Part 128.

---

## Pipeline Builder — Ensemble Fix, Express Animation, Score Gap Analysis & Fixes

### Commits This Session

#### ML-Unified (backend)

| Commit | Description |
|---|---|
| `7c3dca1` | fix(pipeline-builder): preprocess X once before VotingRegressor — Pipeline sub-estimators not recognized as regressors by sklearn |
| `ce0038e` | fix(ensemble): replace VotingClassifier/VotingRegressor with manual cross_val_predict averaging |
| `9a9ad5d` | feat(ensemble): implement stacking (OOF meta-features + LogisticRegression/Ridge meta-model); fix ensemble_type field mismatch; replace VotingClassifier/VotingRegressor with manual cross_val_predict averaging |
| `41f241f` | fix(pipeline-builder): preserve categorical dtypes through FS; add row sampling cap (15K AutoML/Ensemble, 10K Optuna); skip FS pass-through on method=none |

HF Space uploaded: `automl_stage.py`, `automl_preprocess_helpers.py`

#### ml-portfolio (frontend)

| Commit | Description |
|---|---|
| `ef0d603` | feat(pipeline-builder): Express mode running animation — stage nodes with pulse ring, traveling beam connector, scan-line sweep |
| `a19d0d4` | fix(pipeline-builder): clear results on Remove + Express re-run; skip FS in Express; show sampling note in AutoML waterfall tooltip |

---

## Ensemble Fix — Root Cause Analysis

### Error 1: "Pipeline should be a regressor"
Old code wrapped each estimator in `Pipeline([("pre", preprocessor), ("est", estimator)])` and passed pipelines to `VotingRegressor`. sklearn's `_validate_estimators()` calls `is_regressor(est)` which checks `_estimator_type`. The `Pipeline` class didn't pass this check on HF Space's sklearn version.

**Attempted fix**: preprocess X once with `fit_transform`, pass plain estimators to `VotingRegressor`.

### Error 2: "XGBRegressor should be a regressor"
Even plain `XGBRegressor` failed `is_regressor()` on HF Space's sklearn build — XGBoost/LightGBM/CatBoost don't expose `_estimator_type = "regressor"` in that version.

**Real fix**: Removed `VotingClassifier`/`VotingRegressor` entirely. Implemented manual ensemble using `cross_val_predict`:

**Voting**: average OOF predictions across all models:
- Classification: average `predict_proba` → argmax (fallback to majority vote hardcoded)
- Regression: average `predict` → score with MAE

**Stacking**: OOF meta-features → meta-model:
- Level 0: for each fold, train base models on train set, predict val set → meta-feature matrix (n_samples × n_models)
- Level 1: LogisticRegression (classification) or Ridge (regression) on meta-features, scored via 3-fold CV

### Bug: Frontend sends `ensemble_type`, backend had field `type`
`EnsembleConfig` had `type: str = "voting"`. Pydantic silently ignored unknown field `ensemble_type` from frontend, always defaulting to "voting". Fixed by renaming to `ensemble_type`.

---

## Express Mode Running Animation — `ExpressRunner.tsx`

New component at `src/components/pipeline/ExpressRunner.tsx`:

- Appears below Express banner when `runningStage !== null`, slides in/out with AnimatePresence
- 4 stage nodes: Preprocess → Feature Eng → Feature Select → AutoML, each with its own accent color
- **Running node**: pulsing ring radiating outward (`scale: [1, 2], opacity: [0.5, 0]`), inner dot breathing (`scale: [0.4, 0.9, 0.4]`), node glows with `boxShadow`
- **Connector lines**: traveling beam on active connector (`x: ["-100%", "100%"]`); fills solid when stage completes (`width: 0 → 100%`)
- **Done nodes**: filled circle with checkmark SVG
- **Scan-line**: cyan gradient sweep across entire panel (`x: ["-120%", "120%"]`, 2.4s linear repeat)
- Imported in `page.tsx` with `<ExpressRunner runningStage={runningStage} completedStages={completedStages} />`

---

## Score Gap Analysis: AutoML Pipeline (82.68%) vs Pipeline Builder (72%)

### Root causes identified:

**1. Categorical dtype corruption through Feature Selection**

`apply_feature_selection` was dropping ALL non-numeric columns before selection (line 182-184):
```python
leftover_non_num = df_feat.select_dtypes(exclude="number").columns.tolist()
if leftover_non_num:
    df_feat = df_feat.drop(columns=leftover_non_num)  # ← dropped Sex, Embarked
```

Result: `Sex`, `Embarked` removed from CSV before AutoML. AutoML's `_build_preprocessor` received all-numeric data → `cat_cols = []` → OrdinalEncoder never ran → StandardScaler ran on what used to be `[0, 1]` binary categories → corrupted signal.

**Fix**: Rewritten `apply_feature_selection` separates `cat_cols` upfront, runs selection only on numeric columns, recombines at the end:
```python
cat_cols = df_feat.select_dtypes(exclude="number").columns.tolist()
num_X = df_feat.select_dtypes(include="number").fillna(0)
# ... selection on num_X only ...
return df_feat[selected + cat_cols]  # preserve categorical dtypes
```

**2. Feature Selection in Express mode dropping/distorting features**

`top_k=15` with `method="kbest"` on Titanic (7 cols) passes all through but still causes internal distortion. On datasets >15 cols, it actively drops features that chi²/mutual_info might underrank but tree models would use.

**Fix**: Express default changed to `method: "none"` — FS is a pure pass-through in Express mode. Let AutoML see all columns.

**3. Why scaling doesn't cause the gap (tree models are scale-invariant)**

All 4 AutoML models (RF, XGB, LGBM, CatBoost) split on thresholds — `Age = 35` and `Age = 0.40` (scaled) produce the same optimal split. StandardScaler running twice (once from chained stages, once in AutoML internal preprocessor) doesn't affect tree model scores. This is NOT the cause of the gap.

---

## Row Sampling — Compute Cap

New `_maybe_sample` helper in `automl_stage.py`:

```python
def _maybe_sample(X: pd.DataFrame, y: np.ndarray, cap: int, task: str):
    if len(X) <= cap:
        return X, y, 0
    from sklearn.utils import resample
    stratify = y if task == "classification" else None
    try:
        Xs, ys = resample(X, y, n_samples=cap, stratify=stratify, random_state=42, replace=False)
    except Exception:
        Xs, ys = resample(X, y, n_samples=cap, random_state=42, replace=False)
    return Xs, ys, len(X)
```

Caps:
- AutoML: 15,000 rows (20 fits × ~2-3s each = ~1-2 min max)
- Optuna: 10,000 rows (many trials)
- Ensemble: 15,000 rows

AutoML returns `sampled_from: int | null` in response. Frontend waterfall tooltip shows "sampled 15K/80K rows" when triggered.

Performance envelope on HF Space free tier (2 CPU):
- <5K rows: fine
- 10K-50K rows: would have timed out, now capped at 15K → completes
- >100K rows: previously dead, now safe

---

## Animation Bug Fix — ExpressRunner Not Animating on Re-run

**Root cause**: "Remove" button only cleared `csvB64` and `columns`:
```tsx
onClick={() => { setCsvB64(null); setColumns([]); }}
```
`stageResults` persisted → `completedStages` had all 4 stages from previous run → ExpressRunner saw every node as `isDone = true` immediately when new run started → no animations.

**Fix**: Two changes:
1. `runExpressPipeline` clears state at start: `setStageResults({}); setStageCsvs({});`
2. Remove button also clears: `setStageResults({}); setStageCsvs({});`

---

## Architecture Notes

### Why `skip_preprocessing` in AutoML would break future non-tree models

Tree models (RF, XGB, LGBM, CatBoost) are scale-invariant — scaling doesn't affect them.
Distance/linear models (SVM, KNN, LogisticRegression) require scaling:
- SVM RBF kernel: without scaling, `Fare` (0-512) dominates `Age` (0-80) in distance by 44521:169 ratio
- KNN: meaningless on unscaled mixed-range data
- LogisticRegression: convergence failure without scaling

Decision: Always keep `_build_preprocessor()` in AutoML. Fix the INPUT data (categorical dtype preservation) rather than skipping internal preprocessing. This is safe for all model types now and in the future.

---

## File Line Counts (end of session)

| File | Lines |
|---|---|
| `automl_preprocess_helpers.py` | 224 |
| `automl_stage.py` | 400 |
| `stages.py` | 369 |
| `ExpressRunner.tsx` | 130 |
| `page.tsx` | ~406 |

⚠️ `page.tsx` is slightly over 400 — monitor for next session.

---

## Pending

1. **Score gap may still exist** — need to test Express mode after fixes to see if scores align better with standalone AutoML Pipeline
2. **#23 Drift Detection v2**
3. **#24 RAG AI explanation**
4. **#25 Ensemble/stacking backend** (now implemented — stacking via OOF + meta-model)
5. **#33 Categorical frequencies in schema JSON**
6. **#39-44 MLOps items**
7. **#45 E2E Playwright CI**
8. **#47 Dockerize ml-eda + ml-vision**
9. **#50 Batch predictions**
10. **TC-PEND: 47 open TCs**
11. **page.tsx approaching 400 lines** — consider splitting before next feature
