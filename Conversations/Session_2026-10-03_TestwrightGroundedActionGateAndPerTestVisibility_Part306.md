# Part 306 — Testwright: the grounded-action gate, per-test visibility, and "click only what's clickable"

Continues [Part 305](Session_2026-10-02_TestwrightGroundingGenerationInRealPagesAndDashboardPolish_Part305.md).
2026-10-03. Heading-grounding (Part 305) made navigation/heading assertions real, but a
real run still produced 2 reds — both the **same deeper class**: the generator grounds a
real *string* but invents its *role* (clicks page text as if it were a button; guesses a
dynamic placeholder). This session adds the industry fix: **feed only interactive elements
and deterministically refuse to interact with anything else** — plus per-test visibility so
"why did it fail" is answerable at a glance.

Through-line: **ground what you can see; don't trust the AI to pick click targets —
verify every action against the real interactive elements, deterministically.**

---

## Arc 0 — the dashboard was misleading (test-case vs run pass rate)
The dashboard headlined a **7%** pass rate: it counted whole RUNS (a run is "failed" if ANY
test fails), so 13/14 runs failed even though 28/50 individual tests passed. Fixed
(ml-portfolio `ec8db2b`): the gauge now shows the **test-case** pass rate (56%), the old
per-run metric is relabeled "all-green run rate," and the KPI tiles separate runs from tests.

## Arc 1 — repo CI was red (unrelated to the app)
Two of the repo's own CI checks failed after a push:
- **handbook** stale — `public/handbook.md` out of date vs its generator. Fix: re-ran
  `scripts/build-handbook.py`, committed the regenerated file.
- **secret-scan-history** — gitleaks on all 1189 commits found 3 leaks. Investigated with a
  **redacted** scan (no secret values printed): all 3 are secret-SHAPED **demo data** inside
  the security tools' own UIs (Secret Scanner sample log, JWT Analyzer sample tokens). Not
  live credentials. Allowlisted by fingerprint in `.gitleaksignore` → green. (ml-portfolio
  `4fd2200`; verified all 7 jobs pass.)

## Arc 2 — the two real test failures (root cause)
A live run: 8/10 passed, 2 failed —
1. `getByPlaceholder('Search Security & Trust tools')` → the real placeholder is **dynamic**:
   `Search 26 Security & Trust tools…` (count + ellipsis). The guess isn't even a substring →
   30s timeout.
2. `getByRole('button',{name:'Titanic Survival'}) // Placeholder selector` on `/ml` → `/ml`
   is a **landing page**; "Titanic Survival" is the title of an example table and "Fill the
   form" is a how-it-works step — both are **text**, not controls. The model grounded a real
   string but invented its role (clicked text as a button), and even wrote a hedge comment.

The unifying cause: heading-grounding covered *assertions*, not *interactions*. Generation had
no grounding for **interactive controls**, so any fill/click/select still guessed.

## Arc 3 — research: how the industry handles it
Web-searched (the user insisted, rightly): the standard fix is exactly their intuition —
**only act on elements that are actually interactive**, enforced deterministically:
- Target by **accessibility role + name** (Octomind), not text/CSS — ~10× more stable.
- Feed the model **only interactive elements** (Checkly), never plain text as a click target.
- Playwright-MCP hands the model real elements by **ref** so it *cannot* reference a non-element.
- Validate **interactability**, not just visibility.

## Arc 4 — THE fix: three layers
Shipped as ML-Unified `d6030c0` (controls + per-test + anti-hedge), `310254e` (the gate +
proposal grounding), `f45e53d` (aria-hidden in the collector); ml-portfolio `876d0ac`
(per-test UI). All HF-uploaded.

- **Per-test visibility.** `run_report.py` (NEW — split out of `github_runner.py` so both stay
  <350 lines) parses each spec's title/status/duration/error from `results.json` →
  `RunStatus.tests`. The Run view shows a **"Tests (N) — X passed · Y failed"** list with each
  failure's own error inline. (The old UI only showed the first error and couldn't name which
  test failed — the gap that sent the user hunting through GitHub/traces.)
- **Layer 1 — capture controls.** One shared `grabControls()` in `discover.py` emits each
  page's REAL interactive elements as `[role] name="..."` / `[role] placeholder="..."`, for the
  start page (`===CONTROLS===`) and every deep page. Uses the **accessible name** (excludes
  aria-hidden) — a first pass used raw `textContent` and captured a card link's run-on of nested
  tool names, which the model then asserted; fixed in `f45e53d`.
- **Layer 2 — the grounded-action gate.** `action_gate.py` (NEW) `drop_ungrounded_actions`:
  parse the interactive allow-list from the context, then drop any `test()` block whose
  **interaction** (`click/fill/selectOption/check/press/type/...`) targets an element not in it
  — including variable-based locators (`const sel = getByRole('combobox',{name:'Select Model'});
  sel.selectOption(...)`). **Assertions are never touched.** Runs last in author's pipeline
  (after href/exact rewrites); if every test is dropped, the model cascade tries again.
- **Anti-hedge guard.** Author rejects any output containing `// Placeholder` / `actual
  selector` / `in a real test you would need` and tries the next model.
- **Layer 3 — ground proposals.** DISCOVER_SYSTEM: never propose interacting with something
  that's only text; for a page with no form, propose its real CTAs ("Open the platform")
  instead of "fill the form."

## Live proof (2026-10-03)
Fresh Discover (deep) → generate → run against the real site, targeting the two failing
scenarios:
- Discover captured clean controls incl. `Search 26 Security & Trust tools…`.
- Generation: no hedge; search test used the real placeholder + a **clean** heading assertion.
- The `/ml` "select a model" interaction was **DROPPED by the gate** (not shipped as a red).
- Run: **1/1 passed, 0 unexpected.**

The gate was also unit-verified on the exact failing shapes: search test kept, Titanic-button
and Select-Model-combobox tests dropped, grounded nav kept, the orphan assertion gone.

## Key decisions
- **Don't trust the AI to pick click targets.** Deterministically verify every interaction
  against the captured interactive allow-list; drop the whole test if it can't be grounded.
- **Gate interactions only, never assertions.** `expect(heading).toBeVisible()` on body text is
  legitimate; clicking that same text is not.
- **Capture the accessible name, not textContent** (exclude aria-hidden) everywhere a name is
  grounded — link map AND the controls collector.
- **Surface per-test results** — a run must name which tests failed and why, in-product.

## Lessons
- **Each AI run surfaces the next class.** Heading-grounding fixed assertions; the next red was
  interactions. The durable answer isn't "one more prompt rule" — it's a deterministic gate +
  the heal/auto-fix loop as the safety net. Don't promise "last class ever."
- **A fix can introduce the next bug:** the new controls collector re-introduced the run-on
  card-name problem (raw textContent); caught it in the live run, fixed at the source.
  [[feedback_status_claims_need_evidence]]
- **When the user says search online, search online** — the research confirmed their own plain
  logic ("click only if it's clickable") was the industry answer. [[feedback_debug_first]]

## Open / deferred
- Testing the **live predictor** (pick model → fill schema-driven form) needs the generator to
  follow **"Open the platform ↗"** into the separate ML Unified app — a multi-step/cross-app
  flow, not required to stop this bug.
- R7 historical dashboard, learn-from-edits, R5 auth (unchanged).

## Commits
| Repo | Commits |
|---|---|
| ml-portfolio | `ec8db2b` (dashboard test-case rate) · `4fd2200` (CI: handbook + .gitleaksignore) · `876d0ac` (per-test UI) |
| ML-Unified (backend, HF) | `d6030c0` (per-test parse + controls + anti-hedge) · `310254e` (grounded-action gate + proposal grounding) · `f45e53d` (grabControls accessible name) |

Related: [[project_testwright_run_perf]], [[project_testwright_qa_platform]],
[[feedback_debug_first]], [[feedback_status_claims_need_evidence]], [[feedback_secret_shaped_test_data]].
