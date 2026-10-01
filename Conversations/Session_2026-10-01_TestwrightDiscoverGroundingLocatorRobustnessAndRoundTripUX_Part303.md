# Part 303 — Testwright: Discover grounding, locator robustness, honest results, and the Discover→Run round-trip

Continues [Part 302](Session_2026-09-30_ObservabilityErrorTrackingSecurityHardeningAndTestwrightFixes_Part302.md).
2026-10-01. A long, screenshot-driven Testwright pass. Each fix came from the user
running the real tool and hitting the next honest failure — the through-line again:
**ship a fix, verify it live on the deployed Space, let the next failure teach the
next fix.** Many "two failures = stop, find root cause" moments; the HF
`RUNNING_APP_STARTING` stale-container trap bit twice and was caught by the
stage check both times.

---

## 1. P4b — confirm-before-rerun on self-heal
Self-heal auto-fired a fresh ~50s CI run on "Heal", silently spending a cycle on a
possibly-bad fix. Now **Suggest a fix** stages the healed code into the editor and
shows the diff with **Re-run healed test** / **Discard** — no auto-run. Button
renamed "Heal & re-run" → **Suggest a fix**. Verified live end-to-end (heal
grounded to `getByRole('searchbox',…)`, no auto-run, Discard reverts, 0 CI spent).
ml-portfolio `2911264` (RunRunner.tsx, ResultView.tsx).

## 2. Docs refresh
- Testwright plan doc `0cfd4fa`→ updated: marked P0/P4/P4b/P5 shipped; only open
  speed lever = warm/self-hosted runner (recommend skip). ML-Unified `7a4fbe1`.
- **Testwright user guide rewrite** — verified every claim against the stage
  runners + backend `config.py` (no hallucination). Fixed stale self-heal flow,
  added Stop/cancel, flakiness runs, timing, Save/history, Suggest assertions, a
  full Visual walkthrough, ownership gate, provider cascade (cohere→mistral),
  budget caps, the Discover "up to 6" cap. ml-portfolio `860e427` (worldGuide.ts +
  author/userGuide.ts).

## 3. Discover 6-proposal cap — kept at 6
User asked why only 6. Web-searched: Hick's Law (fewer choices = faster), Miller
7±2 (5–9 working-memory band), E2E best practice = quality-over-quantity/80-20,
and LLM output stays more distinct at a small count. 6 sits in the sweet spot.
**Decision: keep 6** (one-line `config.MAX_PROPOSALS` if ever changed). No code.

## 4. Discover grounding — the big root cause (`30c1d62` / `ca75d45`)
**Symptom:** a Discover-generated nav test clicked the "AI AIRaML" logo and
asserted `/ai-airaml` — a route that doesn't exist (the logo's href is `/`). All
runs failed.
**Root cause (two parts):** (a) Discover loaded the page only to pick PROPOSALS;
the code-generation step (`/qa/author/generate`) was **blind** — it got plain
English + base_url, not the page. (b) Playwright's `ariaSnapshot()` has roles/names
but **no hrefs**, so URLs were pure guesses.
**Fix:** the explore spec now also captures a **link accessible-name → href map**
(≤80) appended to the existing `aria.txt` after a `===LINKS…===` delimiter — **no
ml-qa-runner workflow change**. `discover.status` returns `page_context` (snapshot +
link map); the frontend carries it into each generate call; `author.generate_test`
switches to a grounded prompt (`AUTHOR_GROUNDING`): locators verbatim from the
snapshot, URL assertions from the REAL href, in-page `#` anchors assert a visible
result not a URL. **Verified live:** grounded gen emits `toHaveURL(BASE_URL + '/')`,
not `/ai-airaml`; the real explore captures the href map.
Files: discover.py, author.py, prompts.py, models.py, config.py; useDiscover.ts,
DiscoverRunner.tsx.

## 5. Run result — show the failure reason + total (`f4869d4` / `28e46be`)
The Playwright error was already parsed for self-heal (`_first_error`) but not
shown. `_parse_zip` now cleans it (ANSI-stripped, clipped) → `error`;
`run.status` returns `error_message` on a failed run; ResultView shows a **"Why it
failed"** panel and the header leads with **"N total · X passed · Y failed"**.
Verified live (toHaveTitle failure → readable reason).

## 6. Flaky mislabel — multi-test suites aren't flaky (`4364cc4`)
**Symptom:** a 7-test file (1 pass, 6 fail, runs=1) was labelled "Flaky · 7 runs".
**Root cause:** flakiness was computed from `expected+unexpected`, which also sums
across DIFFERENT tests, not just repeats of one test.
**Fix:** `github_runner._count_tests` counts distinct spec titles; flakiness only
when `num_tests == 1 and total_runs > 1`. Multi-test files report plain pass/fail.
Verified: 2-test mixed file (runs=1) → `flaky None`, verdict "Failed". Same commit
also added the AUTHOR_GROUNDING rule about substring name matching.

## 7. Locator robustness — deterministic, not prompt-hoping (`e9eab55` + `a694015`)
Prompt grounding asked the model to disambiguate non-unique names but did so
**unreliably** (added `exact:true` in an isolated test, forgot it in a fuller one).
**Decision: make it deterministic.** `author._disambiguate_locators` post-processes
generated code when page_context is present, grounded in real per-element counts
from the ARIA snapshot (which lists EVERY element — do NOT dedupe into a set, that
was the first-attempt bug that hid duplicates). For each name-only `getByRole`:
- name repeated >1 on the page → append **`.first()`** (identical duplicates like a
  nav link also in the footer, e.g. 'Handbook'×2 — `exact` can't fix those);
- unique name over-matched by substring → **`{exact:true}`** ('Tools' is inside
  'Browse the tools');
- already-unique names untouched.
**Verified GREEN end-to-end:** regenerated the Navigation test → emitted
`AI AIRaML` (bare), `Tools` (exact:true), `Handbook/Platforms/… ` (.first()) → ran
**1 passed, 11/11 steps**.
**Lesson:** Playwright strict mode has TWO ambiguity classes — substring over-match
AND identical duplicates — and name matching is substring by default; a robust
generator must handle both, grounded in element counts, not prompt wishes.

## 8. "Learn from my edits" — scoped, not built (`39c3d62`)
Generation is stateless — hand-corrections aren't remembered on regeneration (only
**Save + re-run the saved test** persists a correction). Scoped a browser-local,
same-host, content-light correction store fed back as few-shot:
`docs/QA_LEARN_FROM_EDITS_PLAN.md` (data model, capture-on-Save, feedback flow,
API `corrections` field, guardrails, 2-phase effort). Recommendation: build only if
corrections stay common now that locators are deterministically fixed.

## 9. Discover persistence + round-trip UX (`82b648d` + `4be6961`)
**Symptom:** after Send-to-Run, returning to Discover lost the 6 proposals →
re-run every time. **Root cause:** Discover results lived only in component state.
**Fix 1 (`82b648d`):** cache the last completed discovery (proposals + page_context
+ url) in `sessionStorage`; restore in a `useEffect` (client-only → no SSR
hydration mismatch); Clear wipes it. **Fix 2 (`4be6961`):** persistence was
invisible — user wouldn't know. Added a **"Sent from Discover — your other
proposals are still there"** banner on Run with a **← Back to Discover** button
(flagged via `qa_run_from_discover` in the handoff). Guide updated.
**Verified live:** Discover → 6 proposals → Generate → Send to Run → banner + back
button present, code carried → Back to Discover → 6 proposals restored, no re-run.

## 10. Send multiple Discover drafts to Run at once (`618c9e7`)
Before: you could **Generate selected (N)** to get N drafts, but each had its own
**Send to Run** and Run executes one file per run — no way to run several at once.
**Built:** after generating ≥2 drafts, a **"Send all N to Run →"** button merges
them into ONE runnable file and hands it off. `mergeTests()` keeps a single
`import { test, expect }` and a single `const BASE_URL`, then appends every file's
`describe`/`test` blocks (naive concatenation would redeclare the import/BASE_URL
and fail to compile). Verified the merge locally: 2 drafts → 1 import, 1 BASE_URL,
both describes. Frontend-only (DiscoverRunner.tsx), reuses the Discover→Run handoff
(so the "← Back to Discover" banner still shows).

## Key decisions
- **Grounding must reach code-gen, not just proposals** — the snapshot that picks
  WHAT to test must also be fed to the step that WRITES the test.
- **Deterministic post-process beats prompt-nudging** for locator uniqueness — a
  prompt rule the model applies "usually" isn't a fix.
- **Discoverability > hidden cleverness** — persistence nobody can see doesn't
  solve the complaint; ship the visible affordance (banner + button).
- **No separate "Edit" button** — the code box IS the editor; document it instead.
- **Keep Discover at 6 proposals** (UX + testing + LLM evidence all agree).

## Lessons
- **ariaSnapshot() has no hrefs** — grounding locators from it fixes names, not
  URLs; capture a link→href map separately. [[feedback_debug_first]]
- **Playwright name match is substring by default** — short names silently match
  many elements; and identical nav+footer links need `.first()`, not `exact`.
- **HF `RUNNING_APP_STARTING` serves the OLD container** — verify stage==RUNNING
  before testing; the first post-upload probe hit stale code twice this session.
  [[feedback_status_claims_need_evidence]]
- **A failing test can be the correct outcome** — several failures here were the
  AI-draft test's wrong assumptions; Testwright reporting them is it working.

## Commits
| Repo | Commits |
|---|---|
| ml-portfolio | `2911264` (P4b) · `860e427` (guide) · `ca75d45` (Discover ctx) · `28e46be` (why-failed UI) · `92455e6` (edit-guide note) · `82b648d` (Discover persist) · `4be6961` (back-to-Discover) · `618c9e7` (send-all-to-Run) |
| ML-Unified (backend, HF-uploaded) | `30c1d62` (grounding) · `f4869d4` (failure reason) · `4364cc4` (flaky gate + substring rule) · `e9eab55` (exact:true) · `a694015` (.first() dupes) |
| ML-Unified (docs) | `7a4fbe1` (plan refresh) · `39c3d62` (learn-from-edits plan) |

## State after this session
- **Discover** grounds generation in the real page (snapshot + link hrefs),
  persists results, and offers a visible round-trip back from Run.
- **Generation** deterministically disambiguates locators (substring → `exact:true`,
  duplicates → `.first()`); self-heal is the backstop.
- **Run** shows total/passed/failed + the real failure reason; multi-test suites are
  no longer mislabelled flaky.
- **Send multiple Discover drafts to Run at once — DONE** (`618c9e7`): "Send all N
  to Run" merges drafts into one suite.
- Open: "learn from my edits" (scoped in `docs/QA_LEARN_FROM_EDITS_PLAN.md`,
  parked). Related: [[project_testwright_qa_platform]],
  [[project_testwright_run_perf]].
