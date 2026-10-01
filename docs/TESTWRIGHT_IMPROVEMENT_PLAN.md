# Testwright (QA platform) — Improvement Plan

**Status:** mostly shipped (updated 2026-10-01). P0 (container, exec-time, Stop/cancel),
P4 (self-heal grounding + confirm-before-rerun) and P5 (progress polish) are **done and
verified live** — see §5. Only open item: D, a warm/self-hosted runner for seconds-fast
runs (recommended skip for a free public portfolio).
**Scope:** the **Run** stage (execute a Playwright test on isolated CI) and its
self-heal. Author/Discover/Visual are out of scope except where they share the
runner. **Owner doc** for the work below.

Companion code: backend `services/ml-api/routers/qa/` (`run.py`, `github_runner.py`,
`heal.py`, `config.py`); frontend `ml-portfolio/src/app/qa/run/` (`useRun.ts`,
`RunRunner.tsx`); runner repo **`ramleo/ml-qa-runner`** (`.github/workflows/qa-run.yml`).

> **Non-negotiable constraint — no regressions.** Every change here must keep all
> existing Testwright functionality working exactly as before: Run pass/fail +
> summary, per-step timeline, failure screenshot, run **video** and **trace**
> artifacts, flakiness/repeat runs (`runs` 1–10, pass-rate), self-heal + its diff,
> **Save test / Load / Re-run**, recent-runs history, the **Author → Run** handoff
> (`qa_run_code` in sessionStorage), and the other stages (Author/Discover/Heal/
> Visual) that share `github_runner`/`qaClient`. Nothing below may break, remove, or
> silently change any of these. Each phase ships only after the regression checklist
> in §7 passes.

---

## 1. How Run works today

`POST /qa/run/execute` fires a `workflow_dispatch` at the public `ramleo/ml-qa-runner`
repo; the browser then polls `GET /qa/run/status/{id}` every 4s (up to ~6 min single /
~13 min flaky) while GitHub Actions runs the test on a fresh `ubuntu-latest` runner and
uploads artifacts (summary, steps, screenshot, video, trace). Nothing executes in the
Space or the user's browser.

## 2. Evidence (measured live 2026-09-30)

- A trivial passing sample took **~68s wall-clock**; the **actual test ran ~0.9s**
  (Launch 205ms, navigate 317ms, 2 asserts ~250ms). **~99% of the time is CI setup.**
- The runner workflow reinstalls everything **every run**: `npm i -D @playwright/test`
  + `npx playwright install --with-deps chromium` (~150MB download + apt). **No browser
  cache, no npm cache, no prebuilt container.** That is the ~2-min fixed cost.
- **No Stop/Cancel control** during a run — the button only flips to a disabled
  "Running…". `useRun.reset()` stops the *client poll* but **not** the GitHub job (no
  cancel endpoint, no GitHub cancel call). A queued/slow job keeps burning minutes.
- **Self-heal does re-run** (`RunRunner.tsx:72`): heal LLM → `setCode` → `run(...)` =
  a second full cold CI cycle.
- **A real self-heal failure, root-caused:** the heal fixed the link (`Browse the
  tools`) and heading (`58 tools, each live and testable`) correctly, but emitted
  `getByPlaceholder('Search all 58 tools')` — the real placeholder is
  `Search 58 tools — try "malware", "PDF" or "SHAP"…`. `getByPlaceholder` is a
  substring match; the guess isn't a substring → `.fill()` timed out → **1 failed**.
  The heal **hallucinated an exact string** instead of grounding it in the DOM.

## 3. Problems, ranked

| # | Problem | Impact |
|---|---|---|
| P1 | ~2-min cold install every run (no cache/container) | Every run slow, even 1-line tests |
| P2 | No way to stop a run | User stuck; runner minutes wasted |
| P3 | No execution-time shown | Can't tell test time from CI overhead |
| P4 | Self-heal hallucinates locators + costs a 2nd full cycle | Heals that still fail, slowly |
| P5 | Queue/timeout opacity | "Timed out" while job still runs on GitHub |

---

## 4. Solutions — every viable option, with trade-offs

### P1 — Speed (the big one)

| Option | How | Saves | Trade-off | Verdict |
|---|---|---|---|---|
| **A. Official Playwright container** | job `container: mcr.microsoft.com/playwright:v1.55.0-jammy`; drop `playwright install` + setup-node (browsers/deps/node in image) | **MEASURED modest** (see note) | GH-hosted runners are ephemeral & DON'T persist Docker layers → the ~2GB image is re-pulled each run, ~offsetting the browser-install it removes | **Shipped 2026-09-30** |
| B. Cache browsers + npm | `actions/cache` on `~/.cache/ms-playwright` keyed by PW version + `setup-node cache:'npm'`; still run `playwright install-deps` (cache holds binaries, not OS libs) | ~30–60s/run on hit | cache-miss falls back to full install; needs a committed lockfile | Good fallback / combine |
| C. Commit `package.json`+lockfile to runner repo, `npm ci` | replaces on-the-fly `npm i` | ~10–20s + enables npm cache | must bump lockfile when PW version changes | Do alongside A or B |
| D. Self-hosted / warm runner (or long-lived container pool) | pre-provisioned runner keeps browsers+deps hot | ~ all setup → runs in seconds | infra + security to run/maintain; the app is public | Later, if speed critical |
| E. Reduce work | `--with-deps` only needs OS libs once (moot under A); already chromium-only, workers:1 | small | none | Included in A |

**MEASURED (2026-09-30, container shipped `ml-qa-runner` 5ee9264):** trivial test went
~68s → **~50–56s** (two live runs: 55.8s, 50.1s; test itself ~0.9–1.1s). A real but
**modest** win — the earlier "~10–20s" estimate was wrong: GitHub-hosted runners are
ephemeral and re-pull the ~2GB image every run, so it replaces the browser download
rather than eliminating the setup floor. **To actually reach seconds you need D (a warm
/ self-hosted runner that persists the image + browsers)** — that is now the real
speed lever, not the container. Option B (browser cache) is comparable, not better,
because the OS-dep install remains. Net: container kept (modest gain, cleaner, no
regression), but **speed is essentially download-bound on GitHub-hosted runners**.

### P2 — Stop / cancel a run

- Backend: `POST /qa/run/cancel/{correlation_id}` → `github_runner.find_run` →
  `POST /repos/ramleo/ml-qa-runner/actions/runs/{run_id}/cancel` (202; use
  `/force-cancel` as fallback when a job won't respond). Token already has repo scope
  (`GH_QA_TOKEN`).
- Frontend: show a **Stop** button while `phase ∈ {queued,in_progress}` that calls the
  endpoint **and** sets `cancelled.current=true` (stop polling). Reflect a
  `cancelled` conclusion in the UI.
- Edge cases: a run not yet created (dispatch→run-id gap) — Stop should mark intent and
  cancel as soon as `find_run` resolves; a run already completed — no-op.

### P3 — Show execution time

Two distinct numbers, show both, labelled:
- **Test time** — sum of step durations (already parsed) or the Playwright report's
  total; ~sub-second for simple tests.
- **Total time** — wall-clock from dispatch to completed. Capture client-side in
  `useRun` (`t0` at execute → on `completed`), and/or from the run's GH `created_at`→
  `updated_at`. Render on the Result card (e.g. "Test 0.9s · Total 68s").

### P4 — Self-heal quality + cost

- **Ground locators in reality:** the heal prompt already gets a snapshot
  (`fetch_failure_context` → `snapshot`) — require the model to pick locators **only
  from elements/roles/text present in that snapshot**, and prefer role-based
  (`getByRole`) or test-id locators over exact `getByPlaceholder`/text strings that are
  easy to hallucinate. Add an explicit rule: "never invent attribute text; copy it
  verbatim from the snapshot or use a role+name that appears there."
- **Validate before re-run:** optionally check the proposed locators' strings against
  the snapshot; if a locator's literal isn't found in the snapshot, flag low confidence.
- **Don't silently spend a 2nd cold cycle:** show the diff + a confidence signal and let
  the user confirm re-run (or auto-run only on high confidence). Cheaper once P1 lands.
- **Reuse warm env** for the re-run if D is ever adopted.

### P5 — Progress & timeout honesty

- Surface the GitHub phase distinctly (pending/dispatched vs queued vs in_progress) with
  an elapsed timer, and expose **Open on GitHub** *during* the run (we have `run_url`).
- On client timeout, say "still running on GitHub — [open] / [stop]" instead of a bare
  "Timed out", and offer Stop (P2).
- Consider a small concurrency/queue note when a prior run is still active.

---

## 5. Phased rollout

- **P0 — SHIPPED 2026-09-30:** container workflow (`ml-qa-runner` 5ee9264, modest
  ~68→~50-56s), execution-time display (ml-portfolio 3bb1be3), and P2 cancel+Stop
  (ML-Unified 970d8f3 + ml-portfolio 3bb1be3). All verified live; no regression
  (sample test still passes, Stop button appears, `test/total` shown).
- **P4 self-heal grounding — SHIPPED 2026-09-30** (ML-Unified `21fc8c6`, HF-uploaded):
  HEAL_SYSTEM now requires every locator string be copied verbatim from the ARIA snapshot
  and prefers `getByRole('searchbox'/'textbox',{name})` over guessed placeholders. Verified
  end-to-end: the §2 failing case heals to a grounded `getByRole('searchbox',…)` and passes.
- **P4b confirm-before-rerun — SHIPPED 2026-10-01** (ml-portfolio `2911264`): heal no longer
  auto-fires a 2nd ~50s CI cycle — it stages the fix into the editor and shows the diff with
  **Re-run healed test** / **Discard**. Verified live on the deployed bundle: Suggest a fix →
  grounded heal, **no auto-run**, Re-run/Discard gate; Discard reverts the code, 0 CI spent.
- **P5 progress/timeout polish — SHIPPED 2026-09-30** (ml-portfolio `acf5d04`): live elapsed
  timer, phase caption, "~40–60s first-run setup" note, Open-on-GitHub during the run, honest
  timeout message.
- **NEXT (real speed lever): D — warm / self-hosted runner.** Evidence shows GitHub-
  hosted runs are download-bound (~50s floor); only a runner that persists the image +
  browsers gets to seconds. This is the only open item for speed — **recommended skip**
  (infra + security cost for a free public portfolio).

## 6. Risks & mitigations

- **Container/PW version drift** — pin the image tag to the exact `@playwright/test`
  version used by tests; bump both together (single constant in `config.py` + workflow).
- **Cancel token scope / rate limits** — reuse `GH_QA_TOKEN`; handle 202 vs 409 (already
  completed) gracefully.
- **Heal over-restriction** — grounding rules could make heal decline more; keep it
  advisory (still show the best attempt), don't hard-fail.
- **Deploy discipline** — runner-repo change is separate from the Space; the backend
  cancel endpoint follows the mandatory HF-upload rule. Batch, deploy once, verify the
  new workflow serves before claiming speed-up (measure a real run).

## 7. Verification plan

- **P1:** time a trivial run before/after; expect the install steps gone from the GH log
  and wall-clock ~10–20s. Confirm a real test still passes (my sample: 1 passed).
- **P2:** start a run, click Stop, confirm the GH run shows *cancelled* (not just the UI
  stopping) and polling ends.
- **P3:** run and read the displayed test vs total time against the GH run timing.
- **P4:** re-run the exact failing case from §2 — the healed placeholder must now match
  the real `Search 58 tools — try …` (or use a role locator) and pass.
- **Regression checklist (run after EVERY phase, per the §-header constraint):** a
  passing test still passes and a failing test still fails with the right summary;
  screenshot, **video**, and **trace** still download; a flakiness run (e.g. 5×) still
  reports pass-rate; self-heal still produces a diff and re-runs; Save / Load / Re-run
  and recent-runs history still work; **Author → Run** handoff still carries code; the
  other stages (Discover/Heal/Visual) that share the runner still function.

## 8. References

- Playwright on GitHub Actions, fast setup — https://endform.dev/blog/playwright-github-actions
- Official Playwright Docker image — https://testdino.com/blog/playwright-in-docker
- Cache Playwright browsers in Actions — https://dev.to/ayomiku222/how-to-cache-playwright-browser-on-github-actions-51o6
- Speed up Playwright (Argos) — https://argos-ci.com/blog/speed-up-playwright
- Cancel a workflow run (REST) — https://docs.github.com/en/rest/actions/workflow-runs
- Force-cancel workflows — https://github.blog/changelog/2023-09-21-github-actions-force-cancel-workflows/
