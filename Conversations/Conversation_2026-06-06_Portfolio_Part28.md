# Conversation — 2026-06-06 | EDA Roadmap + Portfolio Redesign Plan (Part 28)

**Date:** 2026-06-06
**Project:** ML-Unified · ml-portfolio

---

## Built This Session (before this planning conversation)

| Commit | Description |
|---|---|
| `560b4f8` | EDA aesthetic upgrade: Plotly charts, smart insights, sample preview, quality score, skew/kurtosis, sticky nav |
| `a947492` | Box plots (Plotly, all numeric cols, outlier dots) + HTML export (self-contained, PNG-embedded) |
| `d81f711` | Render port-scan fix: `_load()` moved to FastAPI lifespan; `healthCheckPath: /health` in render.yaml |

---

## Full Requirements List — To Be Built

### EDA Explorer — New Features (6 items)

| # | Feature | Implementation Detail |
|---|---|---|
| 1 | **Zoom / pan on all Plotly charts** | Change `displayModeBar: false` → `displayModeBar: 'hover'` and add `scrollZoom: true` in every Plotly config call. Applies to: distributions, box plots, correlation heatmap, PCA 3D scatter, MI heatmap |
| 2 | **ML Readiness panel** | Rule-based per-column verdict. Backend computes flags: ID-like (nunique = nrows → drop), near-constant (std < 0.01 or nunique = 1 → useless), high missing (>20% → drop, >5% → impute), high cardinality categorical (nunique > 50 → needs encoding), datetime not engineered (dtype object but parses as date → extract year/month/dow). Each column gets: status (pass/warn/fail), verdict label, recommendation string. Frontend: new section with traffic-light per column |
| 3 | **Auto-generated narrative paragraph** | Pure Python string templating from existing stats — no LLM. Template covers: shape, quality score, missing columns, likely target detection (binary column with 30–70% positive rate = class imbalance note), highest correlation pair, most skewed column, duplicate warning. Shown at top of results as a "Senior Analyst Summary" card |
| 4 | **Mutual Information matrix** | Backend: discretize all columns (continuous → equal-frequency bins), compute `sklearn.metrics.mutual_info_score` for every pair (N²), normalize to 0–1 by dividing by max(H(X), H(Y)). Cap at 15 columns. Return `{labels, matrix}` same shape as correlations. Frontend: same Plotly heatmap but sequential colorscale (Viridis or Blues), add as new section after Pearson heatmap |
| 5 | **PDF export** | `window.print()` approach. Add `@media print` CSS to `index.html`: hide sidebar, nav, upload zone, export buttons; show only `#edaResults`. Add "Download PDF" button next to "Export Report" button. Zero new dependencies |
| 6 | **PCA 3D scatter** | Backend: scale numeric cols with `StandardScaler`, apply `PCA(n_components=3)`, return `{coords: [[x,y,z],...], explained_variance: [v1,v2,v3], labels: [col1,col2,...]}`. Include first categorical column as optional color dimension. Frontend: Plotly `scatter3d`, dropdown to pick color column, shows explained variance % per axis. New section below MI heatmap |

---

### EDA Explorer — Visual Redesign (7 items)

| # | Item | Implementation Detail |
|---|---|---|
| 7 | **Glassmorphism section cards** | CSS: `background: rgba(255,255,255,0.03)`, `backdrop-filter: blur(12px)`, `border: 1px solid rgba(255,255,255,0.08)`, `box-shadow: 0 8px 32px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05)` |
| 8 | **Animated quality ring** | SVG arc (stroke-dasharray / stroke-dashoffset animation). Arc draws 0 → score in 1.2s ease-out. Stroke: green ≥80, amber ≥60, red <60. Replaces the flat quality chip |
| 9 | **Animated number counters** | JS countUp function: rows, cols, missing %, quality score all count from 0 to final value over 800ms with easing. Triggered once when overview section enters DOM |
| 10 | **Staggered section entrance** | IntersectionObserver on each `.eda-section-card`. On first intersect: animate from `opacity:0, translateY(24px)` → `opacity:1, translateY(0)` over 400ms. 60ms delay multiplied by section index |
| 11 | **Gradient section title accents** | Each section title gets a 3px left border with gradient `#34d399 → #38bdf8`. Implemented via `border-left: 3px solid transparent; background: linear-gradient(...) border-box` technique |
| 12 | **Overview chips with icons** | Icon per chip: Rows=⊞, Cols=▦, Missing=⚠, Duplicates=⊕, Quality=◉. Chips get subtle gradient background tinted by their status color |
| 13 | **Export HTML visual overhaul** | `_buildExportHTML()` redesigned: gradient header with filename + date, glassmorphism-style section cards (dark theme, border-glow), better typography, section dividers, animated CSS counters in HTML (pure CSS counter animation via @keyframes), premium footer |

---

### Portfolio — Animations & Interactions (6 items)

| # | Item | Implementation Detail |
|---|---|---|
| 14 | **3D card tilt** | `onMouseMove` on card → compute cursor offset from card center → CSS `rotateX(Ydeg) rotateY(Xdeg)` up to ±12°. `transform-style: preserve-3d`, `perspective: 1000px`. Accent glow `box-shadow` intensity follows tilt magnitude. `onMouseLeave` → spring back to flat |
| 15 | **Staggered card entrance** | Framer Motion `whileInView={{ opacity:1, y:0 }}` + `initial={{ opacity:0, y:40 }}`. `viewport={{ once: true }}`. Each card has `transition={{ delay: index * 0.1, type: 'spring', stiffness: 80 }}` |
| 16 | **Animated hero** | Gradient mesh background: CSS `@keyframes` animating `background-position` on a radial gradient. Typewriter effect on "AIRaML" headline (CSS animation or JS char-by-char). Badge chip ("MACHINE LEARNING ENGINEER") slides down from above on load. Stats chips count up on mount |
| 17 | **Glow on card hover** | `box-shadow: 0 0 40px ${accent}66` on hover. Transition 300ms. Each card uses its own `accent` color from `registry.json`. Currently only used on tiny chips — should define the card |
| 18 | **Tag filter animation** | Framer Motion `AnimatePresence` wrapping each card. Exit: `scale: 0.8, opacity: 0`. Enter: spring from `scale: 0.8, opacity: 0`. Layout animation on container so remaining cards smooth-reflow |
| 19 | **Metric counter** | `useInView` hook on each card's metric number. When card enters viewport, count from 0 to final value over 1s. e.g. "150" counts up: 0 → 150. Use `useEffect` + `requestAnimationFrame` |

---

### Portfolio — UI/UX Fixes (6 items)

| # | Fix | Detail |
|---|---|---|
| 20 | **Colored top border per card** | `border-top: 3px solid ${accent}` — each card's accent color from registry. Thicker than current, full width |
| 21 | **Hero stats 3× bigger** | Stats row: much larger font (2rem+ for the number), icon per stat, remove the tiny chip style. "2" on its own line above "Live Platforms". Bold, prominent |
| 22 | **Card hover: elevation + lift** | `box-shadow` increases + `transform: translateY(-4px)` on hover. Smooth 200ms transition. Makes cards feel clickable |
| 23 | **Hero contrast layer** | Option A: dark gradient strip behind hero (navy → transparent). Option B: dark hero on light-colored body. Currently hero background ≈ card background ≈ page background — all same value, nothing pops |
| 24 | **Equalize card heights** | Grid: `align-items: stretch`. Cards use `display: flex; flex-direction: column`. Description takes `flex: 1` to fill remaining space. Button always at bottom |
| 25 | **AIRaML significantly larger** | Current size undersells the brand. Target: 5–6rem on desktop. Should be the first thing the eye lands on |

---

## Microservice Discussion — EDA

### Decision: Build features first, extract later

**EDA is the strongest microservice candidate** in the codebase because:
- Shares **nothing** with `MODELS` dict or `.pkl` files
- Compute-heavy operations (MI N² pairs, PCA decomposition) that shouldn't block ML inference
- Completely stateless — every request is a fresh CSV
- `requirements.txt` would be lighter: no xgboost, lightgbm, catboost, joblib

**Extraction path (when ready):**
```
eda-api/
├── app.py           ← 10 lines: FastAPI + include_router + CORS
├── routers/
│   └── eda.py       ← copy as-is, zero logic changes
└── requirements.txt ← pandas, numpy, scikit-learn, fastapi, python-multipart only
```
Frontend change: one env var swap — `EDA_API` instead of `API` for `/eda` endpoint.

**Why not now:** Features aren't complete yet. Extract after all 6 features are built. That's the modular monolith pattern — router is already isolated, extraction is mechanical.

**Memory benefit:** `eda-api` starts in ~10s vs ml-api's 30s+. Render free tier RAM: ~180MB vs ~450MB.

---

## Portfolio UI/UX Critique (from screenshot review)

### What's working
- Clean information hierarchy: badge → name → description → stats → CTA
- "Live ML Apps — click to predict" headline is strong copy
- Tag chips are readable
- About section two-column layout is solid
- Gradient on "AIRaML" and "click to predict" adds personality

### What's broken
- **Hero too empty** — 40% of page, grid background too subtle, stats too small
- **Cards too flat** — white background, thin border, accent only on tiny chip
- **Inconsistent card heights** — Vision card 2× taller than EDA card
- **No depth** — no shadows, no glassmorphism, no visible hover state
- **Typography timid** — "AIRaML" could be 3× bigger, headlines don't command attention
- **Light theme fighting itself** — hero, cards, and page background all near-white, nothing pops

---

## Build Order for Next Session

### EDA (do first)
1. Zoom/pan (#1) — 10 min
2. Visual redesign: glassmorphism + animated counters + quality ring + staggered sections (#7–#12) — 2 hours
3. Export HTML visual overhaul (#13) — 1 hour
4. ML Readiness panel (#2) — backend rules + frontend section
5. Auto-generated narrative (#3) — backend string templating + frontend
6. Mutual Information matrix (#4) — backend + Plotly heatmap
7. PCA 3D scatter (#6) — backend PCA + Plotly scatter3d
8. PDF export (#5) — window.print() + @media print CSS

### Portfolio (do after EDA)
1. UI fixes: hero stats, card heights, border, AIRaML size (#20–#25)
2. Glow + hover elevation (#17, #22)
3. 3D card tilt (#14)
4. Staggered card entrance with Framer Motion (#15)
5. Animated hero: gradient + typewriter + chip animation (#16)
6. Tag filter animation with AnimatePresence (#18)
7. Metric counter on scroll (#19)

---

## Standing Rules (unchanged)

- Apply changes to ALL affected repos simultaneously
- Conversation logs in `ML-Iris/Conversations/`
- Light theme: ALL elements must adapt (glassmorphism must work in light too)
- Vercel = portfolio only; Render = ML apps
- `vision_cache/` and `.mcp.json` must never be committed
- Always run `ruff check` + `pytest` before pushing
- Mock-based tests for inference paths requiring model downloads
- User-facing errors: plain English only
- Keep ml-api and ml-vision requirements.txt fully independent
- All vision endpoint URLs sourced from `VISION_API`, never `API`
- Microservices pattern: modular monolith (router per domain, extractable later)
- `?mode=eda` uses strict mode in `_friendlyEndpoints` — only shows EDA Analysis in Live Metrics
- `_renderEDAPlots` called via `setTimeout(..., 0)` after `innerHTML` set
- ruff found at `.venv/bin/ruff` — not on PATH
- EDA router is already fully isolated in `routers/eda.py` — extraction to `eda-api` microservice is mechanical once features are complete
