# Part 305 — Testwright: grounding generation in REAL pages, the aria-hidden root cause, R7 share links, dashboard polish, parallel deep-explore

Continues [Part 304](Session_2026-10-02_TestwrightPhase2GenerationVerifyRepairLoopAndLiveDashboard_Part304.md).
2026-10-02. A long, user-driven session that started with "is the failure issue
resolved?" and ended with the real, research-backed fix: **generation now SEES the
destination pages before writing tests, so it asserts their real content instead of
guessing.** Live-proven green. Along the way: R7 share links, two more deterministic
locator fixes, the aria-hidden label root cause, a dashboard redesign the user pushed
twice to get right, a found-uncommitted Discover UX, and parallelized deep-explore.

The through-line (again): **ground in what actually executed/rendered, never guess** —
and **"shipped" means committed + deployed + proven, not claimed.**

---

## Arc 1 — R7 Phase 1: shareable run reports (frontend-only)
Scoped in Part 304; built here. Permalink to a read-only run report.
- `supabase/qa_shared_runs.sql` (RLS: service-role only, 90-day TTL — user ran it live).
- `POST /api/qa-run/share` + `GET /api/qa-run/share/[id]` (Next.js routes, service-role
  key, `analyticsWritesEnabled` gate, size caps, code opt-in **off** by default).
- `/qa/run/r/[id]` read-only page reuses `<Result readOnly>`; `ShareButton` + helper.
- Privacy page discloses storage + 90-day retention. ml-portfolio `4783699`, doc `67fa7e6`.

## Arc 2 — two more deterministic locator fixes (the user's reported failures)
From real runs the user drove:
- **`first_on_href_locators`** — append `.first()` to ANY raw `locator('a[href=...]')` the
  model writes itself (not just the getByRole→href rewrite path). Fixes strict-mode when an
  href matches >1 link (`#capabilities`).
- **`strip_junk_locators`** — drop any step with a wildcard/placeholder name (`'*'`, `'...'`,
  empty) that matches nothing and burns the timeout (the 29.5s `name:'*'`).
- Extracted all deterministic post-processors into **`routers/qa/locators.py`** (author.py
  331→179). Prompts hardened (no wildcard names, no invented content). ML-Unified `95748eb`.
- Bug caught by testing: a **regex backreference collision** — two `\1` groups concatenated
  into one alternation point at the wrong branch; dropped the backreference.

## Arc 3 — the unstable card-name root cause (aria-hidden)
The recurring `getByRole('link',{name:'Security & Trust 26 tools'}) not found`.
**Evidence, not guess** (fetched the live homepage): the category card `<a>` has a FIRST
child `<span aria-hidden="true">` holding 26 nested tool names. Discover captured raw
`textContent`, so the link-map label became that tool list and `.slice(0,80)` cut it off
before the real title — nothing matched the model's accessible-name locator, so href-grounding
never fired. Fix (ML-Unified `c155804`): (1) discover excludes `aria-hidden` descendants when
labeling a link (→ matches the ACCESSIBLE NAME); (2) `find_href` matches on an
alphanumeric-only normalized form (so `"Security & Trust26 tools"` == `"...Trust 26 tools"`).
Uniqueness guard kept. Unit-verified: category links → `a[href="/tools/..."].first()`.

## Arc 4 — THE fix: generation sees the destination pages
The last failure class: the generator **invents assertions** it can't know
(`toHaveClass('active')`, a guessed heading like `'AIRaML'` on `/ml`). The user pushed hard:
*"use a tool which can access the page and check instead of blindly asserting"* and
*"when I said search online then do that."* **Searched online** (qaskills/Checkly/Octomind):
industry best practice is to **navigate the pages live and ground assertions in what you saw**
(+ a self-heal loop + deterministic validation) — exactly our gap: generation only ever saw
the START page.

We already had the pieces (Playwright runner + one-hop explore). Made it real (ML-Unified
`957d197`, ml-portfolio `40141b2`):
- **Deep explore ON by default**, visits up to **12** same-origin pages (`MAX_DEEP_PAGES` 3→12,
  `MAX_PAGE_CONTEXT` 20k→34k).
- Each page captured as **title + headings (h1-h3) explicitly** — not a snapshot prefix,
  because the real h1 sits past the nav.
- Prompt: context holds `===PAGE <url>===` sections → assert that page's REAL heading; fall
  back to URL/generic only when a page isn't present; never assert a guessed class/heading (4a).
- **Live-proven end to end:** fresh Discover→generate→run — generated code asserted the REAL
  platform headings (`/ml` "Four trained models…", `/qa` "Write a test in plain English…") and
  real `/docs` headings; suite **3/3 PASSED on first run, no Auto-fix needed.**

## Arc 5 — parallel deep-explore (speed)
Deep visiting 12 pages sequentially was ~2-3 min. Parallelized (ML-Unified `f07324b`): each
page in its own tab of the same context, in chunks of `MAX_DEEP_CONCURRENCY`=4 (2-vCPU sweet
spot) → ~3 rounds instead of 12. The Discover live timer (`7bf4a3e`) shows the lower number.

## Arc 6 — dashboard redesign (pushed twice)
User: "current design look bland… are you not capable of brilliant designs?… can you use
figma?" (No — can't drive Figma; the gap was execution in code.)
- First pass (`678a741`): gradient 270° pass-rate **gauge** w/ glow, depth hero, richer trend
  with y-axis + "now" callout, gradient fail bars, split flaky bars. dataviz-validated.
- User: "this part looks bland" (the lower panels). Second pass (`4385bef`): icon-badged
  section headers, **ranked** top-failing rows with count pills, flaky split bars + % pass,
  proper empty state — removed the dead space. Verified headed, dark + light.

## Arc 7 — found: Discover UX was uncommitted
"Why no time / no Select all on Discover?" — the timer/stepper + Select all existed in the
working tree but were **never committed** (65 lines, `git status` = ` M`). The Part 304 summary
that said they "shipped" was wrong. Committed (`7bf4a3e`). **Lesson: "shipped" ≠ committed —
check git, trust git.**

## Key decisions
- **Ground generation in the real destination pages** (navigate + capture title/headings),
  not prompt band-aids — matches the industry (Octomind/Checkly/MCP). The prompt guard (4a)
  is only a fallback for pages not reached.
- **Capture title + headings explicitly** for deep pages (the real h1 sits past a snapshot
  prefix).
- **Deep ON by default** (grounding out of the box); uncheck for a fast single-page scan.
- **Parallel page visits** (bounded to 4) over a sequential crawl.
- Export/share/dashboard stay **frontend-only** (Supabase via Next routes, no HF).

## Lessons
- **When the user says search online, search online** — don't patch from reasoning first.
  The search confirmed the exact fix and that we already had 2/3 of the pattern.
- **Don't band-aid when the tool can just look.** "Assert less / don't guess" was a patch;
  "actually load the page and read it" was the fix. The user's plain logic was right.
- **A link's textContent ≠ its accessible name** when a card hides decoration with
  aria-hidden — ground the map on the accessible name. [[feedback_debug_first]]
- **Each AI-generated run surfaces a different class** — fix classes, verify on the deployed
  Space (stage==RUNNING), prove live. [[feedback_status_claims_need_evidence]]
- **"Shipped" must mean committed + deployed + proven.** A prior summary's "shipped" was
  uncommitted working-tree code.

## Commits
| Repo | Commits |
|---|---|
| ml-portfolio | `4783699` (R7 share) · `678a741` (dashboard gauge/hero) · `7bf4a3e` (Discover timer+Select all) · `4385bef` (dashboard bottom panels) · `40141b2` (deep default) |
| ML-Unified (backend, HF) | `95748eb` (first_on_href + strip_junk, locators.py) · `c155804` (href aria-hidden + normalize) · `957d197` (ground in destination pages) · `f07324b` (parallel deep) |
| ML-Unified (docs) | `67fa7e6` (R7 plan status) |

## State after this session
- **Generation** sees destination pages (deep default, parallel) and asserts their REAL
  content; locators href-grounded + `.first()`, no wildcards, no unstable card names.
- **The full failure chain is closed:** strict-mode href · wildcard names · unstable card
  names · invented assertions — all fixed, live-proven (3/3 green first run).
- **Run** has the verify-repair loop + export + share links + persisted results.
- **Dashboard** redesigned (gauge, trend, ranked panels), live + animated, dark + light.
- Open/deferred: R7 historical dashboard (Supabase Option B), learn-from-edits, R5 auth.
  Related: [[project_testwright_run_perf]], [[project_testwright_qa_platform]].
</content>
