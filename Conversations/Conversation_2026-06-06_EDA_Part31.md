# Conversation — 2026-06-06 | EDA Export Fixes & Render Port Timeout (Part 31)

**Date:** 2026-06-06
**Project:** ML-Unified · ml-api EDA Explorer
**Continued from:** Part 30

---

## Commits This Session

| Commit | Description |
|---|---|
| `.python-version` added | Forces Render to use Python 3.11.0 (PYTHON_VERSION env var does NOT work — only the file does) |
| `requirements.txt` pinned | All packages pinned to local working versions |
| `39857f3` | Diagnostic: wrap `_load()` in try-except so uvicorn stays up even if model loading fails, real error surfaces in Render Logs |
| `df67a6a` | Previous failing deploy — build succeeded but port never bound |

---

## Bugs Fixed This Session

### BUG — Distributions not captured in HTML export (4th recurrence)

**Final root cause:** `responsive: true` + ResizeObserver. When `Plotly.relayout` resized a live chart, the ResizeObserver fired and snapped it back to the container's CSS height (160px) between relayout and toImage. All captures silently returned null. Sequential loops, CSS overrides, and explicit toImage dimensions all failed because the race condition persisted.

**Final fix:** Off-screen rendering — for each chart, create a hidden `position:fixed; left:-9999px` div, call `Plotly.newPlot` with `staticPlot:true, responsive:false`, call `toImage`, then `Plotly.purge` and remove. Completely independent of live charts.

```js
const offscreen = async (traces, layout, w, h) => {
  const el = document.createElement('div');
  el.style.cssText = `position:fixed;left:-9999px;top:0;width:${w}px;height:${h}px;visibility:hidden;`;
  document.body.appendChild(el);
  try {
    await Plotly.newPlot(el, traces, { ...layout, width: w, height: h }, { staticPlot: true, responsive: false });
    return await Plotly.toImage(el, { format: 'png', scale: 2, width: w, height: h });
  } catch(e) {
    console.error('[EDA export] capture failed:', e);
    return null;
  } finally {
    try { Plotly.purge(el); } catch {}
    document.body.removeChild(el);
  }
};
```

### BUG — PDF button locking the original EDA tab (persistent)

**Root cause:** `window.print()` in ANY tab freezes ALL browser tabs while the print dialog is open. No browser workaround exists. This applied even when opening a new window and calling `win.print()` inside it — still locked all tabs.

**Fix:** Removed ALL `window.print()` from codebase. `#eda-pdf-btn`, `_printEDA()` function, and all print calls deleted. Export report now shows Ctrl+P / ⌘+P instruction instead. User prints manually from the exported HTML.

### BUG — MI/Correlation heatmap bottom row cut off

**Root cause:** `Math.min(600, labels.length * 45 + 110)` — 600px cap was not enough for 15-label matrices with -45° rotated x-axis labels requiring 90px+ bottom margin.

**Fix:** Dynamic cell sizing (`miCellSize = labels.length > 10 ? 38 : 48`), max 780px height, 120px bottom margin.

### BUG — Heatmap cell annotations missing in HTML export

**Root cause:** Off-screen render traces were missing `text` / `texttemplate`. Without these, Plotly renders no cell text at all.

**Fix:** Added to both correlation and MI off-screen renders:
```js
text: matrix.map(r => r.map(v => v !== null ? v.toFixed(2) : '')),
texttemplate: '%{text}',
textfont: { size: 8, color: '#ffffff' }
```

Force `color: '#ffffff'` — inherited theme color was invisible on dark cells.

---

## ONGOING — Render Port-Scan Timeout (Second Occurrence)

**Symptom:** Build succeeds, uvicorn starts (`==> Running 'uvicorn app:app...'`), but no port binds within 60s → "Port scan timeout reached."

**First occurrence (resolved):** Render defaulted to Python 3.14.3; pandas==2.2.2 had no cp314 wheel → source compilation hung during startup. Fix: `.python-version = 3.11.0` + pinned requirements.txt.

**Second occurrence (UNRESOLVED):** With Python 3.11 + pinned packages, build succeeds and uvicorn appears to start, but port never binds. No uvicorn output visible between "Running..." and "No open ports detected" — suggests crash at import time.

**Diagnostic state:** Commit `39857f3` wraps `_load()` in try-except so the process stays alive even if model loading fails, surfacing the real error in Render's Logs tab. Root cause not yet confirmed — need Render Logs output after this deploy.

**Note:** The nvidia-nccl-cu12 (300MB GPU library, transitive catboost dep) theory was WRONG — catboost was always in the project and the port timeout appeared after requirements were *pinned*, not because of a new package.

---

## Render Configuration (Current State)

- `.python-version`: `3.11.0` (in `services/ml-api/`) — this is the ONLY way to control Python runtime on Render
- `PYTHON_VERSION` env var in render.yaml: does NOT control Python runtime, kept for reference only
- `requirements.txt` fully pinned:
  ```
  fastapi==0.136.3
  uvicorn==0.41.0
  scikit-learn==1.8.0
  pandas==2.2.2
  numpy==1.26.4
  joblib==1.5.3
  python-multipart
  xgboost==3.2.0
  lightgbm==4.6.0
  catboost==1.2.10
  ```
- `render.yaml` startCommand: `uvicorn app:app --host 0.0.0.0 --port $PORT`

---

## User Feedback on Work Quality

User called out repeated wrong-guess fixes without understanding root cause ("don't give silly reasons, it was working fine before this"). Multiple wasted deploys from proposing plausible-sounding but unverified theories.

**Rule going forward:** When a production issue appears, surface the actual error first (diagnostics, logs). Do not propose a fix until the real error is known.

---

## Standing Rules (updated)

- Apply changes to ALL affected repos simultaneously
- Conversation logs in `ML-Iris/Conversations/`
- Light theme: ALL elements must adapt
- Vercel = portfolio only; Render = ML apps
- `vision_cache/` and `.mcp.json` must never be committed
- Always run `ruff check` + `pytest` before pushing
- User-facing errors: plain English only
- ruff at `.venv/bin/ruff`
- All Plotly configs: `modeBarButtonsToRemove: ['select2d', 'lasso2d']`
- All 2D chart layouts: `doubleclick: 'reset+autosize'`
- Distribution charts: `type: 'histogram'` + `autobinx: true` + `raw_vals`
- Chart capture: **off-screen rendering only** (`staticPlot:true, responsive:false`) — never resize live charts
- PDF: no `window.print()` anywhere. User uses Ctrl+P / ⌘+P manually
- Heatmaps: force `textfont.color: '#ffffff'` for cell annotations
- Render Python version: `.python-version` file only — env var doesn't work
- Never guess root cause; get actual error from logs before proposing fix
- New tests go in `test_eda.py` with bug ID reference in docstring

---

## Remaining Work

| Item | Notes |
|---|---|
| Render port-scan timeout (2nd) | Awaiting Render Logs output after commit `39857f3` |
| Portfolio animations (items 14–25, Part 28) | Not yet started |
| EDA microservice extraction | Deferred until feature set is stable |
| Frontend automation (Playwright) | Bug log in `EDA_Bug_Log.md` is the spec |
| Run 35 EDA tests | Deferred ("test it later") |
| Cleaned CSV download | Deferred until use case defined |
