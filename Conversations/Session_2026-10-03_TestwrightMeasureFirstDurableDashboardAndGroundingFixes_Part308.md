# Part 308 — Testwright: measure-before-building, durable dashboard, and the grounding fixes behind real reds

Continues [Part 307](Session_2026-10-03_TestwrightGroundedActionGateAndPerTestVisibility_Part306.md)
(Part 307 lives in the Part 306 file). 2026-10-03. After the predictor work, this arc cleared two
parked tracks (learn-from-edits → measurement only; R7 → durable dashboard), diagnosed real failing
suites down to grounding bugs, and rebuilt the dashboard's outcome strip to stop being misleading.

Through-line: **don't build on a guess — ship the cheap counter and let data decide; and when a
run goes red, chase it to the deterministic cause, don't add another prompt rule.**

---

## Arc 1 — Learn-from-edits: measure first, build later (`dbb1082`)
The feature would make generation learn from a user's corrections. But its own plan (§12 of
`docs/QA_LEARN_FROM_EDITS_PLAN.md`) says: only build if corrections are STILL frequent now that
locators are grounded — and that's browser-local with **no telemetry**, so we couldn't answer it.

So instead of building a whole feedback loop on a guess, shipped **Phase 0 = measurement only**
(frontend-only, no backend): a content-free `TEST_EDITED` analytics event (mirrors the existing
`SQL_EDITED`) fires when a user SAVES a generated test they changed, classifying the edit as
**locator / assertion / other** with **assertion-precedence** (an `expect()` wrapping a locator
counts as assertion, so it doesn't falsely inflate "locators still broken"). Emits only a
changed-line count + three booleans — no code, host, or text. Files: `src/app/qa/run/corrections.ts`
(NEW — `editMeta` + `trackEdit`), `RunRunner.tsx` (baseline tracked on Send-to-Run, diffed on Save),
`logEvents.ts`. Plan doc updated to "Phase 0 shipped, Phase 1 gated on its data" (`f6e783f`).

**Verified live end to end:** drove the deployed Run UI, confirmed `/api/track` receives
`test_edited` with the right content-free meta, and that both events persisted
(`/api/events/recent`). The **Live Feed only streams inserts while open** (no backfill), so the
2 earlier events never showed retroactively — fired a fresh batch with the dashboard open and they
appeared; the "Events by Type" donut caps at the top 8 so a 2-event type won't show there (expected,
not a bug). **Decision rule for Phase 1:** if `assertion_change`/`other_change` prove common → build;
if corrections stay rare → park for good. [[feedback_document_only_when_needed]]

## Arc 2 — real failing suites → two grounding fixes
Diagnosed a user's failing handbook/platforms suite with live evidence. Not one bug — a mix, and
two were deterministic grounding gaps:

- **Hidden-heading assertion (`af68989`, HF).** A test asserted
  `getByRole('heading', { name: 'The AIRaML Handbook' }).toBeVisible()` and failed — the heading
  EXISTS but is **visually hidden** (it's in the handbook's print/PDF layer, `offsetParent: null`).
  Root cause: the deep-crawl heading capture used a raw `$$eval('h1,h2,h3')` that included hidden
  headings, so generation grounded on one that isn't on screen. Fix: filter to VISIBLE headings
  (`getBoundingClientRect` size + `visibility`). **Present ≠ visible** — same lesson as the predictor
  empty-state. I verified the real behavior on the live page BEFORE encoding it (a naive
  DOM-presence check would have shipped a false-RED). [[feedback_status_claims_need_evidence]]
- **Misread locator name (`49b6ca1`, HF).** A test used `getByRole('button', { name: 'PDF for
  print (AA)' })` when the real button is **"PDF for print (A4)"** — the model misread the name.
  The grounded-action gate drops ungrounded INTERACTIONS but deliberately never touches assertions,
  so a misread name in an `expect()` shipped and failed. Fix: `action_gate.repair_ungrounded_names`
  — when a getByRole name isn't in the captured context but EXACTLY ONE captured name for that role
  is a very close match (difflib cutoff 0.86), **rewrite it to the real name**. Repairs, never drops
  — safe on assertions too (same spirit as `disambiguate_locators`). Unit-verified on the real
  AA→A4 shape plus correct/dynamic/ambiguous/heading cases; smoke-verified no regression on deploy.

## Arc 3 — R7 Dashboard-B: durable, cross-device run history (`4bfd4f1`)
The Run dashboard only trended runs in ONE browser's localStorage. Added a durable source:
- Supabase `qa_runs` table (content-light: name, outcome, per-test counts, flaky, timing, run_url,
  clipped reason — NO code/screenshot; RLS service-role only, mirrors `qa_shared_runs`).
- `POST /api/qa-run/log` (writes-gated so local dev can't pollute prod; logs every COMPLETED run;
  returns `needs_setup` until the migration is run) + `GET /api/qa-run/stats` (returns rows shaped
  like the local `HistoryEntry`, so the client **reuses the same `computeDashboard` + charts** — no
  chart duplication).
- `RunDashboard` gets a **"This device" ↔ "All runs"** toggle + a setup-hint state; privacy page
  discloses it. Decision (user): log EVERY completed run, not just saved/shared.
- **Requires a ONE-TIME manual migration** (`supabase/qa_runs.sql` in the Supabase SQL editor).
  **Verified live:** migration run → real passing run logged → stats returns it → "All runs" shows
  "across devices (1)", gauge 100%. Used a REAL run (not injected fakes) so the dashboard stays honest.

## Arc 4 — R5 (authenticated testing): planned, stays deferred
Design is already complete in `TESTWRIGHT_IMPROVEMENT_PLAN.md` §9a (model A: GitHub-Secrets +
`storageState` setup project). It stays **deferred** for a real reason, confirmed with the user:
**there is no login-gated app to test**, and R5 can't be verified end to end without one (plus it
needs repo Secrets + an `ml-qa-runner` workflow change). Building a security-sensitive, unverifiable
feature would break the evidence-first rule. Revive when a real authed target exists.

## Arc 5 — the dashboard was misleading; made it a labelled, interactive dual view (`0acf47d`, `86bf7eb`)
User: a run of "4 passed · 1 failed" showed as ONE red bar in "Outcomes over time", with no way to
tell 5 tests = 1 run; and the strip was bland. Web-searched current dashboard practice (drill-down,
hover-to-reveal, clear labels) + applied the `dataviz` skill.
- NEW `src/app/qa/dashboard/OutcomesPanel.tsx`: a **[ Runs | Tests ] toggle** with a plain caption
  each ("each bar = one run — red if any test failed" / "a run of 5 tests becomes 5 bars"), per-bar
  **hover tooltips**, and **click a run bar → inline per-test breakdown** (status/title/duration +
  the failure's error, no re-run). `storage.recordRun()` now logs each run to local history WITH
  per-test detail (`HistoryEntry.testDetail`) AND the durable log in one call; `computeDashboard`
  builds run + test sequences; `RunRunner` uses recordRun (leaner). Only NEW runs have the
  drill-down; older entries show counts + a "re-run to capture" note.
- **href run-on fix (`86bf7eb`, HF).** The failing "ML Unified Platform" test used a card link's
  long run-on accessible name (`getByRole('link', { name: 'ML Unified PlatformPlatform · Enter…' })`)
  that times out. `href_link_locators` SHOULD rewrite it to `a[href="/ml"]` but combined both prefix
  directions into ONE tier, so it tied between the /ml card (map label starts WITH the code name)
  and a shorter sibling link named just "ML Unified Platform" (code name starts with THAT) → two
  hrefs → bailed. Fix: split into DIRECTIONAL tiers (exact → map-starts-with-code → code-starts-with-map
  → substring); the model usually TRUNCATES a long name, so map-starts-with-code wins and resolves
  uniquely to `a[href="/ml"].first()`. Simulation + real-case confirmed.
- **Verified live** with seeded sample runs in an ephemeral test browser (the owner's real history
  is untouched): screenshots show both views, the hover tooltips, the selected-bar ring, and the
  drill-down naming the failing test with its error inline.

## Key decisions
- **Measure before building.** When a build-or-not call hinges on unknown usage, ship the cheap,
  content-free counter first (Phase 0) and let data decide — don't build the feature on a guess.
- **Repair, don't drop, a misread name.** Renaming a unique close match to the real captured name
  is safe on assertions; dropping assertions is not (Part 306's "gate interactions only" still holds).
- **Run-level ≠ test-level.** Surface BOTH, clearly labelled, and let the user drill in — a single
  red bar for a mostly-passing run is misleading on its own.
- **Reuse the aggregation.** Durable rows shaped like the local `HistoryEntry` let one
  `computeDashboard` + one set of charts serve both the local and cross-device views.
- **Verify a post-action / visibility claim on the live app before encoding it.** DOM presence is
  not visibility; a naive check would have shipped a false-RED.

## Open / deferred
- **Learn-from-edits Phase 1** — gated on real `test_edited` data (Phase 0 is live).
- **R5 authenticated testing** — deferred until a login-gated app exists.
- Memory `project_testwright_run_perf.md` is ~265 lines — split when it nears 350.

## Commits
| Repo | Commits |
|---|---|
| ml-portfolio | `dbb1082` (learn-from-edits Phase 0 measurement) · `4bfd4f1` (R7 durable dashboard) · `0acf47d` (interactive dual-view outcome strip) |
| ML-Unified (backend, HF) | `af68989` (visible-headings filter) · `49b6ca1` (misread-name repair) · `86bf7eb` (href directional tiers) |
| ML-Unified (docs) | `f6e783f` (learn-from-edits Phase 0 status) |

Related: [[project_testwright_run_perf]], [[project_testwright_qa_platform]],
[[feedback_status_claims_need_evidence]], [[feedback_document_only_when_needed]], [[feedback_debug_first]].
