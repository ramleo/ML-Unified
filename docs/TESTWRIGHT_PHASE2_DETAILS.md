# Testwright — Phase 2 per-item detail (§9a–§9g)

Companion to [TESTWRIGHT_IMPROVEMENT_PLAN.md](./TESTWRIGHT_IMPROVEMENT_PLAN.md) — the
roadmap table and status live there; this holds the long per-item design/detail blocks,
split out to keep the plan doc under the 400-line limit.

### 9a. R5 detail — Authenticated testing (`storageState`)

**Status: deferred (2026-10-02)** — there is no logged-in app to test yet, so this is
parked until one exists. The design below stands; the first step when revived is to
pick the credential model (A/B/C).

**Goal:** run a test against pages behind a login — log in once at the start of a run,
reuse the session for the test body (standard Playwright: a setup step logs in and writes
`storageState`; the test loads it).

**The crux — credentials vs. a public runner.** `dispatch()` sends the test `code` as a
`workflow_dispatch` input to the **public** `ramleo/ml-qa-runner` repo
(`github_runner.py:46`), so inputs and Actions logs are world-readable. Fine for test
code; a hard **no** for a password or session cookie. Decide the credential model first:

| Path | How creds are handled | Serves | Cost |
|---|---|---|---|
| **A. GitHub Secrets + named login** *(recommended)* | Stored as encrypted repo secrets; login step reads `process.env`, never an input | Owner testing own authed apps | Only the owner can set secrets — doesn't generalize to arbitrary users |
| **B. Private runner repo** | A dedicated **private** auth-runner hides inputs/logs; then pasted creds/`storageState` can transit | Anyone (but owner still sees run records) | Splits infra; private Actions minutes metered (~2000/mo free) |
| **C. Demo-only, public** | Credential field behind the ownership gate + loud "VISIBLE in public CI logs — throwaway accounts only, never a real password" warning | Public demo users | Honest but limited; never for real passwords |

**Decision: build A now + add C's warning path; defer B unless demand appears.**

**Build steps (path A):**
1. **models.py** — optional `auth` on `RunRequest`: `login_url` + plain-English
   `login_steps` + credential-source flag (no raw secrets in the model).
2. **author.py + new prompt** — a login-setup generator: plain-English login → a Playwright
   **setup spec** that fills creds from `process.env`, asserts a logged-in signal, saves
   `storageState` to `playwright/.auth/state.json`.
3. **`ml-qa-runner` workflow** — conditional **setup project** runs the login spec first;
   main test gets `storageState`; creds injected via `env:` from repo **secrets**. *(Only
   change outside the two repos — a separate deploy.)*
4. **github_runner.dispatch** — pass auth config through; never log it (content-free).
5. **RunRunner.tsx** (285 lines, no split needed) — a **"Requires login?"** toggle →
   login URL + steps + the security notice; carry into `/execute`.
6. **Docs** — user-guide login walkthrough + a security note; this plan entry.
7. **Verify** — §7 regression checklist (a no-auth run must work unchanged), then an auth
   run reaching a real logged-in page.

**Honest caveat.** On this deployment (a public portfolio whose own site needs no login),
path A mainly benefits the owner testing their own authed apps; broad public auth testing
isn't safe without path B. Weigh R5 against R4 if there's no authed app to test yet.

### 9b. R8 detail — Scheduled re-runs / monitoring (tests as uptime checks)

**Status: IN PROGRESS (2026-10-04).** Mark a saved test "monitor this" and it re-runs on a
schedule; a failure (or a pass→fail transition) raises an alert and shows as uptime history.
The synthetic-monitoring angle (Checkly/Mabl). Results already flow into `qa_runs` (Dashboard-B),
so the dashboard aggregates monitor runs for free.

**P0 decisions — LOCKED (recommended defaults, 2026-10-04):**
1. **Cost cap** (the real constraint — each check ≈ 50s GitHub Actions minutes on a free
   portfolio): **opt-in per test, ≤5 monitors, daily default / hourly max, a global daily-run
   ceiling.**
2. **Scheduler: A — a scheduled GitHub workflow** in `ml-qa-runner` (same cron pattern as
   `nightly-evals.yml`): one batched job reads the due monitors from Supabase and runs them,
   amortizing the ~50s floor. (Rejected: Vercel Cron — hobby tier is daily-only; `pg_cron` —
   splits the run path.)
3. **Alerts: DB + dashboard first** (reuse the `providerAlert.ts` dedup pattern); **email
   (Resend) deferred** to a later phase.

**The must-fix prerequisite.** A scheduled job cannot read a saved test from a browser's
`localStorage` — monitored tests must live **server-side**. So the foundation is a
`qa_monitors` Supabase table (test code + target + schedule + enabled + last_status), same
service-role/RLS model as `qa_shared_runs`.

**Build steps:**
1. **`supabase/qa_monitors.sql`** — table + RLS (service-role only), `enabled`, `interval`
   (`daily`/`hourly`), `last_run_at`, `last_status`, `consecutive_failures`. Run once in the
   SQL editor (like the other migrations).
2. **`POST /api/qa-run/monitor`** (upsert/enable/disable) + **`GET /api/qa-run/monitor`**
   (list) — Next.js routes, service-role key, `analyticsWritesEnabled` gate, ≤5 cap enforced.
3. **"Monitor this test" toggle** in the Run stage (on a saved/passed run) → upserts the test
   server-side; shows the cap + "runs in public CI" notice. **Owner-gated** (behind the same
   ownership gate R5 uses) — monitoring is *recurring* CI cost, so unlike one-shot Share it must
   not be open to arbitrary visitors. The test **code is stored** here (required to re-run it,
   unlike Share where code is opt-in) — disclosed on the privacy page.
4. **Scheduled workflow** in `ml-qa-runner` — cron reads due monitors (`GET …/monitor?due=1`
   via a shared token), runs them batched, records each to `qa_runs` tagged `source:'monitor'`,
   updates `last_run_at`/`last_status`/`consecutive_failures`.
5. **Alerting** — on failure or pass→fail transition, write a dedup'd alert row; a **Monitors**
   section in `/qa/dashboard` (uptime %, last check, recent failures each linking to its report).
6. **Phase 4 (optional, later):** email via Resend; snooze/ack.
7. **Docs + privacy page** (server-side storage of a monitored test is disclosed) + verify
   (plant a passing + a failing monitor; confirm cap, dedup, dashboard, RLS, writes-gate).

**Honest caveat.** The price is **recurring CI minutes** — that's why the cap is P0, not an
afterthought. Keep the default frequency low and the monitor count small.

### 9c. R9 decision — API / request testing: SKIP for now

**Status: deprioritized / skip (2026-10-04).** API testing (Playwright's `request` fixture:
hit an endpoint, assert status/JSON) is **off-identity** — Testwright is browser E2E, and this
is a different tool bolted on. Three reasons to hold off: (1) users come here to test *screens*,
not endpoints — adding this makes two half-products; (2) it needs a different grounding model —
an API has no ARIA snapshot to copy from, so the "never invent anything" safety net mostly
doesn't apply (the user would hand-feed every endpoint + expected shape); (3) its only real win
is **speed** (no browser → dodges the ~50s floor), which isn't worth a new surface on a test
type this product isn't about. **Revisit only as a tiny complement to E2E** (same-origin,
GET-first, user-supplied endpoint + sample) if real demand appears; otherwise the effort goes
to R8.

### 9d. R11 detail — Run Live (local Companion)

**Status: MVP shipped 2026-10-10.** A website cannot launch a browser on the user's
machine (browser sandbox), so "watch it live" needs a small local process — exactly how
Playwright (VS Code ▶ / `--headed`), Cypress (`cypress open`) and Checkly (`checkly test`)
all do it. The **Testwright Companion** (`ml-qa-runner/companion/`) is a `127.0.0.1` daemon:
`GET /health` (the UI detects it) and `POST /run {code, base_url, test_name}` → writes the
spec, runs `playwright test --headed`, returns pass/fail. CORS locked to the Testwright
origins; target host allow-listed; runs only the spec the UI sends. The Run stage shows a
**Run Live** button (`RunLiveButton.tsx`): companion up → click to watch; down → shows the
one-line `npx @airaml/testwright-companion` to start it. Headless CI stays the default.
**MVP scope:** run once with `npm start`/`npx`, then click-to-run. **Shipped since (R14, §9g):**
zero-typing double-click launchers + a VS Code extension. **Still later:** `--ui` time-travel
mode, live status over WebSocket.

### 9e. R12 detail — TW-GROUND (author grounding on dynamic controls)

**Status: SHIPPED 2026-10-10/11.** Found by the Phase-1 self-test sweep (Testwright testing our
own ~29 targets): ~every failure was an **authoring-grounding miss, not a tool bug** — when
Discover doesn't capture a control, Author *guesses* its label and the test times out waiting
for something that isn't there. sql-app (`/tools/text-to-sql`) was the adversarial case, and
each fix exposed the next layer — **five stacked bugs, all generalised, all HF-uploaded:**

| # | Bug | Fix | Commit |
|---|---|---|---|
| 1 | Guessed `'Run'` + shortened placeholder (SPA renders controls after async load → Discover captured none → gate no-op → LLM guessed) | `discover.py` network-idle settle before `grabControls`; `prompts.py` `10c-ready` wait-for-ready | `ad07f63` |
| 2 | First-load **tour overlay** hid the input on a fresh browser | `discover.py` `_overlay_hint` (`===DISMISS===` block); `prompts.py` `10d-overlay` non-fatal dismiss-first | `0289623` |
| 3 | Navigated to `/sql` (landing) not the given `/tools/text-to-sql` — rule 2 invited `goto(BASE_URL + '<path>')` | rule 2: open the provided base_url **verbatim** | `c860301` |
| 4 | Grounded author returned **empty** when context had no specific heading | rule 10: generic `getByRole('heading').first()` fallback, never empty | `70c9f5d` |
| 5 | **Validator rejected any locator name ending in `.`** — `_OPT_KEY_DOT_LEFT` scanned INSIDE strings, so a heading like `'… get a prediction.'` false-matched the `{name.` typo check → "unparseable" → both providers fail → empty | `validate.py` `_blank_strings()` before the option-key-dot check (regression guards keep a real `{name.` typo + brace imbalance rejected) | `636b39b` |

**Bug #5 was the real blocker** behind the ml/eda/vision landing "author-failed" and silently
broke **every** sentence-style heading site-wide. Found by **reading the Space run logs**
(`/api/spaces/{id}/logs/run`) after adding a content-free "head of rejected code" diagnostic to
`author.py` — two prior guesses (tour, regex-brackets) were both wrong; the logs settled it.
Heal (`heal.py`) timeout-on-action re-resolution was *not* needed once authoring was grounded, so
it stays on the backlog rather than shipped.

### 9f. R13 detail — Activity Log (surface in-band authoring failures)

**Status: SHIPPED 2026-10-10/11.** A dashboard screenshot showed `Errors 0` while authoring was
visibly failing. Root cause: a provider that returns **HTTP 200 with unusable output** (prose, a
hedge, or code the validator rejects) is a success at the transport layer, so `call_log`'s
`instrument()` records it `ok`; the rejection happens one layer up in `author.py` and only reached
the Space's throwaway run buffer. **An "ok" from the transport layer is not an "ok" from the
application** — so that layer now emits its own failure row.

1. **Backend** (`author.py._log_reject`, `4d2d5dc`) — each of the four reject sites in
   `generate_test()` logs a content-free row (`status=error, http=422, error_code=output_rejected,
   op=qa-author`) naming the reason + a short head of the generated test code (never user data).
2. **Feed** (`ml-portfolio /api/activity` + `AnalyticsActivityLog.tsx`, `7f66d67`) — merges
   `llm_calls` (ok / 429-warn / error) with the `errors` table into one newest-first feed with
   All/Warnings/Errors filters.
3. **UX** (`d6a4802`) — warning/error rows show their reason **inline (no click)**; the list is a
   fixed-height scroller so filtering never resizes the card (the old `return null` unmounted it and
   jumped the page); the LLM panel's `· N err` badge dispatches `airaml:activity-focus` → the log
   scrolls into view and selects Warnings.

### 9g. R14 detail — fixtures + fake-media (upload/camera tools testable)

**Status: SHIPPED + verified live 2026-10-11.** ~34 tools need a file upload or a camera
before they do anything, so they were untestable (no file; CI has no camera). Fix, across
three repos:
- **`ml-qa-runner/fixtures/`** — small committed samples (`sample.{csv,png,jpg,pdf,wav,mp4,txt}`,
  `fake-camera.y4m`, `fake-audio.wav`, ~192K); `qa-run.yml` sparse-checks them out and launches
  Chromium with `--use-fake-ui/-device-for-media-stream` + `--use-file-for-fake-video/audio-capture`
  (guarded by existence). The companion mirrors both.
- **backend** — Discover captures each page's file inputs (accept + label) in the explore spec;
  `fixtures.py` (the fixture catalog + single source of truth) turns them, plus a camera-control
  scan, into a `===MEDIA===` grounding block mapping each input to `setInputFiles('fixtures/<name>')`.
  Author rule `14-media` uploads that exact file / just clicks capture; Discover rule `3a` proposes
  the upload/camera journey as primary.
- **robustness** — the weak free model ended upload tests on a false `toBeHidden()` of a permanent
  description; `locators.strip_upload_assert_noise` deterministically drops that and any
  visibility assertion on a hidden file input, leaving the reliable `toHaveValue(/sample…$/)` baseline.
- **Run-Live polish** — zero-typing double-click launchers (`companion/launchers/`, mac/win/linux)
  and a **VS Code extension** (`vscode-extension/`, editor ▶ runs the spec headed with the same
  fixtures + fake-media).

**Verified live:** an EDA CSV-upload test (`setInputFiles` + `toHaveValue`) and a face-liveness
camera test (`Start camera` → button hidden, i.e. `getUserMedia` resolved on the fake stream) both
pass green on the real runner. **Manual publish steps left to the owner:** `npm publish` the
companion `@airaml/testwright-companion@0.2.0`, and package/publish the VS Code extension.
