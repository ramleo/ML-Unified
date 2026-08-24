# Session: Analytics Dashboard Improvements — Part 185
**Date:** 2026-07-13
**Branch:** main
**Repo:** ml-portfolio (`src/app/tools/realtime-analytics/`)

---

## Summary

Continued from Part 184. Completed pending tracking items, added bounce rate + avg session duration stat cards, added time-per-tool in session trace, and designed mockups for two UI redesigns (session trace layout + live feed).

---

## Feature — tool_close Tracking + query_run success/duration (`9851727`)

### useAnalytics.ts
- Extracted shared `track()` helper to avoid repetition
- Added `useToolTracking(toolName)` hook:
  - Fires `tool_open` on mount
  - Fires `tool_close` with `duration_ms: Date.now() - t0` on unmount

### All 12 tool pages
Swapped `useAnalytics("tool_open", { tool: "..." })` → `useToolTracking("...")` via `sed`:
- ensemble, shap, text-to-sql, pipeline-cinema, feature-selection, realtime-analytics, automl, feature-engineering, drift, preprocessing, optuna, pipeline-builder

### TextToSqlRunner.tsx
- Added `t0 = Date.now()` before the SSE fetch
- `evt.type === "results"`: added `success: true, duration_ms: Date.now() - t0`
- `evt.type === "error"`: now fires `query_run` with `success: false, duration_ms`
- Previously: only fired on success, no `success` or `duration_ms` fields

---

## Fix — User Guide Button + Query Success Count (`584d939`, `7dabd98`)

- `i` icon circle → "User Guide" text pill (same style as range pills)
- API: return `query_success_count` + `query_total_count` alongside rate
- `StatCard`: added `sub?: string` prop — renders small line below main value
- Query Success card: shows `94%` + `47 / 50 queries` below
- Fixed condition: always show sub-line even when `0 / 0 queries`

---

## User Guide Clarification (`4e26829`)

User tested: visited preprocessing, FE, FS — query success stayed 0/0. Explained: `query_run` events only fire in Text-to-SQL. Updated user guide in three places:
- Query Success stat card description
- Conversion Funnel `query_run` row
- Events by Type `query_run` card

---

## Feature — Bounce Rate Stat Card (`51fc91b`)

**Definition:** sessions with exactly 1 event (landed and left, no further interaction)

### API
```ts
const sessionEventCount: Record<string, number> = {};
for (const e of events) if (e.session_id) sessionEventCount[e.session_id] = (sessionEventCount[e.session_id] ?? 0) + 1;
const sessionCounts = Object.values(sessionEventCount);
const bounceSessions = sessionCounts.filter(c => c === 1).length;
const bounce_rate = sessionCounts.length > 0 ? Math.round((bounceSessions / sessionCounts.length) * 100) : null;
```
Returns: `bounce_rate`, `bounce_session_count`, `total_session_count`

### Dashboard
- Grid: `grid-cols-3` → `grid-cols-2 lg:grid-cols-4`
- New card: "Bounce Rate" with `bounced / total sessions` sub-line

### Vercel deploy issue
- Commit `51fc91b` was 39 minutes old with CI 1/1 passing but Vercel still served old build
- Playwright DOM confirmed: `grid grid-cols-3` with 3 children (old code)
- Fix: pushed empty commit `91f25b1` to force redeploy

---

## Feature — Avg Session Duration Stat Card (`f54c17f`)

**Source:** mean `duration_ms` from `tool_close` events with `duration_ms > 0`

### API
- Added `duration_ms` to the Supabase select query
- Computed avg from `tool_close` events

### Dashboard
- `formatDuration(ms)`: `< 60s → "Xs"`, `>= 60s → "Xm Ys"`
- Grid: `grid-cols-2 lg:grid-cols-4` → `grid-cols-2 lg:grid-cols-5`
- New card: "Avg Duration" — shows `—` + "no tool_close data yet" until events arrive

### Final stat row (5 cards)
| Active Now | Total Events | Avg Duration | Bounce Rate | Query Success |

---

## Feature — Time per Tool in Session Trace (`f87c16a`)

When a session trace is opened, a "Time per Tool" row appears above the event cards.

### Logic
```ts
const toolTimes: Record<string, number> = {};
for (const ev of sessionEvs) {
  if (ev.type === "tool_close" && ev.duration_ms > 0) {
    const tool = String(ev.meta?.tool ?? ev.path ?? "unknown");
    toolTimes[tool] = (toolTimes[tool] ?? 0) + ev.duration_ms;
  }
}
```
- Renders purple pills per tool: `pipeline-cinema: 2m 31s | preprocessing: 14s | feature-engineering: 7s`
- Only renders when `tool_close` events with `duration_ms > 0` exist
- Added `fmtMs()` helper (same logic as `formatDuration` in dashboard)

---

## Design Research — UI Mockups (not yet implemented)

### Problem
- Session trace "Time per Tool" pills crammed into bottom strip look cluttered
- Live feed looks flat and hard to scan

### Research findings
From Smashing Magazine, Synergy Codes:
- Progressive disclosure: surface key metric first, drill on demand
- Horizontal bar chart > pills for proportional time data
- Left border strip by event type → instant visual scanning
- Avoid animating every change; only highlight what matters

### Option A — Side Drawer
Right panel (260px) overlays dashboard. Sections:
1. Session ID header
2. **Time per Tool** — stacked total bar at top + individual proportional bars per tool
3. **Event Path** — clean vertical timeline with dots and connector lines

### Option B — Full-Width Card
Card inserted between stat row and sparkline:
- Left column (200px): Time per Tool bars
- Right column: horizontal event path (scrollable)

### Live Feed Redesign
| Feature | Current | Redesigned |
|---|---|---|
| Event type | Small dot + monospace text | Colored pill badge |
| Row separator | Flat border | 3px left border strip in event color |
| Session highlight | Green trace button only | Full row tint + green session ID + green trace |
| Path | Monospace, same weight | Lighter color, cleaner mono |

Both mockups shown in Playwright via local HTTP server (`python3 -m http.server 9988`).

**Decision pending** — user has not chosen between Option A and B yet.

---

## Commits

| Hash | Description |
|------|-------------|
| `9851727` | feat: tool_close tracking + query_run success/duration_ms |
| `584d939` | fix: User Guide text button + query success count display |
| `7dabd98` | fix: always show query count sub-line even when 0/0 |
| `4e26829` | docs: clarify query_run is text-to-sql only in user guide |
| `51fc91b` | feat: bounce rate stat card |
| `91f25b1` | chore: force vercel redeploy for bounce rate |
| `f54c17f` | feat: avg session duration stat card |
| `f87c16a` | feat: time per tool summary in session trace panel |

---

## File Sizes (end of session)

| File | Lines |
|------|-------|
| `AnalyticsDashboard.tsx` | ~352 |
| `AnalyticsSessionPanel.tsx` | ~145 |
| `AnalyticsCalendar.tsx` | 94 |
| `AnalyticsUserGuide.tsx` | ~305 |
| `AnalyticsCharts.tsx` | 227 |
| `/api/stats/route.ts` | ~163 |
| `useAnalytics.ts` | ~40 |

---

## Pending / Next

### Design decisions awaiting user input
- Session trace: Option A (side drawer) vs Option B (full-width card)
- Live feed: confirm redesign direction before implementing

### Analytics backlog
- **Live feed filters** — filter by event type or country
- **Per-tool success rate** — break down query SR by tool page
- **CSV export**

### Other
- `text-to-sql-demo` HF Space: `GOOGLE_API_KEY` now set (user confirmed via screenshot)
- `AnalyticsDashboard.tsx` is approaching 350 lines — modularize before next large feature
