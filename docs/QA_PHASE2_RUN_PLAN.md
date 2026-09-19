# Plan: Testwright Phase 2 — Run (execution + artifacts + self-healing)

Continues the platform plan in [QA_AUTOMATION_AND_LOGGING_PLAN.md](QA_AUTOMATION_AND_LOGGING_PLAN.md).
Phase 1 (**Author** — plain English → runnable Playwright TS) is live. Phase 2
closes the loop: actually **run** the generated test, prove it with real
artifacts, and **self-heal** broken locators.

Status: **SHIPPED — all four stages live (2026-09-19).** Written 2026-09-19.

> **UPDATE — DONE.** Phase 2 (Run + artifacts + self-heal), Phase 3 (Discover) and
> Phase 5 (suite-level Heal) are all live, plus saved tests + run history.
> Execution runs on **GitHub Actions** (a new HF Docker Space now needs PRO — see
> the REVISION section). Tests run against **any public site** (own-site allowlist
> removed; private/internal blocked). Full build narrative + commits:
> [Conversations/Session_2026-09-19_Phase2ToFourStagesLive_Part294.md](../Conversations/Session_2026-09-19_Phase2ToFourStagesLive_Part294.md).
> Remaining backlog (agreed order): flakiness detection, assertion suggestions,
> visual regression, third-party ownership gating, record-and-playback.

Original locked decisions (2026-09-19): a dedicated isolated runner Space + full
Phase 2 scope. The Space decision was superseded by the 402/PRO wall (GitHub
Actions instead); the scope was delivered in full and extended through Discover
and Heal.

The north star: this is a recruiter-facing highlight. It must **work properly,
be foolproof, and be tested properly** — pass *and* fail both provably detected,
not just a green screenshot.

---

## REVISION 2026-09-19 — execution moves to GitHub Actions (still free, still isolated)

The dedicated-Space plan below is **superseded.** Creating a new HF **Docker**
Space now returns **402 Payment Required** — HF requires a PRO subscription to
host Gradio/Docker Spaces on free CPU-basic. The user is cost-bound to **$0**, so
we do not pay.

Co-locating the browser inside the existing (already-running) ML-Unified Space
was rejected: Playwright's test runner is Node, so it would mean adding
Node + Chromium into the Python Space that serves all 50 tools + the SQL
platform — bloating the image, slowing every backend deploy, and putting a
browser inside the shared production container. That defeats the foolproof goal.

**Decision (user, 2026-09-19): execute tests in GitHub Actions.** Public-repo
Actions minutes are free and unlimited, runs are fully isolated on GitHub's
runners (zero risk to our site), and Playwright-on-Actions is a first-class,
cached, battle-tested path. Trade-off: execution is **async** (dispatch → poll),
covered by a "queued → running → results" UI. The scaffold in
`services/ml-qa-runner/` (Express + Dockerfile) is **parked**, not deleted — its
bounded Playwright config and known-good/known-bad fixtures are reused by the
Actions workflow; the Space path can be revived if we ever hold PRO.

The **local proof still stands and is not wasted**: the runner logic (pass/fail
detection, screenshot capture, SSRF allowlist, input validation) was verified
end-to-end locally at $0. Only the *host* changed.

### Execution via GitHub Actions — architecture

```
browser → qaClient → /qa/run/* (main Space proxy, holds GH token)
        → GitHub API workflow_dispatch (test code as input, unique correlation_id)
        → isolated Actions runner: setup-node → install Playwright+Chromium
          → run the test under our bounded config → upload results.json + artifacts
        → proxy polls run status, matches by run-name, downloads the artifact zip
        → returns pass/fail + summary + screenshot/trace/video to the UI
```

- **Where the workflow lives:** a dedicated **public** GitHub repo `ml-qa-runner`
  (free unlimited minutes; keeps third-party test runs out of the main repos' CI;
  reinforces the "isolated runner" story). Creating it is a free but outward
  action — confirm before creating, same as the Space.
- **The seam is unchanged:** the main Space still exposes `/qa/run/*` in
  `routers/qa/` (a small `github_runner.py` in that package, reached via
  `deps.py` for limiter/budget). Frontend still uses only `qaClient.ts` → the GH
  token never reaches the browser. Swapping execution backends later = swap this
  one module.
- **Correlation:** the proxy passes a `correlation_id`; the workflow sets
  `run-name: qa <correlation_id>` so the proxy can find the run reliably by name
  (workflow_dispatch returns no run id).
- **Results come back trustworthy, not via a callback:** the proxy reads run
  status and downloads the artifact zip through GitHub's authenticated API, so
  results can't be spoofed by an open callback endpoint.
- **Token:** a fine-grained GitHub PAT scoped to `actions:read/write` on that one
  repo, stored as an HF Space secret `GH_QA_TOKEN`. Never logged or echoed. The
  user-submitted test step gets **no** repo secrets in its environment.

### Revised sub-phases (supersede the Space sub-phases below)

- **2a — DONE (local proof).** Runner logic verified locally at $0: known-good →
  passed, known-bad → failed + screenshot, disallowed baseUrl → 403, empty →
  400. Committed `f916883` (scaffold, now parked for the Space path).
- **2b — GitHub Actions execution end-to-end (no UI yet).** Create the public
  `ml-qa-runner` repo + the `qa-run.yml` workflow; add `/qa/run/execute` +
  `/qa/run/status/{id}` proxy on the main Space; store `GH_QA_TOKEN`. Acceptance:
  dispatch the known-good and known-bad tests via the proxy and get correct
  pass/fail + a failure screenshot back — verified by curl, not UI.
- **2c — `/qa/run` UI + full artifacts.** Real runner page: carry a test from
  Author, run it, show queued → running → results with screenshot, playable
  video, and a downloadable trace + step timeline.
- **2d — Self-healing locators.** On a locator failure, the proxy asks the LLM
  (via `deps.py`, cohere→mistral) to re-resolve the element from the page's
  accessibility snapshot captured by the workflow; re-dispatch with the healed
  locator; report "healed: old → new".

The safety envelope and testing plan below still apply in full (allowlist,
timeouts, caps, cleanup; known-good + known-bad + heal-proof fixtures). The
sections from here down describe the original Space design, kept for the record.

---

## Why a dedicated runner Space (superseded — see REVISION above)

Running a real browser is heavy and occasionally hostile (a hung page, a memory
spike, an infinite redirect). The ML-Unified Space hosts *every* tool on the
site; a runaway browser there would degrade unrelated tools. Isolating execution
in its own Space means:

- **Blast radius = zero** for the rest of the site. If the runner falls over, the
  50 other tools and the SQL platform are untouched.
- **It is literally the microservice** the whole QA design pointed at. The
  "isolated execution service" is a strong architecture story in itself.
- It runs the **real generated TypeScript** via `npx playwright test`, so what
  the user sees in Author is exactly what runs. No IR mismatch.

### The seam (keeps microservice-readiness intact)
- Main API gains one thin proxy route group `/qa/run/*` in `routers/qa/`, reached
  — like everything in that package — only through `routers/qa/deps.py`. It calls
  the runner Space over HTTP and streams results back. The main Space never runs a
  browser.
- Frontend keeps its single `qaClient.ts` → `QA_API`. It never talks to the
  runner directly (the runner has no public CORS surface for the browser).
- The runner Space is a **self-contained FastAPI + Node/Playwright** service with
  its own repo folder (`services/ml-qa-runner/`), its own Dockerfile, its own HF
  Space. Extraction later = it is already extracted.

```
browser → qaClient → /qa/run (main Space, proxy) → ml-qa-runner Space (browser) → artifacts back
```

---

## Sub-phases (each verified before the next begins)

### 2a — Execution spike (FIRST, before any UI)
The make-or-break. Prove the environment before building on it.
- New `services/ml-qa-runner/`: Dockerfile with Node + `@playwright/test` +
  Chromium; a minimal FastAPI `POST /run` that writes the posted `.spec.ts` to a
  temp dir, runs it under a bounded Playwright config, and returns the JSON
  reporter result.
- Create the `ml-qa-runner` HF Space, deploy once.
- **Acceptance:** against our own site, one **known-good** test returns `passed`
  and one **known-bad** test returns `failed` — both correctly — with a failure
  screenshot captured. Verified by direct curl, not UI.
- If the free-tier Space can't run Chromium reliably within memory/time, we learn
  it here, cheaply, before writing a line of UI.

### 2b — Run endpoint + minimal UI
- `/qa/run/execute` proxy on the main Space → runner. Request carries the test
  code (+ optional base URL); response carries status, per-test results, console
  log, and the failure screenshot.
- `/qa/run` page becomes a real runner: paste a test, or carry one over from
  Author ("Send to Run"), press Run, see pass/fail + log + screenshot.
- Safety envelope enforced here (see below).

### 2c — Full artifacts
- Capture **video** (`retain-on-failure`) and a **Playwright trace**
  (`on-first-retry`) in addition to the screenshot.
- `/qa/run` shows a **step timeline** (action → status → thumbnail) and links to
  download the trace (`npx playwright show-trace`) and play the video inline.

### 2d — Self-healing locators (the headline)
- On a locator failure, the runner captures the page's **accessibility snapshot**
  and asks a free LLM (via `deps.py` → `complete`, cohere→mistral cascade) to
  re-resolve the intended element to a new resilient locator.
- Retry with the healed locator; on success, the result reports
  **"healed: `old` → `new`"** and the rerun outcome.
- The UI surfaces every heal explicitly — this is the differentiator testRigor and
  Katalon sell, done honestly on a free stack.

---

## The safety envelope (non-negotiable, enforced from 2b)

- **Own-site allowlist (SSRF).** The runner refuses any base URL not on an
  explicit allowlist (our own domains). Running arbitrary third-party URLs is an
  SSRF and abuse risk; third-party targets come later, gated by ownership proof.
- **Hard wall-clock timeout** per run, enforced by killing the whole process
  tree — not just the test, the browser too.
- **Output + resource caps:** max test size, max artifact size, capped console
  capture, single-worker execution, no parallel fan-out on the free tier.
- **Guaranteed temp-dir cleanup** in a `finally`, so a crash can't leak disk.
- **Budget + rate limit** reuse the existing `security.rate_limit` / budget seam
  via `deps.py`; self-healing LLM calls draw on the QA budget pool.

---

## How we make it foolproof (testing plan, built alongside — not after)

Per the project rule "build a test the tool can fail":

- **Deterministic harness tests** (run in CI, no model, hard assertions):
  external URL rejected; malformed / non-Playwright input handled gracefully;
  timeout actually fires and kills the browser; artifacts cleaned up on both
  success and failure paths.
- **Known-good + known-bad fixtures** committed against our own site, asserting
  the runner reports `passed` for one and `failed` for the other. Green-only is
  not proof.
- **Heal proof fixture:** a test with a deliberately-broken selector that
  self-healing must repair; if the heal doesn't fire and fix it, the test fails.
- **Live smoke** after each deploy: curl the runner with the fixtures, confirm the
  new code is actually serving (not just stage=RUNNING) before any UI test.

---

## Backlog beyond Phase 2 (the "lots of features", later)

- **Discover (Phase 3):** crawl our own site, LLM proposes candidate test cases
  from the DOM / sitemap, user confirms, generate + run.
- **Flakiness detection:** run N times, report a flakiness score.
- **Visual regression:** screenshot diff against a saved baseline.
- **Assertion suggestions:** LLM proposes assertions from a page snapshot.
- **Saved suites + run-history dashboard:** ties into `LOGGING_SPEC.md`.
- **Heal at scale (Phase 5):** group many failures by one root cause
  ("1 issue, 12 tests"), fix in bulk.

---

## Risks / open items to confirm as we go

- **Chromium on HF free tier** — memory/time headroom is unproven; 2a exists to
  de-risk exactly this. If it fails, fallbacks: smaller browser footprint, or the
  step-IR execution model as a degraded mode.
- **Creating a new HF Space** is an outward action — confirm before creating
  `ml-qa-runner`; capture how its write token is stored (same pattern as the `hf`
  remote, never echoed).
- **Rebuild time** for a Node+Chromium image is long; batch changes, deploy once
  per sub-phase, verify once.
