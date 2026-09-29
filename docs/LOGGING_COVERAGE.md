# Logging coverage audit + activation plan

Companion to [LOGGING_SPEC.md](LOGGING_SPEC.md) §12. Detailed findings and the
step-by-step wiring plan, kept here so the spec stays under its size limit.

**Audited 2026-09-28** by a full grep of `ml-portfolio/src`, then corrected while
implementing step 1 (see the correction note below).

---

## 1. Numbers

| Signal | Count |
|---|---|
| Tool pages (`src/app/tools/*`) | 61 |
| Wired for `tool_open` / `tool_close` (`useToolTracking`) | 60 |
| Cover a run via `trackedFetch` (auto `run_success` / `run_error`) | 40+ |
| Emit a run event some other way (`query_run` / `run_success` / shared modal) | rest |
| **Emitted no run event before 2026-09-28** | **11** |
| Wired in step 1 (2026-09-28) | 11 |
| Genuine no-run showcases, intentionally skipped | 2 |

The plumbing was already complete (events table, `/api/track`, `trackedFetch`,
`logEvents.ts`, `llm_calls`, `security_log`). The gap was per-tool run wiring.

### Correction note (the first audit over-counted)

The first pass looked only for `trackedFetch` / `trackRunStart` /
`incrementQueryCount` / `EV.QUERY_RUN` **inside `src/app/tools/*`**, and reported
16 uncovered tools. Two things made that an over-count:

1. **Direct `run_success` emitters were missed.** `feature-engineering` and
   `preprocessing` emit `EV.RUN_SUCCESS` (and `EV.UPLOAD`) directly — already
   covered.
2. **Shared-component coverage was missed.** `automl`'s run goes through
   `src/components/modals/AutoMLModal.tsx`, which already calls
   `trackedFetch(..., { tool: "automl" })` — covered, just not in the tool dir.

Also, **`malicious-package-scanner` makes no network call** — the `fetch(` the
grep matched was inside a *sample source-code string*, not real code. It is a pure
client-side tool. So only `password-audit` actually hits the network (HIBP).

Corrected real gap: **11** tools, all wired in step 1.

---

## 2. Step 1 — the 11 tools wired (2026-09-28)

Helper added to `src/hooks/useAnalytics.ts`:

```ts
export function trackToolRun(toolId: string, meta: Record<string, unknown> = {}) {
  incrementQueryCount(toolId);
  track(EV.QUERY_RUN, { meta: { tool: toolId, ...meta } });
}
```

| Tool | Run moment | `meta` (facts only) |
|---|---|---|
| extension-permission-analyzer | `analyze()` button | `risk` (overall level) |
| periodicity-finder | `onAnalyze()` button | `points` (count) |
| dns-tunneling-detector | `runLog` / `runHost` (hook) | `mode` (log/host) |
| gait-pattern-comparison | `analyze()` start | — |
| movement-form-comparison | `analyze()` start | — |
| video-keystroke-inference | `analyze()` start | — |
| keystroke-biometric-auth-risk | scoring in `finalize()` | `band` (risk band) |
| phishing-email-classifier | live typing, **debounced 1.2s** | `verdict` |
| malicious-package-scanner | live typing, **debounced 1.2s** | `mode` |
| password-audit | `checkBreach()` click | **none — content-free** |
| asl-fingerspelling-recognition | camera session start | — |

Design choices:
- **Live-as-you-type tools** (phishing, malicious-package-scanner) debounce so one
  run is counted per settled edit, not one per keystroke.
- **`password-audit` is content-free by design.** It logs only that a breach check
  ran — never the password *and never the breach outcome*, which is a fact about
  what was typed. This keeps the privacy page's "nothing you type there ... no
  record of it is made anywhere" claim true (§5b/§6).
- **Real-time webcam tool** (asl) has no discrete run, so one run is logged when the
  recognition session starts. No camera/biometric data is logged.

### Not wired, and why
- **Already covered:** `feature-engineering`, `preprocessing` (`run_success`
  direct), `automl` (`AutoMLModal` `trackedFetch`).
- **Visual showcases, no real "run":** `pipeline-cinema`, `pose-vj-visuals`.

---

## 3. Vocabulary status — all emitted (as of 2026-09-29)

31 event types defined; **30 emitted, 1 intentionally not** (`result_expand` — no
distinct interaction; citations are covered by `citation_click`). `guide_open` (step 2),
`tool_card_click` (step 3), `citation_click` (step 4), `sample_load`/`paste_input`/
`run_retry`/`scroll_depth` (steps 5–6), and the gap-closers `error`/`feedback` + platform
tier (§3f) are all wired — see below.

## 3b. Step 2 DONE — `guide_open` (2026-09-28)

There is **no** single shared per-tool guide modal — 44 near-identical copies,
each with only `{ open, onClose }`. So the plan's "one shared emit" wasn't
possible; instead a `useGuideOpenTracking(toolId, open)` hook was added to
`useAnalytics.ts` and called once inside each modal with its own tool id
(43 via the uniform `if (!open) return null;` anchor; `text-to-sql`'s modal
mounts-when-open so it passes `open={true}`). Emits `guide_open` with `{ tool }`,
no content. No privacy change (same category as `tool_open`). The platform-world
guide modals (`WorldUserGuideModal`, the `/qa` modals) are a separate tier and
not yet wired — a small optional follow-up.

## 3c. Step 3 DONE — `tool_card_click` (2026-09-28)

`ToolCard.tsx` **is** a genuine shared component (unlike the guide modals), and
`handleNavigate()` is the single click entry point for every path — card body,
title button, and the back "Try it"/"Launch" buttons all route through it, and it
has `cap.id`. So one emit there covers all tool-card grids. Logs `tool_card_click`
with `{ tool, source, opens }` — `source` derived from the path (`home` / `category`
/ `other`); `opens` is `here` (internal/modal) or `external`. No content. Search
results are a separate component and get their own `search_result_click` later;
platform cards (`ProjectCard`) are a separate tier, not wired.

## 3d. Step 4 DONE — `citation_click` (`result_expand` N/A) (2026-09-28)

`RagSourceCard.tsx` is the shared citation card (multimodal-rag only; the other
"citation" tools don't use it). Its click toggles the card open and selects it —
one choke point. Emits `citation_click` **on open only** (not collapse) with
`{ tool: "multimodal-rag", index, kind }` (chunk type) — never the cited text (§6).
`result_expand` was checked and **not wired**: reconciliation has no expandable
rows, document-intelligence's only toggle is its export dropdown, and the citation
card is already covered by `citation_click`. No interaction left to attach it to, so
it isn't forced.

## 3e. Steps 5–6 DONE — sample_load / paste_input / run_retry / scroll_depth (2026-09-29)

Wiring approach: **global/central** where possible (user's call), per-tool only where
unavoidable. All content-free (§6); tsc-clean; steps 1–4 verified live beforehand.

- **`sample_load`** — per-tool (each "load/try a sample" button is bespoke). Helper
  `trackSampleLoad(toolId, meta?)` added to `useAnalytics.ts`, called in **7 tools**:
  `exploratory-data-analysis`, `extension-permission-analyzer`, `periodicity-finder`,
  `email-auth-checker`, `jwt-analyzer` (×2 — `{variant: weak|strong}`), `secret-scanner`,
  `exploit-payload-detector`. Emits `{ tool, ...variant }` — never the sample's content.
- **`paste_input`** — **one global** `paste` listener (`usePasteInput()` in
  `AnalyticsTracker`), scoped to `/tools/*`, tool read from the path. Emits
  `{ tool, len_bucket }` (empty/<100/<1k/<10k/>=10k) — **never the pasted text**.
  `password-audit` excluded entirely (§5b).
- **`run_retry`** — **derived centrally** in `track()`: a run event (`query_run` /
  `run_success` / `run_error`) for a tool whose previous run outcome was an error emits
  `run_retry { tool }`. Covers both `trackedFetch` and `trackToolRun` with zero per-tool
  wiring. `run_retry` isn't a run event, so no recursion.
- **`scroll_depth`** — **one global** hook (`useScrollDepth()` in `AnalyticsTracker`),
  re-armed per navigation, fires `{ depth }` once at each 25/50/75/100% threshold.

## 3f. Gap-closers DONE — error / feedback / platform tier (2026-09-29)

After a coverage review, three genuine gaps were closed (the site logs the whole journey,
not just tool runs):

- **`error`** — the generic stage-7 event had **0 call sites**, so a page that threw
  during render or a rejected promise vanished silently (only `run_error` was covered).
  Now `useErrorTracking()` (in `AnalyticsTracker`) adds global `window` `error` +
  `unhandledrejection` listeners → `error { source, name }`. **Content-free by design —
  class name + source only, NEVER the message or stack** (those can hold user content or
  secrets). Error storms coalesced to 1/sec.
- **`feedback`** — NEW event. The RAG "Good/Bad answer" thumbs existed but only set local
  state; the signal was thrown away. `trackFeedback(tool, rating)` wired in
  `multimodal-rag/ChatPanel.tsx` → `feedback { tool, rating: up|down }`. No answer text,
  no reason — just the rating. This is the answer-*quality* signal (arguably the most
  valuable of the three).
- **Platform tier** — the native "worlds" (Testwright/`/qa`, EDA, ML, Vision landings)
  were unlogged. `guide_open` now fires from the shared `WorldUserGuideModal` (covers 8
  pages, id `world-<title-slug>`) and `AuthorUserGuideModal` (`world-qa-author`);
  `tool_card_click { tool, source: "platform", opens }` now fires from `ProjectCard`
  (both the internal "Enter" and external "Launch App" paths).

No privacy-page change: all content-free, enumerated meta, no new PII — the page already
discloses event type + fixed choices, and `error` carries no message. Not per-tool
feature-level (every bespoke control) — that remains a larger, separately-scoped project.

## 4. Remaining plan — none

All planned vocabulary is emitted (steps 1–6 done; steps 1–4 verified live). Optional
follow-ups only: platform-world guide modals (`WorldUserGuideModal`, `/qa`) for
`guide_open`, and `ProjectCard` for `tool_card_click` — both a separate tier.

## 5. Privacy-page note

**No** privacy-page change was needed for any step 1–6: no new column, no content, no
new PII. The page already discloses "event type + counts, sizes, durations and fixed
choices," and explicitly "Where the length of something is useful, the length is recorded
and the text is not" — which covers `paste_input`'s length bucket. `scroll_depth`,
`sample_load` and `run_retry` are event-type + enumerated meta, already in scope.
`password-audit` stays content-free (and is excluded from `paste_input`).

## 6. Guardrails (from LOGGING_SPEC.md §6)

- No content in `events` — counts, sizes, enumerated choices only. Search text →
  salted hash, never the string.
- Fire-and-forget; a logging outage is invisible to the user.
- One vocabulary file; no string literals to `track()`.
- `session_id` stays anonymous; no new PII.
- The password tool stays content-free — no password, no derived breach outcome.
