# Conversation_2026-06-27_MLUnified_Part125

Continuation from Part 124.

---

## Fixes Implemented

### 1. Drop columns stale closure fix (commit `bf18d8e`, ml-portfolio)
- **Root cause**: `handleTrain` useCallback dep array `[file, target, taskType, modelName, selectedModels]` was missing `dropCols`, `colEncodings`, `useSMOTE` — stale closure always sent `drop_cols_json=[]`
- **Fix**: Added missing deps to useCallback dependency array

### 2. FrequencyEncoder pickle error (commit `bad87c0`, ML-Unified + HF)
- **Root cause**: `_FreqEnc` was a local class inside `build_cat_transformers` — Python pickle can't serialize local/nested classes (no stable import path)
- **Fix**: Promoted to module-level `FrequencyEncoder` class with numpy/sklearn imports at top of `automl_preprocess_helpers.py`

### 3. Error state persisting across wizard steps (commit `60ad41b`, ml-portfolio)
- **Root cause**: `onBack` only called `setStep("upload")`, never cleared `error` state
- **Fix**: `onBack={() => { setStep("upload"); setError(""); }}`

### 4. n_trials cap raised 50 → 200 (commits `885e35e` ML-Unified, `e1f02ea` + `3fb72f9` ml-portfolio)
- Backend: `max(5, min(200, n_trials))`
- Frontend slider: `max={200}`, label `<span>200</span>`

### 5. Floppy disk emoji → SVG in DatasetEstimator (commit `3d11b0f`, ml-portfolio)
- Replaced `💾` with inline SVG disk icon at lines 81 and 141

### 6. Pipeline Builder — Visual Card Canvas (commits `66e8c16`, `3d11b0f`, `db88588`, ml-portfolio)
- **New files**:
  - `src/context/PipelineContext.tsx` — added localStorage persistence (excludes File objects)
  - `src/components/PipelineCard.tsx` — locked/ready/done states, accent glow, SVG icons, metric line
  - `src/app/tools/pipeline-builder/page.tsx` — 7-card canvas, progress bar, reset button
- **Updated**: `src/data/capabilities.ts` — added Pipeline Builder entry with `internalLink: "/tools/pipeline-builder"`
- **Card states**: locked (deps not met) / ready / done (shows metric)
- **Dependency logic**: optuna/shap/ensemble locked until `automlWinner != null`
- **SVG icons**: filter lines, sun/gear, crosshair, chip, grid, bar chart, star — no emojis

### 7. Emoji → SVG fix in pipeline cards (commit `db88588`)
- All 7 card icons replaced with inline SVGs in `ICONS` map

---

## Test Cases Written (4 agents in parallel)

| File | Parts | TCs |
|------|-------|-----|
| TC-P3.md | 34–50 | 150 |
| TC-P5.md | 66–90 | 72 |
| TC-P6.md | 91–110 | 64 |
| TC-P7.md | 111–124 | 52 |
| **Total new** | | **338** |

Master index `Conversations/testcases.md` updated — 13 files, ~930 total TCs.

---

## Commits

### ML-Unified (backend, GitHub + HF Space)
| Hash | Description | HF |
|------|-------------|-----|
| `bad87c0` | fix(automl): FrequencyEncoder to module level — local class can't be pickled | ✓ |
| `885e35e` | feat(automl): raise n_trials cap from 50 to 200 | ✓ |

### ml-portfolio (frontend → Vercel)
| Hash | Description |
|------|-------------|
| `bf18d8e` | fix(automl): stale closure — dropCols/colEncodings/useSMOTE missing from handleTrain deps |
| `60ad41b` | fix(automl): clear error when navigating back to upload step |
| `e1f02ea` | feat(optuna): raise slider max from 100 to 200 trials |
| `3fb72f9` | fix(optuna): update hardcoded max label from 100 to 200 |
| `66e8c16` | feat(pipeline): add visual card canvas builder at /tools/pipeline-builder |
| `3d11b0f` | feat(pipeline): add Pipeline Builder to capabilities; floppy emoji → SVG |
| `db88588` | fix(pipeline): replace emoji icons with inline SVGs in pipeline builder cards |

---

## Key Technical Lessons

1. **useCallback stale closures**: Any state used inside a callback must be in the dependency array — missing deps silently capture the initial value forever.
2. **Python pickle + local classes**: Classes defined inside functions cannot be pickled — always define custom sklearn transformers at module level.
3. **No emojis**: Always use inline SVG icons, never emoji characters. User has corrected this multiple times.

---

## Pending Backlog (updated)
- **#19–22 Pipeline Builder** ✅ Done (canvas built; only AutoML writes back to context; remaining tools are standalone)
- #23 Drift detection v2
- #24 RAG AI
- #25 Ensemble/stacking backend
- #27 Per-column encoding ✅ Done (this session)
- #33 Categorical frequencies in schema JSON
- #39–44 MLOps items
- #45 E2E Playwright CI
- #47 Dockerize ml-eda + ml-vision
- #50 Batch predictions
- Wire remaining 6 tool modals to write back to PipelineContext (Optuna, SHAP, Ensemble, Preprocessing, FE, FS)
- TC-PEND: 47 open TCs — close as backlog features land
