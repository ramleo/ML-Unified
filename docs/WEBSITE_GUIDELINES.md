# Website Guidelines & Guardrails

Standards for the ml-portfolio site (Next.js 16 / React 19 / Tailwind 4 on Vercel)
and the FastAPI backends (ml-api, ml-sql on Hugging Face Spaces). Pulled from
current 2026 references and mapped to what this project already enforces.

Two parts: **website standards** and **QA testing**. A ✅ marks something already
in force; an item without one is a gap worth closing.

---

## Part 1 — Website standards

### A. Performance — Core Web Vitals (direct Google ranking inputs)

| Metric | Threshold | Where it bites us |
|---|---|---|
| LCP (Largest Contentful Paint) | < 2.5s | Tool pages with WebGL/canvas heroes |
| INP (Interaction to Next Paint) | < 200ms | AI-tool panels, live-run buttons |
| CLS (Cumulative Layout Shift) | < 0.1 | Async-loaded charts / result cards |
| TTFB | < 100ms globally | Vercel edge + caching already helps ✅ |

Guardrails:
- Mobile-first CSS.
- `next/image` with explicit width/height — never let async media shift layout.
- Lazy-load below-fold content only. **Never lazy-load models** (caused a port-scan
  timeout on Render; standing rule).
- Ship green Core Web Vitals *before* adding hero animation.

### B. Accessibility — WCAG 2.2 AA (legally enforceable: EAA, ADA, Section 508)

86 success criteria; 56 for AA. The ones we actually risk failing:
- **Semantic HTML first** — most of AA comes free from correct markup.
- **Focus visible** (2.2 new) — every interactive element needs a visible focus ring. ✅ (standing rule)
- **Touch targets ≥ 24×24px** (2.2 new) — check tool buttons on mobile.
- **Contrast** — 4.5:1 body text, 3:1 UI / large text. Verify the dark theme on both grounds.
- **No emoji as icons** — SVG only. ✅ (standing rule; also better for screen readers)
- Keyboard-operable everything; honour `prefers-reduced-motion` on animated backgrounds.

### C. Security — OWASP Top 10 (2025) + LLM Top 10

The LLM-side sweep (E10–E20) closed most of this. Standing web guardrails:
- **A01 Broken Access Control** — origin allowlists on both Spaces ✅ (E16); IP blocklist ✅ (E17).
- **A02 Security Misconfiguration** — CSP, HSTS, X-Frame-Options headers ✅.
- **A03 Software Supply Chain** — Dependabot + gitleaks ✅; pin versions; skops-over-pickle (E18) ✅.
- **A04 Cryptographic Failures** — no secrets in the repo; `.env.local` holds PROD keys (local-only).
- **A05 Injection** — DuckDB file access locked ✅ (E10); connect-target public-host check ✅ (E14).
- **LLM Top 10** — cost caps, output/message bounds, Turnstile, free-first fallback ✅ (E11–E13).
- **Still open (owner: user):** key rotation — the real close-out for E9 (Vercel) and E10 (both Spaces).

### D. Code & SEO hygiene
- Semantic structure doubles as SEO structure: headings, meta, sitemap, `robots.txt`.
- Edge caching + static generation for sub-100ms TTFB.
- **No file over 400 lines** — check `wc -l` before touching; modularize first if over 350. ✅ (standing rule)

---

## Part 2 — QA testing

### Testing pyramid (2026 allocation: ~70 / 20 / 10)

```
        /\        E2E  5–10%    critical user journeys only (Playwright)
       /  \
      /----\      Integration 20%   API ↔ DB ↔ provider contracts
     /      \
    /--------\    Unit 70%      pure functions — fast, cheap, deterministic
   /__________\
```

### What to test where (mapped to this codebase)

- **Unit (70%)** — pure logic, already proven ad-hoc, should be permanent tests:
  `runOutcomes.ts`, `chatLimits.ts`, `aiToolsLimits.ts`,
  `_conn_guard.py`, `core/skops_safe.py`, `_guard.py` (limit/daily-cap math).
- **Integration (20%)** — FastAPI `TestClient` matrices (guards, connect checks),
  Supabase paging (`fetchAllRows`), provider fallback chains.
- **E2E (5–10%)** — critical journeys only: a tool run press→success,
  text-to-SQL connect, AutoML train→export→re-upload.

### Guardrails (most are already recorded lessons)
- **Run E2E on every pull request**, not just before release.
- **Deterministic shell → hard assertions per push; model output → scored/property
  assertions nightly.** ✅ (all 4 testing-plan phases shipped)
- **Build a test the tool can fail** — plant known ground truth, believe the
  disagreement (found 3 shipped bugs this way).
- **`expect` matches the wrong element** — assert on scoped panels, not the whole
  page (4 false passes in one session).
- **Debug first, never guess** — silent API failure → raw debug call immediately;
  never state a cause without evidence.
- **Status claims need evidence** — never say done/fixed/deployed without a command
  showing it; sweep for the whole bug *class*, and prove a "clean" check can fail.
- **Billed-API testing** — never batch live calls to a paid API for self-verification
  without asking; mock locally, one live call at a time with go-ahead.

---

## Gaps worth acting on (priority order)

1. **Key rotation** (owner: user) — E9 Vercel keys + all keys on both Spaces (E10 exposed them).
2. **WCAG 2.2 + Core Web Vitals audit of the tool pages** — touch targets, contrast, Core Web Vitals
   **and heading structure done 2026-09-17** (`a8090b1`, `f3a6426`, `0b0dc1c`; home 66→100); only the
   `next/image` migration remains.
3. ~~Promote ad-hoc guard proofs (E10 / E14 / E18) into a permanent suite~~ — **done 2026-09-16**
   (E4 closed: `services/ml-sql/tests/` + `test_skops_safe.py`, ml-sql now in CI; ML-Unified `2192ccc`).

---

## Implementation status

**Done 2026-09-16** (this pass through the guidelines):
- **SEO §D** — `app/robots.ts` → `/robots.txt`, `app/sitemap.ts` → `/sitemap.xml` (58 URLs, tool
  slugs auto-read at build). ml-portfolio `e830ce3`.
- **A11y §B — reduced motion** (WCAG 2.3.3) — global CSS `@media (prefers-reduced-motion: reduce)`
  block + `ConstellationBackground` draws a static frame (no rAF, no cursor-repel) when set. `e830ce3`.
- **A11y §B — focus visible** (WCAG 2.4.7/2.4.11) — site-wide `:focus-visible` ring floor. `e830ce3`.
- **A11y §B — main landmark** (WCAG 1.3.1/2.4.1) — `role="main"` on all 53 tool pages'
  content wrapper (41 via the shared `relative z-10` wrapper, 12 hand-placed). ml-portfolio `618ee08`.
- (Related, same window: E3 provider-auth-failure alerting `078d076`; E21 delete-origin guard.)

**Done 2026-09-17** (ml-portfolio `a8090b1`) — verified live against the production build with
axe-core + rect measurement:
- **Touch targets** (WCAG 2.5.8) — every real control now ≥24px: the back button on all 53 tool
  pages (→28px), plus home "See more" / search input / `.cap-clear`, `AutoMLFooter`,
  `pipeline-builder` / `pipeline-cinema`, `FSPageHeader`. The audit corrected the plan's guesses:
  the `ToolsAIChat` controls weren't the hotspot (didn't mount on landing states), and the footer
  nav links (20px) already **pass** via the spacing exception (29px centre-to-centre ≥ 24).
- **Contrast** (WCAG 1.4.3) — axe color-contrast now **0 violations on both themes** (was 25/25).
  `--text3` retuned (dark `#64748b`→`#7e8ca4`, light `#94a3b8`→`#4d5a6d`); new `--link` token
  (=`accent-from`, every palette stop ≥4.5:1) for inline links, `--accent` kept for buttons. The
  light-theme failures turned out to be text sitting over the **constellation lines**, so the
  light-mode constellation was quietened, then re-strengthened after review (dots .30→.50 ×1.4 size,
  lines .11→.15) — clearly visible and still 0 violations across 16 animated samples both themes.
- **Two-button back nav** (ml-portfolio `6bd64b0`) — every tool page now has Home (→ `/`) **and** its
  area link via a shared `<ToolBackNav>` (was a single area button). Fixed pipeline-cinema's "Home"
  (went to ML Pipeline, not `/`), the mis-keyed feature-engineering/feature-selection (fell back to a
  lone "Home"), and kept rag-analytics' parent link. Verified: SSR sweep, all pages ≥2 correct links.

**Done 2026-09-17 — Core Web Vitals** (ml-portfolio `f3a6426`), Lighthouse mobile on live Vercel:
- Tool pages were already 98–100 (LCP ~2.3s, TBT 0) — no work needed.
- **Home was the outlier** (perf 66, LCP 4.2s, TBT 860ms). Root cause: LCP is a *text* element
  render-delayed by main-thread JS — every home section is a framer-motion client component hydrating
  at once. Fix: defer the chatbot + the three below-fold sections (architecture/pipeline/news) via
  `dynamic ssr:false` client wrappers, keeping the hero + tool grid server-rendered.
- **Result (3-run median, live): perf 66→100, LCP 4.2s→1.6s, TBT 860ms→10ms, CLS ~0.** The planned
  option of taking framer-motion off the hero proved unnecessary — LCP is already green.

**Done 2026-09-17 — Heading structure** (WCAG 1.3.1; ml-portfolio `0b0dc1c`). Audit of all 53 tool
pages: every page already had an `<h1>` + `<main>` landmark; the real violations were narrow —
- **drift** had **no `<h1>`** (title was a `<span>`, page started at h2) → title now `<h1>`.
- **8 pages skipped h1→h3** (no h2): their Runner section titles were `<h3>` → changed to `<h2>`
  (ai-code-detector, asl-fingerspelling, astrophotography, email-auth-checker,
  extension-permission-analyzer, prompt-injection-playground, text-prompted-video-tracking,
  crime-scene-reconstruction). All 9 now h1→h2; axe heading-order/page-has-heading-one/empty-heading
  clean.
- **Not done (deliberate):** converting *every* panel's `<div>` section title into a heading across
  all tools — mostly post-interaction result panels, ~40-page judgment pass axe can't verify, and
  every page already has h1 + landmark, so low value vs. regression risk. Do per-tool as touched.

## Remaining plan — scheduled next

4. **`next/image` migration** (§A, CLS) — 28 files use raw `<img>`. Per file: convert to `next/image`
   with explicit width/height (or `fill` + sized parent). Care: data-URI / canvas / dynamic srcs may
   need `unoptimized` or stay `<img>` with a noted reason; set `next.config` image domains if any are
   remote. Verify each page has no layout shift or break. (Largest item — do last.)

This is the last guidelines item. Also outstanding: the dead-code `/simplify` pass from the back-nav
work (unused `handleBack`/imports on ~48 pages). Key rotation stays the user's.

---

*Sources:* Web Dev Best Practices 2026 (selleo, pagepro); Core Web Vitals 2026
(pansofic); WCAG 2.2 AA checklist (levelaccess, clym); OWASP Top 10 2025 +
LLM Top 10 (penetolabs, qaskills); Testing Pyramid 2026 (testomat, getautonoma).
