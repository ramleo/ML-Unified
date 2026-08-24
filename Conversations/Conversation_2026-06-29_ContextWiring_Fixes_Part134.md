# Conversation — 2026-06-29 | Context Wiring Implementation + Fixes | Part 134

## Session Overview

Implemented #21 CSV persistence + context wiring across all 6 ML tool pages. Fixed several follow-up bugs discovered during testing.

---

## Commits This Session

| Hash | Repo | Message |
|---|---|---|
| `690245b` | ml-portfolio | feat(#21): CSV persistence + context wiring across all 6 ML tool pages |
| `a83aebf` | ml-portfolio | fix(context-banner): replace silent auto-load with explicit 'Use this data →' button on FE + FS pages |
| `3da3626` | ml-portfolio | fix(ai-tools): friendly error message on 401/429 from OpenAI-compat providers (Groq, Together, etc.) |

All frontend only — no HF Space upload required.

---

## #21 — CSV Persistence Implementation (complete)

### What was built

4 parallel subagents implemented:

| Page | What was done |
|---|---|
| `src/types/pipeline.ts` | Added `csvB64`, `preprocessedCsvB64`, `feCsvB64`, `fsCsvB64` fields |
| `src/components/CsvFromContextBanner.tsx` | New shared banner component (52 lines) |
| `src/app/tools/preprocessing/page.tsx` | Stores raw upload as `csvB64`; stores result as `preprocessedCsvB64` + columns |
| `src/app/tools/feature-engineering/page.tsx` | Auto-loads `preprocessedCsvB64` on mount; shows banner; writes `feCsvB64` after apply |
| `src/app/tools/feature-selection/page.tsx` | Modularized (FSPageHeader + fsTabs extracted); auto-loads `feCsvB64/preprocessedCsvB64`; writes `selectedFeatures` |
| `src/app/tools/automl/page.tsx` | Falls back to full context CSV chain when sessionStorage absent |
| `src/app/tools/optuna/OptunaRunner.tsx` | Wrapped in PipelineProvider; pre-selects model from `automlWinner`; writes `tunedModel` |
| `src/app/tools/shap/ShapRunner.tsx` | Same — pre-selects model; writes `shapValues` |
| `src/app/tools/ensemble/EnsembleRunner.tsx` | Pre-selects top 3 from `automlRanking`; writes `ensembleType` + `ensembleScore` |

### New files created
- `src/components/CsvFromContextBanner.tsx` (52 lines)
- `src/components/FSPanels/FSPageHeader.tsx` (58 lines)
- `src/components/FSPanels/fsTabs.ts` (38 lines)

---

## Bug Fixes

### Fix 1 — FE banner: silent auto-load replaced with explicit button

**Problem:** The banner showed "Using preprocessed data" but the upload zone also showed. `handleFile()` was called in a background `useEffect` (async, invisible) — if it failed, user saw nothing useful.

**Fix:** Removed silent auto-load. Banner now has a **"Use this data →"** button that explicitly calls `handleFile()` with a loading spinner. Also added `contextLoading` state that clears when `step` advances to "configure".

Files: `src/components/CsvFromContextBanner.tsx` (added `onUseData`, `loading` props), `src/app/tools/feature-engineering/page.tsx`, `src/app/tools/feature-selection/page.tsx`

### Fix 2 — Groq AI Suggest error message

**Problem:** "AI Suggest Methods" showed raw `401: {"error":{"message":"Invalid API Key"...}}`.

**Root cause:** GROQ_API_KEY in Vercel environment is invalid/expired — NOT a code bug.

**Fix:** Updated `callOpenAICompat` in `/api/ai-tools/route.ts` to return friendly messages on 401/429: "Invalid or expired API key for groq. Add your own key in chat settings (gear icon)..."

**To actually fix:** Update `GROQ_API_KEY` in Vercel environment variables.

---

## Pending Bugs (discovered during testing, not yet fixed)

### Bug 1 — RFE keeps N+1 features instead of N

**Root cause:** In `src/lib/fsMain.ts` RFE loop:
```typescript
const score = mi * (1 - 0.35 * avgR);
if (score < minScore) { minScore = score; minName = col.name; }
```
`miScore()` returns `NaN` for some features (zero-variance, failed MI computation). `NaN < Infinity === false` in JavaScript, so `minName` stays empty for those features. The loop hits `if (!minName) break` early, leaving N+1 features instead of N.

**Fix (written but not committed):**
```typescript
const raw = mi * (1 - 0.35 * (isFinite(avgR) ? avgR : 0));
const score = isFinite(raw) ? raw : 0;
if (score < minScore) { minScore = score; minName = col.name; }
```

### Bug 2 — fsCsvB64 not stored in context after FS run

**Root cause:** FS page only stored `selectedFeatures` (column names) after worker result. Never encoded `result.csvText` as base64 and stored it.

**Fix (written but not committed):**
```typescript
const fsCsvB64 = btoa(unescape(encodeURIComponent(sr.csvText)));
setState(prev => ({ ...prev, selectedFeatures: kept, fsCsvB64 }));
```
File: `src/app/tools/feature-selection/page.tsx`

**Impact:** AutoML currently can't auto-load the FS output CSV. Once this is committed, the full Preprocessing→FE→FS→AutoML data chain will work.

### Bug 3 — AutoML card position in capabilities grid

**Root cause:** In `src/data/capabilities.ts`, AutoML is listed as card #2, but correct pipeline order is Preprocessing → FE → FS → AutoML → Optuna → SHAP → Ensemble.

**Fix (written but not committed):** Move AutoML entry in array from position 2 to position 4 (after featureselect, before optuna).

---

## Pipeline Order (correct)
```
Preprocessing → Feature Engineering → Feature Selection → AutoML → Optuna → SHAP → Ensemble
     ↓                  ↓                    ↓               ↓
  csvB64         preprocessedCsvB64       feCsvB64        fsCsvB64     (model results only)
```

---

## Status
- All 3 pending fixes written but NOT committed (user asked to save conversation first)
- Fixes ready to apply in next session
- After commit, full CSV chain will work end-to-end

