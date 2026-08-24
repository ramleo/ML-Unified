# Session 2026-07-16 — Analytics Dashboard: ML Unified Design + AI Explain + Report Export (Part 194)

## Summary

Continuation from Part 193. This session covered: navigating ML Unified AutoML results page via Playwright for UI reference, applying ML Unified design language to the analytics dashboard, adding an AI explanation panel, a markdown report export, and fixing several UX bugs.

---

## 1. ML Unified AutoML Results Page — UI Analysis (Playwright)

Navigated to `https://wram1708-ml-unified.hf.space/?mode=ml`, clicked AutoML, uploaded `test_pipeline.csv`, injected mock result data via `_renderAutoMLResultsPage()` to force the Results page to render.

### Key design patterns extracted

| Pattern | ML Unified | Applied to Analytics |
|---------|-----------|---------------------|
| Left summary card | Winner name, checkmark icon, KV table, CTA buttons | `AnalyticsSummaryCard` — hero count, 3-chip row, period KV table, Generate Report + AI Explain |
| Hero number | `0.12` at ~3.5rem bold fuchsia, top-right, outside any card | Stat cards already have 2rem hero — cards kept as-is |
| Eyebrow text | `WELL SUITED FOR YOUR DATA` tiny uppercase | `REAL-TIME ANALYTICS` eyebrow in summary card |
| 3 stat chips | WINNER / DATASET / MODELS TESTED in 3-col | 3-chip row: ACTIVE / DURATION / QSR |
| Algorithm Comparison bars | Model name + WINNER badge + score, proportional bars | BEST/TOP/Highest SR badges on comparison bars |
| Feature Importance bars | Numbered list, thick accent bars | Applied to Portfolio/HF tool cards |
| Card transparency | `rgba(255,255,255,0.025)` — barely elevated, constellation visible | Changed from `rgba(14,22,40,0.72)` → `rgba(255,255,255,0.03)` |
| AI Explanation | Section with AUTO badge, always visible | `AnalyticsAIPanel` — MANUAL badge, manually triggered |

---

## 2. New Components + Files

### `AnalyticsSummaryCard.tsx` (new)
Left summary panel matching ML Unified's left results card:
- Hero event count with Live badge
- 3-chip row: Active / Duration / QSR (color-coded)
- Period Summary KV table: Top Page, Top Tool, Peak Hour, Bounce, Returning
- Two action buttons: `↓ Generate Report` and `✦ AI Explain ▼`

### `AnalyticsAIPanel.tsx` (new)
- Collapsed by default — `MANUAL` badge (mirrors ML Unified's `AUTO` badge)
- Click "Generate Explanation" to trigger — NOT auto-generated
- Calls `POST /api/ai-explain` with current `stats` + `rangeLabel`
- Renders bold/paragraph formatted explanation
- Shows Regenerate button once content is loaded

### `src/lib/analyticsReport.ts` (new)
Pure function `generateMarkdownReport(stats, rangeLabel)`:
- Summary table, funnel, top pages, HF tools breakdown, portfolio tools breakdown, AI model usage, top countries
- Downloads as `.md` file via Blob URL

### `src/app/api/ai-explain/route.ts` (new)
POST API route — provider cascade: `ANTHROPIC_API_KEY` → `GEMINI_API_KEY` → `GROQ_API_KEY`
- Sends structured prompt asking for 5-section analysis (Traffic / Tools / Funnel / Patterns / Recommendation)
- Returns `{ explanation: string }`

### `AnalyticsQueryByTool.tsx` (extracted from dashboard)
Extracted from `AnalyticsDashboard.tsx` to keep dashboard under 400 lines:
- Path name map: `/eda` → "EDA", `/vision` → "Vision", `/` → "ML Unified", `/tools/text-to-sql` → "Text → SQL" etc.
- `Highest SR` badge on tool with best success rate

---

## 3. Design Fixes

### Card transparency — match ML Unified
All card backgrounds changed from `rgba(14,22,40,0.72)` (solid dark, hides constellation) → `rgba(255,255,255,0.03)` (barely elevated, constellation bg shows through).

Files: `AnalyticsStatCard.tsx`, `AnalyticsSummaryCard.tsx`, `AnalyticsAIPanel.tsx`, `AnalyticsQueryByTool.tsx`, all `bg-[rgba(14,22,40,0.72)]` → `bg-white/[0.03]` in `AnalyticsDashboard.tsx`

### Empty space fix
Right-side stat card grid: `grid-cols-2 lg:grid-cols-3` (5 cards → empty gap in row 2) → `grid-cols-2` with Query Success card as `col-span-2` (fills all rows, no empty cell).

### TOP badge on HF Tools + Portfolio Tools
`AnalyticsHFTools.tsx` and `AnalyticsPortfolioTools.tsx`: compute `topTool` (most total events), pass `isTop` prop to `ToolCard`, renders a color-tinted `TOP` badge next to tool name.

### AI Model Usage — conditional layout
When `provider_breakdown` is empty (e.g. only vision model queries, no SQL providers), the "By Provider" column is hidden and "By Model" shows full-width. Previously showed "No query data yet" which was confusing.

### Device Donut — single segment fix
SVG arc paths break at 100% (start = end point → invisible arc). When `data.length === 1`, render a simple chip row instead of the donut. Also renamed label from "Device Split" → "Visitors by Device".

### Remove duplicate Generate Report
Removed `↓ Report` button from the toolbar (was placed both in toolbar AND summary card). Now lives only in the summary card.

---

## All Commits This Session

| Repo | Hash | Message |
|------|------|---------|
| ml-portfolio | `eee86fa` | feat(analytics): ML Unified design — summary card, AI explain, report export, BEST/TOP badges |
| ml-portfolio | `ea4e81e` | fix(analytics): transparent cards + no empty grid space — match ML Unified |
| ml-portfolio | `78383d8` | fix(analytics): path names, AI model layout, device donut, remove duplicate report button |

---

## Pending / Next Steps

- [ ] Analytics Step 4: Drift + Ensemble tracking (add `track()` calls to those tool pages)
- [ ] Analytics Step 5: Pipeline Builder + Pipeline Cinema tracking
- [ ] Vision smoke test: classify, image processing, segmentation (detection confirmed working)
- [ ] Confirm `ML_VISION_URL` secret on HF Space updated to `https://wram1708-ml-unified.hf.space`
- [ ] Confirm `ANTHROPIC_API_KEY` (or `GEMINI_API_KEY`) set in Vercel for AI explain to work
