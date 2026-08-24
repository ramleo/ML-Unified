# Session 2026-07-15 — Vision Fixes, Analytics Polish (Part 192)

## Summary

Continuation from Part 191. This session covered:
1. **PermissionError fix** — `/app/vision_cache` → `/tmp/vision_cache`
2. **Download timeout fix** — `urlretrieve` (no timeout) → `httpx.stream` (120s timeout, atomic replace)
3. **ONNX session speed fix** — `ORT_ENABLE_ALL` → `ORT_ENABLE_BASIC` (avoids multi-minute graph optimization)
4. **Missing SSE helpers** — `_sseStream`, `_progressBarHTML`, `_updateProgressBar` missing from `common.js`
5. **Lint fix** — unused `FRONTEND` import in `app.py`
6. **HF Space Tools UI redesign** — colors corrected, style matched to dashboard
7. **Analytics Step 2** — Optuna tracking wired (4 events)
8. **Path fix** — `/?mode=vision` → `/vision` in `_track()` calls

---

## 1. PermissionError Fix

### Problem
HF Docker Space runs as `appuser` (non-root). `VISION_CACHE_DIR` was set to `/app/vision_cache` — `/app` is owned by root, so `os.makedirs` failed at import time, crashing the app before uvicorn started.

### Fix
```python
# services/ml-api/routers/vision/shared.py
VISION_CACHE_DIR = "/tmp/vision_cache"   # was: os.path.join(_API_ROOT, "vision_cache")
```

### Commit
| Repo | Hash | Message |
|------|------|---------|
| ML-Unified | `e7afe39` | fix(vision): use /tmp/vision_cache — /app is read-only in HF Docker Space |

---

## 2. Download Timeout + ONNX Speed Fix

### Problem
Two separate issues caused "Detecting..." to hang for 8–11 minutes:
1. `urllib.request.urlretrieve` has no timeout — GitHub LFS download stalls silently
2. `ort.InferenceSession()` defaults to `ORT_ENABLE_ALL` — full graph optimization takes minutes on free-tier CPU

### Fix
Added two shared helpers in `shared.py`:
```python
def download_model(url: str, dest: str, timeout: int = 120) -> None:
    """Download with httpx, 120s timeout, atomic replace on success."""
    import httpx
    tmp = dest + ".tmp"
    try:
        with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=65536):
                    f.write(chunk)
        os.replace(tmp, dest)
    except Exception:
        if os.path.exists(tmp): os.remove(tmp)
        raise

def ort_session(path: str):
    """Load ONNX session with ORT_ENABLE_BASIC — fast, skips heavy optimization."""
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
    return ort.InferenceSession(path, sess_options=opts)
```

All three vision files (`classify.py`, `detection.py`, `segmentation.py`) updated to use these helpers instead of `urllib.request.urlretrieve` and bare `ort.InferenceSession()`.

### Commits
| Repo | Hash | Message |
|------|------|---------|
| ML-Unified | `1f6e8da` | fix(vision): use httpx+timeout for model downloads, ORT_ENABLE_BASIC for fast session load |

---

## 3. Missing SSE Helpers in common.js

### Problem
The split subagent put `_sseStream`, `_progressBarHTML`, `_updateProgressBar` only in `index.html`. `vision.html` uses all three for the detection/segmentation progress UI — they were silently undefined, so no progress bar appeared and the "Detecting..." spinner was the only feedback.

### Fix
Appended all three functions to `common.js`:
```js
async function* _sseStream(response) { ... }
function _progressBarHTML(fillId, msgId, pctId) { ... }
function _updateProgressBar(fillId, msgId, pctId, pct, msg) { ... }
```

### Commits
| Repo | Hash | Message |
|------|------|---------|
| ML-Unified | `38d2599` | fix(frontend): add _sseStream, _progressBarHTML, _updateProgressBar to common.js |

---

## 4. Lint Fix

### Problem
CI (ruff) failed: `FRONTEND` was imported in `app.py` but never used.

### Fix
```python
# Removed FRONTEND from import
from routers.core.shared import (
    _detect_gpu, MODELS, _fetch_hf_models, _load,
    HERE,   # FRONTEND removed
)
```

### Commits
| Repo | Hash | Message |
|------|------|---------|
| ML-Unified | `0c5827e` | fix(lint): remove unused FRONTEND import from app.py |

---

## 5. HF Space Tools UI Redesign

### Problem (two issues)
1. Colors wrong — `ml-unified` was `#818cf8`, `vision` was `#e879f9` (swapped + wrong)
2. Card style didn't match the rest of the dashboard

### Fix
Correct colors from `registry.json`:
- ML Unified: `#e879f9` (fuchsia)
- EDA Explorer: `#34d399` (emerald) — was already correct
- ML Vision: `#a78bfa` (violet)

Card wrapper now matches all other dashboard cards:
```tsx
<div className="rounded-xl border border-white/8 bg-white/[0.03] p-4">
  <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-widest mb-3">
    HF Space Tools
  </p>
  <div className="grid grid-cols-1 lg:grid-cols-3 gap-x-6 gap-y-4 divide-y lg:divide-y-0 lg:divide-x divide-white/[0.05]">
    ...
  </div>
</div>
```

Removed sub-card borders; 3 columns separated by subtle dividers (consistent with other cards).

### Commits
| Repo | Hash | Message |
|------|------|---------|
| ml-portfolio | `f11a940` | feat(analytics): redesign HF Space Tools cards |
| ml-portfolio | `ec2a0bc` | fix(analytics): HF Tools — correct colors from registry, match dashboard card style |

---

## 6. Analytics Step 2 — Optuna Tracking

### What was tracked
Optuna is a portfolio-side tool (Next.js, `/tools/optuna`), NOT on HF Space. Events appear in the live feed and query success rate, not in HF Space Tools.

### Implementation
Exported `track()` from `useAnalytics.ts` (was module-private), then added 4 calls in `OptunaRunner.tsx`:

| Event | Trigger | Key meta fields |
|-------|---------|-----------------|
| `tool_open` | CSV analyzed successfully | `tool:optuna, action:upload_csv, rows, cols` |
| `query_run` | Run button clicked | `tool:optuna, action:optuna_start, model, n_trials, task, sampler` |
| `query_run` | Result SSE event received | `tool:optuna, action:optuna, winner, metric_value, success:true` |
| `error` | fetch catch block | `tool:optuna, action:optuna_error, model` |

### Commits
| Repo | Hash | Message |
|------|------|---------|
| ml-portfolio | `e865b76` | feat(analytics): add Optuna tracking — upload, run start, run complete, error |

---

## 7. Path Fix — `/?mode=vision` → `/vision`

### Problem
`_track()` in `common.js` built paths as `window.location.pathname + '?mode=vision'` = `/?mode=vision`. In Top Pages, these showed as `/?mode=eda`, `/?mode=vision` — not readable.

### Fix
```js
// common.js — _track() path field
path: (APP_MODE === 'eda' ? '/eda' : APP_MODE === 'vision' ? '/vision' : '/')
```

Now Top Pages shows `/`, `/eda`, `/vision` cleanly.

### Commits
| Repo | Hash | Message |
|------|------|---------|
| ML-Unified | `833a939` | fix(analytics): track clean paths /eda /vision / instead of /?mode= query strings |

---

## All Commits This Session

| Repo | Hash | Message |
|------|------|---------|
| ML-Unified | `e7afe39` | fix(vision): use /tmp/vision_cache — /app is read-only in HF Docker Space |
| ML-Unified | `1f6e8da` | fix(vision): use httpx+timeout for model downloads, ORT_ENABLE_BASIC for fast session load |
| ML-Unified | `38d2599` | fix(frontend): add _sseStream, _progressBarHTML, _updateProgressBar to common.js |
| ML-Unified | `0c5827e` | fix(lint): remove unused FRONTEND import from app.py |
| ML-Unified | `833a939` | fix(analytics): track clean paths /eda /vision / instead of /?mode= query strings |
| ml-portfolio | `c8c3931` | fix(api/track): add CORS headers so HF Space can POST cross-origin *(from Part 191)* |
| ml-portfolio | `f11a940` | feat(analytics): redesign HF Space Tools cards — left border accent, pct labels |
| ml-portfolio | `ec2a0bc` | fix(analytics): HF Tools — correct colors from registry, match dashboard card style |
| ml-portfolio | `e865b76` | feat(analytics): add Optuna tracking — upload, run start, run complete, error |

---

## Pending / Next Steps

- [ ] Analytics Step 3: Feature Engineering + Feature Selection + Preprocessing tracking
- [ ] Analytics Step 4: Drift + Ensemble tracking
- [ ] Analytics Step 5: Pipeline Builder + Pipeline Cinema tracking
- [ ] Vision smoke test: classify, image processing, segmentation (detection confirmed working)
- [ ] Vision: ML_VISION_URL secret on HF Space should be `https://wram1708-ml-unified.hf.space` (confirm updated)
