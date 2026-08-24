# Conversation — 2026-06-09 | ML Unified Features (Part 45)

**Date:** 2026-06-09
**Projects:** ML-Unified (Render)
**Continued from:** Part 44

---

## Commits This Session

| Hash | Repo | Summary |
|---|---|---|
| `dd651ff` | ML-Unified | Upgrade drift detection — 7 improvements |
| `3b13607` | ML-Unified | Add SSE progress bars with tqdm for all long-running operations |

---

## Clarification: Drift Baseline Applies to Both Modes

User asked: "above changes will be useful only when we upload a dataset right?"

**Answer:** Yes, in practice the pipeline baseline improvement (extracting real training mean/std) applies to both modes, but only the **upload mode** is reliable. The **predictions buffer** resets on every Render free-tier restart, so drift scores from predictions are never meaningful. The upload mode is the actual working feature.

---

## Feature: 7 Drift Detection Improvements (`dd651ff`)

### 1. Categorical actual frequencies

- `titanic.json` — `cat_freq` added for Sex (male 64.76%, female 35.24%), Pclass (3rd 55.11%, 1st 24.24%, 2nd 20.65%), Embarked (S 72.44%, C 18.90%, Q 8.66%)
- `/train` endpoint — computes `cat_freq` from training CSV for user-trained models
- `drift.py` — uses `field.get("cat_freq")` when available; falls back to uniform
- Frontend — categorical feature cards show "Reference from training data" vs "Reference assumes uniform distribution"

### 2. PSI metric (Population Stability Index)

- Computed for every field alongside z-score
- Numeric: bins actual data vs N(mean, std) reference into 10 equal-width bins
- Categorical: per-option divergence sum
- Thresholds: PSI < 0.10 = stable (green), 0.10–0.25 = caution (amber), > 0.25 = unstable (red)
- Displayed as a small badge next to each feature's drift badge

### 3. KS test

- Upload mode only (needs actual data)
- Two-sample KS test: uploaded values vs synthetic N(training_mean, training_std) reference
- Implemented with numpy + `math.erf` (no scipy dependency needed)
- Asymptotic p-value formula used
- Displays "KS stat: 0.234 · p-value: 0.018 — significant" or "within range"

### 4. Distribution histogram UI

- Per numeric feature: mini 12-bin bar chart showing expected (grey) vs actual (accent color) distribution
- Heights normalised to max = 100%; animated via CSS transition
- Legend shows Expected / Actual swatches
- Only rendered when histogram data is present in response

### 5. Persistent buffer

- Prediction buffer written to `data/drift_buffer.json` after each `record_input()` call
- Loaded from file on startup (survives process restarts, not Render cold starts)
- `data/*.json` added to `.gitignore`; `data/.gitkeep` committed

### 6. Drift trend over time

- Every drift GET or POST call appends a timestamped snapshot to `data/drift_history.json`
- Last 20 snapshots embedded in every drift response as `trend[]`
- Frontend renders SVG sparkline above feature list; line color follows latest drift level
- History endpoint: `GET /drift/{model_id}/history`

### 7. Missing value tracking

- `null_rate` computed per feature from uploaded or predicted rows
- Features with any nulls show a red "X% null" badge next to the field name

---

## Feature: SSE Progress Bars with tqdm (`3b13607`)

### Architecture

```
Browser ──fetch──► FastAPI endpoint
                        │
                        ├── validates input synchronously (HTTPException still works)
                        │
                        └── returns StreamingResponse
                                 │
                                 │   shared/progress.py
                                 │   ┌──────────────────────────────────┐
                                 │   │  StreamingTask.stream(worker_fn) │
                                 │   │    - runs worker_fn in a Thread  │
                                 │   │    - asyncio.Queue as bridge     │
                                 │   │    - yields SSE events           │
                                 │   └──────────────────────────────────┘
                                 │
                              SSE stream: data: {"pct": 35, "msg": "Training..."}
                                          data: {"pct": 100, "result": {...}, "done": true}
```

### `shared/progress.py`

- `StreamingTask` — orchestrates thread + asyncio.Queue + SSE generator
- `_Progress` — wraps `tqdm`; `p.update(pct, msg)` advances tqdm bar in terminal AND sends SSE event to browser
- `p.finish(result={...})` sends the final payload

### Operations with progress bars

| Endpoint | Stages |
|---|---|
| `POST /train` | CSV parse → encode labels → fit model → evaluate → build schema → save |
| `POST /unsupervised` | Prepare features → fit transformers → run algorithm → build plot |
| `POST /shap/{model_id}` | Preprocess → compute SHAP values → aggregate features |

### Frontend

- `_sseStream(response)` — async generator reading SSE chunks line by line with buffer handling
- `_progressBarHTML(fillId, msgId, pctId)` — renders inline progress bar HTML
- `_updateProgressBar(...)` — animates fill width; CSS transition smooths jumps
- All three callers (train wizard, unsupervised panel, SHAP panel) now loop over the stream

### tqdm in server logs

tqdm writes a real progress bar to the terminal on every update:
```
Training Random Forest classifier…:  20%|██        | 20/100%
Training Random Forest classifier…:  82%|████████  | 82/100%
```

### Test changes

- `_sse_result(response)` helper added to `tests/test_api.py` — parses SSE body and returns the final `result` dict
- 5 affected tests updated (`test_train_classification`, `test_train_regression`, `test_unsupervised_kmeans`, `test_unsupervised_pca`, `test_unsupervised_dbscan`)
- All 61 tests still pass

---

## Key Decisions

- **No scipy** — KS test and normal CDF implemented with numpy + `math.erf` from Python stdlib; avoids adding another large dependency
- **Validation before streaming** — input errors (bad CSV, missing columns) still raise `HTTPException` synchronously before the streaming response starts; browser gets a 400 status rather than a 200 with an SSE error event
- **Thread + asyncio.Queue bridge** — standard pattern for streaming from blocking sklearn `.fit()` calls in async FastAPI handlers
- **tqdm as the progress driver** — tqdm advances the internal counter; on each `update()` call the percentage is forwarded to the SSE queue; tqdm bar also visible in Render logs

---

## Standing Rules (unchanged)

- Conversation logs: `ML-Iris/Conversations/Conversation_YYYY-MM-DD_Topic_PartXX.md`
- Never expose `ramleo84@gmail.com` publicly
- `vision_cache/` and `.mcp.json` must never be committed
- Always run `ruff check` + `pytest` before pushing ML-Unified
- User-facing errors: plain English only
- No emojis in UI or code output
- After commit: always push or ask to push

---

## Pending Tasks

| # | Item | Status |
|---|---|---|
| 13 | 35 EDA unit tests | Pending |
| 19 | MLflow experiment tracking | Pending |
| 20 | Playwright E2E tests | Pending |
| 12 | EDA microservice extraction | Deferred |
| 21 | Batch predict — Object Detection + Segmentation | Deferred |
| 11 | Cleaned CSV download | Deferred |
