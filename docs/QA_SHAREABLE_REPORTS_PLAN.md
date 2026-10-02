# Testwright R7 — Run reports: export, share & dashboard (plan)

**Status:** scoped, not built (2026-10-02). Part of the Phase 2 LATER tier in
`TESTWRIGHT_IMPROVEMENT_PLAN.md` §9. Build when a run worth sharing with someone
else is a real need.

## What it is
A **permalink to a finished run** that anyone with the link can open — status,
pass/fail summary, the failure reason, the step timeline, timing, and a link to the
GitHub run. Turns a result that today lives only in one browser into something you can
drop into a bug report, a PR, or a message. The same report can also be **downloaded
as Excel or PDF** (see Export), and many runs can roll up into a **Dashboard** of
trends (see Dashboard).

## Why it's wanted
Right now every run's results live only in the browser's `localStorage` (saved tests +
recent-runs history in `run/storage.ts`). Close the tab or switch devices and it's
gone; a teammate can't see "this test failed here" without re-running it. Shareable
reports are how Octomind/Mabl support team workflows.

## Key architectural finding — frontend-only
Durable writes in this project do **not** go through the HF Space (it holds no DB
credentials). They go through **Next.js API routes on Vercel** that hold
`SUPABASE_SERVICE_ROLE_KEY` (see `ml-portfolio/src/app/api/error/route.ts`, and the
backend even POSTs errors to `{SITE_URL}/api/error`). All the run data is already in
the browser's `useRun` state when a run finishes, so R7 needs **no backend / HF change
at all** — just:
- a Supabase table + SQL migration,
- two Next.js API routes (create share, read share),
- a read-only share page.

## Data model — `qa_shared_runs` (Supabase)
| column | type | notes |
|---|---|---|
| `id` | text PK | random unguessable id (~16 char base62) = the share token |
| `created_at` | timestamptz | default `now()` |
| `name` | text | test name (clipped) |
| `status` | text | `passed` / `failed` / `error` |
| `summary` | jsonb | `{expected, unexpected, flaky, skipped}` |
| `error_message` | text | clipped (reuse the backend's `MAX_ERROR_CHARS` ceiling) |
| `steps` | jsonb | step timeline, clipped to ~60 entries |
| `test_ms`, `total_ms` | int | timing (already shown on the result card) |
| `run_url` | text | GitHub run link |
| `code` | text, nullable | included **only if the user opts in**; clipped |
| `expires_at` | timestamptz, nullable | optional TTL (see decisions) |

RLS: public **read by id** only; **insert via service role** (the API route), never
from the anon key. Follows the `errors.sql` RLS pattern.

## Flow
1. On a completed run, a **Share** button POSTs the current `useRun` result to
   `POST /api/qa-run/share` → the route writes a row (service role) → returns `id`.
2. The UI shows the permalink `…/qa/run/r/<id>` with a copy button.
3. Opening `/qa/run/r/<id>` (a new, read-only route) GETs `/api/qa-run/share/<id>`
   and renders a **read-only `ResultView`** (reuse the existing component; no editor,
   no Run/Heal/Save controls).

## Decisions needed before building
1. **Include the test code in the shared report?** Default **off** (a toggle on
   Share). The code can reveal what/where you test; off by default is safer.
2. **Retention.** Keep indefinitely, or set `expires_at` (e.g. 30/90 days) + a small
   scheduled cleanup? Recommend a 90-day TTL for a free public portfolio.
3. **Screenshot.** The failure screenshot is up to ~3 MB base64. Store it (Supabase
   **Storage** bucket, not a DB column) or omit it from v1 and rely on the GitHub run
   link? Recommend **omit from v1** (summary + reason + steps + timing is the value).
4. **Video/trace are short-lived.** They stream from the Space's
   `/qa/run/artifact/{cid}/{kind}`, which fetches from GitHub — and `find_run` only
   sees the ~40 most recent runs, so an old share can't fetch them. v1 should **not**
   promise video/trace on a shared link (show them only while the run is recent, or
   omit). Durable video/trace = copy artifacts into our storage = out of scope for v1.

## Export — download as Excel & PDF
Independent of sharing: a report can be downloaded straight from the browser, from both
the live result card and a shared report page — no server needed, the data is already
in the page (`useRun` state, or the fetched share row). No export libs exist in
`ml-portfolio` today (checked), so this adds one or two.

**Excel (`.xlsx`)** — one workbook:
- *Summary* sheet: name, status, date, timing (test / total), `run_url`, and the
  passed / failed / flaky / skipped counts; the failure reason as a labeled cell.
- *Steps* sheet: a table of step · category · duration(ms) · ok.
- Library: **ExcelJS** (MIT) — build client-side, download via Blob + anchor.
  (SheetJS/`xlsx` community is Apache-2.0 and also fine; ExcelJS formats nicer.)

**PDF** — a one-page report: header + status badge, summary, timing, failure reason,
steps table.
- Option A *(recommended)*: **jsPDF + jspdf-autotable** (both MIT) → one-click
  "Download PDF" with a real table.
- Option B *(zero-dep)*: a print-only view + `window.print()` ("Save as PDF" in the
  dialog) — no library, but it's print-to-PDF, not a one-click file.

**Decision:** add jsPDF + ExcelJS (one-click files, small, MIT) vs. print-to-PDF +
ExcelJS only. Recommend the libs for a clean one-click experience.

**Ships independently:** export is pure client-side from the current result, so it does
**not** need the Supabase/share work — it can land before, or without, the rest of R7.
Downloads work in the real app (Vercel), unlike the artifact sandbox.

## Dashboard — aggregate view across runs
A single report (above) is one run; a **dashboard** rolls many runs into the health
view a team actually watches. (Charts must follow the project's `dataviz` skill —
inline SVG, no emoji, accessible in light/dark.)

**What it shows:**
- Headline tiles: total runs, pass rate, failures, avg CI time (over a window).
- Pass-rate **trend** over time (line).
- **Top failing tests** by name (bar).
- **Flakiness** — tests whose repeats disagreed.
- Recent failures with reasons (table), each linking to its full report / share.

**Data source — two options:**
- **A. Local (standalone, no server):** aggregate the browser-local run history already
  kept in `run/storage.ts` (recent runs + saved tests). Frontend-only, ships today, but
  per-browser (only this device's runs). A solid "my runs" v1.
- **B. Durable / cross-device (needs persistence):** log runs to a Supabase `qa_runs`
  table (a superset of the shareable-run row) and aggregate. Historical and
  multi-device, but depends on the Phase-1 persistence + a retention/privacy policy, and
  on **deciding whether EVERY run is logged or only saved/shared ones** (content + cost).

**Where it lives:** a Dashboard tab in `/qa`, or folded into the existing analytics
dashboard — decide at build time.

**Dependency:** a meaningful *historical* dashboard needs Option B. Option A can ship
standalone from existing local history, like Export.

## Privacy & abuse
- **Unlisted link** (random id) = anyone with the link can read it; standard for share
  links. State this on the Share action.
- **Content-light**, clipped fields, same `analyticsWritesEnabled` gate as the other
  routes so local dev can't write to prod. Must also update the privacy page (per the
  logging spec rule) since this persists user-triggered data first-party.
- **Abuse bounds:** size cap on the payload, basic rate-limit on the create route,
  and only persist a run that actually completed.

## Effort & phases
- **Phase 0 (can ship first, standalone):** Export to **Excel + PDF** from the live
  result card. Pure client-side, no DB. ~S–M (adds ExcelJS [+ jsPDF]).
- **Phase 1 (v1 sharing):** table + migration, `POST /api/qa-run/share`,
  `GET /api/qa-run/share/[id]`, the `/qa/run/r/[id]` read-only page, Share button.
  Summary + reason + steps + timing + run_url. ~M, frontend-only. (The share page also
  offers the Phase-0 Export buttons.)
- **Phase 2 (optional):** screenshot via Supabase Storage; `expires_at` + cleanup;
  a "my shared runs" list.
- **Phase 3 (dashboard):** Dashboard-A (local history aggregate) can ship standalone
  like export; Dashboard-B (durable `qa_runs` + historical trends) builds on Phase-1
  persistence. Charts per the `dataviz` skill.

## Non-goals
- No account system / per-user ownership (links are unlisted).
- No durable video/trace copy in v1.
- No backend or HF Space change for export/share (dashboard Option B adds a Supabase
  table via a Next.js route, still no ML-API/HF change).

## Verification
- Download **Excel** and **PDF** from a passed and a failed run; open each and confirm
  the summary, timing, failure reason and steps table are correct.
- Create a share from a passed and a failed run; open the link in a fresh
  browser/incognito → read-only report renders with the right status + reason.
- Confirm the anon key cannot insert (RLS), only the service-role route can.
- Confirm local dev does not write to prod (the writes gate).
- Confirm the privacy page lists what's stored.
- Dashboard: aggregates match a known set of runs (plant a few passed/failed), charts
  render in light + dark, and each failure row links to its report.

Related: `TESTWRIGHT_IMPROVEMENT_PLAN.md` §9 (R7), `QA_LEARN_FROM_EDITS_PLAN.md`.
