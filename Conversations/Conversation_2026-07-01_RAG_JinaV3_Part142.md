# Conversation Part 142 — Jina v3 Fix Completion + RAG Phase 2 Planning
**Date:** 2026-07-01  
**Branch:** main  
**Topics:** Jina v3 final fix (transformers pin), persistent cache, retrieval evaluation, Phase 2 scope

---

## Bug Fix: Jina v3 Still Failing After Property Shim

### Error
```
"jina_error": "'list' object has no attribute 'keys'"
```
Our `nn.Module.all_tied_weights_keys = []` (plain list) caused a `.keys()` call somewhere in transformers/Jina code. Each shim attempt cascaded into a new error.

### Root Cause
Jina v3's custom `XLMRobertaModel` code is fundamentally incompatible with `transformers>=4.49`. Shimming `nn.Module` was the wrong approach — every fix exposed a new incompatibility in a different code path.

### Fix
Pinned `transformers<4.49.0` in `requirements.txt` and removed all shims:
```
sentence-transformers>=3.0.0
transformers>=4.41.0,<4.49.0
```
Removed the `nn.Module.all_tied_weights_keys` shim from `routers/rag/__init__.py` entirely.

**Commit:** `c8144b1`

---

## Fix: Jina Model Re-downloads on Every Space Restart (30 min load)

### Problem
`HF_HOME=/home/appuser/.cache/huggingface` (set in Dockerfile) is ephemeral — every Space restart re-downloads the 570 MB Jina model.

### Fix
Set `HF_HOME` to `/data/hf_cache` (persistent volume) at runtime inside `initialize_jina()`, after the volume is mounted. Falls back silently if `/data` isn't writable:

```python
_persistent_cache = "/data/hf_cache"
try:
    os.makedirs(_persistent_cache, exist_ok=True)
    os.environ["HF_HOME"] = _persistent_cache
    logger.info("Jina cache dir: %s", _persistent_cache)
except Exception:
    logger.info("Jina cache dir: falling back to default (~/.cache)")
```

**Commit:** `8841fde`

---

## Jina v3 vs MiniLM — Evaluation Discussion

### Finding
For a 13-doc, 98-chunk KB, Jina v3 gives no meaningful advantage over MiniLM:
- Keyword-heavy queries (XGBoost, log1p, etc.): both models retrieve same chunks at same confidence
- Preprocessing queries: `feature_engineering.md` dominates for both (correct behavior — it IS the right doc)
- Cross-topic queries ("why XGBoost beats RF?"): Jina retrieved 8 sources vs MiniLM's 7 — marginal difference

### Conclusion
Jina v3 is overkill for this KB size. Real benefit shows at scale (large user-uploaded corpora, varied language, no shared vocabulary with source docs). MiniLM is sufficient for current 13-doc KB.

### How to Evaluate Properly
1. Manual A/B: semantically ambiguous queries where keywords don't appear in docs
2. RAGAS evaluation endpoint (Phase 2 pending): reports faithfulness, answer relevancy, context precision on 50 held-out QA pairs

---

## Architecture Notes

- **ChromaDB → Qdrant migration**: deprioritized but architected for easy swap — ChromaDB client is isolated to `__init__.py` only. One-file change when needed.
- **Web search fallback**: not implemented — Phase 3 (CRAG with DuckDuckGo via httpx)

---

## Phase Status

### Phase 1 — Complete
### Phase 2 — Pending Items
| Item | Status |
|------|--------|
| Jina v3 upgrade | Done |
| Cross-encoder reranker | Done |
| Query expansion | Done |
| `POST /rag/ingest` (user file upload) | **Pending** |
| RAGAS evaluation endpoint | **Pending** |
| Semantic caching | **Pending** |
| Response metadata (latency_ms, cache_hit) | **Pending** |

---

## Commits
- `c6e369e` — fix(rag): use plain list not property for all_tied_weights_keys shim
- `c8144b1` — fix(rag): pin transformers<4.49 for Jina v3 compat; remove shim
- `8841fde` — fix(rag): cache Jina model to /data persistent volume at runtime
