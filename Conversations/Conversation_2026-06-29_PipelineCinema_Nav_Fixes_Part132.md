# Conversation — 2026-06-29 | Pipeline Cinema Polish + Nav Fixes | Part 132

## Session Overview

Continued from Part 131. Focus: Pipeline Cinema bug fixes (Model Competition duplication, FE demo pills, FS display), navigation fixes across all tool pages, and backlog review.

---

## Commits This Session

| Hash | Repo | Message |
|---|---|---|
| `7deb1b8` | ml-portfolio | fix(pipeline-cinema): lock AutoML at step 3 once results arrive; demo-only cycling |
| `32b34b9` | ml-portfolio | fix(pipeline-cinema): dynamic FE demo pills from real cols; fix AutoML double-header cycle |
| `05cfb27` | ml-portfolio | fix(tools): rename back-nav label from Portfolio to Home across all tool pages |
| `d96b604` | ml-portfolio | feat(pipeline-cinema): add Home nav link in header |
| `b49efc1` | ml-portfolio | fix(nav): Home button navigates to /#capabilities on all pages; add Home to pipeline-builder |
| `0f0efc3` | ml-portfolio | fix(pipeline-builder): add Home button to ModeSelector screen |
| `e40395a` | ml-portfolio | feat(pipeline-cinema): real FE log1p transforms; FS mutual_info; FSStory freeze on view |
| `dee161b` | ml-portfolio | fix(pipeline-cinema): show up to 17 FS bars; fix features_after narrator count; adaptive row height |

All frontend only — no HF Space upload required.

---

## Bugs Fixed

### 1. AutoML "MODEL COMPETITION" shown twice

**Root cause**: Step cycle ran `0→1→2→3→4→0`. At step 0, the "MODEL COMPETITION" header was visible but cards were hidden (opacity 0) — creating a 2-second blank flash every cycle. When cycling back from step 4→1, cards re-animated with staggered delays and crown disappeared then reappeared, making the whole sequence look like it played twice.

**Fix (first attempt)**: Changed cycle to `1→2→3→4→1` (skip step 0). Partially fixed the flash but re-animation on 4→1 still showed twice.

**Fix (correct)**: Once `automlResults` is set (real data from API), lock step at 3 permanently. Only cycle in demo mode (no CSV). Effect:
```typescript
if (frozen || automlResults) { if (step !== 3) setStep(3); return; }
```

### 2. FE demo pills show Titanic column names on other datasets

**Root cause**: Demo pills hardcoded as `["Age_log1p", "Age×Fare", "Age², Pclass²"]` regardless of dataset.

**Fix**: Generate demo pills dynamically from `displaySource` columns using numeric-sounding regex:
```typescript
const numericLike = displaySource.filter(c =>
  /age|fare|income|amount|price|year|count|num|score|salary/i.test(c)
);
const col1 = numericLike[0] ?? displaySource[0] ?? "Feature1";
const col2 = numericLike[1] ?? displaySource[1] ?? displaySource[0] ?? "Feature2";
const col3 = displaySource[2] ?? displaySource[1] ?? col1;
displayEngineered = [`${col1}_log1p`, `${col1}×${col2}`, `${col1}², ${col3}²`];
```
Applied in both branches (empty engineeredCols + no CSV).

### 3. FS showing "6/6 features kept" when narrator says "15 features"

**Root cause**: Display hard-capped at `kept.slice(0, 6)` — only 6 bars shown regardless of how many features the API returned.

**Fix**: Increased cap to `kept.slice(0, 12)` + `dropped.slice(0, 5)` = max 17 total bars. Score step changed from `0.07` to `0.05` to spread values across more items. Adaptive row height: 16px when >10 features, 22px otherwise.

### 4. FS narrator says wrong feature count

**Root cause**: Narrator used `data.features_after` (includes target column) → said "Keeping 16" when actual was 15 features.

**Fix**: Changed to `data.features_after - 1`.

### 5. FSStory doesn't freeze when viewing completed stage

**Root cause**: FSStory had no `frozen` prop, unlike AutoMLStory.

**Fix**: Added `frozen?: boolean` to FSStory Props. When `!active && keptCols` set → stay at step 3 (not reset to 0). When `frozen` → lock at step 3. Forwarded `frozen` from StageStory.

### 6. FE always shows demo pills (no real engineered features)

**Root cause**: API config sent `{ transforms: {}, poly_cols: [], interactions: [] }` — empty transforms → API returns `new_columns: []`.

**Fix**: `callFeatureEng` now accepts optional `columns?: string[]`. Builds real config:
```typescript
const logCols = numericLike.length > 0 ? numericLike : nonTarget.slice(0, 3);
config: { transforms: { log1p: logCols }, poly_cols: polyCols, interactions: interactionPairs }
```
Call site in `usePipelineRunner.ts` passes `parseCsvHeader(currentCsv)`.

### 7. FS keeps all features (top_k not working)

**Root cause**: `method: "variance"` doesn't rank by predictive power — on high-variance datasets (Titanic, Cereal) it kept all features even with `top_k: 4`.

**Fix**: Changed to `method: "mutual_info"` which scores features by actual predictive power relative to the target. Also updated narrator line from "variance thresholding" to "mutual information scoring".

### 8. "Portfolio" back-nav label on all tool pages

**Fix**: Renamed to "Home" across all 7 tool pages (ensemble, shap, automl, optuna, feature-engineering, feature-selection, preprocessing) using `sed`.

### 9. Pipeline Cinema "Home" button went to `/` (top of page)

**Root cause**: Used `Link href="/"` instead of `router.push("/#capabilities")`.

**Fix**: Added `useRouter`, `handleHome = () => router.push("/#capabilities")`, replaced Link with button.

### 10. No Home option in Pipeline Builder

**Fix (mode selected)**: Added Home button before "Back" in sticky header.

**Fix (ModeSelector screen)**: Added Home button in top-left of the mode selection screen (separate early-return branch).

---

## Files Modified

| File | Changes |
|---|---|
| `src/components/pipeline-cinema/stories/AutoMLStory.tsx` | Lock at step 3 when automlResults set; demo-only cycling |
| `src/components/pipeline-cinema/stories/FEStory.tsx` | Dynamic demo pills from real source cols (both branches) |
| `src/components/pipeline-cinema/stories/FSStory.tsx` | frozen prop; step 3 preserve; adaptive row height; cap 17 bars |
| `src/components/pipeline-cinema/stories/StageStory.tsx` | Forward frozen to FSStory |
| `src/lib/pipelineCinemaApi.ts` | Real FE log1p transforms; mutual_info FS; features_after-1 narrator; dynamic column detection |
| `src/app/tools/pipeline-cinema/usePipelineRunner.ts` | Pass parseCsvHeader(currentCsv) to callFeatureEng |
| `src/app/tools/pipeline-cinema/page.tsx` | useRouter + handleHome → /#capabilities; "← Home" button |
| `src/app/tools/pipeline-builder/page.tsx` | useRouter + handleHome; Home button in header + ModeSelector screen |
| `src/app/tools/ensemble/page.tsx` | "Portfolio" → "Home" |
| `src/app/tools/shap/page.tsx` | "Portfolio" → "Home" |
| `src/app/tools/automl/page.tsx` | "Portfolio" → "Home" |
| `src/app/tools/optuna/page.tsx` | "Portfolio" → "Home" |
| `src/app/tools/feature-engineering/page.tsx` | "Portfolio" → "Home" |
| `src/app/tools/feature-selection/page.tsx` | "Portfolio" → "Home" |
| `src/app/tools/preprocessing/page.tsx` | "Portfolio" → "Home" |

---

## Backlog Review — #21 Context Wiring

Reviewed pending item #21: "6 tools still standalone — don't write back to PipelineContext".

**What already works:**
- `PipelineContext` + `MLPipelineState` in `src/context/PipelineContext.tsx` with localStorage persistence
- `AutoMLModal` writes `automlWinner` + `automlRanking` to context after training

**What's missing:**

| Page | File | Lines | Action |
|---|---|---|---|
| Optuna | `src/app/tools/optuna/OptunaRunner.tsx` | — | Wrap in `PipelineProvider`; read `automlWinner` → pre-select model; write `tunedModel` |
| SHAP | `src/app/tools/shap/page.tsx` | 66 | Wrap in `PipelineProvider`; read `automlWinner`; write `shapValues` |
| Ensemble | `src/app/tools/ensemble/page.tsx` | 55 | Wrap in `PipelineProvider`; read `automlRanking`; write `ensembleType` + `ensembleScore` |
| Preprocessing | `src/app/tools/preprocessing/page.tsx` | 297 | Write `preprocessingConfig` (lower priority) |
| Feature Engineering | `src/app/tools/feature-engineering/page.tsx` | 269 | Write `transforms` (lower priority) |
| Feature Selection | `src/app/tools/feature-selection/page.tsx` | **381** | ⚠️ Modularize first (>350 lines), then wire |

**Priority**: Optuna → SHAP → Ensemble (AutoML winner auto-fills downstream) → Preprocessing → FE → FS

**Key constraint**: `csv` and `cleanedCsv` excluded from localStorage — user must re-upload CSV on each page. Context carries config + scores + column lists only.

Detail added to `pending.md` under #21.

---

## Known Remaining Issues

- FS `mutual_info` + `top_k: 4` still keeping all features on Cereal dataset (backend may not fully respect top_k with mutual_info for mixed categorical/numeric datasets)
- FE: Cereal dataset has many cols — verify log1p actually creates new columns in API response
- AutoMLStory DEMO_MODELS still has "Logistic Reg." (no CSV case — minor, not shown in normal use)
