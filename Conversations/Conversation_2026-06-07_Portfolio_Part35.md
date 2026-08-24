# Conversation — 2026-06-07 | AIRaML Website + ML Unified Restyle (Part 35)

**Date:** 2026-06-07
**Project:** ml-portfolio (Vercel) + ML-Unified (Render)
**Continued from:** Part 34

---

## Commits This Session

| Hash | Repo | Summary |
|---|---|---|
| `2f195c8` | ml-portfolio | Redesign Projects section: two-panel layout (REVERTED) |
| `4c43669` | ml-portfolio | Revert two-panel project layout — back to grid |
| `17d4f9c` | ml-unified | Apply AIRaML design system to ML Unified frontend |

---

## Two-Panel Projects Layout — Attempted & Reverted

User asked for a layout like ML Unified (sidebar list left, detail panel right) for the portfolio project cards. Built and pushed but user said "no not like this, revert it." Reverted with `git revert` — grid layout restored.

**Lesson:** User wants the portfolio project cards to stay as-is (grid with glassmorphism + tilt). The ML Unified app itself should be restyled, not the portfolio cards.

---

## ML Unified — AIRaML Design System Applied (`17d4f9c`)

Restyled the ML Unified frontend (`services/ml-api/frontend/index.html`) to match the AIRaML portfolio design language.

### CSS Variables Added
```css
:root {
  --bg-glass:   rgba(17, 24, 39, 0.60);
  --bg-section: rgba(10, 15, 30, 0.84);
}
[data-theme="light"] {
  --bg-glass:   rgba(255, 255, 255, 0.60);
  --bg-section: rgba(240, 244, 248, 0.84);
}
```

### New CSS Classes
- `.gradient-top-bar` — 3px indigo→sky→emerald bar at very top of page
- `.gradient-text` — gradient background-clip text (indigo→sky→emerald)

### Visual Changes

| Element | Before | After |
|---|---|---|
| Top of page | Nothing | 3px gradient bar |
| Nav logo mark | Flat indigo→sky | Indigo→sky→emerald + glow |
| Nav title | Plain text | Gradient text |
| Sidebar active item | Grey background | Glassmorphism + left accent bar in model color + dot glow |
| Model header | Plain border-bottom | Glassmorphism card + 3px colored top accent bar |
| Predict button | Flat indigo | Gradient indigo→sky with glow shadow |
| Result panel | Solid card | Glassmorphism with blur |
| Empty state | Plain dashed border | Glassmorphism |

### Dynamic Accent Wiring
- `--active-accent` CSS variable set per selected model (sidebar bar + dot glow)
- `--header-accent` CSS variable set per selected model (model header top bar)
- Wired in: `selectModel()`, `selectVision()`, `selectUnsupervised()`, `selectEDA()`

### JS Fix
- `applyNavMode()` updated to use `getElementById('nav-title-el')` / `getElementById('nav-sub-el')` instead of `querySelector('.nav-title')` — avoids conflict with new `.gradient-text` class

---

## Favicon — ML Unified

- Created `services/ml-api/frontend/icon.svg` — identical to AIRaML portfolio favicon
- Neural network node pattern (centre + 8 satellites + connection lines, indigo/sky/emerald gradient)
- Updated `index.html`:
```html
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="alternate icon" href="/favicon.ico" type="image/x-icon">
```
- **Note:** This change is in the working directory but was NOT committed yet (user interrupted before commit)

---

## ML Unified — Full Animation & Aesthetic Plan (Next Session)

1. **Page load** — sidebar items stagger-fade in (60ms apart), main panel slides up + fades in on model select
2. **Model switching** — current panel fades out + slides left, new panel slides in from right
3. **Result reveal** — result card slides up from below, probability bars animate 0→value, classification confidence counts up, regression value counts up
4. **Sidebar interactions** — active dot pulses once on selection, hover: background fill sweeps from left
5. **Predict button** — shimmer/pulse while loading, brief green flash before result appears
6. **Particle background** — canvas dot grid (`position: fixed`, repels from mouse) behind all content
7. **Form fields** — focus glow matches active model's accent color (currently hardcoded indigo)
8. **Metric pill** — count-up animation when model is selected
9. **General aesthetic** — ambient gradient blobs in background, typography tightened

---

## Pending Tasks

- **Favicon commit** — `icon.svg` created but not committed (interrupted)
- **ML Unified animations** — full plan above, to be built next session
- **Render port-scan timeout** (ml-api) — still unresolved
- **RESEND_API_KEY + NEWSAPI_KEY** — user needs to add to Vercel dashboard
- **PCA 3D scatter** (ML-Iris) — in_progress
- **Export HTML visual overhaul** (ML-Iris) — pending
- **ruff check + pytest + commit/push** (ML-Iris) — pending

---

## Standing Rules

- Conversation logs: `ML-Iris/Conversations/Conversation_YYYY-MM-DD_Topic_PartXX.md`
- Never expose `ramleo84@gmail.com` publicly on the website
- Framer Motion + manual transform: outer `motion.div` (entrance) + inner `div` (tilt)
- `--bg-glass` for cards, `--bg-section` for section backgrounds
- Vercel → ml-portfolio; Render → ml-unified backend
- `vision_cache/` and `.mcp.json` must never be committed
- Portfolio project cards stay as grid — do NOT change to two-panel layout
