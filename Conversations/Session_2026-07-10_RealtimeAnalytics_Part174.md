# Session: Real-Time Analytics Dashboard — Part 174
**Date:** 2026-07-10  
**Branch:** main  
**Repos:** ML-Unified (`services/ml-analytics/`) + ml-portfolio (`src/app/`, `src/hooks/`, `src/components/`)

---

## Summary

Designed and built a full-stack real-time analytics dashboard that tracks live usage of the ml-portfolio site. Events (page views, tool opens) are captured from every page via a fire-and-forget hook, stored in Supabase PostgreSQL, and pushed to the dashboard live via Supabase Realtime WebSocket subscriptions — no polling.

---

## Architecture (Final)

```
Any page on ml-portfolio (Vercel)
   ↓  useAnalytics hook → POST /api/track  (Next.js API route, serverless)
      → inserts row into Supabase PostgreSQL (service role key, server-side)
         → Supabase Realtime broadcasts INSERT via WebSocket
            → AnalyticsDashboard receives payload.new
               → feed, charts, stat cards update instantly
```

No separate HF Space needed — backend runs entirely as Vercel serverless functions.

---

## Supabase Setup (Manual Steps Completed by User)

```sql
CREATE TABLE events (
  id         BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  type       TEXT NOT NULL,
  path       TEXT DEFAULT '',
  session_id TEXT DEFAULT '',
  country    TEXT DEFAULT '',
  referrer   TEXT DEFAULT '',
  meta       JSONB DEFAULT '{}'
);
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_insert" ON events FOR INSERT WITH CHECK (true);
CREATE POLICY "allow_select" ON events FOR SELECT USING (true);

-- Realtime
ALTER PUBLICATION supabase_realtime ADD TABLE events;
```

**Project:** AIRaML  
**Project URL:** `https://cwjmpbbpjquonleknhgl.supabase.co`  
**Region:** Northeast Asia (Tokyo)

---

## Files Created / Changed

### ML-Unified (commit `b667022`)
| File | Action |
|------|--------|
| `services/ml-analytics/app.py` | New — FastAPI app with asyncpg pool (kept as reference) |
| `services/ml-analytics/Dockerfile` | New |
| `services/ml-analytics/requirements.txt` | New |
| `services/ml-analytics/routers/__init__.py` | New |
| `services/ml-analytics/routers/analytics.py` | New — /health, /track, /stats, /events/recent |

> Note: ml-analytics HF Space creation failed (free tier requires PRO for Docker Spaces). Backend was moved to Next.js API routes instead.

### ml-portfolio (commits `47cef9d`, `bf6706e`)
| File | Action |
|------|--------|
| `src/app/api/track/route.ts` | New — POST, inserts event via Supabase service role client |
| `src/app/api/stats/route.ts` | New — GET, aggregates today's events in JS |
| `src/app/api/events/recent/route.ts` | New — GET, last 50 events ordered by created_at |
| `src/app/tools/realtime-analytics/page.tsx` | New — page shell, ConstellationBackground, ACCENT=#10b981 |
| `src/app/tools/realtime-analytics/AnalyticsDashboard.tsx` | New — state, Realtime sub, layout |
| `src/app/tools/realtime-analytics/AnalyticsCharts.tsx` | New — Sparkline, TopPagesBar, TypeDonut (hand-rolled SVG) |
| `src/components/AnalyticsTracker.tsx` | New — fires page_view on every page |
| `src/hooks/useAnalytics.ts` | New — fire-and-forget POST /api/track with localStorage session UUID |
| `src/app/layout.tsx` | Updated — added `<AnalyticsTracker />` |
| `src/config/urls.ts` | Updated — added ML_ANALYTICS_API export |
| `src/data/capabilities.ts` | Updated — new dashboard card added |
| `package.json` | Updated — `@supabase/supabase-js` installed |

---

## Dashboard UI

```
┌─────────────────────────────────────────────────────────┐
│  [ ⬤ Active Now: N ]  [ Events Today: N ]  [ Types: N ] │
├──────────────────────┬──────────────────────────────────┤
│  Events/min sparkline│  Top Pages (horizontal bars)     │
├──────────────────────┼──────────────────────────────────┤
│  By Type (donut)     │  Live Feed (scrolling log)       │
└──────────────────────┴──────────────────────────────────┘
```

- All charts: hand-rolled SVG (no recharts), consistent with SqlChart.tsx pattern
- Realtime: `@supabase/supabase-js` `postgres_changes` channel subscription
- On INSERT: feed prepended, stat counts incremented, per_minute/top_pages/by_type updated incrementally

---

## Commits

| Hash | Repo | Description |
|------|------|-------------|
| `b667022` | ML-Unified | feat(ml-analytics): new real-time event ingestion microservice |
| `47cef9d` | ml-portfolio | feat(realtime-analytics): live event dashboard |
| `bf6706e` | ml-portfolio | refactor(analytics): move backend to Next.js API routes |

---

## Env Vars Needed in Vercel

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://cwjmpbbpjquonleknhgl.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | anon key from Supabase Settings → API Keys → Legacy tab |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role key (server-side only, never exposed to browser) |

---

## Key Decisions

- **No HF Space**: free tier blocks new Docker Spaces; moved to Next.js API routes on Vercel (free, serverless)
- **Aggregation in JS**: `/api/stats` fetches raw events and aggregates in JS — avoids complex SQL GROUP BY, fine for portfolio traffic volume
- **Relative `/api` paths**: dashboard and hook use `/api/track`, `/api/stats` directly — no `NEXT_PUBLIC_ML_ANALYTICS_URL` needed
- **Anonymous sessions**: `localStorage` UUID per browser — no auth required, no PII collected
- **Country via headers**: `CF-IPCountry` (Cloudflare) or `x-vercel-ip-country` (Vercel) — no IP logging

---

## Pending

- Add `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` to Vercel and trigger redeploy
- Test end-to-end: open dashboard → open another tab → confirm live feed updates
- Optionally add `tool_open` tracking to individual tool pages via `useAnalytics("tool_open", { tool: "text-to-sql" })`