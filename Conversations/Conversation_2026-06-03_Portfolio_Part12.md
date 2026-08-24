# Conversation – 2026-06-03 (Part 12): ML-Unified Built and Deployed

---

## What Was Done This Session

### ML-Unified — Phase 1 Complete

**Repo:** `github.com/ramleo/ML-Unified`  
**Live URL:** `https://ml-unified.onrender.com`  
**Tech:** FastAPI + Vanilla JS (single HTML page)  
**Hosted on:** Render (free tier)

---

## Architecture

```
ML-Unified/
  app.py              FastAPI — /models, /schemas/{id}, /predict/{id}
  requirements.txt    Pinned scikit-learn==1.8.0, unpinned pandas/numpy
  models/             iris_pipeline.pkl, iris_labels.pkl,
                      titanic_pipeline.pkl, titanic_labels.pkl,
                      diabetes_pipeline.pkl, diabetes_labels.pkl,
                      insurance_pipeline.pkl
  schemas/            iris.json, titanic.json, diabetes.json, insurance.json
  frontend/
    index.html        Single-page app: sidebar + dynamic form + result panel
  render.yaml         Service: ml-unified
  .gitignore
```

### API Endpoints
```
GET  /models              → list all models (id, title, task, accent, metric, classes)
GET  /schemas/{model_id}  → full schema including fields, sample, output info
POST /predict/{model_id}  → { field: value, ... } → { prediction, probabilities?, classes? }
GET  /health              → { status, models: [...] }
```

### Schema-Driven Design
Each `schemas/{id}.json` defines everything the frontend needs:
- `fields` — form field definitions (type, min, max, step, options for selects)
- `sample` — fill sample data
- `ensure_cols` — columns to inject as None (e.g. Name/Ticket for Titanic, psd_* for Insurance)
- `id_cols` — pipeline ID columns to inject as NaN
- `output.class_names` — display labels for classification classes
- `accent` — per-model color

### Model Results (all verified locally)
| Model | Prediction | Result |
|---|---|---|
| Iris | Iris-setosa | 99.6% confidence |
| Titanic (female, 1st class) | Survived | 93.2% |
| Diabetes (sample) | Diabetes | 64.5% |
| Insurance (sample) | ₹1564 | — |

---

## Issues Fixed During Deployment

### 1. `backend/` nested structure — Render couldn't auto-detect
- Moved `app.py`, `requirements.txt`, `models/`, `schemas/` to root
- Render auto-detects Python when these are at root

### 2. render.yaml PYTHON_VERSION not quoted
- `value: 3.11.0` → `value: "3.11.0"` (YAML parses unquoted as float 3.11)

### 3. pandas==2.2.2 build failure on Render (Python 3.14)
- No pre-built wheel for cp314 → source compilation fails/hangs
- Fix: removed version pin → `pandas` and `numpy` (pip grabs latest with cp314 wheels)

### 4. POST /predict returning 404
- `Dict[str, Any] = Body(...)` doesn't work reliably in FastAPI 0.136.3
- Fix: changed to `async def predict(model_id, request: Request)` + `await request.json()`

### 5. Titanic pipeline missing Name/Ticket columns
- Fix: added `"ensure_cols": ["Name", "Ticket"]` to titanic.json

### 6. Insurance pipeline missing psd_* date columns
- Fix: added `"ensure_cols": ["Customer Feedback", "psd_year", "psd_month", "psd_day", "psd_day_of_week"]` to insurance.json

---

## Commits
| Hash | Description |
|---|---|
| `6beb305` | Initial build — all files |
| `5a11a6d` | Flatten structure to root |
| `784a609` | Quote PYTHON_VERSION in render.yaml |
| `20e574e` | Remove Procfile (interfered with render.yaml) |
| `feed523` | Unpin pandas/numpy (>=) |
| `7fc6b41` | Remove all version pins from pandas/numpy |
| `9f95ae1` | Fix predict: use Request.json() instead of Body() |

---

## Platform Strategy Decisions (this session)

### Option 1 confirmed: Add ML-Unified to portfolio
- Add as 5th card in `registry.json` pointing to `https://ml-unified.onrender.com`
- The 4 individual cards stay for now; ML-Unified is a platform card with different visual treatment
- Later (after Phase 2): remove the 4 individual cards, ML-Unified becomes the only entry

### Phase 2 Design: Dataset-Agnostic Upload Wizard
Replace terminal prompts from ML-Pipeline-Auto with a 3-step UI wizard:
1. Upload CSV (or image folder/ZIP for CNN)
2. Auto-detect columns → user picks target column
3. Confirm task type + algorithm → train → schema generated automatically → appears in sidebar

The schema is an **output** of training, not a hand-written input.

### Task Type Roadmap

| task | Input | Output |
|---|---|---|
| `classification` | tabular CSV | class + probabilities ✓ |
| `regression` | tabular CSV | numeric value ✓ |
| `clustering` | tabular CSV | cluster assignment + t-SNE/scatter plot |
| `image-classification` | image upload | class + confidence |

The current schema-driven architecture already supports this — each task type renders a different result component. No architecture rework needed, just extend `task` values and add UI panels.

### Unsupervised + CNN Plan
- Clustering (K-means, DBSCAN): no target column, result is scatter/t-SNE plot
- CNN / image classification: image file upload instead of tabular form
- Both fit the existing sidebar + schema + result panel pattern

### Card Removal Plan
- Now: 5 cards (4 individual + 1 ML-Unified platform card)
- After Phase 2 stable: remove 4 individual cards, ML-Unified is the sole portfolio entry
- Individual Render services stay live as fallback but no longer featured

---

## Session 13 — Phase 2 Built and Deployed

### Completed This Session

#### ML-Unified added to portfolio
- Added 5th card to `ml-portfolio/src/data/registry.json`
- Fuchsia accent `#e879f9`, task badge "Platform", metric "4 Models"
- Points to `https://ml-unified.onrender.com`
- Pushed to `github.com/ramleo/ML-Portfolio` → Vercel auto-deployed

#### Phase 2: CSV Upload Wizard — Built and Pushed
**Commit:** `f0f6e33` → `github.com/ramleo/ML-Unified`

**New backend endpoints (`app.py`):**
- `POST /analyze` — reads CSV, returns columns + dtypes + suggested target column + task type
- `POST /train` — trains RF/GBM pipeline, auto-generates schema, saves pkl + registers live (no restart needed)
- Added `python-multipart` to `requirements.txt` for FastAPI file uploads
- Auto-drops 100%-unique string columns (IDs/names) before training
- Classification: LabelEncoder + RF or GBM → reports Accuracy
- Regression: RF or GBM → reports MAE
- Schema fields auto-generated: numeric → number input with min/max/step; low-cardinality → select dropdown

**New frontend (`frontend/index.html`):**
- "Train New Model" button at bottom of sidebar
- 3-step wizard in main area:
  1. Upload — drag & drop or click, shows filename + size
  2. Configure — model name, target column dropdown, task toggle (auto-suggested), algorithm, 8-color accent palette
  3. Train — spinner → success screen with metric → "Use Model" button jumps to new model
- `suggestTask()` re-suggests classification/regression when user changes target column
- Sidebar refreshes automatically after training — new model appears instantly

#### Regression result label fix
- Removed hardcoded "Annual Premium Estimate" from regression result panel
- Now uses `output.sublabel` from schema — insurance keeps its label, auto-trained models show their target column name
- `output.sublabel` is set to `target_col` in `/train` endpoint automatically

---

### Bugs / Issues This Session
- Edit tool couldn't match box-drawing characters (─) in JS comments → used Python script to inject wizard JS
- "Annual Premium Estimate" was hardcoded in `renderResult()` — fixed with `output.sublabel` pattern
- Render free tier redeploy takes 3–5 minutes (scikit-learn install, no build cache on free tier)

---

### Commits (ML-Unified)
| Hash | Description |
|---|---|
| `f0f6e33` | Phase 2: CSV upload wizard — train any dataset from the browser |
| `bd4fd87` | Fix hardcoded 'Annual Premium Estimate' label in regression result |
| `ab10014` | Show target column name as regression result sublabel |

### Commits (ML-Portfolio)
| Hash | Description |
|---|---|
| `5c34bae` | Add ML Unified Platform as 5th portfolio card |

---

## Session 14 — Polish Fixes

### Issues Fixed

#### Regression result label — "Annual Premium Estimate" hardcoded
- Was hardcoded in `renderResult()` for all regression models
- Fix 1: Used `output.sublabel` from schema, fell back to `output.label` then `'Predicted Value'`
- Fix 2: Stored `target_col` as `output.target_col` in all schemas — single source of truth
- Fix 3: Both classification and regression now show `output.target_col` as the result label
- Works for every current and future dataset automatically

#### All 4 existing schemas updated with `output.target_col`
| Schema | target_col |
|---|---|
| iris.json | `Species` |
| titanic.json | `Survived` |
| diabetes.json | `Outcome` |
| insurance.json | `Premium Amount` |

#### `/train` endpoint updated
- Now stores `"target_col": target_col` in `output` for every auto-trained model

#### Browser caching — hard refresh not working
- Root cause: FastAPI served `index.html` with no cache-control headers; browser cached it aggressively
- Fix: Added `Cache-Control: no-cache, no-store, must-revalidate` header to the `/` route
- After this deploy, browser always fetches fresh HTML — no hard refresh needed

---

### Commits (ML-Unified)
| Hash | Description |
|---|---|
| `058ec07` | Use target column name as regression result label, remove redundant sublabel |
| `9f48dc1` | Use target column name as result label for all models |
| `4211f13` | Disable browser caching for index.html |

---

---

## Session 15 — Unsupervised Analysis, Branding, Fixes

### Completed

#### Removed 4 individual portfolio cards
- `registry.json` in ML-Portfolio now has only the ML-Unified card
- Commit `a1643cd` → ML-Portfolio

#### Rebrand: Ramleo → AIRaML
- `layout.tsx` browser tab title: `"ML Portfolio | AIRaML"`
- `Hero.tsx` hero name: `<span className="gradient-text">AIRaML</span>`
- Commit `42f008d` → ML-Portfolio

#### Clustering task type added to Train wizard (commit `1b79f33`)
- "Clustering" radio in wizard step 2, hides target column, shows n_clusters input
- K-Means only algorithm at this point

#### Clustering renamed to Unsupervised + DBSCAN/t-SNE/PCA added (commit `eada55c`)
- Task toggle label: "Clustering" → "Unsupervised"
- Algorithm dropdown for Unsupervised: K-Means, DBSCAN, t-SNE, PCA
- analyzeCSV fixed: full-screen loading overlay replaces tiny button spinner
- "Waking up server…" message shown after 5 s (Render free-tier cold start)

#### Unsupervised Analysis — full rebuild (commit `9a057c9`)
- **Architecture decision**: unsupervised is not "load model → fill form"
  — user always provides a dataset. No saved model concept.
- Sidebar gains "Unsupervised Analysis" section with 4 algorithm buttons
- Clicking any button shows a dedicated panel: description + CSV upload + params + Run
- `/unsupervised` backend endpoint — runs analysis, returns plot_data + stats, nothing saved to disk

| Algorithm | Parameters | Output |
|---|---|---|
| K-Means | n_clusters (2–15) | Scatter + silhouette score + cluster size table |
| DBSCAN | eps + min_samples | Scatter + cluster count + outlier count |
| t-SNE | perplexity | 2D scatter (similarity visualization) |
| PCA | none | Scatter + PC1/PC2 variance explained |

#### DBSCAN color fix + 3D plots (commit `7b892ec`)
- DBSCAN scatter now colors by "Color By" column even when all points are noise
- DBSCAN shows yellow hint when 0 clusters found: "eps too small"
- All 4 algorithms: 2D / 3D toggle added to params
- 3D mode: backend returns z coordinates (PCA/t-SNE 3 components)
- 3D rendered with Plotly.js (CDN, interactive rotatable scatter3d)
- 2D stays on Canvas for speed

#### Commercial use clarification
- K-Means, DBSCAN, t-SNE, PCA are mathematical algorithm names — no trademark/IP issues
- scikit-learn is BSD licensed — fully commercial-friendly

---

### Algorithm Research Notes (for future reference)

| Algorithm | Can predict new point? | Best for |
|---|---|---|
| K-Means | ✅ `.predict()` | Spherical clusters, known k |
| DBSCAN | ❌ No predict | Arbitrary shapes, outlier detection |
| t-SNE | ❌ Visualization only | Exploring high-dim structure in 2D/3D |
| PCA | ✅ `.transform()` (coordinates, not labels) | Variance analysis, feature reduction |

---

### Commits (ML-Unified)
| Hash | Description |
|---|---|
| `1b79f33` | Add clustering task type — K-Means with scatter plot and silhouette score |
| `eada55c` | Fix wizard loading screen, rename to Unsupervised, add DBSCAN/t-SNE/PCA |
| `9a057c9` | Rebuild unsupervised analysis — dedicated panel, proper algorithm UX |
| `7b892ec` | Fix DBSCAN coloring, add 2D/3D toggle, Plotly 3D scatter plots |

### Commits (ML-Portfolio)
| Hash | Description |
|---|---|
| `a1643cd` | Remove 4 individual model cards — ML Unified is the sole portfolio entry |
| `42f008d` | Rebrand name from Ramleo to AIRaML |

---

## Pending (Next Session)
- ⬜ `image-classification` task type (CNN, image file upload)
- ⬜ MLflow experiment tracking (Point 14)
- ⬜ Data drift / model drift detection (Point 13)
- ⬜ Monitoring — Grafana + Prometheus (Point 12)
- ⬜ Test-gate CI (Point 17)
- ⬜ E2E browser testing — Playwright (Point 18)

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
