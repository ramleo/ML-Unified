# Part 319 — Crash-durable click audit: "did they click it?" from feasibility to a working, dogfooded tool

2026-10-14. The user raised a real organizational problem: *"a user says they clicked Save but
they didn't — how do we validate that?"* This session went from scoping feasibility all the way to a
**shipped, dogfooded click-audit subsystem** on ml-portfolio — durable capture, a dedicated store, a
gated viewer, disclosure — and then iteratively fixed every rough edge the user hit while testing it
live. Full product detail lives in [docs/CLICK_AUDIT.md](../docs/CLICK_AUDIT.md); this is the arc and
the lessons.

Related: [[project_click_audit]] (memory), [[feedback_keep_agents_md]] (memory), Part 318.

---

## Arc 0 — scoping (text-only, before any code)
Two real questions answered honestly before building:
- **Can a hard crash lose a click?** Yes, unless you write locally *first*. `sendBeacon`/`keepalive`
  survive navigation/tab-close but **not** a true crash — only a synchronous local write before the
  network does. So the design is **local-first → keepalive/beacon → flush-on-load + dedupe**.
- **Do orgs disclose click tracking?** The honest framing: this is an **app audit log**, not consumer
  web analytics. Enterprise audit trails (Salesforce/ServiceNow/Workday/Jira/M365) are standard and
  disclosed via ToS / an internal monitoring policy — not a public announcement. Consumer analytics
  (Google/Microsoft Clarity/Hotjar/FullStory) disclose "interaction/usage data" generically.

**Key scoping decision:** the portfolio has **no login**, so a true *named-user* audit isn't possible
there. Chose to build a **portable pattern** keyed by `actor` (= anon session id on the portfolio,
= authenticated user id when dropped into the real app), validated live on the portfolio.

## Arc 1 — the build (Plan #1 durable capture + Plan #2 audit log/viewer/disclosure)
Most of the machinery already existed (a `useFeatureCapture` delegated listener, `/api/track`, the
`errors.sql` separate-store pattern). The new pieces:
- `src/lib/auditClick.ts` — durable core: localStorage **outbox** (synchronous write before network),
  `keepalive` fetch + `sendBeacon` on `pagehide`, flush-on-load, `event_uuid` **dedupe**.
- `src/hooks/useAuditCapture.ts` — one capture-phase listener (mounted in `AnalyticsTracker`).
- `src/app/api/audit/route.ts` — batch **upsert on event_uuid** (idempotent), same local-write gate as
  `/api/track`.
- `src/app/api/audit/lookup/route.ts` — the dispute query, **gated by `AUDIT_ADMIN_KEY`, fails closed**
  (503 unset / 401 wrong). Two modes: a control = "did they click X?"; blank = **timeline**.
- `src/app/audit/page.tsx` — an **unlisted** `/audit` viewer.
- `supabase/click_audit.sql` — dedicated table (separate from analytics `events`; `event_uuid` unique).

**Verified live** against the real table (then deleted the test rows): crash-survival, beacon on unload,
flush-on-load, **two writes of one event_uuid → exactly one row** (DB dedupe), gated 401, empty → 400.

## Arc 2 — "it can be ANY click, did you understand?"
The first build was **opt-in** (`data-audit` tags only). The user corrected: they want to validate
*any* click, not pre-tagged ones. Decisions taken (via explicit questions):
- **Scope:** every *interactive* element (button/link/input/`[role]`/`[onclick]`), tagged or not.
- **Identity:** content-free — `src/lib/clickDescriptor.ts` derives `data-audit:id › testid:id ›
  #id › tag[type][role]@css-path`.
- **Viewer:** added a **timeline** mode (blank control = every click by the actor).

Dogfooding this immediately found a **real durability bug**: the `inFlight` guard dropped concurrent
flushes, so a **burst** of clicks left records undelivered until the next click/reload. Fix:
**re-arm the flush after a successful send**. Verified: a 3-click burst drains the outbox to 0.

## Arc 3 — the dogfooding tail (the user actually used it, one fix per failure)
Each of these came from the user testing the live tool and sending a screenshot:
1. **Live-feed duplicate-key flood** (59 React "two children with same key" errors) — *not* the audit
   code; a pre-existing bug in `useRealtimeFeed` prepending a realtime INSERT already present from the
   initial fetch. Fix: **dedupe by id** before prepend. (Found while testing; fixed in passing.)
2. **`/audit` text invisible in light mode** — the page used made-up CSS vars (`--fg`/`--bg2`) with
   near-white fallbacks. Fix: use the site's real theme tokens (`--text`/`--text2`/`--text3`/
   `--bg-glass`/`--border`/`--accent`). Verified ~15:1 contrast both themes.
3. **"where is the dark-theme option?"** — `/audit` is standalone (no navbar), so no toggle. Added the
   shared `ThemeToggle` top-right (persists to localStorage, flips `html.light`).
4. **"No clicks recorded"** despite clicking — **not a capture failure**: the data was there (verified
   9 rows in the live table). The **default "To" froze at page-load time**, so clicks made *after*
   loading fell outside the window. Fix: default "To" to **end of today**. Same window-boundary class
   as the earlier minute-truncation bug.
5. **"I clicked Generate, it's not recorded"** — again **not** missing (proved it: `/qa/discover`
   `button:nth-of-type(2)` = "Generate selected"). The problem was **readability**: content-free
   descriptors made every button a cryptic css path. Decision (reversing the earlier "no free text"
   call): **capture a readable `label`** = aria-label or trimmed visible text (capped 80). The viewer
   already renders it. Still **never** captures what's *typed into* a field. Privacy page + docs updated.

## The AGENTS.md gotcha (a self-inflicted detour)
Asked to "delete AGENTS.md if not required," I deleted + gitignored it — which **backfired**: Next.js's
`generate-agent-files.js` writes its managed block to `AGENTS.md` when it exists, but **injects it into
`CLAUDE.md`** when it's absent. So the delete polluted the real instructions file on the next
`next dev`. **Resolution: restore AGENTS.md** (it *shields* CLAUDE.md); committing its auto-refresh keeps
the tree clean. Saved as [[feedback_keep_agents_md]] so it isn't repeated.

## Lessons
- **Debug-first beats guessing, every time.** Three "it's not recorded" reports were all *window* or
  *readability* issues, not capture failures — each disproved by querying the live table directly before
  touching code.
- **Durability ≠ timely delivery.** The outbox never lost a click, but without the flush re-arm, bursts
  sat undelivered. Both properties needed explicit tests.
- **Window boundaries are a recurring bug class** (minute-truncation, page-load-frozen "To"). Default
  windows must reach "now"/end-of-day.
- **A privacy-optimal default can defeat the use case.** "No free text" was the conservative call, but it
  made the dispute log unreadable; the right balance was capturing the control *label* (not field input).
- **Verify UI in BOTH themes with real tokens** — made-up CSS vars silently fall back and vanish in one
  theme.

## Setup state (production)
- `supabase/click_audit.sql` run in Supabase ✅ · `AUDIT_ADMIN_KEY` set in Vercel ✅ (lookup returns 401
  gated, confirmed) · `/audit` live and unlisted.

## Commits (ml-portfolio unless noted)
`5d40a01` feat: crash-durable any-click audit + gated lookup/viewer + disclosure ·
ML-Unified `11c7656` docs(spec) · `673c56d` fix: realtime feed dedupe + restore AGENTS.md ·
`27fe59f` fix: theme /audit with real tokens · `05a06b3` feat: theme toggle on /audit ·
`9160cc6` fix: default window end to end-of-today · `d690498` feat: capture readable control label ·
ML-Unified `b469557` docs(label). (Also `8ea99b8` the reverted AGENTS.md delete.)

---

# 2026-10-15 — the aggregate dashboard follow-on (build → redesign → graph-forward → hardening)

The next day the user asked for a **dashboard** on top of the forensic `/audit` lookup. This arc went
build → "looks dull" redesign → "more text or graphs?" cleanup → a security Q&A that turned into real
edge hardening. Product detail is in [docs/CLICK_AUDIT.md](../docs/CLICK_AUDIT.md).

## Arc 4 — build the aggregate dashboard (`/audit/dashboard`)
The bird's-eye complement to the per-actor lookup: counts across **all** actors in a window. Key
decision (confirmed by the user): **internal-only, gated like the lookup** — not a public page.
- `click_audit_stats(start,end,bucket)` **RPC** — all GROUP BYs run in Postgres, one round-trip
  (totals, top controls/pages/actors, by-country, time series, recent feed); client never pulls raw rows.
  Appended to `supabase/click_audit.sql` (idempotent; user re-ran it).
- `/api/audit/stats` — **same `AUDIT_ADMIN_KEY` fail-closed gate** as lookup.
- `src/app/audit/dashboard/{page,Panels,charts}.tsx` — split three ways to stay under 400 lines each.
- **Verified live** against the real table: RPC shape, gate 401/401/200, all panels render real data,
  both themes (used the service-role key to call the RPC directly — read-only, no writes).

## Arc 5 — "looks dull" → research-driven redesign
The user called the first version dull and told me to **research the web**. The recurring best-practice:
*"a bare figure with no baseline is decoration"* + *design for 5-second scanning*. Rebuilt with:
- **Every KPI gets a baseline** — delta vs the previous equal-length window (▲/▼ + %, arrow so it's
  never color-only), fetched in parallel client-side (no new SQL).
- **Featured Total-clicks card with an inline sparkline**; **gradient area chart** with gridlines +
  hover crosshair (was a flat line); stroke icons; section eyebrows (Overview/Trend/Breakdown/Activity).
- Single accent as the one sequential hue → no categorical palette to validate (dataviz).

## Arc 6 — "more text or graphs?" → graph-forward + a real overflow bug
The user's question was the right instinct but the fix was neither: it was **too much raw text**
(structural css-path ids dumped in the hero slot) **plus an overflow bug**. The bug: long control ids
**bled out of the card into the next column**. Root cause — the bar rows used nested `display:grid`
whose **auto track sized to content**, so the flex `min-width:0` ellipsis clamp never engaged. Fix:
**flex-column/block rows** (stretch to the card width) → label is bounded; proven **0px overflow** via
`getBoundingClientRect`. Also: **demoted the structural id to the hover title** (readable label is the
hero), added a **share-of-total donut** for By-country (single-hue sequential + legend = no palette to
validate), and **balanced the layout** (3-col breakdown, responsive grids via a scoped `<style>` block
since inline styles can't media-query).

## Arc 7 — "who are these actors? is it safe?" → edge hardening
The actor ids are **anonymous session ids** (login-less site → no name/email/PII; a session = a browser,
not a person). Honest answer: you can only prove *a session* clicked X; naming a person needs auth
(`actor = user id` in the real app). On "is it safe": **read is already locked** (admin-key gated, fails
closed, service key server-only). Then hardened the two open edges:
- **Rate-limit `POST /api/audit`** (120/min per IP; the durable outbox retries a 429, so nothing lost) —
  the capture endpoint is public by necessity and had no limit.
- **Basic-auth on the `/audit` pages** via `src/proxy.ts` (Next 16 **`proxy`** convention, not deprecated
  `middleware`) so strangers can't even reach the key form; enforced only when `AUDIT_ADMIN_KEY` set,
  **password = that key**. Capture endpoint deliberately **not** matched (stays public).
- Stated the honest **forgeability** caveat: client mints `event_uuid`/`session_id`/descriptor, so a
  malicious client could fabricate records; the real app closes this by deriving `actor` server-side.
- **Verified:** pages 401 no-creds (+ `WWW-Authenticate`) / 200 with; write stays public; rate limit
  trips at ~120/min; dashboard loads end-to-end behind basic-auth. (Test pitfall caught: creds-in-URL
  navigation breaks relative `fetch` — not a bug; a real dialog login has no creds in the URL.)

## Lessons (2026-10-15)
- **"Make it look good" = research first, then build to a rule** — baselines, sparklines, hierarchy, not taste.
- **Nested auto-grid rows defeat a flex ellipsis clamp.** For a width-bounded row, the container must
  stretch to its parent (flex-column/block), not size to content (auto grid track).
- **Verify at the layer that proves the claim:** `curl` for the gate + rate limit, `getBoundingClientRect`
  for overflow, a credentialed browser flow for basic-auth — a screenshot alone proves none of these.
- **"Is it safe" has two halves** — reading (locked) vs writing (public-by-necessity, so rate-limit +
  accept forgeability). Don't conflate them.

## Setup state (production, updated 2026-10-15)
- SQL re-run for `click_audit_stats` ✅ · `AUDIT_ADMIN_KEY` set in Vercel ✅ · `/audit` + `/audit/dashboard`
  live, **now behind Basic auth** (username anything, **password = `AUDIT_ADMIN_KEY`**) + the in-page key.

## Commits (2026-10-15, ml-portfolio unless noted)
`1aa7a1d` feat: aggregate dashboard + stats RPC/endpoint · `3f8c2f0` redesign: KPI baselines + sparkline
+ gradient chart · `b2a7520` fix: graph-forward (overflow fix + country donut) · `ad131ef` feat: rate
limit + page basic-auth (`proxy.ts`). ML-Unified `5fd1f82` docs(dashboard) · `1622546` docs(hardening).
