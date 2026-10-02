# Part 304 — Testwright Phase 2: roadmap build-out, the generate-blind root cause, the verify-repair loop, and a live animated dashboard

Continues [Part 303](Session_2026-10-01_TestwrightDiscoverGroundingLocatorRobustnessAndRoundTripUX_Part303.md).
2026-10-02. A long, two-arc session. Arc 1: a research-backed **Phase 2 roadmap**
(R1–R10) built out stage by stage (R1/R2/R4/R6 shipped, R3 decided, R5 deferred),
then **R7 run reports** (Excel/PDF export, a local dashboard, a live animated redesign).
Arc 2, driven by the user running the real tool: an 8-point UX pass, then a deep,
evidence-led hunt for *why generated tests keep failing* that ended in the real fix —
a **verify-repair loop** (run → heal → re-run, grounded in live execution), with heal
taught to remove invented assertions. Browser-verified end to end.

The through-line: **ground truth by execution, not by a static snapshot** — and
**don't ship the fix you proposed when the evidence disproves it.**

---

## Arc 1 — Phase 2 roadmap (plan doc §9, `TESTWRIGHT_IMPROVEMENT_PLAN.md`)

Research pass (Playwright's own Planner/Generator/Healer agents; Octomind/Mabl/QA.tech/
Checkly; the false-positive/abandonment literature) → a prioritized R1–R10 roadmap.
Guiding principle, evidence-backed: **AI self-heal correlates with ~23% more false
positives and ~41% first-year tool abandonment — so transparency/trust beats autonomy.**

- **R1 — flakiness-proof generation** (`af5e1cb`): deterministic strip of
  `page.waitForTimeout(...)` from every generated/healed test + prompt rules requiring
  web-first assertions. Verified live.
- **R2 — cap flaky-repeat at 3×** (`ec79ebd`/`8258394`): menu + `MAX_RUN_REPEATS`.
  Verified (runs>3 → 422).
- **R3 — deprioritize Visual** — decision only (weakest paradigm).
- **R4 — self-heal beyond locators** (`127a1fc`/`8f5850e`): heal broadened to
  locator+timing, and **refuses to rewrite a failing assertion** (`classify_failure`
  detects a value mismatch and returns an honest explanation). e2e-verified live.
- **R6 — Discover one-hop deep** (`6c76886`/`9784203`): opt-in; the same explore run
  visits ≤3 same-origin links and appends their snapshots. No extra CI. e2e-verified
  (/handbook, /docs, /about).
- **R5 — authenticated testing** — **deferred**: no logged-in app to test yet (plan §9a
  holds the credential-model design A/B/C).

## Arc 1 — R7 run reports (`QA_SHAREABLE_REPORTS_PLAN.md`)
Key architectural finding: durable writes go through **Next.js API routes (Vercel)**
holding the Supabase key, not the HF Space — so export + local dashboard are
**frontend-only, no backend/HF**.
- **Export to Excel/PDF** (`98c71fc`): ExcelJS + jsPDF (MIT), dynamically imported.
  (PDF overflow bug later fixed with `overflow:'linebreak'`.)
- **Local dashboard** (`8b7be70`): `/qa/dashboard` aggregates browser history — tiles,
  outcome strip, top-failing bars, flaky table; dataviz-compliant.
- **Live animated redesign** (`b128f6f`): pass-rate **ring** (SVG arc + count-up),
  cumulative pass-rate **trend** (area+line drawn-in, hover dots), count-up tiles,
  grow-in bars, staggered strip; **live** auto-refresh (storage event + focus + 5s
  interval); reduced-motion aware. Research: animations subtle + purposeful.
  Screenshot-verified.
- Share links + historical dashboard (Supabase) still scoped, not built.

## Arc 2 — the 8-point UX pass (one batch)
From the user's screenshots: PDF overflow fix; **run results persist across navigation**
(`useRun.hydrate` + sessionStorage, screenshot dropped for quota); dashboard counts
**test cases** not just runs (history stores per-test counts); **Select all** on
proposals; Discover **progress stepper + timer**; Generate **"Drafting N/M"** progress.
ml-portfolio `e6140a1`. Plus runner **parallelization** (below).

---

## Arc 2 — the hard part: WHY generated tests keep failing

The user kept hitting failing generated tests and (rightly) rejected "accept them."
Each e2e surfaced a new failure *class*; fixing one revealed the next. Evidence-led:

1. **Speed (244s → ~94s):** merged suites ran ~linearly under `workers:1`. Set
   `fullyParallel:true` + `workers:3` in `ml-qa-runner/qa-run.yml` (`d0727008`, via
   `gh api` — the GitHub MCP creds were stale; `gh` CLI worked). 2-vCPU sweet spot.

2. **"Security & Trust" locator not found — the big misdiagnosis chain:**
   - First guess: giant accessible name → shortened to `/^prefix/i.first()` (`48413e4`).
     Didn't fix it.
   - Second guess: wrong role. **Direct DOM evidence disproved it** — the element IS a
     `link` with that name. *Did not build role-grounding* (the fix I'd proposed) once
     evidence killed it.
   - **Real cause (live DOM):** the homepage category card is one big `<a>` whose
     accessible name is a concatenation of all 25 nested tool names **and changes with
     CSS reveal state** — so ANY name-based locator is non-deterministic. Fix = locate
     by the **stable href** (`/tools/security-trust`), which Discover already captures.
   - **href grounding** (`d038de6`): `_href_link_locators` rewrites
     `getByRole('link',{name})` → `locator('a[href="…"]')` from the link map; explore
     captures a **clean** label (aria-label → inner heading → trimmed text).
   - **Nuance 1 (shared-label hrefs):** "Tools" and "The Toolkit" both → `/#capabilities`.
     An href shared by >1 distinct label is not unique → **keep the name locator**
     (`b87efef`).
   - **Nuance 2 (nav+footer dupes):** the SAME "Platforms" link appears twice with the
     same href → `.first()` on href locators (`cc75539`).

3. **The real remaining cause — invented content assertions.** With locators clean, the
   first failure became `getByText('Client 01')` → not found. The generator **invents
   assertions** for content that isn't on the page. This is a *different* class from
   locators, and it's what kept the count ~stable while we peeled locators away.

## Arc 2 — the actual solution: the verify-repair loop
Root cause of everything: **generation is BLIND** — it writes from a one-shot ARIA
snapshot, then runs against the live page; the two diverge. No prompt patch fixes a
blind guesser. The fix is to **close the loop**: run the draft, see what really fails,
repair, re-run — ground truth by execution.

We already had the pieces (generate, run, heal); what was missing was orchestration.

- **Heal taught to remove invented assertions** (`ddb3239`): a *bounded* new rule — a
  presence assertion (`toBeVisible` on `getByText`/`getByRole` name) that fails
  **not-found AND whose target is absent from the snapshot** is an invented check →
  **remove that single line**. NEVER touches a value mismatch (R4's principle holds).
  Verified live in isolation: `getByText('ZZQQ…')` removed, `toHaveTitle` kept.
- **"Auto-fix & re-run" loop** (ml-portfolio `5393fcd`): one button chains
  run → heal → re-run, ≤2 passes, until pass or heal can't fix it. Reuses
  `onHeal`/`onConfirmHeal`; extracted to `useAutoFix` to keep RunRunner < 350 lines.
- **Browser-verified end to end:** seeded a test with an invented assertion → **Failed**
  → clicked Auto-fix → heal removed it (diff shown, `cohere`) → re-ran → **Passed**.

The honest boundary stays: the loop fixes *mechanics* (locators, timing) and removes
*invented* checks; a **real value mismatch still fails** — a genuine bug it won't hide.

## Key decisions
- **Ground truth by execution, not snapshot** — the verify-repair loop is the real fix;
  prompt rules were symptom patches.
- **Locate unstable-name links by href**, not name; keep the name only when the href is
  ambiguous (shared label). `.first()` for nav+footer dupes.
- **Heal may remove an invented not-found assertion, never a value mismatch** — the two
  are distinguished by "target absent from snapshot" vs "Expected/Received differ."
- **Export + local dashboard are frontend-only** (Supabase via Next.js routes, not the
  Space). Share + historical dashboard deferred.
- **R5 auth deferred** — no authed app to test; building it now would serve no user.

## Lessons
- **Don't build the fix you proposed when evidence disproves it.** I was about to build
  role-grounding; one DOM read showed the role was already correct. Killed it.
  [[feedback_debug_first]] [[feedback_verify_before_recommending]]
- **An unstable *accessible name* is a real failure mode** — a compound card `<a>`'s
  name includes nested text and shifts with CSS state; a snapshot name ≠ runtime name.
  Use a stable attribute (href/testid).
- **AI-generated tests are variable** — each generation picks different proposals, so
  each e2e shows a different failure class. Fix *classes*, not instances; verify on the
  deployed Space, stage==RUNNING, every time.
- **The count stays flat when the cause moves** — fixing locators didn't drop failures
  because the same tests also had invented assertions underneath. Peel every layer.

## Commits
| Repo | Commits |
|---|---|
| ml-portfolio | `e6140a1` (UX pass) · `98c71fc` (export) · `8b7be70` (local dashboard) · `b128f6f` (animated dashboard) · `5393fcd` (auto-fix loop) |
| ML-Unified (backend, HF) | `af5e1cb` (R1) · `8258394` (R2) · `127a1fc` (R4) · `6c76886` (R6) · `48413e4` (name shorten) · `d038de6` (href) · `b87efef` (href unique) · `cc75539` (href .first) · `ddb3239` (heal removes invented) |
| ml-qa-runner (workflow) | `d0727008` (fullyParallel + workers:3) |
| ML-Unified (docs) | `c53c5fc`/`9aa8e1d` (roadmap) · `3741e47`/`e2dfc7c`/`c864181`/`a2e2678` (R7 plan + status) |

## State after this session
- **Generation** now: no hard waits, web-first asserts, short/href-grounded link
  locators, deep-discover option; **self-heal fixes locators+timing, removes invented
  assertions, refuses value mismatches.**
- **Run** has a one-click **verify-repair loop** (Auto-fix & re-run) + export (Excel/PDF)
  + persisted results across navigation.
- **Dashboard** is live + animated (ring, trend, count-ups, auto-refresh).
- **Speed:** parallelized (244s → ~94s on a 13-test suite).
- Open/deferred: R5 auth, R7 share links + historical dashboard (Supabase layer),
  "learn from my edits". Related: [[project_testwright_qa_platform]],
  [[project_testwright_run_perf]].
</content>
