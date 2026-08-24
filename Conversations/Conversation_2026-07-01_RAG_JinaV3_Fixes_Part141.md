# Conversation Part 141 — RAG Jina v3 Fixes
**Date:** 2026-07-01  
**Branch:** main  
**Topics:** Jina v3 loading failures, `/data` permission error, health endpoint 500, false error state in frontend

---

## Session Summary

Continued from Part 140. Diagnosed and fixed a chain of three bugs blocking Jina v3 embedding from loading on HF Space.

---

## Bug Chain

### Bug 1 — `/rag/health` returning 500 Internal Server Error

**Root cause:** `initialize_rag` failed with `PermissionError: [Errno 13] Permission denied: '/data'`.

The Dockerfile set `ENV HF_HOME=/data/hf_cache`. HF Hub tried to create `/data/hf_cache/hub/...` on startup but `/data` (the HF Space persistent volume) either didn't exist or wasn't writable by `appuser`.

Meanwhile our new top-level exception handler in `initialize_rag` set `initialized=True` (to unblock health checks), but `state.collection` remained `None`. The health endpoint then crashed:
```
AttributeError: 'NoneType' object has no attribute 'count'
  File "routers/rag/query.py", line 173: state.collection.count()
```

**Fixes:**
1. `Dockerfile`: Changed `ENV HF_HOME=/data/hf_cache` → `ENV HF_HOME=/home/appuser/.cache/huggingface`  
   `/home/appuser` is created and owned by `adduser` — always writable, no persistent volume dependency.

2. `routers/rag/query.py`: Guarded `state.collection.count()`:
   ```python
   "status": "ok" if not state.init_error else "error",
   "chunks_indexed": state.collection.count() if state.collection is not None else 0,
   ```

**Commit:** `8cbb8dc`

---

### Bug 2 — False "Jina v3 failed" error banner in frontend

**Root cause:** After Space restart, `initialized=true, jina_loading=false, jina_ready=false, jina_error=null` (Jina hasn't been triggered yet — it's lazy-loaded). The polling condition:
```tsx
} else if (data.initialized && !data.jina_loading) {
  setJinaStatus("error");
}
```
…fired immediately, treating "not started" as "failed".

**Fixes in `ToolsAIChat.tsx`:**
1. Changed polling condition to check `data.jina_error` explicitly:
   ```tsx
   } else if (data.initialized && data.jina_error) {
     setJinaStatus("error");
   }
   ```
2. Added one-time health check when chat opens to clear stale `"error"` state from previous session:
   ```tsx
   useEffect(() => {
     if (!open || jinaStatus !== "error") return;
     fetch(`${ML_UNIFIED_API}/rag/health`)
       .then(r => r.json())
       .then(data => { if (!data.jina_error) setJinaStatus("idle"); })
       .catch(() => {});
   }, [open]);
   ```

**Commit:** `47a3fd5` (ml-portfolio)

---

### Bug 3 — Jina loading fails with `'XLMRobertaLoRA' object has no attribute 'all_tied_weights_keys'`

**Root cause:** `transformers>=4.49.0` added `all_tied_weights_keys` as a property expected on all `PreTrainedModel` subclasses. Jina v3's custom `XLMRobertaLoRA` class (loaded via `trust_remote_code=True`) was written before this property was added and doesn't define it. Caused `AttributeError` during `SentenceTransformer` model load.

**Fix in `routers/rag/__init__.py`** — compatibility shim before loading Jina:
```python
try:
    import torch.nn as nn
    if not hasattr(nn.Module, "all_tied_weights_keys"):
        nn.Module.all_tied_weights_keys = property(lambda self: [])
except Exception:
    pass
```
Patches the property onto `nn.Module` so any subclass (including `XLMRobertaLoRA`) inherits it. No version pinning required.

**Commit:** `9a09bf3`

---

## State After Fixes

- `chunks_indexed: 98` — RAG initialized and indexed knowledge base ✓
- `initialized: true` ✓
- `init_error: null` ✓
- `jina_ready: false` — Jina lazy, triggers on toggle
- Jina loading will work once toggle is clicked (570 MB download)

---

## Files Changed

### ML-Unified (backend)
| File | Change |
|------|--------|
| `services/ml-api/Dockerfile` | `HF_HOME` → `/home/appuser/.cache/huggingface` |
| `services/ml-api/routers/rag/query.py` | Guard `state.collection.count()` on None; `status="error"` when init_error set |
| `services/ml-api/routers/rag/__init__.py` | `nn.Module.all_tied_weights_keys` shim before Jina load |

### ml-portfolio (frontend)
| File | Change |
|------|--------|
| `src/components/ToolsAIChat.tsx` | Polling uses `data.jina_error` check; stale error cleared on chat open |

---

## Commits
- `8cbb8dc` — fix(rag): use writable HF cache dir; guard collection.count() on None
- `9a09bf3` — fix(rag): patch all_tied_weights_keys for Jina v3 / transformers>=4.49
- `47a3fd5` — fix(rag): don't false-flag Jina error; clear stale error on chat open (ml-portfolio)
