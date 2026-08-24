# Conversation — KB Expansion + RAG Quality Tracking
**Date:** 2026-07-03  
**Branch:** main  
**Topics:** Frontend multi-tenant wiring, Phase 4 decision, KB expansion, RAG eval baseline, top_k tuning

---

## Frontend Multi-Tenant Session Wiring

Completed the final piece of Phase 2 — backend had session_id isolation but frontend never activated it.

### Changes
| File | Change |
|------|--------|
| `RagIngestButton.tsx` | Added `onSessionId?: (id: string) => void` prop; fires with `data.session_id` on successful upload |
| `ToolsAIChat.tsx` | Added `sessionId` state + `LS_SESSION` localStorage key; reads on mount, persists on change; passes `session_id` in both `/rag/query` and `/rag/agent` request bodies; added to `send` dependency array |

**Commit:** `c9bbea6` — ml-portfolio  
Upload isolation now fully activated end-to-end.

---

## Phase 4 Decision — Skipped

Phase 4 features (Dataset Schema RAG, RAPTOR, Algorithm Recommendation RAG) assessed as low-value for ML-Unified specifically:
- Dataset Schema RAG: `/explain` already does this via LLM prompt injection
- RAPTOR: KB files are short markdown guides, no long-doc problem
- Algorithm Recommendation RAG: AutoML pipeline already trains and picks empirically

**Decision: Skip Phase 4 indefinitely.**

---

## KB Content Expansion

4 new knowledge base guides added to `services/ml-api/data/knowledge_base/`:

| File | Content |
|------|---------|
| `cross_validation.md` | K-fold, stratified, time-series, group, nested CV; common mistakes |
| `hyperparameter_ranges.md` | Practical ranges for XGBoost, LightGBM, CatBoost, RF, LogReg, SVM; Optuna search spaces |
| `data_leakage.md` | Target/temporal/group/aggregation leakage; detection; sklearn Pipeline fix |
| `clustering_guide.md` | K-Means, DBSCAN, hierarchical, GMM; silhouette/Davies-Bouldin/ARI metrics |

KB now has 17 guides total. New guides indexed automatically on next startup (no code change needed — `load_kb_documents` walks the directory).

---

## RAG Quality Tracking

### QA Test Set
`services/ml-api/data/rag_eval_qa.json` — 20 held-out QA pairs covering all KB topics. Added `.gitignore` exception (`!services/ml-api/data/rag_eval_qa.json`) since data/*.json was excluded.

### eval-run Endpoint
`POST /rag/eval-run` added to `evaluate.py` (272 lines total):
- Loads QA file from `/data/rag_eval_qa.json` (HF Space) or local fallback
- Runs full LLM-judged evaluation (faithfulness, answer_relevancy, context_precision, context_recall)
- Appends timestamped aggregate to `data/rag_eval_log.jsonl`
- Returns aggregate scores + log timestamp

**Commit:** `e21d8e5`

---

## Baseline Eval Results

### Judge comparison (top_k=8)

| Judge | context_precision | context_recall | faithfulness | answer_relevancy |
|-------|------------------|----------------|--------------|-----------------|
| Cohere `command-a-03-2025` | 0.15 | 0.765 | 0.86 | 0.95 |
| Gemini `gemini-3.5-flash` | 0.0375 | 1.0 | 1.0 | 1.0 |
| Gemini `gemini-2.5-flash` | 0.05 | 0.92 | 0.915 | 1.0 |

**Gemini 3.5-flash scores are not trustworthy** — three metrics at exactly 1.0, `gemini-3.5-flash` is not a valid model name and likely fell back to unexpected behavior.

**Gemini 2.5-flash** more believable but still lenient. **Cohere is the reliable baseline.**

**Key finding**: Two independent judges (Cohere + Gemini 2.5) agree `context_precision` is low (~0.05–0.15). Retrieval passes too many irrelevant chunks.

---

## top_k Fix

Reduced rerank `top_k` from 8 → 5 in three places:
- `query.py:174` — `/rag/query` endpoint
- `evaluate.py:162` — eval rerank
- `agent_nodes.py:117` — LangGraph agent retriever node

**Commit:** `6c7c941`

### Results after fix (Cohere judge)

| Metric | top_k=8 | top_k=5 | Change |
|--------|---------|---------|--------|
| `context_precision` | 0.15 | **0.183** | +22% |
| `context_recall` | 0.765 | **0.705** | -8% |
| `faithfulness` | 0.86 | **0.890** | +3% |
| `answer_relevancy` | 0.95 | **0.945** | -0.5% |

Precision improved at the cost of slight recall drop — expected trade-off. Precision still low at 0.18.

---

## Pending

- **Reranker score floor**: Raise absolute threshold to drop weak chunks before they're counted. Next lever for improving context_precision beyond 0.18.
- **Eval log**: `data/rag_eval_log.jsonl` now tracks scores over time — run after each significant change.

---

## Curl for eval-run (Cohere)
```bash
curl -X POST https://wram1708-ml-unified.hf.space/rag/eval-run \
  -H "content-type: application/json" \
  -d '{"provider": "cohere", "model": "command-a-03-2025", "user_key": "cohere_1eFAkmrGKlqELuUAVUOcTdQ4YNQVFh5qdhdkZ9re0zVB7F"}'
```
