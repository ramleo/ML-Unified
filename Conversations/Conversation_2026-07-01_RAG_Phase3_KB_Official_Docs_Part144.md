# Conversation Part 144 — CRAG, RAG-Enhanced /explain, KB Official Docs
**Date:** 2026-07-01  
**Branch:** main  
**Topics:** CRAG web search fallback, KB replaced with official docs, RAG-enhanced /explain, automl_helpers.py modularization

---

## CRAG Web Search Fallback

### New file: `routers/rag/crag.py` (117 lines)

Triggers when reranker confidence is low (`top_score < 0.05` or no chunks). Uses DuckDuckGo — no API key required.

**Flow:**
1. Try DDG Instant Answer API (`api.duckduckgo.com/?format=json`)
2. If empty, fall back to DDG HTML scrape (`html.duckduckgo.com/html/`)
3. Returns up to 3 chunks with `source: "web:<url>"`

**Threshold discussion:**
- User confirmed `0.05` sigmoid as the threshold (not `not chunks` only)
- Genuine KB hits score as low as 0.028 — threshold was calibrated to avoid false web triggers
- `rerank.py` ABS_FLOOR = 0.01; relative ratio = 0.30

### Changes to `routers/rag/query.py`:
- Added `from routers.rag.crag import web_search_fallback`
- CRAG fires **before** source events are emitted (so web chunks appear inline)
- Done event gains `"web_fallback_used": true/false`

**Commits:** `0b41ae1`, `cebf35d` (threshold restore), `8a1b783` (threshold fix reverted by user)

---

## Knowledge Base — Replaced with Official Documentation

All 13 KB files replaced with content fetched from official sources.

### Round 1 — Library docs (agent, 9 pages):
| File | Source |
|------|--------|
| `sklearn_algorithms.md` (217 lines) | scikit-learn.org (tree, ensemble, linear_model) |
| `xgboost_guide.md` (131 lines) | xgboost.readthedocs.io (model tutorial, parameters) |
| `lightgbm_guide.md` (128 lines) | lightgbm.readthedocs.io (Features, Parameters) |
| `catboost_guide.md` (134 lines) | catboost.ai (algorithm stages, training parameters) |

**Commit:** `d611f84`

### Round 2 — SHAP, Optuna, FE, FS (agent, 5 pages):
| File | Source |
|------|--------|
| `shap_interpretation.md` (82 lines) | shap.readthedocs.io |
| `optuna_tuning.md` (131 lines) | optuna.readthedocs.io (2 tutorial pages) |
| `feature_engineering.md` (135 lines) | scikit-learn.org/preprocessing |
| `feature_selection.md` (150 lines) | scikit-learn.org/feature_selection |

**Commit:** `8550ee7`

### Round 3 — Ensemble, Metrics, Imbalanced (agent, 3 pages):
| File | Source |
|------|--------|
| `ensemble_methods.md` (214 lines) | scikit-learn.org/ensemble |
| `regression_metrics.md` (196 lines) | scikit-learn.org/model_evaluation (regression) |
| `classification_metrics.md` (252 lines) | scikit-learn.org/model_evaluation (classification) |
| `imbalanced_data.md` (246 lines) | imbalanced-learn.org/stable/user_guide |

**Commit:** `7a0d16d`

### Round 4 — ML Best Practices (agent, web search):
| File | Source |
|------|--------|
| `ml_best_practices.md` (131 lines) | Google Rules of ML + ML Crash Course (3 pages) |

**Commit:** `1b9f3b0`

**KB trust discussion:** AI-generated content was accurate on concepts but risky for version-specific API details. Official docs are now the source of truth. All 13 files from official sources.

---

## RAG-Enhanced `/explain`

### Problem
`automl_helpers.py` was 435 lines — over 400-line limit. Required modularization before adding features.

### Modularization
Extracted 3 functions from `automl_helpers.py` into new `automl_explain.py`:
- `_rule_explanation`
- `_build_prompt`
- `_llm_explanation`

**After split:**
- `automl_helpers.py`: 278 lines (was 435)
- `automl_explain.py`: 197 lines (new)

**Callers updated** (import path changed from `automl_helpers` → `automl_explain`):
- `automl_clf.py`
- `automl_reg.py`
- `inference.py`

### RAG Enhancement
Added `_rag_context_for_winner(winner)` in `automl_explain.py`:

```python
def _rag_context_for_winner(winner: str) -> str:
    from routers.rag import get_rag_state
    from routers.rag.retrieve import multi_query_retrieve
    from routers.rag.rerank import rerank
    state = get_rag_state()
    query = f"{winner} algorithm how it works strengths advantages tabular data"
    chunks = rerank(query, multi_query_retrieve([query], state, top_k=20), state, top_k=3)
    # returns formatted KB context or "" if RAG unavailable
```

`_llm_explanation()` calls `_rag_context_for_winner(winner)` before `_build_prompt()` and passes result as `rag_context=` parameter. `_build_prompt` injects it between the system role line and the dataset stats.

Silently no-ops if RAG not initialized.

**Commit:** `57e31b8`

---

## Where RAG-Enhanced Explain Shows in UI

**Location:** AutoML tool → training completion → Step 4 Results → AI Analysis section

**Two explain paths:**
| Path | RAG-enhanced? |
|------|--------------|
| Inline during training (`automl_clf.py` → `_llm_explanation()`) | **Yes** |
| "Generate Analysis" button (`/api/ai-tools` → Vercel → LLM direct) | **No** |

**To test:** Provide LLM key at training time → train → AI Analysis text should reference official KB mechanics (XGBoost regularized objective, LightGBM leaf-wise growth, etc.). Check HF Space logs for: `INFO RAG-enhanced /explain: retrieved KB context for winner=XGBoost`

**Note:** `POST /explain` in `inference.py` is a dead endpoint — not called from the UI. The real path is inline during training.

---

## RAG for Re-generate Button

### Problem
The "Generate Analysis" / "Regenerate" button in the AutoML results UI called `/api/ai-tools` on Vercel — bypassing FastAPI entirely, so no RAG context was injected into the explanation.

**Two paths existed:**
| Path | RAG-enhanced? |
|------|--------------|
| Inline during training (`automl_clf.py` → `_llm_explanation()`) | Yes |
| "Generate" / "Regenerate" button (`/api/ai-tools` → Vercel → LLM direct) | No ← fixed |

### Fix

**Backend** — `services/ml-api/routers/core/inference.py` (commit `7280ce2`):
- Fixed typo: `key_dirs` → `key_drivers` in the rule fallback response of `POST /explain` (line 189)

**Frontend** — `src/hooks/useAutoMLExplain.ts` (commit `9a71093`):
- Added import: `import { ML_UNIFIED_API } from "@/config/urls"`
- Primary path: if `ML_UNIFIED_API` is set, POST to `${ML_UNIFIED_API}/explain` (FastAPI, RAG-enhanced)
  - Body: `{ automl_data, provider, user_api_key?, custom_base_url?, custom_model? }`
  - Response: `{ explanation: {...}, source: "..." }` — used directly (no JSON parsing)
- Fallback: if backend unreachable or `ML_UNIFIED_API` not set, falls through to old `/api/ai-tools` (Vercel) path automatically
- No UI changes — button looks and works identically to the user

### Key Notes
- `automl_explain.py` already had the full prompt requesting `model_comparison` and `actionable_insights` — no prompt changes needed
- `_llm_explanation()` already calls `_rag_context_for_winner(winner)` before building the prompt — the re-generate button now gets the same RAG enrichment as inline training
- HF Space upload: `routers/core/inference.py` uploaded after commit

---

---

## RAG-Used KB Badge (AutoML AI Analysis)

### Problem
No visual signal indicated whether RAG context was actually retrieved when the user clicked Regenerate. The backend logged it but nothing surfaced to the frontend.

### Fix

**Backend — `automl_explain.py`** (commit `1c855f4`):
- `_llm_explanation()` now includes `"rag_used": bool(rag_context)` in its returned dict
- `inference.py` pops `rag_used` from `llm_exp` before returning and includes it in the response as `"rag_used": true/false`

**Frontend — `useAutoMLExplain.ts` + `AutoMLModal.tsx` + `Step4Results.tsx`** (commit `c65edc0`):
- Hook adds `ragUsed` state, sets it from `data.rag_used` on FastAPI success path, returns it
- `AutoMLModal` threads `ragUsed` → `Step4Results` as a prop
- `Step4Results` renders a small `KB` pill badge next to "AI Analysis" header when `ragUsed` is true
  - Accent-coloured background + border, stacked-layers SVG icon, "KB" text
  - Tooltip: "Knowledge-base enhanced — RAG context was retrieved for this explanation"
  - Badge is absent for rule-based fallback or Vercel fallback path

---

## LangGraph Agentic Loop — Deep Search

### Architecture

```
Router → Retriever → Grader → Generator
                        ↓
                     Rewriter → (loops back to Retriever, max 2×)
```

5 nodes. Simple queries skip the Grader entirely (Router classifies → goes direct to Generator). Complex queries enter the grade → rewrite → retrieve loop.

### New Backend Files

**`routers/rag/agent_nodes.py`** (187 lines):
- `_meta_call()` — one-shot LLM helper for router/grader/rewriter. Uses server `GEMINI_API_KEY` + `gemini-2.0-flash` by default (cheapest, zero extra user cost). Falls back to user's provider with its cheapest model.
- `node_router()` — classifies query as `simple` or `complex`
- `node_retrieve()` — reuses existing `multi_query_retrieve` + `rerank`
- `node_grade()` — grades chunk relevance: `good | rewrite | websearch`. Uses only first 200 chars per chunk (~400 token saving vs full text)
- `node_rewrite()` — reformulates query to improve retrieval. Uses `preserve_case=True`
- `edge_after_retrieve()`, `edge_after_grade()` — conditional edge functions

**`routers/rag/agent.py`** (284 lines):
- `AgentState` TypedDict
- LangGraph graph compiled at import: `StateGraph` with 4 nodes + conditional edges. Fails gracefully if `langgraph` not installed (falls back to direct retrieval)
- `_agent_generator()` — sync SSE generator. Runs `_compiled.stream(initial)` and emits `agent_step` events as each node fires. After graph finishes: web fallback if needed → emit sources → stream LLM tokens via existing `llm.py` helpers
- `POST /rag/agent` endpoint. Registered in `app.py` at `/rag` prefix

**`requirements.txt`**: added `langgraph>=0.2.0`, `langchain-core>=0.3.0`

### SSE Event Protocol

```
{"type": "agent_step", "step": "routing",    "loop": 0, "query": "..."}
{"type": "agent_step", "step": "retrieving", "loop": 0, "query": "..."}
{"type": "agent_step", "step": "grading"}
{"type": "agent_step", "step": "rewriting",  "loop": 1, "query": "..."}
{"type": "agent_step", "step": "retrieving", "loop": 1, "query": "<rewritten>"}
{"type": "agent_step", "step": "generating"}
{"type": "source",  "doc": {...}}
{"type": "token",   "text": "..."}
{"type": "done",    "sources": [...], "loops": 1, "rewritten": true, "web_fallback_used": false, "latency_ms": 4200}
```

### Error Handling Per Node
| Node | Failure | Fallback |
|------|---------|----------|
| Router | Exception | Default to `complex` |
| Retriever | Exception | Return previous chunks |
| Grader | Exception | Default to `good` |
| Rewriter | Exception | Use original query |
| Graph-level | Exception | Emit `warning` SSE, do direct retrieval |
| LangGraph not installed | ImportError | Skip graph, direct retrieval only |

### New Frontend Files

**`ChatMessageList.tsx`** (98 lines) — extracted from `ToolsAIChat` to keep it under 400 lines. Props: messages, loading, loadingLabel, sources, sourcesOpen, accentColor, bottomRef, onSuggestion, onSourcesToggle.

**`AgentGraphDiagram.tsx`** (175 lines) — live animated node-highlighter:
- 5 node rows: Query Router, Retriever, Relevance Grader, Query Rewriter, Generator
- Node states: `idle` (dim circle) → `active` (accent fill + pulsing ring CSS animation) → `done` (accent checkmark)
- Loop badge: `loop N×` appears on the Rewriter row with a dashed arrow when `loops > 0`
- Connector lines between nodes; the Rewriter→Retriever connector glows accent when a rewrite happened
- Static (all idle) when no query running; live-animated during a query as `agent_step` SSE events arrive
- Footer note: "Nodes highlight live as your query flows through the graph." when idle

### ToolsAIChat.tsx Changes (397 lines after modularization)
- **Deep Search toggle** in header (magnifier SVG icon). Label: "Deep" / "Std". Accent-highlighted when active
- Tooltip: latency warning "adds ~3–5 s for query refinement"
- Inline latency note below header when Deep Search is on (info SVG + text)
- Calls `/rag/agent` instead of `/rag/query` when Deep Search is on
- `agent_step` SSE events update `agentStep` (active node) and `agentDoneSteps` (completed nodes)
- Loading label is context-aware: "Analyzing query…" / "Searching knowledge base…" / "Refining search…" etc.
- After response: "Query was refined N× for better results" note with refresh SVG if `done.rewritten` is true
- `AgentGraphDiagram` shown below messages when Deep Search is on (max-height 220px, scrollable)

### Token Efficiency
- Router prompt: ~60 input tokens, 1 output token ("simple" or "complex")
- Grader prompt: ~350 input tokens (200 chars × 5 chunks), 1 output token
- Rewriter prompt: ~50 input tokens, ~15 output tokens
- Total meta-call overhead: ~460 input + ~17 output tokens per agentic query
- Meta calls use `gemini-2.0-flash` (server key) — free tier, no user cost

### Test Queries
| Query | Expected path |
|-------|---------------|
| "When should I choose LightGBM over XGBoost for imbalanced classification and how to tune Optuna differently?" | complex → retrieve → grade → rewrite → retrieve → generate (touches 4 KB files) |
| "What is SMOTE?" | simple → retrieve → generate (no grading loop) |
| "How does Kafka handle backpressure?" | complex → retrieve → grade=websearch → web fallback → generate |

---

## Phase Status

### Phase 3 — Status
| Item | Status |
|------|--------|
| CRAG web search fallback | Done |
| RAG-enhanced `/explain` | Done |
| Frontend: Upload Document UI | Done (already existed) |
| Re-generate button RAG | Done |
| RAG-used KB badge (AutoML) | Done |
| LangGraph agentic loop | Done |

### Commits This Session
| Hash | Repo | Description |
|------|------|-------------|
| `0b41ae1` | ML-Unified | CRAG web search fallback |
| `cebf35d` | ML-Unified | Restore 0.05 threshold |
| `d611f84` | ML-Unified | KB: sklearn/xgboost/lightgbm/catboost official docs |
| `8550ee7` | ML-Unified | KB: SHAP/Optuna/FE/FS official docs |
| `7a0d16d` | ML-Unified | KB: ensemble/metrics/imbalanced official docs |
| `1b9f3b0` | ML-Unified | KB: ml_best_practices from Google ML guides |
| `57e31b8` | ML-Unified | RAG-enhanced /explain + automl_helpers modularization |
| `7280ce2` | ML-Unified | fix: key_dirs → key_drivers in /explain rule fallback |
| `9a71093` | ml-portfolio | feat: re-generate button calls FastAPI /explain for RAG |
| `1c855f4` | ML-Unified | feat: surface rag_used flag in /explain response |
| `c65edc0` | ml-portfolio | feat: KB badge when RAG context used in AI Analysis |
| `b1f1df4` | ML-Unified | feat: LangGraph agentic loop — /rag/agent SSE endpoint |
| `b5ef384` | ml-portfolio | feat: Deep Search toggle, live graph diagram, query-refined note |
