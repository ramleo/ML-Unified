# Session 2026-07-15 — index.html Split Plan (Part 190)

## Context

Following from Part 189 where we decided to split `index.html` before adding analytics tracking. User confirmed: "Yes" to planning the split.

---

## Current Structure of index.html (9977 lines)

| Lines | Content | Size |
|-------|---------|------|
| 1 – 2033 | CSS + HTML shell + `_track` + `initServiceUrls` + `APP_MODE` | ~2000 lines |
| 2034 – 2222 | Theme system + shared UI utilities | ~190 lines |
| 2223 – 6198 | ML Unified JS (Boot, Sidebar, Predict, SHAP, AutoML, Train, RAG, Pipeline, Drift, Cluster) | ~4000 lines |
| 6199 – 8164 | Vision JS (classify, detect, segment, image processing) | ~2000 lines |
| 8165 – 9977 | EDA JS (upload, analyze, clean, chart) | ~1800 lines |

---

## Target File Structure

```
services/ml-api/frontend/
├── index.html      ML Unified only       ~3500 lines
├── eda.html        EDA only              ~2200 lines
├── vision.html     Vision only           ~2200 lines
├── common.js       Shared JS             ~500 lines
└── common.css      All CSS               ~1500 lines
```

---

## What Goes in `common.js`

- `_track()` function
- `let API`, `let VISION_API`, `let EDA_API` + `initServiceUrls()`
- `APP_MODE` detection
- `fetchWithRetry()`
- Theme toggle functions
- Shared UI utilities (modal helpers, toast, spinner, etc.)

## What Goes in `common.css`

Everything currently inside `<style>` tags — the full CSS block (~1500 lines). All 3 HTML files link to it via `<link rel="stylesheet" href="/static/common.css">`.

---

## Per-File Simplifications

**`index.html` (ML Unified):**
- Sidebar renders ML models only — no `APP_MODE` conditionals
- `init()` fetches `/models`, then `selectModel(allModels[0])` — no vision/eda branch
- Drops all Vision and EDA JS entirely

**`eda.html` (EDA Explorer):**
- `init()` calls `initServiceUrls()` then `selectEDA()` directly — **no `/models` fetch at all**
- Loads instantly (no cold-start dependency)
- Drops all ML Unified and Vision JS

**`vision.html` (ML Vision):**
- `init()` calls `initServiceUrls()` then `selectVision()` directly — **no `/models` fetch at all**
- Loads instantly too
- Drops all ML Unified and EDA JS

---

## URL Strategy — No Breaking Changes

Keep `?mode=` URLs intact. FastAPI route reads the param and serves the right file:

```python
@app.get("/")
def index(mode: str = "ml"):
    fname = {"eda": "eda.html", "vision": "vision.html"}.get(mode, "index.html")
    # inject VISION_URL / EDA_URL into the file, return HTMLResponse
```

- `wram1708-ml-unified.hf.space/?mode=eda` → serves `eda.html` ✓
- `wram1708-ml-unified.hf.space/?mode=vision` → serves `vision.html` ✓
- `wram1708-ml-unified.hf.space/` → serves `index.html` ✓

No portfolio links break, no HF Space embed URLs change.

---

## FastAPI Changes

1. `app.py` — update `GET /` to accept `mode` query param and serve correct file
2. Mount `StaticFiles` at `/static` to serve `common.js` and `common.css`

---

## Execution Order

| Step | Action |
|------|--------|
| 1 | Extract `common.css` from `<style>` block |
| 2 | Extract `common.js` from shared JS sections |
| 3 | Build `eda.html` (simplest — pure EDA JS + common includes) |
| 4 | Build `vision.html` (Vision JS + common includes) |
| 5 | Trim `index.html` to ML Unified only |
| 6 | Update `app.py` — mode-aware route + StaticFiles mount |
| 7 | Test all 3 URLs locally, then HF upload all 5 files |

---

## Benefits After Split

- EDA and Vision **load instantly** — no `/models` dependency
- Each file ~2000-3500 lines instead of 10k
- Analytics tracking (Step 1 of analytics plan) becomes 3 clean targeted edits
- Future bugs in Vision don't require hunting through EDA/ML code

---

## Status

User said "yes" to proceed with the split, then interrupted. Split not yet implemented.
Next session: start with Step 1 — extract `common.css`.
