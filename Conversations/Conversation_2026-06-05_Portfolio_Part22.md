# Conversation — 2026-06-05 | SegFormer-B0 + Portfolio Vision Card (Part 22)

**Date:** 2026-06-05
**Project:** ML-Unified + ml-portfolio

---

## Points Completed This Session

| # | Item | Status |
|---|---|---|
| 1 | Implement SegFormer-B0 semantic segmentation (ADE20K 150 classes) | ✅ Done |
| 2 | Add PIL colour segmentation as explicit fallback (`color_segmentation`) | ✅ Done |
| 3 | Add ADE20K 150-class browser to segmentation panel | ✅ Done |
| 4 | Fix segmentation warmup retry: 20 s → 30 s, fix "~135 MB" hint | ✅ Done |
| 5 | Add RENDER_VISION_DEPLOY_HOOK_URL as GitHub secret | ✅ Done (by user) |
| 6 | Add ML Vision Platform card to ml-portfolio | ✅ Done |
| 7 | Add Portfolio link to ML-Unified navbar | ✅ Done |
| 8 | Filter sidebar by `?mode=ml` / `?mode=vision` URL params | ✅ Done |

---

## 1. SegFormer-B0 Implementation

### Why
FCN-ResNet50 (135 MB ONNX) was replaced with PIL colour segmentation as an emergency fix. PIL gives heuristic labels (sky/water, vegetation) but no true semantic labels. SegFormer-B0 gives 150 ADE20K pixel-level semantic classes and loads in ~1 s at only 4.4 MB quantized.

### Model Specs
| Property | Value |
|---|---|
| Source | Xenova/segformer-b0-finetuned-ade-512-512 (Hugging Face) |
| URL | `https://huggingface.co/Xenova/segformer-b0-finetuned-ade-512-512/resolve/main/onnx/model_quantized.onnx` |
| Size | 4.4 MB quantized ONNX |
| Input | `pixel_values` shape `(1, 3, 512, 512)`, ImageNet normalisation |
| Output | `logits` shape `(1, 150, 128, 128)` → argmax → upscale ×4 → RGBA overlay |
| Classes | 150 ADE20K (wall, building, sky, floor, tree, person, car, …) |
| Load time | ~1 s on Render free tier |
| Inference | ~2–5 s on Render free tier CPU |

### Key Code — `services/ml-vision/app.py`

**Download + load:**
```python
_SEGFORMER_URL  = "https://huggingface.co/Xenova/segformer-b0-finetuned-ade-512-512/resolve/main/onnx/model_quantized.onnx"
_SEGFORMER_PATH = os.path.join(VISION_CACHE_DIR, "segformer_b0_quantized.onnx")

def _ensure_segformer_model() -> str:
    if not os.path.exists(_SEGFORMER_PATH):
        import urllib.request
        urllib.request.urlretrieve(_SEGFORMER_URL, _SEGFORMER_PATH)
    return _SEGFORMER_PATH

def _load_segformer_session():
    import gc
    import onnxruntime as ort
    path = _ensure_segformer_model()
    with _large_vision_lock:
        _large_vision_cache.clear()
        gc.collect()
        session = ort.InferenceSession(path)
        _large_vision_cache["model_type"] = "seg"
        _large_vision_cache["model_id"]   = "segformer_b0"
        _large_vision_cache["session"]    = session
    return session
```

**Preprocessing + inference:**
```python
arr = np.array(img.resize((512, 512), PILImage.LANCZOS), dtype=np.float32) / 255.0
arr = (arr - np.array([0.485, 0.456, 0.406])) / np.array([0.229, 0.224, 0.225])
arr = arr.transpose(2, 0, 1)[np.newaxis].astype(np.float32)
logits = session.run(["logits"], {"pixel_values": arr})[0]  # (1, 150, 128, 128)
```

**Postprocessing:**
```python
label_map  = np.argmax(logits[0], axis=0).astype(np.uint8)   # (128, 128)
label_full = np.array(
    PILImage.fromarray(label_map, mode="L").resize((orig_w, orig_h), PILImage.NEAREST)
)
# Build RGBA colour mask, alpha_composite over original image
```

**Palette:** 150 colours using golden-ratio HSV spacing (h = i × 0.618… % 1.0)

**Warmup:** SegFormer-B0 is pre-downloaded on startup alongside TinyYOLOv3:
```python
def _warmup_models() -> None:
    for fn in (lambda: _ensure_det_model("tiny_yolov3"), _ensure_segformer_model):
        try:
            fn()
        except Exception as exc:
            print(f"[warmup] download failed: {exc}", flush=True)
    _warmup_done.set()
```

**503 guard:** if the file is not yet on disk (warmup still running), returns 503 instead of crashing.

### PIL Colour Segmentation — Kept as Explicit Fallback
Extracted into `_pil_segment()` helper. Accessible as `model_name=color_segmentation`. The earlier "Unknown model: color_segmentation" error was because the OLD code (FCN-only) was still running — the fix was deploying the new code.

### ADE20K 150 Classes (in order by class ID)
wall, building, sky, floor, tree, ceiling, road, bed, window, grass, cabinet, sidewalk, person, earth, door, table, mountain, plant, curtain, chair, car, water, painting, sofa, shelf, house, sea, mirror, rug, field, armchair, seat, fence, desk, rock, wardrobe, lamp, bathtub, railing, cushion, base, box, column, signboard, chest of drawers, counter, sand, sink, skyscraper, fireplace, refrigerator, grandstand, path, stairs, runway, case, pool table, pillow, screen door, stairway, river, bridge, bookcase, blind, coffee table, toilet, flower, book, hill, bench, countertop, stove, palm, kitchen island, computer, swivel chair, boat, bar, arcade machine, hovel, bus, towel, light, truck, tower, chandelier, awning, streetlight, booth, television, airplane, dirt track, apparel, pole, land, bannister, escalator, ottoman, bottle, buffet, poster, stage, van, ship, fountain, conveyer belt, canopy, washer, plaything, swimming pool, stool, barrel, basket, waterfall, tent, bag, minibike, cradle, oven, ball, food, step, tank, trade name, microwave, pot, animal, bicycle, lake, dishwasher, screen, blanket, sculpture, hood, sconce, vase, traffic light, tray, ashcan, fan, pier, crt screen, plate, monitor, bulletin board, shower, radiator, glass, clock, flag

### Tests Updated — `services/ml-vision/tests/test_vision.py`
- `test_list_seg_models` — now asserts both `segformer_b0` and `color_segmentation`
- `test_segment_image_color` — PIL path, no mock needed
- `test_segment_image_uniform` — uniform image, PIL path
- `test_segment_image_bad_model` — unknown model → 400
- `test_segment_image_segformer_inference` — mocks ONNX session + `os.path.exists`; verifies `sky` class detected and correct JSON shape

---

## 2. Segmentation Warmup Retry Fix

### Changes to `services/ml-api/frontend/index.html`

**Countdown:** 20 s → **30 s** (matches SegFormer-B0 cold-start time on Render)

**Download hint:** "~135 MB" → **"~4.4 MB"** (SegFormer-B0 quantized, not FCN)

**Retry banner message** (exact text shown to user):
```
⏳ Vision service is warming up — please try again in ~30 seconds.
Auto-retrying in 30s… (attempt 1/3)     [Stop]
```

**Flow:** 503 → banner + 30 s countdown → auto-retry → model on disk → loads 3–5 s → success. Up to 3 attempts, then "Model unavailable" error.

---

## 3. ADE20K 150-Class Browser (Segmentation Panel)

Matches the COCO class browser in object detection. Added to `renderSegmentationPanel()` inside the template string, and two JS functions added after `showSegRetry`.

```html
<button id="segClassBtn" onclick="toggleSegClassBrowser()">
  Browse 150 ADE20K classes ▸
</button>
<div id="segClassPanel" style="display:none">
  <input type="text" oninput="renderSegClassList(this.value)" placeholder="Search classes…">
  <span id="segClassCount">150 classes</span>
  <div id="segClassGrid">…</div>
</div>
```

**JS functions:** `toggleSegClassBrowser()`, `renderSegClassList(q)` — live filter, count updates to "N of 150 matching".

Also fixed stale subtitle: "FCN-ResNet50 / Pascal VOC 21" → "SegFormer-B0 / ADE20K 150 categories".

Also fixed stale Vision sidebar button sub: "FCN · Pascal VOC 21 classes" → "SegFormer-B0 · ADE20K 150 classes".

---

## 4. RENDER_VISION_DEPLOY_HOOK_URL Secret

User added the secret to GitHub → Actions → Secrets. CI now auto-deploys ml-vision on every push to main.

**How to get the deploy hook URL:**
1. Render dashboard → ml-vision service → Settings → Deploy Hook → copy URL
2. GitHub repo → Settings → Secrets and variables → Actions → New repository secret
3. Name: `RENDER_VISION_DEPLOY_HOOK_URL` → paste URL

---

## 5. ML Vision Platform Card — ml-portfolio

Added to `src/data/registry.json`:

```json
{
  "id": "ml-vision",
  "title": "ML Vision Platform",
  "description": "Three vision tasks in one app: classify images across 1000 ImageNet categories (MobileNetV2 · ResNet50 · SqueezeNet · GoogLeNet), detect objects with TinyYOLOv3 (COCO 80 classes), and segment scenes pixel-by-pixel with SegFormer-B0 (ADE20K 150 classes). All models run as ONNX on a FastAPI microservice.",
  "model": "SegFormer-B0 · YOLOv3 · MobileNetV2",
  "task": "Vision",
  "dataset": "ImageNet · COCO · ADE20K",
  "metric": "150",
  "metricLabel": "Seg Classes",
  "features": 3,
  "classes": null,
  "tags": ["Vision", "ONNX", "Segmentation", "Detection", "Classification"],
  "url": "https://ml-unified.onrender.com/?mode=vision",
  "github": "https://github.com/ramleo/ML-Unified",
  "accent": "#a78bfa"
}
```

Purple accent `#a78bfa` matches the in-app vision panel colour. URL includes `?mode=vision` so it opens directly in vision-only mode.

---

## 6. Portfolio Link in ML-Unified Navbar

Added a pill-shaped link in the top-right navbar between the logo and the theme toggle:

```html
<a href="https://ml-portfolio-rho.vercel.app/"
   style="font-size:0.75rem;color:var(--text3);border:1px solid var(--border2);
          border-radius:9999px;padding:0.3rem 0.65rem;…">
  📄 Portfolio
</a>
```

Adapts to light/dark theme via CSS vars. Hover darkens text + border.

---

## 7. Sidebar Mode Filtering — `?mode=` URL Param

### How it works

`APP_MODE` is read once on load:
```js
const APP_MODE = new URLSearchParams(window.location.search).get('mode') || 'all';
```

`renderSidebar()` uses two flags:
```js
const showML     = APP_MODE !== 'vision';  // false when mode=vision
const showVision = APP_MODE !== 'ml';       // false when mode=ml
```

| URL | Sidebar | Nav title | Train button |
|---|---|---|---|
| `?mode=ml` | Supervised + Unsupervised only | ML Unified | Visible |
| `?mode=vision` | Vision only | ML Vision | Hidden |
| (none) | All sections | ML Unified | Visible |

### Nav title update (applied immediately on load)
```js
if (APP_MODE === 'vision') {
  titleEl.textContent = 'ML Vision';
  subEl.textContent   = 'Computer Vision Platform';
}
```

### Portfolio registry URLs updated
- ML Unified Platform: `https://ml-unified.onrender.com/?mode=ml`
- ML Vision Platform: `https://ml-unified.onrender.com/?mode=vision`

### Future microservices note
When ml-vision gets its own frontend URL, change `registry.json` Vision card `url` from `ml-unified.onrender.com/?mode=vision` to `ml-vision.onrender.com`. No other changes needed — the mode filtering stays in place for the unified app, and the portfolio card points to the standalone vision app.

---

## Commits This Session

### ML-Unified repo

| Hash | Description |
|---|---|
| `ad517b4` | Add SegFormer-B0 semantic segmentation (ADE20K 150 classes) |
| `ffcfba9` | Fix segmentation warmup message and retry countdown (20 s → 30 s, ~135 MB → ~4.4 MB) |
| `783740d` | Add ADE20K 150-class browser to image segmentation panel |
| `56b0cfc` | Add Portfolio link to navbar |
| `05c30f7` | Filter sidebar sections by ?mode=ml or ?mode=vision URL param |

### ml-portfolio repo

| Hash | Description |
|---|---|
| `142b26e` | Add ML Vision Platform card to portfolio registry |
| `1ae3a84` | Add ?mode= param to portfolio card URLs for section filtering |

---

## Architecture — Current State

```
GitHub → CI (ruff + pytest) → Render deploy hooks

ml-api  (services/ml-api/)  → https://ml-unified.onrender.com
  ├── Training, classification, unsupervised, predict, analyze
  ├── Serves frontend/index.html (injects ML_VISION_URL as VISION_API)
  ├── ?mode=ml     → sidebar shows Supervised + Unsupervised only
  ├── ?mode=vision → sidebar shows Vision only, nav = "ML Vision"
  ├── (no param)   → shows all sections
  └── Portfolio link in navbar → ml-portfolio-rho.vercel.app

ml-vision  (services/ml-vision/)  → separate Render service
  ├── Image Classifier: MobileNetV2 / ResNet50 / SqueezeNet / GoogLeNet
  ├── Image Processing: PIL operations
  ├── Object Detection: TinyYOLOv3-11 (COCO 80 classes, 35 MB ONNX)
  ├── Image Segmentation: SegFormer-B0 (ADE20K 150 classes, 4.4 MB ONNX)
  │     └── PIL colour_segmentation as explicit fallback
  ├── Warmup thread: pre-downloads TinyYOLOv3 + SegFormer-B0 on startup
  └── Auto-deploy via RENDER_VISION_DEPLOY_HOOK_URL (GitHub secret ✅)

ml-portfolio  → https://ml-portfolio-rho.vercel.app  (Vercel)
  ├── ML Unified Platform card → ?mode=ml  (accent #e879f9)
  └── ML Vision Platform card  → ?mode=vision (accent #a78bfa)
```

---

## Vision Panel — Current Status

| Feature | Model | Status |
|---|---|---|
| Image Classifier | MobileNetV2 / ResNet50 / SqueezeNet / GoogLeNet | ✅ Working |
| Image Processing | PIL (no model) | ✅ Working |
| Object Detection | TinyYOLOv3-11 (COCO 80 classes, 35 MB) | ✅ Working |
| Image Segmentation | SegFormer-B0 (ADE20K 150 classes, 4.4 MB) | ✅ Working |
| Segmentation fallback | PIL colour_segmentation (instant) | ✅ Working |
| Class browsers | COCO 80 (detection) + ADE20K 150 (segmentation) | ✅ Working |

---

## Standing Rules

- Apply changes to ALL affected repos simultaneously
- Conversation logs stored in `ML-Iris/Conversations/` folder
- Light theme: ALL elements must adapt
- Vercel = portfolio only; Render = ML app
- ML-Unified → Render auto-deploy on push to main (~3–5 min), gated by CI
- ml-vision → Render auto-deploy via RENDER_VISION_DEPLOY_HOOK_URL (GitHub secret)
- `vision_cache/` must never be committed
- `.mcp.json` must never be committed
- Always run `ruff check` + `pytest` locally before pushing
- Always verify CI logs before claiming a pipeline is working
- Use mock-based tests for inference paths that require model downloads
- Share `_large_vision_cache` slot — never load two large ONNX models simultaneously
- Boosting libraries (xgboost/lightgbm/catboost) must stay as lazy imports inside `train_model`
- User-facing errors: plain English only — no shapes, tracebacks, or tensor info
- Error technical details → server logs (stdout on Render), not UI
- `secrets` context NOT allowed in GitHub Actions step-level `if:` — use env var + shell check
- Keep ml-api and ml-vision `requirements.txt` fully independent (no shared deps)
- All vision endpoint URLs sourced from `VISION_API`, never `API`
- New vision features go in ml-vision only, not ml-api
- When ml-vision gets its own URL: update `registry.json` Vision card `url` field only
