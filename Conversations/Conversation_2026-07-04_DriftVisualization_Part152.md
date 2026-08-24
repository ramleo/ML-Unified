# Conversation Part 152 — Drift Detection: Rich Visualizations + AI Explanation
**Date:** 2026-07-04  
**Topics:** Drift page visual overhaul, AI explanation panel (Groq/Gemini/Cohere), null handling, feature ranking chart, section descriptions, tooltips

---

## Context (from Part 151)

- Drift detection (#23) shipped end-to-end: `/tools/drift` page, `routers/drift/` package (5 files), batch label versioning
- Last session ended with a working drift page but minimal visualizations (tiny 28px histograms, text-only stats, no charts)

---

## Session Work

### 1. Full Drift Page Visual Overhaul

User flagged 4 issues from screenshot:
1. `{"detail":"Not Found"}` error on "Explain Analysis"
2. No context for what "Drift Trend", "Feature Breakdown", "PSI", "KS Test" mean
3. Only ref mean/std shown — no observed (batch) mean/std
4. Visualizations not rich enough

#### Root cause of error (#1)
FastAPI's built-in 404 (not our custom "Model not found") — the route wasn't registered yet because HF Space hadn't finished restarting after the file upload. Resolves on its own once Space is Running.

**HF Space health check URL:** `https://wram1708-ml-unified.hf.space/rag/health`

#### Null handling (#3)
Backend already drops nulls before computing batch stats (lines 67–71 of `_compute.py`). When `NULL RATE: 100%` / `BATCH N: 0`, there are literally zero non-null values so `recent_mean = None` — "—" is correct. For partial nulls, mean/std is computed on non-null subset. Fix: UI must show this clearly, not hide batch stat cells.

---

### 2. New Backend — `/drift/{model_id}/explain` Endpoint

**`services/ml-api/routers/drift/_explain.py`** (new, 116 lines):
- Builds structured prompt summarizing the full drift result (overall score, per-feature PSI, mean shifts, KS stats)
- Streams tokens via selected provider: Groq (`llama-3.3-70b-versatile`), Gemini (`gemini-2.0-flash`), Cohere (`command-r-plus`)
- Reuses `stream_groq_openai`, `stream_gemini`, `stream_cohere` from `routers/rag/llm.py`
- SSE format: `{"type":"token","text":"..."}` → `{"type":"done"}`

**`services/ml-api/routers/drift/__init__.py`** (modified):
- Added `POST /{model_id}/explain?provider=groq` endpoint
- Uses `Request.json()` to receive full drift result as body
- Returns `StreamingResponse` with `media_type="text/event-stream"`

---

### 3. Frontend — 7 New/Modified Files

#### `driftTypes.ts` (new, 53 lines)
Shared types extracted from DriftRunner: `ModelMeta`, `FeatureDrift`, `TrendPoint`, `DriftResult`, `levelColor()`, `ACCENT`.

#### `DriftFeatureCard.tsx` (rewritten, ~300 lines)
- **`InfoIcon`** — `<span title={tip}>` wrapper around SVG (React `SVGProps` doesn't accept `title` on `<svg>` directly)
- **`MetricCell`** — label + value with optional info icon
- **`StatsTable`** — Reference vs Observed table, always renders all rows:
  - Partial nulls (0 < null_rate < 1): yellow-left-border note "computed on N non-null rows (X% nulls excluded) — differences may be partly explained by which rows were non-null"; column header shows `n=X`
  - Full nulls (null_rate = 1): red-left-border note "All batch values are null"
  - Highlighted in yellow when mean shifts > 10%
- **`GaugeBar`** — gradient-filled horizontal bar, threshold markers at low/high, label + info icon
- **`NumericHistogram`** — 96px tall, y-axis labels (25%/50%/75%/100%), grid lines, gradient bars (training = dim, batch = solid), x-axis range labels, hover tooltips on each bar
- **`CategoricalBars`** — ref/now labeled rows per category, `+/-pp` shift label colored red/green
- **Main card** — high-drift cards open by default; `⚠ high nulls` badge in header when null_rate ≥ 80%; high-null warning banner inside expanded content

#### `DriftOverview.tsx` (modified)
- Every section has a descriptive italic subtitle:
  - **Overall Drift Score**: "Weighted average PSI across all features. 0–10% stable, 10–25% moderate, >25% significant."
  - **Feature Breakdown**: "Count of features in each severity bucket — instantly shows how many columns are at risk."
  - **Drift Trend**: "Overall drift score across successive batch uploads. Rising = worsening shift."
- Trend chart: filled area under curve, y-axis labels, grid lines

#### `DriftRankingChart.tsx` (new, ~100 lines)
- Horizontal bar chart of ALL features ranked by drift severity (high → medium → low)
- Gradient-filled bars colored by level; divider line between severity groups
- PSI value label inside bar when wide enough
- Legend explains bar length is relative to highest drift in batch
- Inserted between `DriftOverview` and `DriftAIExplain` in the page layout

#### `DriftAIExplain.tsx` (new, 200 lines)
- Provider toggle: **Groq** (amber), **Gemini** (green), **Cohere** (purple)
- "Explain Analysis" button → streams SSE from `POST /drift/{model_id}/explain`
- Streaming text output with blinking cursor `▌`
- **Recommendations panel** (auto-generated, no AI needed):
  - High overall drift: retrain immediately, audit pipelines, add data validation
  - Medium: monitor, collect ground truth labels, plan retraining
  - Lists high-drift features by name
  - Lists medium-drift features to watch

#### `DriftRunner.tsx` (simplified, 143 lines)
- Slim orchestrator: config panel + state + imports
- Layout: Overview → Ranking Chart → AI Explain → Feature Cards

---

## Q&A This Session

**Q: How do I know when HF Space is up after a file upload?**
A: Go to `https://wram1708-ml-unified.hf.space/rag/health` — if it returns JSON the Space is fully up. The HF Space dashboard also shows Building → Running status.

**Q: If we impute nulls before computing drift, is that misleading?**
A: Yes — imputing with training mean would make the batch distribution look artificially similar to reference, hiding the actual problem. Correct approach: drop nulls, compute stats on non-null values only, treat null rate shift as a first-class drift signal. Already implemented in backend. UI fix: show "computed on N non-null rows (X% excluded)" note.

**Q: Can we ignore nulls and calculate mean/std, noting that null values are one reason for any difference?**
A: Yes — this is exactly what the backend already does (lines 67–71, `_compute.py`). The frontend now surfaces this context: partial-null stats table shows sample size in column header and a left-bordered note explaining null exclusion.

---

## Commits This Session

| Hash | Repo | Description |
|------|------|-------------|
| `57d6f2b` | ml-portfolio | feat(drift): rich visualizations, AI explanation panel + recommendations |
| `4b006ff` | ml-portfolio | feat(drift): feature ranking chart, section descriptions, null warnings, richer viz |
| `c333c4a` | ml-portfolio | fix(drift): null exclusion context in stats table + InfoIcon SVG type fix |
| `6136050` | ML-Unified | feat(drift): add /drift/{model_id}/explain endpoint with LLM streaming |

HF Space upload complete for `routers/drift/_explain.py` and `routers/drift/__init__.py`.

---

## Files Changed (line counts)

| File | Lines | Status |
|------|-------|--------|
| `src/app/tools/drift/driftTypes.ts` | 53 | new |
| `src/app/tools/drift/DriftRunner.tsx` | 143 | rewritten |
| `src/app/tools/drift/DriftFeatureCard.tsx` | ~310 | rewritten |
| `src/app/tools/drift/DriftOverview.tsx` | ~175 | modified |
| `src/app/tools/drift/DriftRankingChart.tsx` | ~100 | new |
| `src/app/tools/drift/DriftAIExplain.tsx` | 200 | new |
| `services/ml-api/routers/drift/_explain.py` | 116 | new |
| `services/ml-api/routers/drift/__init__.py` | 99 | modified |

---

## Pending (open ☐ items after this session)

| # | Item |
|---|------|
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
