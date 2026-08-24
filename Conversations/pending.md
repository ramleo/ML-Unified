# Pending Items — ML-Unified + ml-portfolio

Last updated: 2026-07-06 (items 7–10, 13, 19–22, 23, 26–27, 30, 31, 41, 46, 47, 60–72 completed; session 160)

---

## Frontend — ml-portfolio

### Feature Engineering

| # | Done | Item | Notes |
|---|------|------|-------|
| 1 | ☑ | One-hot encoding for categorical columns | Output: binary indicator columns per unique value |
| 2 | ☑ | Target encoding | Category → mean of target column |
| 3 | ☑ | Transform presets | One-click: Skew correction, Normalize all, Tree-ready |
| 4 | ☑ | Column search within transforms panel | Done 2026-06-23 — search input in NumericTransformsPanel + CategoricalPanel; shown when 8+ columns |
| 5 | ☑ | Transform recipe summary before applying | Done 2026-06-23 — summary banner in FE sidebar e.g. "Will apply: 3 log1p, 2 sqrt → ~5 cols" |
| 6 | ☑ | DatasetEstimator not added to FE configure step | Was already present via FEUploadInfo at configure step — confirmed 2026-06-23 |
| 7 | ☑ | Date/datetime extraction | Done 2026-06-24 — DatetimePanel.tsx; creates _year/_month/_day/_dayofweek/_hour; commit a7291c6 |
| 8 | ☑ | Polynomial features (degree 2) | Done 2026-06-24 — polynomial x² section in NumericTransformsPanel; creates col_sq; commit a7291c6 |
| 9 | ☑ | Binning | Done 2026-06-24 — custom binning section in NumericTransformsPanel; creates col_binN (3–20 bins); commit a7291c6 |
| 10 | ☑ | Ratio/diff/group-aggregation | Done 2026-06-24 — RatioDiffPanel.tsx; up to 5 pairs; creates col_a_div_col_b + col_a_minus_col_b; commit a7291c6 |

### Feature Selection

| # | Done | Item | Notes |
|---|------|------|-------|
| 11 | ☑ | AI Suggest "no valid JSON" / intermittent 502 error | Fixed 2026-06-23 — maxDuration=30 on ai-tools route; switched FS+FE AI Suggest to Groq (decoupled from chat gear icon) |

### AutoML UX

| # | Done | Item | Notes |
|---|------|------|-------|
| 12 | ☑ | Model Fitness tooltip | Done 2026-06-23 — ⓘ icon with LLM-rated 0–100 explanation in Step4Results |
| 13 | ☑ | More ML algorithm pills | Done 2026-06-24 — backend branches added in automl_clf.py + automl_reg.py; frontend pills already present; uploaded to HF Space |
| 14 | ☑ | "Own key" button rename + UX clarity | Done — renamed to "Use my API key", base URL + model fields, per-provider hints, rate limit note |
| 15 | ☑ | Fix `showAutoMLWizard()` | Done 2026-06-23 — clears _lastAutoMLResult, always calls _startFreshAutoML() |

### Tool Pages (static → interactive)

| # | Done | Item | Notes |
|---|------|------|-------|
| 16 | ☑ | Optuna Tuning page | Done 2026-06-24 — OptunaRunner.tsx; CSV upload → analyze → model + trial config → stream train → results; commit d8693ea |
| 17 | ☑ | SHAP Explainability page | Done 2026-06-24 — ShapRunner.tsx; CSV upload → analyze → model select → SHAP-style importance bars; commit d8693ea |
| 18 | ☑ | Ensemble Methods page | Done 2026-06-24 — EnsembleRunner.tsx; multi-algo pills → CV leaderboard + spread metric; commit d8693ea |

### Pipeline Builder

| # | Done | Item | Notes |
|---|------|------|-------|
| 19 | ☑ | `MLPipelineState` data contract | Done 2026-06-27 — PipelineContext.tsx + types/pipeline.ts; localStorage persistence; commit 66e8c16 |
| 20 | ☑ | AutoML standalone modal | Done 2026-06-27 — AutoML writes automlWinner back to PipelineContext; commit 66e8c16 |
| 21 | ☑ | Remaining card modals (FE, SHAP, Optuna, Ensemble) | Done 2026-06-29 — all pages wrapped in PipelineProvider; CsvFromContextBanner on all 4; onReady/triggerRef pattern; commits 1aabba7 a30c7a2 |
| 22 | ☑ | Pipeline builder UI | Done 2026-06-27 — /tools/pipeline-builder; 7 cards, locked/ready/done states, progress bar, reset; commits 66e8c16 db88588 |

#### #21 Context Wiring — Completed 2026-06-29

Full pipeline context chain built:
1. Preprocessing → `csvB64`, `preprocessedCsvB64`
2. Feature Engineering → `feCsvB64`
3. Feature Selection → `fsCsvB64`, `selectedFeatures`
4. AutoML → `automlWinner`, `automlRanking` (auto-written on train completion; "Save to Pipeline" button removed)
5. Optuna → reads `automlWinner` to pre-select model; writes `tunedModel` (with `params`)
6. SHAP → reads `tunedModel` (Optuna params auto-detected) or `automlWinner`; sends `preset_params_json` to backend
7. Ensemble → reads `automlRanking` to pre-select top 3 models

CSVs passed as base64 strings via context; `CsvFromContextBanner` on all tool pages lets user load from previous step without re-uploading.

### Downloads & Params (Session 136 — 2026-06-29)

| # | Done | Item | Notes |
|---|------|------|-------|
| 53 | ☑ | Download winner model (.pkl) | Backend: `GET /model/{id}/download` → FileResponse; Frontend: button in Step4Results; commit 4d2befc |
| 54 | ☑ | Download Optuna params (JSON) | `handleDownloadParams` in OptunaRunner; `optuna_params → best_params` field mapping fix; commits 4d2befc 676bee0 |
| 55 | ☑ | SHAP: use Optuna-tuned params | Checkbox + upload JSON in configure step; `preset_params_json` Form field in backend `/train`; backend rebuilds winner model; commits 0f5c288 6469c6c |
| 56 | ☑ | Auto-write `automlWinner` on completion | Moved from button click to `onResult` callback; "Save to Pipeline" button removed; commit 6c5ab27 |

### Ensemble UX Fixes (Session 137 — 2026-06-29)

| # | Done | Item | Notes |
|---|------|------|-------|
| 57 | ☑ | Ensemble leaderboard blank MODEL names | Backend returns `algorithm` field; frontend read `name`; fixed by mapping `r.name ?? r.algorithm` in EnsembleRunner SSE parser; commit 6550150 |
| 58 | ☑ | Ensemble rank emojis → SVG medal ribbons | Replaced 🥇🥈🥉 with two-tone ribbon + circle SVG; gold/silver/bronze; commits 774ff2d 5b108ff |
| 59 | ☑ | Ensemble accent color clash (green vs pink) | `EnsembleRunner` + `EnsembleResults` hardcoded `#10b981`; threaded `accent` prop from page (`#f472b6`); commit 1e3e386 |

---

## Backend — ML-Unified

### AutoML Phases

| # | Done | Phase | Notes |
|---|------|-------|-------|
| 23 | ☑ | Phase 3: Drift detection with data versioning | V1 = training baseline; V2+ = prev vs new batch. extract_batch_stats + save_version + compare_to_training toggle; GET /drift/{id}/versions; commits `18008d9` (backend) `8715672` (frontend) |
| 24 | ☑ | Phase 4: RAG-enhanced AI explanation | Done — KB context injected into /explain for winning algorithm; commit 57e31b8; KB badge + re-generate button in frontend; commits 9a71093, c65edc0 |
| 25 | ☑ | Phase 9: Ensemble/stacking | Done 2026-06-24 — EnsembleRunner.tsx page at /tools/ensemble; multi-algo CV leaderboard; manual ensemble in pipeline_builder/automl_stage.py; commit d8693ea |
| 26 | ☑ | Phase 10: Pipeline export | Done 2026-06-24 — GET /models/{id}/export endpoint in inference.py; ↓ Download .pkl button in Step4Results; commit 0a90fbb |
| 27 | ☑ | Phase 11: Per-column encoding options | Done 2026-06-26 — per-column onehot/ordinal/frequency dropdowns in AutoML Step 2; FrequencyEncoder at module level; commits e02015d, bad87c0 |
| 28 | ☐ | Phase 12: GPU toggle | Not started |
| 29 | ☑ | Phase 13: SMOTE | Done 2026-06-24 — imblearn ImbPipeline applied when is_imbalanced + minority≥20; k_neighbors dynamic; commit 215194e |

### SHAP / What-If

| # | Done | Item | Notes |
|---|------|------|-------|
| 30 | ☑ | SHAP bars for FE-derived features | Done 2026-06-24 — getParentLabel() in AutoMLCharts.tsx shows "↳ from Age" under derived feature bars; commit 0a90fbb |
| 31 | ☑ | "Why only X features?" collapsible | Done 2026-06-24 — details/summary collapsible in FeatureImportanceSection.tsx; commit 0a90fbb |
| 32 | ☑ | Fix learning curve interpretation | Done 2026-06-23 — dataset-size-aware thresholds in interpretLearningCurve(); badge shown in Step4Results |

### Data Drift

| # | Done | Item | Notes |
|---|------|------|-------|
| 33 | ☑ | Categorical actual frequencies | Done — `cat_freq` dict stored in schema fields at train time (automl_train_work.py:121); drift.py already reads it via `field.get("cat_freq")` |
| 34 | ☑ | Persistent drift buffer | Done in Part 45 — rolling window written to `data/drift_buffer.json` + `drift_history.json` via `routers/drift.py` |

### Bugs

| # | Done | Item | Notes |
|---|------|------|-------|
| 35 | ☑ | Fix Gemini-2.5-flash | Fixed — maxTokens 3000, extractJson hardened, model_comparison schema corrected |
| 36 | ☑ | Fix Groq model IDs | Fixed — updated to `llama-3.3-70b-versatile` + `llama-3.1-8b-instant` everywhere |
| 37 | ☑ | Regression confidence intervals | Done 2026-06-23 — 200-sample bootstrap CI in app.py; WinnerMetricsGrid shows "R²/RMSE 95% CI: x.xx – x.xx" |

### Model Persistence

| # | Done | Item | Notes |
|---|------|------|-------|
| 38 | ☑ | Models don't persist across Render restarts | Moot — Render removed, now on HF Space. HF Space free tier still sleeps; upgrade to HF Pro ($9/mo) for always-on |

### MLOps (not started)

| # | Done | Item | Notes |
|---|------|------|-------|
| 39 | ☐ | Model versioning + rollback | Not started |
| 40 | ☐ | Drift alerting | Email/Slack notifications on drift detection |
| 41 | ☑ | LLM-assisted feature suggestions after EDA | Done 2026-07-06 — POST /eda/suggest; Groq/Gemini/Cohere SSE; markdown render; provider dropdown in EDA Explorer; commits `1d0eb8f` `5d65839` |
| 42 | ☐ | Automated retraining pipeline | Not started |
| 43 | ☐ | Time series forecasting | Prophet/ARIMA/LSTM |
| 44 | ☐ | Microservices migration | When off HF Space — reference doc created in Part 87 |

---

## RAG / Chat AI — ToolsAIChat

| # | Done | Item | Notes |
|---|------|------|-------|
| 60 | ☑ | KB not indexed on HF Space (0 candidates) | DATA_DIR default was `/data` (absolute); changed to `data` (relative); 47 chunks indexed; commit `32425a8` |
| 61 | ☑ | Jina RustBindingsAPI error | Pinned `tokenizers>=0.20,<0.21` in requirements.txt; commit `32425a8` |
| 62 | ☑ | Settings panel scroll (preventDefault missing) | Added `e.preventDefault()` alongside `stopPropagation()`; Playwright verified; commit `4d49595` |
| 63 | ☑ | Tiered answer source + confidence badge | `dataset/uploaded_doc/knowledge_base/web` labels; score-based confidence; badge rendered in ChatMessageList; commits `6568a37` `f865aa0` |
| 64 | ☑ | Drift page thin context (no per-column stats) | `buildDriftContext()` now includes `batch_mean/std/range/ref_mean/ref_std` per feature; commit `5420029` |
| 65 | ☑ | Confidence bump when dataset + KB combined | `_determine_confidence()` lowers thresholds one tier when `has_dataset=True`; commit `3ba9c7c` |
| 66 | ☑ | "How I Searched" missing in Deep Search | Agent done event now emits `expanded_queries`, `candidates_retrieved`, `answer_source`, `confidence`; commit `3ba9c7c` |
| 67 | ☑ | Tiered retrieval (uploaded docs → KB priority) | `tiered_hybrid_retrieve` in retrieve.py; uploaded-first, KB fallback if score < 0.15; `uploaded` metadata now passed through dense+BM25 hits; commit `e0b5f56` |
| 68 | ☑ | Manual web override toggle | `force_web` field in QueryRequest/AgentRequest; amber globe button in chat header; cache bypassed when force_web=True; commits `1af3955` `79de7e2` |
| 69 | ☑ | Dataset badge showing KB instead of Dataset | `_determine_answer_source` returns `"dataset"` when `has_dataset=True` and not web/uploaded; commit `90af1af` |
| 70 | ☑ | Web override returning cached KB response | Skip semantic cache when `force_web=True`; commit `90af1af` |
| 71 | ☑ | Web source detection broken (chunks[0] was KB not web) | Use `web_fallback_used` flag directly instead of checking source prefix; `force_web` replaces KB chunks instead of appending; commit `bc28ed1` |
| 72 | ☑ | KB sources shown under Dataset badge | Hide sources panel in ChatMessageList when `answerSource === "dataset"`; Playwright verified; commit `59d0626` |

---

## Infrastructure

| # | Done | Item | Notes |
|---|------|------|-------|
| 45 | ☐ | E2E Playwright tests in CI | Suite exists locally; not wired into CI pipeline |
| 46 | ☑ | `app.py` refactor | Done 2026-06-24 — split into routers/core/ (12 files, all ≤400 lines); app.py now 131 lines; uploaded to HF Space |
| 47 | ☑ | Dockerize ml-eda | Done 2026-07-06 — Dockerfile added; deployed as wram1708/ml-eda HF Space; commit `1d0eb8f` · ml-vision still pending |

---

## Deferred (explicitly, not cancelled)

| # | Done | Item | Notes |
|---|------|------|-------|
| 48 | ☑ | #11 Cleaned CSV download | Done |
| 49 | ☐ | #12 EDA microservice extraction | Deferred |
| 50 | ☐ | #21 Batch predictions | Cap 10 images, before/after layout; Object Detection + Segmentation |
| 51 | ☐ | #19 MLflow experiment tracking | Skipped — local file-based has no user-visible benefit on deployed site |

---

## Testing

| # | Done | Item | Notes |
|---|------|------|-------|
| 52 | ☐ | Playwright automated tests — ml-portfolio | Upload CSV, verify 4 toggles, DatasetEstimator placement, sampling indicators in FS result cards — set aside |

---

*Parts 1–39 not yet searched — may contain additional pending items.*
