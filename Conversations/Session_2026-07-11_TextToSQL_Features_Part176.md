# Session: Text-to-SQL Feature Sprint — Part 176
**Date:** 2026-07-11
**Branch:** main
**Repos:** ml-portfolio (`src/app/tools/text-to-sql/`)

---

## Summary

Completed multi-tab results (interrupted from Part 175), fixed Ask button bug, then implemented all 10 suggested improvements to text-to-sql in order.

---

## Bug Fixes

### Multi-tab results: Ask button did nothing (`08637f1`)
**File:** `QuestionInput.tsx`

`onClick={onSubmit}` passed the React `SyntheticEvent` as the first argument to `runQuery`, so `questionOverride` received a MouseEvent object. Then `.trim()` threw `TypeError: t.trim is not a function`. Fixed: `onClick={() => onSubmit()}`.

Discovered via Playwright → browser console → `TypeError: t.trim is not a function`.

### SQL Explain: hallucinated "no results" (`e902a3d`)
**File:** `QueryResultPanel.tsx`

`fetchSqlExplanation` was passing `columns: []` and `rows: []`. The LLM saw no data and said "there are no results to display." Fixed: pass `results?.columns ?? []` and `results?.rows?.slice(0, 5) ?? []`.

### MD export: silent clipboard failure (`06cf941`)
**File:** `QueryResultPanel.tsx`

`navigator.clipboard.writeText()` silent fails without user feedback. Changed MD button to use `downloadFile()` like CSV/JSON — downloads `results.md` directly.

---

## Features Completed

### Multi-tab results (`d3c7237`)
**Files:** `TextToSqlRunner.tsx` (rewrite), `QuestionInput.tsx` (new)

Replaced single result state with `tabs: ResultTab[]` + `activeTabId`. Each question spawns a new tab (max 5, oldest unpinned evicted). Each tab holds its own SQL, results, pagination, filter, and editor state. SSE `patchTab(id, patch)` updates correct tab even if user switches tabs mid-stream.

### Collapsible history panel + SQL structure explanation (`eb20071`)
**Files:** `QueryHistoryPanel.tsx`, `QueryResultPanel.tsx`

- History: collapsed by default, chevron toggle, 340px scrollable
- SQL card: "Explain" button calls `/sql/explain` with result data → explains JOIN/GROUP BY structure inline inside the SQL card; separate from result-data explanation at bottom

### Clickable suggestion pills (`eb15186`)
**File:** `QueryResultPanel.tsx`

"You might also ask" chips changed from `<span>` to `<button>`. Clicking fires the suggested question as a new query and updates the question input. Added `onSuggest?: (q: string) => void` prop.

### MD table export + tab state persists (`955f3f5`)
**Files:** `QueryResultPanel.tsx`, `TextToSqlRunner.tsx`

- MD button downloads `results.md` markdown table
- Tabs and activeTabId saved to `sessionStorage` on every change; restored on mount

### Column sort — click header (`d7344ca`)
**File:** `QueryResultPanel.tsx`

Click any column header to sort asc/desc client-side. ↕ on hover, ↑/↓ when active. `sortCol` and `sortDir` state. Resets on new results. Sorts numbers numerically, strings lexicographically, nulls last.

### Chart type selector pills (`d7344ca`)
**File:** `SqlChart.tsx`

Row of 8 type pills below chart header (Bar, H-Bar, Grouped, Line, Area, Scatter, Donut, Stat). Clicking overrides auto-detected type. Shows "manual" vs "auto" badge, "reset" link to restore auto. Override resets on new query.

### Schema autocomplete while typing (`4a9821c`)
**File:** `QuestionInput.tsx`

Dropdown after 2 chars matching any table/column name from schema. Tab to complete, ↑↓ navigate, Esc dismiss. Each suggestion shows "table" or "col" badge. Resets on schema change.

### Keyboard shortcuts + pinnable tabs + TabBar extraction (`251918f`)
**Files:** `TextToSqlRunner.tsx`, `TabBar.tsx` (new)

- `Ctrl/Cmd+K` focuses question input
- `Ctrl/Cmd+Enter` runs query globally (uses `runQueryRef` to avoid stale closure)
- Tab chips have star pin button (hover to reveal); pinned tabs exempt from 5-tab eviction
- `TabBar.tsx` extracted to keep TextToSqlRunner under 400 lines

### SQL diff view (`b94d84a`)
**Files:** `QueryResultPanel.tsx`, `_utils.tsx`

"Edited · diff" badge is now clickable — shows red/green line diff between original AI SQL and current edits. `SqlDiff` component extracted to `_utils.tsx`. Resets on new query.

### Query templates + similar past queries (`329ee4f`)
**Files:** `DesktopSidebar.tsx`, `QuestionInput.tsx`

- Templates: collapsible sidebar section with 6 parameterised queries ("Top [N] [column] by [metric]" etc.); clicking fills input
- Past queries: autocomplete dropdown now includes matching history from localStorage (`ml_sql_fewshot`) when ≥3 chars typed; clicking replaces entire question

### First-time walkthrough (`56695a1`)
**Files:** `WalkthroughTooltip.tsx` (new), `TextToSqlRunner.tsx`, `QuestionInput.tsx`, `DesktopSidebar.tsx`, `DbConnectPanel.tsx`

6-step spotlight tour for first-time visitors:
1. Ask in plain English (question input)
2. Pick AI provider
3. Explore schema sidebar
4. Sample questions
5. Connect your own DB
6. You're ready

CSS mask creates hole in dark overlay at target element. Indigo pulse ring animates around highlighted element. Skip / Back / Next / Done. Dismissed state saved to `localStorage.ml_sql_walked`.

---

## Commits

| Hash | Description |
|------|-------------|
| `d3c7237` | feat(sql): multi-tab results |
| `08637f1` | fix(sql): Ask button MouseEvent bug |
| `eb20071` | feat(sql): collapsible history + SQL explain button |
| `eb15186` | feat(sql): clickable suggestion pills |
| `955f3f5` | feat(sql): MD export + tab persistence |
| `e902a3d` | fix(sql): SQL explain hallucination fix |
| `06cf941` | fix(sql): MD export downloads file |
| `d7344ca` | feat(sql): column sort + chart type selector |
| `4a9821c` | feat(sql): schema autocomplete |
| `251918f` | feat(sql): keyboard shortcuts + pinnable tabs + TabBar |
| `b94d84a` | feat(sql): SQL diff view |
| `329ee4f` | feat(sql): query templates + past query matching |
| `56695a1` | feat(sql): first-time walkthrough |

---

## File Sizes (end of session)

| File | Lines |
|------|-------|
| `TextToSqlRunner.tsx` | 394 |
| `QueryResultPanel.tsx` | 385 |
| `SqlChart.tsx` | 373 |
| `QuestionInput.tsx` | 173 |
| `TabBar.tsx` | 55 |
| `WalkthroughTooltip.tsx` | 118 |
| `DesktopSidebar.tsx` | 115 |
| `QueryHistoryPanel.tsx` | 103 |
| `_utils.tsx` | 87 |

---

## Skipped

**#9 Result pinning** — pin a row value into the next question. Deferred due to complexity of state threading across components.
