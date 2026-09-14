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
2. **WCAG 2.2 + Core Web Vitals audit of the tool pages** — never formally done; now enforceable.
3. **Promote ad-hoc guard proofs (E10 / E14 / E18) into a permanent unit + integration suite.**

---

*Sources:* Web Dev Best Practices 2026 (selleo, pagepro); Core Web Vitals 2026
(pansofic); WCAG 2.2 AA checklist (levelaccess, clym); OWASP Top 10 2025 +
LLM Top 10 (penetolabs, qaskills); Testing Pyramid 2026 (testomat, getautonoma).
