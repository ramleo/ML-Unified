# Conversation – 2026-06-03 (Part 10): Portfolio Website + Bug Fixes

---

## What Was Done This Session

### 1. Portfolio Website Built (Points 7–10)

**Repo:** `github.com/ramleo/ML-Portfolio`  
**Live URL:** `https://ml-portfolio-rho.vercel.app`  
**Tech:** Next.js 16 + Tailwind CSS v4 + TypeScript  
**Hosted on:** Vercel

**Structure:**
```
ml-portfolio/
  src/
    app/
      globals.css       CSS variables for dark/light theme
      layout.tsx        Metadata + no-flash theme script
      page.tsx          Assembles all sections
    components/
      Navbar.tsx        Fixed nav, blur backdrop, theme toggle
      Hero.tsx          Gradient hero, stats row, CTA buttons
      ProjectCard.tsx   Card per project (accent bar, metrics, tags, buttons)
      About.tsx         Bio + grouped tech stack pills
      ThemeToggle.tsx   localStorage-based dark/light toggle
    data/
      registry.json     Single source of truth for all project data
```

**registry.json entries:**
| Project | Model | Task | Metric | URL |
|---|---|---|---|---|
| Iris Species Classifier | Random Forest | Classification | 96.7% Accuracy | ml-iris-with-frontend.onrender.com |
| Titanic Survival Predictor | Gradient Boosting | Classification | 82.5% Accuracy | ml-titanic-with-frontend.onrender.com |
| Diabetes Risk Predictor | Random Forest | Classification | 77.5% Accuracy | ml-diabetes-with-frontend.onrender.com |
| Insurance Premium Predictor | Gradient Boosting | Regression | ±668 MAE | ml-insurance-with-frontend.onrender.com |

**Design decisions:**
- Dark mode default, light mode toggle (☀/☾), persists via localStorage
- No-flash script injected in `<head>` before React hydrates
- CSS variables (`--bg`, `--text`, `--border` etc.) for theming — no Tailwind dark: prefix needed
- Each project card has unique accent color bar at top
- "Launch App" button opens Render URL in new tab
- GitHub icon button links to each repo
- Footer note: "first load may take ~15s to spin up" (Render free tier cold start)

**Deployment:**
- Vercel connects to GitHub via OAuth + installs webhook
- Every `git push origin main` triggers automatic redeploy
- Build: `npm run build` → static HTML + JS served from Vercel CDN

---

### 2. Bug Fixes Across All 4 ML Projects

**Problem:** Clear button did not hide the prediction result panel — result stayed visible after clearing fields.  
**Fix:** Added 3 lines to `clearAllFields()` in all projects:
```javascript
emptyState.style.display  = 'flex';
resultState.style.display = 'none';
if (typeof errState !== 'undefined') errState.style.display = 'none';
```

**Problem:** Insurance (`ml-insurance-with-frontend`) had no Fill Sample button or `clearAllFields()` function.  
**Fix:** Added both functions + Fill Sample button HTML + light mode CSS.

Insurance sample data used:
```javascript
{"Annual Income": 75000, "Previous Claims": 1, "Credit Score": 680,
 "Insurance Duration": 8, "Health Score": 72.5, "Age": 35,
 "Number of Dependents": 2, "Vehicle Age": 5, "Gender": "Male",
 "Marital Status": "Married", "Education Level": "Bachelor's",
 "Occupation": "Employed", "Location": "Urban",
 "Policy Type": "Comprehensive", "Smoking Status": "No",
 "Exercise Frequency": "Weekly", "Property Type": "House"}
```

---

### 3. Commits This Session

| Repo | Commit | Description |
|---|---|---|
| ML-Portfolio | `013afed` | Build ML portfolio: Navbar, Hero, ProjectCard, About, registry |
| ML-Titanic | `19b4108` | Fix: Clear button now resets prediction result panel |
| ML-Iris | `b2c2bba` | Fix: Clear button now resets prediction result panel |
| ML-Diabetes | `52ba06c` | Fix: Clear button now resets prediction result panel |
| ML-Insurance | `aa508bf` | Add Fill Sample button, clearAllFields, light mode Clear CSS |

---

### 4. Architecture Clarified

```
ml-portfolio-rho.vercel.app     ← Vercel (Next.js showcase, no ML)
         │
         │  "Launch App" buttons link to →
         │
         ├── ml-iris-with-frontend.onrender.com        (Render, FastAPI + ML)
         ├── ml-titanic-with-frontend.onrender.com     (Render, FastAPI + ML)
         ├── ml-diabetes-with-frontend.onrender.com    (Render, FastAPI + ML)
         └── ml-insurance-with-frontend.onrender.com   (Render, FastAPI + ML)
```

- **Vercel** = portfolio only (JavaScript/Next.js, no Python support)
- **Render** = ML prediction APIs (Python/FastAPI + .pkl model files)
- They are fully independent — Vercel just has links pointing to Render URLs

---

### 5. Unified Template Idea (Proposed, Not Yet Built)

User suggested: instead of 4 separate Render deployments, build one unified app where:
- User selects or uploads a dataset
- Backend auto-processes (classification or regression)
- Frontend adapts dynamically — same UI, only theme changes
- Add new model by uploading CSV, no new repo needed

This aligns with ML-Pipeline-Auto but taken to a multi-model serving platform level.
**Status: planned for future session.**

---

## Standing Rules
- Apply changes to ALL affected repos simultaneously
- Also push to `ML-Pipeline-Auto` (+ re-embed `bootstrap.py`) for template changes
- Conversation logs stored in `ML-Iris/` folder
- Light theme: ALL elements must adapt — overlays, text, images, buttons, icons
- Vercel = portfolio only; Render = ML projects (Python backend)

## Next Steps (Remaining Points)
- ⬜ Unified ML platform (proposed this session)
- ⬜ MLflow experiment tracking (Point 14)
- ⬜ Data drift / model drift detection (Point 13)
- ⬜ Monitoring — Grafana + Prometheus (Point 12)
- ⬜ Test-gate CI (Point 17)
- ⬜ E2E browser testing — Playwright (Point 18)
- ⬜ Full pipeline validation commit → live (Point 19)
- ⬜ CNN / deep learning project (Point 15)
- ⬜ Data injection (DB, cloud, real-time) (Point 16)
