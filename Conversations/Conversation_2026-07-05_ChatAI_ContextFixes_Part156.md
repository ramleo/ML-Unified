# Conversation — 2026-07-05 · Chat AI Context Fixes · Part 156

## Session Summary

Continuation from Part 155 (context compacted). Fixed multiple issues with chat AI bubble not reading uploaded datasets, settings panel scroll, and semantic cache cross-contamination.

---

## Issues Fixed

### 1. Data Preprocessing — Rich Dataset Context (commit `e4166d2`)

**Problem:** Chat AI on preprocessing page only saw basic row/column counts. Could not answer dataset-specific questions like "which columns need normalization?"

**Fix:** Replaced minimal inline summary with `buildPreprocessingContext()` function that builds a detailed per-column context string including:
- mean, std, min/max, skewness for every numeric column
- missing count, unique values for categoricals
- Dedicated "high-skewness columns" line listing candidates for log/sqrt transform
- After-preprocessing summary once cleaning completes

**File:** `src/app/tools/preprocessing/page.tsx`

---

### 2. AutoML, SHAP, Optuna, Ensemble — Live Training Results in Context (commit `d4d32bf`)

**Problem:** All four tool pages had hardcoded generic summaries ("Automated ML wizard that trains...") that never updated with actual training results. Chat AI answered generically regardless of what was trained.

**Fix:**
- Added `onResult?: (r: TrainResult | null) => void` prop to `ShapRunner`, `OptunaRunner`, `EnsembleRunner`
- Called `onResult?.(data)` when training completes in each runner
- Lifted `trainResult` state to each page component
- Built context string with winner model, metrics, feature importance, CV scores
- AutoML: used existing `onResultChange` prop on `AutoMLModal`, accessed `.automl` sub-object

**Files:** `ShapRunner.tsx`, `OptunaRunner.tsx`, `EnsembleRunner.tsx`, `shap/page.tsx`, `optuna/page.tsx`, `ensemble/page.tsx`, `automl/page.tsx`

---

### 3. Settings Panel Scroll — `onWheel` React vs Native (commit `d4d32bf` → `fc79485`)

**Problem:** When cursor is on the settings panel (Provider/Model/API Key) and user scrolls, the background page scrolls instead of being contained.

**First attempt (wrong):** Added `onWheel={e => e.stopPropagation()}` to the settings div. This doesn't work because React uses event delegation — all events are handled at the document root, so the native event has already propagated by the time React's handler runs.

**Root cause discovery via Playwright:** JS synthetic wheel events (`new WheelEvent(...)` dispatched via `dispatchEvent()`) don't trigger native browser scroll — browsers only scroll from real user input. So the first Playwright test gave false confidence (`scrolled: false`). The second test (checking if document listener fires) proved the event still reached the document (`nativeHandlerFired: true`, `deployedFixWorking: false`).

**Correct fix (commit `fc79485`):** Replaced React `onWheel` with native `addEventListener` in `useEffect`:
```tsx
useEffect(() => {
  const el = ref.current;
  if (!el) return;
  const handler = (e: WheelEvent) => e.stopPropagation();
  el.addEventListener("wheel", handler, { passive: false });
  return () => el.removeEventListener("wheel", handler);
}, []);
```
Native listeners fire at the element level during bubbling — before the document receives the event — so `stopPropagation()` actually prevents the page from scrolling.

**File:** `src/components/ToolsAIChatSettings.tsx`

**Status:** Deployed to Vercel. Playwright verification pending (user stopped wait).

---

### 4. Semantic Cache Cross-Dataset Contamination (commit `1300262`)

**Problem:** Playwright confirmed that after uploading a dataset to preprocessing and asking "which columns need normalisation?", the response was **CACHED · 467ms** — a generic stale answer from a previous session with no dataset loaded. Cache key was only the query embedding, ignoring `tool_context` entirely.

**Root cause:** `_cache_lookup` matched on `(query_emb, provider)` only. Same question always returned the same cached answer regardless of which dataset was loaded.

**Fix:** Added `ctx_hash` — short MD5 of `tool_context` — to both cache lookup and store:
```python
def _ctx_hash(tool_context: str) -> str:
    import hashlib
    return hashlib.md5(tool_context.strip().encode(), usedforsecurity=False).hexdigest()[:8] if tool_context.strip() else ""

def _cache_lookup(query_emb, state, provider, ctx_hash):
    for entry in state.semantic_cache:
        if entry.get("provider") != provider: continue
        if entry.get("ctx_hash", "") != ctx_hash: continue
        ...

def _cache_store(..., ctx_hash=""):
    state.semantic_cache.append({..., "ctx_hash": ctx_hash})
```

Call sites updated in `_sse_generator`:
```python
ctx_hash = _ctx_hash(req.tool_context)
cached = _cache_lookup(query_emb, state, provider, ctx_hash)
# ...
_cache_store(query_emb, full_text, seen_sources, chunks, state, provider, ctx_hash)
```

**Playwright verification:** After fix — fresh 15.3s response mentioning actual column names (`income` 38,000–95,000, `age` 22–55, `promoted` binary) instead of generic advice.

**Files:** `services/ml-api/routers/rag/query.py`  
**HF Upload:** Done

---

## Commits

| Hash | Description |
|------|-------------|
| `e4166d2` | feat(preprocessing): rich dataset context for chat AI |
| `d4d32bf` | feat(chat-ai): wire live results to ToolsAIChat context + fix settings scroll |
| `1300262` | fix(rag): context-aware semantic cache — include tool_context hash in cache key |
| `fc79485` | fix(settings): native wheel listener to stop background scroll |

---

## Playwright Findings

- **Chat AI reads dataset:** CONFIRMED — response mentions actual column names and ranges from uploaded CSV
- **Settings scroll:** PENDING — Vercel deploy in progress when user stopped session. Native event listener approach is architecturally correct; synthetic JS wheel events cannot test browser scroll behavior.

---

## Pending

- Playwright confirm settings scroll fix (Vercel deploy `fc79485` needed)
- Feature Selection page context could also be enriched (currently has col names but no per-column stats)
