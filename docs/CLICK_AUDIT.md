# Crash-durable click audit

A durable, per-actor log that answers one question cleanly: **"did this actor click
this control in this time window?"** Built for disputes of the form "the user says
they clicked Save but the system shows nothing." Separate from the content-free
*analytics* pipeline ([LOGGING_SPEC.md](LOGGING_SPEC.md)) on purpose — audit needs
its own store, retention, access control, and a hard uniqueness guarantee.

Lives in **ml-portfolio** (the login-less showcase) as a working, verified
reference; the same code drops into a signed-in app by wiring that app's
authenticated user id into the one `actor` field.

## Why it is separate from analytics
- Analytics (`events` table) is aggregate and best-effort — a dropped event barely
  matters. An audit record is the evidence, so losing one defeats the purpose.
- Analytics is content-free and world-readable via its own API. Audit names an
  actor and their actions, so its read path is **gated** and **fails closed**.

## The durability guarantee (Plan #1) — three stages, strongest first
1. **Local-first (synchronous).** On click the record is written to a
   `localStorage` outbox *before* any network call. A synchronous local write
   survives a tab/browser/OS crash; only power loss in the microsecond between
   click and write beats it.
2. **Keepalive / beacon.** Delivery uses `fetch(..., { keepalive: true })`, which
   the browser finishes even as the page unloads; on `pagehide`/visibility-hidden
   the outbox is also flushed with `navigator.sendBeacon`.
3. **Flush on load + dedupe.** Anything the server never acked is re-sent on the
   next load. Every record carries a client-minted `event_uuid`; the server upserts
   on it, so a re-sent-but-already-delivered click is never counted twice.

An entry leaves the outbox only on an *acked* keepalive send. The beacon path is
best-effort and deliberately does not clear the outbox — the next load reconciles,
and the dedupe makes the re-send free.

## What a record holds (LOGGING_SPEC §6)
`event_uuid`, `control` (the structural derived id below), `path`, `session_id`/`actor`,
`client_ts`, server `created_at`, `country`, and `meta`: `tag`, `role`, `type`, `id`,
`data-testid`, `name`, css `path`, and a readable **`label`** = the control's aria-label
or its trimmed visible text (capped 80 chars), shown in the viewer's "What was clicked".
The label CAN include user content for text-labelled links/rows (capped + disclosed on
the privacy page); **the one hard rule is it never stores what you TYPED/pasted/uploaded
into a field** — only the control's own label. The `control` id stays purely structural.

## Every interactive click, tagged or not
Capture is **not** opt-in: every click on an interactive element — a button, link,
input, `[role=…]`, or `[onclick]` — is recorded. Clicks on plain text/background are
ignored. The `control` id is derived content-free, most explicit first:
`data-audit:<id>` › `testid:<id>` › `#<id>` › `tag[type][role]@<css-path>`. A
`data-audit="save-btn"` on an important control gives it a clean, stable id (and
`data-audit-value` an enumerated choice), but it is an *optional upgrade*, not a
requirement. Identity is derived from structure (tag/role/attributes/position) and
`aria-label`, **never** the element's visible text — see `src/lib/clickDescriptor.ts`.

The password tool (`§5b`) is excluded from capture entirely.

## Where things live (ml-portfolio)
- `src/lib/auditClick.ts` — durable core (outbox → keepalive → beacon → flush + dedupe;
  re-arms after a successful send so a burst of clicks drains promptly).
- `src/lib/clickDescriptor.ts` — content-free identity for any interactive click.
- `src/hooks/useAuditCapture.ts` — one global capture-phase listener for `data-audit`;
  flush-on-mount; beacon-on-unload. Mounted once in `components/AnalyticsTracker.tsx`.
- `src/app/api/audit/route.ts` — batch upsert on `event_uuid`; same local-write gate
  as `/api/track` (`analyticsWritesEnabled()`); returns `delivered[]` so the client
  clears exactly what landed.
- `src/app/api/audit/lookup/route.ts` — the dispute query (the `click_audit_lookup`
  RPC). **Gated** by `AUDIT_ADMIN_KEY` (header `x-audit-key` or `?key=`); with no key
  set it returns 503 (fails closed).
- `src/app/api/audit/stats/route.ts` — the aggregate feed for the dashboard (the
  `click_audit_stats` RPC). **Same gate** as the lookup, fails closed. Counts are
  GROUPed in the DB; the client never pulls raw rows.
- `src/app/audit/dashboard/page.tsx` + `Panels.tsx` — the internal dashboard viewer
  (aggregate overview). Split in two to stay under the 400-line file limit.
- `supabase/click_audit.sql` — the dedicated table (`event_uuid` unique = the dedupe
  key), its indexes, and the `click_audit_lookup(actor, control, start, end)` function.
  Run once in the Supabase SQL editor, like `errors.sql`.

## Setup
1. Run `supabase/click_audit.sql` in the Supabase SQL editor (once).
2. Set `AUDIT_ADMIN_KEY` in the environment (Vercel) to enable the lookup endpoint.
3. Add `data-audit="<id>"` to the controls that matter for disputes.
4. Run `supabase/rate_limit.sql` (once) to enable the durable, cross-instance rate
   limit on the capture endpoint. Optional — without it the route falls back to the
   in-memory limiter. Uses `AIRAML_LOG_TOKEN` to salt the IP hash (shared with the
   security log).

## Using the lookup
`GET /api/audit/lookup?actor=<id>&start=<ISO>&end=<ISO>` with the key, plus an
**optional** `control`:
- **with `control`** → "did they click X?": `{ mode:"control", clicked, count, rows[] }`
  (empty rows = they did not click it in the window).
- **without `control`** → **timeline**: every click by the actor in the window,
  newest first (`mode:"timeline"`), up to 1000.

The `/audit` viewer wraps this: leave Control blank for the timeline, or fill it to
check one control. On the login-less portfolio `actor` is the random session id; in
the real app it is the authenticated user id.

## The dashboard (aggregate overview)
`/audit/dashboard` is the bird's-eye complement to the per-actor lookup: counts
across *all* actors in a window, for internal use only. It is a thin client over the
gated `GET /api/audit/stats?start=&end=&bucket=hour|day`, which calls the
`click_audit_stats(start, end, bucket)` RPC. One round-trip returns: totals
(clicks / actors / sessions / controls / pages), top controls (with readable
`label`), top pages, most active actors, clicks by country, a bucketed time series,
and a 50-row recent feed. Panels: five stat tiles, a single-series area+line time
chart (hover crosshair), four ranked bar-lists, and the recent table. It shares the
`AUDIT_ADMIN_KEY` gate and the `ThemeToggle`; the key is remembered in the same
sessionStorage slot as `/audit`. Not in any public nav. Requires the
`click_audit_stats` function — re-run `supabase/click_audit.sql` after pulling it in
(`create or replace` makes it idempotent; the table/lookup are untouched).

## Verified (2026-10-14)
Against the live `click_audit` table: local-first write survives a dead network;
`sendBeacon` fires on `pagehide` without clearing the outbox; flush-on-load clears a
leftover record; two writes of the same `event_uuid` leave **exactly one row**
(DB-level dedupe); the gated lookup returns the row with the correct key and 401
with a wrong one; empty batch → 400. **Any-click + timeline:** clicking three
*untagged* controls recorded three content-free structural descriptors; a burst
drained the outbox to zero (re-arm fix); the `/audit` viewer's timeline mode (blank
control) listed every click for the actor. Test rows were deleted afterward.

## Access & hardening
- **Read is gated, fails closed.** `/api/audit/lookup` and `/api/audit/stats`
  require `AUDIT_ADMIN_KEY` (401 wrong / 503 unset); the Supabase service key is
  server-side only. The audit data (who-clicked-what) is never world-readable.
- **The pages are behind Basic auth too** (`src/proxy.ts`, Next's `proxy`
  convention): `/audit` and `/audit/dashboard` return 401 without the key, so
  strangers can't reach the key form. Enforced only when `AUDIT_ADMIN_KEY` is set
  (prod); password = that key, username ignored. The capture endpoint is **not**
  matched — it must stay public.
- **The write path (`POST /api/audit`) is public by necessity** (every visitor's
  browser posts its own clicks) but hardened: input validated + length-capped,
  batch ≤ 500, dedupe on `event_uuid`, Vercel-only writes, coarse `country` only
  (no IP), and a per-IP rate limit (120/min). The limit is two-layer: a cheap
  in-memory first pass plus a **durable DB counter** (`rate_limit.sql`'s
  `rate_limit_hit`, keyed on a salted IP hash) that is **shared across serverless
  instances** — the in-memory one alone is defeated by spreading requests across
  warm lambdas or a cold start. The durable outbox retries a 429, so nothing is
  lost. Fails open if `rate_limit.sql` is not yet applied.
- **Not tamper-proof against a malicious client.** Because the browser mints
  `event_uuid`/`session_id`/descriptor, a determined user could forge a record.
  The log is strong evidence for a normal user; in the signed-in app you close
  this by deriving `actor` from the server-side auth session, never the client.

## Honest limits
- Power loss in the ~microsecond between click and the local write is the only
  unrecoverable case.
- It proves a click reached the browser's handler (the button was clicked), not the
  user's intent, and not that the downstream action then succeeded.
- On a login-less site it can only identify a session, not a named person; a real
  per-user audit needs authentication.
