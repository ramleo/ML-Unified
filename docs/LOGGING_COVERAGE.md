# Logging coverage audit + activation plan

Companion to [LOGGING_SPEC.md](LOGGING_SPEC.md) §12. Detailed findings and the
step-by-step wiring plan, kept here so the spec stays under its size limit.

**Audited 2026-09-28** by a full grep of `ml-portfolio/src`. Method:
- run-event coverage = a tool references `trackedFetch` (auto `run_success` /
  `run_error`) **or** a manual run event (`trackRunStart` / `incrementQueryCount`
  / `EV.QUERY_RUN`).
- The gap = tool dirs under `src/app/tools/*` referencing **neither**.

---

## 1. Numbers

| Signal | Count |
|---|---|
| Tool pages (`src/app/tools/*`) | 61 |
| Wired for `tool_open` / `tool_close` (`useToolTracking`) | 60 |
| On `trackedFetch` → auto run outcome | 40 |
| Emit a manual `query_run` | 17 |
| **Emit no run event at all** | **16** |

The plumbing is complete (events table, `/api/track`, `trackedFetch`,
`logEvents.ts`, `llm_calls`, `security_log`). The gap is per-tool wiring, plus a
set of vocabulary names that exist but are never emitted.

---

## 2. The 16 tools with no run event

```
asl-fingerspelling-recognition   automl
dns-tunneling-detector           extension-permission-analyzer
feature-engineering              gait-pattern-comparison
keystroke-biometric-auth-risk    malicious-package-scanner
movement-form-comparison         password-audit
periodicity-finder               phishing-email-classifier
pipeline-cinema                  pose-vj-visuals
preprocessing                    video-keystroke-inference
```

Notes:
- **`malicious-package-scanner`, `password-audit`** call the network with a
  **plain `fetch`**, not `trackedFetch` — so even their outcomes are unlogged.
  - `password-audit`'s only call is a third-party **HIBP k-anonymity range
    lookup** (`api.pwnedpasswords.com/range/<prefix>`): it sends a SHA-1 *prefix*,
    never the password. Keep that design — give it a counts-only `trackToolRun`,
    do **not** log any input (§5b excludes the password tool from content logging).
  - `malicious-package-scanner`: migrate its call to `trackedFetch` (one-line) for
    outcome logging; verify the target before assuming it's our backend.
- **`pipeline-cinema`, `pose-vj-visuals`** are visual showcases with no real
  "run" — judge per tool; don't force an event.
- The rest are genuine client-side tools (FFT, biometric, CV, data-prep) whose
  analysis runs in the browser and should emit a manual run event.

---

## 3. Defined but never emitted (dead vocabulary)

These 8 names exist in `logEvents.ts` but have zero call sites:

`guide_open`, `tool_card_click`, `scroll_depth`, `sample_load`, `paste_input`,
`run_retry`, `result_expand`, `citation_click`.

Most are cheap because a single shared component covers every tool:
- `guide_open` → the shared User-Guide modal (one emit → all 60 tools).
- `tool_card_click` → the shared tool-card component.
- `result_expand` / `citation_click` → only where expandable rows/citations
  exist (multimodal-rag, reconciliation, document-intelligence).

Already wired once at the shared-component level (not dead): `search`,
`search_result_click`, `nav_click`, `session_start`, `session_end`,
`demo_start` / `demo_complete` / `demo_abandon`, plus `upload`, `result_view`,
`export`, `copy`, `download`, `config_change` in the tools that have them.

---

## 4. Activation plan (cheapest, highest-value first)

Each step ships with the privacy page update (§7), carries **enumerated facts
only — never content** (§6), and relies on the existing production write-gate.

1. **Close the 16-tool run-event gap.**
   - Add a shared helper to `src/hooks/useAnalytics.ts`:
     ```ts
     export function trackToolRun(toolId: string, meta: Record<string, unknown> = {}) {
       incrementQueryCount(toolId);
       track(EV.QUERY_RUN, { meta: { tool: toolId, ...meta } });
     }
     ```
   - Call `trackToolRun("<id>")` at each client-side tool's run moment.
   - Migrate `malicious-package-scanner` to `trackedFetch`; give `password-audit`
     a counts-only `trackToolRun` (no input, ever).
   - Skip `pipeline-cinema` / `pose-vj-visuals` unless a real run is defined.

2. **`guide_open`** — one emit in the shared User-Guide modal.

3. **`tool_card_click`** — one emit in the shared tool-card component.

4. **Results depth** — `result_expand`, `citation_click` where they apply.

5. **Setup + retries** — `sample_load`, `paste_input`, `run_retry`.

6. **`scroll_depth`** last — lowest value, noisiest.

## 5. Guardrails (from LOGGING_SPEC.md §6)

- No content in `events` — counts, sizes, enumerated choices only. Search text →
  salted hash, never the string.
- Fire-and-forget; a logging outage is invisible to the user.
- One vocabulary file; no string literals to `track()`.
- `session_id` stays anonymous; no new PII.
- The password tool stays fully excluded from content logging.
