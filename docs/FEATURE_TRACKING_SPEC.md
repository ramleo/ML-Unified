# Feature-Level Tracking Specification

**Status:** **Phases 0–3 built (2026-09-29); 0–2 verified live.** Extends
[LOGGING_SPEC.md](LOGGING_SPEC.md) — the journey vocabulary (steps 1–6 +
gap-closers) is complete; this adds *per-tool, per-control* granularity via one
`feature_use` event. Phase 3 (dashboard) is built and shipped but needs its Supabase
RPC applied once — run `ml-portfolio/supabase/feature_usage.sql` in the SQL editor;
until then the panel shows a setup hint.
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

**Phase 2 — high-value explicit `data-ev`. DONE 2026-09-29** (batches 1–4:
c523609, 9d53acb, f5d2cc5, 2cab8bb). Tagged every tool with a distinctive control
beyond its (already-tracked) run button:
1. `multimodal-rag` — `visual-action` select (captures all detect/verify/describe
   actions as the value), draw-region, restricted-zone, sharpen (whole/region/
   cancel/view), watermark (embed/verify), download/reset-edit, detect-faces,
   find-similar, provider-settings, answer-length (value via `data-ev-value`).
2. `exploratory-data-analysis` — `eda-section` (value = section id).
3. `text-to-image` — style-option, enhance-prompt, variation-count, edit-sharpen,
   apply-edit. `meeting-intelligence` — transcript-seek, toggle-transcript.
4. Media — `text-prompted-video-tracking` (video-playpause, frame-scrub),
   `face-cloak`/`style-cloak` (cloak-strength slider),
   `captcha-hardening-lab` (captcha-intensity slider),
   `face-deanonymization-demo` (protect-retest, gallery-remove),
   `wildlife-reidentification` (gallery-remove).

**Not tagged, intentionally:** run-and-show tools (scan-descreen, gait/movement
comparison, keystroke-biometric, intrusion-detection, asl-fingerspelling,
video-keystroke-inference) — their only control is analyze/run, already tracked by
`query_run`/`run_success`. Generate/download/upload buttons everywhere are left to
their existing run/download/upload events to avoid double counting.

Enhancement shipped alongside batch 1: the click path reads an optional
`data-ev-value` so button groups capture the choice while keeping a stable
control id (still enumerated, never content).

**Phase 3 — read side — BUILT 2026-09-29 (9a0a333), pending RPC install.**
Delivered exactly as scoped below: `supabase/feature_usage.sql` (the RPC),
`/api/feature-usage` (calls it; `{needs_setup}` until installed), and
`AnalyticsFeatureUsage.tsx` in `realtime-analytics` (per-tool ranked control bars +
value chips + tool selector), wired into `AnalyticsDashboard`. **Remaining action:
run the SQL in the Supabase editor once**, then data appears. Original scope:
A per-tool feature-usage view built on the **existing** `realtime-analytics`
dashboard. No new client events — this only reads the `feature_use` rows already
being written (`meta = {tool, control, action, value}`).

*What already exists (build on, don't duplicate):* the `realtime-analytics` tool is
a full dashboard (`AnalyticsDashboard` + ~20 components incl. `AnalyticsQueryByTool`,
`AnalyticsPortfolioTools`, `AnalyticsHeatmap`, `AnalyticsAIPanel`), fed by
`ml-portfolio/src/app/api/stats/route.ts`, which pages all events in a range and
aggregates in JS (it already selects the `meta` column, so `feature_use` data is
already arriving — just not aggregated or shown).

*3.1 Aggregation.* Produce, per range: `feature_use` grouped by `meta.tool` →
`meta.control` → `meta.action` with counts; a **value breakdown** per enumerated
control (e.g. `provider-settings` → provider mix, `answer-length` →
concise/normal/detailed, sliders → quartile distribution); overall and per-tool
"top controls".

*3.2 Data path — the one real decision (volume).* `feature_use` is the
**highest-volume** event and `/api/stats` currently fetches every row to JS, which
will not scale for 30-day ranges. **Recommended:** a dedicated aggregated endpoint
(or a Supabase SQL function / RPC) doing `GROUP BY meta->>'tool', meta->>'control'`
server-side, returning counts not raw rows — do NOT widen the all-events fetch.
(Alternative, faster to ship but doesn't scale: reuse the existing JS-aggregation
pattern in `/api/stats`.)

*3.3 UI.* One new `AnalyticsFeatureUsage.tsx` in `realtime-analytics`, mirroring
`AnalyticsQueryByTool`/`AnalyticsPortfolioTools`: a tool filter (reuse
`AnalyticsToolbar`), a ranked bar list of top controls for the selected tool, an
action mix (click/change/slider), and value-breakdown mini-charts for enumerated
controls. Wire into `AnalyticsDashboard`; add the shape to `analyticsTypes.ts`;
follow the dataviz skill for the charts.

*3.4 Guardrails.* Read-only over already-logged, content-free data → **no privacy
change, no new events, no new columns.** Access model is whatever `realtime-analytics`
already uses.

*Effort:* moderate — 1 aggregated endpoint (SQL RPC recommended) + 1 component +
types. Acceptance: the panel shows top controls per tool and at least one value
breakdown, over a 30-day range, without a full-table scan in the browser.

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
