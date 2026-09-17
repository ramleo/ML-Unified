# Part 288 — The guidelines got finished, and the clips began

Continues [Part 287](Session_2026-09-16_TestsGuardsAndGuidelines_Part287.md).

2026-09-17 — the day scheduled in `WEBSITE_GUIDELINES.md` for the measurement-driven
tail. This session ran that plan to completion (a11y touch targets + contrast,
Core Web Vitals, heading structure, and a decision on `next/image`), then added a
two-button back nav, closed the frontend's QA gap with vitest + CI, and started on
the demo-clip backlog. All of ml-portfolio; nothing touched the Spaces.

The spine of the day: **measure before you fix — the audit kept correcting the
plan's guesses**, and a fix that changes what people see is the user's call, not
mine.

---

## 1. Accessibility — the audit disagreed with the plan (helpfully)

Ran Playwright + axe on the live site before touching anything. The plan's guesses
were off, in our favour:

- **Touch targets (WCAG 2.5.8).** The predicted hotspot (`ToolsAIChat` controls)
  wasn't one — those don't mount on the landing state. The footer nav links looked
  small (20px) but **pass via the spacing exception** (29px centre-to-centre ≥ 24).
  The real sub-24px controls were the shared back button (18–20px, on all 53 tool
  pages) and a few home controls — fixed to ≥24px.
- **Contrast (WCAG 1.4.3) — 25 violations per theme, but nearly all one token.**
  `--text3` (`#64748b`) on the dark ground was 4.01:1. Retuned dark→`#7e8ca4`,
  light→`#4d5a6d`; added a `--link` token (= `accent-from`, every palette stop
  ≥4.5:1) for inline links so `--accent` could stay on buttons. Result: **0 axe
  violations on both themes.**

The light theme hid a second cause: text failed **over the constellation lines**
(blue on white composited to a mid-grey behind glyphs). Proven by hiding the canvas
→ 0 violations. `a8090b1`.

## 2. The constellation tradeoff — the user's call, twice

Quietening the light-mode constellation to pass contrast is a visible design
change, so it went to the user, not into a silent commit. It took two rounds of
their eyeball feedback:

- First pass over-quietened it ("too faint"). The tension is real and inherent: to
  be *visible* on white, lines must be dark; the darker they are, the more they hurt
  text on top. The math showed lines alone would have to drop to ~8% opacity —
  invisible — so I split the work across **two knobs**: fainter lines *and* darker
  muted text. `9006d4f`.
- Still too faint. The key insight: **the dots, not the lines, are the AA
  constraint's escape hatch** — a dot is a small point axe rarely samples as a
  text background, while the dark inline links on the home page cap how bright the
  *lines* can go. So dots went bold (0.30→0.50, ×1.4 size), lines stayed modest.
  Verified 0 violations across 16 animated samples. `fd21981`. The user confirmed
  the live look.

## 3. Two-button back nav (Home + area), and three bugs it surfaced

Tool pages had a single "← Area" button and no one-click path home. Built a shared
`<ToolBackNav>` (Home → `/` plus the tool's area) and swapped it into all 53 pages
(codemod for the 48 uniform ones, hand-edits for the bespoke headers). Bugs found
in the process:

- **pipeline-cinema's "Home" went to ML Pipeline, not `/`** — the exact bug the
  user had spotted. Now Home → `/`, plus ML Pipeline, plus the Pipeline Builder
  cross-link.
- **feature-engineering / feature-selection were mis-keyed** in the area map
  (capability ids `featureeng`/`featureselect` vs the route slugs), so they fell
  back to a lone "Home". Added the route-slug keys.
- **rag-analytics** kept its useful parent link (Home + Multimodal RAG).

Verified by an SSR sweep: every tool page ≥2 correct links, all four area pages
200. Net −339 lines (one component replaced ~53 copies). `6bd64b0`.

## 4. Core Web Vitals — home was the only outlier

Lighthouse (mobile, live) on home + three heavy pages. The **tool pages already
score 98–100** (LCP ~2.3s, TBT 0). **Home was alone at 66** (LCP 4.2s, TBT 860ms).
The LCP element is *text*, 85% render-delayed — every home section is a
framer-motion client component hydrating at once. Fix: defer the chatbot + the
three below-fold sections via `dynamic ssr:false` wrappers, keeping the hero + tool
grid server-rendered.

Result (3-run median, live): **perf 66→100, LCP 4.2s→1.6s, TBT 860ms→10ms, CLS
~0.** The planned "take framer-motion off the hero" step proved unnecessary. The
first post-deploy Lighthouse run was a cold-cache 81 outlier — the median of warm
runs is the honest number. `f3a6426`.

## 5. `next/image` — closed as not-needed, by evidence

Audited all 65 `<img>` across 37 files. They are all either **dynamic runtime
images** (blob/data-URI/canvas — `next/image` can't optimize these; it passes
data/blob URIs through) or **already optimized** (the one static case, `ToolCard`'s
`/thumbs/*.webp`, is already lazy + async + explicit width/height + webp). The plan
assumed 28 migratable images; there are effectively none. Migrating would add Vercel
image-opt requests for no gain. Closed as not-needed, no code change. `cc4ba52`.

## 6. QA gap closed — vitest + CI

Backend QA was solid (22 pytest files + CI). The **frontend had zero unit tests** —
only Playwright E2E. Added vitest and **22 unit tests** for the pure-logic lib the
guidelines name (`runOutcomes`, `chatLimits`, `aiToolsLimits`). One test failed on
first run — a *good* failure: my 8000-char input tripped the per-message cap before
the total-chars trim it meant to exercise; the code was right, the test's assumption
wrong. `0e67e4d`. Then wired a `unit` CI job. `2d474eb`.

## 7. Dead-code cleanup, driven by the compiler

The nav swap left `handleBack` + orphaned imports dead on ~48 pages. Rather than
guess the cascade, ran `tsc --noUnusedLocals` to get the authoritative list and
removed only what it flagged, iterating until clean — 279 declarations, **net −195
lines**, tsc + build green. `4c828cb`.

## 8. E6 wasn't the handbook — it's the demo clips

"Handbook clips at 25 of 50" reads as the printed handbook, and I first "verified"
it done: 51/51 tools have real chapters. The user corrected me — **"clip" means the
demo *video* recordings**. Real state: 25 of 51 tools have a `.webm`; 26 have
neither a clip nor a script. Understood the pipeline (`record-demo.mjs` replays
`src/data/demos/*.json` through **visible** Chrome — headless films WebGL as a blank
box — with narration + ffmpeg), which means **I can't record here**; my part is
authoring each tool's demo script (JSON + `data-wt` hooks + manifest entry), the
user records + eyeballs start/end on their Mac. Started, one at a time:
- `exploratory-data-analysis` — already had hooks, so JSON + manifest only. `6a418a9`.
- `ai-code-detector` — added 6 hooks + script. `13b764e`.

24 tools remain (each needs hooks added first).

---

## Where I was wrong, and corrected

- Said **ml-portfolio has no CI workflow — twice.** It has a thorough one
  (secret scans, file-length, handbook, build+typecheck, Playwright e2e). I added
  the missing `unit` job to it.
- Suggested **password-audit** as a missing-clip candidate; it's already done and in
  the manifest. Reading `index.ts` caught it before I wrote a duplicate.
- "Verified" **E6 done** on the wrong reading (handbook, not clips).

The pattern in all three: I answered from a plausible inference before checking the
authoritative source (the CI file, the manifest, the user's intent). Each was caught
by reading the real thing — or by the user.

---

## Commits

| Repo | Commit | What |
|---|---|---|
| ml-portfolio | `a8090b1` | a11y: contrast (0 both themes) + touch targets ≥24px |
| ML-Unified | `b5a88e0` | tracker: touch targets + contrast |
| ml-portfolio | `9006d4f` | constellation: fainter lines + darker text (round 1) |
| ml-portfolio | `fd21981` | constellation: bolder/larger dots (round 2) |
| ml-portfolio | `6bd64b0` | two-button back nav + 3 nav bugs |
| ml-portfolio | `f3a6426` | CWV: defer chatbot + below-fold (home 66→100) |
| ML-Unified | `f4a98a7` | tracker: Core Web Vitals |
| ml-portfolio | `0b0dc1c` | a11y: heading hierarchy fixes |
| ML-Unified | `a99524d` | tracker: heading structure |
| ML-Unified | `cc4ba52` | tracker: next/image closed as not-needed |
| ml-portfolio | `4c828cb` | remove dead nav code (tsc-driven, −195 lines) |
| ml-portfolio | `0e67e4d` | vitest + 22 unit tests |
| ml-portfolio | `2d474eb` | CI: unit-test job |
| ml-portfolio | `6a418a9` | demo script: exploratory-data-analysis |
| ml-portfolio | `13b764e` | demo: ai-code-detector (hooks + script) |

WEBSITE_GUIDELINES plan is complete (bar key rotation, the user's). Demo clips are
the live backlog: 24 tools left, one at a time.

---

## Lessons

- **Measure before you fix; the audit will correct your plan.** Touch targets
  weren't where predicted, contrast was one token plus a canvas interaction, home
  was the only CWV outlier, `next/image` had nothing to migrate, and E6 wasn't the
  handbook. Every one of those was a guess the evidence overturned.
- **A visible tradeoff is the user's call.** The constellation faint↔visible tension
  took two rounds of their eyeball; the right move was to surface it, not silently
  pick — and to solve it with two knobs instead of pushing one to an extreme.
- **Let the compiler do the dangerous edits.** `tsc --noUnusedLocals` turned a
  48-file dead-code cascade into a precise, safe list.
- **Read the authoritative source before answering.** Three wrong claims this
  session all came from inferring instead of opening the CI file / the manifest /
  asking what "clip" meant.
- **A test that fails on its first run is doing its job** — believe it before the
  code.
