# Conversation — 2026-06-06 | EDA Explorer — Build, Bugs, Fixes (Part 29)

**Date:** 2026-06-06
**Project:** ML-Unified · ml-api EDA Explorer
**Continued from:** Part 28

---

## Commits This Session

| Commit | Description |
|---|---|
| `bcb9e10` | PCA 3D scatter, MI matrix, ML Readiness, narrative, premium HTML export |
| `4c9586c` | Fix: PCA render (string colors), distribution capture, PDF approach, color dropdown |
| `00b2c78` | Feat: SPLOM, nav highlight, low-variance labels, PCA color options |
| `6f72532` | Fix: histogram binning (native type), chart capture dimensions, 3D zoom |
| `0c85f90` | Remove: CSV download button (added no value) |
| `9f04040` | Fix: chart capture restore bug, lasso/box removal, PDF tab lock, double-click reset |

---

## Features Built

### PCA 3D Scatter
- **Backend** (`eda.py`): `StandardScaler` + `PCA(n_components=3)` on numeric cols (≥50% non-null). Returns `coords`, `explained_variance` (%), `cat_cols`, `cat_color_map` (all categorical + low-cardinality numeric cols up to 8).
- **Frontend**: Plotly `scatter3d`, color-by dropdown, `_drawPCA3D` / `_recolorPCA` helpers.
- **Critical bug**: Plotly scatter3d requires **numeric** color values. Passing string category arrays (cereal names) to a sequential colorscale silently fails → blank transparent div → file input tooltip bleeds through ("No file chosen"). Fix: `unique.indexOf(v)` maps strings to integers; colorbar ticktext shows original labels.
- **Color options**: Backend includes low-cardinality numeric cols (2–15 unique) alongside cat cols so binary targets / ordinal ratings appear in dropdown.

### SPLOM (Scatter Plot Matrix)
- **Backend**: aligned 400-row sample of numeric cols (up to 8) + `color_map` dict for cat cols.
- **Frontend**: Plotly `splom` trace, `showupperhalf: false`, lower triangle only, color-by dropdown matches PCA UX.
- **Export**: captured as PNG, embedded in HTML/PDF export.

### Export HTML — Premium Redesign
- Gradient header with badges, glassmorphism cards, narrative + ML Readiness sections.
- All charts embedded as sequentially-captured PNGs.
- "Save as PDF" button baked into the exported HTML with `@media print` CSS.

### PDF Export Rework
- **Original approach**: `window.print()` on live glassmorphism app → terrible output.
- **Second approach**: Open new window, write HTML, call `win.print()` → freezes all tabs while print dialog is open.
- **Final approach**: Generate premium HTML export as blob URL, `window.open(url, '_blank')`. User clicks "Save as PDF" inside that report. Original tab never affected.

### Other Features
- **Low-variance labels**: backend flags `std/range < 5%` cols; frontend shows `⚠ low variance` badge on dist card title.
- **Nav active highlight**: persistent IntersectionObserver toggles `.eda-nav-active` on sticky nav tabs as sections scroll into view. `data-section` attribute links tabs to sections.
- **`doubleclick: 'reset+autosize'`** on all chart layouts — double-click resets zoom/selection.

---

## Bugs Fixed

### Histogram rendering (giant bars / empty charts)
- **Root cause**: Pre-computed numpy equal-width bins. If data clusters in one range, all 77 rows fall in 1 bin → one giant bar; spread data → many bins with 1–2 counts each → invisible bars.
- **Fix**: Switch numeric distributions to Plotly native `type: 'histogram'` with `autobinx: true` and `raw_vals` (already in `d.stats[col].raw_vals`). Plotly picks optimal bin widths per column automatically.

### Distribution/chart capture returning null
- **Root cause**: `imgFor` had one `try/catch` block. The restore call `Plotly.relayout(el, { width: null })` threw (`null` is invalid) → `catch` discarded the already-captured image.
- **Fix**: Two independent try blocks — capture and restore don't share error handling. Use `autosize: true` instead of `null` for restore.

### Chart capture dimensions inconsistent
- **Root cause**: Layout had explicit `height: 160` overriding toImage's dimension param. Chart rendered at 160px; toImage couldn't override it.
- **Fix**: Removed explicit height from `baseLayout`. Call `Plotly.relayout(el, { width, height, paper_bgcolor: '#111827' })` before capture to physically resize chart, then restore.

### PCA 3D scroll zoom disabled
- `scrollZoom: false` was set explicitly in `_drawPCA3D` and `_recolorPCA`. Changed to `true`.
- 3D controls: scroll = zoom, left-drag = rotate, modebar has zoom-in/out buttons.

### Lasso / box select
- Non-functional in EDA context (no `plotly_selected` handler). Removed via `modeBarButtonsToRemove: ['select2d', 'lasso2d']` on all chart configs.

### CSV download button removed
- Added without thinking it through. Button re-downloaded the original uploaded file — no value. Removed.
- **Future**: Genuine cleaned CSV (dedup, impute, drop ID cols) requires a new backend endpoint returning a modified DataFrame. Build only when user defines what "cleaned" means.

---

## Architecture Notes

### `_captureAllEDACharts()` pattern
Sequential capture (not `Promise.all`) to avoid Plotly race conditions:
1. `Plotly.relayout(el, { width, height, paper_bgcolor: '#111827' })` — resize + opaque bg
2. `Plotly.toImage(el, { format: 'png', scale: 2 })` — capture
3. `Plotly.relayout(el, { autosize: true, paper_bgcolor: 'transparent' })` — restore
Steps 1–2 and step 3 are in separate try blocks so restore failure never discards a captured image.

### PCA color map structure
Backend returns:
```python
{
  "cat_cols": ["name", "mfr", "type", "shelf"],   # all color-eligible cols
  "cat_color_map": { "name": [...77 vals], "mfr": [...], "shelf": [...] },
  "color_col": "name",   # default
}
```
Frontend `_recolorPCA(colName)` does `pca.cat_color_map[colName]` — works for any column.

### SPLOM color map
Same pattern: `splom.color_map[colName]` for any column. Separate from PCA map because SPLOM uses aligned rows from `splom_df.sample(400)`.

---

## Deferred / Not Built

| Item | Reason |
|---|---|
| Cleaned CSV download | Needs backend endpoint; build when use case is defined |
| PCA 3D in HTML export | scatter3d uses WebGL, `Plotly.toImage` doesn't support it. Export shows an info card with explained variance + pointer to live app |
| EDA microservice extraction | Router is isolated in `routers/eda.py`, extraction is mechanical. Do after feature set is stable |
| Portfolio animations (items 14–25, Part 28) | Not yet started |

---

## Standing Rules (unchanged)

- Apply changes to ALL affected repos simultaneously
- Conversation logs in `ML-Iris/Conversations/`
- Light theme: ALL elements must adapt
- Vercel = portfolio only; Render = ML apps
- `vision_cache/` and `.mcp.json` must never be committed
- Always run `ruff check` + `pytest` before pushing
- User-facing errors: plain English only
- ruff found at `.venv/bin/ruff`
- `_renderEDAPlots` called via `setTimeout(..., 0)` after innerHTML set
- All Plotly configs use `modeBarButtonsToRemove: ['select2d', 'lasso2d']`
- Distribution charts: `type: 'histogram'` with `raw_vals` + `autobinx: true`
- Chart capture: relayout → toImage → relayout-restore in separate try blocks
