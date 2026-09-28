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

## 3. Still pending — dead vocabulary (8 names)

Defined in `logEvents.ts`, zero call sites: `guide_open`, `tool_card_click`,
`scroll_depth`, `sample_load`, `paste_input`, `run_retry`, `result_expand`,
`citation_click`.

Most are cheap — one shared component covers every tool:
- `guide_open` → the shared User-Guide modal.
- `tool_card_click` → the shared tool-card component.
- `result_expand` / `citation_click` → only where expandable rows/citations exist
  (multimodal-rag, reconciliation, document-intelligence).

## 4. Remaining plan (cheapest, highest-value first)

Each step ships with the privacy page update (§7) **if it introduces a new data
category**, carries enumerated facts only (§6), and uses the production write-gate.

2. `guide_open` — one emit in the shared User-Guide modal.
3. `tool_card_click` — one emit in the shared tool-card component.
4. `result_expand`, `citation_click` where they apply.
5. `sample_load`, `paste_input`, `run_retry`.
6. `scroll_depth` last — lowest value, noisiest.

## 5. Privacy-page note for step 1

Step 1 needed **no** privacy-page change: it adds no new column and no content —
`query_run` and enumerated meta are already disclosed under "What is recorded about
your visit", and `password-audit` logs a content-free run. Steps 2–6 must be
re-checked against the page individually.

## 6. Guardrails (from LOGGING_SPEC.md §6)

- No content in `events` — counts, sizes, enumerated choices only. Search text →
  salted hash, never the string.
- Fire-and-forget; a logging outage is invisible to the user.
- One vocabulary file; no string literals to `track()`.
- `session_id` stays anonymous; no new PII.
- The password tool stays content-free — no password, no derived breach outcome.
