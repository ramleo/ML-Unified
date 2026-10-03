# Testwright — "Learn from my edits" (scoped plan)

**Status:** Phase 0 (measurement) SHIPPED 2026-10-03 — Phase 1 GATED ON ITS DATA.
Proposed 2026-10-01. Scopes a feature so Testwright's generators improve from a
user's own corrections instead of repeating a mistake. **Owner doc** for the work
below. Companion: `docs/TESTWRIGHT_IMPROVEMENT_PLAN.md`.

> **Phase 0 is live (ml-portfolio `dbb1082`, frontend-only).** Before building the
> full feature we measure whether corrections are still frequent (see §12). A
> content-free `TEST_EDITED` analytics event (mirrors `SQL_EDITED`) fires when a
> user saves a GENERATED test they changed, classifying the edit as **locator /
> assertion / other** (assertion-precedence, so an `expect()` wrapping a locator
> counts as assertion and doesn't inflate the "locators still broken" signal).
> Emits only counts + booleans — no code, host, or text. Files:
> `src/app/qa/run/corrections.ts` (`editMeta`, `trackEdit`), `RunRunner.tsx`
> (baseline tracked on Send-to-Run, diffed on Save), `logEvents.ts`.
> **How to read it:** Realtime Analytics → Live Feed, event `test_edited`.
> **Decision rule:** `locator_change` near-zero but `assertion_change` /
> `other_change` common → build Phase 1 below. Corrections rare → park; Save+re-run
> is enough. Do NOT rebuild Phase 0.

## 1. Problem
Generation (Author `/qa/author/generate`, and Discover which calls it) is
**stateless**. If a user hand-corrects a generated test, regenerating a similar
test later does **not** remember the correction — the same class of mistake can
recur. Today the only way to keep a correction is **Save the test and re-run the
saved one**; the generator itself learns nothing.

Note: the most common reason to correct a locator (ambiguous names) is already
handled deterministically in `author._disambiguate_locators`. This feature targets
the *remaining*, idiosyncratic corrections a user makes (preferred assertions,
chosen locators for their own markup, phrasing).

## 2. Goals / non-goals
- **Goal:** a user's past corrections for a site bias future generations for that
  same site toward the pattern they chose.
- **Goal:** zero login, no server-side storage of user content, content-light.
- **Non-goal:** a global model/fine-tune, cross-user learning, or server state.
- **Non-goal:** remembering across devices/browsers (browser-local is acceptable).

## 3. Principles
- **Browser-local.** Corrections live in `localStorage` (like saved tests / history),
  never persisted server-side. Same trust model as the existing QA storage.
- **First-party / same-host only.** A correction learned on host A is only offered
  when generating for host A. Avoids leaking one site's structure into another.
- **Locator-level, not whole files.** Store the *diff* (the lines that changed —
  locators/assertions), not the full test, to stay small and content-light.
- **Advisory, reversible.** Fed to the model as a hint, not a hard rule; the user
  can view and **Clear learned fixes** at any time.

## 4. Data model (localStorage)
Key `qa_corrections` → array (cap ~20, FIFO), each:
```
{
  id, host,                 // host from the test's base URL
  before: string[],         // removed locator/assertion lines (<= ~6)
  after:  string[],         // added locator/assertion lines  (<= ~6)
  at: number                // timestamp
}
```
Derived from the existing `lineDiff(original, edited)` already used by the heal
banner — reuse it, don't add a new differ.

## 5. Capture flow
When do we record a correction? Two safe triggers (pick one to start):
- **On Save** of a test that differs from the last generated version for the same
  host — diff generated→saved, store the locator/assertion lines.
- (later) **On a passing run** of an edited test — stronger signal it's correct.
Start with **On Save** (simplest, user-intentional). De-dupe identical diffs.

## 6. Feedback flow
On `/qa/author/generate` (and Discover's per-pick generate), the frontend attaches
up to **N=3** most-recent corrections **for the same host** as a new optional
field `corrections: [{before, after}]`. Backend `generate_test` appends a short
"learned preferences" block to the user message when present:
> "The user previously corrected similar tests on this site. Prefer these patterns:
> replaced `<before>` with `<after>`. Apply the same style where it fits."
Keep it in the user message (not the system prompt), capped in length, and only
when `page_context`/host matches.

## 7. API / code changes
- **models.py** — `GenerateRequest.corrections: list[CorrectionPair] = []` (cap
  length; each side clipped, e.g. 400 chars, <=6 lines).
- **author.py** — `generate_test(..., corrections=None)`: build the learned-prefs
  block; include only when non-empty. No new provider calls.
- **Frontend** — `qa/run/storage.ts`: `getCorrections(host)`, `addCorrection(...)`,
  `clearCorrections()`. `RunRunner` records on Save; `useRun`/Discover attach the
  top-N for the host to the generate body. A small "Learned fixes (N) · Clear"
  line near Saved tests.

## 8. Guardrails
- Same-host match only; cap 3 fed per request; cap 20 stored.
- Locator/assertion lines only (no full files); clip length.
- User-visible count + **Clear learned fixes** control.
- Advisory wording — never force; the deterministic disambiguator and self-heal
  remain the reliable safety nets.
- Content note: corrections are the user's own test code, browser-local, sent only
  to our own generate endpoint. Update the privacy page if anything leaves the
  browser (it already does for generation requests — same posture).

## 9. Risks
- **Prompt bloat / cost** — cap N and length; measure.
- **Reinforcing a bad edit** — user can Clear; keep advisory; prefer recent.
- **Fuzzy relevance** — "similar test" is approximate; scope to host + keep it a
  hint, not a template. Risk is low because it only nudges.
- **Over-engineering** — if usage is low, Save+re-run already covers the need.

## 10. Effort & phasing
- **Phase 0 (measurement) — DONE 2026-10-03 (`dbb1082`):** content-free `TEST_EDITED`
  event on Save-of-a-changed-generated-test, classified locator/assertion/other.
  Frontend-only. Answers §12 with data before any Phase 1 investment. See the status
  box at the top for how to read it and the decision rule.
- **Phase 1 (MVP) — gated on Phase 0 data:** storage.ts helpers + record-on-Save +
  attach top-3 on generate + backend block + a Clear control. ~1 focused session.
  Backend deploy for the model/API half; frontend for capture/feed. Reuse Phase 0's
  `editMeta`/baseline plumbing in `corrections.ts` — it already captures the diff.
- **Phase 2:** record-on-pass (stronger signal), per-correction enable/disable,
  show which corrections influenced a generation.

## 11. Open questions
- Trigger: on Save only, or also on a passing run? (Start: Save.)
- Should corrections be scoped per host only, or also per page/path? (Start: host.)
- Surface in Author too, or Run/Discover only? (Start: wherever generate is called.)

## 12. Recommendation
Worth building, but **after** confirming the deterministic locator fixes reduced
real correction frequency. If corrections stay common for non-locator reasons,
build Phase 1. Otherwise Save+re-run may be enough and this stays parked.
