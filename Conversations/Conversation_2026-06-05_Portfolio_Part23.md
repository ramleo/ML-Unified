# Conversation — 2026-06-05 | Monitoring + Portfolio Polish (Part 23)

**Date:** 2026-06-05
**Projects:** ML-Unified · ml-portfolio

---

## Points Completed This Session

| # | Item | Status |
|---|---|---|
| 1 | Hero: remove "Hi, I'm", update stats | ✅ Done |
| 2 | Theme sync — Portfolio ↔ ML Unified (both directions) | ✅ Done |
| 3 | Vision card + Portfolio link in ML Unified navbar | ✅ Done (prev session, confirmed) |
| 4 | Sidebar section filtering by ?mode=ml / ?mode=vision | ✅ Done |
| 5 | Live request monitoring — ml-api + ml-vision + frontend panel | ✅ Done |

---

## 1. Hero Changes — ml-portfolio

**File:** `src/components/Hero.tsx`

### Heading
Removed "Hi, I'm" prefix. Heading is now just the gradient name:
```tsx
<h1 …>
  <span className="gradient-text">AIRaML</span>
</h1>
```

### Stats updated
| Before | After |
|---|---|
| `4` Live Projects | `2` Live Platforms |
| `3` Datasets | `4` Datasets (Iris, Titanic, Diabetes, Insurance) |
| `96.7%` Best Accuracy | `96.7%` Best Accuracy (unchanged) |
| `Auto-ML` Pipeline | `Auto-ML` Pipeline (unchanged) |

---

## 2. Bidirectional Theme Sync

### The problem
Portfolio (`ml-portfolio-rho.vercel.app`) and ML Unified (`ml-unified.onrender.com`) are on different domains. `localStorage` is origin-scoped — they cannot share it directly.

### Solution: URL param `?theme=light/dark`

**Portfolio → ML Unified (Launch App button)**
`ProjectCard.tsx` — `Launch App` changed from `<a>` to `<button>` with onClick:
```tsx
onClick={() => {
  const theme = document.documentElement.classList.contains("light") ? "light" : "dark";
  const sep = url.includes("?") ? "&" : "?";
  window.open(`${url}${sep}theme=${theme}`, "_blank");
}}
```

**ML Unified → Portfolio (Portfolio nav link)**
`index.html` — `onclick` sets href dynamically before navigation:
```html
<a href="https://ml-portfolio-rho.vercel.app/"
   onclick="this.href='https://ml-portfolio-rho.vercel.app/?theme='
            + document.documentElement.getAttribute('data-theme')">
  Portfolio
</a>
```

**ML Unified reads ?theme= on load**
Theme IIFE in `index.html` — checks URL param before localStorage:
```js
(function () {
  const urlTheme = new URLSearchParams(window.location.search).get('theme');
  if (urlTheme === 'light' || urlTheme === 'dark') {
    setTheme(urlTheme);
    try { localStorage.setItem('theme', urlTheme); } catch(e) {}
  } else {
    try { if (localStorage.getItem('theme') === 'light') setTheme('light'); } catch(e) {}
  }
})();
```

**Portfolio reads ?theme= on mount**
`ThemeToggle.tsx` — `useEffect` checks URL param first:
```tsx
useEffect(() => {
  const urlTheme = new URLSearchParams(window.location.search).get("theme");
  let dark: boolean;
  if (urlTheme === "light" || urlTheme === "dark") {
    dark = urlTheme === "dark";
    localStorage.setItem("theme", urlTheme);
  } else {
    const stored = localStorage.getItem("theme");
    dark = stored !== "light";
  }
  setIsDark(dark);
  document.documentElement.classList.toggle("light", !dark);
}, []);
```

### Flow (both directions)
```
Portfolio light → Launch App → ml-unified.onrender.com/?mode=vision&theme=light
→ ML Unified reads ?theme=light → applies light → saves to localStorage ✓

ML Unified light → click Portfolio → ml-portfolio-rho.vercel.app/?theme=light
→ ThemeToggle reads ?theme=light → applies light → saves to localStorage ✓
```

---

## 3. Sidebar Section Filtering — `?mode=` URL Param

Added `APP_MODE` constant read once on load:
```js
const APP_MODE = new URLSearchParams(window.location.search).get('mode') || 'all';
```

`renderSidebar()` uses two flags:
```js
const showML     = APP_MODE !== 'vision';
const showVision = APP_MODE !== 'ml';
```

| URL | Sidebar | Nav title | Train button |
|---|---|---|---|
| `?mode=ml` | Supervised + Unsupervised only | ML Unified | Visible |
| `?mode=vision` | Vision only | ML Vision | Hidden |
| (none) | All sections | ML Unified | Visible |

Nav title is updated immediately on load via `applyNavMode()` IIFE.

**registry.json URLs:**
- ML Unified Platform → `https://ml-unified.onrender.com/?mode=ml`
- ML Vision Platform → `https://ml-unified.onrender.com/?mode=vision`

---

## 4. Live Request Monitoring

### Architecture (microservices-correct)
Each service owns its own metrics — no shared state, no external service, no database.

```
ml-api    → GET /metrics  (own circular buffer, own uptime)
ml-vision → GET /metrics  (own circular buffer, own uptime)

Frontend fetches both in parallel → renders side-by-side in panel
```

### Backend — both services

**Middleware** (identical pattern in both `app.py` files):
```python
_SKIP_PATHS = {"/health", "/metrics"}   # ml-api also skips "/", "/app-config"
_req_log: collections.deque = collections.deque(maxlen=1000)
_svc_start = time.time()

@app.middleware("http")
async def _monitor(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    if request.url.path not in _SKIP_PATHS:
        _req_log.append({
            "ts": time.time(), "path": request.url.path,
            "method": request.method, "status": response.status_code, "ms": ms,
        })
    return response
```

**`GET /metrics` response shape:**
```json
{
  "service":        "ml-vision",
  "uptime_s":       3742,
  "total_requests": 47,
  "avg_ms":         312.4,
  "p95_ms":         891.0,
  "error_rate":     2.1,
  "endpoints": [
    { "path": "/segment-image", "count": 12, "avg_ms": 4120.1,
      "p95_ms": 5800.0, "error_rate": 0.0 },
    …
  ]
}
```

Notes:
- Circular buffer — maxlen=1000, resets on redeploy (acceptable for portfolio)
- p95 uses index `min(int(len * 0.95), len-1)` to avoid IndexError on small samples
- `/health` and `/metrics` calls are excluded from logging (avoid self-noise)

### Frontend — Live Metrics panel

**"Live Metrics" button** — bottom of sidebar in every mode:
```js
const metricsBtn = `
  <div style="flex:1"></div>
  <button class="sidebar-upload-btn" onclick="openMetricsPanel()" …>
    📈 Live Metrics
  </button>`;
```

**Panel behaviour:**
- Slides in from bottom-right corner (fixed, z-index 1000)
- Fetches `API/metrics` and `VISION_API/metrics` in parallel
- Auto-refreshes every 30 s (`setInterval`)
- Dismissible with ✕ button → `closeMetricsPanel()` clears interval

**Latency bar colour coding:**
- Green: < 200 ms
- Amber: 200–800 ms
- Red: ≥ 800 ms

**Per-endpoint table columns:** path · request count · avg ms · p95 latency bar

### Tests added

**`services/ml-vision/tests/test_vision.py`:**
- `test_metrics_empty` — fresh service returns valid schema
- `test_metrics_records_requests` — after GET /image-models, appears in /metrics

**`services/ml-api/tests/test_api.py`:**
- `test_metrics_empty` — valid schema, service = "ml-api"
- `test_metrics_records_requests` — after GET /models, appears in /metrics

---

## Commits This Session

### ML-Unified repo

| Hash | Description |
|---|---|
| `6cce9f2` | Apply theme from ?theme= URL param on load |
| `18aaa5d` | Append current theme to Portfolio nav link on click |
| `05c30f7` | Filter sidebar sections by ?mode=ml or ?mode=vision URL param |
| `56b0cfc` | Add Portfolio link to navbar |
| `2a0b944` | Add live request monitoring to ml-api and ml-vision |

### ml-portfolio repo

| Hash | Description |
|---|---|
| `33ce8d7` | Remove 'Hi I'm' from hero, update stats, sync theme to launched apps |
| `be4de81` | Read ?theme= URL param on load for bidirectional theme sync |

---

## Pending — Next Sessions

### Phase 2: Theme palette picker + high contrast + vision ambient themes
- 5 themes: Dark (default) · Light · Ocean · Forest · High Contrast
- Theme picker in navbar (both portfolio and ML Unified)
- Vision task ambient themes: each panel (Classifier/Processing/Detection/Segmentation)
  gets its own background tint + accent colour matching its sidebar dot colour
- Sync palette across domains via URL param (extend existing `?theme=` to `?theme=ocean` etc.)

### Phase 3: ML Unified + Vision improvements
- UI: prediction confidence as bar chart, side-by-side original vs result for vision
- Features: batch predict (CSV upload), image processing enhancements,
  SHAP feature importance, training history/comparison
- Mobile: sidebar collapses to bottom tab bar

### Phase 4: Data drift detection
- Flag when prediction inputs drift from training distribution
- Per-feature distribution tracking, KS-test or PSI metric

### Phase 5: MLflow experiment tracking
- Log training runs (metrics, params, artifacts)
- Compare runs, select best model

### Phase 6: E2E tests
- Playwright: upload → predict → assert result shape

---

## Architecture — Current State

```
GitHub → CI (ruff + pytest) → Render deploy hooks

ml-api  (services/ml-api/)  → https://ml-unified.onrender.com
  ├── Supervised ML (train, predict, analyze)
  ├── Unsupervised (K-Means, DBSCAN, t-SNE, PCA)
  ├── GET /metrics → own request log (uptime, latency, error rate)
  ├── Serves frontend with ?mode=ml / ?mode=vision / (all) filtering
  ├── Injects ML_VISION_URL as VISION_API server-side
  └── Portfolio link → passes ?theme= for bidirectional sync

ml-vision  (services/ml-vision/)  → separate Render service
  ├── Image Classifier (MobileNetV2 / ResNet50 / SqueezeNet / GoogLeNet)
  ├── Image Processing (PIL operations)
  ├── Object Detection (TinyYOLOv3, COCO 80 classes)
  ├── Image Segmentation (SegFormer-B0, ADE20K 150 classes)
  ├── GET /metrics → own request log
  └── Auto-deploy via RENDER_VISION_DEPLOY_HOOK_URL (GitHub secret ✅)

ml-portfolio  → https://ml-portfolio-rho.vercel.app (Vercel)
  ├── ML Unified Platform card → ?mode=ml&theme=<current>
  ├── ML Vision Platform card  → ?mode=vision&theme=<current>
  └── Launch App passes active theme via URL param
```

---

## Standing Rules

- Apply changes to ALL affected repos simultaneously
- Conversation logs stored in `ML-Iris/Conversations/`
- Light theme: ALL elements must adapt
- Vercel = portfolio only; Render = ML apps
- ML-Unified → Render auto-deploy on push to main, gated by CI
- ml-vision → auto-deploy via RENDER_VISION_DEPLOY_HOOK_URL
- `vision_cache/` and `.mcp.json` must never be committed
- Always run `ruff check` + `pytest` before pushing
- Use mock-based tests for inference paths requiring model downloads
- Share `_large_vision_cache` slot — never load two large ONNX models simultaneously
- User-facing errors: plain English only — no shapes or tracebacks
- `secrets` context NOT allowed in GitHub Actions step-level `if:`
- Keep ml-api and ml-vision requirements.txt fully independent
- All vision endpoint URLs sourced from `VISION_API`, never `API`
- New vision features → ml-vision only
- When ml-vision gets its own URL: update registry.json Vision card url only
- Consider microservices architecture in all new features
- Vision task ambient themes planned for Phase 2 (each task = own bg tint + accent)
