# Part 311 — Wiring the 15 tool User Guides into their in-app modals

Continues [Part 310](Session_2026-10-04_TestwrightBYOKOwnerModelMonitoringCIRescueAndGuides_Part310.md).
2026-10-07. Short, focused session: closed Part 310's one shipped-but-not-wired
follow-up — the 15 new `userGuide.ts` files fed the handbook but weren't shown
**inside** each tool's own page. Now every one has an in-app "User Guide" button + modal.

Through-line: **content shipped ≠ feature wired** — a guide that only reaches the
handbook is invisible where the user actually is (the tool page). And:
**verify the build, not just the linter** — a CLI eslint "error" is not the same as
a build failure.

---

## The gap (confirmed, not assumed)
The user asked what "wiring each into its in-app guide modal/chat" meant. Verified
live before answering:
- All 15 `userGuide.ts` files exist and **do** feed the handbook (build globs
  `src/app/tools/<id>/userGuide.ts`; rebuild produced no diff → already current).
- But **none** of the 15 tool pages imported their guide — no `*UserGuideModal.tsx`,
  no button — unlike wired tools (anomaly-detection, jwt-analyzer, …). So the guides
  were handbook-only; the per-tool "?" was missing.

## What shipped (`f78ff1d`, ml-portfolio, frontend-only)
A "User Guide" header button + modal on all 15 tools, rendering each tool's
`*_GUIDE` markdown. Tools: text-to-image, depth-parallax, automl, shap, drift,
ensemble, feature-engineering, feature-selection, optuna, preprocessing,
pipeline-builder, pipeline-cinema, pose-vj-visuals, rag-analytics, face-liveness.

## Decisions
- **One shared component, not 15 copies.** `components/ToolGuideModal.tsx`
  (`guide`/`title`/`accent`/`toolId` props) instead of 15 near-identical 77-line
  modal files — honors the "don't generate near-identical files" rule. Existing
  per-tool modals (older tools) left untouched.
- **Chat left as-is.** The 10 chat-enabled tools already had hand-written
  suggestions; swapping them in would be churn with no gain. The 5 without chat
  (face-liveness, pipeline-builder, pipeline-cinema, pose-vj-visuals, rag-analytics)
  got **modal only** — they're a camera toy, an animation and a dashboard; chat
  doesn't fit. Agreed up front, not discovered late.
- **Split the two >350-line pages BEFORE adding the feature** (file-length rule):
  - `feature-selection` 351→**345**: extracted `ACCENT`+`CARD` to `fsConstants.ts`;
    button added to the existing `FSPageHeader` via an optional `onGuideOpen` prop
    (page growth stayed tiny because its header was already a component).
  - `pipeline-cinema` 363→**339**: extracted the CSV parsers + transport icons to
    `cinemaHelpers.tsx`.
- **`pipeline-builder` left at 367** (was 340). It has two header variants, so the
  button+modal went into both. Rule-compliant (was <350 when touched, <400 cap);
  flagged as a future-split candidate. User: **keep as-is.**

## The eslint-vs-build lesson
Scoped eslint flagged **2 errors** (`react-hooks/set-state-in-effect`) in
`feature-engineering/page.tsx`. Checked ownership before reacting:
- My FE diff was **additions only, 0 deletions** — the flagged `useEffect` bodies
  were untouched.
- `git stash` of the file + re-lint on HEAD → **count = 2**: both errors are
  **pre-existing**, not mine.
- `next.config` has no `eslint.ignoreDuringBuilds`, yet **`next build` exits 0**
  ("Compiled successfully") with those errors present — so the CLI flat-config
  severity ≠ what the build gates on. Build green = the real verification; the CLI
  error count was a false alarm about my change.

**Verification chain:** `tsc --noEmit` = 0 after each batch (3 batches of ~5) →
full `next build` = exit 0 at the end. Nothing called done without the build proving it.

## Staging discipline
Working tree also held `AGENTS.md` (modified) and `verify-recon-warning.mjs`
(untracked) — **not this session's**. Staged exactly the 19 intended paths by name;
left those two alone. [[feedback_never_git_add_all]] [[feedback_never_delete_user_files]]

## Open / next
- **Site-wide doc-coverage CI check** (Part 310 Arc 6) — still designed, not built;
  the only item with no external blocker.
- Parked (need something that doesn't exist yet): Learn-from-edits Phase 1
  (`test_edited` data); R5 authenticated testing (login-gated app). R9 API testing = skip.

## Commits
| Repo | Commit |
|---|---|
| ml-portfolio | `f78ff1d` — wire User Guide modal into 15 tool pages (+ `ToolGuideModal.tsx`, `fsConstants.ts`, `cinemaHelpers.tsx`) |

Related: [[project_testwright_qa_platform]], [[feedback_file_length]],
[[feedback_status_claims_need_evidence]], [[feedback_use_subagents]].
