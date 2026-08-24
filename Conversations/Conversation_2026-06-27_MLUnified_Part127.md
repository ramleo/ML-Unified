# Conversation_2026-06-27_MLUnified_Part127

Continuation from Part 126.

---

## Pipeline Builder — Bug Fixes + UI Improvements

### Bug Fixes Committed This Session

| Commit | Description | Repo |
|---|---|---|
| `e6a2d3b` | fix(pipeline-builder): fix API key names, CSV column parsing, Express mode, model_id chain | ml-portfolio |
| `e21eb1f` | feat(pipeline-builder): arrow connectors between stages + row/col delta in waterfall | ml-portfolio |
| `df03f49` | fix(pipeline-builder): remove unused imports | ml-portfolio |
| `0a5e488` | fix(pipeline-builder): define WaterfallStage type locally | ml-portfolio |
| `a8dd007` | fix(pipeline-builder): extract WaterfallStageDef to pipeline-types.ts | ml-portfolio |
| `2777a7a` | fix(pipeline-builder): single WaterfallStage type in pipeline-types.ts | ml-portfolio |
| `a7de5c9` | feat(pipeline-builder): return row/col stats in stage responses | ML-Unified (HF uploaded) |

### UI Improvements Committed This Session

| Commit | Description | Repo |
|---|---|---|
| `50c403d` | feat(pipeline-builder): waterfall before/after labels, flow connector animation, cinematic card animations | ml-portfolio |

---

## Architecture Recap

- **Stateless pipeline**: browser holds CSV chain, sends with each stage request
- **Stats in backend**: preprocessing/FE/FS all return `stats: { rows_before, rows_after, cols_before, cols_after }`
- **Shared type**: `WaterfallStage` defined in `src/components/pipeline/pipeline-types.ts` (plain .ts, no "use client") — imported by WaterfallChart, StageGrid, page.tsx
- **Flow connector**: `FlowConnector` component in StageGrid.tsx — glowing dot animating along a wire between cards
- **Card animations**: spring entrance (y:32→0), DONE 5-keyframe bounce, RUNNING shimmer sweep + border flicker

---

## TypeScript Issues Resolved

Root cause: Next.js TS plugin (`"plugins": [{"name": "next"}]`) blocks named type exports from `"use client"` components via `@/` alias. Fix: move shared types to plain `.ts` file (no directive).

---

## Live URL

**ml-portfolio**: https://ml-portfolio-rho.vercel.app  
**Pipeline Builder**: https://ml-portfolio-rho.vercel.app/tools/pipeline-builder

---

## Pending (next session)

1. **Waterfall section** — make animated and lively:
   - Count-up numbers (0 → 15 rows)
   - Staggered row entrance (slide in from left with delay)
   - Row glow when stage result arrives
   - Header animation
   - Fix right-side labels: `15 rows (no change)` + `6 cols (no change)` stacked looks cluttered — combine into `15 rows · 6 cols` or pill/badge style

2. **#23 Drift Detection v2**
3. **#24 RAG AI explanation**
4. **#25 Ensemble/stacking backend**
5. **#33 Categorical frequencies in schema JSON**
6. **#39-44 MLOps items**
7. **#45 E2E Playwright CI**
8. **#47 Dockerize ml-eda + ml-vision**
9. **#50 Batch predictions**
10. **TC-PEND: 47 open TCs**

---

## File Line Counts (pipeline components)

| File | Lines |
|---|---|
| `pipeline-types.ts` | 13 |
| `WaterfallChart.tsx` | 148 |
| `StageGrid.tsx` | 228 |
| `StageCard.tsx` | 397 |
| `page.tsx` | ~336 |
