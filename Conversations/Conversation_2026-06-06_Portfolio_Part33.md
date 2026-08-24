# Conversation — 2026-06-06 | AIRaML Website — Animations & 3D Planning (Part 33)

**Date:** 2026-06-06
**Project:** ml-portfolio (Vercel) — AIRaML full website
**Continued from:** Part 32

---

## Fixes This Session

### Capgemini Title Corrected
- Changed "Data Engineer" → **"Consultant B2"** in `Timeline.tsx`
- User clarified: official Capgemini title is Consultant B2, not Data Engineer

### NewsAPI Query Tightened
Updated `/api/news/route.ts` to search only for AI/ML terms:
```
"artificial intelligence" OR "machine learning" OR "deep learning" OR
"large language model" OR "generative AI" OR "neural network" OR "MLOps"
```
Free tier only allows keyword filtering — no topic categories. This is the tightest possible filter.

---

## Environment Variables — Vercel Setup

To add `RESEND_API_KEY` and `NEWSAPI_KEY` in Vercel:
1. vercel.com → project → **Settings** → **Environment Variables**
2. Add each key with value, tick all 3 environments (Production, Preview, Development)
3. Save → go to Deployments → Redeploy latest

- **RESEND_API_KEY**: from resend.com → Dashboard → API Keys → Create API Key
- **NEWSAPI_KEY**: from newsapi.org → free developer account → API key on dashboard

Contact form sends email only when `RESEND_API_KEY` is set. Falls back to `console.log` otherwise.
News Industry tab shows "configure key" message when `NEWSAPI_KEY` is missing.

---

## Planned — 3D Animation Overhaul (Next Session)

User wants website to be like Resend (resend.com) — heavily animated, 3D interactive, premium feel.

### Three components (all approved by user):

| Component | Location | Tech | Status |
|---|---|---|---|
| Neural Network 3D sphere (rotating nodes + connections) | Hero — centerpiece | `@react-three/fiber` + `@react-three/drei` | Pending |
| Rotating data cube (metrics on each face) | Skills or About section | Pure CSS 3D | Pending |
| Particle/dot grid + magnetic buttons + scroll reveals | Site-wide | Framer Motion + CSS | Pending |

### What Resend has that we need to add:
- 3D rotating centerpiece in hero (→ neural network sphere for AIRaML)
- Interactive particle/dot grid background (responds to mouse)
- Magnetic buttons (follow cursor when hovering near)
- Much more dramatic scroll-triggered reveals per section
- Gradient noise mesh background (not flat color)
- Heavy glassmorphism with inner glow on cards

### Bundle note:
Three.js (`@react-three/fiber`) adds ~200–300KB. Vercel/CDN handles this fine. Worth it for the visual impact.

---

## Current Site State (Committed: c1c9eb4)

All 10 sections live on Vercel:
- Hero, About, Skills, Projects, Pipeline, News, Timeline, Contact, Footer
- arXiv papers tab works immediately (no key needed)
- Industry news tab needs `NEWSAPI_KEY` in Vercel
- Contact form needs `RESEND_API_KEY` in Vercel

---

## Standing Rules

- Apply changes to ALL affected repos simultaneously
- Conversation logs in `ML-Iris/Conversations/`
- Light theme: ALL elements must adapt
- Vercel = AIRaML website only; Render = ML apps
- `vision_cache/` and `.mcp.json` must never be committed
- Never guess root cause on production issues — get logs first
- User can edit all content (timeline, skills, bio) — it's all in TSX data arrays at the top of each file
