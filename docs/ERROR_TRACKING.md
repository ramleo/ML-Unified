# Error Tracking

Two complementary systems answer "why did it break, and where": a **DIY
first-party error store** (our own, on Supabase) and **hosted Sentry** (optional,
richer). Both are content-free per [LOGGING_SPEC.md](LOGGING_SPEC.md) §6 and both
run alongside the content-free `error` event already in the `events` table (which
stays the in-dashboard volume metric).

## Why two

- The frontend `error` event logs only a class name; the backend had **no global
  exception handler** — unhandled errors reached only the Space's ephemeral
  stdout (wiped on restart). Neither was enough to root-cause a fault.
- **Sentry** is the deepest tool (grouping, breadcrumbs, alerts) but is a third
  party and needs an account. **The DIY store** is fully ours, on infrastructure
  we already run at $0, and survives Space restarts. We keep both; the DIY store
  is primary, Sentry is a bonus that can stay dormant.

## DIY error store (primary)

**Data path.** One shared endpoint, `ml-portfolio/src/app/api/error/route.ts`:
- `POST` ingests one error. Used by **both** the browser and the backend — the
  backend posts here (default `SITE_URL=https://ml-portfolio-rho.vercel.app`)
  rather than holding the Supabase service-role key on the public HF Space.
- `GET` returns grouped faults for the dashboard via the `error_groups` RPC.

**Storage.** `ml-portfolio/supabase/errors.sql` — table `public.errors`
(`source`, `kind`, `message`, `route`, `fingerprint`, `stack`, `session_id`,
`meta`, `created_at`) + the `error_groups(p_start, p_end)` RPC that groups by
`fingerprint` server-side (never pages raw rows to JS). **Must be run once in the
Supabase SQL editor** — until then `/api/error` returns `needs_setup` and the
dashboard panel shows a hint.

**Capture.**
- Frontend: `useErrorTracking()` in `src/hooks/useAnalytics.ts` (mounted in
  `AnalyticsTracker`) — `window.error` + `unhandledrejection` → POST `/api/error`
  with `{kind, message, stack, route, session_id}`. Coalesced 1/s; password page
  excluded; query string stripped from the route.
- Backend: `security/error_reporting.py` `error_capture_dispatch` middleware
  (added **first** in `app.py`, so innermost) catches an unhandled router
  exception, best-effort POSTs it to `/api/error` (`source:"backend"`, 2s
  timeout, coalesced), then **re-raises** so Sentry and the default 500 still
  apply. Backend stack traces are full/readable.

**Read.** `AnalyticsErrors.tsx` in `realtime-analytics` — one row per distinct
fault, ranked by count, with the page, a sample message, and "last seen". Warm-red
accent marks it as the problems panel. Wired into `AnalyticsDashboard`.

**Fingerprint** = `source:kind:route` (computed in the route). Same fault on the
same page groups into one row regardless of who reported it.

## Hosted Sentry (optional, dormant until DSN set)

- Frontend: `@sentry/nextjs` via Next 16 native instrumentation hooks
  (`src/instrumentation*.ts`, `src/sentry.*.config.ts`). No `withSentryConfig`
  wrapper (v11 doesn't export it cleanly; it's only needed for source-map upload,
  which needs an auth token) — so **frontend stack traces are minified** in Sentry
  until source maps are added later.
- Backend: `sentry-sdk[fastapi]`; `init_error_reporting()` in `app.py` before app
  creation → FastAPI integration auto-captures unhandled exceptions.
- Both: no Session Replay, no tracing, `beforeSend`/`before_send` strips the user
  object (IP) + request body/cookies/headers.
- **Activate:** set `NEXT_PUBLIC_SENTRY_DSN` (Vercel) and `SENTRY_DSN` (HF Space
  secret), then redeploy. No DSN = complete no-op.

## Content-safety (both systems)

Stored/sent: the error class, message, stack, the route (query stripped), the
browser, and (frontend) the analytics `session_id` so a fault links to the
`events` table. **Never** stored/sent: request bodies, cookies, IP, uploaded or
typed content, or a DOM recording. Exception **messages are kept** (they make a
trace debuggable) — the one residual: a message a developer wrote could embed
user text; scrub a specific one if it ever does. `password-audit` is excluded
entirely. Privacy page discloses both (first-party store in the logging section,
Sentry in third-parties).

## Setup checklist

1. **DIY (required to see data):** run `ml-portfolio/supabase/errors.sql` in the
   Supabase SQL editor once.
2. **Sentry (optional):** create 2 Sentry projects (Next.js + Python), set
   `NEXT_PUBLIC_SENTRY_DSN` (Vercel) + `SENTRY_DSN` (HF secret), redeploy.
