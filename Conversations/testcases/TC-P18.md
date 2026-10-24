# TC-P18 — Parts 310–319

**Prefix:** TC-P18
**Parts covered:** 310–319 (10 sessions)
**Status:** ✅ Complete
**Method:** Inline — no subagents; full line-by-line re-read of all 10 session logs.

Covers: Testwright model-selection (owner paid + BYOK) and scheduled monitoring; the two-week-stale CI rescue; wiring 15 tool guides; the doc-coverage CI gate; the full observability roadmap O1–O6 (trace id, RUM, LLM telemetry front+back, Sentry trace-tag, SLOs, agent span timing) and the `ts`-column bug it exposed; Testwright self-testing + Run-Live Companion + the TW-GROUND stacked authoring bugs + the Activity Log; the analytics dashboard redesign; Testwright Phase 2 (fixtures/fake-media, npm publish, the volatile-control taxonomy → 6/6 green, Node-26 companion crash); and the crash-durable click-audit subsystem.

---

## Testwright Model Selection, Monitoring, CI Rescue (Part 310)

### TC-P18-001
**Category:** Feature
**Test Name:** QA generation: free cascade / BYOK / owner paid, resolved per request
**Steps:**
1. Call `/qa/author/generate` as a visitor naming `gemini` without a key/token, with a BYOK key, and with the owner token.
**Expected Result:** Visitor → falls back to free (`cohere`) — the server's paid Gemini is never spent by a visitor; BYOK → caller's own key, single provider, browser-only; owner token (`QA_OWNER_TOKEN`, constant-time compare) → paid Gemini.
**Automation Hint:** API test all three.
**Source:** Part310 (`bec6707`)

### TC-P18-002
**Category:** Feature
**Test Name:** Scheduled monitoring re-runs a saved test and records it
**Steps:**
1. Create a monitor on a passed run; fire the scheduled workflow.
**Expected Result:** Owner-gated `qa_monitors` CRUD; the scheduled `ml-qa-runner` workflow finds due monitors, re-runs (no LLM call), records → dashboard updates. Full loop create→due→run→record→dashboard.
**Automation Hint:** monitor e2e.
**Source:** Part310 (`1ccf02f`)

### TC-P18-003
**Category:** Bug-Regression
**Test Name:** A skipped CI step hid three independent failures for two weeks
**Steps:**
1. Inspect per-check CI status.
**Expected Result:** file-length red since Sep 20 (reskin grew `common.css` past its pin → split into `common-anim.css`); ruff red (156 deliberate E402 in app.py for pixel-caps-before-import → `# ruff: noqa: E402`, not moving imports); fixing lint let pytest run again, unmasking 5 stale `test_provider_cascade` tests (document cascade dropped Mistral → `[cohere,gemini]`). A failing early step silently skips later ones.
**Automation Hint:** none (method); per-check CI audit.
**Source:** Part310 (`9885b28`/`94a7c01`)

### TC-P18-004
**Category:** Bug-Regression
**Test Name:** eslint CLI errors ≠ build failures — verify the build
**Steps:**
1. `next build` with pre-existing `react-hooks/set-state-in-effect` CLI errors present.
**Expected Result:** Exit 0 ("Compiled successfully") — the CLI flat-config severity isn't what the build gates on; confirm ownership (`git stash` + re-lint) and trust the build, not the linter count.
**Automation Hint:** none (method).
**Source:** Part311

### TC-P18-005
**Category:** Architecture
**Test Name:** One shared guide modal, not 15 copies; chat left where it fits
**Steps:**
1. Open the User Guide on the 15 newly-wired tools.
**Expected Result:** Shared `ToolGuideModal` (props) — not 15 near-identical files; the 5 non-chat tools get modal-only; >350-line pages split before the button went in.
**Automation Hint:** presence check + file-length.
**Source:** Part311 (`f78ff1d`)

---

## Doc-Coverage Gate + Observability O1–O6 (Parts 312–314)

### TC-P18-006
**Category:** Feature
**Test Name:** A doc-coverage CI gate enumerates tool→card, guide→wired, platform→guide
**Steps:**
1. Plant a violation of each of the three relations.
**Expected Result:** `check-doc-coverage.py` red on each (reuses `handbook_sources.py`); green on HEAD; inherent limit stated in the script — a pure behavior change in an existing file has no footprint to enumerate (needs human review).
**Automation Hint:** run the gate against planted violations.
**Source:** Part312 (`5919311`)

### TC-P18-007
**Category:** Feature
**Test Name:** O1 correlation id threads browser → route → Space → provider
**Steps:**
1. Make a tool call; follow the trace id.
**Expected Result:** `trackedFetch`'s existing `run_id` is sent as `x-trace-id` (one chokestream, 78 callers); backend `trace.py` middleware echoes/mints it, holds a contextvar, stamps 500s into `errors.meta.trace_id` (no migration — existing jsonb). A custom header triggers CORS preflight — verified `allow_headers:["*"]` first.
**Automation Hint:** assert the id round-trips.
**Source:** Part312 (`b02df24`/`fd43ea4`)

### TC-P18-008
**Category:** Feature
**Test Name:** O2 RUM + O3 LLM telemetry, content-free, with a dated price table
**Steps:**
1. Load a page; make LLM calls front and back.
**Expected Result:** `tracesSampleRate 0.1` records Web Vitals (replay off, query stripped); `llm_calls` already had `run_id` (= trace id, no `trace_id` column) + added tokens/cost/operation; cost from a dated, verified price table (not guessed); `ai-tools` logs server-key calls only (BYOK is the caller's spend).
**Automation Hint:** telemetry + dashboard.
**Source:** Part312 (`0c95e5c`/`2875a84`) / Part313 (`96a4bca`)

### TC-P18-009
**Category:** Bug-Regression
**Test Name:** `llm_calls` is filtered on `ts`, not `created_at`
**Steps:**
1. Query `/api/slo` and `/api/llm-stats`.
**Expected Result:** Filter on `ts` — `created_at` raises Postgres 42703 (undefined column), which `isMissingSchema` swallowed as `needs_setup`, silently hiding 283 real rows from the LLM panel for days; the `errors` table DOES use `created_at` (postdates the convention). `feedback_llm_calls_ts_column`.
**Automation Hint:** query assertion on the column.
**Source:** Part313 (`f367eeb`)

### TC-P18-010
**Category:** Bug-Regression
**Test Name:** SLO success excludes recovered rate-limits (user-facing success)
**Steps:**
1. Compute the 30d LLM-success SLO with 48 recovered Mistral 429s.
**Expected Result:** 99.0% (PASS), not 79.9% — a recovered 429 isn't a user-facing failure (the cascade answers); excluded from the denominator + p95 and surfaced separately as `rate_limited_excluded`, not hidden.
**Automation Hint:** SLO calc test.
**Source:** Part313 (`e7e2ea2`)

### TC-P18-011
**Category:** Bug-Regression
**Test Name:** Sentry trace tag set where the contextvar is still live
**Steps:**
1. Trigger a backend 500.
**Expected Result:** Tag set in `error_capture_dispatch`'s except block (not `before_send` — the outer trace middleware's `finally` resets the contextvar before the exception reaches Sentry's auto-capture); `sentry_active` surfaced on `/security/status` (a malformed DSN makes init raise → silently dormant).
**Automation Hint:** backend error + status check.
**Source:** Part313 (`b5bbcf9`/`4371a65`)

### TC-P18-012
**Category:** Feature
**Test Name:** O6 agent span timing attributes per-node latency
**Steps:**
1. Run the LangGraph agent.
**Expected Result:** `agent_spans.py` `SpanTimer` emits `ms` on each `agent_step` + a `spans:[{node,ms}]` on done (e.g. retrieving 5304ms dominates); live-only (the generate call is already in `llm_calls`); `siem_triage` left alone (single judge call, one span). `useRagChat` split to `ragSseHandlers.ts` first (over 350 lines).
**Automation Hint:** assert spans present.
**Source:** Part314 (`3c2dbe0`/`e4000e7`)

### TC-P18-013
**Category:** Architecture
**Test Name:** Page Inspector is whole-site (captured in the root layout), an error log not an access log
**Steps:**
1. Trace where per-page errors are captured.
**Expected Result:** Root `AnalyticsTracker` global `window.error`/`unhandledrejection` → `/api/error` with `location.pathname` (any page; "password" routes skipped); backend `error_capture_dispatch` logs all 500s; ~6 tools enrich with `trackRunError` for handled in-band errors; blind spot = SSR render errors (surface as backend). It answers "what broke on this page", not "who visited".
**Automation Hint:** none (coverage from the capture path).
**Source:** Part314 (`project_page_error_log_coverage`)

---

## Self-Testing, Run-Live, TW-GROUND, Activity Log (Part 315)

### TC-P18-014
**Category:** Bug-Regression
**Test Name:** "author-failed" is often the daily cap, not a bug
**Steps:**
1. Self-test the site via the QA API; hit author-failed.
**Expected Result:** Mostly the author daily cap (429 checked BEFORE provider selection, so even Gemini can't bypass) — unblock by raising `QA_TEST_AUTHOR_DAILY_CAP`, not switching model. Classify before "fixing".
**Automation Hint:** none (method).
**Source:** Part315

### TC-P18-015
**Category:** Feature
**Test Name:** Run-Live uses a local Companion (a website can't launch a headed browser)
**Steps:**
1. Start the Companion; click Run Live.
**Expected Result:** A `127.0.0.1` daemon (`/health`, `/run`) runs the spec `--headed` locally; CORS locked to Testwright origins, target host allow-listed; CI stays the headless default.
**Automation Hint:** companion integration.
**Source:** Part315 (`aad6259`)

### TC-P18-016
**Category:** Bug-Regression
**Test Name:** TW-GROUND — five stacked authoring bugs on an SPA, each generalized
**Steps:**
1. Discover-author against `/tools/text-to-sql`.
**Expected Result:** (1) network-idle settle before `grabControls` + a 10c-ready wait (SPA renders controls after async load); (2) overlay dismiss-first (`===DISMISS===`, first-load tour hid the input); (3) open the given base_url verbatim (not `/sql` landing); (4) generic heading fallback, never empty; (5) the validator's `_OPT_KEY_DOT_LEFT` scanned INSIDE strings so a sentence heading ending in `.` false-matched "unparseable" → `_blank_strings` before the option-key-dot check. Bug #5 silently broke every sentence-style heading site-wide; found by reading the Space run logs.
**Automation Hint:** per-fix unit tests incl. the real `{name.` typo still rejected.
**Source:** Part315 (`ad07f63`…`636b39b`)

### TC-P18-017
**Category:** Feature
**Test Name:** Activity Log surfaces recovered failures the Errors panel misses
**Steps:**
1. View the Activity Log after 429s and an in-band author rejection.
**Expected Result:** `/api/activity` merges `llm_calls` (ok/warn/429/error) + `errors` into one chronological feed (All/Warnings/Errors chips, clickable rows); a 200-with-broken-payload author rejection is logged via `author._log_reject` (`status=error, http=422, output_rejected`) — it was invisible because the HTTP call succeeded (200) while the validator rejected one layer up.
**Automation Hint:** activity feed assertion.
**Source:** Part315 (`7f66d67`/`4d2d5dc`)

### TC-P18-018
**Category:** Architecture
**Test Name:** A transport "ok" is not an application "ok"
**Steps:**
1. Log a provider call that returns 200 but whose payload is then rejected.
**Expected Result:** The HTTP funnel logs `ok/200` (right place for provider errors), so the usefulness check one layer up must emit its own failure row — else the exact case the Activity Log exists for stays invisible.
**Automation Hint:** none (method).
**Source:** Part315

---

## Analytics Redesign (Part 316)

### TC-P18-019
**Category:** UI
**Test Name:** Analytics dashboard ported to the approved mockup (RowBars)
**Steps:**
1. Compare the live dashboard to the mockup.
**Expected Result:** Shared `AnalyticsBars` (`RowBars` flat=count/gradient=score, `SectionDivider`), plain Activity Log + legend, no card rails, Geist-Mono labels, title gradient; the mockup is the contract — deviations get raised, not improvised; verify by screenshotting both and diffing.
**Automation Hint:** visual/computed-style compare.
**Source:** Part316 (`0f94b01`…`6d05208`)

### TC-P18-020
**Category:** Bug-Regression
**Test Name:** Handbook Ch17 prose lives in its source chapter, not the generated file
**Steps:**
1. Regenerate `handbook.md`.
**Expected Result:** No diff — the observability prose was moved to `docs/chapters/realtime-analytics.md` (it had been hand-written into the generated `handbook.md` → permanent CI mismatch for a day). A generated file is output; edit the source.
**Automation Hint:** regenerate + `git diff --quiet`.
**Source:** Part316 (`a3d4950`)

### TC-P18-021
**Category:** Bug-Regression
**Test Name:** "Visitors by Country" is a real map (or bars), not dots on empty grid
**Steps:**
1. Open the geo panel; toggle Bars/Map.
**Expected Result:** Bars (country code→name) + a Map toggle rendering a real equirectangular world map (`world-equirect.svg`, lazy-loaded only on first Map click, themed via CSS); the old "map" was lat/lon dots on a gridless void. "Keep X" is still a decision that needs verifying.
**Automation Hint:** panel render check.
**Source:** Part316 (`6a5b43c`/`edbbe85`)

### TC-P18-022
**Category:** Bug-Regression
**Test Name:** Tool search matches title/subtitle/tags, not description prose
**Steps:**
1. Search "real" in ML Pipeline.
**Expected Result:** 1 result (not Periodicity Finder via "real time units" in its description) — `scoreTerm` dropped the description field; a keyword only in prose belongs in `tags`.
**Automation Hint:** search unit test.
**Source:** Part316 (`5b2efd8`)

---

## Phase 2: Fixtures, npm, Volatile Controls (Parts 317–318)

### TC-P18-023
**Category:** Feature
**Test Name:** Upload/camera tools are testable via fixtures + fake-media
**Steps:**
1. Author+run an EDA CSV-upload test and a face-liveness camera test on CI.
**Expected Result:** Both green — `qa-run.yml` sparse-checks-out `fixtures/` (had no checkout) + Chromium `--use-fake-ui/-device-for-media-stream` + `--use-file-for-fake-video/audio-capture`; `fixtures.py` emits a `===MEDIA===` grounding block → `setInputFiles('fixtures/<name>')`. "Testable" = a green run on the real runner, not "the mechanism runs".
**Automation Hint:** CI e2e on both.
**Source:** Part317 (`76edb9a`/`f89064d`)

### TC-P18-024
**Category:** Bug-Regression
**Test Name:** Dynamic control names are grounded to a stable prefix regex
**Steps:**
1. Author a test against the analytics dashboard (`Warnings 1`, `Activity Log — today`, `✦ AI Explain ▼`, card-title `<p>`s).
**Expected Result:** `stabilize_dynamic_control_names` matches a volatile tail (trailing count / ` — state` / caret) by a stable prefix (`/^Warnings/`); `fix_invented_heading_role` rewrites `getByRole('heading')` → `getByText` when the control is a `<p>`; stable/regex names untouched. One root cause (values baked into names), one central transform — in `name_grounding.py`.
**Automation Hint:** `name_grounding` unit tests.
**Source:** Part317 (`6ea5901`/`f1a4114`)

### TC-P18-025
**Category:** Bug-Regression
**Test Name:** Data-driven select, absent control groups, and query hrefs are grounded
**Steps:**
1. Author tests touching a data-driven `<select>`, country chips (absent when <2 countries), and an export link whose href encodes `?range`.
**Expected Result:** `stabilize_data_driven_select` → `{index:0}` + `toHaveValue(/.+/)`; `guard_noop_visibility_click` wraps a click-then-"still visible" in `if (await x.isVisible())` (skips when the group is absent); `stabilize_query_href_locators` → `a[href^="/path"]`. 6/6 green.
**Automation Hint:** per-transform unit tests.
**Source:** Part318 (`32adfe0`) / Part317 (`12636ef`)

### TC-P18-026
**Category:** Architecture
**Test Name:** A prompt rule the free model ignores is not a fix — enforce in code
**Steps:**
1. Compare the prompt-only `15-livedata` rule vs the code transform.
**Expected Result:** The free model ignored the prompt and still wrote `selectOption('ml-pipeline')`/"filter by US"; the real fix is a deterministic transform in the Author post-process. Deterministic beats prompt.
**Automation Hint:** none (method).
**Source:** Part318 (`ad09126` ignored → `32adfe0`)

### TC-P18-027
**Category:** Bug-Regression
**Test Name:** Run-Live Companion survives Node ≥22 (temp dir, not node_modules)
**Steps:**
1. Run Live under `npx` on Node 26.
**Expected Result:** Config written to an OS temp dir with node_modules symlinked in, Playwright called by resolved binary path (writing `.ts` into `__dirname/.tw-run` under `npx` is inside node_modules → `ERR_UNSUPPORTED_NODE_MODULES_TYPE_STRIPPING`); output shows on any non-pass (a crash gives `passed===null`); 15s expect timeout for lazy/ssr:false controls. Companion v0.2.2 (republish pending).
**Automation Hint:** reproduce the write+load.
**Source:** Part318 (`23e2115`/`6485221`)

### TC-P18-028
**Category:** Architecture
**Test Name:** npm publish now mandates 2FA (passkey/Touch ID), scoped org
**Steps:**
1. Publish `@airaml/testwright-companion`.
**Expected Result:** `npm login` (ENEEDAUTH), 2FA via a WebAuthn passkey/Touch ID (no authenticator app), create the free `airaml` org (E404 scope). Run-Live only works for everyone once published (npx fetched nothing before).
**Automation Hint:** none (process).
**Source:** Part317

### TC-P18-029
**Category:** Architecture
**Test Name:** Three logs, three jobs — a failed test is not a site error
**Steps:**
1. A generated test times out on a locator.
**Expected Result:** Correctly in none of the error logs — the Activity Log is LLM calls, the Errors/Page Inspector is JS crashes + 500s, the QA dashboard is test pass/fail. Unit tests prove the transform; only dogfooding proves the product.
**Automation Hint:** none (method).
**Source:** Parts317/318

---

## Crash-Durable Click Audit (Part 319)

### TC-P18-030
**Category:** Feature
**Test Name:** Click capture survives a hard crash (local-first outbox)
**Steps:**
1. Click, then crash the tab before the network send; reload.
**Expected Result:** `auditClick.ts` writes a localStorage outbox synchronously first, then `keepalive` fetch + `sendBeacon` on `pagehide`, flush-on-load, `event_uuid` dedupe; the API upserts on `event_uuid` → two writes of one id = exactly one row. `sendBeacon` survives navigation but not a true crash — only the sync local write does.
**Automation Hint:** crash-survival + dedupe test.
**Source:** Part319 (`5d40a01`)

### TC-P18-031
**Category:** Feature
**Test Name:** Any interactive click is captured, content-free, with a readable label
**Steps:**
1. Click an untagged button; open the gated viewer.
**Expected Result:** Every interactive element (not just `data-audit`-tagged) via `clickDescriptor` (`data-audit › testid › #id › tag[type][role]@css-path`) + a readable `label` (aria-label/visible text, capped 80); NEVER what's typed into a field; `/audit` lookup gated by `AUDIT_ADMIN_KEY`, fails closed (503 unset / 401 wrong), with a control-query and a timeline mode.
**Automation Hint:** gated-lookup + descriptor test.
**Source:** Part319 (`5d40a01`/`d690498`)

### TC-P18-032
**Category:** Bug-Regression
**Test Name:** Burst clicks all deliver (re-arm the flush after send)
**Steps:**
1. Click 3× rapidly.
**Expected Result:** Outbox drains to 0 — the `inFlight` guard dropped concurrent flushes; re-arm after a successful send. Durability (never lost) and timely delivery are separate properties, both tested.
**Automation Hint:** burst-flush test.
**Source:** Part319

### TC-P18-033
**Category:** Bug-Regression
**Test Name:** The default audit window reaches "now" (end of today)
**Steps:**
1. Load the viewer, click, then look.
**Expected Result:** Clicks made after load appear — the default "To" no longer freezes at page-load time (same window-boundary class as the earlier minute-truncation bug); three "not recorded" reports were all window/readability, proven by querying the live table.
**Automation Hint:** window-boundary test.
**Source:** Part319 (`9160cc6`)

### TC-P18-034
**Category:** Architecture
**Test Name:** Don't delete AGENTS.md (it shields CLAUDE.md)
**Steps:**
1. Check what `generate-agent-files.js` does when AGENTS.md is absent.
**Expected Result:** It injects its managed block into `CLAUDE.md` instead → deleting AGENTS.md pollutes the real instructions file on the next `next dev`; keep AGENTS.md and commit its auto-refresh. `feedback_keep_agents_md`.
**Automation Hint:** none (process).
**Source:** Part319 (`673c56d`)

### TC-P18-035
**Category:** Feature
**Test Name:** Aggregate audit dashboard: RPC-backed, baselines, hardened edges
**Steps:**
1. Open `/audit/dashboard`.
**Expected Result:** `click_audit_stats` RPC (all GROUP BYs server-side, one round-trip), same `AUDIT_ADMIN_KEY` gate; every KPI carries a prev-window delta (▲/▼ + %, arrow not color-only) + sparkline; `POST /api/audit` rate-limited 120/min per IP (the outbox retries a 429); `/audit` pages behind basic-auth via `proxy.ts` (password = the admin key); forgeability caveat stated (client mints the ids — the real app derives `actor` server-side).
**Automation Hint:** RPC + gate + rate-limit + basic-auth checks.
**Source:** Part319 (`1aa7a1d`/`ad131ef`)

### TC-P18-036
**Category:** Bug-Regression
**Test Name:** A width-bounded bar row must stretch, not auto-size (overflow)
**Steps:**
1. Render a dashboard bar row with a long control id.
**Expected Result:** 0px overflow — flex-column/block rows stretch to the card so the `min-width:0` ellipsis clamp engages (nested `display:grid` auto tracks sized to content → the id bled into the next column); structural id demoted to the hover title, readable label is the hero.
**Automation Hint:** `getBoundingClientRect` overflow check.
**Source:** Part319 (`b2a7520`)

---

## Cross-cutting / Process (Parts 310–319)

### TC-P18-037
**Category:** Architecture
**Test Name:** Build on the funnel/jsonb that already exists (migration-free where possible)
**Steps:**
1. Add correlation/telemetry.
**Expected Result:** O1 landed the trace id in `errors.meta.trace_id` (existing jsonb, no migration); O3 only grew `llm_calls` for genuinely new numeric fields; `run_id` was already the trace id. Wiring, not new infrastructure.
**Automation Hint:** none (method).
**Source:** Parts312–313

### TC-P18-038
**Category:** Architecture
**Test Name:** A broad `isMissingSchema`/`needs_setup` catch hides column typos
**Steps:**
1. Return `needs_setup` from an endpoint.
**Expected Result:** Verify against the live schema first — Postgres 42703 (undefined column) looks identical to a missing table, so a wrong column name became a silent "run the migration" that hid 283 rows. A check that silently passes on a typo is as bad as one that can't fail.
**Automation Hint:** none (method).
**Source:** Part313

### TC-P18-039
**Category:** Architecture
**Test Name:** Read the Space run logs before theorizing a QA/validator failure
**Steps:**
1. Diagnose a repeated author-failed / rejected-code case.
**Expected Result:** A content-free "head of rejected code" log named the validator bug instantly (two prior guesses were wrong); `/api/spaces/{id}/logs/run` + the kept `author.py` diagnostic. Debug-first beats guessing.
**Automation Hint:** none (method).
**Source:** Parts315/313

### TC-P18-040
**Category:** Architecture
**Test Name:** Batch the deploy; verify once (two-failures-stop)
**Steps:**
1. Fix a cascade of QA failures, each needing an HF upload.
**Expected Result:** Gather all fixes, deploy once, verify once (a rebuild per failure wastes the user's scarce time); verify stage==RUNNING (not RUNNING_APP_STARTING) before testing.
**Automation Hint:** none (method; Rule 5).
**Source:** Part318

---

**Total: 40 test cases, Parts 310–319.**
