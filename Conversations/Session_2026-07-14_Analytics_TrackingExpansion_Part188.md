# Session: Analytics — Tracking Expansion, Modularization & Other Tools — Part 188
**Date:** 2026-07-14 (continued from Part 187)
**Branch:** main
**Repos:** ML-Unified, ml-portfolio

---

## Summary

Expanded the Real-Time Analytics tracking to capture 7 new event types/meta fields, added dedicated dashboard sections for all of them, fixed the Live Feed row expand bug, modularized three oversized files, updated the User Guide, and wired tracking into EnsembleRunner and DriftRunner.

---

## Tracking Additions

### New Events
| Event | Where fired | Meta |
|---|---|---|
| `error` | SQL query failure | `{ tool, error_type: "query_error", message }` |
| `error` | Ensemble analyze/train failure | `{ tool, error_type: "analyze_error" / "train_error" }` |
| `error` | Drift detection failure | `{ tool, error_type: "drift_error" }` |
| `export` | Analytics dashboard Export CSV click | `{ format: "csv", range }` |
| `copy` | SQL tool copy button | `{ tool: "text-to-sql", content_type: "sql" }` |
| `query_run` | Ensemble analyze success | `{ tool, action: "analyze", rows }` |
| `query_run` | Ensemble train success | `{ tool, action: "train", winner, score }` |
| `query_run` | Drift detect success | `{ tool, action: "detect_drift", features, high_drift }` |

### New Meta Fields on Existing Events
| Event | Field | Description |
|---|---|---|
| `query_run` | `model` | Specific model name mapped from provider (groq→llama-3.3-70b-versatile, openai→gpt-4o-mini, anthropic→claude-haiku-4-5) |
| `query_run` | `query_length` | Character count of the user's question |
| `query_run` | `rows` | Rows returned by the query |
| `tool_close` | `queries_run` | Total successful queries during the session |
| `page_view` | `device` | `"mobile"` or `"desktop"` from window.innerWidth |
| `page_view` | `returning` | bool — true if user has visited before (localStorage counter) |

---

## Stats API Additions (`src/app/api/stats/route.ts`)

| Field | Description |
|---|---|
| `provider_breakdown` | Query counts by provider from `query_run.meta.provider` |
| `error_count` | Count of `error` type events in range |
| `device_breakdown` | Page view counts by device from `page_view.meta.device` |
| `returning_pct` | % of page views from returning visitors |
| `avg_query_length` | Avg character count across `query_run` events |
| `avg_queries_per_session` | Avg `queries_run` from `tool_close` events |
| `export_conversion_pct` | % of sessions that ran a query AND exported CSV |

---

## New Dashboard Sections (`AnalyticsDashboard.tsx`)

| Section | Trigger |
|---|---|
| **AI Provider Usage** | Always visible; horizontal bar chart by provider |
| **Error Rate / SQL Copies / CSV Exports** | 3-col stat row, always visible |
| Device split | Sub-text on Active Now card: "4 desktop · 1 mobile" |
| Returning visitors % | Sub-text on Bounce Rate card: "25% returning" |
| Avg query length | Sub-text on Query Success card: "avg 45ch" |
| Avg queries/session | Sub-text on Avg Duration card: "3.2 queries/session" |
| Export conversion | Sub-text on CSV Exports card: "N% of query sessions exported" |

---

## Bug Fix: Live Feed Row Expand (`AnalyticsLiveFeed.tsx`)

- **Problem:** Clicking a feed row did nothing. Root cause: `expandedId` typed as `number | null`, but Supabase Realtime WebSocket events deliver `id` as a string (JSON bigint serialization), causing `expandedId === ev.id` to always fail.
- **Fix:** Changed expand key to `session_id + created_at` string (always present, always string). Commit `7267ec6`.

---

## Modularization

| File | Before | After | Extracted to |
|---|---|---|---|
| `TextToSqlRunner.tsx` | 420 lines | 201 lines | `useQueryRunner.ts` (259 lines) |
| `AnalyticsUserGuide.tsx` | 357 lines | 92 lines | `AnalyticsUserGuideSections.tsx` (313 lines) |
| `AnalyticsDashboard.tsx` | 391 lines | ~387 lines | `AnalyticsStatCard.tsx` (StatCard, SkeletonCard, formatDuration) |
| `AnalyticsCharts.tsx` | 302 lines | 332 lines | Added ProviderBreakdownBar |

### useQueryRunner.ts extracts:
All query execution state + callbacks from TextToSqlRunner: `question`, `running`, `status`, `retryMsg`, `copied`, `history`, `fewShot`, `tabs`, `activeTabId`, `activeTab`, `patchTab`, `closeTab`, `runQuery`, `runDirectSQL`, `copySQL`, `changePage`, `filterResults`, `clearFilter`.

---

## User Guide Updates (`AnalyticsUserGuideSections.tsx`)

New sections added to pill nav and content:
- **AI Provider** — bar chart explanation, groq/openai/anthropic color coding
- **Engagement** — Error Rate, SQL Copies, CSV Exports explained with interpretation note
- Updated: stat card sub-texts documented (device split, returning %, avg query length, avg queries/session)
- Updated: Event Detail Drawer — all meta fields listed (query_length, provider, model, success, rows, queries_run, device)
- Updated: Event Types — `meta.device` on page_view, `meta.query_length`/`model` on query_run, `meta.queries_run` on tool_close

---

## Commits

| Hash | Repo | Description |
|---|---|---|
| `4361a75` | ml-portfolio | All 7 tracking additions (provider breakdown, errors, device, returning, query_length, copy, export) |
| `6f8c486` | ml-portfolio | Fix: always show provider usage section and error count |
| `9f25950` | ml-portfolio | Error Rate / SQL Copies / CSV Exports section; avg query length + queries/session stats |
| `7267ec6` | ml-portfolio | Fix: live feed row expand (id type coercion bug) |
| `e1acac8` | ml-portfolio | Complete all tracking gaps + modularize + User Guide update + Ensemble/Drift events |

---

## Remaining / Deferred

| Item | Status | Notes |
|---|---|---|
| Device split donut chart | Deferred | Dashboard at 387 lines; donut would exceed 400 |
| Error rate over time (sparkline) | Deferred | Needs time-bucketed error data from API |
| ShapRunner.tsx tracking | Pending | File at 370 lines — needs modularization first |
| AutoML events | Pending | Training logic is inside AutoMLModal component |
| `model` breakdown chart | Partial | Provider breakdown exists; specific model name now captured in meta |
