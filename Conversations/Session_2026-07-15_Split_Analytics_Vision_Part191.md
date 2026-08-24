# Session 2026-07-15 — index.html Split, Analytics Tracking, Vision Merge (Part 191)

## Summary

This session covered:
1. **index.html split** — 9992-line monolithic file split into 5 files
2. **Analytics tracking** — 21 `_track()` call sites wired across 3 HF Space HTML files
3. **Sidebar regression fix** — left panel missing from vision.html and eda.html after split
4. **CORS fix** — `/api/track` was silently failing for cross-origin HF Space requests
5. **HF Space Tools dashboard section** — new section in realtime-analytics showing EDA/Vision/ML Unified breakdown
6. **aiofiles missing dep** — caused HF Space to hang for 30+ min after split
7. **Vision service merge** — merged ml-vision into ml-unified since new HF Docker Spaces require Pro

---

## 1. index.html Split

### Target structure
```
services/ml-api/frontend/
├── index.html      ML Unified only       5008 lines
├── eda.html        EDA Explorer only     1937 lines
├── vision.html     ML Vision only        1286 lines
├── common.js       Shared JS              327 lines
└── common.css      All CSS               1693 lines
```

### Key design decisions
- CSS extracted from inline `<style>` block → `common.css`
- Shared JS (`_track`, `initServiceUrls`, `fetchWithRetry`, theme, particles) → `common.js`
- URL injection: each HTML has `<script>window.__ML_URLS__ = { vision: '__VISION_URL__', eda: '__EDA_URL__' };</script>` before `common.js`; `app.py` string-replaces the placeholders at serve time
- EDA and Vision `init()` call `selectEDA()`/`selectVision()` directly — NO `/models` fetch, loads instantly
- `app.py`: added `StaticFiles` mount at `/static` + mode-aware `GET /` route

### FastAPI app.py change
```python
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "frontend")), name="static")

@app.get("/")
def index(mode: str = "ml"):
    fname = {"eda": "eda.html", "vision": "vision.html"}.get(mode, "index.html")
    fpath = os.path.join(HERE, "frontend", fname)
    html = open(fpath).read()
    html = html.replace("'__VISION_URL__'", f"'{vision_url}'", 1)
    html = html.replace("'__EDA_URL__'",    f"'{eda_url}'",    1)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
```

### Commits
| Hash | Message |
|------|---------|
| `5190a06` | refactor(frontend): split index.html (9992 lines) into 3 focused HTML files + common.js + common.css |

---

## 2. Analytics Tracking (Step 1 — HF Space)

### Events wired

**index.html (ML Unified):**
- `tool_open` — model selected (line 604) — `model_id`, `task`
- `tool_open` — CSV uploaded (line 1879) — `action:"upload_csv"`, `rows`, `cols`
- `query_run` — predict (line 1439) — `action:"predict"`, `model_id`, `confidence`
- `query_run` — SHAP (lines 1596, 1781) — `action:"shap"`, `model_id`
- `query_run` — AutoML (line 4209) — `action:"automl"`, `winner`, `models_tried`
- `query_run` — train (line 4279) — `action:"train"`, `model_type`, `metric_value`, `features_count`
- `query_run` — cluster (line 4832) — `action:"cluster"`, `algorithm`, `n_samples`

**eda.html:**
- `tool_open` — panel open (line 110)
- `tool_open` — CSV upload (line 174) — `rows`, `cols`
- `query_run` — analyze (line 176) — `rows`, `cols`
- `query_run` — clean (line 653) — `operation`
- `query_run` — chart (line 1248) — `chart_type:"distribution"`
- `error` — API fail (lines 179, 684)

**vision.html:**
- `tool_open` — panel open (line 119)
- `tool_open` — image upload (line 248)
- `query_run` — classify (line 335) — `model`, `top_label`, `confidence`
- `query_run` — detect (line 907) — `model`, `objects_found`
- `query_run` — segment (lines 1127, 1161) — `model`
- `error` — each catch block

### Commits
| Hash | Message |
|------|---------|
| `0fd572d` | feat(analytics): add real-time tracking to ML Unified, EDA, Vision |

---

## 3. Sidebar Regression Fix

### Problem
The split subagent removed the sidebar from both `vision.html` and `eda.html`, replacing them with `<!-- Layout — no sidebar on standalone Vision page -->` and a single-column layout. The left panel with tool buttons was gone.

### Fix
Restored sidebar HTML in both files:
- **vision.html**: Image Classifier, Image Processing, Object Detection, Image Segmentation buttons
- **eda.html**: EDA Explorer, Clean & Export buttons

Active state already handled by `selectVision()`, `selectEDA()` etc. (they call `querySelectorAll('.model-btn').forEach(b => b.classList.remove('active'))`).

### Commits
| Hash | Message |
|------|---------|
| `b71d360` | fix(frontend): restore sidebar panels to vision.html and eda.html |

---

## 4. CORS Fix for `/api/track`

### Problem
`_track()` fires from HF Space (`wram1708-ml-unified.hf.space`) to Vercel (`ml-portfolio-rho.vercel.app/api/track`). Cross-origin POST with `Content-Type: application/json` requires a CORS preflight (OPTIONS). The `/api/track` route had no OPTIONS handler and no CORS headers → preflight failed → events were silently dropped.

### Fix (ml-portfolio `src/app/api/track/route.ts`)
```ts
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export async function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: CORS });
}

export async function POST(req: NextRequest) {
  // ... existing logic ...
  return NextResponse.json({ ok: true }, { headers: CORS });
}
```

### Commits (ml-portfolio)
| Hash | Message |
|------|---------|
| `c8c3931` | fix(api/track): add CORS headers so HF Space can POST cross-origin |

---

## 5. HF Space Tools Dashboard Section

### Problem
All HF Space events showed path `/` in the analytics feed — indistinguishable between EDA, Vision, ML Unified.

### Fix 1: Path in `_track()` (common.js)
```js
path: window.location.pathname + (typeof APP_MODE !== 'undefined' && APP_MODE && APP_MODE !== 'ml' ? '?mode=' + APP_MODE : '')
```
Now EDA events show `/?mode=eda`, Vision shows `/?mode=vision`.

### Fix 2: New `AnalyticsHFTools` component (ml-portfolio)

**New file**: `src/app/tools/realtime-analytics/AnalyticsHFTools.tsx`
- 3-column grid: ML Unified (indigo) / EDA Explorer (emerald) / ML Vision (fuchsia)
- Each column: total event count + mini bar chart per action (predict, train, shap, analyze, clean, etc.)
- Falls back to "No HF Space activity" when empty

**Stats route** (`src/app/api/stats/route.ts`):
```ts
const hfTools: Record<string, Record<string, number>> = {};
for (const row of hfRaw ?? []) {
  const tool = row.meta?.tool;
  const action = row.meta?.action ?? "other";
  if (!["ml-unified", "eda", "vision"].includes(tool)) continue;
  if (!hfTools[tool]) hfTools[tool] = {};
  hfTools[tool][action] = (hfTools[tool][action] ?? 0) + 1;
}
// added to response: hf_tools: hfTools
```

### Commits (ml-portfolio)
| Hash | Message |
|------|---------|
| `c90d7fa` | feat(analytics): add HF Space Tools section to dashboard |

### Commits (ML-Unified)
| Hash | Message |
|------|---------|
| `f2fedd0` | fix(analytics): include ?mode= in _track path for HF Space tools |

---

## 6. aiofiles Missing Dependency

### Problem
`StaticFiles` added in the split commit requires the `aiofiles` package. It was not in `requirements.txt`. HF Space was stuck in "Restarting" for 30+ minutes because the app crashed at startup.

### Fix
Added `aiofiles>=23.0.0` to `services/ml-api/requirements.txt`.

### Commits
| Hash | Message |
|------|---------|
| `e675c2b` | fix(deps): add aiofiles — required by FastAPI StaticFiles mount |

---

## 7. Vision Service Merge into ml-unified

### Problem
- `wram1708/ml-vision` HF Space never existed
- Creating new Docker Spaces via API requires HF Pro subscription
- Solution: merge Vision routes directly into ml-unified

### Structure created
```
services/ml-api/routers/vision/
├── __init__.py       32 lines  — combined router + init_vision_models()
├── shared.py        103 lines  — StreamingTask, VISION_CACHE_DIR, model cache
├── classify.py      170 lines  — /classify-image, /imagenet-classes, /image-models
├── processing.py    104 lines  — /process-image, /image-operations
├── detection.py     244 lines  — /detect-objects, /detect-models
└── segmentation.py  291 lines  — /segment-image, /seg-models
```

All routes at root level (no prefix) — frontend calls `/classify-image` etc. unchanged.

### app.py changes
```python
from routers.vision import router as vision_router, init_vision_models
# In _bg():
init_vision_models()  # runs after _load() in background thread
# After routers:
app.include_router(vision_router)
```

### requirements.txt additions
```
Pillow>=10.0.0
onnxruntime>=1.18.0
```

### Final step needed by user
Update `ML_VISION_URL` secret on HF Space from `https://wram1708-ml-vision.hf.space` to `https://wram1708-ml-unified.hf.space`.

### Commits
| Hash | Message |
|------|---------|
| `93f0b80` | feat(vision): merge Vision service into ml-unified HF Space |

---

## All Commits This Session

| Repo | Hash | Message |
|------|------|---------|
| ML-Unified | `5190a06` | refactor(frontend): split index.html into 3 HTML + common.js + common.css |
| ML-Unified | `0fd572d` | feat(analytics): add real-time tracking to ML Unified, EDA, Vision |
| ML-Unified | `b71d360` | fix(frontend): restore sidebar panels to vision.html and eda.html |
| ML-Unified | `f2fedd0` | fix(analytics): include ?mode= in _track path for HF Space tools |
| ML-Unified | `e675c2b` | fix(deps): add aiofiles — required by FastAPI StaticFiles mount |
| ML-Unified | `93f0b80` | feat(vision): merge Vision service into ml-unified HF Space |
| ml-portfolio | `c8c3931` | fix(api/track): add CORS headers so HF Space can POST cross-origin |
| ml-portfolio | `c90d7fa` | feat(analytics): add HF Space Tools section to dashboard |

---

## Pending / Next Steps

- [ ] User must update `ML_VISION_URL` secret to `https://wram1708-ml-unified.hf.space`
- [ ] Verify Vision classification works after HF Space restarts
- [ ] Analytics Step 2: Optuna tracking (`OptunaRunner.tsx`)
- [ ] Analytics Steps 3–5: FE+FS+Preprocessing, Drift+Ensemble, Pipeline+Cinema
