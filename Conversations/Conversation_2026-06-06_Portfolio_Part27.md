# Conversation — 2026-06-06 | EDA Explorer Upgrades (Part 27)

**Date:** 2026-06-06
**Project:** ML-Unified

---

## Points Completed This Session

| # | Item | Status |
|---|---|---|
| 1 | EDA Explorer — aesthetic + feature upgrades (Plotly charts, smart insights, sample preview, quality score, skew/kurtosis, sticky nav) | ✅ Done |
| 2 | EDA Explorer — box plots (one Plotly chart, all numeric columns) | ✅ Done |
| 3 | EDA Explorer — HTML export (self-contained, PNG-embedded, offline-ready) | ✅ Done |

---

## All Commits This Session

| Hash | Description |
|---|---|
| `560b4f8` | Upgrade EDA Explorer: Plotly charts, smart insights, sample preview, quality score |
| `a947492` | Add box plots and HTML export to EDA Explorer |

---

## What Was Built — Commit `560b4f8`

### Backend (`routers/eda.py`)
- **Skew + kurtosis** added to every numeric column's stats (`s.skew()`, `s.kurtosis()`)
- **Sample data** — first 5 rows returned as `{ columns, rows }` with NaN-safe native Python types via `_to_native()`
- **Smart insights** — auto-generated list, each `{ type, text }`:
  - Missing >5% → warning; >20% → danger
  - Duplicates > 0 → info or warning
  - High skew (abs > 2) → info + log transform hint
  - Outlier-heavy cols (>10% of rows) → warning
  - High-correlation pairs (Pearson ≥ 0.9) → danger + multicollinearity note
- **Quality score** (0–100) — deductions: missing % × 2 (max –40), dup % × 3 (max –15), avg skew × 2 (max –10), avg outlier % × 1.5 (max –15)

### Frontend (`frontend/index.html`)
- **5-chip overview** — added Quality /100 chip, colour-coded green/amber/red
- **Smart insights section** — colour-coded alert cards (danger/warning/info) with icons
- **Sticky section nav** — tabs scroll to Overview / Sample / Columns / Statistics / Distributions / Box Plots / Correlations
- **Sample data preview** — first 5 rows as a styled table; NaN shown as italic placeholder
- **Stats table** — Skew + Kurtosis columns added; skew cell colours by magnitude (amber >1, red >2)
- **Plotly distribution charts** — replaced SVG mini-bars; green histograms (numeric), purple bars (categorical)
- **Plotly correlation heatmap** — replaced CSS table; RdBu diverging colorscale, annotated cell values, auto-height
- **Section card wrappers** — every section inside `eda-section-card` for visual separation
- **`_renderEDAPlots(d)`** — new function called via `setTimeout(..., 0)` after `innerHTML` set; reads CSS vars (`--text3`, `--border`) for theme-aware Plotly colors

---

## What Was Built — Commit `a947492`

### Box Plots

**Backend:** `raw_vals` added to each numeric column's stats entry — up to 300 uniformly sampled values. Enables Plotly to draw true box plots with outlier dots.

**Frontend:** Single Plotly `type: 'box'` chart inside a new "Box Plots" section. All numeric columns rendered side-by-side. Key config:
```js
{
  type: 'box', name: col,
  y: d.stats[col].raw_vals,
  boxpoints: 'outliers',
  marker: { color: '#34d399', size: 3, opacity: 0.7 },
  fillcolor: 'rgba(52,211,153,0.12)',
}
```
IQR whiskers computed automatically by Plotly from raw values. Outlier dots rendered as scatter points.

### HTML Export

**`_exportEDAReport()`** — async, no server involved:
1. Finds every Plotly div (`eda-dist-0…N`, `eda-box-plot`, `eda-corr-hm`)
2. Calls `Plotly.toImage(el, { format: 'png', scale: 2 })` for each
3. Calls `_buildExportHTML(...)` with data + PNG data URLs
4. Creates a Blob, triggers `<a download>` click, revokes object URL
5. Button shows "Exporting…" and disables during capture

**`_buildExportHTML()`** — generates self-contained HTML:
- Dark-theme CSS fully inline (no external dependencies)
- All sections regenerated from raw data: overview chips, insights cards, sample table, column info table, stats table
- Charts embedded as `<img src="data:image/png;base64,...">` tags
- Distribution charts in a responsive CSS grid
- File named `<csv_name>_eda_report.html`, opens offline in any browser

**Export button** lives in the overview card title bar, right-aligned via `margin-left:auto`. Styled in EDA green, only present once results are rendered.

---

## Key Architectural Notes

- `_edaCurrentData` and `_edaCurrentFilename` are module-level vars — set in `_runEDA`, read by `_exportEDAReport`
- Box plots section order: Distributions → Box Plots → Correlations
- `_renderEDAPlots` reads CSS custom properties at call time for theme-aware Plotly colors — works for both dark and light themes
- `boxpoints: 'outliers'` — Plotly auto-computes IQR fences from raw values, so no manual whisker calculation needed

---

## Pending

### EDA Explorer (remaining)
- Missing value heatmap (rows × cols grid) — visual pattern detection

### Microservices restructure (paused from Part 25)
- Partial files in `ml-api/routers/` and `ml-api/shared/`
- Need: `training.py`, `unsupervised.py`, ml-vision full router split, update both `app.py`, update tests

### SHAP Interpreter (separate portfolio card)
- User uploads model (.pkl) + dataset → SHAP feature importance + summary plot

### Build Pipeline (inside ML Unified, second tab)
- Step-by-step: Load → EDA → Preprocess → Train → Evaluate → Deploy

### Phase 2: Theme palette picker + vision ambient themes
### Phase 4–6: Data drift · MLflow · E2E tests

---

## Standing Rules (unchanged)

- Apply changes to ALL affected repos simultaneously
- Conversation logs in `ML-Iris/Conversations/`
- Light theme: ALL elements must adapt
- Vercel = portfolio only; Render = ML apps
- `vision_cache/` and `.mcp.json` must never be committed
- Always run `ruff check` + `pytest` before pushing
- Mock-based tests for inference paths requiring model downloads
- User-facing errors: plain English only
- Keep ml-api and ml-vision requirements.txt fully independent
- All vision endpoint URLs sourced from `VISION_API`, never `API`
- Microservices pattern: modular monolith (router per domain, extractable later)
- ml-vision must have `/` root endpoint and `/favicon.ico` in `_SKIP_PATHS`
- `?mode=eda` treats EDA as ml-api for metrics; uses strict mode to hide non-EDA endpoints
- New endpoints → own router file in `routers/`, included in `app.py`
- `_renderEDAPlots` called via `setTimeout(..., 0)` after `innerHTML` set — ensures DOM is ready before Plotly
- ruff found in `.venv/bin/ruff` (not on PATH); run as `.venv/bin/ruff check <file>`
