# Conversation — 2026-06-11 — ML-Unified — Part 57

---

## Session Summary

Continued from Part 56. Investigated and fixed Render port-scan timeout on ml-api service (commit `bcbf131`). Also applied SHAP Feature Impact visual style (transparent card, `.shap-header`) to Clean & Export panel (commit `5d77bf1`).

---

## Issue: Render Port-Scan Timeout on ml-api

### Symptom
```
==> Running 'uvicorn app:app --host 0.0.0.0 --port $PORT'
==> No open ports detected, continuing to scan...
==> Port scan timeout reached, no open ports detected.
```

Build succeeded but service failed to start. No port was detected open.

### Root Cause

Chain of events:
1. `catboost==1.2.10` now pulls in `nvidia-nccl-cu12==2.30.7` (303 MB CUDA library) as a new transitive dependency
2. At startup, `_lifespan` called `_load()` synchronously
3. `_load()` calls `joblib.load()` on pkl files — deserialising a catboost model implicitly runs `import catboost`
4. Catboost import initialises `nvidia-nccl-cu12` on a CPU-only Render instance — this blocks or takes very long
5. All of this happened on the **asyncio event loop thread**, freezing uvicorn completely
6. Render's port-scan sends an HTTP request; uvicorn couldn't respond while the event loop was frozen
7. Render declared the port "not open" and timed out

### Fix — commit `bcbf131`

Move `_load()` into a background **daemon thread**. `yield` executes immediately so uvicorn binds and answers Render's port-scan within milliseconds. Models finish loading ~30–60s later in the background.

**Before:**
```python
@asynccontextmanager
async def _lifespan(app: FastAPI):
    try:
        _load()
    except Exception as exc:
        ...
    yield
```

**After:**
```python
@asynccontextmanager
async def _lifespan(app: FastAPI):
    import threading
    def _bg():
        try:
            _load()
            print(f"Models loaded: {list(MODELS.keys())}", flush=True)
        except Exception as exc:
            import traceback
            print("ERROR: _load() failed:", exc, flush=True)
            traceback.print_exc()
    threading.Thread(target=_bg, daemon=True).start()
    yield  # server binds immediately; models load in background
```

Existing `if model_id not in MODELS: raise HTTPException(404)` guards handle any request arriving before loading completes.

---

## Issue: Clean & Export Card Doesn't Blend with Background

### Symptom
Feature Impact section uses `background: transparent` and blends into ambient gradient. Clean & Export used `.eda-section-card` which has `background: var(--bg-card)` — solid opaque card that doesn't blend.

### Fix — commit `5d77bf1`

- Added `background:transparent; box-shadow:none` inline override on the card div
- Replaced `.eda-section-title` with `.shap-header` / `.shap-title` / `.shap-subtitle` for identical header structure
- `sectionTitle` helper updated to use smaller, dimmer text matching Feature Impact sub-labels

---

## Commit Log (this session)

| Hash | Description |
|------|-------------|
| `5d77bf1` | feat(clean): transparent background + shap-header to match Feature Impact blend |
| `bcbf131` | fix(startup): load models in background thread to unblock uvicorn port bind |

---

## Key Decisions

- **nvidia-nccl-cu12**: Not pinned or excluded — it's a transitive dep of catboost 1.2.10. Removing it would require pinning catboost to an older version, which risks sklearn 1.8.0 incompatibility. Background thread is the safer fix.
- **Background thread vs run_in_executor**: Thread chosen because `run_in_executor` still blocks the lifespan from yielding. Thread + immediate yield is the only way to let uvicorn serve requests before `_load()` completes.
- **Race condition**: Acceptable. Models load in ~30s. Cold-start warning already shown to users after 5s of loading (from earlier commit `186f172`).

---

## Pending Items

| # | Item | Status |
|---|------|--------|
| #20 | Playwright E2E tests | Not started |
| #22 | Dockerize full app | Not started |
| #21 | Batch predict (Object Detection + Segmentation) | Deferred |
| #5  | Proxy page | Deferred |
