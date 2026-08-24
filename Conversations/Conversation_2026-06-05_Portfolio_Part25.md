# Conversation — 2026-06-05 | Live Metrics Polish + ML Unified Improvement Discussion (Part 25)

**Date:** 2026-06-05
**Project:** ML-Unified · ml-portfolio

---

## Points Completed This Session

| # | Item | Status |
|---|---|---|
| 1 | Raw JSON ↗ button in Live Metrics panel | ✅ Done |
| 2 | Fix metrics panel: stats layout, 100% errors, favicon, browser title, instant load | ✅ Done |
| 3 | Microservices restructure (partial — interrupted by user) | ⏸ Paused |
| 4 | Mode-specific metrics (ML Unified shows only ml-api, ML Vision shows only ml-vision) | ✅ Done |
| 5 | Details ▾ toggle: hide endpoint rows by default, expand on demand | ✅ Done |
| 6 | Friendly endpoint names + grouping (/schemas/iris + /predict/iris → Iris) | ✅ Done |
| 7 | Details always visible + known items pre-populated + hide internal paths | ✅ Done |
| 8 | ML Unified improvement discussion (pipeline vs dataset vs model-centric) | ✅ Discussed |

---

## 1. Raw JSON ↗ Button

Added a small pill button next to each service label in the Live Metrics panel.
Clicking opens `<service-url>/metrics` in a new tab — no manual URL typing needed.

**Commit:** `b9da9d4`

---

## 2. Metrics Panel — 5 Fixes in One Commit

### Fix 1: Stats chips wrapping in light theme
- **Root cause:** `display:flex;flex-wrap:wrap` — chips overflowed to a new row in light theme
- **Fix:** Changed to `display:grid;grid-template-columns:repeat(5,1fr)` — always 5 fixed columns, never wraps

### Fix 2: 100% error rate in ML Vision
- **Root cause:** Browser auto-requests `/favicon.ico` on every page load. ml-vision had no `/favicon.ico` route → 404 → logged → 100% error rate
- **Fix:** Added `"/favicon.ico"` to ml-vision `_SKIP_PATHS`

### Fix 3: Favicon missing
- **Root cause:** No `<link rel="icon">` in HTML; SVG emoji approach unreliable cross-browser
- **Fix:** Copied `ml-portfolio/src/app/favicon.ico` → `ml-api/frontend/favicon.ico`; added `/favicon.ico` FastAPI route; changed `<link rel="icon" href="/favicon.ico">`

### Fix 4: Wrong browser tab title
- **Root cause:** `<title>` was static "ML Unified — Multi-Model Predictor" regardless of mode
- **Fix:** Added `document.title` update inside `applyNavMode()` IIFE:
  - `?mode=vision` → "ML Vision — Computer Vision Platform"
  - `?mode=ml` → "ML Unified — Multi-Model Predictor"

### Fix 5: Slow panel open
- **Root cause:** Metrics only fetched when panel opens — user waits for both API calls
- **Fix:** Pre-fetch on `window load` event; cache result in `_metricsCache`; panel shows cached data instantly, then background-refreshes

**Commit:** `0a807b5`

---

## 3. Microservices Restructure (Paused)

**Plan agreed but interrupted by user. Partial files created — not yet complete.**

Planned split:

```
ml-api/
  app.py              ← thin assembler
  routers/
    monitoring.py     ← /metrics + middleware
    config.py         ← /, /health, /app-config
    inference.py      ← /models, /schemas, /predict
    training.py       ← /train, /analyze
    unsupervised.py   ← /unsupervised
  shared/
    paths.py          ← HERE, SCHEMA_DIR, MODEL_DIR, FRONTEND
    registry.py       ← MODELS dict, load_models(), slugify()

ml-vision/
  app.py              ← thin assembler
  routers/
    monitoring.py, health.py, classifier.py
    processing.py, detection.py, segmentation.py
  shared/
    paths.py, cache.py
```

Files created so far (not committed):
- `ml-api/shared/__init__.py`, `paths.py`, `registry.py`
- `ml-api/routers/__init__.py`, `monitoring.py`, `config.py`, `inference.py`
- ml-vision equivalents: `__init__.py` files only

**Status:** Resume in next session. Need to complete `training.py`, `unsupervised.py`, ml-vision routers, update `app.py`, update tests.

---

## 4. Mode-Specific Metrics

**Problem:** Live Metrics panel always showed both ML Unified + ML Vision sections regardless of which platform was open.

**Fix:** `_fetchMetrics()` and `_renderMetrics()` now branch on `APP_MODE`:

```js
if (APP_MODE === 'vision') {
  // fetch + render ML Vision only
} else if (APP_MODE === 'ml') {
  // fetch + render ML Unified only
} else {
  // fetch + render both (default)
}
```

| URL | Panel shows |
|---|---|
| `?mode=ml` | ML Unified stats only |
| `?mode=vision` | ML Vision stats only |
| no mode | Both sections |

**Commit:** `20ad73f`

---

## 5. Details Toggle — Endpoint Breakdown Hidden by Default

**User feedback:** "Why are endpoints shown? Any specific reason?"

**Decision:** Hide per-endpoint rows by default. Add "Details ▾/▴" toggle to expand on demand.

**Implementation:**
- `_metricsDetailsOpen = {}` — persists open/closed state across 30s auto-refresh
- `_toggleMetricsDetails(key)` — toggles display:none/block on details div, updates button text
- Button always present; chevron flips between ▾ (closed) and ▴ (open)

**Commit:** `7693d34`

---

## 6. Friendly Endpoint Names + Grouping

**User feedback:** "Don't show `/models` path — show 'Insurance', 'Titanic' etc. User doesn't need to know the path."

**`_friendlyEndpoints(endpoints, key)` function:**

Path → friendly name mapping:
| Path | Friendly Name |
|---|---|
| `/schemas/iris` or `/predict/iris` | Iris |
| `/schemas/diabetes` or `/predict/diabetes` | Diabetes |
| `/schemas/titanic` or `/predict/titanic` | Titanic |
| `/schemas/insurance` or `/predict/insurance` | Insurance |
| `/train` | Training |
| `/unsupervised` | Clustering |
| `/analyze` | CSV Analysis |
| `/classify-image` | Classifier |
| `/process-image` | Processing |
| `/detect-objects` | Detection |
| `/segment-image` | Segmentation |

**Grouping:** `/schemas/iris` + `/predict/iris` → single "Iris" row with combined request count and max p95.

**Commit:** `7693d34`

---

## 7. Details Always Visible + Known Items + Hide Internal Paths

**Three user requests in one:**

### 7a. Details button always visible
- **Before:** Button hidden when 0 requests ("No requests yet" shown instead)
- **After:** Button always rendered; details section shows known items dimmed when no activity

### 7b. Known items always pre-populated
Items always shown even before first request — dimmed with `—` placeholder:

```js
const _METRICS_KNOWN = {
  ml:     ['Iris', 'Titanic', 'Diabetes', 'Insurance', 'Training', 'Clustering'],
  vision: ['Classifier', 'Processing', 'Detection', 'Segmentation'],
};
```

Active items show count + latency bar. Inactive items show dimmed row with `—`.

**User rationale:** "User will not understand why it is not showing. Think from user perspective."

### 7c. Hide internal/infrastructure paths
```js
const _METRICS_SKIP = new Set([
  '/models', '/image-models', '/detect-models', '/seg-models',
  '/imagenet-classes', '/image-operations',
]);
```

These are background calls the frontend makes automatically — not user actions, not useful in Details.

**Commit:** `e4b8557`

---

## 8. ML Unified Improvement Discussion

**User's 3 questions:**

**Q1 — Dataset-centric (current)?**
- Good for quick demos; shows specific use cases
- Problem: fixed showcase, user can't bring their own problem

**Q2 — Model-centric (like unsupervised)?**
- More flexible; algorithm is starting point
- Problem: real ML doesn't start with "I want Random Forest"

**Q3 — Full ML pipeline?**
- Best direction; makes it a platform not just a demo

**Recommended approach — hybrid:**

| Section | What it does |
|---|---|
| Quick Predict (keep) | Pre-trained models on curated datasets — fast demo |
| Build Pipeline (new) | Step-by-step: Load → Explore → Train → Evaluate → Deploy |
| Unsupervised (keep) | Clustering / dimensionality reduction on any CSV |

**Full pipeline steps:**
1. Load → upload CSV or pick built-in dataset
2. Explore → EDA: shape, distributions, missing values, correlations
3. Preprocess → handle nulls, encoding, scaling
4. Train → choose algorithm, hyperparameters
5. Evaluate → metrics, confusion matrix, SHAP feature importance
6. Deploy → model becomes live prediction endpoint
7. Monitor → prediction distribution, data drift alerts

**Priority order:**
1. EDA step (high value, moderate effort)
2. Evaluation report (confusion matrix, feature importance)
3. SHAP explainability
4. Pipeline stepper UI
5. Data drift monitoring (Phase 4)

**Status:** Discussed only — implementation not started yet.

---

## All Commits This Session

| Hash | Description |
|---|---|
| `b9da9d4` | Add Raw JSON button to Live Metrics panel |
| `0a807b5` | Fix metrics panel: layout, 100% errors, favicon, title, instant load |
| `d10f2ec` | Fix metrics labels, favicon route, ml-vision 100% error, root endpoint |
| `20ad73f` | Show mode-specific metrics (ml vs vision) |
| `7693d34` | Metrics Details: toggle + friendly names + grouping |
| `e4b8557` | Metrics Details: always visible, known items pre-populated, hide internal paths |

---

## Key Decisions / Rules Established

- **Metrics panel is mode-aware:** `?mode=ml` → ML Unified only; `?mode=vision` → Vision only
- **Details always visible** regardless of request count
- **Known items always shown** — user perspective: they expect to see all features, not just active ones
- **Internal paths hidden from Details:** `/models`, `/image-models`, `/detect-models`, `/seg-models`
- **ml-vision needs `/` root endpoint** — browser hits it on load; without it → 404 → logged → inflated error rate
- **ml-vision needs `/favicon.ico` in `_SKIP_PATHS`** — same reason

---

## Pending

### Microservices restructure (paused mid-session)
- Partial files exist in `services/ml-api/routers/` and `services/ml-api/shared/`
- Need: `training.py`, `unsupervised.py`, ml-vision full router split, update `app.py` for both services, update tests

### Phase 2: Theme palette picker + vision ambient themes
- 5 themes: Dark · Light · Ocean · Forest · High Contrast
- Vision task ambient themes (Classifier=fuchsia, Processing=orange, Detection=cyan, Segmentation=purple)

### Phase 3: ML Unified improvements
- EDA step, evaluation report, SHAP, pipeline stepper UI

### Phase 4–6: Data drift · MLflow · E2E tests

---

## Standing Rules (unchanged)

- Apply changes to ALL affected repos simultaneously
- Conversation logs in `ML-Iris/Conversations/`
- Light theme: ALL elements must adapt
- Vercel = portfolio only; Render = ML apps
- `vision_cache/` and `.mcp.json` must never be committed
- Always run `ruff check` + `pytest` before pushing
- Mock-based tests for inference paths requiring model downloads
- User-facing errors: plain English only
- Keep ml-api and ml-vision requirements.txt fully independent
- All vision endpoint URLs sourced from `VISION_API`, never `API`
- Consider microservices architecture in all new features
- ml-vision must have `/` root endpoint and `/favicon.ico` in `_SKIP_PATHS`
