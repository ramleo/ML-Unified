# Microservices Architecture Notes — ML Unified

> Current setup: single HF Space container (monolith). These notes are for future reference when moving to proper cloud infrastructure.

---

## Current Monolith: `services/ml-api/app.py`

All of the below lives in one FastAPI process. Each section is a candidate for extraction into its own microservice.

---

## Candidate Microservices

### 1. Training Service
**What:** `/train` endpoint — AutoML CV, Optuna tuning, final model fit, learning curve, feature importance
**Why split:** Long-running (minutes), CPU-heavy, blocks other requests
**Cloud pattern:** Async job queue (Celery + Redis). Client gets a job ID, polls for status.
**Trigger:** When concurrent users need to train simultaneously without blocking each other

---

### 2. Inference / Prediction Service
**What:** `/predict/{model_id}` endpoint
**Why split:** Lightweight, high-frequency, stateless per request. Can scale horizontally.
**Cloud pattern:** Separate FastAPI pod, auto-scales with load. Models pre-loaded in memory.
**Trigger:** When prediction latency matters or traffic is high

---

### 3. SHAP / Explainability Service
**What:** `/shap/{model_id}` endpoint — SHAP value computation
**Why split:** Heavy compute (~shap library), only called on-demand, not on every prediction
**Cloud pattern:** Separate worker with model loaded, triggered on demand
**Trigger:** When SHAP computation starts timing out or blocking predictions

---

### 4. AutoML Service
**What:** The AutoML CV phase inside `/train` — tests RF, XGB, LGB, CatBoost with 5-fold CV + Optuna tuning
**Why split:** Most CPU-intensive part of training. Could run trials in parallel across workers.
**Cloud pattern:** Parallel workers (one per model), results aggregated. Optuna supports distributed via RDB backend.
**Trigger:** When AutoML takes too long on large datasets; parallel trials would 4× speedup

---

### 5. LLM Explanation Service
**What:** `/automl-explain` endpoint — calls Anthropic/OpenAI/Gemini APIs
**Why split:** Pure external API calls, no compute. Isolates API key management and rate limiting.
**Cloud pattern:** Thin proxy service with key vault integration, retry/fallback logic
**Trigger:** When multiple LLM providers need different auth or rate limit handling

---

### 6. Model Storage / Persistence Service
**What:** `_upload_model_to_hf()`, `_fetch_hf_models()`, `_load()` — HF XET upload/download
**Why split:** I/O bound, independent of compute. Could handle versioning, rollback, multi-storage backends.
**Cloud pattern:** Storage microservice with S3/GCS/HF XET adapters. Training service calls it after fit.
**Trigger:** When moving off HF XET to S3/GCS, or when model versioning is needed

---

### 7. Feature Engineering Service
**What:** `FeatureEngineeringTransformer` — transforms, bins, interactions, polynomial features
**Why split:** Stateful transformer that needs to be consistent between train and predict
**Cloud pattern:** Shared library or separate service that both Training and Inference call
**Trigger:** When FE logic grows complex enough to need independent versioning and testing

---

### 8. Clustering / Unsupervised Service
**What:** K-Means, DBSCAN, t-SNE, PCA endpoints
**Why split:** Completely different workload from supervised ML — no labels, no SHAP, different output
**Cloud pattern:** Separate service, independently deployable
**Trigger:** When unsupervised analysis needs different scaling/memory than supervised

---

### 9. Monitoring / Drift Service
**What:** `/drift`, `/monitor`, `/performance` endpoints — data drift detection, actuals tracking
**Why split:** Always-on background process vs on-demand compute. Could run on a schedule.
**Cloud pattern:** Scheduled job (cron) + separate API for querying results
**Trigger:** When monitoring needs to run continuously in background, not just on user request

---

## Priority Order for Cloud Migration

1. **Training Service** — biggest impact, unblocks concurrent users
2. **Inference Service** — most latency-sensitive
3. **AutoML Service** — parallel trials would dramatically cut training time
4. **SHAP Service** — second most CPU-heavy
5. **Storage Service** — needed before switching from HF XET
6. **LLM Service** — low priority, already external
7. **FE Service** — only if FE logic grows significantly
8. **Clustering Service** — lowest priority
9. **Monitoring Service** — only when active user base exists

---

## Current Bottleneck (HF Space)

Training + SHAP both block the same FastAPI thread. First fix when scaling:
- Job queue with separate training workers (Celery + Redis)
- Keeps inference responsive while training runs in background

---

## Note on Current Refactor Threshold

Per deferred refactor plan: split `app.py` when it exceeds ~1500 lines.
Microservices split follows after that — same principle of not over-engineering prematurely.
