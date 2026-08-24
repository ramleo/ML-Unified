# Conversation — 2026-06-04 | CI/CD Deep Dive & Unit Tests (Part 16)

**Date:** 2026-06-04
**Projects:** ML-Unified, ML-Portfolio

---

## What Was Done This Session

### Points Completed
| # | Item | Status |
|---|---|---|
| 11 | Portfolio: CI/CD pipeline (GitHub Actions) | ✅ Done |
| 17 | Test-gate CI (block deploy if tests fail) | ✅ Done |

**Updated score: 12 done, 8 pending.**

---

## Files Created

### ML-Unified
| File | Purpose |
|---|---|
| `tests/__init__.py` | Makes tests/ a Python package |
| `tests/test_api.py` | 22 unit tests covering all endpoints |
| `requirements-dev.txt` | Dev dependencies (pytest, httpx, ruff) |
| `.github/workflows/ci.yml` | CI pipeline: lint → test → deploy |

### ML-Portfolio
| File | Purpose |
|---|---|
| `.github/workflows/ci.yml` | CI pipeline: type check → build |

---

## CI Pipeline Design

### ML-Unified (`.github/workflows/ci.yml`)
```
on: push / PR to main
env: FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

jobs:
  test:
    1. Spin up Ubuntu VM (fresh, isolated)
    2. Checkout code
    3. Install Python 3.11
    4. pip install -r requirements-dev.txt
    5. ruff check app.py       ← FAIL? deploy skipped
    6. pytest tests/ -v        ← FAIL? deploy skipped

  deploy:
    needs: test
    only on push to main (not PRs)
    7. curl RENDER_DEPLOY_HOOK_URL → Render rebuilds live app
```

### ML-Portfolio (`.github/workflows/ci.yml`)
```
on: push / PR to main
env: FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

jobs:
  build:
    1. Spin up Ubuntu VM
    2. Checkout code
    3. Install Node.js 20
    4. npm ci
    5. tsc --noEmit    ← catches TypeScript type errors
    6. npm run build   ← catches Next.js build failures
```

---

## Unit Tests — 22 Tests Total

### Test Coverage by Endpoint

| Endpoint | Tests |
|---|---|
| `GET /health` | `test_health` |
| `GET /models` | `test_list_models`, `test_list_models_fields` |
| `GET /schemas/{id}` | `test_get_schema_iris`, `test_get_schema_insurance`, `test_get_schema_not_found` |
| `POST /predict/{id}` | `test_predict_iris_setosa`, `test_predict_iris_virginica`, `test_predict_titanic`, `test_predict_diabetes`, `test_predict_insurance`, `test_predict_model_not_found` |
| `POST /analyze` | `test_analyze_csv_classification`, `test_analyze_csv_regression`, `test_analyze_csv_bad_file` |
| `POST /unsupervised` | `test_unsupervised_kmeans`, `test_unsupervised_pca`, `test_unsupervised_dbscan` |
| `POST /train` | `test_train_classification`, `test_train_regression`, `test_train_invalid_task`, `test_train_missing_target_col` |

### Why `/` is not tested
Static HTML file — no ML logic to verify.

### Train test cleanup pattern
`_cleanup_model(model_id)` removes `.pkl`, `.json`, and MODELS dict entry after each train test — no artifacts left on disk between runs.

---

## Key Decisions & Discussions

### Notification on CI failure
- GitHub emails on failure to configured email address
- Set up at `github.com/settings/notifications` → Actions section
- User added alternate email at `github.com/settings/emails`

### Node.js 24 deprecation warning
- Warning: `actions/checkout@v4`, `actions/setup-python@v5`, `actions/setup-node@v4` target Node.js 20
- Fix applied: `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` env var in both workflows
- Remaining cosmetic warning ("being forced to run on Node.js 24") is unavoidable until GitHub updates the action marketplace versions — will disappear automatically

### What the Ubuntu VM actually is
- GitHub spins up a real isolated Ubuntu VM (not a container, not a metaphor)
- Fresh every run — nothing pre-installed except base OS
- Proves "works on my machine" isn't enough — code must work on a clean machine with only `requirements-dev.txt`
- Destroyed after job finishes — no state persists between runs
- `runs-on: ubuntu-latest` can be changed to `windows-latest` or `macos-latest`

### CI gate demo (test branch)
- Created `test/ci-failure-demo` branch with deliberate broken test (`"ok"` → `"broken"`)
- Opened PR #1 → CI failed → deploy job skipped
- Branch + PR deleted after demo — main untouched

### ML-specific tooling roadmap (discussed, not built)
| Tool | Relevance | Decision |
|---|---|---|
| MLflow Model Registry | High — Point 14 | Build after CI |
| DVC | Low | Skip — datasets are static |
| Airflow / Prefect | Low | Skip — no live data feeds yet |
| Kubeflow | None | Ignore completely |
| Dagster / ZenML | Low–Medium | Revisit after MLflow |

---

## Commits

| Repo | Hash | Description |
|---|---|---|
| ML-Unified | `d643311` | Add CI pipeline, 18 unit tests, lint fixes |
| ML-Unified | `8952457` | Fix: opt into Node.js 24 for GitHub Actions |
| ML-Unified | `1680f0b` | Add /train endpoint tests (4 tests) |
| ML-Portfolio | `4153c6f` | Add CI pipeline (build + type check) |
| ML-Portfolio | `c34e05a` | Fix: opt into Node.js 24 for GitHub Actions |

---

## Lint Fixes Applied to app.py

| Line | Issue | Fix |
|---|---|---|
| 20 | E401: multiple imports on one line | Split into individual imports |
| 309, 335, 358, 363, 443 | E741: ambiguous variable name `l` | Renamed to `lbl` |

---

## Pending — 8 Items Remaining

| # | Item |
|---|---|
| 12 | Monitoring — Grafana + Prometheus |
| 13 | Data drift / model drift detection |
| 14 | MLflow experiment tracking |
| 15 | CNN / image classification task type |
| 16 | Data injection (DB, cloud, real-time) |
| 18 | E2E browser testing — Playwright |
| 19 | Full pipeline validation commit → live |
| 20 | CI/CD end-to-end pipeline test automation |

---

## Standing Rules

- Apply changes to ALL affected repos simultaneously
- Conversation logs stored in `ML-Iris/Conversations/` folder
- Light theme: ALL elements must adapt
- Vercel = portfolio only (ML-Portfolio repo); Render = ML app (ML-Unified repo)
- ML-Portfolio → Vercel auto-deploy on push to main
- ML-Unified → Render auto-deploy on push to main (~3–5 min free tier), gated by CI
- pkl files trained with scikit-learn==1.8.0 — keep pinned, unpin pandas/numpy
- ML-Unified schema is auto-generated on upload/train — never hand-write schemas
- Unsupervised analysis: always dataset-in → visualization-out, no saved model
- `.mcp.json` must never be committed — always in `.gitignore`
- Run tests locally before pushing: `cd ML-Unified && .venv/bin/pytest tests/ -v`
