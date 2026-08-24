# Conversation — 2026-07-01 — RAG Embedding Upgrade: Jina v3 Opt-In + UX Polish (Part 140)

## Summary
Continued from Part 139. Polished RAG source card confidence display, then implemented Jina v3 as an opt-in fallback embedding with lazy loading, automatic ready detection via polling, persistent model cache, and new-data sync into the Jina collection.

---

## Part A — Source Card Badge Polish

### Problem
The source card badge showed `100%` for the top-ranked source (always, by definition) and used `display_score` (relative rank) for coloring. Users had no intuitive way to understand what `100%` meant — it reads as "100% confident" when raw model confidence might be only 23%.

### Fix
- Badge now shows **Low / Medium / High** text instead of a percentage
- Color and label both driven by **raw model confidence** (`rawScore`), not the relative display score
- Tooltip: `"Low confidence — raw model confidence: 23%"` — exact number still accessible on hover
- Expanded view still shows `Raw model confidence: X%` for users who want the number

**File:** `src/components/RagSourceCard.tsx`

| Commit | Description |
|--------|-------------|
| a969813 | fix(rag): source card badge shows Low/Medium/High based on raw model confidence |

---

## Part B — Jina v3 as Opt-In Fallback Embedding

### Background
Current embedding: `all-MiniLM-L6-v2` — 22MB, 384 dimensions, symmetric encoder, general-purpose.
`jina-embeddings-v3`: 570MB, 1024 dimensions, asymmetric (separate query/passage encoders via `task=` param), trained for retrieval, better on technical/domain-specific content.

Problem with immediate upgrade: 570MB download on HF Space CPU cold start = slow. User decision: keep MiniLM as default, expose Jina as an opt-in toggle with a loading indicator.

### Design
**Two triggers to activate Jina:**
1. User clicks the ⚡ toggle in the chat header (Standard → Jina)
2. A query returns `low_confidence: true` (top reranked chunk raw score < 10%) → nudge button appears

**Backend:**
- `RagState` gains: `jina_collection`, `jina_query_fn`, `jina_passage_fn`, `jina_ready`, `jina_loading`
- `initialize_jina(state)` in `__init__.py`: lazy-loads model, creates separate `rag_kb_jina` ChromaDB collection, re-indexes all `corpus_chunks` using `jina_passage_fn`
- `retrieve.py`: `use_jina` flag threads through `embed_query → dense_retrieve → hybrid_retrieve → multi_query_retrieve`; Jina query encoder used for queries, `jina_collection` queried for dense retrieval
- `query.py`: `embedding_model: str = "minilm"` field on `QueryRequest`; `low_confidence` + `jina_status` + `embedding_used` added to `done` SSE event; `POST /rag/prepare-jina` endpoint triggers background `initialize_jina`
- `/rag/health` updated to include `jina_ready` and `jina_loading` fields

**Frontend:**
- `SparkleIcon` (lightning bolt) toggle in chat header — **Std** / **Jina** label, accent-colored when active
- `RagJinaBanner.tsx` (new): renders three states — loading (amber), ready (accent), low-confidence nudge button
- Passes `embedding_model: useJina ? "jina" : "minilm"` in every query request
- `done` event handler: updates `jinaStatus` and `lowConfidence` state
- Polling `useEffect`: while `jinaStatus === "loading"`, polls `GET /rag/health` every 5s; auto-updates banner to "Enhanced embedding active" when `jina_ready: true` — no user action needed

### Data sync gap fix
`index_chunks()` in `ingest.py`: if `state.jina_ready`, newly uploaded chunks are also embedded with `jina_passage_fn` and added to `jina_collection` immediately — no gap between MiniLM and Jina collections after initial load.

`delete_source()` in `ingest.py`: also deletes from `jina_collection` when an uploaded doc is removed.

### Persistent model cache
`Dockerfile`: `ENV HF_HOME=/data/hf_cache` — HF model downloads go to the persistent `/data` volume on HF Spaces. Jina downloads once (~570MB, ~60s), survives Space restarts. Subsequent loads are ~10–15s (weight loading only, no download).

---

## Commits

### ML-Unified
| Hash | Description |
|------|-------------|
| 497c294 | feat(rag): Jina v3 as opt-in fallback embedding — lazy-load, separate collection, low-confidence signal, prepare-jina endpoint |
| 6886bcb | fix(rag): HF_HOME to /data for persistent model cache; sync new chunks+deletes into Jina collection |

### ml-portfolio
| Hash | Description |
|------|-------------|
| a969813 | fix(rag): source card badge shows Low/Medium/High based on raw model confidence |
| 83d8d1d | feat(rag): Jina v3 embedding toggle — lazy-load on demand, low-confidence nudge, standard/enhanced toggle in header |
| 7862b03 | fix(rag): poll /rag/health every 5s while Jina loads — banner auto-updates to ready |

---

## Key Design Decisions
- **Jina is never loaded at startup** — only when a user explicitly enables it or is nudged by a low-confidence result. Avoids 570MB download on every Space boot.
- **Separate ChromaDB collections** (`rag_kb` for MiniLM, `rag_kb_jina` for Jina) — embedding spaces are incompatible; can't mix vectors from different models in the same collection.
- **`initialize_jina` always rebuilds** the Jina collection (deletes + recreates) to handle the case where corpus has changed since last build.
- **`low_confidence` threshold**: top chunk raw cross-encoder score < 10% — signals that retrieval quality is poor and Jina may help.
- **Polling stops automatically** when Jina is ready — `useEffect` cleanup runs `clearInterval`, so there's no persistent background poll.
