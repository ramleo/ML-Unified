# Session 2026-07-14 — Analytics Tracking Plan (Part 189)

## Summary

This session covered:
1. **fetchWithRetry regression fix** — removed erroneous `if (!res.ok) throw new Error(...)` from `fetchWithRetry` in `index.html`. The original code never had an ok-check; adding it caused HTTP errors to retry 4×12s = 48s before surfacing the same failure. Fixed to only retry on network-level failures (catch block). Commit `b3e913c`, pushed to GitHub + uploaded to HF Space.

2. **Analytics tracking plan** — planned real-time analytics tracking for ML Unified, EDA, Vision (HF Space / index.html) and all ml-portfolio tools (Optuna, FE, FS, Preprocessing, Drift, Ensemble, Pipeline Builder, Pipeline Cinema).

---

## fetchWithRetry Fix

**Bug introduced in commit `95d7381`:**
```js
// WRONG — made HTTP errors retry instead of fail fast
if (!res.ok) throw new Error(`HTTP ${res.status}`);
```

**Fix in commit `b3e913c`:**
```js
async function fetchWithRetry(url, maxRetries = 4, delayMs = 12000) {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch(url);
      return res; // return regardless of status — caller handles non-200
    } catch(e) {
      if (attempt === maxRetries) throw e;
      const msg = document.getElementById('loadingMsg');
      const remaining = (maxRetries - attempt);
      if (msg) msg.textContent = `Server waking up — retrying in ${delayMs/1000}s… (${remaining} attempt${remaining !== 1 ? 's' : ''} left)`;
      await new Promise(r => setTimeout(r, delayMs));
    }
  }
}
```

Why the ok-check was wrong:
- `list_models()` backend never returns 500 — empty MODELS returns `[]` with 200 OK
- HF cold-start returns connection refused (caught by catch), not a 503
- Adding `if (!res.ok) throw` was a solution to a non-existent problem

---

## Combined Analytics Tracking Plan

### Already done ✓
SHAP, AutoML, Text-to-SQL — all tracked.

---

### Tools to track (9 targets)

#### HF Space — index.html (3 apps, 1 deploy)

| # | App | Event | Trigger | Key meta |
|---|-----|-------|---------|----------|
| 1 | ML Unified | `tool_open` | Sidebar model selected | `model_id`, `task` |
| 2 | ML Unified | `query_run` | Train complete | `action:"train"`, `model_type`, `metric_value`, `features_count` |
| 3 | ML Unified | `query_run` | Predict complete | `action:"predict"`, `model_id`, `confidence` |
| 4 | ML Unified | `query_run` | SHAP done | `action:"shap"`, `model_id` |
| 5 | ML Unified | `query_run` | AutoML done | `action:"automl"`, `winner`, `models_tried` |
| 6 | ML Unified | `query_run` | Unsupervised done | `action:"cluster"`, `algorithm`, `n_samples` |
| 7 | ML Unified | `query_run` | RAG query | `action:"rag"` |
| 8 | ML Unified | `tool_open` | CSV uploaded | `action:"upload_csv"`, `rows`, `cols` |
| 9 | ML Unified | `error` | Any API fail | `action`, `status_code` |
| 10 | EDA | `tool_open` | Panel selected | `tool:"eda"` |
| 11 | EDA | `tool_open` | CSV uploaded | `tool:"eda"`, `action:"upload"`, `rows`, `cols` |
| 12 | EDA | `query_run` | Analyze/profile done | `tool:"eda"`, `action:"analyze"`, `rows`, `cols` |
| 13 | EDA | `query_run` | Clean op done | `tool:"eda"`, `action:"clean"`, `operation` |
| 14 | EDA | `query_run` | Chart generated | `tool:"eda"`, `action:"chart"`, `chart_type` |
| 15 | EDA | `error` | EDA API fail | `tool:"eda"`, `action`, `status_code` |
| 16 | Vision | `tool_open` | Panel selected | `tool:"vision"` |
| 17 | Vision | `tool_open` | Image uploaded | `tool:"vision"`, `action:"upload_image"` |
| 18 | Vision | `query_run` | Classify done | `tool:"vision"`, `action:"classify"`, `model`, `top_label`, `confidence` |
| 19 | Vision | `query_run` | Detect done | `tool:"vision"`, `action:"detect"`, `model`, `objects_found` |
| 20 | Vision | `query_run` | Segment done | `tool:"vision"`, `action:"segment"`, `model` |
| 21 | Vision | `error` | Vision API fail | `tool:"vision"`, `action`, `status_code` |

---

#### ml-portfolio tools (Next.js, Vercel deploy)

| # | Tool | File | Lines | Event | Trigger | Key meta |
|---|------|------|-------|-------|---------|----------|
| 22 | Optuna | `OptunaRunner.tsx` | 338 | `tool_open` | CSV uploaded | `tool:"optuna"`, `rows`, `cols` |
| 23 | Optuna | `OptunaRunner.tsx` | 338 | `query_run` | Study completes | `tool:"optuna"`, `best_value`, `n_trials`, `direction`, `sampler` |
| 24 | Optuna | `OptunaRunner.tsx` | 338 | `error` | Study fails | `tool:"optuna"`, `error_type` |
| 25 | FE | `feature-engineering/page.tsx` | 329 | `tool_open` | CSV uploaded | `tool:"feature-engineering"`, `rows`, `cols` |
| 26 | FE | `feature-engineering/page.tsx` | 329 | `query_run` | Transform applied | `tool:"feature-engineering"`, `operation`, `features_created` |
| 27 | FE | `feature-engineering/page.tsx` | 329 | `error` | Transform fails | `tool:"feature-engineering"`, `operation` |
| 28 | FS | `feature-selection/page.tsx` | 358 | `tool_open` | CSV uploaded | `tool:"feature-selection"`, `rows`, `cols` |
| 29 | FS | `feature-selection/page.tsx` | 358 | `query_run` | Selection done | `tool:"feature-selection"`, `method`, `features_selected`, `original_features` |
| 30 | FS | `feature-selection/page.tsx` | 358 | `error` | Selection fails | `tool:"feature-selection"`, `method` |
| 31 | Preprocessing | `preprocessing/page.tsx` | 353 | `tool_open` | CSV uploaded | `tool:"preprocessing"`, `rows`, `cols` |
| 32 | Preprocessing | `preprocessing/page.tsx` | 353 | `query_run` | Pipeline applied | `tool:"preprocessing"`, `operations[]`, `rows_out` |
| 33 | Preprocessing | `preprocessing/page.tsx` | 353 | `error` | Pipeline fails | `tool:"preprocessing"` |
| 34 | Drift | `drift/DriftRunner.tsx` | 230 | `tool_open` | Datasets uploaded | `tool:"drift"`, `rows`, `features` |
| 35 | Drift | `drift/DriftRunner.tsx` | 230 | `query_run` | Analysis done | `tool:"drift"`, `drifted_features`, `total_features`, `drift_score` |
| 36 | Drift | `drift/DriftRunner.tsx` | 230 | `error` | Analysis fails | `tool:"drift"` |
| 37 | Ensemble | `ensemble/EnsembleRunner.tsx` | 362 | `tool_open` | CSV uploaded | `tool:"ensemble"`, `rows`, `cols` |
| 38 | Ensemble | `ensemble/EnsembleRunner.tsx` | 362 | `query_run` | Run complete | `tool:"ensemble"`, `method`, `n_models`, `metric_value` |
| 39 | Ensemble | `ensemble/EnsembleRunner.tsx` | 362 | `error` | Run fails | `tool:"ensemble"` |
| 40 | Pipeline Builder | `pipeline-builder/page.tsx` | 391 | `tool_open` | CSV uploaded | `tool:"pipeline-builder"`, `rows`, `cols` |
| 41 | Pipeline Builder | `pipeline-builder/page.tsx` | 391 | `query_run` | Pipeline run | `tool:"pipeline-builder"`, `steps_count`, `metric_value` |
| 42 | Pipeline Cinema | `usePipelineRunner.ts` | 281 | `tool_open` | Simulation started | `tool:"pipeline-cinema"`, `algorithm`, `dataset` |
| 43 | Pipeline Cinema | `usePipelineRunner.ts` | 281 | `query_run` | Simulation done | `tool:"pipeline-cinema"`, `algorithm`, `steps`, `duration_ms` |

---

## Execution Order

| Step | Target | Why this order | Deploy |
|------|--------|---------------|--------|
| 1 | **index.html** (ML Unified + EDA + Vision) | Single file, 3 apps in 1 deploy — knock it out together | HF Space upload |
| 2 | **Optuna** (`OptunaRunner.tsx`) | Biggest gap — zero events currently | `git push` → Vercel |
| 3 | **FE + FS + Preprocessing** | Same pattern, same file structure — batch in one commit | `git push` → Vercel |
| 4 | **Drift + Ensemble** | Runner-component pattern, similar to SHAP — batch together | `git push` → Vercel |
| 5 | **Pipeline Builder + Pipeline Cinema** | Both pipeline tools, natural pair | `git push` → Vercel |

Total: 5 execution steps, 42 tracking events across 9 tools.

---

## index.html Split Discussion

**User:** why is index.html 9977 lines? can we not split it? only answer, dont do anything

**Claude:** Yes, it can be split — but it's a vanilla JS single-page app, not a framework. The reason it's 9977 lines is that everything was added incrementally into one file: HTML structure, CSS styles, and all JavaScript for 3 different app modes (ML Unified, EDA, Vision) with their own UI panels, API calls, chart rendering, and state management — all co-located because there's no build system or module bundler running on the HF Space.

To split it properly you'd need to either:
1. **Add a build step** — use Vite/esbuild to bundle separate JS modules into one output file for HF Space deployment. Proper solution but non-trivial setup.
2. **Split into multiple HTML files** — `index.html` (ML Unified), `eda.html`, `vision.html` — served by separate routes in FastAPI. Simpler but changes the URL structure.

For now it's monolithic because that was the path of least resistance when building on HF Space. Splitting is doable but is a separate refactor task, not something to mix with analytics tracking.

---

**User:** what you suggest?

**Claude:** Split into 3 separate HTML files served by FastAPI routes.

**Why:**
- No build tooling needed — FastAPI already serves `index.html`, just add 2 more routes
- Each file stays focused (~3000 lines each instead of 10k)
- EDA and Vision become independently deployable/debuggable
- Shared CSS/JS (sidebar logic, `_track`, utilities) goes into a small `common.js` that all 3 include via `<script src="/static/common.js">`

**The split:**
| File | Route | Content |
|------|-------|---------|
| `index.html` | `GET /` | ML Unified only |
| `eda.html` | `GET /eda` | EDA Explorer only |
| `vision.html` | `GET /vision` | ML Vision only |
| `common.js` | `GET /static/common.js` | Shared: sidebar init, `_track`, API base URLs, shared CSS |

**Tradeoff:** One session of refactor work (~2–3 hours) before we can cleanly add analytics. But after the split, every future change (analytics, fixes, new features) becomes 3x easier to reason about.

**Recommendation:** Do the split first, then add analytics into the clean files. The analytics work will be faster and less error-prone on 3000-line files than hunting through 10k lines.

---

## Commits This Session

| Hash | Message |
|------|---------|
| `b3e913c` | fix(index.html): remove erroneous if (!res.ok) throw from fetchWithRetry |
