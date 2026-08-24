# Conversation — 2026-06-07 | AIRaML Website — 3D Animations, Card Polish, Fixes (Part 34)

**Date:** 2026-06-07
**Project:** ml-portfolio (Vercel) — AIRaML full website
**Continued from:** Part 33

---

## Commits This Session

| Hash | Repo | Summary |
|---|---|---|
| `62eec92` | ml-portfolio | Add 3D animations: neural network hero, rotating data cube, particle grid |
| `ed9b0d4` | ml-portfolio | Add AIRaML neural-network SVG favicon, update page title |
| `8aff25a` | ml-portfolio | Fix particle grid gelling across all sections |
| `d0e225b` | ml-portfolio | Glassmorphism cards + 3D tilt on Skills and Project cards |
| `e0561aa` | ml-portfolio | Fix 3D tilt on Skill cards; add tilt + glassmorphism to News cards |
| `bb2f692` | ml-portfolio | Fix skill card height, news glow visibility, remove EDA Explorer card (reverted) |
| `4adce3c` | ml-portfolio | Restore EDA Explorer card; add accent bar to news cards |
| `4266b08` | ml-portfolio | Remove public email address from Contact and About sections |
| `223fdef` | ml-portfolio | Remove email address from footer Connect section |
| `433e1d9` | ml-unified | Hide EDA Explorer from ML/Vision sidebar modes |

---

## 3D Animations Added

### NeuralNetwork3D (`src/components/NeuralNetwork3D.tsx`)
- Three.js sphere: 120 nodes distributed on a sphere surface, connected by lines when within distance threshold
- Pulsing emissive core (sky blue, `meshStandardMaterial`)
- Slow auto-rotation via `useFrame`
- Loaded via `React.lazy` + `Suspense` in Hero — no SSR, doesn't block page load
- Renders as a full-hero backdrop behind all hero content

### DataCube3D (`src/components/DataCube3D.tsx`)
- Pure CSS 3D — no Three.js dependency
- 6 faces: 96.7% Accuracy, 4+ Live Apps, 2+ Years ML, 3.7/4 GPA, CNN, RAG
- Auto-rotates; drag with mouse to rotate manually
- Placed in About section right column with "drag to rotate" hint
- Uses `requestAnimationFrame` for auto-rotation, stops on viewport leave

### ParticleGrid (`src/components/ParticleGrid.tsx`)
- Canvas dot grid sized to viewport (`window.innerWidth × window.innerHeight`)
- Dots repel from mouse cursor (radius 120px, force-based spring physics)
- Connected by faint lines when within 1.5× gap distance
- `position: fixed; z-index: 0` — visible through all sections
- Loaded client-side only via `ParticleGridClient` wrapper (SSR=false required for server components)
- Mouse coords: `clientX/Y` only (no `+ scrollY` — fixed bug from original version)

### MagneticButton (`src/components/MagneticButton.tsx`)
- Wraps Hero CTAs; card drifts toward cursor on hover, springs back on leave
- `strength: 0.35` default (35% of cursor offset distance)
- Spring-back: `transform 0.5s cubic-bezier(0.23, 1, 0.32, 1)`

---

## Glassmorphism Cards

Added `--bg-glass` CSS variable (rgba 60% opacity) for dark and light themes.

Applied to: ProjectCard, SkillCard, NewsCard
- `background: var(--bg-glass)` + `backdropFilter: blur(14px)`
- Radial gradient shimmer overlay that tracks tilt angle — holographic reflection
- `boxShadow` glow uses card's accent colour on hover

---

## 3D Tilt — Root Cause Fix

**Bug:** Framer Motion owns the `transform` property on `motion.div`. Setting `style.transform` on a `motion.div` that has `initial`/`animate` gets overridden every render frame — tilt never shows.

**Fix:** Always separate concerns:
- Outer `motion.div` — entrance animation only (`initial`, `animate`, `transition`)
- Inner plain `div` — tilt transform (`onMouseMove`, `style.transform`)

Applied to: `SkillCard`, `NewsCard`

---

## Particle Grid — Section Gelling

**Problem:** Some sections had `background: var(--bg)` (solid opaque), hiding the particle grid. ProjectsSection had no background at all (inconsistent).

**Fix:**
- Added `--bg-section: rgba(10,15,30,0.84)` CSS variable
- All sections now use `var(--bg-section)` — semi-transparent, particles visible through all sections uniformly
- `nav, section, footer { position: relative; z-index: 1 }` ensures content layers above the fixed canvas

---

## News Cards

- Added coloured top accent bar (3px, same as Project/Skill cards)
- Glassmorphism background + 3D tilt + shimmer
- Glow opacity bumped: `55` ring / `35` spread (was too faint at `30`/`18` for indigo/sky tones)
- `alignItems: stretch` on grid + `height: 100%` chain — consistent card heights per row

---

## Skill Cards — Height Fix

All skill cards in a row now match the tallest card (MLOps, 20 chips).
- `height: 100%` added to both the outer `motion.div` and inner tilt `div`

---

## EDA Explorer Sidebar Fix (ML-Unified)

**What the user wanted:** Remove EDA Explorer from the ML Unified app sidebar when in `?mode=ml`.

**What was done incorrectly first:** Removed EDA Explorer from `registry.json` (portfolio project cards) — wrong repo entirely.

**Correct fix:** `services/ml-api/frontend/index.html`
```js
// Before
const showEDA = APP_MODE !== 'vision';
// After
const showEDA = APP_MODE === 'eda';
```
EDA Explorer now only appears in sidebar when explicitly opening `?mode=eda`. ML and Vision modes have clean sidebars.

EDA Explorer card in portfolio `registry.json` was restored.

---

## Email Address Removed from Public Pages

User confirmed: contact form delivers to inbox via Resend — no need to expose email publicly.

Removed `ramleo84@gmail.com` from:
- `Contact.tsx` — LINKS array
- `About.tsx` — CONTACTS array
- `Footer.tsx` — SOCIALS array + standalone mailto link (replaced with "Use the contact form to get in touch.")

---

## Favicon

- Created `src/app/icon.svg` — dark rounded square, neural network node pattern (centre node + 8 satellites with connection lines, indigo/sky/emerald gradient)
- Deleted default Vercel `favicon.ico`
- Next.js App Router auto-detects `app/icon.svg` and serves it at `/icon.svg`
- Page title updated: "AIRaML | ML Engineer Portfolio"

---

## Standing Rules

- Conversation logs: `ML-Iris/Conversations/Conversation_YYYY-MM-DD_Topic_PartXX.md`
- Never expose `ramleo84@gmail.com` publicly on the website
- Framer Motion + manual transform: always separate into outer motion.div (entrance) + inner div (tilt)
- `--bg-glass` for cards, `--bg-section` for section backgrounds
- Vercel → ml-portfolio; Render → ml-unified backend
- `vision_cache/` and `.mcp.json` must never be committed
