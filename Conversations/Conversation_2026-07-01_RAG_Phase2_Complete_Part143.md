# Conversation Part 143 — RAG Phase 2 Complete
**Date:** 2026-07-01  
**Branch:** main  
**Topics:** Phase 2 implementation (evaluation endpoint, semantic caching, response metadata), Cohere unicode fix

---

## Phase 2 Items Implemented

### Status at session start
- `/rag/ingest` — already implemented (Part 141/142)
- RAGAS evaluation, semantic caching, response metadata — pending

---

## 1. `POST /rag/evaluate` — `routers/rag/evaluate.py` (new file)

Evaluation endpoint without external deps — uses existing MiniLM embeddings.

**Request:**
```json
{
  "qa_pairs": [{"question": "...", "ground_truth": "..."}],
  "provider": "groq",
  "model": "llama-3.3-70b-versatile",
  "user_key": "optional",
  "generate_answers": true
}
```

**Metrics per question:**
- `context_relevance` — avg cosine(embed(question), embed(chunk)) for retrieved chunks
- `answer_coverage` — keyword recall of generated answer vs ground_truth
- `faithfulness_proxy` — cosine(embed(answer), mean(embed(top-4 chunks)))

**Response:**
```json
{
  "aggregate": {"n": 2, "avg_context_relevance": 0.72, "avg_answer_coverage": 0.61, "avg_faithfulness_proxy": 0.68},
  "results": [...]
}
```

Set `generate_answers: false` for retrieval-only evaluation (no LLM key needed).

---

## 2. Semantic Caching — `routers/rag/query.py`

- Embeds each query with MiniLM → cosine check against in-memory cache
- Threshold: **0.95** cosine similarity
- Cache max: **100 entries** (oldest evicted)
- Cache hit: skips expand + retrieve + rerank + LLM entirely

Added to `RagState` in `__init__.py`:
```python
semantic_cache: list[dict] = field(default_factory=list)
```

Cache entry structure: `{embedding, full_text, sources, chunks}`

---

## 3. Response Metadata — `done` SSE event

`done` event now includes:
```json
{
  "type": "done",
  "latency_ms": 3241,
  "chunks_retrieved": 8,
  "rerank_scores": [0.9123, 0.8741, ...],
  "cache_hit": false
}
```

Cache hits return `"embedding_used": "cache"` and significantly lower `latency_ms`.

---

## Bug Fix: Cohere/Gemini Latin-1 Unicode Error

### Error
```
LLM error: 'latin-1' codec can't encode character '”' in position 45
```

### Root Cause
`urllib` (used by `stream_cohere` and `stream_gemini`) encodes string data as latin-1 internally. KB chunks contain curly quotes (`"` `"`) from `.md` files — these land in the system prompt, triggering the encode error.

### Fix
Switched both `stream_cohere` and `stream_gemini` in `routers/rag/llm.py` to use `httpx` (already in requirements). `httpx` handles unicode natively.

**Note:** User reported Cohere still erroring after fix — left unresolved, moved on.

---

## Files Changed

| File | Change |
|------|--------|
| `routers/rag/evaluate.py` | New — evaluation endpoint |
| `routers/rag/__init__.py` | Added `semantic_cache` field to RagState |
| `routers/rag/query.py` | Semantic cache logic + response metadata in done event |
| `routers/rag/llm.py` | Switched Gemini + Cohere from urllib to httpx |
| `app.py` | Registered `rag_eval_router` |

---

## Commits
- `5b872c2` — feat(rag): Phase 2 — evaluation endpoint, semantic caching, response metadata
- `d4fdf30` — fix(rag): switch Gemini+Cohere streaming to httpx — fixes latin-1 unicode error

---

## Phase Status

### Phase 2 — Complete
| Item | Status |
|------|--------|
| Jina v3 upgrade | Done |
| Cross-encoder reranker | Done |
| Query expansion | Done |
| `POST /rag/ingest` | Done |
| RAGAS evaluation endpoint | Done |
| Semantic caching | Done |
| Response metadata | Done |

### Phase 3 — Pending (options presented to user)
1. **CRAG web search fallback** — DuckDuckGo via httpx when `low_confidence=true`
2. **RAG-enhanced `/explain`** — retrieve top-3 KB chunks for winning algorithm before generating explanation
3. **LangGraph agentic loop** — multi-step router → retriever → grader → rewriter → generator
4. **Frontend: Upload Document UI** — button in ToolsAIChat to POST to `/rag/ingest`

Session ended before user chose next item.
