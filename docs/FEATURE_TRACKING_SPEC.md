# Feature-Level Tracking Specification

**Status:** proposed 2026-09-29 (not yet built). Extends
[LOGGING_SPEC.md](LOGGING_SPEC.md) — the journey vocabulary (steps 1–6 +
gap-closers) is complete; this adds *per-tool, per-control* granularity.
**Owner:** this file is the source of truth for feature-level instrumentation.

Companion: [LOGGING_SPEC.md](LOGGING_SPEC.md) (journey events, guardrails §6,
privacy §7), [LOGGING_COVERAGE.md](LOGGING_COVERAGE.md) (per-tool wiring).

---

## 1. Goal

Today we log the *journey* (arrival → run → results → leave) and a handful of
shared interactions. We do **not** log which bespoke control inside a tool a user
touched — draw-region, sharpen, watermark, provider switch, video seek, sliders,
mode tabs, etc. This spec adds that, for all 61 tools, **without** an event-name
explosion.

Surface being instrumented (grep, 2026-09-29): 61 tool dirs, ~607 `onClick`,
~165 `onChange`, 15 `type="range"` sliders, and **232 existing `data-wt` anchors**
(the walkthrough system already tags each tool's key controls).

## 2. The core decision — one event, many properties

The naive approach (one event name per control) is the industry anti-pattern
"event explosion": ~800 event names, unusable reporting, constant drift. Every
major analytics vendor prescribes the opposite:

> **Events = actions; properties = context.** Keep a small, fixed set of event
> names; put the variable detail (which tool, which control) in property *values*,
> never in the event name. Event/property names are fixed strings in code.

So feature-level tracking is **one new event** — `feature_use` — carrying
properties, not 800 events. This keeps the taxonomy lean and the dashboards
queryable ("top controls in tool X", "sharpen usage over time") with a single
event type.

References: Amplitude *Lean Data Taxonomy* and *Chaos to Clarity*; the
Object-Action naming framework; Mixpanel *event vs. property* guidance. Consensus:
parameterize, don't multiply event names.

## 3. Event schema

One event, added to `src/lib/logEvents.ts`:

```
FEATURE_USE: "feature_use"
```

| Property   | Type    | Meaning                                              |
|------------|---------|-----------------------------------------------------|
| `tool`     | string  | tool id (from the path, or explicit for platforms)  |
| `control`  | string  | **stable** control id, e.g. `draw-region`, `sharpen`|
| `action`   | string  | `click` \| `change` \| `slider`                     |
| `value`    | string? | **enumerated only** — a select option, a slider bucket, a toggle state. Omitted for anything free-text. |

`control` and `value` are property *values* (variable data belongs here), exactly
per the object-action framework. The event name is the only fixed string.

Example: choosing the Gemini provider in a tool →
`feature_use { tool: "document-intelligence", control: "provider-switch", action: "change", value: "gemini" }`.

## 4. Instrumentation — attribute-driven autocapture

Instrumenting ~800 controls by hand is infeasible and would rot. Instead: **one
delegated listener** reads a marker attribute off the control. Controls opt in
with a single attribute — no per-handler code.

### 4.1 The listener (`useFeatureCapture()` in `useAnalytics.ts`, mounted once in `AnalyticsTracker`)

- `click` (capture phase): `const el = e.target.closest('[data-ev],[data-wt]')`.
  If found and on a `/tools/*` or known platform path, emit
  `feature_use { tool, control, action: "click" }`.
- `change` on `<select>` / checkbox / radio: emit `action: "change"` with
  `value` = the **enumerated** option/state.
- `input` on `type="range"`: **debounced ~400ms** (fire on settle, not per tick);
  `action: "slider"`, `value` = a coarse bucket, never the raw number if the
  number is user content.

`control` id resolution order: `data-ev` (explicit, preferred) → `data-wt`
(reuse the walkthrough anchor). `tool` from `location.pathname` (`/tools/<id>`),
or `data-ev-tool` for platform pages where the path doesn't carry it.

### 4.2 Why reuse `data-wt`

The 232 `data-wt` anchors already mark each tool's *meaningful* controls (they're
what the walkthrough highlights). Reading `data-wt` as a fallback `control` id
means **~232 key controls are tracked the moment the listener ships — zero new
attributes.** New/finer controls then get an explicit `data-ev`.

## 5. Content-safety rules (hard — from LOGGING_SPEC §6)

- **Never** read `<input type=text>` / `<textarea>` values. Log only that an
  interaction occurred. `paste_input` already covers text entry (length bucket).
- `value` is logged **only** for enumerated controls: `<select>` options, radios,
  checkboxes (on/off), and slider buckets. A control whose value is user content
  logs no `value`.
- Slider values are **bucketed** (e.g. quartile or a fixed small set), never the
  raw figure when it could be content.
- Debounce sliders; coalesce rapid repeats; **no** hover / mousemove / focus.
- `password-audit` excluded entirely (§5b), like everywhere.
- One fixed event name; `control`/`value`/`tool` are property values only.

## 6. What is explicitly out of scope

- Keystroke-level capture, mouse heatmaps, session replay — not this project.
- Reading any typed/pasted/uploaded content or results.
- Per-control event *names* (the anti-pattern in §2).

## 7. Rollout — phased, each phase shippable

**Phase 0 — core (small).**
- Add `FEATURE_USE` to `logEvents.ts`.
- Add `useFeatureCapture()` to `useAnalytics.ts`; mount in `AnalyticsTracker`.
- Add the privacy-page line (§8). **Ships nothing visible; no coverage yet.**

**Phase 1 — free coverage via `data-wt`.**
- Listener reads existing `data-wt` → ~232 key controls tracked instantly.
- Live-verify a handful (a click, a select change, a slider) at the network layer.

**Phase 2 — high-value explicit `data-ev`, prioritized.**
Add `data-ev` to rich controls not already `data-wt`-tagged. Suggested order by
value/complexity:
1. `multimodal-rag` — **DONE (c523609, 2026-09-29):** `visual-action` select (one
   attribute captures all detect/verify/describe actions as the value), draw-region,
   restricted-zone, sharpen (whole/region/cancel/view), watermark (embed/verify),
   download/reset-edit, detect-faces, find-similar, provider-settings, answer-length
   (value = concise/normal/detailed via `data-ev-value`).
2. Video/image tools — frame seek, region select, mode tabs. *(pending)*
3. `exploratory-data-analysis` — **section nav DONE (c523609):** `eda-section`
   (value = section id). Per-column ops / report toggles pending.
4. Remaining tools with distinctive controls, in usage order. *(pending)*

Enhancement shipped alongside batch 1: the click path reads an optional
`data-ev-value` so button groups capture the choice while keeping a stable
control id (still enumerated, never content).

**Phase 3 — read side.**
A per-tool feature-usage view (top controls, trends). Backend/analytics query
only; no new client events.

## 8. Privacy

Unlike journey steps 1–6, this **does** add a new granularity: *which controls
within a tool you interact with*. Phase 0 **must** add a line to
`ml-portfolio/src/app/privacy/page.tsx` under "What is recorded about your visit,"
e.g.:

> "…and which features within a tool you use (for example that you opened the
> region tool or switched provider) — the control's name, never anything you typed
> into it."

Still content-free, still no new PII, still enumerated meta. The insert in
`src/app/api/track/route.ts` is unchanged (same columns); only the disclosure
text expands. See LOGGING_SPEC §7.

## 9. Open questions / decisions

- **Slider bucketing:** fixed quartiles vs. per-control buckets? Default: quartiles
  unless a control defines its own.
- **`data-ev` id casing:** kebab-case, tool-scoped uniqueness (ids need only be
  unique within a tool, since `tool` is always a property).
- **Volume:** `feature_use` will be the highest-volume event. Confirm the events
  table + retention (14 months, §7) tolerate it; consider sampling only if volume
  proves a problem (measure first).
- **Platform worlds:** they lack a `/tools/<id>` path — require `data-ev-tool`.

## 10. Acceptance

Phase 0+1 is "done" when: `feature_use` fires from `data-wt` controls across
several tools, verified live at the network layer with correct `{tool, control,
action}` and **no** content in any payload; the privacy page is updated in the same
change; `tsc` clean; docs updated.
