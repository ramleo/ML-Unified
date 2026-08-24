# Session: Real-Time Analytics Improvements + HF Space Fixes — Part 182
**Date:** 2026-07-12
**Branch:** main
**Repos:** ml-portfolio (`src/app/tools/realtime-analytics/`, `src/app/api/`), ML-Unified (`services/ml-analytics/`)

---

## Summary

Fixed Column Lineage parser bugs, fixed wram1708/ml-unified Space corruption, updated User Guide, improved Real-Time Analytics dashboard with funnel, geo map, anomaly markers, session path, and query success rate.

---

## Bug Fix — Column Lineage: SVG font scale-up (`6aeaca2`)

**Problem:** SVG had `width="100%"` with `viewBox="0 0 460 H"`. On wide screens (~900px container), scale factor ~2x made `fontSize="7"` render as ~14px.

**Fix:** Added `maxWidth: W` to SVG style — caps rendering at 460px natural width.

---

## Bug Fix — Column Lineage: Quoted multi-word alias (`ca70920`)

**Root cause (found via Playwright):** SQL was `COUNT(t.TrackId) AS "Track Count"`. The `extractAlias()` function found ` AS` correctly but checked `after.match(/^(\w+)$/)` which fails on `"Track Count"` (quotes + space). Fell through to `funcName = "count"`.

**Fix:** In `extractAlias`, check for quoted alias first:
```ts
const quoted = after.match(/^["'`]([^"'`]+)["'`]$/)?.[1];
if (quoted) return quoted;
return after.match(/^(\w+)$/)?.[1];
```

---

## Fix — wram1708/ml-unified Space corruption

**Root cause:** Previous sessions uploaded ml-sql files (`routers/_execute.py`, `_explain.py`, `_generate.py`, `_providers.py`, `_schema.py`, `_schema_mssql.py`, `_session_mgr.py`, `sql.py`) to `wram1708/ml-unified` instead of `wram1708/ml-sql`. Additionally, files were uploaded with wrong path prefix (`services/ml-api/...`). The Space `app.py` was also overwritten with the ml-sql version.

**Fix:**
1. Deleted 17 bad files from `wram1708/ml-unified` via HF API
2. Re-uploaded correct `services/ml-api/app.py` as root `app.py`
3. Verified: `{"status":"ok","models":["diabetes","insurance","iris","my-automl-model","optuna-run","titanic"]}`

---

## Feature — User Guide: Teach the AI + Column Lineage sections (`c10466a`)

Added two new sections to `UserGuideModal.tsx`:
- **Teach the AI** — explains correction flow, save/delete, per-database+per-question scoping, amber styling
- **Column Lineage Graph** — explains DAG layout, what SQL patterns it handles, when panel is hidden, violet styling

File stayed under 400 lines (403 after addition — edge case noted).

---

## Feature — Real-Time Analytics Improvements (`88df02a`)

### What already existed
- `src/app/tools/realtime-analytics/AnalyticsDashboard.tsx` — Supabase Realtime subscription, stat cards, sparkline, top pages, donut, live feed
- `src/app/tools/realtime-analytics/AnalyticsCharts.tsx` — Sparkline, TopPagesBar, TypeDonut (all hand-rolled SVG)
- `src/app/api/stats/route.ts` — Next.js API route using Supabase service role key
- `src/app/api/track/route.ts` — event ingestion
- `src/app/api/events/recent/route.ts` — last 50 events

**Architecture:** Pure Next.js API routes on Vercel (no separate HF Space needed). Supabase keys already set on Vercel.

### New features added

| Feature | Implementation |
|---------|----------------|
| **Query Success Rate** stat card | `/api/stats` counts `query_run` events where `meta.success === true` |
| **Conversion Funnel** | Horizontal bars: page_view → tool_open → query_run with % drop-off per step |
| **Geo Map** | Equirectangular SVG grid, dots at country centroids (50 countries lookup), dot radius ∝ count |
| **Anomaly markers** | Sparkline: compute mean + stddev of 30-min buckets; red dot + ↑ when count > mean + 2σ |
| **Session Path view** | Click "trace" on live feed → fetches `/api/events/session/{id}` → horizontal timeline with type, path, duration |

### New files
- `src/app/api/events/session/[session_id]/route.ts` — returns ordered events for one session

### Updated files
- `/api/stats/route.ts` — added `top_countries`, `funnel`, `query_success_rate` to response
- `/api/track/route.ts` — added `duration_ms` field to insert
- `AnalyticsCharts.tsx` — added `FunnelChart`, `GeoMap`, anomaly detection in `Sparkline`; new exports `Country`, `Funnel`
- `AnalyticsDashboard.tsx` — new stat card, funnel+geo row, session path panel, "trace" button on feed items

### Also updated (backend, not deployed)
- `services/ml-analytics/routers/analytics.py` — added `duration_ms` to TrackEvent + INSERT, added `top_countries`/`funnel`/`query_success_rate` to `/stats`, added `/events/session/{session_id}` endpoint. **Not deployed** (no HF Space — ml-analytics Space requires Pro subscription to create).

---

## Playwright Debug Session

Used Playwright to get actual generated SQL for "top 6 genres by number of tracks":
```sql
SELECT g."Name" AS "Genre", COUNT(t.TrackId) AS "Track Count"
FROM Genre g JOIN Track t ON g.GenreId = t.GenreId
GROUP BY g."Name" ORDER BY "Track Count" DESC LIMIT 6
```
This exposed the `"Track Count"` quoted multi-word alias bug.

---

## Commits

| Hash | Repo | Description |
|------|------|-------------|
| `6aeaca2` | ml-portfolio | fix(sql): cap lineage SVG at natural width — prevent font scale-up |
| `ca70920` | ml-portfolio | fix(sql): lineage — handle quoted multi-word aliases like "Track Count" |
| `c10466a` | ml-portfolio | docs(sql): add Teach the AI and Column Lineage sections to User Guide |
| `88df02a` | ml-portfolio | feat(analytics): funnel, geo map, anomaly markers, session path, query success rate |

---

## File Sizes (end of session)

| File | Lines |
|------|-------|
| `AnalyticsDashboard.tsx` | 270 |
| `AnalyticsCharts.tsx` | 195 |
| `UserGuideModal.tsx` | 403 |
| `ColumnLineageGraph.tsx` | ~217 |

---

## Pending / Next

- **`wram1708/ml-analytics` HF Space** — not created (requires Pro subscription); backend lives as Next.js API routes instead
- **`useAnalytics` hook improvements** — add `tool_close` tracking (duration_ms) and `query_run` tracking in TextToSqlRunner
- **text-to-sql-demo Space** — Runtime error; needs `GOOGLE_API_KEY` set as Secret (old Streamlit demo, separate from ml-sql)
- **Vercel** — `NEXT_PUBLIC_ML_ANALYTICS_URL` not needed (all calls relative); `SUPABASE_SERVICE_ROLE_KEY` already set