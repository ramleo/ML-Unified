# Conversation — 2026-06-06 | Portfolio → Full AIRaML Website (Part 32)

**Date:** 2026-06-06
**Project:** ml-portfolio (Vercel) → Full AIRaML website rebuild
**Continued from:** Part 31 (EDA), Part 28 (Portfolio)

---

## Context

User decided to evolve the portfolio page into a full professional website branded "AIRaML". Resume was read and all content captured. Career update: not at JoulestoWatts anymore.

---

## Career Timeline (Corrected)

| Company | Role | Period |
|---|---|---|
| Statestreet Syntel Services | Associate | Jun 2006 – Jun 2010 |
| Valuegain Distributors | BD Executive | Apr 2012 – Oct 2013 |
| Veenus Cybersoft | Junior Executive | Oct 2013 – May 2014 |
| SBI Life Insurance | BD Executive | May 2014 – Jul 2017 |
| JoulestoWatts Business Solutions | Support Engineer | Nov 2024 – Nov 2025 |
| **Capgemini** | **Data Engineer** | **Dec 2025 – Present** |

**Note:** Official title at Capgemini is Data Engineer but actually works as Support Engineer at client site. User doesn't have deep DE expertise — website should NOT emphasize Data Engineering. Show the title as-is, no description.

---

## Items 14–25 Implemented (Previous Session)

All 12 animation/UX items completed:
- #14 3D card tilt, #15 staggered entrance, #16 typewriter + blobs, #17 per-accent glow
- #18 tag filter AnimatePresence, #19 count-up on scroll
- #20 top border, #21 2rem stats, #22 -4px lift, #23 dark gradient bottom
- #24 equal card heights, #25 6rem AIRaML headline
- framer-motion@12.40.0 installed

---

## Full Website Rebuild — AIRaML

### Architecture Decision
- Brand: AIRaML (not "portfolio")
- URL: Vercel deployment (unchanged)
- No microservices needed — Next.js API routes handle everything
- Docker: planned for ML backend (ml-api), NOT for Next.js site

### Complete Section Map

| # | Section | Status |
|---|---|---|
| 1 | Hero | Rewriting — more dramatic |
| 2 | About | Done — resume content, avatar placeholder, education |
| 3 | Skills | Building — 6 categories |
| 4 | Live Apps/Projects | Existing (tag filter, 3D tilt, glow) |
| 5 | ML Pipeline Showcase | Building — interactive 7-stage diagram |
| 6 | AI News Feed | Building — arXiv API + NewsAPI (env var) |
| 7 | Experience Timeline | Building — animated vertical timeline |
| 8 | Contact | Building — form + social links |
| 9 | Footer | Building — animated |

### Special Features
- **AI News Feed**: Two tabs — Research Papers (arXiv, free, no key) + AI News (NewsAPI, requires NEWSAPI_KEY env var)
- **ML Pipeline**: 7 interactive stages: Data Ingestion → EDA → Feature Engineering → Model Training → Evaluation → Deployment → Monitoring (MLFlow — coming soon)
- **Contact form**: Next.js API route → Resend (requires RESEND_API_KEY env var), gracefully falls back to console.log

### Skills (6 Categories from Resume)

| Category | Accent | Skills |
|---|---|---|
| Machine Learning | Indigo | Linear/Logistic Reg, RF, XGBoost, SVM, KNN, KMeans, SMOTE... |
| Deep Learning | Violet | ANN, CNN, RNN, LSTM, Transfer Learning, VGG16/19, ResNet50... |
| Generative AI | Amber | Transformers, RAG, AI Agents, LangChain, LangGraph |
| NLP | Emerald | Word2Vec, LSTM, Sentiment Analysis, Topic Modeling, POS Tagging |
| Computer Vision | Sky | Image Classification, Object Detection, Segmentation, ONNX, YOLO |
| MLOps & Tools | Rose | Python, FastAPI, Flask, Docker, GCP, SHAP, LIME, MLFlow, SQL |

---

## Files Created This Session

| File | Type | Purpose |
|---|---|---|
| `src/app/api/news/route.ts` | New | arXiv + NewsAPI feed |
| `src/app/api/contact/route.ts` | New | Contact form handler (Resend) |
| `src/app/globals.css` | Updated | Full CSS overhaul — section styles, skill chips, timeline, pipeline, form |
| `src/components/About.tsx` | Updated | Full rewrite with resume content |
| `src/components/Navbar.tsx` | Updated | All 7 nav links + Resume download button |
| `src/components/Hero.tsx` | Updated | More dramatic (in progress) |
| `src/components/Skills.tsx` | New | 6 skill categories (in progress) |
| `src/components/PipelineShowcase.tsx` | New | 7-stage ML pipeline (in progress) |
| `src/components/NewsSection.tsx` | New | arXiv + NewsAPI tabs (in progress) |
| `src/components/Timeline.tsx` | New | Career + education timeline (in progress) |
| `src/components/Contact.tsx` | New | Form + social links (in progress) |
| `src/components/Footer.tsx` | New | Animated footer (in progress) |
| `src/app/page.tsx` | Updated | All sections composed |

---

## Environment Variables Needed (Render / Vercel)

| Variable | Service | Required? |
|---|---|---|
| `NEWSAPI_KEY` | Vercel | Optional — news tab shows message if missing |
| `RESEND_API_KEY` | Vercel | Optional — contact form logs to console if missing |

---

## Pending Items (Larger Roadmap)

- Data drift monitoring + MLFlow integration
- Card click drawer/modal (full project detail)
- Dockerize ml-api backend
- Playwright frontend automation tests
- 35 EDA tests (deferred)
- EDA microservice extraction
- Portfolio animations (items 14–25) — DONE this session

---

## Standing Rules

- Apply changes to ALL affected repos simultaneously
- Conversation logs in `ML-Iris/Conversations/`
- Light theme: ALL elements must adapt
- Vercel = portfolio/website only; Render = ML apps
- `vision_cache/` and `.mcp.json` must never be committed
- User-facing errors: plain English only
- Never guess root cause on production issues — get logs first
- PDF export: off-screen rendering only
- Chart capture: never resize live charts
