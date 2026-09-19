# Part 293 — From a tool card to a platform world (Testwright + Text-to-SQL)

Continues [Part 292](Session_2026-09-19_TwoToolsAndTheRegistrationsIForgot_Part292.md).

2026-09-19. Built the QA test-automation tool — then rebuilt it, twice, because
the first two attempts were the wrong *shape*. The through-line: **match the tier
to the thing.** A full app is a Platform (its own world), not a tool card; and a
user guide is a real guide, not a marketing blurb. The user pushed hard on both,
and was right both times.

---

## 1. Phase 1, built the small way first (and it was too small)

Shipped the QA test author as planned: backend `POST /qa-test-author/generate`
(free cohere→mistral cascade, budget-capped) and a client tool at
`/tools/qa-test-author` in a **new "Developer Tools" area**. HF-deployed and
verified end-to-end live (production UI generated valid Playwright TS from
cohere). Commits: ML-Unified `8af0689`, ml-portfolio `b50b080`.

Then the correction: *"why the name 'Developer Tools'? why a card inside dev
tools? … QA Automation is a website in itself, treat it like a website … search
online, study the design, study our website, then plan the blueprint."*

The miss: I put a whole product in the wrong tier. testRigor and Katalon each
build an entire site around this. Our own site already has the right tier —
**Deployed Platforms** (full apps, `registry.json`) sits above the 50 tool cards
— and I'd used the tool tier.

---

## 2. Studied the references and our own IA, then planned a world

Went through **testRigor** and **Katalon** properly (IA + design, not just a
feature list): both lead with the plain-English→test translation, a
how-it-works, a capability grid, and a "one platform, N modules that hand off"
frame. Katalon's four modules (Studio→TestOps→TestCloud→TrueTest) map almost
exactly onto our phased plan.

Decision (mine, per "you suggest"): **QA becomes the 4th Platform — a native
`/qa` world (Testwright)** with its own in-world sub-nav, not a new tool area and
not a 7th global nav link. Delivered a **design mockup artifact** first
("Testwright"), got the name and the teal→cyan signature approved, plus a hard
constraint: **make future microservice extraction hassle-free.**

---

## 3. Built the Testwright world — microservice-ready

**One coupling seam on each side:**
- Backend: `services/ml-api/routers/qa/` package; every route reaches shared
  infra (LLM `complete`, key resolution, budget, limiter) **only** through
  `routers/qa/deps.py`. Unified `/qa/*` prefix (`/qa/author/generate`). Extract =
  copy the folder + reimplement `deps.py`. ML-Unified `5e07563`, HF-verified.
- Frontend: all QA calls go through `src/app/qa/lib/qaClient.ts` against a single
  `QA_API` (`NEXT_PUBLIC_QA_API_URL ?? ML_UNIFIED_API`).

The `/qa` world: `WorldShell` (constellation + navbar + in-world sub-nav),
landing (hero + four-stage lifecycle + how-it-works + honest scope), the Author
tool relocated to `/qa/author`, and Run/Discover/Heal as honest roadmap pages.
Homepage gained a native platform card (`ProjectCard` now renders "Enter" →
internal route vs "Launch App" → external HF app). The premature Developer Tools
area was folded in and removed. ml-portfolio `98be844`; plan doc `0752bf6`.

---

## 4. Make it look like the Toolkit, and make it five

Feedback: the Platforms section should read like **The Toolkit** area grid, and
it should show **5**. The 5th was **Text-to-SQL** — a full app on its own
deployed `ml-sql` Space that had only ever been a tool card.

Restyled the platforms into the toolkit's `.dom-card` bento tiles (new
`PlatformTile`), dropped the tag-filter chips, and added Text-to-SQL to
`registry.json`. ml-portfolio `6aedd3c`.

---

## 5. The polish round that found real bugs

Four sharp notes, all fair:
- **Inconsistent verb** — tiles mixed "Enter"/"Launch". Now all say "Enter".
- **Name overlapped the texture behind it** — *"is it deliberate or bad work?"*
  It was the shared toolkit design: caption pinned to the bottom sat inside the
  texture's fade. Fixed properly — texture now **fills** the tile and the caption
  sits on its own **scrim** (`.dom-cap::before` → `--bg-card`), taller rows use
  the empty space. Fixes both the platforms and the toolkit grids.
- **"Make Text-to-SQL the same as Testwright"** → built a full **`/sql` world**
  mirroring `/qa` (hero + English→SQL panel + four live capabilities + how +
  scope), reusing extracted shared chrome (`WorldShell`, `WorldNav`,
  `WorldUserGuideModal`).
- **Add guide + chat to the Testwright landing.**
ml-portfolio `ea5d852`.

Then the last, sharpest round:
- **The Testwright "guide" was a blurb, not a guide** — *"are you doing a favor
  … you added a stupid document."* Rewrote it into a real user guide:
  step-by-step Author usage, reading/running the output, resilient locators
  explained, FAQ, honest limits.
- **Text-to-SQL was double-listed** — still a tool card in Language & Documents
  *and* a platform, and its tool page breadcrumbed to "Language & Documents".
  Removed it from the toolkit entirely (card + area + metadata), added a
  `PLATFORM_OF` map so `/tools/text-to-sql` breadcrumbs to its platform
  (`/sql`), and reused the tool's **own comprehensive guide** for the platform.
ml-portfolio `f3a7de0`.

---

## Commits

| Repo | Commit | What |
|---|---|---|
| ML-Unified | `8af0689` | qa-test-author generate endpoint (first attempt) |
| ml-portfolio | `b50b080` | qa-test-author tool + Developer Tools area (first attempt) |
| ML-Unified | `5e07563` | refactor to microservice-ready `routers/qa/` package |
| ml-portfolio | `98be844` | Testwright `/qa` world (4th platform) |
| ML-Unified | `0752bf6` | QA plan restructured around the platform + seams |
| ml-portfolio | `6aedd3c` | Toolkit-style bento tiles + Text-to-SQL as 5th platform |
| ml-portfolio | `ea5d852` | tile overlap fix, consistent verb, `/sql` world, guide+chat |
| ml-portfolio | `f3a7de0` | Text-to-SQL fully leaves toolkit; comprehensive guides |

---

## Lessons

- **Match the tier to the thing.** A full app with its own backend is a
  Platform (its own world), not a single-purpose tool card. When the user says
  "treat it like a website," build the world — hero, sub-nav, multiple routes —
  not a card. Ask which tier before building. Saved as
  [[project_testwright_qa_platform]] and [[feedback_new_tool_needs_thumbnail]].
- **Study references' design *and* IA, and our own, before planning.** The
  answer (Platforms vs Toolkit tiers) was already in our codebase.
- **Microservice-ready = one seam each side.** Backend `deps.py` adapter + a
  unified route prefix; frontend a single API base + one client module. Then
  extraction is a copy + one file + one env var.
- **A user guide is a guide, not a blurb.** How-to, steps, what each control
  does, FAQ, limits. When a comprehensive guide already exists (the tool's own),
  reuse it as the single source of truth rather than writing a thin new one.
- **When a tool graduates to a platform, remove it from the toolkit fully** —
  card, area listing, breadcrumb, and derived metadata — or it reads as
  double-listed and half-migrated.
- **Local homepage screenshots blank** (the particle-canvas page); verify the
  DOM structurally with `browser_evaluate` instead of trusting the image.
