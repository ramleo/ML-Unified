# Conversation — 2026-06-29 | Pipeline Cinema Bug Fixes | Part 131

## Session Overview

Continued from a compacted previous session. Focus: fixing multiple Pipeline Cinema bugs in ml-portfolio (Next.js), verified with Playwright using Titanic dataset.

---

## Commits This Session

| Hash | Message |
|---|---|
| `6decb64` | fix(pipeline-cinema): metric labels, winner logic, FS drops, FE demo, narrator on view |
| `cdc43cd` | fix(pipeline-cinema): badge overlap, 4-model list, neg_ metric labels |
| `6821b9b` | fix(pipeline-cinema): real AutoML data, winner crown, persistent stage viewer, frozen step |
| `ac24941` | fix(pipeline-cinema): orb alignment, fuzzy winner lookup, generic FE beams, stage navigation |

All frontend only — no HF Space upload required.

---

## Bugs Fixed

### 1. AutoML `[object Object] 0.0%` in narrator
- **Root cause**: `data.winner` from API is an object `{algo, score, metric}`, not a string. `data.scores` doesn't exist — it's `data.leaderboard[]`.
- **Fix**: Handle object shape in `callAutoML`; parse leaderboard array; filter out `-999` error sentinels.

### 2. Winner wrong for loss metrics
- **Root cause**: Backend uses max-score logic regardless of metric type. For `neg_mean_absolute_error`, higher value = worse MAE, not better.
- **Fix**: In `callAutoML`, after extracting winner from API, override with min-score model when `metric.startsWith("neg_")` or is `mae/mse/rmse`.

### 3. Metric label `neg_mean_absolute_error` showing raw
- **Root cause**: `AutoMLStory.tsx` had its own separate `metricLabel` mapping that wasn't updated (different from `pipelineCinemaApi.ts`).
- **Fix**: Updated both files. Added `neg_mean_absolute_error → MAE`, `neg_root_mean_squared_error → RMSE`, `neg_mean_squared_error → MSE`; fallback strips `neg_` and replaces `_`.

### 4. Metric label repeated on every model card
- **Fix**: Removed `metricLabel` from `ModelCard` props entirely. Added single `"scored by {metricLabel}"` subtitle line below "MODEL COMPETITION" header.

### 5. AutoML story shows empty / cards disappear (step cycling)
- **Root cause**: After pipeline finishes, clicking a stage pill set `activeStage` for only 1.5s. `AutoMLStory` starts at step 0 (no visible cards). By the time screenshot taken, step had cycled back to 0.
- **Fix**: 
  - `handleStageClick` (not-running path): sets `viewingStage` persistently (toggle), not just `activeStage` for 1.5s
  - `CinemaScene`: `active={activeStage !== null || viewingStage !== null}`; `frozen={viewingStage !== null && activeStage === null}`
  - `AutoMLStory`: added `frozen` prop — when true, locks step at 3 (winner state, all cards visible with crown)
  - When deactivated (`active=false`): resets to step 3 if `automlResults` exists, step 0 otherwise

### 6. FE stage shows "No new features added" with no animation
- **Root cause**: FE API config sends empty transforms `{}` → API returns `new_columns: []` → `engineeredCols = []` → story showed only text, no beams.
- **Fix**: When `engineeredCols` is defined but empty, use demo pill names (`Age_log1p`, `Age×Fare`, `Age², Pclass²`) so beams animate; show "No new features added." as a small note below pills at step 4 only. Hide `+{n} features` counter badge when `noNewFeatures=true`.

### 7. FS badge "6/6 features kept" overlapping scores
- **Fix**: Moved badge from `position: absolute, top: 8, right: 8` to `alignSelf: flex-end` rendered below the feature bars.

### 8. FS always shows 6/6 kept
- **Root cause**: Config sent `top_k: 10` but dataset had only 6 features → nothing dropped.
- **Fix**: Changed to `top_k: 4`. Note: backend variance method on Titanic still keeps many features (backend limitation).

### 9. AutoML model list — only RandomForest showing
- **Root cause**: Config sent `["RandomForest", "LogisticRegression"]`. LogisticRegression fails on regression tasks → score `-999` → filtered out → 1 model.
- **Fix**: Changed to `["RandomForest", "XGBoost", "LightGBM", "CatBoost"]` — 4 models, 2×2 grid. Any that fail on backend are silently filtered.

### 10. Narrator doesn't update when navigating to completed stage
- **Root cause**: `NarratorPanel` only received `activeStage` (null after 1.5s post-click). `viewingStage` was never passed.
- **Fix**: 
  - `CinemaScene`: pass `viewingStage` to `NarratorPanel`
  - `NarratorPanel`: `narrateStage = activeStage ?? viewingStage ?? null`; when `isViewing` (activeStage=null, viewingStage set), shows last line of that stage's `dynamicLines` or fallback `SCRIPTS`
  - Stage label (colored `● FEATURE ENGINEERING`) now uses `narrateStage` not `activeStage`

### 11. Orb misalignment
- **Root cause**: Formula `(i/(STAGES.length-1))*0.85+0.06` gave wrong X positions.
- **Fix**: `X_PERCENT_FOR_STAGE(stage)` returns hardcoded percentages `{preprocessing: 0.12, feature-eng: 0.37, feature-select: 0.63, automl: 0.88}` matching stage dot positions.

---

## Files Modified

| File | Changes |
|---|---|
| `src/lib/pipelineCinemaApi.ts` | leaderboard parsing, winner object shape, neg_ winner logic, top_k: 4, 4-model list, metric label map, neg_ fallback |
| `src/app/tools/pipeline-cinema/usePipelineRunner.ts` | handleStageClick sets viewingStage persistently; pause/stop/reset fixed |
| `src/components/pipeline-cinema/CinemaScene.tsx` | `active` includes viewingStage; `frozen` prop; viewingStage to NarratorPanel |
| `src/components/pipeline-cinema/stories/AutoMLStory.tsx` | frozen prop; step locks at 3 in viewer mode; metric label map updated; label moved to header |
| `src/components/pipeline-cinema/stories/FEStory.tsx` | empty engineeredCols → demo pills; hide +0 badge; desc hint when noNewFeatures |
| `src/components/pipeline-cinema/stories/FSStory.tsx` | badge moved below bars |
| `src/components/pipeline-cinema/stories/StageStory.tsx` | frozen prop forwarded to AutoMLStory |
| `src/components/pipeline-cinema/NarratorPanel.tsx` | viewingStage prop; narrateStage logic; stage label for viewing mode |

---

## Playwright Testing

- **Tool**: `mcp__playwright__browser_run_code_unsafe` with `setInputFiles(csvPath)` — the `browser_file_upload` MCP tool is broken for this project (returns `setFiles(undefined)`).
- **Dataset**: Titanic (`/Users/wrks/Downloads/Claude-documentation/Projects/ML-Titanic/data/Titanic-Dataset.csv`), target=Survived, Classification
- **Upload helper**: `upload_titanic.js` script using `page.locator('input[type="file"]').setInputFiles(csvPath)`

### Verified
- ✅ Preprocessing: real 891-row table, NaN red-highlighted, narrator narrates
- ✅ Feature Engineering: real Titanic source cols, demo beams animate, "No new features added." note
- ✅ Feature Selection: real cols, bars animate with threshold line, lower features dim
- ✅ AutoML: CatBoost 0.816 wins (F1, classification), all 4 model cards, crown correct, "scored by F1 score" once
- ✅ Narrator: "● AUTOML" label + last line shown when clicking completed AutoML pill

---

## Known Remaining Issues / Pending

- **FE**: Config always sends empty transforms → always `new_columns: []`. To show real engineered features, send `transforms: {"log1p": [...numericCols]}` dynamically.
- **FS**: Variance method on Titanic (many high-variance cols) keeps most features even with `top_k: 4`. Chi2 or mutual_info method would be more selective.
- **FSStory viewer mode**: Not frozen like AutoMLStory — steps still cycle when in viewer mode.
- **AutoMLStory DEMO_MODELS**: Still uses old `Logistic Reg.` in demo (no CSV case). Minor — won't show in normal use.

---

## Key Technical Reference

### Playwright file upload (working method)
```js
// In upload_titanic.js (place in project root or allowed path)
async (page) => {
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles('/path/to/file.csv');
  await page.waitForTimeout(800);
}
// Run with: mcp__playwright__browser_run_code_unsafe filename=upload_titanic.js
```

### AutoML API response shape (current backend)
```json
{
  "leaderboard": [{"algo": "RandomForest", "score": 0.816, "error": null}],
  "winner": {"algo": "CatBoost", "score": 0.816, "metric": "f1_weighted"},
  "model_id": "...",
  "rows": 712
}
```

### Winner override logic (frontend)
```typescript
// After extracting winner from API — override for loss metrics
if (metric.startsWith("neg_") || ["mae","mse","rmse"].includes(metric)) {
  const minEntry = Object.entries(scores).sort((a, b) => a[1] - b[1])[0];
  if (minEntry) { winner = minEntry[0]; winnerScore = minEntry[1]; }
}
```
</content>
</invoke>