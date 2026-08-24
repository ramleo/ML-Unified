# Conversation — 2026-06-29 | #21 Context Wiring + CSV Persistence Plan | Part 133

## Session Overview

Reviewed pending item #21 (context wiring) and defined the full data persistence requirement across all 6 ML tool pages.

---

## #21 — Context Wiring (reviewed)

### What already works
- `PipelineContext` + `MLPipelineState` in `src/context/PipelineContext.tsx` with localStorage persistence
- `AutoMLModal` writes `automlWinner` + `automlRanking` to context after training
- `File` objects (`csv`, `cleanedCsv`) excluded from localStorage — users currently must re-upload on every page

### Priority breakdown
- **High**: Optuna, SHAP, Ensemble — read `automlWinner`/`automlRanking` to pre-select model; write results back
- **Lower**: Preprocessing, FE — write config/transforms to context
- **Blocked**: Feature Selection (381 lines) — must modularize first per Rule 3

---

## CSV Persistence Requirement (new — agreed 2026-06-29)

### User requirement
User uploads CSV once at Preprocessing. That file (and its transformed versions) should flow automatically through FE → FS → AutoML → Optuna/SHAP/Ensemble. Each page should:
- Auto-load the upstream stage's output CSV from context
- Show a "Using preprocessed data ✓" banner with row/col count
- Still allow uploading a different file (for standalone use)

### Pipeline data flow
```
User uploads CSV → Preprocessing → FE → FS → AutoML → Optuna / SHAP / Ensemble
                        ↓             ↓      ↓      ↓
                 preprocessedCsvB64  feCsvB64 fsCsvB64  (model results only)
                   stored in MLPipelineState (localStorage-safe base64 strings)
```

### New fields to add to `MLPipelineState` (src/types/pipeline.ts)
| Field | Type | Set by | Read by |
|---|---|---|---|
| `csvB64` | `string \| null` | Any page (raw upload) | All pages as fallback |
| `preprocessedCsvB64` | `string \| null` | Preprocessing page | FE page (default input) |
| `feCsvB64` | `string \| null` | FE page | FS page (default input) |
| `fsCsvB64` | `string \| null` | FS page | AutoML page (default input) |

Note: `csv` and `cleanedCsv` (File objects) remain excluded from localStorage. These 4 new fields are base64 strings — fully serializable.

### UX on each page
Each tool page gets a data source bar above the upload zone:
```
┌──────────────────────────────────────────────────────┐
│ ✓ Using preprocessed data (891 rows × 8 cols)        │
│                          [Upload different file ↑]   │
└──────────────────────────────────────────────────────┘
```
If no upstream data in context → normal drag-and-drop upload as today.

### Files to touch
| File | Lines | Action |
|---|---|---|
| `src/types/pipeline.ts` | — | Add `csvB64`, `preprocessedCsvB64`, `feCsvB64`, `fsCsvB64` to `MLPipelineState` + `emptyPipelineState` |
| `src/context/PipelineContext.tsx` | — | Remove old `csv`/`cleanedCsv` from `EXCLUDED`; new b64 fields persist by default |
| `src/app/tools/preprocessing/page.tsx` | 297 | Wrap in `PipelineProvider`; on upload store `csvB64`; after run write `preprocessedCsvB64` + `fileName` + `columns` |
| `src/app/tools/feature-engineering/page.tsx` | 269 | Wrap in `PipelineProvider`; read `preprocessedCsvB64` on load (auto-fill); write `feCsvB64` after apply |
| `src/app/tools/feature-selection/page.tsx` | **381** | ⚠️ Modularize first, then wrap + read `feCsvB64` + write `fsCsvB64` |
| `src/app/tools/automl/page.tsx` | — | Already has `PipelineProvider`; read `fsCsvB64` on load |
| `src/app/tools/optuna/OptunaRunner.tsx` | — | Wrap page in `PipelineProvider`; read `automlWinner.algo` → pre-select model; write `tunedModel` |
| `src/app/tools/shap/ShapRunner.tsx` | — | Same pattern as Optuna |
| `src/app/tools/ensemble/EnsembleRunner.tsx` | — | Read `automlRanking` → pre-select top models; write `ensembleType` + `ensembleScore` |

### Key constraint
`csv` and `cleanedCsv` (File objects) still can't persist — that's fine. The base64 strings carry the actual data. The `File` object fields can be removed from state or kept as runtime-only (excluded from localStorage).

---

## Status
- Plan approved by user ("haan kar") on 2026-06-29
- Implementation deferred to next session (user asked to save conversation first)
- Do Optuna/SHAP/Ensemble wiring + CSV persistence in one go since they're tightly related
