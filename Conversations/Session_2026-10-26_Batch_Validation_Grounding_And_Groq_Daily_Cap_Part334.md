# Part 334 — Batch validation, the 24% first-author yield, grounding, and the Groq daily cap (2026-10-26)

Continues Part 333. That part ended on one open task: *batch the pilot, prove the
21-dispatch number, build the browser lane.* This session did the first two, built
most of the third, and hit a limit that changes the provider decision.

Through-line: **every wrong number today was a limit I could have read first.**

---

## 1. The batch run — the "40 hours" claim is dead

`scripts/testops_batch_run.py` merges finished specs and dispatches them together
instead of one GitHub Actions run per test.

| | pilot (Part 333) | batch |
|---|---|---|
| Dispatches for 16 specs | 16 | **1** |
| Wall-clock | 58.5 min | **1.2 min** |
| Actual test time, all 16 | — | 37.6 s |
| Dispatches for 817 | 817 | **21** |

16 specs merged = 17,170 chars, 29% of `MAX_RUN_CODE` (60,000) → ~40 per dispatch.
All 16 passed again a day later; nine of them were pilot *heals*, so this was an
independent check that those heals were real fixes.

Mechanics that mattered:

- One `import` kept; each file's body block-scoped `{ }` so six colliding
  `const BASE_URL` declarations stop fighting.
- Every `test()` title is tagged `[TC-ID]` — the JSON report returns the *test*
  title, not the describe title, so the id is the only link back to a row.
- Bug found by the 54-spec run: the tagging regex matched `'` and `"` but not
  backticks, so a spec writing `` test(`... ${path}`) `` produced an unmappable
  result (TC-P9-100 → `NOT_IN_REPORT`). Fixed.
- Multi-chunk path (54 specs → 40 + 14, concurrent) works: **3.9 min wall-clock.**

## 2. The 40-case authoring run — measured, and humbling

`scripts/testops_author.py`: one LLM call per case, **no target URL** (the resolver
is dead — Part 333), seeded random sample across 20 TC files (sorting by id had
picked 40 consecutive `TC-BUG-*` cases — a biased sample, caught before running).

- **38/40 authored, 55 s per case** (36.5 min). Two empty (rate limit).
- Validated: **25/54 pass.** 16 are the old specs; **new specs passed 9/38 = 24%.**

The pilot's "80% usable" was *with heal* (9 of 16 were HEALED). First-author only,
the pilot was 7/20 = 35%. The authoring lane was built without a heal step, so the
two numbers were never comparable. Heal is most of the yield, not a refinement.

Failure shape: 22 of 29 reds were `toBeVisible() failed` after ~18 s — a locator for
an element that does not exist. Also: TC-P15-006 hallucinated
`toHaveCountGreaterThan` (not a Playwright matcher; passes the syntax guard).

**Side result:** TC-P13-037, the case the URL resolver had manufactured a false bug
for, **passes** when re-authored with no URL. Direct confirmation the resolver was
the bug, not the case.

## 3. Heal cannot work inside a merged suite (not yet fixed)

`github_runner.fetch_failure_context()` returns `first_error()` and the first
`error-context.md` in the artifact zip — one failure per run. A merged suite with 29
reds can heal exactly one. Fix is small: select context by test title, add the title
to `HealRequest`. It is a backend change to `routers/qa/` → needs an HF Space
upload. **Not done.**

## 4. The real cause: authoring guessed, and Testwright already had the cure

The user pressed on "why does the AI guess — can't a tool do this?" Checking
`routers/qa/discover.py`: **Testwright already has a Discover stage** that dumps the
page's real controls, and `locators.py` rewrites code against it. I didn't use it —
I fed the model a hand-typed site map. Also: the app has **1 `data-testid` across
633 components**, so there is nothing stable to anchor to.

Why not call Discover as-is: its `/status` endpoint **throws the snapshot away if
its own LLM proposal step fails**, and that step runs on exhausted free quotas.

So: `scripts/testops_snapshot.py` captures locally with Playwright — no LLM, no
rate limit, no CI cost. Same `[role] name="..."` format `locators.py` grounds on.

- Crawling alone reached 31 pages: tool cards are `<button>`, not `<a href>`.
- Routes are therefore read from `src/app` (93 static routes) + crawl.
- **103 pages, 1,519 controls, 5.1 min, 0 `data-testid`.**
- Cached at `tests/.testops/snapshots.json` (re-run when the UI changes).

## 5. The page choice was wrong too, not just the selectors

17 of the 29 reds had been sent to the portfolio **root**. But TC-P3-112 is the Drift
tool, TC-P6-022 AutoML, TC-P7-041 Optuna, TC-DOC-002/TC-P3-020 the ML Unified Space.
The element genuinely wasn't on the page.

`scripts/testops_reauthor.py` shortlists 3-4 candidate pages by scoring the case
against **captured page content** and lets the model choose. This is *not* the dead
resolver: that one regexed prose for a slug and committed to one URL.

Scorer bug found on the way: `/tools/text-to-sql` outranked `/tools/optuna` for the
Optuna case because the case said "description **text**". Fixed by weighting each
path word by `1/(pages that contain it)` — "optuna" names one page, "text" names
three. **Stopped tuning there on purpose**: over-tuning a scorer against cases I'm
looking at is the 91%-vs-67% trap from Part 333.

## 6. The wall: Groq free tier has a daily cap

The re-author run completed **1 of 29** in 25 minutes. Space logs (read directly):

> `Rate limit reached for model openai/gpt-oss-120b ... on tokens per day (TPD):
> Limit 200000, Used 199889, Requested 5265`

Part 333 only knew the 8,000 TPM limit. **The free tier is also capped at 200,000
tokens/day.** The job was retrying 3× per case against a wall; killed it.

Measured from the error message (the first real figure): an author call costs
**~5,300 tokens**.

| | free | paid (Developer tier) |
|---|---|---|
| Limit | 200K tokens/day | 250K/min, no daily cap |
| Author calls | **~37/day** | ~47/min |
| 817 cases | **~22 days** | **~18 min** |

Cost, recomputed from third-party price trackers (Groq's own page would not load):
$0.15/M in + $0.60/M out → 817 × 5,300 ≈ 4.3M in ($0.65) + ~0.7M out ($0.39) ≈
**$1–2 with heal rounds.** *Caveats: prices unverified against Groq; output-token
count is my estimate.* Part 333's "$9" and "~10 h free" were both wrong; the
Part 333 "12.5 h" figure from earlier today was also wrong.

`llm_calls` records no token counts for qa-author (`input_tokens`/`output_tokens`
are empty) — which is why this had to be read from the 429 text.

## State at end of session

- **Committed:** `bea297b` (batch runner). **Uncommitted:** `testops_author.py`,
  `testops_snapshot.py`, `testops_reauthor.py`, a `testops_batch_run.py` edit
  (backtick regex + chunking), 38 new specs, `tests/.testops/`.
- Registry: 1,795 cases · **52 passing (27 repo + 25 browser)** · 28 STILL_RED ·
  1,709 never run. Honest denominator is ~1,417 automatable (excludes 102 LESSON +
  14 DEAD) → **3.7%**, not the 2.9% quoted against all 1,795.
- Specs backed up before re-author at scratchpad `suite_before_reauthor/`.
- **Re-author never completed** — the grounding experiment (same 29 cases, same
  model, one variable changed) is still unrun.

## Decision waiting on the user

Upgrade Groq to Developer tier (~$1–2, ~18 min for 817), wait out the reset at ~37
cases/day, or use another paid provider. Not changed unilaterally.

## Lessons

- **Read the governing limit before quoting a number.** One call would have shown
  the daily cap this morning. Four wrong estimates today, all from this.
- **A yield measured on a different pipeline isn't comparable.** 80% (with heal) vs
  24% (without) looked like a regression and was a missing step.
- **Don't retry into a wall.** Two failures = stop and read the logs; the job
  retried 3× per case for 25 minutes before I looked.
- **Capture ground truth locally, don't route it through the LLM-gated endpoint.**
  The Discover snapshot was blocked by a step that had nothing to do with it.
- **A sampler that sorts is biased.** 40 consecutive ids = one feature, one author.
- **Don't tune a scorer against the cases you're reading** — stop when the cases
  you care about look right, not when they all do.
- **Missing observability hides cost.** No token counts in `llm_calls` meant the
  per-call cost was invisible until a 429 spelled it out.

## Open

1. Groq decision (above).
2. Heal-by-test-title backend change + HF upload.
3. Run the re-author, validate 54, record before/after.
4. Record token counts in `llm_calls` for qa-author.
5. API lane (566), 262 unclassified — unchanged.
