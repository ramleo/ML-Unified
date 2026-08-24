# Conversation — 2026-06-16 — ML-Unified — Part 88

---

## Session Summary

Discussed Phase 9 ensemble options, discovered the AIRaML portfolio (`ml-portfolio`), and built the `MLCapabilities` section for it. No changes to ML-Unified this session.

---

## Topics Covered

### 1. Phase 9 Ensemble / Stacking Decision

User raised two valid concerns:
- AutoML Step 2 is getting cramped (already has target, task, metric, FE, Optuna)
- There's a home page — why put more config there?

**Decision:** Ensemble does NOT go into AutoML Step 2. It will be a post-training feature elsewhere. Not yet implemented.

---

### 2. Portfolio Home Page Discovery

User shared screenshot of `https://huggingface.co/spaces/wram1708/ml-unified` — an AIRaML portfolio page (not the ML Unified app).

**Portfolio details:**
- Local: `/Users/wrks/Downloads/Claude-documentation/Projects/ml-portfolio`
- GitHub: `https://github.com/ramleo/ML-Portfolio`
- Deployed: `https://ml-portfolio-rho.vercel.app/`
- Framework: Next.js 16 / React 19 / TypeScript
- Local and GitHub were confirmed in sync (`git status` → up to date, nothing uncommitted)

**Page section order:**
`Hero → About → Skills → ProjectsSection → PipelineShowcase → NewsSection → Timeline → Contact → Footer`

**Existing 3 project cards** (in `src/data/registry.json`):
1. ML Unified Platform
2. EDA Explorer
3. ML Vision Platform

---

### 3. MLCapabilities Section — Built & Deployed

Added a new `ML Capabilities` section between `ProjectsSection` and `PipelineShowcase`.

**Layout rule (user's specification):**
- Odd count OR < 6 cards → horizontal scroll strip
- Even count AND ≥ 6 → 3-column grid
- Mobile → always horizontal scroll

Currently 5 cards (odd) → horizontal scroll. When Phase 9 ensemble is added as card 6 (even) → auto switches to 3×2 grid.

**Portability design:** Fully self-contained. To move to another page: remove import + `<MLCapabilities />` from `page.tsx`, add both anywhere else. No other changes needed.

**Cards (in `src/data/capabilities.ts`):**

| Card | Accent | Tags |
|------|--------|------|
| AutoML Pipeline | `#34d399` green | scikit-learn, XGBoost, LightGBM, CatBoost |
| Optuna Tuning | `#a78bfa` purple | Optuna, TPE Sampler, 5-fold CV |
| Feature Engineering | `#38bdf8` blue | Transforms, Interactions, Date Features, Binning |
| SHAP Explainability | `#f59e0b` amber | SHAP, Feature Impact, Classification, Regression |
| Ensemble Methods | `#f472b6` pink | Voting, Stacking, Meta-Learner, scikit-learn |

**Files created/modified:**
- `src/data/capabilities.ts` — card data only, edit here to change content
- `src/components/MLCapabilities.tsx` — self-contained display component
- `src/app/page.tsx` — added import + `<MLCapabilities />` between Projects and Pipeline

**Build:** Clean (`npm run build` ✓ no errors)
**Playwright verified:** Both ends of horizontal scroll strip visible and correct

---

### 4. Portability / Dockerization (discussed, not implemented)

For moving the portfolio freely between Vercel → Render → HF Space → GCP:
- Add `Dockerfile` with multi-stage build (node:alpine → build → serve)
- Add `output: 'standalone'` to `next.config.ts` — cuts image size ~800MB → ~150MB
- No other changes needed; all platforms read Dockerfile automatically

Not implemented yet — noted for future.

---

## Commit This Session

| Hash | Repo | Description | GitHub |
|------|------|-------------|--------|
| `53f684e` | ml-portfolio | feat(capabilities): add ML Capabilities section between Projects and Pipeline | ✓ pushed |

### Deploy Notes

- `src/data/capabilities.ts` — all card data (title, description, accent color, tags, icon ID). Edit cards here, nothing else changes.
- `src/components/MLCapabilities.tsx` — self-contained display component. Zero page-level dependencies.
- `src/app/page.tsx` — one import + one `<MLCapabilities />` line. Remove both to relocate.

**To move to another page later:** delete those 2 lines from `page.tsx`, add `import MLCapabilities from "@/components/MLCapabilities"` + `<MLCapabilities />` wherever you want. No other changes needed.

Vercel auto-deploys from GitHub push — live within ~1 min of push.

---

## Pending Items

### ML-Unified
| Priority | Item | Status |
|----------|------|--------|
| Next | Phase 9: Ensemble / stacking (NOT in AutoML Step 2 — location TBD) | Not started |
| Low | Phase 10: Pipeline export | Not started |
| Low | Phase 11: Encoding per-column | Not started |
| Low | Phase 12: GPU toggle | Not started |
| Low | Phase 13: SMOTE | Not started |
| User action | Retrain 80 Cereals model | Pending |

### ml-portfolio
| Priority | Item | Status |
|----------|------|--------|
| Future | Dockerize (`Dockerfile` + `output: 'standalone'`) | Not started |
| Future | Add Ensemble card when Phase 9 ships (will auto-switch to 3×2 grid) | Waiting on Phase 9 |

---

## Process Reminders

- Playwright: maximize window on open (`browser_resize 1440×900`), close after deploy confirmation
- Always screenshot UI before deploying
- ML-Unified: commit ID + push GitHub + upload HF after every change
- ml-portfolio: commit + push GitHub (Vercel auto-deploys)
