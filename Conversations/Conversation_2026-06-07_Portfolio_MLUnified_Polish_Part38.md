# Conversation — 2026-06-07 | Portfolio Polish + Mobile Responsiveness (Part 38)

**Date:** 2026-06-07
**Projects:** ml-portfolio (Vercel)
**Continued from:** Part 37

---

## Commits This Session

| Hash | Repo | Summary |
|---|---|---|
| `85c3cc3` | ml-portfolio | Pipeline stages: apply Skills card treatment (glass, 3D tilt, shimmer, accent bar) |
| `db9de69` | ml-portfolio | Mobile responsiveness: navbar hamburger, timeline single-column, grid fixes |
| `c26e1ad` | ml-portfolio | Fix mobile navbar: hamburger outside nav-links, theme toggle always visible, dropdown with all links + resume |
| `78d9155` | ml-portfolio | Reduce light theme network line opacity 0.32→0.22; remove unused useThree import |
| `dbe25ac` | ml-portfolio | Replace all emojis with SVG icons: Skills categories, DockerHub, Location, checkmark |

---

## Pipeline Stages — Skills Card Treatment

Applied the same glassmorphism + 3D tilt + shimmer + accent bar treatment from the Skills section to the Pipeline stage tiles.

### New `StageCard` component in PipelineShowcase.tsx

| Feature | Detail |
|---|---|
| Glass background | `var(--bg-glass)` + `backdrop-filter: blur(14px)` |
| 3D tilt on hover | `perspective(900px) rotateX/Y` tracking mouse within tile |
| Shimmer overlay | Radial gradient following cursor position |
| Accent top bar | 3px strip at top edge matching each stage's accent color |
| Border + glow | Accent-colored border and box-shadow on hover/active |
| Active state | Stronger border (`accent60`) when tile is selected/expanded |

---

## Pending Task Audit (Full Review)

### Completed (were listed as pending but ARE done)
- PCA 3D scatter ✅ (Part 29)
- Export HTML visual overhaul ✅ (Part 29 + Part 37)
- Portfolio animations ✅ (Parts 12–37)
- All 25 UI/UX points from Part 28 plan ✅
- RESEND_API_KEY + NEWSAPI_KEY ✅ (user added to Vercel)

### Full Priority-Ordered Pending List (20 items)

| # | Item | Status |
|---|---|---|
| 1 | Mobile responsiveness | ✅ Done this session |
| 2 | ruff + pytest | Pending |
| 3 | Chatbot (portfolio-wide, context-aware) | Pending |
| 4 | Theme palette picker | Pending |
| 5 | Proxy page (`/app/[id]`) | Pending |
| 6 | SHAP Interpreter card | Pending |
| 7 | Build Pipeline mode (ML Unified) | Pending |
| 8 | Prediction confidence bar chart | Pending |
| 9 | SHAP in ML Unified | Pending |
| 10 | Training history / comparison | Pending |
| 11 | Cleaned CSV download | Pending |
| 12 | EDA microservice extraction | Pending |
| 13 | 35 EDA unit tests | Pending |
| 14 | Side-by-side vision results | Pending |
| 15 | Batch predict for vision | Pending |
| 16 | Vision ambient themes | Pending |
| 17 | Mobile bottom tab bar | Pending |
| 18 | Data drift detection | Pending |
| 19 | MLflow experiment tracking | Pending |
| 20 | Playwright E2E tests | Pending |

---

## Mobile Responsiveness (`db9de69` + `c26e1ad`)

### New file: `src/hooks/useIsMobile.ts`
- `MutationObserver`-free approach — `window.innerWidth` + `resize` event
- Breakpoint default: 768px
- Used in Timeline.tsx for conditional layout

### globals.css additions
```css
.nav-links     { display: flex; align-items: center; gap: 1.25rem; }
.nav-hamburger { display: none; }

@media (max-width: 768px) {
  .section       { padding: 3rem 1.25rem; }
  .nav-links     { display: none !important; }
  .nav-hamburger { display: flex !important; }
  .timeline-line { left: 0.5rem; transform: none; }
}
```

### Navbar fix (two-step)

**Root cause:** Hamburger and ThemeToggle were both inside `.nav-links`, so hiding that div on mobile hid both.

**Fix:** Restructured to:
```
<nav>
  Logo
  <div style="flex row">
    <div class="nav-links">  ← links + Resume, hidden on mobile
    <ThemeToggle />           ← always visible
    <button class="nav-hamburger">  ← always visible on mobile
  </div>
  Mobile dropdown (all links + Resume)
</nav>
```

### Timeline mobile layout
- Desktop: two-column alternating (left/right cards), center line
- Mobile: single column, full-width cards, line moves to left rail (`left: 0.5rem`), dot at `left: -1.6rem`
- Animation: x-slide replaced with y-slide on mobile

### Grid fixes
- `minmax(320px, 1fr)` → `minmax(min(320px, 100%), 1fr)` in Skills and ProjectsSection
- Prevents overflow on 320px phones where 320px min > available width

---

## Light Theme Network Line Opacity (`78d9155`)

Reduced from `0.32` → `0.22` in light mode. Stays visible but no longer overpowers hero content. Dark mode unchanged at `0.18`.

Also removed unused `useThree` import from NeuralNetwork3D.tsx.

---

## Emoji → SVG Replacement (`dbe25ac`)

### New file: `src/components/SiteIcons.tsx`
Shared SVG icon components used across About, Contact, Footer:
- `LinkedInIcon` — LinkedIn logo mark
- `GitHubIcon` — GitHub Octocat mark
- `DockerIcon` — Docker container grid (rows of small boxes)
- `LocationIcon` — Map pin with filled circle
- `CheckCircleIcon` — Circle with polyline checkmark
- `SiteIcon({ id })` — Dispatcher: maps string id → icon component

### Skills.tsx
Added `SkillIcon({ id, accent, size })` component with 6 SVG cases:

| Category | ID | SVG Design |
|---|---|---|
| Machine Learning | `ml` | 3 nodes (circles) connected by lines — neural network |
| Deep Learning | `dl` | Lightning bolt polyline with fill |
| Generative AI | `genai` | 4-pointed star/sparkle path |
| NLP | `nlp` | Chat bubble with two text lines |
| Computer Vision | `cv` | Eye outline with filled iris circle |
| MLOps & Tools | `mlops` | Gear with center circle |

All icons use `stroke: accent`, `fill: accent` at low opacity — same tinted tile pattern as Pipeline.

Changed data field from `icon: "🧠"` → `id: "ml"` etc.

### About.tsx / Contact.tsx
- `"🐳"` → `icon: "docker"` → renders `<DockerIcon>`
- `"📍"` → `icon: "location"` → renders `<LocationIcon>`

### Contact.tsx — success state
- `<div style={{ fontSize: "2rem" }}>✅</div>` → `<CheckCircleIcon size={36} />`

### Footer.tsx
- `icon: "GH"` / `"IN"` upgraded to `"gh"` / `"in"` → proper `<GitHubIcon>` / `<LinkedInIcon>`
- `"🐳"` → `"docker"` → `<DockerIcon>`

---

## Chatbot — Decision

**Location:** Portfolio-wide floating widget (bottom-right)
**Context-aware:** IntersectionObserver tracks current section → changes system prompt context
**Engine:** Claude API (Haiku) — demonstrates practical LLM integration as a portfolio skill
**Section-specific suggestions:**
- Hero → "Ask me about my ML experience"
- Projects → "Ask about tech stack, accuracy, or how any project was built"
- Skills → "Ask how I've used XGBoost, CNNs, or any framework"
- Pipeline → "Curious about any stage of the ML pipeline?"
- About/Contact → "Ask about my background or availability"

---

## Standing Rules (unchanged)

- Conversation logs: `ML-Iris/Conversations/Conversation_YYYY-MM-DD_Topic_PartXX.md`
- Never expose `ramleo84@gmail.com` publicly on the website
- `vision_cache/` and `.mcp.json` must never be committed
- Portfolio project cards stay as grid — do NOT change to two-panel layout
- Vercel → ml-portfolio; Render → ml-unified backend
- `--bg-glass` for cards, `--bg-section` for section backgrounds
- Always run `ruff check` + `pytest` before pushing ML-Unified
- User-facing errors: plain English only
