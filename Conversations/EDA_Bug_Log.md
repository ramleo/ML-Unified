# EDA Explorer — User-Reported Bug Log

Bugs reported by the user across sessions. Each entry links to the test case that now covers it.

---

## BUG-001 — Distribution charts not captured in HTML/PDF export (reported 3×)

**Reported:** 2026-06-06  
**Severity:** High  
**Status:** Fixed (`9f04040`)

**Symptom:** HTML export and PDF showed missing or blank distribution chart images.

**Root causes found (in order of discovery):**
1. `Promise.all` race condition — all 12+ charts captured simultaneously, some failed silently.
2. Explicit `height: 160` in Plotly layout overrode `toImage`'s dimension params — chart captured at 160px not 700×280.
3. Restore call `Plotly.relayout(el, { width: null })` threw (`null` invalid) — single `try/catch` discarded the already-captured image.

**Fixes:**
- Sequential capture loop (not `Promise.all`).
- Removed explicit height from `baseLayout`.
- `Plotly.relayout(el, { width, height })` before capture, restore in a **separate** `try` block so restore failure never discards a captured image.

**Test:** `test_eda.py::test_eda_distributions_have_raw_vals` (verifies backend sends raw_vals required for capture)

---

## BUG-002 — Histogram shows one giant bar for clustered data / empty for spread data

**Reported:** 2026-06-06  
**Severity:** High  
**Status:** Fixed (`6f72532`)

**Symptom:** Columns like sodium, sugars, potass showed one full-height green bar. Columns like calories, protein showed near-invisible bars.

**Root cause:** Pre-computed numpy equal-width bins (`np.histogram` with fixed n_bins). Clustered data → all rows in 1 bin → 1 giant bar. Spread data → many bins with 1–2 counts → invisible bars relative to y-scale.

**Fix:** Switched to Plotly native `type: 'histogram'` with `autobinx: true` and `raw_vals` (already present in `d.stats[col].raw_vals`). Plotly auto-selects optimal bin widths.

**Test:** `test_eda.py::test_eda_stats_include_raw_vals`

---

## BUG-003 — PCA 3D chart blank, "No file chosen" tooltip appears on section

**Reported:** 2026-06-06  
**Severity:** High  
**Status:** Fixed (`4c9586c`)

**Symptom:** PCA 3D section card showed title and dropdown but no chart. Browser showed "No file chosen" tooltip in the chart area.

**Root cause:** `colorVals` was an array of strings (category labels like cereal names). Plotly `scatter3d` with a sequential colorscale (`'Turbo'`) requires numeric color values — string arrays cause a silent render failure. The 480px chart div stayed empty and transparent, allowing the file-input element beneath to show its hover tooltip.

**Fix:** `colorData = colorVals.map(v => unique.indexOf(v))` maps strings to integer codes. Colorbar `ticktext` shows original labels.

**Test:** `test_eda.py::test_eda_pca_result_structure` + `test_eda.py::test_eda_pca_cat_color_map_values_are_strings`

---

## BUG-004 — PCA "Color by" dropdown only showed first categorical column as functional

**Reported:** 2026-06-06  
**Severity:** Medium  
**Status:** Fixed (`4c9586c`)

**Symptom:** Dropdown had multiple options but selecting any column other than the first had no effect.

**Root cause:** Backend sent `color_vals` for only the first categorical column. `_recolorPCA` checked `colName !== pca.color_col` and fell back to `null`.

**Fix:** Backend sends `cat_color_map: {col_name: [all_values]}` for all categorical + low-cardinality numeric cols (2–15 unique). `_recolorPCA` does `pca.cat_color_map[colName]` — works for any column.

**Test:** `test_eda.py::test_eda_pca_cat_color_map_all_cols` + `test_eda.py::test_eda_pca_includes_low_cardinality_numeric`

---

## BUG-005 — PDF export locks original tab / can't interact with EDA page

**Reported:** 2026-06-06  
**Severity:** Medium  
**Status:** Fixed (`9f04040`)

**Symptom:** After clicking PDF button, the EDA Explorer page became unresponsive. User couldn't scroll or interact.

**Root cause:** `_printEDA()` called `win.print()` in the new window. Many browsers freeze all tabs while a print dialog is open.

**Fix:** PDF button now opens the premium HTML as a blob URL in a new tab — no `window.print()` call. User prints manually from inside the report using the embedded "Save as PDF" button.

---

## BUG-006 — Lasso select and box select non-functional, no way to deselect

**Reported:** 2026-06-06  
**Severity:** Low  
**Status:** Fixed (`9f04040`)

**Symptom:** Lasso and box select buttons appeared in chart modeBar but triggered no action. Once activated there was no way to exit the selection mode.

**Root cause:** No `plotly_selected` event handler existed anywhere. Buttons were present but dead.

**Fix:** Removed both buttons via `modeBarButtonsToRemove: ['select2d', 'lasso2d']` on all chart configs. Added `doubleclick: 'reset+autosize'` to `baseLayout` so users can reset zoom/state on any chart by double-clicking.

---

## BUG-007 — CSV download button added with no real value

**Reported:** 2026-06-06  
**Severity:** Medium (UX deception)  
**Status:** Removed (`0c85f90`)

**Symptom:** "⬇ CSV" button in overview re-downloaded the original uploaded file unchanged.

**Root cause:** Suggested and built without verifying that a "download cleaned data" feature required backend data transformation — not just a re-download of the in-memory File object.

**Resolution:** Button removed. Genuine cleaned CSV (dedup + impute + drop ID cols) is a separate backend feature worth building only when a concrete use case is defined.

---

## BUG-008 — PDF via window.print() on live app produced bad output

**Reported:** 2026-06-06  
**Severity:** High  
**Status:** Fixed (`4c9586c` → `9f04040`)

**Symptom:** Clicking "PDF" opened browser print dialog on the live dark/glassmorphism UI. Result was unusable — transparent backgrounds, backdrop-filter ignored, charts not rendered.

**Root cause:** `window.print()` renders exactly what the browser sees. Glassmorphism (`backdrop-filter`, `rgba` backgrounds, SVG animations) does not survive print rendering.

**Fix:** PDF generates the premium HTML export (all charts as embedded PNGs), opens as blob URL, user prints from a clean document that has proper `@media print` CSS.

---

## Known Limitations (not bugs)

| Item | Detail |
|---|---|
| PCA 3D not in HTML export | `scatter3d` uses WebGL; `Plotly.toImage` doesn't support WebGL charts. Export shows an info card instead. |
| Low-variance charts still look flat | One giant bar IS the correct representation of clustered data. `⚠ low variance` label now flags these. |
| SPLOM limited to 8 cols | More columns make the matrix unreadable. Cap is intentional. |
