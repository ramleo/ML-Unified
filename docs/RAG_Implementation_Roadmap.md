# RAG Pipeline Implementation — ML-Unified

## Context

ML-Unified is a FastAPI-based AutoML platform deployed on HuggingFace Space (CPU-only, ~16GB RAM, persistent `/data/` directory). It already integrates 5 LLM providers (Anthropic, OpenAI, Groq, Gemini, Cohere) but uses them only for post-training text generation — no retrieval, no embeddings, no knowledge base.

The goal is a **state-of-the-art RAG pipeline** that:
1. Powers the existing `ToolsAIChat` component (present on every tool page in ml-portfolio) with grounded, citation-backed ML answers
2. Augments the `/explain` endpoint with retrieved algorithm documentation
3. Provides a `/rag/ingest` endpoint so users can upload their own domain documents
4. Is built incrementally in 4 phases — from working MVP to agentic RAG

---

## Architecture Overview

```
User Query (ToolsAIChat)
        │
        ▼
 [Query Expansion]  ← LLM generates 3 alternative phrasings
        │
   ┌────┴─────┐
   ▼          ▼
 BM25      Dense Embeddings
(sparse)   (jina-v3 / MiniLM)
   └────┬─────┘
        ▼
  RRF Fusion (top 50)
        │
        ▼
  Cross-Encoder Reranker (top 8)
        │
        ▼
  Context Compression
        │
        ▼
  LLM Generation (SSE stream)
        │
        ▼
  Response + Sources → ToolsAIChat
```

**Phase 3 adds:** CRAG relevance grader → conditional web fallback before LLM generation  
**Phase 3 adds:** LangGraph agentic loop for multi-step queries

---

## Tech Stack

| Component | Phase 1 (MVP) | Phase 2 (Prod) | Phase 3 (Advanced) |
|-----------|--------------|----------------|---------------------|
| Framework | LlamaIndex core | LlamaIndex core | LangGraph (agentic) |
| Vector Store | ChromaDB (in-process) | Qdrant (Docker) | Qdrant |
| Embedding | `all-MiniLM-L6-v2` (22MB) | `jina-embeddings-v3` (570MB) | same |
| Sparse | `rank-bm25` | `rank-bm25` | same |
| Reranker | None | `ms-marco-MiniLM-L-6-v2` | Cohere Rerank 3 (API) |
| Evaluation | None | RAGAS | RAGAS + CI integration |
| Web Fallback | None | None | DuckDuckGo via `httpx` |

HF Space constraint: CPU-only → no GPU-dependent models. All embedding/reranker models must be CPU-compatible.

---

## Knowledge Base (Pre-seeded)

Store at `/data/knowledge_base/` (persists across HF Space restarts):

- `sklearn_algorithms.md` — Decision Trees, RF, SVM, LogReg, Ridge guide
- `xgboost_guide.md` — XGBoost hyperparameters, tuning strategy, best practices
- `lightgbm_guide.md` — LightGBM vs XGBoost, leaf-wise vs level-wise
- `catboost_guide.md` — CatBoost categorical handling, why it wins on tabular
- `shap_interpretation.md` — How to read SHAP values, force plots, beeswarms
- `optuna_tuning.md` — TPE sampler, n_trials, pruning, metric selection
- `feature_engineering.md` — Encoding, scaling, polynomial, binning, datetime
- `feature_selection.md` — ANOVA, mutual info, RFE, when to drop features
- `ensemble_methods.md` — Voting vs stacking, diversity, meta-learner choice
- `ml_best_practices.md` — Train/val/test split, leakage, overfitting, data drift
- `imbalanced_data.md` — SMOTE, class weights, precision-recall trade-offs
- `regression_metrics.md` — R², RMSE, MAE — when each matters
- `classification_metrics.md` — Accuracy, F1, AUC-ROC, confusion matrix reading

---

## New Backend Files (all ≤ 400 lines each)

```
services/ml-api/routers/rag/
├── __init__.py           ← register router; init vector store + embedding on startup
├── ingest.py             ← document loading, chunking, embedding, indexing
├── retrieve.py           ← BM25 + dense hybrid retrieval with RRF fusion
├── rerank.py             ← cross-encoder reranking + context compression
├── query.py              ← FastAPI endpoints: /rag/query (SSE), /rag/ingest, /rag/health
└── evaluate.py           ← RAGAS evaluation endpoint /rag/evaluate (Phase 2)

services/ml-api/data/knowledge_base/
└── *.md                  ← 13 pre-seeded ML knowledge docs (see above)
```

### `__init__.py` — Startup
- Singleton `RagState`: holds `chroma_client`, `embedding_fn`, `bm25_index`, `reranker`
- On app startup: load all docs from `/data/knowledge_base/` → chunk → embed → index
- Exposes `get_rag_state()` dependency for FastAPI routes

### `ingest.py` — Chunking Strategy
- **Recursive semantic chunking**: 450 tokens, 10% overlap (LlamaIndex `SentenceSplitter`)
- Preserve metadata: `source_file`, `section_header`, `chunk_index`
- Also maintain document-level BM25 corpus (list of tokenized chunks)
- Endpoint: `POST /rag/ingest` — accepts `.txt`, `.md`, `.pdf` file upload
- PDF parsing: `pypdf` (lightweight, CPU-friendly)

### `retrieve.py` — Hybrid Retrieval
```python
# Pseudocode
def hybrid_retrieve(query, k=50):
    dense_hits = vector_store.similarity_search(embed(query), k=k)
    sparse_hits = bm25.get_top_n(tokenize(query), corpus, n=k)
    return reciprocal_rank_fusion([dense_hits, sparse_hits], k=k)
```
- RRF formula: `score(d) = Σ 1 / (rank(d, list) + 60)`
- Returns top-50 candidates for reranking

### `rerank.py` — Cross-Encoder + Compression
- Phase 1: skip (pass top-8 directly from retrieval)
- Phase 2: `cross-encoder/ms-marco-MiniLM-L-6-v2` loaded once at startup
- Score each (query, chunk) pair → sort → take top-8
- Context compression: drop chunks scoring < 0.3 threshold
- Output: ordered list of `{text, score, source, metadata}`

### `query.py` — FastAPI SSE Endpoint
```
POST /rag/query
Body: { query: str, tool_context: str, history: list, stream: bool }

Response (SSE):
  data: {"type": "source", "doc": {...}}   ← one per retrieved chunk
  data: {"type": "token", "text": "..."}   ← streamed LLM tokens
  data: {"type": "done", "sources": [...]} ← final summary
```
- Uses existing LLM client pattern from `automl_helpers.py` (supports all 5 providers)
- Prompt template injects: `tool_context` (which page the user is on) + retrieved chunks + query
- Streaming via `StreamingResponse` (already used in `/train` endpoint)

---

## Frontend Changes (ml-portfolio)

### `src/components/ToolsAIChat.tsx`
- Replace current generic chat with RAG-aware chat:
  - `POST /rag/query` with `{ query, tool_context, history, stream: true }`
  - Parse SSE stream: accumulate tokens, show sources as they arrive
  - Render `<RagSourceCard>` for each retrieved source below the response
  - Keep existing gear icon / provider selector UI

### New: `src/components/RagSourceCard.tsx`
- Small collapsible card: shows `source_file` + excerpt snippet
- Accent color matches parent tool page
- `[source: sklearn_algorithms.md]` style citation inline in response text

---

## New `requirements.txt` additions

```
# RAG core
llama-index-core>=0.12.0
llama-index-vector-stores-chroma>=0.3.0   # Phase 1
llama-index-vector-stores-qdrant>=0.4.0   # Phase 2

# Embeddings
sentence-transformers>=3.4.0

# BM25 sparse
rank-bm25>=0.2.2

# Vector store
chromadb>=0.5.0                            # Phase 1
qdrant-client>=1.13.0                      # Phase 2

# PDF parsing
pypdf>=5.0.0

# Evaluation (Phase 2)
ragas>=0.2.0

# Async HTTP for web fallback (Phase 3)
httpx>=0.28.0
```

---

## Phase 1 — MVP (Weeks 1–2): Working RAG end-to-end

**Goal**: `ToolsAIChat` answers ML questions grounded in the knowledge base.

**Steps:**
1. Add `routers/rag/` package + register in `app.py`
2. Create 13 knowledge base `.md` files in `/data/knowledge_base/`
3. `ingest.py`: load docs at startup → SentenceSplitter (450 tok, 10% overlap) → ChromaDB
4. `retrieve.py`: dense-only retrieval (BM25 added in step 5)
5. `retrieve.py`: add BM25 index + RRF fusion (dense + sparse → top 50 → top 8)
6. `query.py`: `POST /rag/query` SSE endpoint with retrieved context injection
7. Update `ToolsAIChat.tsx`: call `/rag/query`, parse SSE, render sources
8. Create `RagSourceCard.tsx` component
9. HF Space upload: all new `.py` files + `requirements.txt`
10. Verify: ask "why did XGBoost win?" → see retrieved XGBoost guide chunks in response

**Acceptance**: ToolsAIChat on AutoML page answers grounded ML questions with cited sources.

**Verified working end-to-end 2026-07-01.** Step 10 was blocked for most of this period by an
unrelated infra bug, not a RAG logic bug: the Dockerfile never `COPY`'d `data/` into the image and
`.dockerignore` excluded `*.md` globally, so the 13 KB docs were never actually indexed
(`0 chunks in corpus, 0 in ChromaDB` since Phase 1 shipped). Every "wrong source" / "zero sources"
symptom traced back to this — not retrieval, reranking, or calibration logic, which were all sound
once real KB content was actually present. Fixed via `COPY --chown=appuser:appuser data/ data/`
+ a `.dockerignore` exception for `data/knowledge_base/*.md`.

---

## Phase 2 — Production Hardening (Weeks 3–4) ✅ COMPLETE

**Goal**: Better retrieval quality, reranking, evaluation, user document upload.

**Steps:**
1. ☑ Jina v3 embedding: `jinaai/jina-embeddings-v3` (570MB) lazy-loaded via `/rag/prepare-jina`; switchable per query via `embedding_model: "jina"` — done
2. ☑ Add `rerank.py`: `ms-marco-MiniLM-L-6-v2` cross-encoder (top 50 → top 8) — done 2026-06-30; upgraded to L-12-v2 2026-07-03
3. ☑ Query expansion: LLM generates 2 alternate phrasings before retrieval, RRF-merged across
   variants, reranked against the original query — done 2026-06-30 (`expand.py`, `llm.py`)
4. ☑ `POST /rag/ingest`: user uploads `.pdf`, `.md`, `.txt` → chunk + embed + add to store — done (Phase 1)
5. ☑ `evaluate.py`: `POST /rag/evaluate`, `POST /rag/eval-run`, `GET /rag/eval-history`, `GET /rag/eval-dashboard` — RAGAS-style LLM-judged metrics; Chart.js dashboard — done 2026-07-03
6. ☑ ChromaDB retained (Qdrant migration skipped — ChromaDB handles our scale fine; DATA_DIR env var makes it trivially swappable)
7. ☑ Semantic caching: embed query → cosine ≥ 0.95 check → return cached response; `state.semantic_cache` in `RagState` — done
8. ☑ Response metadata: `latency_ms`, `chunks_retrieved`, `cache_hit`, `jina_status`, `embedding_used` — done
9. ☑ Update `ToolsAIChat.tsx`: "Upload Document" button → POST to `/rag/ingest` — done 2026-06-30
10. ☑ Multi-tenant document isolation: `session_id` on each ingest, `source_sessions` map in `RagState`, `session_id` filter propagated through `multi_query_retrieve` — done
11. ☑ `GET /rag/uploads`, `DELETE /rag/uploads/{source}` — manage/remove uploaded documents (KB docs protected) — done 2026-06-30
12. ☑ Duplicate-upload detection — returns 409 instead of silently double-indexing — done 2026-06-30
13. ☑ BM25 stopword filtering (`text.py`) — done 2026-06-30
14. ☑ Relevance filtering: relative threshold (≥30% of top score) replacing fixed absolute floor — done 2026-07-01
15. ☑ DATA_DIR env var: all `/data/` paths configurable via env; platform-independent — done 2026-07-03

**Eval status**: L-12 reranker deployed 2026-07-03 — run `/rag/eval-run` to get updated metrics.

---

## Phase 3 — Advanced RAG: CRAG + Agentic (Weeks 5–6) ✅ COMPLETE

**Goal**: Self-correcting retrieval; multi-step agentic queries.

### CRAG (Corrective RAG) ☑
- `routers/rag/crag.py` (95 lines) — relevance grader + web search fallback
- Tavily search (API key optional) with DuckDuckGo instant-answer fallback (no key needed)
- Triggered automatically when local retrieval confidence is low

### LangGraph Agentic Loop ☑
- `routers/rag/agent.py` (313 lines) + `routers/rag/agent_nodes.py` (187 lines)
- 5-node graph: `router → retrieve → grade → [rewrite → retrieve loop | generate]`
  - **router**: classify factual vs. complex multi-hop
  - **retrieve**: hybrid retrieval (BM25 + dense, optional Jina)
  - **grade**: LLM binary relevance grade per chunk
  - **rewrite**: reformulate query if retrieval poor (max 3 loops)
  - **generate**: final SSE streaming response
- Endpoint: `POST /rag/agent`

### RAG-Enhanced `/explain`
- Not implemented — `automl_helpers.py` is at the 400-line limit. Deferred until Phase 4 or a modularization pass.

---

## Phase 4 — ML-Specific RAG (Weeks 7–8)

**Goal**: Dataset-aware recommendations, hierarchical indexing for long docs.

1. **Dataset Schema RAG**: after CSV analyze, embed schema (column names + types + stats) → retrieve similar dataset handling guides from KB
2. **RAPTOR Hierarchical Indexing**: for ML papers > 10k tokens, build recursive cluster-and-summarize tree → retrieves at multiple abstraction levels
3. **Algorithm Recommendation RAG**: given data characteristics (n_rows, n_features, imbalance ratio, task) → retrieve "which algorithm wins on similar data" from indexed benchmark results
4. **Multimodal** (optional): if ML papers with figures are indexed, use LlamaIndex `MultimodalVectorStoreIndex` to embed page images via CLIP

---

## `app.py` Change

```python
from routers.rag import query as rag_router
app.include_router(rag_router.router, prefix="/rag")
```

---

## File Size Constraints (CLAUDE.md Rule 3)

Before touching any existing file:
- `routers/core/automl_helpers.py` (435 lines) — **already over 400**; extract `_prompt_builders.py` before Phase 3 RAG-enhanced explain
- All new RAG files: designed to stay ≤ 400 lines each

---

## Verification Plan

### Phase 1
1. `curl -X POST /rag/query -d '{"query":"why did XGBoost beat Random Forest?"}' --no-buffer` → verify SSE stream with sources
2. Open ToolsAIChat on AutoML page → ask "what hyperparameters matter for XGBoost?" → see `[source: xgboost_guide.md]` citation
3. Check HF Space `/rag/health` → returns `{status: ok, chunks_indexed: N}`

### Phase 2
1. Upload a custom PDF via `/rag/ingest` → query against it → verify retrieval
2. Run RAGAS via `POST /rag/evaluate` → check faithfulness > 0.75
3. Send identical query twice → second response returns `cache_hit: true` in < 100ms

### Phase 3
1. Ask ambiguous query with empty KB topic → verify CRAG triggers web fallback, sources show `web:` prefix
2. Complex multi-hop query → verify LangGraph agent loops retriever twice before generating

---

## HF Space Upload (CLAUDE.md Rule 4)

After every backend commit that touches `services/ml-api/**`:
- Upload all changed `.py` files to `wram1708/ml-unified` HF Space
- Strip `services/ml-api/` prefix from `path_in_repo`
- Also upload updated `requirements.txt`
- HF Space will rebuild Docker image — verify `/rag/health` after restart

---

---

# Research Findings — RAG Techniques & Benchmarks (2024–2025)

*Sourced from 3 parallel research agents: codebase audit + two web/paper research sweeps.*

---

## ML-Unified Backend — Full Folder & File Structure

```
services/ml-api/
├── app.py                                      # FastAPI entry point (134 lines)
├── requirements.txt                            # Dependencies
├── Dockerfile
├── README.md
├── .python-version
│
├── routers/
│   ├── core/                                   # Core ML/AutoML (3,133 lines total)
│   │   ├── __init__.py
│   │   ├── shared.py                           # Global state, model loading, HF sync (198 lines)
│   │   ├── automl.py                           # Main /train endpoint (400 lines)
│   │   ├── automl_helpers.py                   # LLM explanation + prompt building (435 lines) ⚠️ over 400
│   │   ├── automl_optuna_explain.py            # Optuna tuning explanations (122 lines)
│   │   ├── automl_clf.py                       # Classification-specific logic (304 lines)
│   │   ├── automl_reg.py                       # Regression-specific logic (302 lines)
│   │   ├── automl_fe.py                        # Feature engineering (129 lines)
│   │   ├── automl_preprocess_helpers.py        # Preprocessing utilities (224 lines)
│   │   ├── automl_train_work.py                # Model persistence logic (256 lines)
│   │   ├── fe_transformer.py                   # Custom feature transformer class (215 lines)
│   │   └── inference.py                        # /predict, /analyze, /explain (217 lines)
│   │
│   ├── shap.py                                 # SHAP explainability endpoint (276 lines)
│   ├── drift.py                                # Data drift detection & monitoring (581 lines)
│   ├── eda.py                                  # Exploratory data analysis (403 lines)
│   ├── pipeline.py                             # Pipeline inspection endpoint (141 lines)
│   ├── training.py                             # Training workflow orchestration (91 lines)
│   │
│   └── pipeline_builder/                       # Pipeline composition & export (1,229 lines)
│       ├── __init__.py
│       ├── automl_stage.py                     # AutoML pipeline stage (400 lines)
│       ├── stages.py                           # Generic pipeline stages (393 lines)
│       ├── comparison.py                       # Model comparison logic (222 lines)
│       └── export.py                           # Export to Python/scikit-learn (201 lines)
│
├── schemas/                                    # Pre-built model metadata JSON
│   ├── diabetes.json
│   ├── iris.json
│   ├── titanic.json
│   └── insurance.json
│
├── models/                                     # Trained model artifacts (joblib/pickle)
│   ├── [model_id]_pipeline.pkl
│   ├── [model_id]_labels.pkl
│   ├── [model_id]_fe.pkl
│   └── [model_id]_actuals.json
│
├── data/                                       # Persistent JSON storage
│   ├── drift_buffer.json                       # Rolling window of recent predictions
│   └── drift_history.json                      # Timestamped drift snapshots
│
├── frontend/                                   # Static HTML/JS UI (served by FastAPI)
│   ├── index.html
│   ├── favicon.ico
│   └── icon.svg
│
├── shared/
│   └── progress.py                             # Progress tracking utilities
│
└── tests/
    ├── conftest.py
    └── test_api.py
```

### Registered FastAPI Routes (app.py)

```python
app.include_router(inference_router.router)     # /predict, /analyze, /explain, /models/{id}/export
app.include_router(automl_router.router)        # /automl/preprocess, /train, /model/{id}/download
app.include_router(monitoring_router.router)    # /metrics, /request-log
app.include_router(_shap_router.router)         # /shap/{model_id}
app.include_router(_pipeline_router.router)     # /pipeline/{model_id}
app.include_router(_training_router.router)     # /train-model
app.include_router(_drift_router.router)        # /drift/{model_id}, /drift/{id}/upload, /drift/{id}/history
app.include_router(_pb_router)                  # /pipeline-builder/* endpoints
```

Root endpoints: `GET /` (frontend HTML), `GET /health`, `GET /system-info`, `GET /app-config`

### Existing LLM Integration Pattern (automl_helpers.py:352–436)

All 5 providers (Anthropic, OpenAI, Groq, Gemini, Cohere) supported via `_llm_explanation()`. Called after training to explain results. This exact pattern will be reused for RAG generation.

```python
# Provider routing in _llm_explanation():
# Anthropic → anthropic.Anthropic() client (45s timeout)
# OpenAI/Groq/Custom → openai.OpenAI() client (compatible API)
# Gemini → urllib.request to REST API
# Cohere → urllib.request to REST API
```

### Persistence Layer

| Data | Format | Location |
|------|--------|----------|
| Trained models | `.pkl` (joblib) | `models/` |
| Model metadata | `.json` | `schemas/` |
| Drift buffer | `.json` (rolling) | `data/` |
| Feature engineering | `.pkl` | `models/` |

No SQL, no Redis, no vector DB — everything is file-based. RAG will add `data/knowledge_base/` (markdown) and `data/chroma_db/` (vector index).

---

## ToolsAIChat — Current Wiring (ml-portfolio)

**File**: `src/components/ToolsAIChat.tsx` (385 lines)  
**Used on**: All 7 tool pages — AutoML, Optuna, SHAP, Ensemble, Preprocessing, FE, FS

### How It Currently Works

1. **Floating bubble** (bottom-right, fixed position) — opens/closes chat panel
2. **Provider selector**: Gemini, Claude, OpenAI, Groq, Together AI, Mistral, Perplexity (7 providers)
3. **Model selector**: per-provider model list (e.g. Gemini 2.5 Flash, Claude Haiku 4.5, Llama 3.3 70B)
4. **API key**: optional — stored in `localStorage` only, never persisted server-side
5. **Send flow**:
   ```
   User types → POST /api/ai-tools (Next.js API route)
     body: { messages, provider, model, userKey, toolContext }
   ← returns { reply: string }   (non-streaming, full response at once)
   ```
6. **Tool context injected**: each page passes `{ tool: "AutoML Wizard", summary: "..." }` — prepended to the prompt as system context

### What Changes for RAG

| Current | After RAG |
|---------|-----------|
| Calls `/api/ai-tools` (Next.js route → direct LLM) | Calls `POST ML_UNIFIED_API/rag/query` (FastAPI RAG pipeline) |
| Returns full `reply` string at once | Streams SSE: `source` events + `token` events + `done` event |
| No retrieval — pure LLM generation | Retrieves from ML knowledge base first, injects context |
| No sources shown | `<RagSourceCard>` rendered per retrieved chunk |
| `toolContext` as plain string | `tool_context` field + `history` array sent to backend |

### Props Interface (unchanged — context passes through)

```typescript
type ToolChatContext = {
  tool: string;     // e.g. "AutoML Wizard", "Optuna Tuning", "SHAP Explainability"
  summary: string;  // description of the tool — injected as system context in RAG prompt
};
```

The `tool` field tells the RAG backend which page the user is on → used to bias retrieval toward relevant knowledge base docs (e.g. SHAP page → prioritize `shap_interpretation.md`).

---

## Codebase Baseline (ML-Unified as of 2026-06-29)

| Aspect | Status |
|--------|--------|
| LLM Integration | ✅ 5 providers (Anthropic, OpenAI, Groq, Gemini, Cohere) |
| Vector Store | ❌ None |
| Embeddings | ❌ None |
| Document Storage | ❌ None (model .pkl + JSON only) |
| Chunking / Parsing | ❌ None |
| Semantic Search | ❌ None |
| Conversation Memory | ❌ Stateless |
| RAG code | ❌ Zero — LLMs used for generation only |

LLM clients live in `routers/core/automl_helpers.py` (lines 352–436). Pattern supports all 5 providers via a unified `_llm_explanation()` function. This same pattern will be reused for RAG generation.

---

## Key RAG Research Papers (2023–2025)

### Foundational
- **RAG (Lewis et al., 2020)** — original paper; showed retrieval + generation outperforms closed-book LLMs on knowledge-intensive NLP tasks
- **RAG Survey 2024** ([arxiv 2410.12837](https://arxiv.org/abs/2410.12837)) — tripartite analysis of retrieval, generation, augmentation strategies; essential reading
- **RAG Survey May 2025** ([arxiv 2506.00054](https://arxiv.org/html/2506.00054v1)) — covers RQ-RAG, RAG-Fusion, advanced recall improvements

### Self-Correcting & Adaptive RAG
- **Self-RAG (ICLR 2024 Oral)** — model learns to emit reflection tokens (`[Retrieve]`, `[IsRelevant]`, `[IsSupportive]`) to decide when to retrieve and whether context is useful. Outperforms ChatGPT on open-domain QA. Requires instruction-tuned or fine-tuned LM.
- **CRAG — Corrective RAG (Yan et al., 2024)** ([openreview](https://openreview.net/forum?id=JnWJbrnaUE)) — lightweight retrieval evaluator grades docs as Correct / Incorrect / Ambiguous. If Incorrect → triggers web search fallback. Not a linear pipeline — conditional branching based on confidence.
- **Speculative RAG (arxiv 2407.08223)** — drafting approach for faster generation

### Multi-Query & Fusion
- **RAG-Fusion (Feb 2024)** ([arxiv 2402.03367](https://arxiv.org/abs/2402.03367)) — 3-stage: LLM generates 5–10 query variants → parallel retrieval for each → Reciprocal Rank Fusion merges. Better recall and robustness than single-query RAG. Simple to implement (1–2 extra LLM calls).
- **HyDE — Hypothetical Document Embeddings** — LLM generates a hypothetical answer → embed that → retrieve real docs using hypothetical embedding. Bridges semantic gap between query and documents. 25–60% latency increase on small LLMs; worth it for domain-specific or specialized corpora.

### Hierarchical & Long-Doc
- **RAPTOR (arxiv 2401.18059)** — bottom-up: embed → cluster → summarize → build parent nodes. Retrieves at multiple abstraction levels (leaf chunks + summaries). 20% absolute improvement on QuALITY benchmark (complex multi-step QA) paired with GPT-4. Best for documents > 10k tokens.
- **Late Chunking (arxiv 2409.04701)** — embed full document first (token-level), then cluster tokens into chunks. Each chunk retains global document context. Better semantic coherence vs. traditional chunking.

### Agentic RAG
- **Agentic RAG Survey (Jan–Apr 2025, arxiv 2501.09136)** — RAG as loop not pipeline. LLM acts as reasoning engine with plan-act-observe cycles. Multi-agent coordination, iterative refinement, tool use.
- **PlanRAG, Search-o1, Search-r1, GraphSearch** — representative 2024–2025 agentic RAG methods
- **LangGraph** — best production framework for agentic RAG loops; supports cyclic graphs, checkpoints, human-in-the-loop

### Knowledge Graph RAG
- **GraphRAG (Microsoft, 2024)** — 20k+ GitHub stars by EOY 2024. Autonomous entity extraction via LLM → relationship mapping → community detection via Leiden algorithm. Enables "global reasoning" (patterns across corpus) that standard RAG fails at. Best for: finance, healthcare, customer intelligence, supply chain. LLM-intensive at construction time — use selectively.
- **ROGRAG (arxiv 2503.06474)** — Robustly Optimized GraphRAG Framework

### Evaluation
- **RAGAS** — industry standard RAG evaluation framework. LLM-as-judge (no expensive human eval at scale). Key metrics: Faithfulness, Answer Relevancy, Context Precision, Context Recall.
- **FVA-RAG (arxiv 2512.07015)** — Falsification-Verification Alignment to reduce sycophantic hallucinations

---

## Advanced RAG Techniques — Details

### 1. Hybrid Search (Dense + Sparse BM25)
**Why**: Dense vector search captures semantic meaning; BM25 captures exact keyword matches. Neither alone is sufficient.  
**Key finding**: On many benchmarks, BM25 alone outperforms even OpenAI `text-embedding-3-large` alone — never skip sparse retrieval.  
**Improvement**: Hybrid + Cohere Rerank achieved +17.4% relative Recall@5 vs. hybrid alone.  
**Fusion**: Reciprocal Rank Fusion (RRF): `score(d) = Σ 1/(rank(d, list) + 60)`  
**Implementation**: `rank-bm25` library for sparse; sentence-transformers for dense; custom RRF merge.

### 2. Cross-Encoder Reranking
**Why**: Retrieve top-50 candidates cheaply, then rerank to top-8 accurately. Cross-encoders score query+document jointly (much more accurate than bi-encoders but slower).  
**Top models**:
- Cohere Rerank 3 (API, highest quality)
- `cross-encoder/ms-marco-MiniLM-L-6-v2` (open-source, self-hosted, good balance)
- `BAAI/bge-reranker-base` (open-source, multilingual)  
**Token savings**: 80%+ context reduction after reranking without quality loss.

### 3. Context Compression
**Hard compression**: Extractive — select only relevant sentences from retrieved chunks.  
**Soft compression**: Maps context to dense embeddings (requires fine-tuning).  
**Practical impact**: 40–60% token reduction post-rerank.  
**Implementation**: Drop chunks scoring < 0.3 after cross-encoder; extractive sentence selection.

### 4. Query Expansion (Multi-Query)
**How**: LLM generates 3–5 alternative phrasings of user query → retrieve for each → deduplicate + RRF merge.  
**Cost**: 1–2 additional LLM calls per query. Cheap and highly effective.  
**Best for**: Multi-turn conversations, ambiguous queries, domain-specific terminology.

### 5. Semantic Caching
**How**: Embed incoming query → check cache with cosine similarity ≥ 0.95 → return cached response if hit.  
**Impact**: 50–80% API call reduction; 5–10x speed improvement.  
**Implementation**: In-memory dict or Redis. Key = query embedding; value = full response + sources.  
**LLM calls are 10–100x more expensive than embeddings** — caching is the single highest ROI optimization.

### 6. CRAG (Corrective RAG) — Implementation Pattern
```
Retrieve → Grade each chunk (LLM: "relevant" | "irrelevant" | "ambiguous")
    ├─ All relevant → generate directly
    ├─ Ambiguous → web search to supplement
    └─ All irrelevant → web search fallback, discard local results
```
Web fallback: DuckDuckGo via `httpx` (no API key needed).

### 7. LangGraph Agentic Loop — Node Structure
```
router → retriever → grader → rewriter ──┐
                        │                ↓
                        └──────────► generator (SSE)
                   (loop if poor retrieval, max 3 iterations)
```
- **Router**: classify query type (factual / analytical / multi-hop)
- **Grader**: LLM binary grade per chunk (pass/fail)
- **Rewriter**: reformulate query to improve retrieval
- **Generator**: final streaming response

---

## Embedding Models — Ranked (MTEB Retrieval Benchmark 2025)

| Rank | Model | Size | MTEB Score | Cost | Best For |
|------|-------|------|-----------|------|---------|
| 1 | Gemini Embedding 2 | API | 67.71 | Paid API | Multimodal (text+image+PDF+audio) |
| 2 | Cohere Embed v4 | API | 65.2 | Paid API | General purpose, high quality |
| 3 | OpenAI text-3-large | API | 64.6 | Paid API | Established, not updated since Jan 2024 |
| 4 | Jina v5-text-small | 677M | ~71.7 | Free, self-hosted | **Best quality-to-size ratio** |
| 5 | Qwen3-Embedding-8B | 8B | ~70+ | Free, self-hosted | Emerging leader, Apache 2.0 |
| 6 | BGE-M3 | ~570M | 63.0 | Free, self-hosted | Multilingual (100+ languages) |
| 7 | all-MiniLM-L6-v2 | 22MB | ~58 | Free, self-hosted | Smallest/fastest; good for MVP |

**For ML-Unified (HF Space, CPU-only):**
- Phase 1: `all-MiniLM-L6-v2` — 22MB, loads in seconds, excellent for MVP
- Phase 2: `jina-embeddings-v3` — 570MB, best open-source quality/size ratio
- If multimodal needed later: Gemini Embedding 2 API (avoids painful migration)

---

## Vector Store Comparison

| Store | Deployment | Scaling | HF Space Fit | Hybrid Search | Best For |
|-------|-----------|---------|-------------|---------------|---------|
| **ChromaDB** | In-process | Single node | ✅ Perfect | ❌ No | Dev/prototyping |
| **Qdrant** | Docker | Horizontal | ✅ Good | ✅ RRF built-in | **Production** |
| **Weaviate** | Docker | Horizontal | ⚠️ Heavier | ✅ BM25+vector | Knowledge graphs |
| **FAISS** | In-memory | Single node | ⚠️ No REST | ❌ Manual | Max speed, batch |
| **Milvus** | Kubernetes | Distributed | ❌ Too heavy | ✅ Yes | 100M+ vectors |
| **Pinecone** | Managed | Automatic | ✅ Yes | ❌ Limited | Zero-ops, high cost |

**Decision for ML-Unified:**
- **Phase 1**: ChromaDB (zero ops, SQLite-backed, persistent)
- **Phase 2**: Qdrant Docker container with `/data/` persistent volume on HF Space
- pgvector benchmarks: 471 QPS @ 99% recall on 50M vectors; Qdrant: 41 QPS — Qdrant better fit for our scale

---

## Chunking Strategies — Ranked

| Strategy | When to Use | Token Size | Overlap | Recall Impact |
|----------|------------|-----------|---------|---------------|
| **Recursive Semantic** | Default for all text | 400–512 | 10–20% | +9% vs. naive |
| **Semantic (sentence similarity)** | When boundary quality matters | Variable | 0% | +5–10% |
| **Document-aware** | PDFs with headers/tables | Per section | Varies | High for structured |
| **Late Chunking** | Long docs (>10k tokens) | Post-embed | 0% | Best coherence |
| **RAPTOR** | Complex multi-step QA | Multi-level | — | +20% on QuALITY |
| **Page-level** | Paginated PDFs | Per page | 0% | Won NVIDIA benchmarks |

**Recommendation for ML-Unified:**
- All knowledge base `.md` files: Recursive semantic, 450 tokens, 10% overlap (LlamaIndex `SentenceSplitter`)
- User-uploaded PDFs: Document-aware (respect headers) + page-level fallback
- Future ML papers: RAPTOR hierarchical indexing

---

## RAG Frameworks Comparison

| Framework | Token Overhead | Best For | Learning Curve | Production Readiness |
|-----------|--------------|---------|----------------|---------------------|
| **LlamaIndex** | ~1.60k avg (lowest) | Core RAG, data ingestion, 150+ connectors | Low | ⭐⭐⭐⭐⭐ |
| **LangChain** | ~2.40k avg | Agents, complex workflows, tool use | Medium | ⭐⭐⭐⭐⭐ |
| **Haystack** | ~1.57k avg (best) | Modular pipelines, A/B testing, debugging | Medium | ⭐⭐⭐⭐ |
| **LangGraph** | ~2.03k | Agentic RAG, multi-step reasoning | Medium | ⭐⭐⭐⭐ |

**Decision for ML-Unified:**
- Phase 1–2: **LlamaIndex** (lowest token overhead, simplest API, best indexing)
- Phase 3: Add **LangGraph** for agentic loop only (not replacing LlamaIndex)
- Avoid Haystack (pipeline-first design adds friction for our FastAPI integration)

---

## RAGAS Evaluation Metrics — Detail

| Metric | What It Measures | Good Score | How Computed |
|--------|-----------------|-----------|-------------|
| **Faithfulness** | Claims in answer grounded in retrieved context (hallucination detection) | > 0.75 | LLM extracts claims → checks each against context |
| **Answer Relevancy** | Answer actually addresses the user's question | > 0.70 | LLM generates questions from answer → checks if original query matches |
| **Context Precision** | Retrieved chunks contain only relevant info (no noise) | > 0.70 | LLM marks irrelevant sentences; precision = relevant/total |
| **Context Recall** | All necessary info was retrieved (nothing missed) | > 0.80 | LLM checks if ground-truth facts appear in retrieved context |

**Why RAGAS > BLEU/ROUGE**: BLEU/ROUGE measure lexical overlap — useless for semantics. RAGAS measures actual RAG behavior using an LLM judge.

**Setup**: Create 50–100 QA pairs with ground-truth answers from the knowledge base. Run RAGAS before and after each phase change to catch regressions.

---

## Production Deployment — FastAPI + HF Space Patterns

### Key Constraints (HF Space Free Tier)
- CPU-only (no GPU)
- ~16GB RAM
- Persistent storage at `/data/` directory
- Docker-based deployment

### Resource Management Rules
1. Load embedding model **once at startup** — not per request
2. Cache reranker in memory (singleton)
3. Use connection pooling for vector store
4. BM25 index held in-memory (fast, cheap for <100k chunks)
5. Semantic cache reduces LLM calls by 50–80%

### Worker Config
- Gunicorn + Uvicorn workers = number of CPU cores (typically 2–4 on HF Space)
- All endpoints `async def` — FastAPI is async-first
- Offload blocking embedding/reranking to thread pool if needed

### Streaming (SSE)
- Already established in `/train` endpoint — same `StreamingResponse` pattern
- RAG responses stream token-by-token + source events
- Frontend parses SSE: accumulate tokens + collect source cards

### Caching Strategy (4 layers)
1. **Semantic query cache** (cosine ≥ 0.95 → return cached): saves 50–80% LLM cost
2. **Embedding cache**: reuse embeddings for identical strings
3. **Retrieval cache**: cache vector search results per query hash
4. **BM25 cache**: pre-tokenized corpus stays in memory

---

## Common RAG Pitfalls to Avoid

| ❌ Pitfall | ✅ Fix |
|-----------|--------|
| Dense-only vector search | Always add BM25 hybrid |
| No reranking | Cross-encoder reranking is near-free quality gain |
| Fixed chunk size without semantic consideration | Recursive semantic splitting |
| Only automated metrics | Add human eval sample for critical features |
| Ignoring token efficiency | Compress context post-rerank (40–60% savings) |
| One embedding model for everything | Different models for retrieval vs. reranking |
| No fallback for low-confidence retrieval | CRAG-style conditional logic |
| Loading embedding model per request | Singleton loaded at startup |
| Ignoring metadata | Filter by doc type, date, source at retrieval time |
| No evaluation baseline | Set up RAGAS from day 1 |

---

## When to Use Each Advanced Technique

| Technique | Use When | Skip When |
|-----------|----------|-----------|
| Hybrid Search (BM25 + dense) | Always — baseline | Never skip |
| Cross-Encoder Reranking | Always for production | Never skip |
| Query Expansion | Ambiguous queries, multi-turn chat | Simple exact-match lookups |
| Semantic Caching | Any API-cost-sensitive deployment | Unlimited budget (unlikely) |
| CRAG | Incomplete KB, high reliability needed | Simple closed-domain systems |
| Self-RAG | Fine-tuned model available | Off-the-shelf LLM only |
| LangGraph Agentic | Multi-step reasoning, tool use | Simple Q&A |
| RAPTOR | Docs > 10k tokens, multi-hop QA | Short focused documents |
| GraphRAG | Global reasoning, relationship analysis | Specific fact lookup |
| Late Chunking | Long docs needing context coherence | Short docs |
| Multimodal RAG | ML papers with figures/tables | Text-only KB |

---

## Key Research Sources

1. [RAG Survey 2024](https://arxiv.org/abs/2410.12837)
2. [RAG Survey May 2025](https://arxiv.org/html/2506.00054v1)
3. [Agentic RAG Survey 2025](https://arxiv.org/abs/2501.09136)
4. [Self-RAG — ICLR 2024 Oral](https://iclr.cc/virtual/2024/oral/19736)
5. [CRAG — Corrective RAG](https://openreview.net/forum?id=JnWJbrnaUE)
6. [RAG-Fusion](https://arxiv.org/abs/2402.03367)
7. [RAPTOR](https://arxiv.org/abs/2401.18059)
8. [Late Chunking](https://arxiv.org/abs/2409.04701)
9. [Enhancing RAG: Study of Best Practices (Jan 2025)](https://arxiv.org/html/2501.07391v1)
10. [Engineering the RAG Stack](https://arxiv.org/pdf/2601.05264)
11. [Best Embedding Models 2025](https://milvus.io/blog/choose-embedding-model-rag-2026.md)
12. [Vector DB Comparison 2025](https://medium.com/tech-ai-made-easy/vector-database-comparison-pinecone-vs-weaviate-vs-qdrant-vs-faiss-vs-milvus-vs-chroma-2025-15bf152f891d)
13. [Best Chunking Strategies 2026](https://www.firecrawl.dev/blog/best-chunking-strategies-rag)
14. [RAGAS Evaluation Guide](https://dkaarthick.medium.com/ragas-for-rag-in-llms-a-comprehensive-guide-to-evaluation-metrics-3aca142d6e38)
15. [GraphRAG — Microsoft Open Source](https://github.com/microsoft/graphrag)
16. [Production FastAPI RAG](https://dev.to/hamluk/building-production-ready-rag-in-fastapi-with-vector-databases-39gf)
17. [The Economics of RAG — Cost Optimization](https://thedataguy.pro/writing/2025/07/the-economics-of-rag-cost-optimization-for-production-systems/)
18. [Dynamic Context Compression for RAG](https://arxiv.org/html/2507.22931v2)

---

## What is "Enterprise-Grade RAG"?

A loose term for RAG pipelines that meet production requirements at scale. Key characteristics:

| Area | What it means |
|------|---------------|
| **Retrieval quality** | Hybrid (dense + sparse), reranking, query expansion, CRAG/self-correction |
| **Scale** | Distributed vector store (Pinecone/Qdrant/Weaviate), not in-process |
| **Multi-tenancy** | Isolated namespaces per org/user, not shared collections |
| **Observability** | Tracing per query (latency, retrieval scores, cache hits), eval metrics (RAGAS) |
| **Guardrails** | PII detection, toxicity filters, hallucination detection |
| **Auth + governance** | API key scoping, audit logs, data retention policies |
| **Evaluation CI** | Automated RAGAS runs on every deploy, regression alerts |
| **Reliability** | SLA, rate limiting, fallback providers, no cold-start delays |

---

## Is Our RAG Enterprise-Grade?

**Retrieval quality: yes. Infrastructure: not yet.**

### What qualifies:
- Hybrid BM25 + dense retrieval with RRF fusion
- Cross-encoder reranking (`ms-marco-MiniLM-L-12-v2`)
- Multi-query expansion (LLM generates alternate phrasings)
- CRAG with web fallback (Tavily + DuckDuckGo)
- Semantic caching (cosine ≥ 0.95)
- Tiered retrieval (uploaded docs → KB priority)
- Confidence scoring + answer source classification (`dataset / uploaded_doc / knowledge_base / web`)
- Multi-provider LLM support (5 providers)
- LangGraph agentic loop (router → retrieve → grade → rewrite → generate)
- Session-scoped multi-tenant document isolation
- RAGAS-style evaluation endpoint

### What's missing for true enterprise grade:
- **ChromaDB is in-process** — not horizontally scalable (Qdrant migration planned, pending)
- **No RAGAS in CI** — eval endpoint exists but not automated on deploy
- **No guardrails** — no PII detection, hallucination scoring, or toxicity filters
- **No auth scoping** on RAG endpoints — anyone with the URL can query
- **No observability dashboard** — latency/score data emitted per response but not aggregated
- **HF Space free tier** — cold starts, single instance, no SLA
- **Logical isolation only** — session_id filter per tenant, not physical namespace separation

### Summary:
The retrieval architecture is solid and competitive — better than most tutorials and many production systems. It becomes enterprise-grade once deployed on a scalable infra (Qdrant + proper hosting), RAGAS is wired into CI, and guardrails are added. The code is ready for that migration; it's an infra and ops gap, not a design gap.
