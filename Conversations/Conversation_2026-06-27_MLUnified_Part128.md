# Conversation_2026-06-27_MLUnified_Part128

Continuation from Part 127.

---

## Pipeline Builder — UI Improvements + Bug Fixes

### Commits This Session

#### ml-portfolio (frontend)

| Commit | Description |
|---|---|
| `3f3fe98` | feat(pipeline-builder): animated waterfall — count-up numbers, staggered entrance, arrival glow, combined row·col label |
| `733c9fe` | fix(pipeline-builder): clean metric names (MAE/RMSE), before→after row/col labels, suppress 0-stats |
| `3b222c2` | feat(pipeline-builder): typewriter header, accent underline, before→after labels, count-up + glow animations |
| `94fc785` | fix(pipeline-builder): show 'no change' instead of dash for FE/FS with no stats |
| `2843499` | feat(pipeline-builder): custom target dropdown (opens down) + hover tooltips on waterfall rows |
| `f3b4986` | fix(pipeline-builder): show plain 'No change' when shape unchanged; tooltip opens below right label |
| `88f7ac0` | fix(pipeline-builder): SHAP key fix, Optuna regression score, Ensemble response key |
| `589f589` | feat(pipeline-builder): pulse glow on waterfall container when new stage row arrives |

#### ML-Unified (backend)

| Commit | Description |
|---|---|
| `c02f2ff` | fix(pipeline-builder): Optuna double-negation, Ensemble score key + robustness |

HF Space uploaded: `automl_stage.py` → `routers/pipeline_builder/automl_stage.py`

---

## Features Implemented

### Waterfall Chart (WaterfallChart.tsx)
- **Typewriter effect**: "STAGE IMPACT" types character-by-character (45ms/char) with blinking cursor
- **Accent underline**: gradient line sweeps in after typing completes
- **Staggered row entrance**: each row slides in from left with index-based delay
- **Count-up numbers**: row/col counts animate 0 → N with ease-out cubic
- **Arrival glow flash**: bar track flashes accent color on entry then fades
- **Container pulse**: when a new stage row arrives (not on initial mount), container border glows cyan + inset shadow for 900ms
- **Label format**: `No change` (italic, muted) when shape unchanged; `{before} → {after} rows (±N)` in accent color when changed
- **Metric names**: `neg_mean_absolute_error` → `MAE`, `neg_root_mean_squared_error` → `RMSE`, `r2` → `R²` etc.
- **OUTPUT column header**: tiny muted label aligned right above value column
- **Hover tooltips**: each row shows tooltip below-right explaining what the stage did

### Custom Target Dropdown (page.tsx)
- Replaced native `<select>` (opens upward due to browser space detection) with custom `TargetDropdown` component
- Always opens downward, max-height 200px scrollable, closes on outside click
- Selected option highlighted in green (#4ade80) with checkmark

### Bug Fixes

#### SHAP shows nothing
- Backend `/shap` returns `feature_importance` (list of `{feature, importance}`)
- StageModal was reading `d.shap_values` (wrong key) → fixed to read `d.feature_importance`

#### Optuna large negative number for regression
- **Backend bug**: `score_after = -score_after` was applied after `study.best_value` was already the positive MAE → double negation
- **Frontend bug**: `(score_after - score_before) * 10000 / 100` amplified the already wrong sign
- Fix: backend removes negation; backend returns correct `improvement`; frontend uses `d.improvement` directly
- Classification: `improvement * 10000 / 100` (converts F1 delta to percentage)
- Regression: `improvement * 100 / 100` (keeps MAE delta in raw units)

#### Ensemble API error 500
- Backend returned key `"score"` but StageModal read `d.ensemble_score` → renamed to `"ensemble_score"`
- Backend now skips models that scored -999 (failed individually) from the ensemble
- Nested try/except: soft voting → hard voting → HTTPException for classification; try/except for regression

#### Zero stats (FE/FS showing "0 cols")
- `page.tsx`: FE/FS only pass `colsBefore/colsAfter` to waterfall when `cb > 0 || ca > 0`
- Otherwise returns bare stage entry → waterfall shows "No change"

---

## Architecture Notes

### Preprocessing "no change" for Titanic
Expected behavior: Express mode uses `mv_num: "median"`, `mv_cat: "most_frequent"` (imputation). Imputation fills NaN in-place — rows are NOT dropped. Row and column shape stays the same. "No change" is correct. Row removal only happens with `remove_outliers: true`.

### Tooltip position
Tooltip opens below-right of each waterfall row (`top: calc(100% + 6px)`, `right: 0`) — aligns under the label text where the user is hovering.

### Framer-motion hooks order
WaterfallChart had hooks declared after the `if (!stages.length) return null` early return — technically a hooks violation. Moved all hook declarations above the early return to comply with Rules of Hooks.

---

## File Line Counts (end of session)

| File | Lines |
|---|---|
| `pipeline-types.ts` | 14 |
| `WaterfallChart.tsx` | ~200 |
| `StageGrid.tsx` | 228 |
| `StageCard.tsx` | 397 |
| `StageModal.tsx` | 315 |
| `page.tsx` | ~400 |
| `automl_stage.py` | ~349 |

---

## Pending

1. **FE/FS stats not showing** — backend returns stats (cols_before/after) for FE and FS but they show "No change" because the pipeline runs with default config (no transforms/selections that actually change columns). Need to verify with a dataset where FE adds columns or FS removes some.
2. **Preprocessing "no change" context** — add tooltip explaining imputation preserved row count
3. **#23 Drift Detection v2**
4. **#24 RAG AI explanation**
5. **#25 Ensemble/stacking backend**
6. **#33 Categorical frequencies in schema JSON**
7. **#39-44 MLOps items**
8. **#45 E2E Playwright CI**
9. **#47 Dockerize ml-eda + ml-vision**
10. **#50 Batch predictions**
11. **TC-PEND: 47 open TCs**
