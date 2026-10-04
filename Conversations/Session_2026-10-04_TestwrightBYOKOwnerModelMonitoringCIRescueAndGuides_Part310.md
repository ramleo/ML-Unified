# Part 310 — Testwright: owner-only paid model + BYOK, R8 monitoring, a two-week-stale CI rescued, and 15 tool guides

Continues [Part 309](Session_2026-10-03_TestwrightHealSyntaxGuardAndEvidenceFirstFailureDrill_Part309.md).
2026-10-04. Cleared Part 309's "tomorrow" queue, then built two real features (model
selection and scheduled monitoring), discovered CI had been partly red for two weeks and
fixed it at the root, and closed the documentation gaps.

Through-line: **close the loop with live evidence** — nothing was called done without a
command proving it (a real generation call, a scheduled monitor run, 7/7 CI checks). And:
**a green-looking repo can be lying** — a skipped job hides failures until something forces
it to run.

---

## Arc 1 — the two Part-309 "tomorrow" items, shipped
- **Grounding rules 10e/10f** (`e119d8c`, HF): a filter/toggle **button ≠ navigation**
  (don't `toHaveURL` on it — that was the Computer Vision 31s timeout); a **print** button
  opens the print dialog, not a download (`waitForEvent('download')` only on a real
  `[download]` link). `discover.py` marks `<a download>`; `locators._parse_link_map` strips
  both `[newtab]`/`[download]`. Heuristics + the one deterministic marker.
- **Gemini comparison** (off-line, 2 paid calls, key read from `.env.local`, never wired in):
  Gemini-3.6-flash was clean on both cases the free cascade fumbled (heal typo; 10e trap).
  **Decision unchanged** then — but Arc 2 changed the design properly.

## Arc 2 — model selection: owner-only paid model + BYOK (`bec6707` HF, `bd5c396` FE)
Resolved the standing tension ("Gemini can't go on public endpoints — it bills every
visitor"). Generation (author/assertions/heal) now resolves its provider **per request**:
- **Free cascade** (cohere→mistral) — unchanged default, every visitor.
- **BYOK** — caller's own key for any provider, single provider, no fallback; key used for
  that request only, stored only in the browser.
- **Owner** — an **owner token** (`QA_OWNER_TOKEN`, constant-time compare) unlocks the
  server's paid Gemini. A visitor naming a paid provider without a key/token falls back to
  free — **the server's paid key is never spent by a visitor** (verified live: `/generate`
  with `gemini`+wrong-token → provider `cohere`).
The infra was half-built: `_resolve_key(provider, user_key)` already supported BYOK; QA
just never exposed it. New: `deps.select_candidates` + `owner_allowed`; `ModelChoice`
fields on the LLM request models (optional → back-compatible); FE `lib/modelChoice.ts` +
`ModelPicker.tsx` in Author (set once, stored per browser).
[[project_llm_provider_status]] [[feedback_no_unilateral_provider_swaps]]

## Arc 3 — R8 scheduled monitoring, verified end-to-end
Owner-only (recurring CI cost, reuses the same owner token; BYOK doesn't apply — a monitor
re-runs a saved test, no LLM call). `qa_monitors` table (`1ccf02f`) + owner-gated
`/api/qa-run/monitor` CRUD + "Monitor this test" on a passed run + a dashboard **Monitors**
panel (`5f83008`) + a scheduled `ml-qa-runner` workflow (`6a7b6de`, container-aligned
`7627f41`, Refresh feedback `76a5c7b`). **Verified live:** 2 monitors created in UI →
manual `workflow_dispatch` → "due monitors: 2" → both passed → recorded → dashboard updated.
Full loop proven: create → due-check → scheduled CI run → record → dashboard.
**Decision:** R9 (API testing) = **skip** (off-identity; needs different grounding; only
win is speed). R7 "share + historical dashboard" was already shipped — a stale §9 roadmap
row, fixed (`91b6d63`).

## Arc 4 — CI had been partly red for TWO WEEKS (the lesson)
The user spotted red ✗ (4/6) on every recent commit. Drilled with `gh api check-runs`:
- **file-length** — red since **Sep 20** (the apps-reskin commits grew `common.css` past
  its 1693 pin). Not mine. Fix: **split** the self-contained animation block into
  `common-anim.css` + `@import` at the top of common.css (no HTML change → no other pins
  trip; the 3 consuming HTMLs are themselves pinned). `9885b28`.
- **ruff `test`** — red since ~Sep 30. `app.py` has 156 **E402** ("import not at top") —
  **deliberate**: pixel-caps/env must run before cv2/PIL (the decompression-bomb guard,
  `dd19f1c`). Fix: file-level `# ruff: noqa: E402` with the reason, **not** moving imports.
  `9885b28`.
- **Then `test` still failed** — fixing the lint let **pytest run again** (it had been
  *skipped* for ~2 weeks because the lint step failed first), which **unmasked 5 stale
  tests**: `test_provider_cascade.py` still expected `[cohere, mistral, gemini]`, but the
  document cascade dropped Mistral in `3889bd6` → now `[cohere, gemini]`. Updated the tests
  to match the code (verified by loading the real `_cascade`), RAG fallback untouched.
  `94a7c01` → **7/7 green**.

**Lesson:** a failing early step (lint) silently skips later steps (pytest), so "the job is
red" hid *three* independent problems, two of them pre-existing and invisible. Green per
check ≠ everything runs. None were mine; all fixed at root, no pins raised, no tests
weakened.

## Arc 5 — agent observability: where it applies
Asked whether an agent-observability framework fits the site. Real agents = **`rag/agent.py`**
(LangGraph `StateGraph`), **`rag/crag.py`** (corrective RAG loop), `siem_triage.py`.
Testwright + most tools are **single LLM calls**, not agents. So orchestration/multi-hop
tracing applies only to the two LangGraph flows; cost/token, latency, quality, guardrails
apply site-wide (and partly exist: DIY error store + Sentry, budget caps, cascade logging).

## Arc 6 — a doc-coverage CI check: feasible, with an inherent limit
Can CI catch "added a feature, forgot the guide"? **Only for feature-shaped things with a
footprint CI can enumerate** — a new tool dir, platform, API route, or named control. A
pure **behavior** change inside existing code (no new file/route/label) has nothing to
enumerate, so it can't be auto-caught — that always needs human review. (The handbook's own
check works only because handbook.md is *generated*: regenerate + `git diff`.) Proposed a
site-wide presence check (tool → capabilities entry; platform → guide; route → mentioned in
a guide); not yet built.

## Arc 7 — 15 tool userGuides + handbook (4 batches)
Found **16 of 61 tool dirs had no `userGuide.ts`** (by design — documented via their
`capabilities.ts` card; `[domain]` is a dynamic route, not a tool). Wrote the 15 real ones,
content-first (what/purpose/how-to/worked example/reading/limits + suggestions), regenerating
the handbook each batch. Now **every real tool has a guide**; `rag-analytics` (which had no
card either) got its first handbook coverage.
**Caveat recorded:** these are content-only — they feed the handbook now; wiring each into
its in-app guide modal/chat (`page.tsx` + a modal per tool) is a deferred follow-up.
Also updated the **Testwright in-app guide** (`worldGuide.ts`) with model selection,
monitoring and dashboard/share/export sections (`66b79b6`), and regenerated the handbook
(`403e1bd`).

## Key decisions / lessons
- **Fix the class, not the provider** (carried from 309): BYOK + an owner gate solved the
  public-endpoint cost problem without swapping the free default.
- **A skipped CI step hides everything after it.** Make the real check actually run before
  trusting green.
- **Pre-existing ≠ ignore, but verify ownership first.** Each red was drilled to a commit
  (Sep-20 reskin, `dd19f1c`, `3889bd6`) before touching anything — none were this session's.
- **Doc automation has a hard floor:** you can enforce "sources are present/in sync," never
  "sources describe every behavior."

## Open / deferred
- **In-app wiring** of the 15 new tool guides (modal + chat per tool) — content shipped,
  wiring pending.
- **Site-wide doc-coverage CI check** (Arc 6) — designed, not built.
- Still parked: Learn-from-edits Phase 1 (needs `test_edited` data); R5 auth testing (no
  logged-in app).

## Commits
| Repo | Commits |
|---|---|
| ML-Unified (backend/HF) | `e119d8c` (10e/10f grounding), `bec6707` (model select + BYOK + owner), `9885b28` (CI: E402 noqa + common.css split), `94a7c01` (stale cascade tests), `579dcf7`·`91b6d63` (R8/R9 plan + stale R7 row) |
| ml-portfolio | `bd5c396` (model picker), `1ccf02f`·`5f83008`·`76a5c7b` (R8 monitoring), `66b79b6` (in-app guide), `403e1bd` (handbook), `ff502b1`·`9e2f7a8`·`e9370aa`·`064ed77` (15 tool guides, batches 1–4) |
| ml-qa-runner | `6a7b6de`·`7627f41` (scheduled qa-monitors workflow) |

Related: [[project_testwright_run_perf]], [[project_testwright_qa_platform]],
[[feedback_status_claims_need_evidence]], [[feedback_answer_short_and_plain]].
