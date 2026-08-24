# Conversation — 2026-06-18 — ML-Unified — Part 101

---

## Session Summary

Continuation from Part 100. Focus: building the 5 Step 3 ml-portfolio tool pages, wiring them correctly, and beginning the platform independence refactor.

---

## Changes This Session

### 1. Built 5 Step 3 Tool Pages (`844890a`)

Created dedicated `/tools/*` pages for all 5 remaining Step 3 capabilities:

| Page | Route | Accent | Type |
|---|---|---|---|
| Feature Engineering | `/tools/feature-engineering` | `#38bdf8` | Static showcase (later replaced) |
| Feature Selection | `/tools/feature-selection` | `#fb923c` | Static showcase |
| Optuna Tuning | `/tools/optuna` | `#a78bfa` | Static showcase |
| SHAP Explainability | `/tools/shap` | `#f59e0b` | Static showcase |
| Ensemble Methods | `/tools/ensemble` | `#f472b6` | Static showcase |

All follow tool page standard: `ConstellationBackground`, no outer background, no wrapper card, tabbed sections, stats rows, key insight cards.

### 2. Wired Cards to Internal Routes (`b77e15f`)

- Added `internalLink?: string` field to `Capability` type in `capabilities.ts`
- Set `internalLink` for all 5 Step 3 capabilities
- Updated `MLCapabilities.tsx` to add a third button branch: `internalLink` → shows "Try it", navigates via `router.push()`, no Render call

**Root cause of bug:** `modalEnabled` was not set → fell to "Launch App" branch → `window.open(ml-unified.onrender.com)`.

### 3. Feature Engineering — Real Interactive Tool (`557e784` → `e119405`)

First built with Render backend (`/feature-engineer` endpoint), then correctly moved to fully client-side after user pointed out platform independence requirement.

**Final version (`e119405`):** Everything runs in the browser:
- CSV parsing in JavaScript
- Column analysis (types, skew, missing counts)
- Transforms: log1p, sqrt, percentile rank, outlier flag, missing flag, equal/quantile binning
- Date extraction (year, month, day, dayofweek, hour, quarter)
- Interaction terms (col A × col B)
- Polynomial cross-terms (degree 2, all pairwise products)
- Download via `Blob` + `URL.createObjectURL`

No API calls, no server, data never leaves browser. "runs in browser" badge shown in header.

### 4. Removed Hardcoded Render Fallback (`0eb281f`)

`src/config/urls.ts` previously had:
```ts
export const ML_UNIFIED_API =
  process.env.NEXT_PUBLIC_ML_UNIFIED_URL ?? "https://ml-unified.onrender.com";
```

Changed to: no fallback — `NEXT_PUBLIC_ML_UNIFIED_URL` must be set explicitly. Logs a warning if missing. Frontend now works with any backend URL (Render, HF Spaces, Railway, localhost).

### 5. Preprocessing — Fully Client-Side (`edc623b`)

Created `src/lib/preprocessing.ts` containing all computation:
- CSV parser (handles quoted fields, CRLF)
- `analyzeCSV()` — column type detection, skew, mean, std, min, max, missing counts
- `preprocessCSV()` — full preprocessing pipeline:
  - Duplicate removal
  - Column dropping
  - Missing value imputation: mean, median, most_frequent, ffill, bfill, constant, drop rows
  - **KNN imputation (k=5)** — Euclidean distance on normalized numeric features
  - **MICE imputation** — OLS regression via Gaussian elimination, 5 iterations
  - Outlier removal (IQR method: Q1 - 1.5×IQR to Q3 + 1.5×IQR)
  - Skewness fix (log1p for skew > 1 on positive columns)
  - Encoding: One-Hot, Ordinal (label), Frequency, Target
  - Z-score standardization
- CSV serializer

Updated `preprocessing/page.tsx`:
- Removed `import { ML_UNIFIED_API }` — no API imports at all
- `analyze()` now reads file as text, calls `analyzeCSV()` client-side
- `handlePreprocess()` now calls `preprocessCSV()` client-side (setTimeout 50ms to allow spinner to render)
- `downloadCSV()` uses `Blob([result.csvText])` directly
- `passToAutoML()` encodes `csvText` to base64 using `btoa()` for sessionStorage handoff to AutoML page
- Added "runs in browser" badge to header

---

## Platform Independence — Concepts Established

### What "platform independent" means for this app

```
Platform Independence
│
├── Frontend (ml-portfolio) — Next.js static export
│   ├── urls.ts fallback removed ✓
│   ├── Feature Engineering → client-side ✓
│   ├── Preprocessing → client-side ✓
│   ├── Feature Selection → client-side (todo)
│   └── Navigation links → env var driven (todo)
│
└── Backend (ML-Unified) — FastAPI in Docker
    ├── Docker image = runs identically on any platform
    ├── Deploy to Render → set NEXT_PUBLIC_ML_UNIFIED_URL=https://render-url
    ├── Deploy to HF Spaces → set NEXT_PUBLIC_ML_UNIFIED_URL=https://hf-url
    ├── Deploy to Railway → set NEXT_PUBLIC_ML_UNIFIED_URL=https://railway-url
    └── Run locally → set NEXT_PUBLIC_ML_UNIFIED_URL=http://localhost:8000
```

### Key insight: Docker is the foundation
Docker makes the backend platform-independent — same image runs everywhere. The only thing that changes between platforms is the env var pointing the frontend at the backend.

### What still needs a backend (legitimately)
- AutoML training (scikit-learn model competition)
- Optuna tuning (actual hyperparameter search, 30 trials)
- SHAP explainability (trained model + SHAP computation)
- Ensemble methods (model training)

These tools will always need the Docker backend — they do real compute.

### What runs entirely in browser (no backend)
- Feature Engineering ✓
- Preprocessing ✓
- Feature Selection (todo)

---

## Commits This Session

| Hash | Repo | Description |
|---|---|---|
| `844890a` | ml-portfolio | feat(tools): add 5 Step 3 tool pages |
| `b77e15f` | ml-portfolio | fix(capabilities): wire Step 3 cards to internal routes, show Try it |
| `557e784` | ml-portfolio | feat(feature-engineering): initial interactive tool (with Render — later replaced) |
| `99df567` | ML-Unified | feat(api): add /feature-engineer endpoint (later unused) |
| `e119405` | ml-portfolio | refactor(feature-engineering): move all processing client-side |
| `0eb281f` | ml-portfolio | fix(config): remove hardcoded Render fallback from API URL |
| `edc623b` | ml-portfolio | feat(preprocessing): move all processing client-side — KNN, MICE, OHE |

---

## Pending Backlog

### Platform Independence (in progress)
- [ ] Feature Selection → client-side
- [ ] Navigation links (capabilities.ts, PipelineShowcase.tsx, Footer.tsx) → env var driven
- [ ] Backend HF startup model download → bake into Docker image

### ml-portfolio — Step 3 pages
- [ ] Feature Selection page → real interactive tool (client-side)
- [ ] Optuna, SHAP, Ensemble — static showcases are fine (need backend)

### ml-portfolio — Step 4
- [ ] Pipeline builder UI

### ML-Unified backlog
- [ ] Fix `showAutoMLWizard()` always starting fresh (line ~4566)
- [ ] Phase 9: Ensemble / stacking
- [ ] Phase 10: Pipeline export (.pkl / Python script)
- [ ] Phase 11–13: Encoding options, GPU, SMOTE
- [ ] Retrain 80 Cereals model
- [ ] Verify AdaBoost winner-training branch exists in app.py

---

## Process Reminders
- NO EMOJIS
- Always report short git hash with every commit
- Always push to GitHub after every commit
- ConstellationBackground on every new tool page
- No single wrapper card — render directly on page background
- TSC is always truth for TypeScript — never trust IDE diagnostics
- All portfolio tool pages that do data manipulation → client-side, no backend
- Tools that need actual ML training (AutoML, Optuna, SHAP, Ensemble) → Docker backend
