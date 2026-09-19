# Part 294 — Testwright Phase 2, all the way to four live stages

Continues [Part 293](Session_2026-09-19_FromAToolCardToAPlatformWorld_Part293.md).
2026-09-19. Started with a guide correction, then built Testwright's whole
execution half — Run, artifacts, self-heal, Discover and the suite-level Heal —
each verified live before the next. Ended by stripping the competitor names and
"own-site" framing the platform never should have shipped with.

The through-line: **build the honest thing, verify it red-and-green, and say what
it is without apologising or name-dropping.**

---

## 0. The guide correction that opened the session

The Text-to-SQL *platform* was rendering the thin 72-line `userGuide.ts`
distillation (meant only as the AI chat's knowledge) as its "User Guide," not the
tool's real 403-line `UserGuideModal`. Fixed: the platform now opens the tool's
own comprehensive modal verbatim. Then made that modal actually usable — a
visible scrollbar (macOS hides overlay scrollbars) and a **search box** that
filters its 14 sections. Split it to stay under 400 lines. ml-portfolio
`2ae7a51`, `d00964a`.

Lesson (again): a guide is the real, comprehensive one users see, not the string
we feed the chatbot. Reuse the single source of truth.

---

## 1. The cost wall: HF Docker Spaces now need PRO

Phase 2 = actually run tests. The plan was a dedicated isolated runner Space.
Creating a new HF **Docker** Space returned **402 — PRO required**. The user was
right to flag cost. Co-locating a browser in the shared ML-Unified Space was
rejected (it would put Chromium in the container serving all 50 tools).

**Decision: execute on GitHub Actions.** Public-repo minutes are free and
unlimited, runs are fully isolated on GitHub's runners, and Playwright-on-Actions
is rock-solid. The trade-off (async: dispatch → poll) is covered by a
queued→running→results UI. The Node/Express runner scaffold from Phase 2a is
**parked**, not deleted — its bounded config + fixtures were reused.

Architecture (the seam held): browser → `qaClient` → `/qa/run/*` proxy on the
main Space (holds the GH token) → `workflow_dispatch` on the public
`ramleo/ml-qa-runner` repo → poll by run-name → download the artifact zip → back
to the UI. The GH token is a fine-grained PAT stored as the `GH_QA_TOKEN` Space
secret; it never reaches the browser.

---

## 2. Run, artifacts, and the reporter that lied

- **2b Run** — `/qa/run/execute` + `/qa/run/status/{id}`; pass/fail from
  `results.json`, not the run conclusion, so a **failing test keeps the run green
  and doesn't email the owner** (a QA tool's failures are normal). ML-Unified
  `91fc705`, `13a266c`; ml-portfolio `6a7ed47`.
- **2c.1 artifacts** — `/qa/run/artifact/{id}/{kind}` streams the **video**
  (inline) and **trace** (download) through the Space so the token stays
  server-side; the status returns a **step timeline** + `has_video`/`has_trace`.
  ML-Unified `b152e2c`, `9ee2594`; ml-portfolio `7000052`.
  - **Gotcha:** Playwright's built-in JSON reporter omits per-step data. A custom
    reporter in the workflow writes `steps.json`, which the proxy reads.

---

## 3. Self-healing locators (the headline)

On a failed run, **Heal & re-run** feeds the LLM the original test, the error, and
the **ARIA page snapshot Playwright already writes to `error-context.md`**, and
gets a corrected test back; the UI shows the diff (old → new) and re-runs it.
Locator repair only — a real bug still fails honestly. ML-Unified `45a222a`;
ml-portfolio `ce360e7`, guide `8812e66`. Verified live: `name: 'AIRaML Platform'`
→ `name: 'AIRaML'` → re-run passes.

---

## 4. Discover (Phase 3) and the whole four-stage lifecycle

- **Discover** — an "explore" run (reusing the qa-run workflow) dumps the page's
  `ariaSnapshot()` to `aria.txt`; the LLM proposes ≤6 test cases; pick some →
  Author drafts each → Send to Run. ML-Unified `2f2df3f`,
  `ramleo/ml-qa-runner` `a4bf61b`; ml-portfolio `f45b790`.
- **Saved tests + run-history dashboard** — per-visitor `localStorage` (no login):
  Save a test, re-load/re-run it, and a Recent-runs panel with a pass-rate.
  ml-portfolio `ab820bf`.
- **Heal stage (Phase 5)** — run the saved tests as a suite, `/qa/heal/group`
  buckets failures by signature (the failing locator) into "1 issue · N tests,"
  and Heal-all reuses per-run heal + execute. ML-Unified `2cdc7b7`; ml-portfolio
  `5317ceb`. Verified: 2 same-cause failures → 1 group → both healed·passed.
- **User Guide button** added to every stage page (`906ad3e`).

All four stages — Author, Run, Discover, Heal — are now **live**.

---

## 5. Drop the competitor names; stop restricting to our own site

The user, on seeing the copy: *"why are you mentioning testRigor, Katalon … it is
not only for our website, don't restrict it."* Both fair.

- Removed **every** testRigor/Katalon mention and the "device farm / for our own
  site / where the line is" framing from the UI and guide; rewrote to confident,
  current copy with honest limits stated plainly.
- Replaced the own-site allowlist with `routers/qa/urlcheck.py`
  `validate_target_url`: **any public http(s) URL** is accepted; only
  private/internal addresses (localhost, LAN, link-local, metadata IPs) are
  blocked. Abuse stays bounded by the per-stage daily budget caps. ML-Unified
  `85ceb0c`; ml-portfolio `4423252`.
- Fixed the stale Author-only landing (hero + closing CTA still said "Author runs
  today, Run is next"). ml-portfolio `361febb`.

---

## Logging status

No new logging work was needed: every stage page calls `useToolTracking`
(`qa-world`, `qa-test-author`, `qa-run`, `qa-discover`, `qa-heal`) and all backend
calls go through `qaClient` → `trackedFetch`, which emits `run_start` /
`run_success` / `run_error`. The full `LOGGING_SPEC.md` event vocabulary
(upload / config_change / result_view) remains the separate, deferred item.

---

## Commits

| Repo | Commits |
|---|---|
| ml-portfolio | `2ae7a51` `d00964a` (guide) · `6a7ed47` `7000052` `ce360e7` `8812e66` (Run/artifacts/heal) · `f45b790` `ab820bf` (Discover/saved) · `906ad3e` `5317ceb` (guide btn/Heal) · `4423252` `361febb` (copy) |
| ML-Unified | `f916883` `dab439e` (2a/pivot) · `91fc705` `13a266c` `b152e2c` `9ee2594` (Run/artifacts) · `45a222a` (heal) · `2f2df3f` `85ceb0c` `2cdc7b7` (Discover/URL/Heal) |
| ramleo/ml-qa-runner | `2348f3f` (workflow) · `7ed911a` (green-on-fail) · `3644860` (steps.json) · `a4bf61b` (aria.txt) |

---

## The five backlog items (agreed order, not yet built)

The user asked to do these next, after the above:

1. **Flakiness detection** — *best ROI, do first.* Run a test N× via Playwright
   `--repeat-each`; `results.json` already reports flaky. Small: a "run 5×" toggle
   + surface the flaky count. Cost: N× CI minutes (free).
2. **Assertion suggestions** — LLM proposes assertions from a page snapshot.
   Small (snapshot + LLM already exist), but overlaps with Author/Discover — low
   marginal value.
3. **Visual regression** — `toHaveScreenshot()` diff vs a baseline. **Large + poor
   fit:** no persistent baseline storage, and our own site's particle canvas makes
   pixel diffs permanently flaky. Scope carefully or skip.
4. **Third-party sites (ownership-gated)** — mostly **moot now** that any public
   URL is allowed; a formal ownership-verification flow is the only remaining part.
5. **Record-and-playback authoring** — click-through → test. Large; real codegen
   needs a live driven browser (not feasible free/isolated). Plain-English +
   Discover already cover authoring.

---

## Pending — DEFERRED TO TOMORROW (2026-09-20, user's call)

Both were raised this session and consciously pushed to the next day:

- **Turn ml-unified / eda-explorer / ml-vision into native platform worlds** like
  `/qa` and `/sql`. All three are modes of one HF Space
  (`wram1708-ml-unified.hf.space?mode=ml|eda|vision`); each gets a landing world
  (hero + sections + User Guide + AI chat) that launches its mode, reusing the
  shared `WorldShell` / `WorldNav` / `WorldUserGuideModal`, with its `registry.json`
  entry flipped to `internal:true` + an `href`. Three `/sql`-sized builds.
  **Approach:** build **ML-Unified first as the template**, verify live, then
  replicate to EDA + Vision. Not started.
- **Handbook** — generated by `scripts/build-handbook.py` from `capabilities.ts`
  + `registry.json`. It has a Platforms section (now 5 entries) but a naive
  regenerate would **drop the Text-to-SQL chapter** (that card left
  `capabilities.ts`). **Decided approach (do tomorrow):** teach the script to keep
  graduated-tool chapters (and add a Testwright chapter), then **regenerate
  `handbook.md` and diff** before committing.

---

## Lessons

- **Check the cost before committing to the host.** A new HF Docker Space is no
  longer free; GitHub Actions is (public repo) and more isolated anyway.
- **The failure artifacts already had what we needed** — `error-context.md` is a
  YAML ARIA snapshot; reuse it for healing instead of building capture.
- **Don't trust a reporter's defaults** — the JSON reporter omits steps; a 6-line
  custom reporter fixed the timeline.
- **A QA tool's failures are normal** — keep the CI run green and read pass/fail
  from the data, or you spam the owner's inbox.
- **Say what it is.** No competitor name-drops in your own product; no apologetic
  "for our own site." Match the claim to what the tool actually does.
