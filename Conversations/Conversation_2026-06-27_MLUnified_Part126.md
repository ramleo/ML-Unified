# Conversation_2026-06-27_MLUnified_Part126

Continuation from Part 125.

---

## Pipeline Builder — Complete Rebuild

### Background / Decision

User investigated #19–22 (Pipeline Builder). Concluded the original canvas was redundant with ML Unified's AutoML wizard. After discussion, decided to rebuild it as a genuinely different product with:

- **3 modes**: Guided (one stage at a time), Express (auto-run all stages with defaults), A/B Compare (two pipeline configs side by side)
- **Stage-by-stage impact visualization** (waterfall chart)
- **Python code export** (generates sklearn Pipeline code)
- **A/B pipeline comparison** (runs two configs, compares scores)
- **Cinematic Framer Motion animations** (spring entrance, status transitions, circuit board SVG overlay)
- **Stateless backend** (browser holds CSV, sends with each request — no session management, no HF Space sleep issue)

### Architecture

- Browser sends `csv_b64` (base64 CSV) + config with each stage request
- Each stage returns `processed_csv_b64` (output CSV passed to next stage)
- Model ID stored in MODELS dict (in-memory) for Optuna/SHAP after AutoML
- 9 synchronous (non-SSE) endpoints under `/pipeline-builder/`

---

## Backend Changes (ML-Unified)

### New package: `services/ml-api/routers/pipeline_builder/`

| File | Lines | Endpoints |
|---|---|---|
| `__init__.py` | 13 | assembles sub-routers |
| `stages.py` | 353 | `/preprocess`, `/feature-eng`, `/feature-select` |
| `automl_stage.py` | 348 | `/automl`, `/optuna`, `/shap`, `/ensemble` |
| `export.py` | 201 | `/export-code` |
| `comparison.py` | 222 | `/compare` |

`app.py` updated to register `_pb_router`.

**Commit:** `d425459` — all 6 files uploaded to HF Space

---

## Frontend Changes (ml-portfolio)

### New directory: `src/components/pipeline/`

| File | Lines | Purpose |
|---|---|---|
| `ModeSelector.tsx` | 246 | 3-mode picker with stagger animation |
| `StageCard.tsx` | 398 | 5 statuses, spring animations |
| `CircuitBoard.tsx` | 167 | SVG bezier overlay with animated glow dots |
| `StageModal.tsx` | 311 | config+results panel, API calls |
| `StageConfigForms.tsx` | 302 | per-stage config forms |
| `FormHelpers.tsx` | 137 | shared form primitives |
| `WaterfallChart.tsx` | 135 | animated stage impact bars |
| `CodeExportModal.tsx` | 225 | copy/download pipeline.py |
| `ComparisonPanel.tsx` | 297 | A/B score count-up |
| `StageGrid.tsx` | 109 | extracted grid layout |
| `ABPanel.tsx` | 100 | A/B column layout |
| `FileUploadSection.tsx` | 68 | drag-drop CSV uploader |

`src/app/tools/pipeline-builder/page.tsx` — full rebuild (281 lines)
`src/components/PipelineCard.tsx` — deleted

**Commits:** `280612a` (rebuild), `c2d52ca` (TypeScript fixes)

---

## Bugs Found and Fixed (this session, Part 126)

### Bug 1: API error 400 — config key name mismatch

**Root cause:** `StageConfigForms.tsx` used different key names than backend expects:
- `numeric_impute` → should be `mv_num`
- `cat_impute` → should be `mv_cat`
- `fix_skew` → should be `fix_skewness`
- `drop_columns` → should be `drop_cols`
- `cv_folds` → should be `n_folds`

**Fix:** Updated all key names in `StageConfigForms.tsx`

### Bug 2: Drop columns showing no columns

**Root cause:** `FileUploadSection.tsx` always called `onFile(b64, [])` — empty columns array. The page then tried to call `/analyze` endpoint with JSON body, but `/analyze` expects multipart form data → silent failure → columns always empty → target always "" → backend raises 400 "Target column '' not found"

**Fix:** Parse CSV header client-side in `FileUploadSection.tsx`:
```tsx
const decoded = atob(b64);
const firstLine = decoded.split("\n")[0] ?? "";
const cols = firstLine.split(",").map(c => c.trim().replace(/^"|"$/g, "")).filter(Boolean);
onFile(b64, cols);
```
Also updated `handleFile` in `page.tsx` to accept `(b64: string, cols: string[])` — no longer calls `/analyze`.

### Bug 3: Express = Guided (no difference)

**Root cause:** `page.tsx` rendered identical grid for both modes.

**Fix:** Added Express mode banner + "Auto-Run Pipeline" button that runs stages 1–4 (preprocessing/FE/FS/AutoML) sequentially with default configs:
```tsx
async function runExpressPipeline() { ... }
```
Also added `setRunningStage` setter (was missing).

### Bug 4: outputCsvB64 wrong field name

**Root cause:** `StageModal.tsx` read `json.output_csv_b64` but backend returns `json.processed_csv_b64`.

**Fix:** `json.processed_csv_b64 as string | undefined`

### Bug 5: Optuna/SHAP model_id from wrong result

**Root cause:** `buildBody` read `model_id` from `existingResult` (the optuna stage's own previous result = null first time) instead of from the AutoML stage result.

**Fix:** Added `modelId?: string` prop to `StageModal`; page passes `stageResults["automl"]?.data?.model_id`; `buildBody` now accepts separate `modelId` param.

### Bug 6: task_type not sent for AutoML/Ensemble

**Root cause:** `buildBody` only sent `{ csv_b64, target, config }` for automl/ensemble, but backend requires `task_type` at top level.

**Fix:** Added `if (stageId === "automl") return { ...base, task_type: taskType }` in `buildBody`.

---

## Pending (TypeScript check)

TypeScript check (`tsc --noEmit`) not yet run — user asked to save conversation first. Run this next session to verify zero errors.

---

## Commits

### ML-Unified
| Hash | Description | HF |
|---|---|---|
| `d425459` | feat(pipeline-builder): add /pipeline-builder/* endpoints | ✓ |

### ml-portfolio
| Hash | Description |
|---|---|
| `280612a` | feat(pipeline-builder): cinematic rebuild — 3 modes, Framer Motion animations |
| `c2d52ca` | fix(pipeline-builder): resolve all TypeScript errors post-rebuild |

Bug fixes from Part 126 not yet committed — need to commit after TypeScript check passes.

---

## Key Technical Notes

1. **Stateless pipeline**: Browser maintains chain of CSVs (raw → preprocessed → FE → FS). Each stage gets the previous stage's output CSV via `getStageCsv()`.
2. **Express auto-run**: Stages 1–4 run sequentially with hardcoded optimal defaults. Optuna/SHAP/Ensemble still require manual trigger.
3. **A/B compare**: Calls `/pipeline-builder/compare` which runs both full pipelines server-side and returns winner.
4. **modelId chain**: AutoML stage stores model in MODELS dict with `pb_{uuid}` key → returns model_id → page passes to StageModal as `modelId` prop → Optuna/SHAP use it.
