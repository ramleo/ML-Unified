# Part 333 — TestOps: the registry, the first runnable lane, and a measured pilot (2026-10-25)

Continues Part 332, whose headline numbers were **wrong** (corrected in `2c8ae78`).
This session replaced guesses with measurements, shipped an owner-only page to hold
them, and ran the browser lane end to end for the first time.

Through-line: **every number here was measured, and three of them contradicted what
I had confidently told the user the day before.**

---

## 1. Why Part 332 was wrong

The Part 332 trial used instructions I hand-wrote, with the URL already in them. It
proved the Testwright *pipeline* worked and said nothing about whether the *test
cases* were usable. The rule that would have caught this —
"plant a known ground truth, then believe the disagreement" — was already in memory.

Parsing the real files:

- **1,795 cases**, not 1,545. A parser requiring a bare `### TC-id` silently dropped 8
  headings carrying suffixes like `(Fixed)`.
- Of 817 browser cases, **26 name a target page and need no setup**. 450 name no URL
  at all. The "~670 ready to automate" figure was fantasy.

---

## 2. The classifier is 67% — and that is the honest number

Lane counts kept moving because I kept adjusting the regex. So: freeze one rule set,
hand-label a stratified random sample, and **measure**.

| | tuned sample | held-out | honest |
|---|---|---|---|
| v1 | — | — | **54%** |
| v2 | 91% | **67%** | **67%** |

The 91% is what I would have reported had I scored on the sample I tuned against.
That gap is the whole lesson. 77 hand-labelled cases now exist as a reusable benchmark.

Regex over prose plateaus near 70%; further tuning chases the sample. This is why the
schema carries `lane_origin` and `lane_locked`, and why `testops_sync.py` splits into
two batches — **a human correction must survive the next sync**.

---

## 3. TestOps — the owner-only page

`/testops`, gated with `isOwnerEmail` exactly like `/eval`.

- **`testops_cases`** — one row per documented case.
- **`testops_events`** — ONE extensible log, deliberately not four rigid tables.
  `kind` names the record type, a JSONB `payload` carries the rest, so a new thing to
  record is an insert, not a migration. No CHECK on `kind`, on purpose. In use:
  `run_verdict`, `finding`, `cost`, `decision`, `sync`, `quarantine`.
- RLS on with no policies, matching `security_log`; the owner gate lives in the route.

The page leads with **needs attention** (worst first, clickable), then coverage, lane
breakdowns, a drillable trend, activity and the full registry. Charts are clickable
filters; filters live in the URL so a view is a link.

**Three bugs found in my own work while building it:**

- The registry showed "1,000 cases" of 1,795. **PostgREST caps responses at
  `db-max-rows` and truncates silently** — `.limit(5000)` returned 1,000 and no error.
- The detail drawer was a **keyboard trap**: no Escape, no dialog semantics, no focus
  management.
- `CaseTable` reached 355 lines, over the 350 modularize trigger, before I noticed.

---

## 4. The repo-assertion lane — first cases that actually run

34 cases assert something about the repository, so they need no browser, no network
and no LLM. **27 pass.** Committed deliberately with reds visible rather than `xfail`.

Triaging them produced the session's recurring finding: **a red has three causes.**

- `_generate.py` at 366 lines — a **second, stricter threshold** (350) fighting the
  project's real limit (400). Removed; one limit now.
- The unsplit `AKIA…EXAMPLE` demo literal — a genuine rule violation, harmless in
  practice (AWS's published example key).
- `TC-P11-096` — **stale case**: it demands `SqlChart.tsx` be deleted, but the chart
  was rebuilt client-side afterwards and is live.
- `services/ml-eda` is **not gone** — folded into ml-api in `a0108ec`. I had written a
  skip reason claiming otherwise.

Ten skip stubs for the predecessor AutoML-generator project were deleted: that code
was never in this monorepo, so a stub for it is code that can never run. "This is
dead" belongs in the registry, not a test file. Same for a dead-code note I had
parked as a skip — it is a `finding` event now. **A test file is not a notepad.**

---

## 5. The browser pilot — two arms, and the resolver dies

20 real cases, end to end: author from the case text → run on the GitHub runner →
heal ≤3 → record the verdict. **16/20 usable** (7 PASS, 9 HEALED).

Built with a control so the URL resolver was measured rather than assumed:

| arm | input | usable |
|---|---|---|
| A | resolved URL supplied | 10/13 (77%) |
| B | **no URL**, site map only | **6/7 (86%)** |

**Arm B did better. The resolver is dropped.** Worse than useless: it manufactured a
false bug report, sending `TC-P13-037` to `/tools/ml-pipeline` because "ml-pipeline"
appears in the case's expected-result text, when the case is about `/`.

Both escalations were checked in a real browser and **neither was a site bug** —
both were stale case text. The heal gate refusing assertion failures behaved exactly
as designed: it escalated rather than healing a real mismatch into a fake pass.

---

## 6. The cost model, corrected twice

I told the user ~7-8 hours, then measured 2.9 min/case and said **~40 hours**. The
user pushed back: 40 hours for 817 tests means something is wrong.

They were right, and the fault was architectural, not the model's:

**My pilot dispatched one GitHub Actions run per test** — paying 2-3 minutes of
queue, checkout and browser install for a test that runs in seconds.

`MAX_RUN_CODE = 60000`, a spec is 1-2 KB, and the runner already returns per-test
results. **~40 tests fit in one dispatch; merged suites are first-class.**

| | my pilot | correct |
|---|---|---|
| Dispatches for 817 | 817 | **21** |
| Validation wall-clock | ~40 h | **~5 min**, run concurrently |
| Authoring | 817 LLM calls | unavoidable — the only per-test cost |

| | one-time build | each later run |
|---|---|---|
| Free (Groq, 8,000 TPM) | ~10 h unattended | **minutes** |
| Paid (Gemini) | ~80 min, ~$9 | **minutes** |

Industry baseline agrees a suite run should be minutes, not hours.

---

## Lessons

- **A pipeline trial must use real input from the real source.** Curated inputs only
  prove the plumbing is connected. This cost a day.
- **Score on held-out data or the number is theatre.** 91% on the tuned sample, 67%
  held out, same classifier.
- **Measure the alternative, don't assume it.** A control arm killed a whole planned
  phase in one run — and showed the feature was actively harmful.
- **Architecture beats provider.** "40 hours" was one dispatch per test, not a slow
  model. Check the system's own limits before quoting a cost.
- **A red test still has three causes** — site bug, test written wrong, or the case
  itself wrong. Every red needs a human glance. Both pilot escalations were stale cases.
- **A test file is not a notepad.** Skip stubs for dead subjects and parked findings
  are code that can never run; they belong in the registry.
- **Silent truncation is the dangerous kind.** PostgREST returned 1,000 of 1,795 rows
  with no error.
- **Don't use `git checkout` to undo a syntax error** — it wiped a test I had just
  written. Fix the line.

## State after this session

- `/testops` live: 1,795 cases, coverage 2.4% (43 automated), 27 repo + 16 browser.
- Commits: `2c8ae78` `6eac9eb` `c736c9a` `3c35a4f` `244762e` `1e47bc3` `31f5b18`
  `222b16d` `2a8676a` `5532141` `bec874b` `1165390` `d92755c` `53d67d4`.
- **PRD updated — and it is gitignored, so this line is the only record of it.**
  `docs/prd/02-cross-cutting-systems.md` gained a **TestOps** section (placed with
  the cross-cutting systems, not the Q-roadmap: it is internal quality
  infrastructure). It carries the reasoning that would otherwise be lost — why
  `lane_locked` exists (the 67% classifier), why `testops_events` is one table
  rather than four, why RLS has no policies, why a skipped test does not count as
  coverage, and the corrected cost model. **No handbook change**: the handbook is
  the user-facing tool catalogue and no owner-only page appears in it.
- Open: batch the pilot (~40 per dispatch) and build the browser lane; the API lane
  (566 cases) is a separate pytest effort; 262 cases remain unclassified.
