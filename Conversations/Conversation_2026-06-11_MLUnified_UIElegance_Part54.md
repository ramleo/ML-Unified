# Conversation — 2026-06-11 — ML-Unified — Part 54

---

## Session Summary

Reviewed pending items list, confirmed EDA microservice is implemented, discussed untracked refactor files, deferred refactor decision.

---

## Pending Items (Revised as of 2026-06-11)

### Actually Pending

| # | Item | Notes |
|---|------|-------|
| #20 | Playwright E2E tests | Not started |
| #22 | Dockerize full app (ml-api + ml-eda + ml-vision) | Not started |
| #14 | Side-by-side vision results | Not started |
| #16 | Vision ambient themes | Not started |

### Deferred

| # | Item |
|---|------|
| #21 | Batch predict — Object Detection + Segmentation |
| #11 | Cleaned CSV download |
| #5  | Proxy page (`/app/[id]`) — low ROI |

### Items Confirmed Done (were showing as pending in older notes)

| Item | Status |
|------|--------|
| UI elegance re-apply | Done — Part 53 |
| Drift detection (#18) | Done — Part 45 |
| SHAP zeros fix (Iris) | Done — Part 50 |
| EDA unit tests (#13) | Done — 35 tests already existed, all passing |
| MLflow (#19) | Explicitly skipped — no user-visible benefit on Render free tier |
| EDA microservice extraction (#12) | Done — `services/ml-eda/` is a full standalone FastAPI service |

---

## EDA Microservice — Confirmed Implemented

`services/ml-eda/` is a complete standalone FastAPI service:
- Own `app.py`, `routers/eda.py`, `requirements.txt`, `tests/`
- `ml-api` reads `ML_EDA_URL` from env and passes it to frontend via `/app-config`
- Frontend uses `let EDA_API = ''` populated at runtime

**Needs verification:** `ML_EDA_URL` env var set in Render dashboard for ml-api service.

---

## Untracked Refactor Files — Deferred

A partial refactor of `services/ml-api/app.py` (794 lines) was started but never committed:

- `services/ml-api/routers/config.py` — frontend serving, /health, /app-config
- `services/ml-api/routers/inference.py` — /models, predict
- `services/ml-api/routers/monitoring.py` — request logging middleware
- `services/ml-api/shared/paths.py` — path constants
- `services/ml-api/shared/registry.py` — MODELS dict + load_models()
- `services/ml-vision/routers/` + `services/ml-vision/shared/`

**Decision: Deferred.** App is stable, portfolio project, no new developers. Not worth deployment risk now.

**When to revisit:** app.py grows past ~1500 lines.

**Critical wiring task when implementing:** All 4 existing routers (shap.py, pipeline.py, drift.py, training.py) do `from app import MODELS` lazily inside each function. Every one must be updated to `from shared.registry import MODELS` — missing any one crashes the app on startup.
