# Conversation — 2026-06-27 — Pipeline Builder Cinematic Rebuild (Part 126)

## Context
Working directory: `/Users/wrks/Downloads/Claude-documentation/Projects/ml-portfolio`
Task: Full cinematic rebuild of the `/tools/pipeline-builder` page — 3 modes (Guided / Express / A/B Compare), Framer Motion animations, SHAP bar chart, stage impact waterfall, code export, A/B comparison panel.

---

## What Was Built

### New files created in `src/components/pipeline/`

| File | Lines | Description |
|------|-------|-------------|
| `ModeSelector.tsx` | 246 | Three-card mode picker (Guided / Express / A/B), stagger animation, hover scale 1.03 |
| `StageCard.tsx` | 398 | Stage card with 5 statuses (locked/ready/running/done/error), shake on error, pulse on done, running border animation |
| `CircuitBoard.tsx` | 167 | SVG overlay drawing cubic bezier paths between card centers; completed = #38bdf8 glow, active = animated dash, pending = dim |
| `StageModal.tsx` | 311 | Fixed overlay two-panel modal; left = StageConfigForm; right = results per stage (preprocessing stats, feature-eng badges, automl leaderboard, optuna delta, SHAP bars, ensemble score) |
| `StageConfigForms.tsx` | 302 | Per-stage config forms: preprocessing (imputation dropdowns, outlier toggle), feature-eng (per-column transforms), feature-select (method + K slider), automl (model pills, CV folds), optuna (trials slider), shap (info only), ensemble (type radio + model pills) |
| `WaterfallChart.tsx` | 135 | Horizontal animated bar chart showing score delta per completed stage |
| `CodeExportModal.tsx` | 225 | Fixed overlay with code block, copy-to-clipboard, download as pipeline.py |
| `ComparisonPanel.tsx` | 296 | A/B side-by-side score comparison with count-up animation, delta badge, winner highlight |
| `StageGrid.tsx` | 109 | Extracted component: guided/express card grid with CircuitBoard + WaterfallChart |
| `ABPanel.tsx` | 100 | Extracted component: A/B mode two-column layout + ComparisonPanel |
| `FormHelpers.tsx` | 137 | Shared form primitives (Field, SelectField, Toggle, SliderField, ModelPills) |
| `FileUploadSection.tsx` | 68 | Drag-drop upload zone component |

### Rebuilt page
`src/app/tools/pipeline-builder/page.tsx` — **281 lines** (was 255 lines of old PipelineProvider-based implementation)

### Deleted
`src/components/PipelineCard.tsx` — replaced by the new component system

---

## Key Technical Decisions

- **Hooks rule compliance**: 7 `useRef` calls (r0–r6) created individually, not in a loop, both in page.tsx (original agent) and StageGrid.tsx (extracted component)
- **CircuitBoard containerRef bug**: original subagent's page.tsx was missing `containerRef` prop; fixed by a follow-up subagent that rewrote page.tsx to 281 lines and adds `gridRef` passed as `containerRef`
- **File size compliance**: all files under 400 lines; StageCard exactly 398
- **No emojis**: all icons are inline SVG with `width={22} height={22} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round"`
- **StageResult type**: exported from StageModal.tsx, imported by StageConfigForms and page.tsx

---

## API Endpoints Used (POST to `${ML_UNIFIED_API}/pipeline-builder/...`)
- `/preprocess` — body: `{ csv_b64, target, config }`
- `/feature-eng` — body: `{ csv_b64, target, config }`
- `/feature-select` — body: `{ csv_b64, target, config }`
- `/automl` — body: `{ csv_b64, target, config }`
- `/optuna` — body: `{ csv_b64, target, model_id, config }`
- `/shap` — body: `{ csv_b64, target, model_id, config }`
- `/ensemble` — body: `{ csv_b64, target, config }`
- `/export-code` — body: `{ target, task_type, winner_algo, winner_params, preprocess_config, fe_config, fs_config }`
- `/compare` — body: `{ csv_b64, target, task_type }` (A/B mode)
- `/analyze` — body: `{ csv_b64 }` — used on file upload to get columns

---

## Status at end of conversation
- All component files written and verified (line counts checked)
- page.tsx at 281 lines — compliant
- Git commit + push: **PENDING** (user approved, then saved conversation first)

## Next step (after compact)
```bash
cd /Users/wrks/Downloads/Claude-documentation/Projects/ml-portfolio
git add src/components/pipeline/ src/app/tools/pipeline-builder/page.tsx
git rm src/components/PipelineCard.tsx
git commit -m "feat(pipeline-builder): cinematic rebuild — 3 modes, Framer Motion animations, stage impact, code export, A/B compare"
git push origin main
git rev-parse --short HEAD
```
