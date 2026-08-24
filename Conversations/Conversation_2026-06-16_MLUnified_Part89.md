# Conversation — 2026-06-16 — ML-Unified — Part 89

---

## Session Summary

Fixed MLCapabilities cards (equal height + Try it buttons), discussed URL versatility, standalone card execution, and pipeline architecture. No ML-Unified changes this session — all work in ml-portfolio.

---

## Fixes Applied to ml-portfolio

### 1. Try it buttons added (`eafee21`)
Each capability card now has a CTA button that opens ML Unified in a new tab, passing current theme + palette params.

### 2. Equal card heights fixed (same commit)
- `alignItems: "stretch"` on scroll container
- `display: "flex"` on each snap wrapper div
- `height: "100%"` on each card's motion.div

---

## Discussions & Decisions

### URL Versatility (not yet implemented)
User asked why cards link to Render. Answer: hardcoded `ml-unified.onrender.com` in `capabilities.ts`.

**Agreed approach: Layer 1 + Layer 2**
- `src/config/urls.ts` — single config file, all external links in one place
- `process.env.NEXT_PUBLIC_ML_UNIFIED_URL` — env var overrides, no code change to switch platforms
- Not yet implemented — queued for next session

### Why HF Space starts on Diabetes Risk Predictor
ML Unified has no landing/home screen. On load it runs `selectModel(allModels[0].id)` — always picks first model. The AIRaML hero exists only on Vercel portfolio. Separate feature if user wants HF Space to show a landing screen first.

### AutoML "skips wizard" bug
Root cause: `showAutoMLWizard()` line 4566 — if `_lastAutoMLResult` is set from a previous run in the same tab, it restores results instead of starting fresh. NOT caused by portfolio link. Fix = change `showAutoMLWizard()` to always start wizard, keep last result accessible via "View Last Result". Not yet fixed — queued.

### Standalone Cards (no code yet)
Each MLCapabilities card could have a modal where user uploads CSV + fills minimal info and runs the feature directly from the portfolio without going to ML Unified.

| Card | Independent? | Needs |
|------|-------------|-------|
| AutoML | Yes | CSV + target col + task type |
| Feature Eng | Yes | CSV + column/transform config |
| SHAP | Yes | CSV + trained model (.pkl) |
| Optuna | No | Needs AutoML winner first |
| Ensemble | No | Needs 2+ trained models |

**Modal approach chosen** — cards stay visually identical, modal overlays for input. Pipeline builder lives at section level, outside cards.

### Pipeline Architecture — Agreed Sequence

**Step 1 — Data contract (next session)**
Define `MLPipelineState` type — what each card produces and consumes:
```ts
type MLPipelineState = {
  csv:        File | null
  columns:    string[]
  target:     string | null
  model:      { algo, params } | null   // AutoML → Optuna, SHAP
  tunedModel: { params } | null         // Optuna → Ensemble
  shapValues: any | null                // SHAP output
}
```

**Step 2** — AutoML standalone modal (first card end-to-end)
**Step 3** — Remaining card modals (read/write same state)
**Step 4** — Pipeline builder UI (section-level, chains existing steps)

Why this order: contract first = no rework. One card at a time validates pattern. Pipeline builder is just UI on top of already-working pieces.

---

## Commits This Session

| Hash | Repo | Description | GitHub |
|------|------|-------------|--------|
| `53f684e` | ml-portfolio | feat(capabilities): add ML Capabilities section | ✓ |
| `eafee21` | ml-portfolio | fix(capabilities): equal card heights + Try it buttons | ✓ |

---

## Pending Items

### ml-portfolio
| Priority | Item | Status |
|----------|------|--------|
| **Next** | Step 1: Design `MLPipelineState` data contract | Ready to start |
| After | Step 2: AutoML standalone modal | Waiting on Step 1 |
| After | Step 3: Remaining card modals | Waiting on Step 2 |
| After | Step 4: Pipeline builder UI (section-level) | Waiting on Step 3 |
| Future | `src/config/urls.ts` + env var for URL versatility | Not started |
| Future | Dockerize (`Dockerfile` + `output: 'standalone'`) | Not started |

### ML-Unified
| Priority | Item | Status |
|----------|------|--------|
| Bug | `showAutoMLWizard()` — always start wizard, not last result | Not fixed |
| Next | Phase 9: Ensemble / stacking (NOT in AutoML Step 2) | Not started |
| Low | Phase 10–13 (Pipeline export, Encoding, GPU, SMOTE) | Not started |
| User action | Retrain 80 Cereals model | Pending |

---

## Process Reminders

- Playwright: maximize window (`browser_resize 1440×900`), close after deploy confirmation
- ml-portfolio: commit + push GitHub → Vercel auto-deploys
- ML-Unified: commit + push GitHub + upload to HF after every change
