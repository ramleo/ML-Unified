# Conversation — Part 160
**Date:** 2026-07-06  
**Topics:** EDA Microservice Deployment · AI Feature Suggestions (#41) · Dockerize ml-eda (#47)  
**Commits:** `1d0eb8f` `5d65839` (ML-Unified)

---

## Summary

Deployed ml-eda as a standalone microservice on HuggingFace Space, modularized its codebase, added LLM-powered AI feature suggestions (Groq/Gemini/Cohere with SSE streaming and markdown rendering), and wired the "Generate" button into the EDA Explorer UI.

---

## Work Done

### 1. Pending.md + Context

- Updated pending.md "Last updated" to 2026-07-05 (items 41, 47 now done)
- Discussed next steps after #41 (real-world project shortlist deferred)
- Clarified GPU toggle (#28) is currently moot on HF Space free tier (CPU-only)

### 2. EDA Microservice Architecture Discussion

- Explained difference between ml-unified (monolith with UI) and ml-eda (microservice, API only)
- `wram1708/ml-unified` — serves frontend + all ML endpoints; calls ml-eda via `ML_EDA_URL`
- `wram1708/ml-eda` — pure FastAPI API, no UI, one job (EDA/cleaning/suggestions)
- Restaurant analogy: ml-unified = main restaurant, ml-eda = specialist kitchen

### 3. Modularize ml-eda (650 → 5 files, all ≤ 400 lines)

Original `routers/eda.py` was 650 lines — split into:

| File | Lines | Contents |
|------|-------|---------|
| `routers/_utils.py` | 11 | `_to_native()` helper |
| `routers/_stats.py` | 67 | `compute_stats`, `compute_distributions`, `compute_correlations` |
| `routers/_readiness.py` | 243 | `compute_insights`, `compute_quality_score`, `compute_readiness`, `compute_narrative`, `compute_mi`, `compute_pca`, `compute_splom`, `compute_low_variance` |
| `routers/_clean.py` | 194 | `run_clean()` — full cleaning logic |
| `routers/eda.py` | 107 | Thin router — imports functions, two endpoints |

### 4. AI Feature Suggestions — POST /eda/suggest (#41)

**`routers/_suggest.py`** (198 lines):
- `SuggestRequest` Pydantic model: overview, columns, stats, correlations, insights, readiness, narrative, low_variance_cols, provider
- `_build_prompt()` — constructs dataset-specific prompt from EDA stats (skewed cols, outliers, high cardinality, correlation pairs, readiness issues)
- Three async SSE streaming functions:
  - `_stream_groq()` — Groq llama-3.3-70b-versatile via OpenAI-compatible API
  - `_stream_gemini()` — Gemini 2.0 Flash via `streamGenerateContent?alt=sse`
  - `_stream_cohere()` — Cohere command-r-plus-08-2024 via `/v2/chat`
- `POST /eda/suggest` endpoint routes to correct provider based on `req.provider`

### 5. Dockerfile for ml-eda (#47)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN adduser --disabled-password --gecos "" appuser
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY routers/ routers/
USER appuser
EXPOSE ${PORT:-7860}
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}"]
```

`requirements.txt` updated to add `httpx>=0.28.0`.

### 6. HF Space Deployment

- `wram1708/ml-eda` HF Space created (`space_sdk="docker"`)
- All 10 files uploaded: Dockerfile, app.py, requirements.txt, routers/__init__.py, eda.py, _utils.py, _stats.py, _readiness.py, _clean.py, _suggest.py
- `ML_EDA_URL=https://wram1708-ml-eda.hf.space` set as Variable on `wram1708/ml-unified`
- User manually added `GROQ_API_KEY`, `GEMINI_API_KEY`, `COHERE_API_KEY` as Secrets on ml-eda

### 7. EDA Explorer UI Updates (index.html)

**Suggest card in `_renderEDA()`:**
- Provider dropdown (Groq / Gemini / Cohere) next to Generate button
- Subtitle: "LLM-powered recommendations based on your dataset's statistics, distributions, and ML readiness flags"
- `#eda-suggest-output` div for streamed response

**`_runEdaSuggest()` function:**
- Reads selected provider from dropdown
- POSTs full EDA data + provider to `${EDA_API}/eda/suggest`
- During streaming: accumulates tokens, renders as `pre-wrap` text (live typing effect)
- On `done` event: converts full text to styled markdown via `_mdToHtml()`

**`_mdToHtml()` + `_inlineMd()` functions:**
- Numbered items (`N. **Title**`) → indigo left-border card with bold title
- Inline: `**bold**` → `<strong>`, `*italic*` → `<em>`, `` `code` `` → styled `<code>`
- Paragraph blocks → `<p>` tags

**Streaming → Markdown flow (by design):**
- Text shown live during streaming (pre-wrap)
- Converts to styled markdown all at once when LLM finishes
- User noticed the switch — explained it's intentional (stream live → render on done)

---

## Files Changed

| File | Repo | Change |
|------|------|--------|
| `services/ml-eda/routers/eda.py` | ML-Unified | Rewritten as thin router (107 lines) |
| `services/ml-eda/routers/_utils.py` | ML-Unified | New — `_to_native` helper |
| `services/ml-eda/routers/_stats.py` | ML-Unified | New — stats/distributions/correlations |
| `services/ml-eda/routers/_readiness.py` | ML-Unified | New — readiness/insights/PCA/SPLOM/MI |
| `services/ml-eda/routers/_clean.py` | ML-Unified | New — cleaning logic |
| `services/ml-eda/routers/_suggest.py` | ML-Unified | New — Groq/Gemini/Cohere SSE suggest |
| `services/ml-eda/app.py` | ML-Unified | Register suggest router |
| `services/ml-eda/Dockerfile` | ML-Unified | New — Docker build for HF Space |
| `services/ml-eda/requirements.txt` | ML-Unified | Added httpx |
| `services/ml-api/frontend/index.html` | ML-Unified | Provider dropdown + markdown rendering |

---

## Pending After This Session

| Item | Notes |
|------|-------|
| #28 GPU toggle | Moot on HF free tier (CPU-only) |
| #39 Model versioning + rollback | Not started |
| #40 Drift alerting | Email/Slack on drift threshold breach |
| #42 Automated retraining pipeline | Not started |
| #43 Time series forecasting | Prophet/ARIMA/LSTM |
| #44 Microservices migration | When off HF Space |
| #45 E2E Playwright in CI | Suite exists locally |
| #47 Dockerize ml-vision | ml-eda done; ml-vision still pending |
| #50 Batch predictions (vision) | Not started |
| Real-world project | Text-to-SQL Agent shortlisted; decision deferred to next session |
