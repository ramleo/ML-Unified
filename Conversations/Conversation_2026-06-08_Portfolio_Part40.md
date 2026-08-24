# Conversation — 2026-06-08 | Palette Sync + SHAP Planning (Part 40)

**Date:** 2026-06-08
**Projects:** ml-portfolio (Vercel), ML-Unified (Render)
**Continued from:** Part 39

---

## Commits This Session

| Hash | Repo | Summary |
|---|---|---|
| `40ea65f` | ml-portfolio | Pass palette param to project apps on launch |
| `9112885` | ML-Unified | Add cross-portfolio palette sync to ML Unified frontend |
| `c162cf7` | ML-Unified | Apply palette to ML Unified brand elements |

---

## Cross-Portfolio Palette Sync

### Problem
User expectation: selecting a palette in the portfolio should apply across the entire platform, including ML Unified. Previous clarification ("ML Unified is a separate app") was correct technically but missed the user's intent — they don't care about Vercel vs Render, they expect a unified experience.

### Standing Rule Added
**Every project launched from the portfolio inherits the active palette via URL parameter.** Future project apps must implement the same pattern.

### Implementation

**Portfolio side (`ProjectCard.tsx`):**
- "Launch App" button already passed `?theme=xxx`
- Now also passes `&palette=xxx` read from `localStorage.getItem("palette")`

**ML Unified side (`index.html`):**
- Added `--accent-from`, `--accent-via`, `--accent-to` CSS variables to `:root`
- Added `[data-palette="sunset/aurora/ocean"]` attribute selectors with variable overrides
- Added `setPalette()` + IIFE that reads `?palette=` from URL, applies it, saves to localStorage, cleans URL (mirrors existing `?theme=` pattern)
- ML Vision shares the same HTML file (`?mode=vision`), so one change covers all modes

### Brand Elements Updated (CSS variables)
| Element | Change |
|---|---|
| Gradient top bar | `var(--accent-from/via/to)` |
| Logo mark (circle icon) | `var(--accent-from/via/to)` |
| "ML Unified" / "ML Vision" text | `var(--accent-from/via/to)` |
| Predict / Train / Analyze buttons | `var(--accent-from/via)` |
| Live Metrics panel gradient bars | `var(--accent-from/via/to)` |

### Intentionally Unchanged
- Sidebar model dots — each model has its own identity color
- Metric pill (77.5%) — follows per-model accent
- Model card header gradient — follows per-model accent

---

## SHAP Interpreter — Plan Agreed

### Approach
Build SHAP **inside ML Unified** (not a separate portfolio card). This covers pending items #6 and #9 together.

### Backend (`ml-api`)
- `POST /shap` — takes `model_id` + input values → returns SHAP base value + per-feature contributions
- `POST /shap/custom` — accepts `.pkl` model upload + CSV row → returns SHAP breakdown for any model
- Uses `shap.TreeExplainer` (all 4 existing models are tree-based: Random Forest, Gradient Boosting)
- Add `shap` to `requirements.txt`

### Frontend (ML Unified)
- "Feature Impact" panel expands below prediction result
- Horizontal bar chart: green bars = positive contribution, red = negative
- Base value shown as baseline
- Separate "Custom Model" section: upload `.pkl` + CSV row → get SHAP chart

### Models in Scope (all 4)
- Diabetes Risk Predictor (Random Forest)
- Iris Species Classifier (Random Forest)
- Titanic Survival Predictor (Gradient Boosting)
- Insurance Premium Estimator (Gradient Boosting)

### Portfolio Update
- Update ML Unified project card description + tags to mention SHAP
- No new project card needed

### Implementation order agreed
1. Backend endpoint (`/shap`)
2. Frontend Feature Impact panel
3. Custom model upload (`/shap/custom`)
4. Portfolio card update

**Status: Planning complete, implementation not yet started**

---

## Feedback / Standing Rules Updates

### Push after commit
- **Rule added to memory:** After every commit, ask to push or push immediately — don't stop silently at commit step.
- User called this out: "why suddenly this behaviour?...you used to ask and push"

---

## Pending Task List (updated)

| # | Item | Status |
|---|---|---|
| 1 | Mobile responsiveness | ✅ Done (Part 38) |
| 2 | ruff + pytest | ✅ Done (Part 39) |
| 3 | Chatbot (portfolio-wide, context-aware) | ✅ Done (Part 39) |
| 4 | Theme palette picker | ✅ Done (Part 39) |
| 5 | Proxy page (`/app/[id]`) | Deferred — low ROI |
| 6 | SHAP Interpreter card | **Plan agreed, not started** |
| 7 | Build Pipeline mode (ML Unified) | Pending |
| 8 | Prediction confidence bar chart | Pending |
| 9 | SHAP in ML Unified | **Merged with #6** |
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

## Standing Rules (unchanged)

- Conversation logs: `ML-Iris/Conversations/Conversation_YYYY-MM-DD_Topic_PartXX.md`
- Never expose `ramleo84@gmail.com` publicly on the website
- `vision_cache/` and `.mcp.json` must never be committed
- Always run `ruff check` + `pytest` before pushing ML-Unified
- User-facing errors: plain English only
- Every project launched from portfolio inherits active palette via `?palette=xxx` URL param
- After commit: always push or ask to push — don't stop silently
