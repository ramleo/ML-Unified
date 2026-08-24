# Conversation Part 146 — RAGAS LLM-Judged Metrics + Multi-Tenant Upload Isolation
**Date:** 2026-07-02  
**Branch:** main  
**Topics:** Phase 2 completion check, LLM-judged RAGAS evaluation, multi-tenant session isolation

---

## Context (Continued from Part 145)

Part 145 completed all source category badges (KB/Web/User/Model), Tavily web search, universal score filter, second-chance web fallback, and Model badge placeholder. The session ended with a priority list for remaining Phase 2 work.

---

## Phase 2 Completion Audit

User asked to confirm whether these 4 items were done:
- Jina v3 embeddings
- Semantic caching
- RAGAS evaluation
- Multi-tenant upload isolation

### Findings

| Feature | Status |
|---------|--------|
| Jina v3 embeddings | **Done** — `initialize_jina()` loads `jinaai/jina-embeddings-v3`, separate `rag_kb_jina` ChromaDB collection, `/prepare-jina` endpoint, used when `embedding_model="jina"` |
| Semantic caching | **Done** — `_cache_lookup()` / `_cache_store()` in `query.py`, cosine threshold 0.95, LRU cap 100, `cache_hit: true` in done event |
| RAGAS evaluation | **Partial** — `evaluate.py` existed but used cosine proxy metrics (not LLM-judged). `ragas` package not in requirements. |
| Multi-tenant isolation | **Not done** — single global `RagState` singleton, shared `uploaded_sources` set, no session/user scoping. `user:` prefix was frontend-only cosmetic. |

---

## RAGAS — LLM-Judged Metrics

### Why the proxy was insufficient

The old proxy used `cosine(embed(answer), mean(embed(chunks)))` — this measures embedding similarity, not semantic faithfulness. A hallucinated answer can have high cosine similarity to retrieved chunks while still making false claims.

### New implementation (`evaluate.py` rewritten, 209 lines)

All 4 metrics are now LLM-judged via the existing `complete()` function:

**faithfulness** — "Score 0-10: how faithful is the answer to the context only? 10 = every claim grounded in context, 0 = pure hallucination."

**answer_relevancy** — "Score 0-10: how relevant and complete is the answer to the question?"

**context_precision** — Per-chunk Yes/No: "Is this chunk useful for answering the question?" → fraction of Yes answers.

**context_recall** — "Score 0-10: what fraction of the ground truth information is present in the retrieved contexts?"

Helper: `_parse_score()` extracts first number from LLM response, normalizes to [0, 1] (divides by 10 if > 1).

No new dependencies — uses existing `complete()` and providers already wired.

### User experience impact

None. `/rag/evaluate` is a backend-only diagnostic endpoint. Nothing calls it during normal chat. It's for developer use: POST a set of QA pairs, get quality scores back as a test suite.

---

## Multi-Tenant Upload Isolation

### Problem

Before this fix: User A uploads `my_guide.pdf` → chunks stored in shared ChromaDB with no ownership tag → User B's query retrieves User A's private chunks.

### Design

Each `/ingest` call generates a UUID `session_id`. It is:
- Stored in ChromaDB chunk metadata: `{"source": ..., "uploaded": True, "session_id": "uuid"}`
- Stored in BM25 lookup: `state.source_sessions[source] = session_id`
- Returned to the client in the ingest response

When the client passes `session_id` in a `/query` or `/agent` request, retrieval applies:
- **Dense (ChromaDB)**: `where = {"$or": [{"uploaded": false}, {"session_id": "uuid"}]}` — KB chunks always included, only matching user's uploads included
- **BM25**: post-filter — KB chunks always pass; uploaded chunks only pass if `state.source_sessions[source] == session_id`

KB chunks (uploaded=False, session_id="") are always visible to everyone. Only user-uploaded chunks are isolated.

### Files changed

| File | Change |
|------|--------|
| `__init__.py` | Added `source_sessions: dict[str, str]` to `RagState`; Jina re-index includes session_id in metadata |
| `ingest.py` | `index_chunks()` takes `session_id=""` param; populates `state.source_sessions`; `/ingest` generates UUID, returns it; `delete_source` cleans `source_sessions` |
| `retrieve.py` | `dense_retrieve()` takes `where` param; `bm25_retrieve()` takes `session_id` and filters; `hybrid_retrieve()` + `multi_query_retrieve()` thread session_id |
| `query.py` | `QueryRequest.session_id: str = ""`; passed to `multi_query_retrieve` |
| `agent.py` | `AgentState.session_id: str`; `AgentRequest.session_id: str = ""`; threaded into `_agent_generator` |
| `agent_nodes.py` | `node_retrieve` reads `state.get("session_id", "")`, passes to `multi_query_retrieve` |

### Frontend integration needed

After ingesting a file, store the returned `session_id` (e.g. in localStorage or component state). Include it in subsequent `/rag/query` and `/rag/agent` requests. Without it, uploaded chunks still surface (no filter applied when session_id is empty string).

---

## Commit

| Hash | Repo | Description |
|------|------|-------------|
| `0bc76b2` | ML-Unified | feat(rag): LLM-judged RAGAS metrics + multi-tenant upload isolation |

7 files uploaded to HF Space.
