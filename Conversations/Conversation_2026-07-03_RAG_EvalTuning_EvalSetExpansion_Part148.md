# Conversation Part 148 — RAG Eval Tuning & Eval Set Expansion
**Date:** 2026-07-03  
**Topics:** Reranker relative ratio tuning, retrieval candidate reduction, eval set 20→50 QA pairs

---

## Context (from Part 147)

- RAG pipeline Phases 1–3 complete
- KB expanded to 17 docs (13 original + 4 new: cross_validation, hyperparameter_ranges, data_leakage, clustering_guide)
- Held-out eval set (20 QA pairs) + `/rag/eval-run` endpoint added
- Baseline eval: precision 0.15, recall 0.765, faithfulness 0.86, relevancy 0.95
- top_k reduced 8→5 → precision 0.183, recall 0.705
- Next identified lever: reranker absolute score floor / relative ratio

---

## Session Work

### 1. Reranker Relative Ratio 0.3 → 0.5 (REVERTED)

**Change:** `_RELATIVE_RATIO` in `rerank.py` raised from 0.3 to 0.5.  
**Hypothesis:** Stricter relative floor would drop weakly-relevant chunks, improving precision.  
**Result (Cohere eval):**
- precision: 0.1667 ↓ (was 0.183)
- recall: 0.665 ↓ (was 0.705)
- faithfulness: 0.870 ↓
- answer_relevancy: 0.900 ↓

**Diagnosis:** Secondary-relevant chunks score 25–45% of the top match. Raising ratio to 0.5 cut them — both precision AND recall dropped, confirming they carried relevant information.  
**Action:** Reverted to 0.3. Commit `ea5fa74`.

Also fixed `agent_nodes.py` which had `abs_floor=0.0` explicitly bypassing the floor — changed to use default. Commit `1ed9e51` (later reverted with ratio revert).

---

### 2. Retrieval Candidates 50 → 20

**Change:** `multi_query_retrieve(..., top_k=50)` → `top_k=20` in `query.py`.  
Agent path was already at 20. Commit `c46f6eb`.

**Result (Cohere eval):**
- precision: 0.125 ↓
- recall: 0.895 ↑↑ (+27%)
- faithfulness: 0.965 ↑↑ (+8%)
- answer_relevancy: 0.950 →

**Analysis:** With a tighter candidate pool, the reranker picks 5 chunks that together cover the topic broadly (high recall, high faithfulness) but each individual chunk isn't laser-focused (lower per-chunk precision). Since recall and faithfulness are more user-visible than precision, **kept top_k=20**.

---

### 3. Full Eval Score History

| Config | precision | recall | faithfulness | relevancy |
|---|---|---|---|---|
| top_k=8 (baseline) | 0.150 | 0.765 | 0.860 | 0.950 |
| top_k=5 rerank | 0.183 | 0.705 | 0.890 | 0.945 |
| ratio=0.5 | 0.167 | 0.665 | 0.870 | 0.900 |
| candidates=20 ✅ | 0.125 | 0.895 | 0.965 | 0.950 |

**Current best config:** candidates=20, rerank top_k=5, relative_ratio=0.3

---

### 4. Status Check — Previously "Pending" Items

Verified via code inspection:
- **Jina v3 embeddings** — ✅ Already implemented (lazy-loaded background thread, `rag_kb_jina` collection)
- **Multi-tenant session isolation** — ✅ Already implemented (`ingest.py` tags chunks with `session_id`, filters at retrieval)
- **RAG-enhanced `/explain`** — ✅ Already implemented in `automl_explain.py` (`_rag_context_for_winner()` retrieves top-3 KB chunks, injects into prompt, returns `rag_used` flag)
- **Qdrant migration** — Skipped (user decision)
- **Phase 4** — Skipped (low value for ML-Unified)

---

### 5. Eval Set Expansion 20 → 50 QA Pairs

Added 30 new QA pairs to `services/ml-api/data/rag_eval_qa.json`. Commit `79f8fc8`.

New topics covered:
- Stacking vs voting ensembles
- Ridge/Lasso/ElasticNet differences
- SVM kernels and use cases
- R² interpretation and when it misleads
- F1 score vs accuracy
- Target leakage
- Nested cross-validation
- DBSCAN eps selection
- LightGBM `num_leaves`
- SMOTE mechanics
- Group k-fold
- Precision vs recall tradeoff
- Davies-Bouldin index
- CatBoost ordered target encoding
- Time series cross-validation
- Gaussian Mixture Models
- XGBoost `subsample` / `colsample_bytree`
- Calinski-Harabasz score
- Repeated k-fold
- XGBoost `min_child_weight`
- SHAP beeswarm plot reading
- LightGBM hyperparameter ranges
- Hierarchical clustering linkage types
- Feature leakage via aggregation
- Optuna TPE vs random search
- Confusion matrix reading
- Extra Trees vs Random Forest
- Log transform use cases
- LightGBM subsample
- Mutual information for feature selection

---

## Commits This Session

| Hash | Description |
|---|---|
| `1ed9e51` | feat(rag): tighten reranker relative ratio 0.3→0.5 |
| `ea5fa74` | revert(rag): restore _RELATIVE_RATIO to 0.3 |
| `c46f6eb` | feat(rag): reduce retrieval candidates 50→20 |
| `79f8fc8` | feat(rag): expand held-out eval set 20→50 QA pairs |

---

## Pending

- **Eval dashboard** — visualize `rag_eval_log.jsonl` trends across runs
- **L-12 reranker** — `ms-marco-MiniLM-L-12-v2` for wider score spreads (precision improvement)
- **Pipeline Cinema FE/FS improvements** (frontend)
