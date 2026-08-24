# Conversation — 2026-06-22 — ML-Unified Part 114

## Context
Continuation of Part 113. Work spans ml-portfolio (Next.js frontend) and ML-Unified backend.

---

## Session Summary

### Preprocessing Configure Panel — Scroll Fix

**Problem:** Right panel showed only 2 of 4 toggles (Fix Skewness + Standardize cut off). Root cause: `DatasetOverview` defaulted to `open = true`, consuming most of the 530px viewport.

**Fix journey:**
1. Tried collapsing DatasetOverview by default (`open = false`) → toggles visible but graphs gone
2. Tried sticky bottom section (toggles always visible) → user rejected MouseTiltCard on toggles
3. User clarified: wants scrollable panel, graphs visible when expanded, toggles reachable by scrolling
4. Final fix: single scrollable right panel + removed MouseTiltCard from toggle card + DatasetOverview `open = true`

**Commits:**
- `f1e443b` — minHeight:0 on content div + DatasetOverview collapsed (later reverted open state)
- `701288c` — scrollable right panel, DatasetOverview open by default, remove MouseTiltCard from toggles

---

### DatasetEstimator Changes (7 agreed items)

All 5 active items implemented via subagent:

| Item | Status |
|------|--------|
| Remove `navigator.deviceMemory` RAM display | ✅ Done |
| Add Recommended RAM (peak memory × 3) | ✅ Done |
| AutoML: remove "All rows processed" note from upload step | ✅ Done |
| AutoML: add DatasetEstimator to config step | ✅ Done |
| Preprocessing: add DatasetEstimator to left sidebar | ✅ Done |

**Commit:** `c39355e`

**Files changed:**
- `src/lib/hardwareEstimator.ts` — removed memGB, added `recommendedRamMB()`
- `src/components/DatasetEstimator.tsx` — shows cores only + Recommended RAM
- `src/components/AutoMLSteps/Step1Upload.tsx` — removed static note
- `src/components/AutoMLSteps/Step2Configure.tsx` — added DatasetEstimator
- `src/components/PreprocessingPanels/ConfigurePanel.tsx` — added DatasetEstimator to left sidebar

---

### Web Workers — UMAP, FA, Gibbs LDA

**Problem:** Heavy computations ran on main JS thread inside `setTimeout` — froze browser tab on large datasets.

**Implementation:**
- Created `src/workers/fsSelectionWorker.ts` — runs full `runSelection()` (UMAP + FA + all FS algos) in worker
- Created `src/workers/ldaWorker.ts` — runs Gibbs LDA in worker
- Updated `feature-selection/page.tsx` — replaced setTimeout+runSelection with worker
- Updated `src/hooks/useFELDA.ts` — replaced setTimeout+runLDA with worker
- Both use `new Worker(new URL('...', import.meta.url))` — webpack 5 bundles automatically

**Bug fix:** Subagent used wrong relative path `../../workers/` (2 levels) instead of `../../../workers/` (3 levels from `src/app/tools/feature-selection/`). Fixed in `6afd4d9`.

**Commits:** `679a960`, `6afd4d9`

---

### Streaming CSV Parse

**Problem:** `FileReader.readAsText()` loads entire file as string — 50MB file = 50MB text + 50MB rows = 100MB+ peak.

**Implementation:**
- Created `src/lib/parseCSVStream.ts` — reads via `file.stream().pipeThrough(new TextDecoderStream())`, parses 64KB chunks
- Exports `parseCSVStream()` (returns `string[][]`) and `parseCSVStreamFS()` (returns `{ headers, rows }`)
- Handles quoted fields, `\r\n`, `""` escaped quotes
- Replaced `FileReader.readAsText` in Preprocessing, FE, and FS tools

**Peak memory:** one 64KB chunk + parsed rows (vs full text + rows previously)

**Commit:** `679a960`

---

### Build Error Fix

Turbopack build failed: `Module not found: Can't resolve '../../workers/fsSelectionWorker.ts'`

Cause: Wrong relative path. From `src/app/tools/feature-selection/page.tsx`, workers directory needs 3 levels up (`../../../`), not 2.

**Commit:** `6afd4d9`

---

### Pending Items Review

Searched conversation parts 40–113, created master pending list at:
`/Users/wrks/Downloads/Claude-documentation/Projects/ML-Unified/Conversations/pending.md`

Items removed from list this session:
- ~~Retrain 80 Cereals model~~ — not required
- ~~Verify AdaBoost winner-training branch~~ — full retrain not necessary per earlier decision
- ~~Add `RENDER_EDA_DEPLOY_HOOK_URL` to GitHub Secrets~~ — already done, confirmed

---

## All Commits This Session

| Commit | Repo | What |
|--------|------|------|
| `f1e443b` | ml-portfolio | fix: minHeight:0 on content div + DatasetOverview collapsed default |
| `701288c` | ml-portfolio | fix: scrollable right panel, DatasetOverview open default, remove MouseTiltCard from toggles |
| `c39355e` | ml-portfolio | feat: remove deviceMemory, add Recommended RAM, DatasetEstimator to AutoML config + Preprocessing |
| `679a960` | ml-portfolio | feat: web workers for UMAP/FA/Gibbs + streaming CSV parse |
| `6afd4d9` | ml-portfolio | fix: correct relative path to fsSelectionWorker.ts (3 levels up) |

---

## Pending Items (as of end of session)

See full table in `pending.md`. Key items:

**Frontend (ml-portfolio):**
- FE: one-hot encoding, target encoding, transform presets, column search, recipe summary, date/datetime/polynomial/binning/ratio features
- FE: DatasetEstimator not added to configure step
- FS: AI Suggest intermittent JSON error
- AutoML: Model Fitness tooltip, more algorithm pills, "Own key" UX, showAutoMLWizard() bug
- Tool pages: Optuna, SHAP, Ensemble (static → interactive)
- Pipeline builder (Steps 1–4)

**Backend (ML-Unified):**
- AutoML Phases 3, 4, 9–13
- SHAP/What-If improvements
- Gemini + Groq LLM broken (API deprecation)
- Model persistence across Render restarts

**Testing:**
- Playwright automated tests — set aside

*Parts 1–39 not yet searched for additional pending items.*
