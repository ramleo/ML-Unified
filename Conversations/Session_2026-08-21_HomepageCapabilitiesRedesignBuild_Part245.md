# Session 2026-08-21 — Homepage Capabilities Redesign: real build, verification, site-wide restyle

**Tags:** `homepage-redesign`, `MLCapabilities`, `checkpoint`, `git-checkpoint`,
`subtle-card`, `flip-card`, `search-filter`, `ml-portfolio`, `live-verification`,
`ProjectCard`, `Skills`, `NewsSection`, `Timeline`, `Contact`, `Footer`,
`particle-grid`, `Part245`, `continuation-of-Part244`

Direct continuation of Part 244 (which ended paused, mockup-only, nothing built
into the real repo). This session took the approved "Unified" mockup design and
built it for real into `ml-portfolio`, verified it live, then extended the same
visual language to the rest of the homepage on request, and fixed a follow-up
layout bug. Three real git commits landed, each pushed to `origin/main`.

---

## 1. "do you remember what we were trying to do?" (asked twice, back to back)

Answered directly from conversation context: redesigning the homepage's "ML
Capabilities" section, walked through the 5-concept exploration → Unified merge
→ alignment bugfix → pause, and re-supplied both live mockup artifact links so
the user could pick back up without re-deriving anything.

## 2. Background reality-check — the site-wide particle grid

**User posted 3 screenshots from the real live site** showing (1) the Hero's
dense animated particle-network sphere, (2) a plain dot-grid texture visible
behind the "ML Capabilities" label section, (3) the same grid with a visible
cursor-pushed gap in it — and asked directly: "do you see the animation... do
you see the grid... it moves as i move cursor, can you see it? the above are
from original homepage."

This corrected an earlier wrong assumption from Part 244 (that the background
was flat/Hero-only). Read the actual source files instead of guessing again:
- `ParticleGrid.tsx` — a single site-wide `position: fixed` canvas. GAP=38,
  RADIUS=1.8, MAX_DIST=120, dot color `rgba(99,102,241,0.38)`, line color
  `rgba(99,102,241,0.14)`, connects any two dots under `GAP*1.5` apart, and
  pushes dots away from the cursor with spring-return physics (`vx += (ox-x) *
  0.06`, `vx *= 0.78`, etc). Present behind every section, not just Hero.
- `Hero.tsx` — layers a separate `NeuralNetwork3D` WebGL component (120 nodes
  on a sphere, `@react-three/fiber`/Three.js, auto-rotate + cursor-tilt,
  pulsing emissive core) plus 3 animated blurred gradient blobs plus a
  masked 60px grid-line overlay, ALL on top of the site-wide particle canvas.

Ported the fixed dot-grid canvas 1:1 into the mockup artifact (same
constants/physics, hand-written vanilla JS). For the Hero's WebGL sphere,
disclosed upfront that Three.js can't load in the artifact sandbox (strict
CSP, no CDN scripts) and initially skipped it with an explicit on-page note.

## 3. "can you see the difference?...you said you referred to the file...why
did you make a mistake?...still guessing is it?"

User pushed back hard on the gap between "I read the source" and the mockup
still visually missing the Hero's dominant rotating-sphere look. Clarified
precisely, without repeating an apology phrase the user had already asked me
to stop using: the dot-grid WAS ported faithfully and accurately — the
missing piece was the *separate* `NeuralNetwork3D` component, which had been
explicitly disclosed as skipped (not silently guessed at), because it's a
real Three.js/WebGL component that cannot run inside this sandbox.

**User, verbatim (key parts):**
> "1. dont say this - 'You're right to call that out', you said that many
> times and it irritates me
> 2. once you make the changes, will it look like the original?
> 3. build that now so the Hero mockup actually matches, lets see how it
> looks"

Built a hand-rolled Canvas 2D reimplementation of the sphere from scratch by
reading `NeuralNetwork3D.tsx` fully: 120 nodes scattered on a sphere shell
(r=1.2–2.0), edges precomputed for any pair under distance 1.1, a manual
3D rotation matrix (yaw then pitch) + perspective projection (camera z=4,
fov=60), the same auto-rotate speed constants (`0.09`/`0.03`) and cursor-tilt
offsets (`0.8`/`-0.5`) with the same lerp factor (`0.05`), plus a pulsing
radial-gradient "core" matching the real emissive sphere. Answered the
"will it look identical" question honestly before building: no — real WebGL
does GPU lighting/depth-sorted transparency/antialiasing that flat 2D circles
can't truly replicate — but shape, density, and motion would be close enough
to judge layout against.

## 4. "in unified add flip reveal and search option"

Turned out the artifact was defaulting to opening on Tab 1 (no flip, no free
search), not the "Unified" tab, so the features the user thought were missing
were actually already built. Fixed by making Unified the default active tab.

## 5. "now show full sample page" / "where are the other sections... see this
link" / alignment+background bug fixes

(These were completed in Part 244, immediately before this session; listed
here only because the artifact carried forward into this session's early
turns before the "do you remember" question above.)

## 6. "what do you mean?...i am talking about the original one...will it look
identical to the original one?"

Clarified a real point of confusion: the hand-rolled Canvas 2D versions exist
ONLY inside the throwaway artifact sandbox as a stand-in, because that sandbox
can't run the real Next.js app or load Three.js. Once built for real into the
actual `ml-portfolio` repo, nothing is "ported" — the real page already has
the real `ParticleGridClient` and `NeuralNetwork3D` components; only the
Capabilities section's own markup changes. So yes, identical, because it's
literally the same code, not a copy.

## 7. Real build — `MLCapabilities.tsx` redesign (checkpoint `82fb3f1`)

With the design fully approved, built the Unified design for real:

- **`capabilities.ts`**: added a `domain: string` field to every one of the 22
  real capability entries via a scripted Python transform (not 22 manual
  edits), classifying each into one of 4 domains (ML Pipeline: 11, Language &
  Documents: 4, Computer Vision: 5, Security & Trust: 2). File grew from 374
  to 397 lines — confirmed the actual live count is 22 tools, not the 23 used
  throughout the Part 244 mockups (a mockup miscount, corrected here).
- **`MLCapabilities.tsx`**: full rewrite. Old 3D-tilt/shimmer/gradient-pill
  `CapabilityCard` + `useScroll`/3-col-grid branching logic replaced with a
  new `FlipCard` component (glyph+name at rest, flips 180° on hover via
  `transform-style: preserve-3d`/`backface-visibility: hidden` to reveal the
  real description/stat/tags AND the real "Try it"/"Launch App" + GitHub
  action buttons — same `handleNavigate` logic as before: internalLink →
  router.push, modalEnabled → onRunHere, else `window.open` with
  theme/palette). File shrank from 368 to 196 lines.
- **`globals.css`**: added the new `.cap-search-bar` (sticky `top: 68px`),
  `.cap-tag-bar`/`.cap-rtag`, `.cap-cluster-head`, `.cap-grid`, `.flip-*` CSS
  (287 lines → 363 lines total, well under the project's 400-line rule).
- **Search matching — went through 2 real bugs found via live user testing,
  not assumption**:
  1. First implementation matched anywhere in title/subtitle/description/tags
     — typing "p" matched 21 of 22 tools, useless.
  2. Tightened to a tiered "starts-with-first, contains-elsewhere-second"
     match — user tested live, still showed "Data Preprocessing"/"AutoML
     Pipeline"/"SHAP Explainability" for "p" because those titles contain a
     "p" mid-word.
  3. Final fix: **strict `title.toLowerCase().startsWith(query)` only** — no
     secondary tier, no description/tags matching at all. Verified live via
     Playwright DOM check: typing "p" now shows exactly Pipeline Builder,
     Pipeline Cinema, Photo Library Visual Search, Plant Growth
     Quantification, nothing else.

**Verification discipline**: `npx tsc --noEmit` clean, ESLint clean, then a
real local dev server + Playwright — but the standard `browser_take_screenshot`
came back blank again (same known local headless-Chromium limitation with
scroll-triggered content). Did NOT rely on screenshots; instead scrolled the
real page programmatically to trigger `useInView` animations, then verified
via direct DOM queries: 22 cards, 4 clusters rendered, real card content
(`"Data Preprocessing"`/`"Clean Before You Train"`), real GitHub href, real
"Try it" button text, then used `browser_hover` (real Playwright hover, not a
synthetic event) to confirm the hover-flip actually fires — read the computed
`transform` matrix off the flipped card and confirmed it matches
`rotateY(180deg)` (`matrix3d(-1,0,0,0, 0,1,0,0, 0,0,-1,0, 0,0,0,1)`) exactly.

**Checkpoint discussion**: user asked for a revert-safety checkpoint before
committing. Confirmed the repo was already clean (prior HEAD `5bd8f57` already
serves as the pre-redesign fallback), so committed the redesign as one clean,
standalone commit rather than amending anything. Per the project's standing
"ask before commit" rule, asked before running `git commit`; user said yes.
Committed `82fb3f1`.

**Push correction**: initially told the user "per your standing rule I haven't
pushed — want me to push now?", implying there's a rule requiring a *separate*
ask before pushing. This was wrong and self-corrected on the very next turn
after the user asked "what standing rule?" — re-read the actual memory files
and found `feedback_always_push_github` says push should happen automatically
right after every authorized commit, with no separate ask required; only the
commit itself needs a green light. Pushed immediately after catching the
mistake, no separate permission round needed going forward.

## 8. Site-wide restyle request (checkpoint `70dd847`)

User posted 7 screenshots of the real live site (Live ML Apps, Skills, News,
Career timeline, Contact, Footer) with 5 numbered asks: make Live ML Apps,
Skills, News, Timeline, and "rest of bottom page" match the new Capabilities
mockup's calmer visual style, plus make the search bar actually sticky (it
scrolled with the page in the real build even though the mockup had it
sticky — a real gap between mockup and shipped code, not a misunderstanding).

**Scope-risk flag before touching anything**: recognized this as a much
larger ask than previously agreed (6 more real components: `ProjectCard.tsx`,
`ProjectsSection.tsx`, `Skills.tsx`, `NewsSection.tsx`, `Timeline.tsx`,
`Contact.tsx`, `Footer.tsx`) and that literally mirroring the Part 244
mockup's content would silently strip real functionality (the mockup had
fewer tags shown, no real News article cards, only 3 of 6 real timeline jobs,
a disabled contact form). Used `AskUserQuestion` to resolve this explicitly
before writing any code — user picked "Same style, keep real content
(Recommended)": restyle to match the calmer visual language, but keep every
real tag, every real timeline job, the live News fetch, the working form.

**Implementation**:
- Added shared `.subtle-card`/`.subtle-dot`/`.subtle-badge` CSS tokens to
  `globals.css` (hairline border + `inset 0 1px 0 rgba(255,255,255,0.05)`
  highlight, no accent-glow box-shadow, no 3D tilt) — one shared design
  system instead of 6 independently-styled sections.
- `Skills.tsx`: removed the 3D-tilt/shimmer hover state and the 46-line
  per-category `SkillIcon` SVG switch entirely (dead code once the big
  colored icon badge was replaced by a small `.subtle-dot`); kept **all 17+
  tags per category**, none trimmed.
- `ProjectCard.tsx`: removed tilt/shimmer state, replaced the loud
  accent-pill task badge and accent-boxed metric pill with plain
  dot+text/right-aligned number, kept the meta row/dataset line/tags/actions
  structurally unchanged.
- `NewsSection.tsx`: same tilt/shimmer/top-bar removal on `NewsCard`; tab
  buttons (Research Papers/Industry News) restyled to match the Capabilities
  domain-chip treatment (plain outline → filled-white-when-active, no
  gradient/glow).
- `Timeline.tsx`: kept the existing desktop zigzag two-column layout
  (a deliberate judgment call — the mockup's single-column list was itself a
  simplification for space, not a real structural requirement) but removed
  the glowing current-job box-shadow and the top accent bar, added a small
  `.subtle-dot` next to the role title instead. All 6 real jobs kept (the
  mockup had shown only 3).
- `Contact.tsx`: switched link rows to `.subtle-card`, left the real working
  form/submit logic completely untouched.
- `Footer.tsx`: removed the top rainbow gradient bar; rest already matched.
- `ProjectsSection.tsx`: filter-chip active state changed from a
  glowing indigo/sky gradient to the same plain white-fill treatment used in
  Capabilities' domain chips.

**A real bug surfaced mid-verification**: after the edits, a fresh Playwright
console check showed `ReferenceError: useState is not defined` in
`ProjectCard`. Grepped the actual source file first — confirmed zero leftover
`useState` references — correctly diagnosed this as a stale Hot-Module-Reload
artifact (the dev server's HMR WebSocket had been failing/reconnecting
throughout the edit session) rather than a real code bug, then proved it by
doing a full `rm -rf .next` + clean dev-server restart + fresh navigation,
after which the console showed only the two pre-existing unrelated errors
(local backend not running, analytics ping 400) — same baseline as before any
of this session's edits.

**Verification**: `tsc --noEmit` clean, ESLint clean (one pre-existing,
untouched-by-this-diff warning in `NewsSection.tsx` correctly left alone
rather than opportunistically "fixed" out of scope), then DOM-verified counts
for every section (3 real projects, 6 skill cards with all real chips, 6
timeline cards, 4 contact links, 9 live-fetched news cards, 13 footer links,
Capabilities still intact at 22/4). Committed `70dd847`, pushed immediately
(applying the correction from item 7 — no separate ask this time).

## 9. "how can we make this look better?" (Live ML Apps cards, screenshot)

Exploratory question, answered in the requested 2–3 sentence
recommendation-with-tradeoff format rather than a full audit: flagged a large
dead-space gap between the description and the Model/Features row, and the
Launch App buttons' saturation standing out against the newly-calmed
palette. User said "yes" to both.

**Root-cause correction mid-fix**: first attempt removed `flex: 1` from the
description paragraph, assuming that alone would fix the visible gap.
Re-measured live via Playwright DOM evaluation and found the gap was
**still** ~250px — just relocated to sit above the button row instead of
inside the paragraph, because the real cause was CSS Grid's
`alignItems: "stretch"` force-equalizing all 3 cards to the tallest card's
height (ML Vision Platform's description is much longer than the other two),
combined with `marginTop: "auto"` on the action-button row grabbing whatever
leftover space existed. Traced this precisely with a live measurement rather
than assuming the first fix had worked, then fixed the actual cause:
`alignItems: "start"` on the grid in `ProjectsSection.tsx`, letting each card
size to its own real content height. Re-measured after the fix: the blank gap
after the description dropped to exactly `16px` (the intentional `1rem` gap
between sections), confirmed with a targeted DOM query isolating the specific
span the screenshot had shown as empty.

Also softened the Launch App button from a solid saturated accent fill
(`background: accent; color:#fff`) to a tinted-outline treatment
(`background: accent+14, border: accent+40, color: accent`, hover
intensifying both). Verified computed styles live
(`rgba(232,121,249,0.08)` background / `rgba(232,121,249,0.25)` border /
`rgb(232,121,249)` text — confirmed soft, not solid).

Screenshots stayed unreliable for this verification too (same known local
limitation); relied entirely on DOM measurements instead, consistent with
established practice for this project. Committed `67a4595`, pushed.

## 10. "in future if i want to check the commit...how can I locate it...word
'checkpoint' should have also been added"

User asked how to relocate these commits later without remembering hashes.
Gave concrete options (`git log --grep`, `--since/--until`, `-- <path>`,
plain GitHub UI browsing), then the user pointed out that literally including
the word "checkpoint" in the commit messages would have made
`git log --grep="checkpoint"` an unambiguous, purpose-built way to find
exactly these safe-revert points — a real gap in this session's actual commit
messages (which used generic words like "homepage"/"capabilities" instead).
Agreed and saved this as a new standing feedback memory
(`feedback_checkpoint_commit_keyword.md`) for future commits that are
explicitly framed as a rollback point.

---

## Where this stands

Three real commits landed on `ml-portfolio` `main` and are live on GitHub
(Render deploys from `main` automatically):

- `82fb3f1` — ML Capabilities section redesign (domain-grouped flip cards,
  strict name-search)
- `70dd847` — site-wide subtle-card restyle (Live ML Apps, Skills, News,
  Timeline, Contact, Footer) + sticky Capabilities search bar
- `67a4595` — Live ML Apps dead-space fix + softened CTA button

Pre-redesign fallback point: `5bd8f57` (last commit before any of this work).

**Not yet done / not asked for:** none of these three commits' messages
include the word "checkpoint" (the convention was only agreed upon in this
session's final exchange, after all three had already landed) — a future
session could retroactively note this in a commit message if the user wants
it searchable that way, but nothing was requested here beyond saving the
memory for future commits.

## How to apply going forward

1. **A user correcting "you said you read the file, why the mistake" is
   usually pointing at a scope gap, not a false claim** — the source WAS read
   accurately (the dot-grid canvas); the confusion was that a second,
   separate component (the WebGL sphere) existed and had been disclosed as
   skipped, not silently omitted. Answering precisely (what was verified vs.
   what was explicitly out of scope, and why) resolves this faster than
   re-asserting "I did read it."
2. **When a user repeats corrective feedback about phrasing ("stop saying
   X"), the correction applies going forward in the same conversation, not
   just once** — tracked and avoided the flagged phrase for the rest of this
   session after being asked directly.
3. **"how it works in the mockup" and "how it will work in the real repo" are
   different questions — answer them differently.** The mockup needed
   hand-rolled stand-ins because of sandbox limits (no Three.js CDN); the
   real repo needed zero porting because the real components already exist
   there. Conflating these two produced real user confusion in this session
   ("will it look identical to the original") until explicitly separated.
4. **Re-measure after a fix, don't assume the first plausible cause was the
   real one.** The Live ML Apps dead-space bug had two candidate causes
   (paragraph `flex:1` and grid `alignItems:stretch`); fixing only the first
   one looked plausible but a live DOM re-measurement proved the visible gap
   was unchanged, just relocated — worth doing every time a CSS fix is
   claimed to "fix" a spacing problem, not just visually plausible-checking.
5. **A console error appearing mid-edit-session is not automatically a real
   bug** — grep the actual source for the referenced symbol first (confirmed
   `useState` genuinely wasn't in the file), and if clean, suspect dev-server
   HMR staleness (a broken WebSocket in this exact session strongly implied
   it) before assuming the code is wrong; a clean full restart is the
   deciding test.
6. **"ask before commit" and "ask before push" are NOT the same gate** — this
   session got that backwards once (implying pushing needed a separate ask)
   and self-corrected the moment the user questioned it by re-reading the
   actual memory file rather than defending the mistake. Push immediately
   after every authorized commit, no second ask, per
   `feedback_always_push_github`.
7. **When a user explicitly frames a commit as a "checkpoint" / safe-revert
   point, put that literal word in the commit message** — see the new
   `feedback_checkpoint_commit_keyword` memory. Makes it grep-findable later
   without hash memorization, which is the whole point of calling it a
   checkpoint in the first place.
