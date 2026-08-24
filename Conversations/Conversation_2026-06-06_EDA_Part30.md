# Conversation — 2026-06-06 | EDA Bug Fixes, Tests & QA (Part 30)

**Date:** 2026-06-06
**Project:** ML-Unified · ml-api EDA Explorer
**Continued from:** Part 29

---

## Commits This Session

| Commit | Description |
|---|---|
| `6f72532` | Fix: histogram binning (native type), chart capture dimensions, 3D zoom |
| `0c85f90` | Remove: CSV download button (added no value) |
| `9f04040` | Fix: chart capture restore bug, lasso/box removal, PDF tab lock, double-click reset |
| `fbcc1c0` | Test: EDA test suite (35 tests) derived from user-reported bugs |

---

## Bugs Fixed This Session

### BUG-001 (3rd recurrence) — Distributions not captured in HTML/PDF

**Final root cause:** Restore call `Plotly.relayout(el, { width: null })` threw because `null` is invalid in Plotly layout. Single `try/catch` block discarded the already-captured image. Image was successfully captured in step 2 but thrown away in the catch from step 3.

**Fix:** Two independent try blocks — capture and restore have separate error handling. Use `autosize: true` instead of `null` for restore.

```js
let img = null;
try {
  await Plotly.relayout(el, { width: w, height: h, paper_bgcolor: '#111827' });
  img = await Plotly.toImage(el, { format: 'png', scale: 2 });
} catch { }
try {
  await Plotly.relayout(el, { autosize: true, paper_bgcolor: 'transparent' });
} catch { }
return img;
```

### BUG-002 (2nd recurrence) — Histogram giant bars / empty charts

**Final root cause:** Pre-computed numpy equal-width bins. Clustered data → all rows in 1 bin → one giant bar. Spread data with many bins → counts of 1-2 → invisible at y-scale.

**Fix:** Switched to Plotly native `type: 'histogram'` with `autobinx: true` using `raw_vals` already present in `d.stats[col].raw_vals`.

### BUG-005 — Lasso and box select non-functional, no way to deselect

**Fix:**
- Removed both buttons: `modeBarButtonsToRemove: ['select2d', 'lasso2d']` on all chart configs (applied `replace_all: true` since cfg appears 3 times).
- Added `doubleclick: 'reset+autosize'` to `baseLayout` — double-click resets zoom and clears state on any chart.

### BUG-006 — PDF button opened new window, locked original tab scroll

**Root cause:** `_printEDA()` called `win.print()` in the new window. Many browsers freeze all tab interactions while a print dialog is open in any window.

**Fix:** PDF button now generates the premium HTML export as a blob URL and opens it in a new tab via `window.open(url, '_blank')` — no `window.print()` call. User clicks "Save as PDF" inside that report. Original tab is never affected.

### BUG-007 — CSV download button removed

**Context:** Button added without verifying it delivered what the description implied. It re-downloaded the original uploaded file unchanged — no value to the user.

**Resolution:** Removed. Genuine cleaned CSV (dedup, impute, drop ID cols) requires a backend endpoint returning a modified DataFrame. Documented in memory and bug log. Build only when use case is defined.

### BUG-008 — 3D scatter scroll zoom disabled

**Root cause:** `scrollZoom: false` explicitly set in `_drawPCA3D` and `_recolorPCA`.

**Fix:** Changed to `scrollZoom: true` in both locations.

---

## Test Suite Created

**File:** `services/ml-api/tests/test_eda.py` — 35 tests across 8 classes.

Every test is derived from a bug reported by the user. Each test class maps to a bug ID.

| Class | Bug(s) | What it verifies |
|---|---|---|
| `TestDistributions` | BUG-001, BUG-002 | raw_vals present in stats, low-variance flagging |
| `TestPCA` | BUG-003, BUG-004 | structure, 3D coords, color values are strings, all cols in map |
| `TestPCANoCatCols` | BUG-003 | graceful handling when no categorical columns exist |
| `TestMLReadiness` | — | ID col fail, constant col fail, high/moderate missing |
| `TestSPLOM` | — | aligned rows, color_map alignment, 8-col cap enforced |
| `TestNarrative` | — | present, mentions row count, mentions quality |
| `TestMutualInformation` | — | symmetric, diagonal=1 (except constant cols), values in [0,1] |
| `TestEdgeCases` | — | single col, all-missing col, empty CSV, non-CSV rejected |

**Bug log:** `ML-Iris/Conversations/EDA_Bug_Log.md` — structured document with symptom, root cause, fix, and test reference for each bug. Foundation for future Playwright/Selenium frontend automation.

### Test fixes applied before commit

Four tests failed on first run — all test logic issues, not backend bugs:

| Test | Issue | Fix |
|---|---|---|
| `test_eda_low_variance_detects_constant_col` | Fixture `rng.normal(5.0, 0.01, n)` has std/range ≈ 20% > 5% threshold | Changed to `5.0 + rng.uniform(-1e-5, 1e-5, n)` — truly near-constant |
| `test_readiness_id_col_flagged_fail` | Fixture adds 3 duplicate rows so `id` nunique < nrows → not ID-like | Moved to standalone fixture with guaranteed unique IDs |
| `test_narrative_mentions_row_count` | `len(mixed_df) + 3` double-counted — fixture already includes duplicates | Changed to `len(mixed_df)` |
| `test_mi_matrix_diagonal_is_one` | Constant column has H(X)=0, so MI(X,X)/H(X)=0/0 → 0.0 by convention | Skip diagonal check for columns where diagonal is 0.0 |

---

## User Feedback on Work Quality

User directly called out the pattern of shipping features that don't work end-to-end, only discovering issues when they tested and reported back. Specifically:

- CSV download button described as "filtered/cleaned data" but only re-downloaded the original file.
- Distribution capture "fixed" twice before the actual root cause was found.
- PDF approach shipped without tracing what `window.print()` on a glassmorphism UI would actually produce.

**Resolution going forward:** Before marking something done, trace the full user-facing outcome end-to-end — not just whether the code compiles and tests pass.

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
- Chart capture: relayout (resize + dark bg) → toImage → relayout-restore in **separate** try blocks
- PDF: open blob URL in new tab, no `window.print()` in code
- Cleaned CSV download: deferred — needs backend endpoint, build only when use case defined (see `project_cleaned_csv.md` memory)
- New tests go in `test_eda.py` with bug ID reference in docstring

---

## Remaining Work

| Item | Notes |
|---|---|
| Portfolio animations (items 14–25, Part 28) | Not yet started |
| EDA microservice extraction | Deferred until feature set is stable |
| Frontend automation (Playwright) | Bug log in `EDA_Bug_Log.md` is the spec |
| Cleaned CSV download | Deferred until use case defined |
