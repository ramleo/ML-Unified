# Conversation — 2026-06-05 | Detection Fixes + Progress Bar (Part 20)

**Date:** 2026-06-05
**Project:** ML-Unified

---

## Points Completed This Session

| # | Item | Status |
|---|---|---|
| — | Switch Object Detection: SSD-12 → TinyYOLOv3-11 (35 MB, MIT) | ✅ Done |
| — | Fix infinite retry loop — max 3 attempts + Stop button | ✅ Done |
| — | Progress bar (upload % real + inference animated) for detection + segmentation | ✅ Done |
| — | Fix 500 "Internal Server Error" — wrap all postprocessing in try/except | ✅ Done |
| — | Fix detection postprocessing — batch dim + indices normalisation | ✅ Done |
| — | Fix letterbox preprocessing — YOLO requires aspect-ratio-preserving resize | ✅ Done |
| — | Add COCO 80 class browser to detection panel (searchable, like classifier) | ✅ Done |

---

## TinyYOLOv3-11 Switch

### Why
SSD-12 was 100 MB on disk, expanding to ~200 MB in ONNX Runtime memory — too large for Render free tier (512 MB RAM).

### Model
| Property | Value |
|---|---|
| Model | TinyYOLOv3-11 |
| License | MIT ✓ |
| Source | ONNX Model Zoo |
| Size | ~35 MB |
| Classes | COCO 80 (0-indexed, no background at 0) |
| Input 1 | `input_1` — (1, 3, 416, 416), normalised [0,1] only (no ImageNet mean/std) |
| Input 2 | `image_shape` — (1, 2) = [416, 416] (model input size, not original) |
| Output 0 | boxes — (1, max_boxes, 4) — y1,x1,y2,x2 in letterboxed 416×416 space |
| Output 1 | scores — (1, 80, max_boxes) — per-class confidence |
| Output 2 | indices — (num_det, 3) — [batch, class, box] post-NMS |

### Key differences from SSD-12
- Two inputs (image + image_shape) vs one
- No ImageNet normalisation — divide by 255 only
- Letterbox preprocessing (aspect-ratio-preserving, grey padding) — NOT simple stretch
- Outputs include NMS indices array, not parallel label/score arrays
- Class IDs are 0-indexed (class 0 = person), so `name_idx = class_idx + 1` for existing `_COCO_CLASSES` list
- Input names read from `session.get_inputs()` dynamically (not hardcoded)

---

## Retry Loop Fix

### Problem
`showDetRetry` and `showSegRetry` retried forever with no way to stop.

### Fix
- Max 3 attempts — after 3rd failure, shows permanent red error
- **Stop button** visible during countdown — clears timer, resets count
- `_detRetryCount` / `_segRetryCount` module-level state tracks across calls
- `cancelDetRetry()` / `cancelSegRetry()` reset state and clear timers

---

## Progress Bar

### Design
Replaces static "Running…" spinner with an XHR-based animated bar.

| Phase | Range | Source |
|---|---|---|
| Uploading | 0–30% | Real XHR `upload.progress` events |
| Running model | 30–65% | Animated crawl (~0.65% per 260 ms) |
| Processing | 65–90% | Continues crawl, stalls near 90% |
| Complete | 100% | Snaps when XHR `load` fires |

### Implementation
Shared helper `_postWithProgress(url, formData, resultId, accent, noteText)` used by both detection and segmentation. Returns a Promise with `{ status, ok, text(), json() }` interface matching fetch — no changes needed to error handling.

Accent colours:
- Detection: `#38bdf8` (sky-blue)
- Segmentation: `#a78bfa` (violet)

---

## Detection Debugging — 4 Rounds

### Round 1: Generic "Internal Server Error"
**Cause:** FastAPI's default handler catches unhandled exceptions and returns `{"detail": "Internal Server Error"}`. Postprocessing (sort, PIL drawing, base64) was entirely outside try/except.

**Fix:** Dynamic input names from `session.get_inputs()` + wrap entire preprocessing/inference/postprocessing/drawing in one try/except.

---

### Round 2: "Detection failed: index 1 is out of bounds for axis 0 with size 0"
**Now visible because try/except was fixed.**

**Root cause:** When ONNX runtime returns `indices` as shape `(0,)` for zero NMS detections instead of `(0, 3)`, iterating gives 0-element rows and `row[1]` fails.

**Fix (commit `2bfafa1`):**
- Keep batch dim throughout: `scores_out[batch, class, box]`, `boxes_out[batch, box]`
- Normalise indices to `(K, 3)` before iterating:
  ```python
  if indices_raw.ndim < 2 or indices_raw.size == 0:
      indices_2d = np.empty((0, 3), dtype=np.int64)
  else:
      indices_2d = indices_raw.reshape(-1, 3)
  ```
- Full bounds check on all output array dimensions
- Output shapes temporarily included in error message for debugging

---

### Round 3: "No objects detected above the confidence threshold" (0 detections at 15%)

**Cause:** Simple `img.resize(416, 416)` distorts the aspect ratio. YOLO models are trained on **letterboxed** images (aspect-ratio-preserving resize + grey padding). A 236×148 bicycle stretched to 416×416 becomes 2.8× taller relative to width — the model fails to recognise it.

**Fix (commit `f989ee5`):**
```python
scale  = min(size / orig_w, size / orig_h)
nw, nh = int(orig_w * scale), int(orig_h * scale)
pad_x  = (size - nw) // 2
pad_y  = (size - nh) // 2
canvas = PILImage.new("RGB", (size, size), (128, 128, 128))
canvas.paste(img.resize((nw, nh), PILImage.LANCZOS), (pad_x, pad_y))
# Pass model input size so boxes come back in 416×416 letterboxed space
image_shape = np.array([[size, size]], dtype=np.float32)
```

Unletterbox after NMS to convert boxes back to original pixel coordinates:
```python
x1 = (x1_lb - pad_x) / scale
y1 = (y1_lb - pad_y) / scale
```

**Result: Detection confirmed working ✅**

---

## COCO Class Browser

Added a collapsible "Browse 80 COCO classes ▸" section at the bottom of the detection panel, matching the image classifier's "Browse 1,000 categories" pattern.

- Live search filter
- 80 classes inlined in JS as `_COCO_80` array (no API call needed)
- Toggle functions: `toggleDetClassBrowser()`, `renderDetClassList(q)`
- Same grid layout and styling as the ImageNet category browser

---

## UX Feedback Saved to Memory

**Rule:** User-facing errors must be plain English only. Never show numpy shapes, stack traces, or tensor info in the UI.

- Temporary exception: shape info is in error message while debugging TinyYOLOv3 (detection now confirmed working — cleanup pending)
- Future: generic "Detection failed — please try again" for users; technical detail to `stdout` (Render logs) or a dedicated log file

---

## Commits This Session

| Hash | Description |
|---|---|
| `7b795f2` | Switch detection to TinyYOLOv3-11 (35 MB, MIT) and fix infinite retry loop |
| `4d5fdca` | Show upload + inference progress % in detection and segmentation panels |
| `be30b83` | Fix detection 500: dynamic input names and wrap all postprocessing in try/except |
| `2bfafa1` | Fix detection postprocessing: keep batch dim, normalise indices shape |
| `f989ee5` | Fix detection: letterbox preprocessing instead of simple stretch |
| `f28c420` | Add COCO class browser to object detection panel |

---

## Vision Sidebar — Status

| Feature | Accent | Model | Status |
|---|---|---|---|
| Image Classifier | Pink `#e879f9` | MobileNetV2 / ResNet50 / SqueezeNet / GoogLeNet | ✅ Working |
| Image Processing | Orange `#fb923c` | PIL (no model) | ✅ Working |
| Object Detection | Sky-blue `#38bdf8` | TinyYOLOv3-11 (COCO 80 classes, MIT) | ✅ Working |
| Image Segmentation | Violet `#a78bfa` | FCN-ResNet50 (Pascal VOC 21 classes) | ⚠️ Pending test |

---

## Architecture Discussions

### Vision Portfolio Card
User asked whether a dedicated Vision card can be added to the ML-Iris portfolio (Vercel), matching the style of the existing ML-Unified card.

**Answer: Yes — straightforward.**
Vision suite already runs on the same Render URL. A new card on the portfolio just links to it. HTML/CSS change on ML-Iris only, no backend work.

**Decision: Pending user confirmation to proceed.**

---

### Microservices Conversion
User asked whether the existing monolith (`app.py`) can be split into microservices.

**Answer: Yes — but with a trade-off on Render free tier.**

Current monolith:
```
ML Training + Classification + Detection + Segmentation + Processing  (one app.py)
```

Proposed split (two services to start):
```
ml-api     — training, classification, image processing (no ONNX, no vision models)
ml-vision  — object detection + segmentation (ONNX only, no boosting libraries)
```

**Why it helps:**
- Solves the 512 MB OOM problem properly — vision models isolated from catboost/xgboost overhead
- Independent deploys and restarts
- Cleaner separation of concerns

**The Render free tier catch:**
Each free service sleeps after 15 min inactivity. With two services, a cold-start request may need to wake both — cascading 30–60 s delays. On a paid tier this is a non-issue.

**Recommendation:** Start with two services (ml-api + ml-vision). Not 4–5, to avoid coordination complexity.

**Decision: Pending user confirmation to proceed.**

---

### Microservices — Can We Add More Services Later?

User asked whether the number of microservices can be increased beyond the initial 2-service split.

**Answer: Yes — the 2-service split is just the starting point.**

Natural expansion path:

| Service | What it holds | When to split it out |
|---|---|---|
| `ml-api` | Training + Classification | Starting point — split further when needed |
| `ml-training` | Training only (async jobs) | When catboost/xgboost 30–120 s runs block classification requests |
| `ml-classify` | Image classifier (small ONNX models) | If MobileNetV2/ResNet compete for RAM with detection |
| `ml-vision` | Detection + Segmentation | Already proposed |
| `ml-processing` | PIL image ops | Rarely worth isolating — fast CPU-only ops |

**Practical guidance:**
- Start with 2, prove the split on Render, then add a third only when a real bottleneck is hit (OOM, slow responses, deploy coupling)
- Each additional free-tier service adds another potential cold-start in the chain
- The split is just FastAPI app boundaries — reorganisation is mechanical once the boundary is decided

---

## Pending — Items Remaining

| # | Item |
|---|---|
| — | Clean up shape info from error message → move to logs |
| — | Test image segmentation end-to-end |
| — | Add Vision card to ML-Iris portfolio (pending approval) |
| — | ~~Microservices split: ml-api + ml-vision~~ ✅ Done (commit `1a3a2b0`) |
| 12 | Monitoring — Grafana + Prometheus |
| 13 | Data drift / model drift detection |
| 14 | MLflow experiment tracking |
| 16 | Data injection (DB, cloud, real-time) |
| 18 | E2E browser testing — Playwright |
| 19 | Full pipeline validation |
| 20 | CI/CD end-to-end automation |

---

---

## Microservices Split (2026-06-05)

### What was done
Monolith `app.py` split into two independent FastAPI services. Commit `1a3a2b0`.

| Service | Path | Contents | Requirements |
|---|---|---|---|
| `ml-api` | `services/ml-api/` | Training, Classification, Unsupervised, `/app-config` | sklearn, pandas, xgboost, lightgbm, catboost — **no onnxruntime** |
| `ml-vision` | `services/ml-vision/` | Image classify, process, detect, segment | onnxruntime, Pillow, numpy — **no boosting libs** |

### Memory budgets after split
| Service | Base | Peak model | Total |
|---|---|---|---|
| `ml-api` | ~150 MB | ~200 MB (catboost during training) | ~350 MB ✓ |
| `ml-vision` | ~80 MB | ~300 MB (FCN-ResNet50) | ~380 MB ✓ |

Both fit within Render free tier 512 MB limit.

### Frontend routing
`/app-config` endpoint added to `ml-api` — returns `{"vision_url": ML_VISION_URL_env}`.
Frontend calls `initVisionUrl()` on load, stores `VISION_API`. All vision endpoints
(`/classify-image`, `/imagenet-classes`, `/process-image`, `/detect-objects`, `/segment-image`)
now use `${VISION_API}/...` instead of `${API}/...`.

### Render setup required
1. Create **ml-api** service on Render — root dir: `services/ml-api/`
2. Create **ml-vision** service on Render — root dir: `services/ml-vision/`
3. After ml-vision is deployed, copy its URL into ml-api's `ML_VISION_URL` environment variable
4. Add `RENDER_VISION_DEPLOY_HOOK_URL` GitHub secret for the new service's deploy hook
5. Delete the old `ml-unified` service

### Tests
- `services/ml-api/tests/test_api.py` — 24 tests ✅
- `services/ml-vision/tests/test_vision.py` — 19 tests ✅

---

## Standing Rules

- Apply changes to ALL affected repos simultaneously
- Conversation logs stored in `ML-Iris/Conversations/` folder
- Light theme: ALL elements must adapt
- Vercel = portfolio only; Render = ML app
- ML-Unified → Render auto-deploy on push to main (~3–5 min), gated by CI
- `vision_cache/` must never be committed
- `.mcp.json` must never be committed
- Always run `ruff check` + `pytest` locally before pushing
- Always verify CI logs before claiming a pipeline is working
- Use mock-based tests for inference paths that require model downloads
- Share `_large_vision_cache` slot — never load two large ONNX models simultaneously
- Boosting libraries (xgboost/lightgbm/catboost) must stay as lazy imports inside `train_model`
- User-facing errors: plain English only — no shapes, tracebacks, or tensor info
- Error technical details → server logs (stdout on Render), not UI
