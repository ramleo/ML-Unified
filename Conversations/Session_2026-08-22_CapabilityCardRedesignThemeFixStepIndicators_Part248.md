# Session 2026-08-22 — Capability Card Redesign, Theme Fix, Step Indicators (Part 248)

Continuation of the same day as Part 247, but a distinct session: fixed the ML
Capabilities tool-card design (AI-slop patterns), then a flip-card height/glow bug,
then discovered and fixed a real site-wide theme bug affecting all 25 tool pages,
and finished by rolling out a live step-progress header across all 7 pipeline-stage
pages. All four threads were triggered by the user pointing at real screenshots,
not by proactive work — each fix was scoped through direct investigation before
any code changed.

Tags: `ml-portfolio`, `MLCapabilities`, `capabilities.ts`, `lucide-react`,
`PipelineShowcase`, `subtle-card`, `hover-glow`, `flip-card`, `StepIndicator`,
`ConstellationBackground`, `light-dark-theme`, `theme-bug`, `AutoMLModal`,
`OptunaRunner`, `EnsembleRunner`, `ShapRunner`, `feature-selection`,
`Playwright-verification`, `Part248`, `continuation-of-Part247`

---

## 1. ML Pipeline tool-card redesign — real AI-generated-design tells, not just "odd"

User flagged the ML Pipeline cards (Data Preprocessing, Feature Engineering, etc.)
as looking odd and asked for a web-researched opinion. Real web search (not
recalled knowledge) confirmed two specific, named patterns:
- **Colored top-border strip on a rounded card** — explicitly called out across
  multiple current design-critique sources as "the most specific tell" of
  AI-generated UI, on par with em-dashes in text.
- **Single-letter fallback icons** (`title.slice(0,1)`) — flagged as a generic
  identical-feature-cards pattern, made worse here since several cards repeated
  the same letter (three "P"s, two "F"s, two "D"s).

Fix: removed the `.card-top` strip entirely (the existing hover radial glow
already carried the per-card accent color). Added a real, semantically matched
`lucide-react` icon per tool (already a project dependency, confirmed via
`node_modules` before picking names) — e.g. `Sparkles` for Data Preprocessing,
`ShieldAlert` for Adversarial Robustness Lab, `Sprout` for Plant Growth — via a
new `icon: LucideIcon` field on `Capability`. Verified all 24 cards render a real
SVG glyph via DOM inspection (screenshots render blank on this machine — a known
local canvas-background rendering quirk, not a new issue). Commit `7a2041a`.

## 2. Flip-card height bug, then a second-order height bug from fixing it

User's very next screenshot showed the flipped (back-face) card content
overflowing and getting clipped (a purple "7" and "Stages" label cut off mid
character on Pipeline Builder). Real measurement (not guessed) found EVERY
card's back-face content needed 265-328px against a 148px fixed box.

First pass: gave front AND back faces one shared fixed height (310px, tuned from
real `scrollHeight` measurements across all 24 cards), added a description
"See more" toggle (only shown when a real `scrollHeight > clientHeight` overflow
check fires — not every card gets one), capped the expanded description at a
scrollable 170px region so toggling never resizes the card. Verified zero overflow
in both collapsed and expanded state across all 24 cards.

User's next message: "cards before flip should be small as before" — the shared
310px height had also inflated the RESTING card, which the user never asked for.
Corrected by decoupling sizing back to pure CSS (`:hover` grows 148px → 310px,
`.expanded` class grows further to 448px only for "See more" on the longest
description) instead of one shared JS-driven height — this also surfaced and fixed
a real pre-existing bug: `.flip-face.front { position: relative }` had been
silently overriding the base `.flip-face` rule's `position: absolute`, which is
what makes `inset:0` fill-to-container sizing work — meaning the front face had
been rendering at its own ~77px content height inside a taller shared container
the whole time, just invisible at the old 148px size. Also fixed the hover glow
(`--acc-glow` `::after`) to apply to BOTH faces, since it had only been on the
front face and vanished the instant a hover-triggered flip completed. Commit
`6298aa0`, then `58fa142` after the resize-behavior correction.

## 3. Hover glow extended to all `.subtle-card` sections

User asked why "Live ML Apps" doesn't glow like the Pipeline stage cards.
Answer: not a bug — a CSS comment in `globals.css` explicitly documented
`.subtle-card` as a deliberately calmer, no-glow alternative from an earlier
session, used across Live ML Apps / Skills / News / Timeline / Contact. Asked
the user directly whether to extend glow everywhere, to just Live ML Apps, or
leave it — user chose everywhere. Added the same `--acc-glow` radial `::after`
pattern generically to `.subtle-card`, wired per-item accent colors into
ProjectCard/Skills/Timeline/NewsSection, and used `color-mix(in srgb, var(--accent)
10%, transparent)` for Contact's links, which have no per-item color of their
own. Verified real `:hover` activation on both mechanisms via Playwright.
Commit `3aeee29`.

## 4. Root-cause theme bug: every tool page ignored the site's light/dark toggle

User showed a light-themed homepage next to a Feature Engineering tool page
stuck in dark mode with a "ghosted double text" / washed-out upload-box look,
plus a janky 3D-tilt dropzone hover inconsistent with other cards. Spawned a
research-only background agent (worktree-isolated) rather than guessing — it
found the real root cause: `ConstellationBackground.tsx` injected
`<style>{'body { background: #060d1a; }'}</style>` — same specificity as
`globals.css`'s theme-aware `body { background: var(--bg) }` but loading later
in the DOM, so it always won. Used on **25** tool pages. The "ghosting" wasn't a
render/hydration bug at all — text and cards were already correctly resolving
light-theme colors, just sitting on a background stuck in dark mode.

Fixed the root cause (`var(--bg)` instead of the literal hex), then — after the
user explicitly chose the larger scope over a two-file minimal fix — swept 10
more flagged tool pages (`ensemble`, `shap`, `automl`+`error.tsx`, `drift`,
`optuna`, `preprocessing`, `pipeline-builder`, `pipeline-cinema`,
`realtime-analytics/AnalyticsCharts.tsx`) for their OWN hardcoded dark-only
colors — sticky header backgrounds/borders (`rgba(6,13,26,0.92)` →
`var(--bg-nav)`), dividers, disabled-button/input backgrounds, chart panel
fills and gridlines (`#0a0f1e`/`#1f2937`/`rgba(255,255,255,0.0x)` →
`var(--bg-card)`/`var(--border)`/`var(--border2)`) — replaced each with the
matching theme token. Also replaced Feature Engineering's CSV dropzone, which
was the ONLY upload-style card using a bespoke per-frame cursor-tracking 3D
`MouseTiltCard` (used elsewhere in the codebase, but not for any other upload
card), with the standard `.subtle-card` hover to match the rest of the site.
Verified body/header backgrounds and dropzone hover resolve correctly in both
themes across 4 different pages via Playwright (`localStorage.theme` toggle +
real DOM measurement, since screenshots render blank on this machine). Commit
`2d56a64`.

## 5. Step-progress header rollout across all 7 pipeline-stage pages

User compared two more screenshots (Feature Engineering vs. Data Preprocessing
headers) and asked "do you see any difference?" — the real answer: only
Preprocessing has a live "1 Upload — 2 Configure — 3 Processing — 4 Results"
stepper; every other pipeline page (Feature Engineering, Feature Selection,
AutoML, Optuna, SHAP, Ensemble) shows a static "Step N" badge with no live
progress. Investigated file-by-file (explicitly asked by the user to keep going
rather than batch-assume) and found the real shape was far from uniform:
- Preprocessing / Feature Engineering: 4-step state (`upload/configure/
  processing/results`) already in `page.tsx`.
- AutoML: 4-step state (`upload/config/training/results`) — different names —
  living inside the `AutoMLModal` child component, not the page.
- Optuna / Ensemble / SHAP: 3-step state (`1|2|3`, no separate "processing"
  step), each ALREADY had its own inline step bar rendered inside the runner
  BODY (not the header) — discovered via direct file reads, not assumed.
- Feature Selection: no step concept at all, anywhere.

Presented this real complexity to the user before proceeding (three options:
full rollout, the 2 easy pages only, or just fix colors) — user chose full
rollout. Generalized `StepIndicator` (moved from `PreprocessingPanels/` to a
shared top-level component) to take plain `labels: string[]` + `currentIndex`
instead of Preprocessing's own `Step` type, and fixed its own hardcoded
`rgba(255,255,255,0.0x)` colors in the same pass. For AutoML/Optuna/Ensemble/
SHAP, added an `onStepChange` callback prop so the child component's internal
step state could be mirrored into the page-level header state, then DELETED the
now-redundant inline step bars (including the `OptunaStepBar` component, now
fully unused) to avoid showing progress twice. For Feature Selection, derived a
step from existing state (`!hasFile → 1`, `hasFile && !result → 2`, `result → 3`)
rather than adding new state. Verified live via Playwright: step labels render
correctly on all 7 pages, and — since a real training run needs a backend not
running locally — specifically verified Feature Selection's DERIVED step by
dispatching a real synthetic `File` + `change` event at the hidden file input
(no backend needed, pure client-side CSV parse) and confirmed the header
flipped from "Upload" to "Configure" live. Commit `ef7ab18`.

---

## Pending / backlog state at end of session

- No open items from this session — all five threads (card redesign, flip-card
  sizing, hover-glow consistency, theme root-cause + 10-page sweep, step
  indicator rollout) were fully built, verified live, committed, and pushed.
- Broader pending-master-list items untouched this session (deepfake detection,
  steganography detection, keystroke inference, CAPTCHA-solving research,
  remaining real-world adversarial-ML use cases) — not discussed today.
