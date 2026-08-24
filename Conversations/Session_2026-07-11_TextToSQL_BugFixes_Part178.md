# Session: Text-to-SQL Bug Fixes & Improvements — Part 178
**Date:** 2026-07-11
**Branch:** main
**Repos:** ml-portfolio (`src/app/tools/text-to-sql/`), ML-Unified (`services/ml-sql/`)

---

## Summary

Continued from Part 177. Fixed 4 bugs, improved UI, and added a full User Guide modal.

---

## Bug Fixes

### Bug 1 — Walkthrough tooltip clipped at bottom (Steps 4+)
**File:** `WalkthroughTooltip.tsx`

`cardPos()` computed position from the target element rect but never clamped to the viewport. Step 4 (`try-asking`) target sits near the bottom of the sidebar — tooltip rendered offscreen.

**Fix 1 (`48f7267`):** Added `clamp()` function that caps `top` and `left` within viewport bounds. Moved `cardPos` return type from `React.CSSProperties` to `{ top: number; left: number }`.

**Fix 2 (`617d5d2`):** `CARD_H` estimate was 170 — too low for the actual rendered card. Bumped to 210 and increased bottom margin from 8 to 20px.

---

### Bug 2 — Glossary showed Chinook placeholder after CSV upload
**Files:** `DesktopSidebar.tsx`, `MobileSidebar.tsx`

The glossary `<textarea>` had hardcoded placeholder text: `"revenue: sum of invoice totals\nLTV: lifetime value of customer"` — Chinook-specific terms that showed whenever the field was empty, including after switching to a CSV upload.

**Investigation:** Fetched the deployed JS bundle (`1d0c-864mmxmf.js`) and confirmed `setGlossary("")` (minified as `A("")`) IS called in the upload callback. The field was empty — it was the placeholder making it look like real content.

**Fix (`2e32841`):** Changed placeholder to generic: `"e.g. revenue: total of all sales\nLTV: lifetime value of a customer"`.

**Also added (belt-and-suspenders, `17aa721`):** Direct `setGlossary("")` call inside `uploadDb` and `connectRemote` callbacks (in addition to the existing `useEffect` on `dbRef` change).

---

### Bug 3 — ER Diagram useless for single-table CSV uploads
**Files:** `SchemaDiagram.tsx`, new `ColumnProfileView.tsx`

When a CSV is uploaded, it becomes 1 table with 0 relationships — the ER diagram canvas showed one lonely card on a black background with "1 tables · 0 relationships".

**Fix (`1667287`, `17aa721`):**
- Created `ColumnProfileView.tsx` — shown instead of the canvas when `names.length === 1 && foreign_keys.length === 0`
- `SchemaDiagram` is now a wrapper: checks condition, renders either `ColumnProfileView` or `SchemaDiagramCanvas` (inner component renamed to avoid hooks-after-conditional-return violation)
- Column Profile v1 (bland list) redesigned in `17aa721` to include:
  - Type-colored icons per column (TEXT=indigo, INTEGER=green, FLOAT=orange, DATE=cyan)
  - Color-coded type badges with matching bg tints
  - Type distribution summary bar (counts + proportional color bar)
  - Row numbers in left gutter
  - Hover highlight on rows
  - PK/FK badges with gold/indigo colors
  - Gradient header with table name pill

---

### Bug 4 — pg/MySQL/SQL Server pagination total count always -1
**Files:** `_execute.py`, `sql.py`

`count_rows_sqlite()` was only called for `stype == "sqlite"`. All remote DBs returned `total_count = -1`, breaking "Showing X of Y rows" pagination display.

**Fix (`74f94a0`):**
- Added `count_rows_remote(session, sql)` in `_execute.py` — uses `_count_sql()` (shared COUNT(*) wrapper) dispatched to `execute_pg / execute_mysql / execute_mssql`
- Updated all 3 call sites in `sql.py` (`/sql/page`, `/sql/filter`, `_run_pipeline`) to branch on `stype`:
  - `"sqlite"` → `count_rows_sqlite`
  - `"postgresql" | "mysql" | "mssql"` → `count_rows_remote`
  - everything else (duckdb) → `-1`
- HF Space uploaded: `routers/_execute.py`, `routers/sql.py`

---

## New Feature — User Guide Modal

**Files:** new `UserGuideModal.tsx`, `DesktopSidebar.tsx`
**Commit:** `909758e`

A scrollable modal accessible via a "User Guide" button at the bottom of the left sidebar. Covers all features:

| Section | Content |
|---|---|
| Getting Started | Walkthrough tour, question input, Surprise Me |
| Connecting Data | Chinook demo, file upload, remote DBs |
| AI Providers | Groq / Gemini / Cohere comparison |
| Working with Results | Table, sorting, pagination, filter, charts, export |
| Multi-Tab Workflow | Pin, close, persistence, question sync |
| SQL Panel | View, copy, edit & re-run |
| AI Explanation | Explain button, follow-up suggestions |
| Schema & Glossary | Schema panel, ER diagram / Column Profile, Glossary |
| History & Saved | Session history, localStorage saved queries |
| Keyboard Shortcuts | ⌘Enter, ⌘K |
| Tips & Tricks | 6 practical tips |

---

## Rate Limit Investigation

User showed a screenshot of the rate limit error — confirmed it was from the Playwright testing session (back-to-back queries across all 3 providers in Part 177). Nothing fires LLM calls automatically in the codebase.

---

## Feature Ideas Researched (web search agent)

6 mind-blowing text-to-SQL features found via research:

| # | Feature | Source | Hard? |
|---|---|---|---|
| 1 | Ambiguity Clarification (AmbiSQL) | arxiv 2025 — 42%→92% accuracy jump | Medium |
| 2 | Streamed Chain-of-Thought reasoning panel | Novel UX — nothing in Metabase/Looker does this | Medium |
| 3 | Column Lineage Graph | `sqllineage` lib + D3 DAG | Medium |
| 4 | Query Fingerprinting & drift warnings | Select Star concept | Easy-Medium |
| 5 | Auto-Insights (anomaly scan on results) | Databricks Genie direction | Easy-Medium |
| 6 | Semantic Diff ("what changed?") | CDC tool concept, novel for text-to-SQL | Medium |

Recommended build order: 5 → 2 → 3.

---

## Commits

| Hash | Repo | Description |
|---|---|---|
| `48f7267` | ml-portfolio | fix(sql): clamp walkthrough tooltip within viewport |
| `617d5d2` | ml-portfolio | fix(sql): increase walkthrough CARD_H and bottom margin |
| `1667287` | ml-portfolio | fix(sql): glossary clear on db switch + column profile view for CSV |
| `17aa721` | ml-portfolio | fix(sql): redesign column profile; belt-and-suspenders glossary clear |
| `2e32841` | ml-portfolio | fix(sql): replace Chinook-specific glossary placeholder with generic text |
| `909758e` | ml-portfolio | feat(sql): User Guide modal with full feature documentation |
| `74f94a0` | ML-Unified | fix(ml-sql): count_rows_remote for pg/mysql/mssql pagination |

---

## File Sizes (end of session)

| File | Lines |
|---|---|
| `TextToSqlRunner.tsx` | 386 |
| `QueryResultPanel.tsx` | 388 |
| `SqlChart.tsx` | 359 |
| `SchemaDiagram.tsx` | 344 |
| `ColumnProfileView.tsx` | 95 (new) |
| `UserGuideModal.tsx` | 318 (new) |
| `DesktopSidebar.tsx` | 130 |
| `_types.ts` | 33 |
| `WalkthroughTooltip.tsx` | 128 |
| `_execute.py` (ml-sql) | ~185 |
