# Session: Analytics Dashboard — Part 186
**Date:** 2026-07-14
**Branch:** main
**Repo:** ml-portfolio (`src/app/tools/realtime-analytics/`)

---

## Summary

Continued from Part 185. Redesigned the live feed (data + visual), replaced the session trace bottom bar with a right-side drawer, cleared the analytics backlog (live feed filters, per-tool SR, CSV export), and updated the User Guide.

---

## Feature — Live Feed Redesign (`e8dadc0`)

### New file: `AnalyticsLiveFeed.tsx`
Extracted from `AnalyticsDashboard.tsx` to keep Dashboard under 400 lines.

### Data improvements
- Fixed-width 86px type badges — all rows align in a clean grid
- `/tools/` prefix dimmed (`#2d3748`), tool name bright (`#94a3b8`)
- Duration chip (`2m 31s`) shown on `tool_close` rows
- Session ID bumped to `#4b5563` (readable, not near-invisible)
- Trace button hidden until row hover (`group-hover:opacity-100`)
- Session ID itself is clickable to trace (not just the trace button)
- Added `duration_ms` to `FeedEvent` interface + `/api/events/recent` select

### Visual upgrades
- Gradient border + inset box-shadow for card depth
- "LIVE FEED" header text: emerald → indigo gradient
- Double-ring sonar pulse instead of flat animated dot
- 3px left type-color strip per row; active session rows get a strip glow
- Active session rows tinted `rgba(16,185,129,0.055)`
- New events slide in from top (`feedIn` keyframe, 0.2s)

---

## Feature — Session Trace → Right-Side Drawer (`0716caa`)

Replaced the full-width `fixed bottom-0 left-0 right-0` panel with a 320px right-side drawer.

### Layout
- `fixed inset-0` container with blurred backdrop (`rgba(4,8,20,0.55)` + `backdrop-filter: blur(3px)`)
- Click outside or `✕` to close
- Drawer: `width: 320px`, gradient bg `#0b1220 → #080f1e`, emerald left border

### Time per Tool section (replaces purple pills)
- Proportional horizontal bars per tool, ordered by time spent
- Each bar: tool name (truncated mono), `%` share, formatted duration in purple
- Total "master" bar at top (full width, faint)

### Event Path section (replaces horizontal scroll cards)
- Vertical timeline: color dot + connecting spine line
- Each entry: event type (colored), duration chip for tool_close, tool name/path, timestamp
- No more collapsed groups — flat list

### Dead props removed
- `expandedGroups`, `setExpandedGroups`, `toggleGroup` removed from Dashboard
- `expandedGroups`, `onToggleGroup` removed from SessionPathPanel Props interface

---

## Feature — Live Feed Filters (`859d195`)

Added type + country filter pills to `AnalyticsLiveFeed.tsx`.

### Implementation
- `useState<string | null>` for `typeFilter` and `countryFilter`
- Unique types and countries derived from feed at render time
- Filter bar only renders when `types.length > 1 || countries.length > 1`
- Filtered feed passed to row renderer
- "All" pill resets both filters; clicking active pill also clears it
- Empty state: "No events match filter." vs "Waiting for events…"

---

## Feature — Per-Tool Query Success Rate (`859d195`)

### API (`/api/stats/route.ts`)
```ts
const toolMap: Record<string, { success: number; total: number }> = {};
for (const e of queryRuns) {
  const key = e.path ?? "unknown";
  if (!toolMap[key]) toolMap[key] = { success: 0, total: 0 };
  toolMap[key].total++;
  if (e.meta?.success === true) toolMap[key].success++;
}
const query_by_tool = Object.entries(toolMap)
  .map(([path, { success, total }]) => ({
    path, success_count: success, total_count: total,
    success_rate: Math.round((success / total) * 100),
  }))
  .sort((a, b) => b.total_count - a.total_count);
```

### Dashboard
- `query_by_tool` field added to `Stats` interface
- New section between Top Referrers and Donut+LiveFeed
- Horizontal bars color-coded: green ≥ 90%, amber 70–89%, red < 70%
- Section hidden entirely when `query_by_tool.length === 0`

---

## Feature — CSV Export (`859d195`)

### New route: `/api/events/export/route.ts`
- Same range logic as stats API (range preset or custom start/end)
- Selects: `id, created_at, type, path, session_id, country, duration_ms, meta`
- `meta` serialized as JSON string; values with commas/quotes CSV-escaped
- Ordered descending by `created_at`, limit 5000
- Returns `Content-Type: text/csv` + `Content-Disposition: attachment; filename="analytics-{range}-{date}.csv"`

### Dashboard
- "Export CSV" `<a download>` button added to toolbar (next to User Guide)
- `href` computed from active range: `/api/events/export?range={range}` or `?start=&end=`

---

## Docs — User Guide Update (`97fb46f`)

Updated `AnalyticsUserGuide.tsx`:

| Section | Change |
|---------|--------|
| Range Selector | Added Export CSV Feature entry |
| Live Feed | Rewrote: describes left strip, fixed badges, duration chip, filter pills, session ID as button |
| Session Trace | Rewrote: right-side drawer, Time per Tool bars, vertical timeline; removed stale collapsed-groups entry |
| Query Success by Tool | New section: documents green/amber/red bar chart |

---

## Commits

| Hash | Description |
|------|-------------|
| `e8dadc0` | feat(analytics): redesign live feed — data improvements + visual upgrades |
| `0716caa` | feat(analytics): session trace → right-side drawer with bar chart time-per-tool |
| `859d195` | feat(analytics): live feed filters + per-tool SR + CSV export |
| `97fb46f` | docs(analytics): update user guide for new features + remove dead props |

---

## File Sizes (end of session)

| File | Lines |
|------|-------|
| `AnalyticsDashboard.tsx` | ~327 |
| `AnalyticsLiveFeed.tsx` | ~175 |
| `AnalyticsSessionPanel.tsx` | ~155 |
| `AnalyticsUserGuide.tsx` | ~305 |
| `AnalyticsCharts.tsx` | 227 |
| `/api/stats/route.ts` | ~175 |
| `/api/events/recent/route.ts` | ~20 |
| `/api/events/export/route.ts` | ~62 |

---

## Pending / Next

Nothing pending. Analytics dashboard backlog fully cleared.

### If new work starts
- Dashboard is at ~327 lines — still has headroom before the 400-line modularization trigger
- Any future backend changes to `services/ml-api/**` require HF Space upload after push
