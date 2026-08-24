# Session: Text-to-SQL Improvements + Analytics — Part 175
**Date:** 2026-07-11
**Branch:** main
**Repos:** ML-Unified (`services/ml-sql/`) + ml-portfolio (`src/app/tools/text-to-sql/`, `src/hooks/`, analytics)

---

## Summary

Bug fixes and feature additions across text-to-sql and the realtime analytics dashboard. Confirmed analytics dashboard live after Vercel env vars were added.

---

## Fixes

### LIMIT respected in paginated queries (`be020bb`)
**File:** `services/ml-sql/routers/_execute.py`

`paginate_sql()` was stripping the user's `LIMIT N` before wrapping with `LIMIT page_size (50)`. Added `_extract_user_limit()` and `_strip_limit()` helpers. Now uses `min(user_limit, page_size)` as effective limit. Also fixed `_count_sql()` to wrap inner query in the user's LIMIT so the row badge reflects the correct count.

### All chart types capped at 200px (`f82c182`, `c89190d`, `facf759`)
**File:** `src/app/tools/text-to-sql/SqlChart.tsx`

All SVG charts used `w-full` causing them to scale to full card width (very tall). Applied `style={{maxHeight:"200px"}}` to Bar, GroupedBar, LineArea, Scatter. Reduced horizontal bar container from `max-h-[420px]` → `max-h-[260px]` and row height 16→12. Donut: radius 74→56, viewBox 340×192→290×155, `maxHeight:"180px"`.

---

## Features

### Manual SQL editor with Edited badge (`c561468`)
**Files:** `QueryResultPanel.tsx`, `TextToSqlRunner.tsx`, `_utils.tsx` (new), `DesktopSidebar.tsx` (new)

- **Edit** button in the Generated SQL panel header toggles an editable `<textarea>` 
- **Done** collapses back to syntax-highlighted view
- **Amber "Edited" badge** appears on first keystroke that diverges from AI-generated SQL
- **"Run edited SQL" button** re-executes via `/sql/page`, updates results in place
- Resets on new AI query (new `generatedSql` prop → `useEffect` resets editor state)
- `onRunSQL` prop added to `QueryResultPanel`; `runDirectSQL` callback added to `TextToSqlRunner`

**Analytics tracking:** First diverging edit fires `fetch("/api/track", { type: "sql_edited" })` fire-and-forget.

**Modularization (both files were >350 lines):**
- Extracted `_utils.tsx`: `highlightSQL`, `formatCell`, `cleanErr`, `csvEscape`, `downloadFile`, `exportNotebook`
- Extracted `DesktopSidebar.tsx`: desktop aside (schema, try-asking, glossary, saved queries panels)
- Result: QueryResultPanel 362→299 lines, TextToSqlRunner 395→367 lines

### `tool_open` tracking on all 12 tool pages (`6a2350f`)
**Files:** All `src/app/tools/*/page.tsx`

Added `import { useAnalytics } from "@/hooks/useAnalytics"` and `useAnalytics("tool_open", { tool: "<name>" })` to every tool page. Fires on mount, fire-and-forget.

### `query_run` tracking on every successful SQL execution (`2478f8a`)
**File:** `TextToSqlRunner.tsx` line 167

On `evt.type === "results"` in the SSE loop, fires `POST /api/track` with `type: "query_run"`, row count, and provider in meta.

---

## Analytics Dashboard Confirmed Live

After user added Vercel env vars (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`), Playwright confirmed the dashboard at `/tools/realtime-analytics` is live. Live feed showed real events including a `sql_edited` event from India.

**4 event types now tracked:**

| Event | Where |
|-------|-------|
| `page_view` | Root layout (every page load) |
| `tool_open` | Every tool page mount |
| `query_run` | Successful SQL execution (with row count + provider) |
| `sql_edited` | First manual edit of AI-generated SQL |

---

## Commits

| Hash | Repo | Description |
|------|------|-------------|
| `be020bb` | ML-Unified | fix(ml-sql): respect user LIMIT in paginated queries |
| `facf759` | ml-portfolio | fix(sql-chart): shrink donut chart |
| `c89190d` | ml-portfolio | fix(sql-chart): cap donut chart height at 180px |
| `c561468` | ml-portfolio | feat(sql): manual SQL editor with Edited badge + analytics |
| `6a2350f` | ml-portfolio | feat(analytics): tool_open tracking on all 12 tool pages |
| `f82c182` | ml-portfolio | fix(sql-chart): cap all chart heights at 200px |
| `2478f8a` | ml-portfolio | feat(analytics): query_run event on successful SQL execution |

---

## In Progress (interrupted)

**Multi-tab results** for text-to-sql — started but not completed:
- `QuestionInput.tsx` was created (extracted from TextToSqlRunner, ~75 lines)
- TextToSqlRunner rewrite was in progress: replacing `generatedSql/results/error/currentPage/totalCount/activeFilter` + refs with `tabs: ResultTab[]` + `activeTabId`
- Plan: max 5 tabs, each with own SQL/results/pagination/filter state; tab bar UI above QueryResultPanel; `patchTab(id, patch)` helper for SSE updates

### ResultTab interface (planned)
```ts
interface ResultTab {
  id: string;
  question: string;
  sql: string | null;
  currentSql: string | null;
  originalSql: string | null;
  results: { columns: string[]; rows: unknown[][]; count: number; exec_time_ms: number } | null;
  error: string | null;
  currentPage: number;
  totalCount: number;
  activeFilter: string | null;
}
```

### Files created but not yet committed
- `src/app/tools/text-to-sql/QuestionInput.tsx` — extracted question card + provider select + pipeline status + share button

---

## Saved Queries Note

Saved queries are **already persistent** via localStorage (`KEY = "ml_sql_saved"`, max 20). No work needed.
