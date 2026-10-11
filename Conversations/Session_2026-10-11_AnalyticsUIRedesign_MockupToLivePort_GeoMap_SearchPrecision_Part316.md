# Part 316 — Analytics dashboard redesign: mockup → live port, and the fixes it surfaced

Continues [Part 315](Session_2026-10-11_TestwrightSelfTesting_RunLive_TWGround_ActivityLog_Part315.md).
2026-10-11. The user disliked the Real-Time Analytics UI ("doesn't look good"), so we
researched state-of-the-art dashboards, built an **approved design-direction mockup** as an
artifact, then **ported it to the ~20 live React components** in batches. The port, and the
user's close review of it, surfaced a chain of real defects (a stale generated handbook that
had been failing CI, a geo "map" that was never a map, a search that matched description prose,
mismatched donut sizes).

Through-lines:
- **A mockup is the spec; match it, don't improvise.** Every deviation I made from the approved
  mockup (keeping the geo map; "completing" early) came back as a correction.
- **"Verify" means screenshot both and diff — not claim.** The user said "i dont trust you";
  the answer was an actual side-by-side (served the mockup locally, screenshotted live, compared).
- **A generated file is not a source.** The handbook CI had been red for a day because Ch17 prose
  was hand-written into the generated `public/handbook.md`.

---

## Arc 1 — research + approved mockup
Researched dashboard design (Vercel/Linear/PostHog/Grafana): **one meaningful accent on a
monochrome base, status = colour + icon, hero metric first, area-fill charts, deliberate motion**.
Extracted the site's own tokens (`01-tokens.css`: `#0a0f1e` ground, glass cards, indigo→sky→emerald
gradient, Geist/Geist-Mono) so the redesign *extends the site*, not a template. Built a single-file
HTML **mockup artifact** (`KWiVGKqQdCtP2yVaQT9Hh8`) and iterated with the user to approval:
- plain **Activity Log** (no row boxes/badges) with a colour **legend** (yellow=warn, red=error);
- **row-fill bars** (the row *is* the bar) — flat accent for counts, **gradient for 0–100 scores**;
- **no card rails**; **2-col KPIs**; theme toggle = exact copy of the site's `ThemeToggle`.

## Arc 2 — the port (frontend-only, ml-portfolio → Vercel)
Ported the approved look to the live components as shared primitives, in reviewable batches:
- **`AnalyticsBars.tsx` (new):** `RowBars` (count=flat / score=gradient) + `SectionDivider`.
- **batch 1** `0f94b01`: `AnalyticsCharts` bars+funnel → RowBars (373→235 lines), QueryByTool →
  gradient, ActivityLog → plain+legend, StatCard → monochrome/no-rail.
- **batch 2** `e75cf4d`: HF/portfolio card rails removed, feature/LLM bars → row-fill, 7 section
  dividers in the dashboard.
- **batch 3** `1eb1520`: grouped-errors panel → row-fill (last old bar).
- **typography + colour** `6d05208`: Geist-Mono on labels/sections/metadata + larger sizes
  (the live labels were a hard-to-read 9–11px); **title gradient** on "Analytics"; summary-card
  greens → muted. Gotcha: a section `<h2>` took the site's heading font ("Archivo") over the
  `font-mono` **class** — forced the family inline.
Each batch: typecheck, `npm run dev` + Playwright screenshot/computed-style check, then commit.

## Arc 3 — the handbook CI had been red for a day
Pushing the port made the red ✗ (8/9) obvious. The failing check was **handbook**: it regenerates
`public/handbook.md` from sources and diffs. Commit `936af5e` (Part 315's "Ch17 observability")
had written 113 lines **straight into the generated file** with no source change, so every
regenerate dropped them → permanent mismatch. **Fix** (`a3d4950`): moved the prose into its real
source (`docs/chapters/realtime-analytics.md`, the deep chapter — its headings start at `##`) and
regenerated; content preserved, generator back in sync, 9/9 green. **Lesson:** a generated file is
output; edits belong in its source, and a CI that regenerates-and-diffs is what catches the slip.

## Arc 4 — "Visitors by Country": the map that was never a map
The user asked "is this geo map?" — it was lat/lon dots on an **empty grid, no landmasses**. I had
"kept" it and called the redesign complete without checking it rendered as a map. Two moves:
1. `6a5b43c`: replaced the dot-grid with **row-fill bars** (country code→name via
   `Intl.DisplayNames`) to match the mockup.
2. `edbbe85`: the user then wanted a map **option** too → built `AnalyticsGeoPanel` with a
   **Bars / Map toggle**. Map = a **real equirectangular world map** (Natural Earth 50m,
   `public/world-equirect.svg`, ~540KB, **lazy-loaded only on first Map click**, themed via our own
   CSS on `.region` paths, visitor bubbles at lat/lon from a centroid table). Sourcing: fetched the
   SVG from Wikimedia (`Special:FilePath`), confirmed equirectangular (1100×550, 2:1) + class-based
   paths (so it themes cleanly), stripped metadata. **Lesson:** don't call it complete until you've
   looked at the panel; "keep X" is still a decision that needs verifying.

## Arc 5 — tool search matched description prose
Typing "real" in ML Pipeline surfaced **Periodicity Finder** — because its description reads
"timestamps in **real** time units" and `scoreTerm` (`lib/toolSearch.ts`) scored descriptions.
`5b2efd8`: dropped the description field; search now matches **title / subtitle / tags only**.
Verified live (1 of 13). **Honest note to user:** the earlier "nothing broken in tools" audit
checked that tools *load/are wired*, not search-*relevance* — so this was a real miss in that claim.
Tradeoff: a keyword only in prose won't surface now; it belongs in `tags`.

## Arc 6 — donut size mismatch
The two donuts in one card rendered at different scales: `TypeDonut` used a `360×140` viewBox,
`DeviceDonut` `200×100`, both `w-full` → the device donut + legend scaled up ~1.8×. `4267b53`:
gave `DeviceDonut` the identical geometry/viewBox/font sizes.

## Key decisions / lessons
- **The approved mockup is the contract.** Deviations (geo map kept; premature "complete") each
  bounced back. Match it; raise deviations explicitly, don't just do them.
- **Trust is rebuilt with evidence, not assertions.** Served the mockup over `http.server`,
  screenshotted it + live, and diffed — that's what "check everything again" needed.
  [[feedback_status_claims_need_evidence]] [[feedback_verify_claims_with_screenshots]]
- **Generated ≠ source.** [[feedback_debug_first]] — regenerate-and-diff CI caught a hand-edit.
- **File-length discipline held:** `AnalyticsCharts` dropped 373→235 by extracting RowBars;
  `AnalyticsDashboard` sits at ~348 (split before the next big edit). [[feedback_file_length]]
- **Lazy-load the heavy bit:** the 540KB map loads only when Map is selected; Bars stays light.

## Commits (all ml-portfolio)
| Commit | What |
|---|---|
| `0f94b01` | redesign batch 1 — RowBars, plain log, clean cards |
| `e75cf4d` | batch 2 — panels, rails removed, section dividers |
| `a3d4950` | handbook CI fix — Ch17 prose moved to its source chapter |
| `1eb1520` | batch 3 — grouped errors → row-fill |
| `6d05208` | typography + colour — Geist-Mono labels, title gradient, muted greens |
| `6a5b43c` | Visitors by Country → row-fill bars |
| `edbbe85` | Visitors by Country → Bars/Map toggle + real world map (`public/world-equirect.svg`) |
| `5b2efd8` | tool search ignores description prose (title/subtitle/tags only) |
| `4267b53` | device donut matches type donut size + legend font |

## Open / next
- **Phase 2** (Testwright fixtures + fake-media for the ~34 upload/camera tools) — still the only
  parked item.
- Donut palette (Events-by-Type uses a broader multi-colour set than the mockup's tight brand set)
  and a couple of panels the mockup consolidated (Top Referrers, Tool Comparison) — user said leave
  them.

Related: [[project_analytics_ui_redesign]], [[feedback_status_claims_need_evidence]],
[[feedback_verify_claims_with_screenshots]], [[feedback_debug_first]], [[feedback_file_length]],
[[project_search_matching_hybrid]].
