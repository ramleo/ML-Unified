# Conversation — 2026-06-04 | 20-Point Plan Status Review (Part 15)

**Date:** 2026-06-04  
**Purpose:** Status audit of the 20-point plan across all conversation logs

---

## What Was Done This Session

No code changes. Pure status review — went through all MD files in `ML-Iris/Conversations/` to get accurate pending/done status of the 20-point plan.

---

## Carry-Overs from Part 14 — Confirmed Done

- ✅ DBSCAN fix confirmed — `test_clusters.csv` (24 rows, 3 obvious clusters) returns 3 clusters on live deploy
- ✅ MCP servers confirmed in `ml-portfolio` — all 3 approved (filesystem, playwright, github)

---

## CNN / Image Classification — Point 15 Plan (Discussed, Not Yet Built)

Two options discussed:

**Option A — Pre-trained model only (recommended first step)**
- Load a pre-trained ImageNet model (MobileNetV2) at startup in ML-Unified
- User uploads an image → backend runs inference → returns top-3 predictions
- No training step — fixed "Image Classifier" entry in the sidebar
- Fast to build, no GPU needed, works on Render free tier

**Option B — Upload + train your own CNN**
- Extend the CSV wizard to accept a ZIP of labelled images (folder per class)
- Backend trains a small CNN (transfer learning on MobileNetV2 base) → saves model → appears in sidebar
- More complex, Render free tier may time out on training

**Decision:** Start with Option A. Option B comes later as a train-wizard extension.

---

## Next Priority Revised

User decided to tackle **Point 11 — GitHub Actions CI for ML-Portfolio / ML-Unified** before CNN.

---

## CI/CD Planning Discussion

### Unit Tests Decision
- **ML-Unified** → write unit tests + GitHub Actions CI (covers Points 11 + 17 together)
- **ML-Portfolio** → GitHub Actions build check only (`npm run build`) — no unit tests needed (static site, no backend logic)

### CI/CD Tool Decision: GitHub Actions
Chosen over CircleCI, Jenkins, Render built-in, pre-commit hooks.

**Why GitHub Actions:**
- Free, native to GitHub repos
- Integrates with Render deploy webhooks (test-gate)
- Scales to matrix builds, Docker, staged pipelines, scheduled runs, reusable workflows
- 2,000 free minutes/month for private repos

### ML-Specific Tooling — What's Relevant vs Overkill

| Tool | Relevance | Decision |
|---|---|---|
| **MLflow Model Registry** | High — Point 14 on plan | Build after CI is done |
| **DVC** | Low — datasets are static | Skip for now |
| **Apache Airflow / Prefect** | Low — no live data feeds yet | Skip until Point 16 (real-time data) |
| **Kubeflow** | None — K8s overkill | Ignore completely |
| **Dagster / ZenML** | Low–Medium | Revisit after MLflow |

### Practical Tooling Roadmap
```
Now        → GitHub Actions (CI/CD)         ← Point 11, 17
Next       → MLflow (experiment tracking)   ← Point 14
Later      → Grafana + Prometheus           ← Point 12
Much later → DVC / ZenML                    ← only if datasets grow
Never      → Kubeflow                        ← overkill
```

### GitHub Actions Pipeline Design

**ML-Unified (Python/FastAPI):**
```
on: push / PR to main
jobs:
  test → ruff lint → pytest
  deploy → only if test passes (Render webhook)
```

**ML-Portfolio (Next.js):**
```
on: push / PR to main
jobs:
  build → npm ci → npm run build → tsc --noEmit
```

Points completed together: **11 (CI pipeline) + 17 (test-gate deploy)**

---

## What Was Built This Session

### Unit Tests — ML-Unified (`tests/test_api.py`)

18 tests covering all critical endpoints:

| Test Group | Tests |
|---|---|
| Health & meta | `test_health`, `test_list_models`, `test_list_models_fields` |
| Schema | `test_get_schema_iris`, `test_get_schema_insurance`, `test_get_schema_not_found` |
| Predict — classification | `test_predict_iris_setosa`, `test_predict_iris_virginica`, `test_predict_titanic`, `test_predict_diabetes` |
| Predict — regression | `test_predict_insurance` |
| Predict — errors | `test_predict_model_not_found` |
| Analyze CSV | `test_analyze_csv_classification`, `test_analyze_csv_regression`, `test_analyze_csv_bad_file` |
| Unsupervised | `test_unsupervised_kmeans`, `test_unsupervised_pca`, `test_unsupervised_dbscan` |

All 18 passed locally. Runner: pytest + FastAPI TestClient.

### Dev Dependencies (`requirements-dev.txt`)
```
-r requirements.txt
pytest==8.3.5
httpx==0.28.1
ruff==0.9.10
```

### GitHub Actions CI — ML-Unified (`.github/workflows/ci.yml`)
```
on: push / PR to main
jobs:
  test  → ruff check app.py → pytest tests/ -v
  deploy → curl RENDER_DEPLOY_HOOK_URL (only if test job passes, only on push to main)
```
Secret required: `RENDER_DEPLOY_HOOK_URL` (added to GitHub repo secrets by user)

### GitHub Actions CI — ML-Portfolio (`.github/workflows/ci.yml`)
```
on: push / PR to main
jobs:
  build → npm ci → tsc --noEmit → npm run build
```

### Lint Fixes in `app.py`
- E401: split `import joblib, pandas as pd, json, os, io, re` into individual imports
- E741: renamed ambiguous variable `l` → `lbl` in 4 places (dict comprehensions + generator)

---

## Commits

| Repo | Hash | Description |
|---|---|---|
| ML-Unified | `d643311` | Add CI pipeline, unit tests, and lint fixes |
| ML-Portfolio | `4153c6f` | Add CI pipeline for build and type check |

---

## Updated 20-Point Plan Score: 12 done, 8 pending

| # | Item | Status |
|---|---|---|
| 1–10 | (previously done) | ✅ Done |
| 11 | Portfolio: CI/CD pipeline (GitHub Actions) | ✅ Done |
| 12 | Monitoring — Grafana + Prometheus | ⬜ Pending |
| 13 | Data drift / model drift detection | ⬜ Pending |
| 14 | MLflow experiment tracking | ⬜ Pending |
| 15 | CNN / image classification task type | ⬜ Pending |
| 16 | Data injection (DB, cloud, real-time) | ⬜ Pending |
| 17 | Test-gate CI (block deploy if tests fail) | ✅ Done |
| 18 | E2E browser testing — Playwright | ⬜ Pending |
| 19 | Full pipeline validation commit → live | ⬜ Pending |
| 20 | CI/CD end-to-end pipeline test automation | ⬜ Pending |

---

## 20-Point Plan — Verified Status

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | What-if sliders | ✅ Done | Sessions 8–9 |
| 2 | Prediction comparison table | ✅ Done | Sessions 8–9 |
| 3 | Feature importance / Key Factors bar chart | ✅ Done | Session 7 |
| 4 | CSV batch upload (`/predict/upload`) | ✅ Done | Session 7 |
| 5 | Testing suite — 33 unit tests (Insurance) | ✅ Done | Session 6 |
| 6 | Dark/light theme toggle | ✅ Done | Session 9 |
| 7 | Portfolio: project cards per dataset | ✅ Done | Part 10 — ML-Portfolio built |
| 8 | Portfolio: embed/proxy each project's UI | ✅ Done | Part 12 — ML-Unified is the unified platform |
| 9 | Portfolio: navbar, About, Projects sections | ✅ Done | Part 10 — Next.js components |
| 10 | Portfolio: registry-based new project addition | ✅ Done | Part 10 registry.json + Part 12 `/train` auto-registers |
| 11 | Portfolio: CI/CD pipeline (GitHub Actions) | ⬜ Pending | Individual repos have CI, but ML-Portfolio / ML-Unified do NOT have a GitHub Actions workflow — only Vercel/Render auto-deploy |
| 12 | Monitoring — Grafana + Prometheus | ⬜ Pending | Listed in every pending list through Part 13 |
| 13 | Data drift / model drift detection | ⬜ Pending | Listed in every pending list through Part 13 |
| 14 | MLflow experiment tracking | ⬜ Pending | Listed in every pending list through Part 13 |
| 15 | CNN / image classification task type | ⬜ Pending | Listed in Part 12 & 13 pending |
| 16 | Data injection (DB, cloud, real-time) | ⬜ Pending | CSV upload done; DB/cloud/real-time not built |
| 17 | Test-gate CI (block deploy if tests fail) | ⬜ Pending | Listed in every pending list through Part 13 |
| 18 | E2E browser testing — Playwright | ⬜ Pending | Listed through Part 13 |
| 19 | Full pipeline validation commit → live | ⬜ Pending | Listed in Part 12 |
| 20 | CI/CD end-to-end pipeline test automation | ⬜ Pending | Not completed in any session |

**Summary: 10 done, 10 pending.**

---

## Key Correction Made This Session

Point 11 was incorrectly marked as Done in an earlier summary. Clarified:
- GitHub Actions CI (`.github/workflows/ci.yml`) was added to individual ML repos (Iris, Titanic, Diabetes, Insurance) — that is separate work.
- ML-Portfolio (Vercel) and ML-Unified (Render) do NOT have GitHub Actions CI pipelines — they only use platform auto-deploy on push.
- Point 11 is genuinely **Pending**.

---

## Immediate Carry-Overs from Part 14 (before tackling 20-point items)

- ⬜ Confirm DBSCAN fix returns 3 clusters on `test_clusters.csv` on live deploy (`https://ml-unified.onrender.com`)
- ⬜ Confirm MCP servers in `ml-portfolio` (run `claude` inside ml-portfolio folder → approve the 3 MCP servers)

---

## Suggested Next Priority Order

1. Confirm DBSCAN fix (carry-over from Part 14)
2. Confirm MCP in ml-portfolio (carry-over from Part 13)
3. **Point 15** — CNN / image classification task type (last missing task type in ML-Unified)
4. **Point 11** — GitHub Actions CI for ML-Unified (test → deploy gate)
5. **Point 17** — Test-gate CI (block Render deploy if tests fail)
6. **Point 14** — MLflow experiment tracking
7. **Point 13** — Data drift / model drift detection
8. **Point 12** — Monitoring — Grafana + Prometheus
9. **Point 18** — E2E browser testing — Playwright
10. **Point 16** — Data injection (DB, cloud, real-time)
11. **Point 19** — Full pipeline validation commit → live
12. **Point 20** — CI/CD end-to-end pipeline test automation

---

## Standing Rules

- Apply changes to ALL affected repos simultaneously
- Conversation logs stored in `ML-Iris/Conversations/` folder
- Light theme: ALL elements must adapt
- Vercel = portfolio only (ML-Portfolio repo); Render = ML app (ML-Unified repo)
- ML-Portfolio → Vercel auto-deploy on push to main
- ML-Unified → Render auto-deploy on push to main (~3–5 min free tier)
- pkl files trained with scikit-learn==1.8.0, Python 3.14 — keep scikit-learn pinned, unpin pandas/numpy
- ML-Unified schema is auto-generated on upload/train — never hand-write schemas for new models
- Unsupervised analysis: always dataset-in → visualization-out, no saved model
- `.mcp.json` must never be committed — always in `.gitignore`
