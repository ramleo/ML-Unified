# Conversation – 2026-06-03 (Part 11): Unified ML Platform Plan

---

## Core Motivation (Why Unified)

This directly evolves what `ML-Pipeline-Auto` already does — instead of fixing bugs across 4 separate repos forever, one unified app means:

- **Fix once, works everywhere** — no more patching the same bug in 4 repos
- **Add a new dataset by uploading a CSV** — no new repo, no new Render service, no code changes
- **Users can switch between models in one place** — single URL, sidebar navigation

---

## Auto-Train Feature — Honest Breakdown

"Upload CSV → auto-train" is the end goal but the hardest part. Here's what it requires:

1. User uploads CSV + picks the target column
2. Backend detects task type (classification if target has few unique values, else regression)
3. Runs preprocessing: handle nulls, encode categoricals, scale numerics
4. Trains a model (Random Forest or Gradient Boosting), evaluates it
5. Saves the `.pkl` + generates a `schema.json` automatically
6. New model appears in the sidebar immediately — no code changes

This is essentially `ML-Pipeline-Auto` running as a live web service, not a local script.

**Build in two phases to avoid a messy half-finished result:**

- **Phase 1** (next session): Unified app with the 4 existing models loaded from pre-built `.pkl` files. Dynamic schema-driven UI. Everything works end-to-end.
- **Phase 2** (session after): Add the CSV upload → auto-train → auto-register flow on top of the working foundation.

---

## What Was Discussed This Session

### Context Recap
- Portfolio live at `https://ml-portfolio-rho.vercel.app`
- 4 separate Render services (Iris, Titanic, Diabetes, Insurance) — each its own repo + deployment
- All 4 bug fixes from Part 10 are live (Fill Sample, Clear resets result panel)

---

## Unified ML Platform — Architecture Plan

**Goal:** Replace 4 separate Render deployments with one unified app that:
- Lists all available models in a sidebar/dropdown
- Loads form schema dynamically per selected model
- Same prediction UI everywhere — only accent color/theme changes per model
- Future: upload a CSV → backend trains and adds it to the list automatically

### Planned Repo: `ML-Unified`

```
ml-unified/
  backend/
    models/           iris.pkl, titanic.pkl, diabetes.pkl, insurance.pkl
    schemas/          iris.json, titanic.json, diabetes.json, insurance.json
    main.py           FastAPI — /models (list), /predict/{model_id} (predict)
    requirements.txt
  frontend/
    index.html        Single page: sidebar + dynamic form + result panel
  render.yaml         Service name: ml-unified
  Dockerfile (optional)
```

### Schema Format (per model)

Each `schemas/{id}.json` defines everything the frontend needs to render the form:

```json
{
  "id": "iris",
  "title": "Iris Species Classifier",
  "task": "classification",
  "accent": "#818cf8",
  "fields": [
    { "name": "sepal_length", "label": "Sepal Length (cm)", "type": "number", "min": 4.0, "max": 8.0, "step": 0.1 },
    { "name": "sepal_width",  "label": "Sepal Width (cm)",  "type": "number", "min": 2.0, "max": 5.0, "step": 0.1 },
    { "name": "petal_length", "label": "Petal Length (cm)", "type": "number", "min": 1.0, "max": 7.0, "step": 0.1 },
    { "name": "petal_width",  "label": "Petal Width (cm)",  "type": "number", "min": 0.1, "max": 2.5, "step": 0.1 }
  ],
  "sample": {
    "sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2
  },
  "output": {
    "type": "classification",
    "classes": ["Setosa", "Versicolor", "Virginica"]
  }
}
```

For regression (Insurance):
```json
{
  "id": "insurance",
  "title": "Insurance Premium Predictor",
  "task": "regression",
  "accent": "#fbbf24",
  "fields": [ ... ],
  "output": {
    "type": "regression",
    "unit": "₹",
    "label": "Estimated Premium"
  }
}
```

### FastAPI Backend (`main.py`)

```python
GET  /models              → list of { id, title, task, accent }
GET  /schemas/{model_id}  → full schema JSON for that model
POST /predict/{model_id}  → { input: {...} } → { prediction, confidence?, label? }
```

- Loads all `.pkl` files at startup into a dict
- Reads schema files from `schemas/` folder
- Single `predict` handler routes to the right model by `model_id`

### Frontend Logic

1. On load: `GET /models` → render sidebar list
2. On model select: `GET /schemas/{id}` → dynamically build form HTML
3. Fill Sample: populate from `schema.sample`
4. Clear: reset all fields + hide result panel
5. Predict: `POST /predict/{id}` → render result (classification label + confidence, or regression value)
6. Accent color applied from schema — one CSS variable `--accent` set per model switch

### Deployment

- One Render service: `ml-unified` → `ml-unified.onrender.com`
- Portfolio `registry.json` gets one new entry pointing to this unified URL
- Old 4 Render services stay live (no breaking changes to existing portfolio links)
- Over time can redirect old URLs or keep both

---

## Standing Rules
- Apply changes to ALL affected repos simultaneously
- Conversation logs stored in `ML-Iris/` folder
- Light theme: ALL elements must adapt — overlays, text, images, buttons, icons
- Vercel = portfolio only; Render = ML projects (Python backend)

## Next Steps (Next Session — Start Here)
- ⬜ **Build `ML-Unified`** — new repo, copy .pkl files, write schemas, FastAPI backend, single-page frontend
- ⬜ MLflow experiment tracking (Point 14)
- ⬜ Data drift / model drift detection (Point 13)
- ⬜ Monitoring — Grafana + Prometheus (Point 12)
- ⬜ Test-gate CI (Point 17)
- ⬜ E2E browser testing — Playwright (Point 18)
- ⬜ Full pipeline validation commit → live (Point 19)
- ⬜ CNN / deep learning project (Point 15)
- ⬜ Data injection (DB, cloud, real-time) (Point 16)
