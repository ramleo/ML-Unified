# Conversation — 2026-06-06 | EDA Explorer + Architecture Discussion (Part 26)

**Date:** 2026-06-06
**Project:** ML-Unified · ml-portfolio

---

## Points Completed This Session

| # | Item | Status |
|---|---|---|
| 1 | Ruff E402 fix — EDA router import moved to top of app.py | ✅ Done |
| 2 | Live Metrics fix — `?mode=eda` shows only ML Unified (not both) | ✅ Done |
| 3 | Live Metrics label — shows "EDA EXPLORER" instead of "ML UNIFIED" in eda mode | ✅ Done |
| 4 | EDA Explorer — full implementation (router + frontend + portfolio card) | ✅ Done (from session start) |
| 5 | Architecture discussion — router vs microservice, extraction path | ✅ Discussed |
| 6 | EDA improvement discussion — aesthetic + new features | ✅ Discussed |

---

## Architecture Clarifications

### Router vs Microservice

| | Router | Microservice |
|---|---|---|
| Deployment | One server, one process | Separate server, separate process |
| Communication | Direct function call (in-memory) | HTTP request over network |
| Cold start | Shared — one start for all routers | Each service starts independently |
| Cost | One Render instance | One Render instance per service |

Analogy: Routers = floors of the same building. Microservices = separate buildings.

### Extracting a router to its own microservice (future)

Only copy `pipeline.py` to a new repo and wire a thin `app.py`. Zero logic changes. Frontend updates one env var (`PIPELINE_API`). Extract only when you feel pain — not before.

### Build Pipeline — ML Unified vs separate card

**Decision: inside ML Unified as a second tab/mode.**
- Name "ML Unified" fits — unifies Quick Predict + full pipeline building
- EDA Explorer and SHAP Interpreter → separate portfolio cards (standalone tools)

### p95 explained

p95 = 95th percentile latency. If p95 = 340ms, 95 of every 100 requests finished in 340ms or less. The slowest 5% took longer. Better than average because average hides outlier pain.

### Should Build Pipeline have its own microservice?

No — not yet. Same service, own router (`ml-api/routers/pipeline.py`). Extract only if training jobs block other requests, or need different compute.

---

## EDA Explorer — What Was Built

### Backend: `services/ml-api/routers/eda.py`

`POST /eda` — accepts CSV upload, returns:

```json
{
  "overview":      { "rows", "cols", "duplicates", "missing_total", "missing_pct" },
  "columns":       [ { "name", "dtype", "is_numeric", "missing", "missing_pct", "nunique" } ],
  "stats":         { "col": { "mean", "median", "std", "min", "max", "q25", "q75", "outliers" } },
  "distributions": { "col": { "type": "histogram|bar", "bins/labels", "counts" } },
  "correlations":  { "labels": [...], "matrix": [[...]] }
}
```

- Numeric columns: histogram (up to 12 cols)
- Categorical columns: top-10 value counts (up to 6 cols)
- Correlation: Pearson, NaN-safe
- Outlier detection: IQR method (1.5× IQR)

Registered in `app.py`:
```python
from routers import eda as _eda_router   # line 2 — ruff-clean
app.include_router(_eda_router.router)
```

### Frontend: `?mode=eda`

- Nav: "EDA Explorer / Exploratory Data Analysis"
- Browser title: "EDA Explorer — Dataset Inspector"
- Sidebar: "Data Tools → EDA Explorer" button (visible in ml/all/eda modes)
- Auto-selects EDA panel on load when `?mode=eda`
- CSV drag-and-drop upload zone
- Results: overview chips → column table → descriptive stats → mini distribution charts → Pearson heatmap

**Mode-aware metrics fixes:**
- `_fetchMetrics`: `APP_MODE === 'eda'` fetches only ml-api metrics
- `_renderMetrics`: `APP_MODE === 'eda'` renders only one section, labelled "EDA EXPLORER"

### Portfolio: `ml-portfolio/src/data/registry.json`

New card:
```json
{
  "id": "eda-explorer",
  "title": "EDA Explorer",
  "url": "https://ml-unified.onrender.com/?mode=eda",
  "accent": "#34d399",
  "tags": ["EDA", "Statistics", "Correlation", "Distributions", "Data Profiling"]
}
```

---

## Bugs Fixed This Session

### 1. Ruff E402 — EDA router import not at top
- **Root cause:** `from routers import eda` placed after all function definitions
- **Fix:** Moved to line 2 of `app.py`, removed duplicate at bottom
- **Commit:** `b58a75c`

### 2. Live Metrics showing both sections in `?mode=eda`
- **Root cause:** `APP_MODE === 'eda'` fell through to `else` branch (show both)
- **Fix:** Added `|| APP_MODE === 'eda'` to the ml branch in both `_fetchMetrics` and `_renderMetrics`
- **Commit:** `8fa0d4b`

### 3. Live Metrics label showing "ML UNIFIED" in eda mode
- **Root cause:** Hard-coded label `'ML Unified'` passed regardless of mode
- **Fix:** `const label = APP_MODE === 'eda' ? 'EDA Explorer' : 'ML Unified';`
- **Commit:** `6fd9d51`

---

## EDA Improvement Discussion

### Aesthetic upgrades (priority order)

| Improvement | Why |
|---|---|
| Plotly distribution charts | Plotly already loaded; interactive hover, much richer than SVG bars |
| Plotly correlation heatmap | Replaces CSS grid; colour scale, hover shows pair names |
| Sticky section tab strip | Overview · Columns · Stats · Distributions · Correlations |
| Colour-coded overview chips | Green/yellow/red based on health |
| Card containers per section | Better visual separation |

### New features (priority order)

| Feature | Value | Effort |
|---|---|---|
| Sample data preview (first 5 rows) | High — first thing any analyst checks | Low |
| Smart insights (auto-text warnings) | High — makes EDA actionable, not just visual | Medium |
| Skewness + kurtosis per column | Signals need for log transform | Low |
| Missing value heatmap (rows × cols grid) | Visual pattern detection | Medium |
| Outlier box plots (Plotly) | Better than IQR count alone | Medium |
| Data quality score (0–100) | Impressive summary metric | Medium |
| Export as HTML report | Useful but not urgent | High |

---

## All Commits This Session

| Hash | Repo | Description |
|---|---|---|
| `b1958d3` | ML-Unified | Add EDA Explorer: /eda endpoint + ?mode=eda frontend + portfolio card |
| `8720bff` | ml-portfolio | Add EDA Explorer card to portfolio registry |
| `b58a75c` | ML-Unified | Fix ruff E402: move EDA router import to top of app.py |
| `8fa0d4b` | ML-Unified | Fix Live Metrics in ?mode=eda: show only ML Unified stats |
| `6fd9d51` | ML-Unified | Show 'EDA Explorer' label in Live Metrics when mode=eda |

---

## Pending

### EDA Explorer improvements (discussed, not built)
- Sample data preview (5 rows)
- Plotly distribution charts (upgrade from SVG)
- Plotly correlation heatmap (upgrade from CSS table)
- Smart auto-insights text
- Skewness + kurtosis in stats table
- Missing value heatmap
- Outlier box plots

### Microservices restructure (paused from Part 25)
- Partial files exist in `ml-api/routers/` and `ml-api/shared/`
- Need: `training.py`, `unsupervised.py`, ml-vision full router split, update both `app.py`, update tests

### SHAP Interpreter (separate portfolio card)
- User uploads model (.pkl) + dataset → SHAP feature importance + summary plot

### Build Pipeline (inside ML Unified, second tab)
- Step-by-step: Load → EDA → Preprocess → Train → Evaluate → Deploy

### Phase 2: Theme palette picker + vision ambient themes
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
- Microservices architecture pattern: modular monolith (router per domain, extractable later)
- ml-vision must have `/` root endpoint and `/favicon.ico` in `_SKIP_PATHS`
- `?mode=eda` treats EDA as part of ml-api for metrics purposes
- New endpoints → own router file in `routers/`, included in `app.py`
