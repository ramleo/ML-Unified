# Session 2026-07-17 — Document Intelligence Implementation + Analytics Constellation Fix (Part 196)

## Summary

Continuation from Part 195. This session covered: exiting plan mode and implementing Document Intelligence (backend + frontend), fixing the analytics constellation background bug, and optimising Docker build times with layer splitting.

---

## 1. Analytics Constellation Fix

### Root Cause
`ConstellationBackground` renders a canvas at `position: fixed; z-index: -1`. The root div on the analytics and text-to-sql pages had `bg-[#0a0a0f]` — a solid opaque background that painted OVER the canvas, making the constellation completely invisible.

### Fix
Removed `bg-[#0a0a0f]` from the root div in both pages. The body background (`#060d1a`, set by ConstellationBackground's inline `<style>` tag) provides the dark base, and the canvas at z-index -1 shows through all transparent cards.

**Files changed:**
- `src/app/tools/realtime-analytics/page.tsx` — removed `bg-[#0a0a0f]`
- `src/app/tools/text-to-sql/page.tsx` — removed `bg-[#0a0a0f]`

| Commit | Description |
|--------|-------------|
| `1754deb` | fix(ui): remove solid root bg that blocked constellation canvas on analytics + text-to-sql |

---

## 2. Document Intelligence — Backend (ml-api)

### Architecture
- Digital PDFs: PyMuPDF4LLM → Markdown → LLM extraction + pymupdf `page.search_for()` for bounding box lookup
- Scanned PDFs / images: Gemini Vision API (image input) → field extraction + estimated bboxes
- LLM cascade: Groq (llama-3.3-70b) → Gemini 2.0 Flash → Cohere (command-r-plus)
- SSE stream: step events (extract/classify/analyze/validate) → field events (70ms stagger) → done event with base64 page image
- Zero cross-imports from other ml-api routers — fully microservice-extractable

### New files
| File | Purpose |
|------|---------|
| `routers/document/__init__.py` | Package init |
| `routers/document/_schema.py` | 8 doc type definitions with typed field schemas |
| `routers/document/_extract.py` | PDF/image extraction via PyMuPDF4LLM + Pillow; bbox search |
| `routers/document/_llm.py` | LLM cascade (text + Gemini Vision); JSON response parsing |
| `routers/document/router.py` | `POST /document/analyze` (SSE), `GET /document/types` |

**8 Document Types:** Invoice, Receipt, Contract, Resume/CV, Medical Report, Bank Statement, ID Card, Purchase Order

**app.py changes:**
```python
from routers.document import router as document_router
app.include_router(document_router)
```

**New requirements:** `pymupdf>=1.24.0`, `pymupdf4llm>=0.0.17`

| Commit | Repo | Description |
|--------|------|-------------|
| `ba1632e` | ML-Unified | feat(document-intelligence): backend — 8 doc types, SSE streaming |

---

## 3. Document Intelligence — Frontend (ml-portfolio)

### Files created
| File | Purpose |
|------|---------|
| `_types.ts` | TypeScript interfaces: ExtractedField, StepEvent, DoneEvent, DocTypeInfo |
| `DocSidebar.tsx` | Doc type selector, AI-detected type badge, supported formats, how-it-works |
| `DocViewerPanel.tsx` | Base64 PDF preview, SVG bounding box overlay, scanning line animation |
| `DocFieldsPanel.tsx` | Framer Motion field pop-in stagger, SVG confidence rings, copy/export |
| `DocIntelRunner.tsx` | Upload zone (drag/drop), SSE consumer, 4-step processing rail |
| `page.tsx` | Tool shell: ConstellationBackground, useToolTracking, cyan accent (#06b6d4) |

### Key design decisions
- **Accent:** Cyan `#06b6d4` — distinct from all other tools
- **Cards:** `bg-white/[0.03]` + `border border-white/[0.08]` — all transparent, constellation shows through
- **Scanning animation:** `@keyframes scanLine` — cyan gradient bar sweeps top→bottom during processing
- **Field pop-in:** Framer Motion `AnimatePresence` with `opacity 0→1` + `translateY 8→0` per field
- **Confidence rings:** SVG `stroke-dasharray` circle fills to confidence %, green/amber/red by threshold
- **Bounding boxes:** SVG layer absolutely positioned over document preview, normalized `[0,1]` coords
- **Upload zone:** drag/drop + click, accepts PDF/PNG/JPG/JPEG/WEBP

### Other changes
- `AnalyticsQueryByTool.tsx`: added `"/tools/document-intelligence": "Doc Intel"` to PATH_NAMES
- `capabilities.ts`: added Document Intelligence tool card

| Commit | Repo | Description |
|--------|------|-------------|
| `d350cb2` | ml-portfolio | feat(document-intelligence): frontend — 6 files, SSE streaming, bbox overlays |

---

## 4. Docker Build Optimisation — Layer Splitting

### Problem
Any change to `requirements.txt` invalidates the Docker pip install layer, forcing all packages (torch, transformers, catboost, chromadb…) to reinstall from scratch. Build time: **~30 min** on HF free tier CPU.

### Solution
Split into two requirement files, installed as separate Docker layers:

**`requirements-base.txt`** — heavy, stable packages (rarely changes):
- scikit-learn, pandas, numpy, xgboost, lightgbm, catboost, shap, optuna
- sentence-transformers (brings torch), transformers, chromadb, langgraph, etc.

**`requirements.txt`** — lightweight/new packages (changes when adding tools):
- fastapi, uvicorn, httpx, pymupdf, pymupdf4llm, anthropic, openai, pypdf, etc.

**Dockerfile:**
```dockerfile
# Layer 1: heavy packages — cached unless requirements-base.txt changes
COPY requirements-base.txt .
RUN pip install --no-cache-dir -r requirements-base.txt

# Layer 2: lightweight packages — only this rebuilds when adding new tools
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

**Result:** First build still takes ~30 min. Every subsequent build where only `requirements.txt` changes: **~2-3 min**.

| Commit | Repo | Description |
|--------|------|-------------|
| `a8f1413` | ML-Unified | fix(docker): split requirements into base + app layers for faster rebuilds |

---

## 5. Status at Session End

- HF Space still building (`RUNNING_BUILDING`) after 25+ min — this is the first build with the new layer structure; subsequent builds will be fast
- Document Intelligence at `/tools/document-intelligence` — live on Vercel, backend 404 until HF build completes
- Constellation background fix — live on Vercel

## Pending / Next Steps

- [ ] Verify Document Intelligence end-to-end once HF Space build completes
- [ ] Test: upload invoice PDF → scanning animation, field streaming, bbox overlays
- [ ] LLM Fine-tuning Pipeline (next on real-world use cases shortlist)
- [ ] Time Series Forecasting (#43 in pending.md)
- [ ] Multimodal RAG
