# Conversation Part 151 — Data Drift Detection
**Date:** 2026-07-04
**Topics:** Pending items cleanup (#24, #25, #33 already done), drift detection page build, drift modularization, upload icon fix

---

## Context (from Part 150)

- RAG Phases 1–3 complete; Agent Step Rail + "How I Searched" panel shipped
- Pending items reviewed: #23 drift, #24 RAG explain, #25 ensemble, #33 cat freq, and MLOps items open

---

## Session Work

### 1. Pending Items Cleanup

User flagged #24 and #25 as already done. Verified in codebase and git log:

| # | Item | Evidence |
|---|------|---------|
| `#24` | RAG-enhanced /explain | commit `57e31b8`; KB badge + re-generate button in `9a71093`, `c65edc0` |
| `#25` | Ensemble/stacking | `EnsembleRunner.tsx` at `/tools/ensemble`; `pipeline_builder/automl_stage.py`; commit `d8693ea` |
| `#33` | Categorical drift frequencies | `cat_freq` dict stored in schema at train time (`automl_train_work.py:121`); `drift.py` already reads via `field.get("cat_freq")` — no code change needed |

All three marked `☑` in `pending.md`.

---

### 2. Drift Detection (#23) — `/tools/drift` page

**Decision:** standalone tool page, not a pipeline builder card. Drift is post-deployment monitoring, not a train-time step.

#### Backend — modularize `drift.py` first (581 lines → package)

CLAUDE.md Rule 3 triggered. Split `routers/drift.py` (581 lines) into `routers/drift/` package:

| File | Lines | Contents |
|------|-------|---------|
| `_stats.py` | 126 | PSI numeric/categorical, KS test, histogram, `is_number`, `level`, `psi_level`, `norm_cdf` |
| `_baseline.py` | 69 | `get_baseline()`, `_extract_pipeline_stats()` from fitted sklearn pipeline |
| `_compute.py` | 185 | `compute_drift()`, `_process_numeric()`, `_process_categorical()` |
| `_state.py` | 105 | Rolling buffer, history snapshots, persistence (`load_all`, `save_buffer`, `save_history`), `record_input()` |
| `__init__.py` | 78 | FastAPI router + 3 endpoints; re-exports `record_input` for `app.py` |

`app.py` import unchanged: `from routers import drift as _drift_router`.

#### Backend — batch label versioning (item #23)

`POST /drift/{model_id}/upload` now accepts optional `?label=` query param stored in each history snapshot:
```python
label: Optional[str] = Query(default=None, description="Optional batch label, e.g. 'Week 3'")
```
Enables named batch tracking in the trend chart.

#### Frontend — `DriftRunner.tsx` (301 lines) + `page.tsx` (52 lines)

- **Model selector** — `GET /models`; pre-selects first model
- **Batch label input** — optional free text, passed as `?label=` query param
- **Drag-and-drop CSV upload zone** — triggers `POST /drift/{model_id}/upload`; upload SVG icon above text
- **Overall drift card** — score badge (green/amber/red), row count, baseline type, label, filename
- **Trend sparkline** — SVG polyline of `overall_score` across batches; dots colored by drift level; shown when ≥ 2 batches uploaded
- **Feature cards** — sorted by drift score descending, high-drift first
  - Numeric: ref mean/std, batch mean/std, PSI + level, KS stat + p-value, inline histogram overlay (training ref bars vs batch bars)
  - Categorical: per-category dual bar pairs (train freq vs batch freq); fallback warning shown when `cat_baseline = "uniform"` (no `cat_freq` stored)
- **Home page card** — drift entry added to `capabilities.ts`; "Try it" → `/tools/drift`; accent `#fb923c`

#### How the model dropdown is populated

`GET /models` reads from in-memory `MODELS` dict. Models enter it two ways:
1. **Train time** — when you run AutoML (or Pipeline Builder), the backend trains the pipeline, writes a schema JSON to `data/schemas/{id}.json` and a `.pkl` to `data/models/`, then adds the entry to `MODELS` in memory
2. **On startup** — `app.py` scans both directories and reloads all saved schemas + pipelines back into `MODELS`, so models survive Space restarts

The "Diabetes Risk Predictor" is a built-in demo model pre-seeded at startup. Any model trained via the AutoML wizard also appears there.

---

### 3. Upload Icon Fix

User noted the drop zone had no visual icon. Added SVG upload arrow (↑ into tray) above the drop text in `DriftRunner.tsx`.

---

## Q&A This Session

**Q: Does it monitor data drift or model drift?**
A: Data drift only — compares input feature distributions of a new batch against training baseline. Does not monitor prediction accuracy degradation (model drift), which requires ground truth labels on the new batch.

**Q: How does `/tools/drift` work end to end?**
A: Model selector → upload batch CSV (optionally labelled) → backend computes z-score / PSI / KS per feature against training stats stored in schema → frontend renders overall badge + per-feature cards with histograms + trend sparkline.

---

## Commits This Session

| Hash | Repo | Description |
|------|------|-------------|
| `e77a958` | ml-portfolio | feat(drift): add /tools/drift page — model picker, batch CSV upload, per-feature drift cards |
| `b3ec6e7` | ml-portfolio | feat(drift): add drift detection card to home page capabilities |
| `f5e6bc5` | ml-portfolio | fix(drift): add upload SVG icon to drop zone |
| `e2d2ed4` | ML-Unified | refactor(drift): split drift.py into routers/drift/ package; add batch label to upload endpoint |

HF Space upload complete for all 5 backend files.

---

## Pending (open ☐ items after this session)

| # | Item |
|---|------|
| 23 | Drift detection with data versioning — ✅ done this session |
| 28 | GPU toggle |
| 39 | Model versioning + rollback |
| 40 | Drift alerting (email/Slack) |
| 41 | LLM-assisted feature suggestions after EDA |
| 42 | Automated retraining pipeline |
| 43 | Time series forecasting (Prophet/ARIMA/LSTM) |
| 44 | Microservices migration (deferred until off HF Space) |
| 45 | E2E Playwright tests wired into CI |
| 47 | Dockerize ml-eda + ml-vision |
| 49 | EDA microservice extraction (deferred) |
| 50 | Batch predictions for vision |
| 51 | MLflow experiment tracking (explicitly skipped) |
| 52 | Playwright automated tests for ml-portfolio |
