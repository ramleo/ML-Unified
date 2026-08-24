# Session 2026-07-16 — Document Intelligence Plan + Analytics Fixes (Part 195)

## Summary

Continuation from Part 194. This session covered: analytics dashboard path name fixes (Top Pages + Live Feed + Summary Card), identifying the real-world use cases shortlist from Part 159, planning the Document Intelligence tool, and fixing the analytics stat card transparency regression.

---

## 1. Analytics Path Name Fixes

Applied `pathLabel()` from `AnalyticsQueryByTool.tsx` to two more places that were still showing raw paths:

### Summary Card — "Top Page" row
- `AnalyticsSummaryCard.tsx` line 111: replaced manual `.replace("/tools/", "").replace("/", "")` with `pathLabel(topPage.path)`

### Live Feed — path column
- `AnalyticsLiveFeed.tsx`: replaced the dimmed `/tools/` prefix + bright tool name pattern with a single `pathLabel(ev.path)` call
- Removed `isToolPath` and `toolName` variables; replaced JSX with `<span>{friendlyPath}</span>`

### Top Pages Bar
- `AnalyticsCharts.tsx`: exported `pathLabel` from `AnalyticsQueryByTool.tsx`, imported it in charts, used in `TopPagesBar` label computation

| Commit | Repo | Description |
|--------|------|-------------|
| `83edad8` | ml-portfolio | fix(analytics): use friendly path names in Top Pages bar |
| `7d082a0` | ml-portfolio | fix(analytics): use friendly path names in summary card + live feed |

---

## 2. Pending Backlog Status — All Clear

Confirmed all tracking steps (Steps 4 + 5 — Drift, Ensemble, Pipeline Builder, Pipeline Cinema) were already complete from a previous session. All 12 tool pages have `useToolTracking`. Analytics dashboard backlog fully cleared.

---

## 3. Real-World AI/ML Use Cases Shortlist (from Part 159)

First discussed in Part 159 under "What's Hiring in 2026" — a shortlist of real-world portfolio projects selected for maximum interview/resume impact.

| Project | Status |
|---------|--------|
| **Text-to-SQL Agent** | ✅ Built (Parts 161–180+) |
| **LLM Fine-tuning Pipeline** | ☐ Not started |
| **Document Intelligence** | ☐ Planning started (this session) |
| **Time Series Forecasting** | ☐ Not started (#43 in pending.md) |
| **Multimodal RAG** | ☐ Not started |

### What Each Is

**LLM Fine-tuning Pipeline** — Take an open-source base model (Llama, Mistral, Phi), fine-tune with LoRA/QLoRA on a domain dataset, evaluate vs base model, serve. Requires GPU (even QLoRA needs ~8GB VRAM). HF Space free tier is CPU-only — would need paid GPU Space or Colab.

**Document Intelligence** — Extract structured fields from PDFs/images (invoices, contracts, resumes, medical reports etc.) using OCR + LLM. Planning started this session — see plan file.

**Time Series Forecasting** — Prophet/ARIMA/LSTM for a real domain (sales, energy, finance). Evergreen, classic ML use case.

**Multimodal RAG** — PDFs with figures/tables → image+text chunking → cited answers. Bleeding edge; high complexity.

---

## 4. Document Intelligence — Plan Created

Plan file: `/Users/wrks/.claude/plans/temporal-gliding-pascal.md`

### Research Summary

**Architecture decision:** Hybrid pipeline — no local VLM (too slow on CPU). Use existing LLM provider cascade (Groq → Gemini → Cohere) for field extraction.

- Digital PDFs: PyMuPDF4LLM → Markdown → LLM extraction (~2-4s)
- Scanned PDFs/images: PyMuPDF rasterize → Surya OCR → LLM extraction (~8-20s CPU)
- Auto-detect which path based on whether PDF has an embedded text layer

**8 Document Types:**

| Type | Domain |
|------|--------|
| Invoice | Finance / B2B |
| Receipt | Retail / expense |
| Contract | Legal |
| Resume/CV | HR |
| Medical Report | Healthcare |
| Bank Statement | Finance |
| ID Card | Identity |
| Purchase Order | Procurement |

**Backend:** New `routers/document/` package in `ml-api` (zero cross-imports from other routers — ready for microservice extraction later). 5 files: `router.py`, `_extract.py`, `_schema.py`, `_llm.py`, `__init__.py`.

**Frontend:** `/tools/document-intelligence/` — 6 files: `page.tsx`, `DocIntelRunner.tsx`, `DocViewerPanel.tsx`, `DocFieldsPanel.tsx`, `DocSidebar.tsx`, `_types.ts`.

**Accent color:** Cyan `#06b6d4`

### UI/Animations Planned
- Scanning line sweeps over document preview during processing (CSS keyframe)
- Fields stream in one-by-one via SSE with staggered fade+slide pop-in (Framer Motion)
- Bounding box draw-in via SVG `stroke-dashoffset` animation per extracted field
- Confidence rings (circular SVG) per field: green >0.9, amber 0.7-0.9, red <0.7
- Processing steps rail (4 steps: Extract → Classify → Analyze → Validate)

### Card Transparency Rule (Non-Negotiable)
All cards use `bg-white/[0.03]` + `border border-white/[0.08]`. Constellation must show through. No solid dark backgrounds. Also applies to the analytics stat card transparency regression fix.

---

## 5. Analytics Stat Card Transparency Bug

The stat cards (`ACTIVE NOW`, `TOTAL EVENTS`, `AVG DURATION`, `BOUNCE RATE`, `QUERY SUCCESS`) reverted to solid dark backgrounds — need `AnalyticsStatCard.tsx` background fixed to `rgba(255,255,255,0.03)`. Not yet implemented (discovered while in plan mode).

---

## Pending / Next Steps

- [ ] Exit plan mode → fix analytics stat card transparency (`AnalyticsStatCard.tsx`)
- [ ] Implement Document Intelligence backend (`routers/document/`)
- [ ] Implement Document Intelligence frontend (`/tools/document-intelligence/`)
- [ ] LLM Fine-tuning Pipeline (after Doc Intel)
- [ ] Time Series Forecasting (#43)
- [ ] Multimodal RAG