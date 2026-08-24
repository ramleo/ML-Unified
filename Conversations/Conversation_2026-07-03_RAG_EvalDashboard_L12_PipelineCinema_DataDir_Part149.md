# Conversation Part 149 — Eval Dashboard, L-12 Reranker, Pipeline Cinema Fixes, DATA_DIR
**Date:** 2026-07-03  
**Topics:** RAG eval dashboard, L-12 reranker upgrade, Pipeline Cinema FS/AutoML freeze fix, DATA_DIR env var

---

## Context (from Part 148)

- RAG Phases 1–3 complete; eval set expanded 20→50 QA pairs (commit `79f8fc8`)
- Current best config: candidates=20, rerank top_k=5, relative_ratio=0.3
- Metrics: precision 0.005 (problematic), recall 0.970, faithfulness 0.964, relevancy 0.980
- Pending: eval dashboard, L-12 reranker, Pipeline Cinema FE/FS improvements

---

## Session Work

### 1. Eval Dashboard

Added two new endpoints to `services/ml-api/routers/rag/evaluate.py`:

- `GET /rag/eval-history` — returns all logged eval runs as JSON array
- `GET /rag/eval-dashboard` — dark Chart.js HTML page with:
  - Line chart: 4 metric lines over run history (precision=red, recall=green, faithfulness=blue, relevancy=yellow)
  - Color-coded table: green ≥ 0.7, yellow ≥ 0.4, red < 0.4
  - Model name column added (commit `2dcebe6`)

**Why dashboard showed "No eval runs yet":** HF Space restarted on deploy, wiping `/data/rag_eval_log.jsonl` — ephemeral filesystem. Fix: enable Persistent Storage in HF Space settings.

**Why `/rag/eval-run` showed "Method Not Allowed":** It's a POST endpoint — can't hit it via browser URL. Use curl or `/docs` Swagger UI.

Commits: `847d1f5` (dashboard), `2dcebe6` (model column)

---

### 2. L-12 Reranker Upgrade

Changed `cross-encoder/ms-marco-MiniLM-L-6-v2` → `cross-encoder/ms-marco-MiniLM-L-12-v2` in `routers/rag/__init__.py`.

- No requirements.txt change needed (same sentence-transformers library)
- L-12 is ~130MB vs ~23MB for L-6; first HF Space boot will be slower
- Wider score spreads between relevant/irrelevant chunks — expected to improve context_precision

Commit: `ef3dd31`

---

### 3. Platform Independence Discussion

**Question:** Is the app platform-independent / can it be dockerized?

**Answer:** Already has a Dockerfile. Largely platform-independent:
- FastAPI + all deps install via requirements.txt on any platform
- ChromaDB runs in-process, no external DB
- ML models download from HF Hub at startup (works anywhere with internet)
- CPU-only — no GPU dependency

**Only HF-specific assumption:** `/data/` path hardcoded for storage. Fixed via DATA_DIR env var (see below).

**Pre-baking models:** Recommendation — skip for now. Download-at-startup works fine on HF. Pre-bake into Docker image only if moving to a platform where cold starts matter.

---

### 4. Pipeline Cinema Fixes

**Files changed:** `ml-portfolio` repo

#### Bug 1: FSStory re-animates when navigating back during AutoML
**Root cause:** `CinemaScene.tsx` line 292 had `frozen={viewingStage !== null && activeStage === null}`. When AutoML is running, `activeStage="automl"` so `frozen=false`, causing FSStory to re-animate from scratch when user clicks back to FS stage.

**Fix:** Changed to `frozen={viewingStage !== null}` — whenever a stage is pinned for viewing, always show final state regardless of what's currently active.

#### Bug 2: FS narrator text said "low-variance" but uses mutual_info
**Root cause:** `pipelineCinemaApi.ts` FS description lines still referenced "low-variance features" and "variance threshold" despite the API call using `method: "mutual_info"`.

**Fix:** Updated text to "Features with low mutual information with the target" and "low-signal features".

**Already correct (no change needed):**
- FE stage IS sending real log1p transforms (was already implemented)
- FS stage IS using `method: "mutual_info"` (was already implemented)

Commit: `d13ed30` (ml-portfolio repo)

---

### 5. DATA_DIR Env Var

Made all hardcoded `/data/` paths in RAG files configurable via `DATA_DIR` environment variable (defaults to `/data` — HF Space behavior unchanged).

**Files changed:**
- `routers/rag/__init__.py` — HF model cache (`/data/hf_cache`), ChromaDB persist dir (`/data/chroma_db`)
- `routers/rag/evaluate.py` — QA file path, eval log path
- `app.py` — knowledge base directory

**Pattern used:**
```python
_DATA_DIR = os.environ.get("DATA_DIR", "/data")
```

**To use on another platform:** Set `DATA_DIR=/app/data` (or any volume mount path) — no code changes needed.

Commit: `fcf53ed`

---

### 6. Does DATA_DIR Make Data Persist?

**No.** DATA_DIR only makes the path configurable, not persistent.

Current state on HF Space — all ephemeral (wiped on restart):

| Data | Path | Persists? |
|------|------|-----------|
| ChromaDB | `/data/chroma_db` | ❌ |
| Eval log | `/data/rag_eval_log.jsonl` | ❌ |
| HF model cache | `/data/hf_cache` | ❌ |
| Knowledge base | `/data/knowledge_base` | ❌ |

**To make data persist:** Enable Persistent Storage in HF Space settings (Settings → Persistent Storage → Enable). This mounts `/data/` as a real persistent volume. Costs ~$0.5/GB/month on HF.

---

## Commits This Session

| Hash | Repo | Description |
|------|------|-------------|
| `847d1f5` | ML-Unified | feat(rag): eval-history + eval-dashboard endpoints |
| `2dcebe6` | ML-Unified | feat(rag): add model name column to eval dashboard |
| `ef3dd31` | ML-Unified | feat(rag): upgrade reranker L-6-v2 → L-12-v2 |
| `fcf53ed` | ML-Unified | feat: DATA_DIR env var for platform-independent storage |
| `d13ed30` | ml-portfolio | fix(pipeline-cinema): freeze FS/AutoML story on navigate-back; fix FS mutual-info text |

---

## Current State

**RAG pipeline:** Complete (Phases 1–3). Remaining optional items:
- Enable HF Persistent Storage (settings toggle, not code)
- Eval dashboard will populate after next `/rag/eval-run` call

**Pipeline Cinema:** All three originally-identified issues resolved (FE was already correct, FS text fixed, AutoML freeze fixed).

**Platform independence:** Achieved — DATA_DIR env var + existing Dockerfile. Set `DATA_DIR` + mount a volume to deploy anywhere.
