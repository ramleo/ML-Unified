# Conversation — 2026-06-04 | Image Segmentation + OOM Debugging (Part 19)

**Date:** 2026-06-04
**Project:** ML-Unified

---

## Points Completed This Session

| # | Item | Status |
|---|---|---|
| 15d | Image Segmentation — FCN-ResNet50 (Apache 2.0), Pascal VOC 21 classes | ✅ Done |
| — | Fix: 502/OOM — shared vision model slot | ✅ Done |
| — | Fix: JS body stream already read error | ✅ Done |
| — | Fix: lazy-import xgboost/lightgbm/catboost (~200 MB saved at startup) | ✅ Done |

---

## 15d — Image Segmentation

### Model
| Property | Value |
|---|---|
| Model | FCN-ResNet50 (Fully Convolutional Network) |
| Backbone | ResNet-50 |
| License | Apache 2.0 ✓ |
| Source | ONNX Model Zoo |
| Size | ~135 MB |
| Classes | Pascal VOC 21 (background + 20 foreground) |
| Input | Any H×W (capped at 480px), ImageNet normalisation |

### Pascal VOC 21 Classes
background, aeroplane, bicycle, bird, boat, bottle, bus, car, cat, chair, cow,
diningtable, dog, horse, motorbike, person, pottedplant, sheep, sofa, train, tvmonitor

### Endpoints
- `GET /seg-models` — returns model metadata
- `POST /segment-image` — accepts image, returns colour-overlay PNG + class breakdown

### Response shape
```json
{
  "model": "fcn_resnet50",
  "model_label": "FCN-ResNet50",
  "classes_found": [
    {"class_id": 15, "label": "person", "pixel_count": 12345, "percentage": 8.5, "color": "#c08080"}
  ],
  "image_b64": "data:image/png;base64,...",
  "orig_width": 640,
  "orig_height": 480
}
```

### Visualisation
- argmax over 21 classes → per-pixel label map
- Pascal VOC standard colour palette mapped to each class
- RGBA overlay blended onto original image at ~70% opacity
- Background (class 0) transparent

### Frontend
- Violet `#a78bfa` sidebar button under Vision
- Upload zone, preview, Segment Image button
- Result: overlay image full-width, colour-coded class chips with coverage %
- Download button

### Tests added (4 new, 40 total)
| Test | What it verifies |
|---|---|
| `test_list_seg_models` | GET /seg-models returns fcn_resnet50 |
| `test_segment_image_bad_model` | 400 for unknown model |
| `test_segment_image_inference` | Mock session → person class detected, overlay returned |
| `test_segment_image_background_only` | All-background logits → classes_found == [] |

---

## OOM Debugging — 3 Rounds

### Round 1: Goldfish / bicycle returns 502
**Diagnosis:** SSD model (100 MB) was downloaded inside the request handler.
Render cold start (~20s) + model download (~60s) = ~80s total → worker killed → 502.

**Fix attempted:** Background preload threads at startup.
- `_preload_det()` thread downloads SSD on startup
- `_preload_seg()` thread downloads FCN on startup

**Result:** Made it worse → OOM (next section).

---

### Round 2: "Ran out of memory (used over 512 MB)"
**Diagnosis:** Both preload threads ran simultaneously:
- SSD (100 MB in RAM) + FCN (135 MB in RAM) + Python overhead (~310 MB) = ~545 MB → OOM

**Fix:** Remove preload threads. Replace two separate caches with a **shared slot**:
```python
_large_vision_cache: Dict[str, Any] = {}   # "model_type", "model_id", "session"
_large_vision_lock:  threading.Lock  = threading.Lock()
```
- Only ONE large model lives in RAM at a time
- Loading detection evicts segmentation (and vice versa)
- `_load_det_session()` and `_load_seg_session()` both call `_large_vision_cache.clear()` first

**JS bug caught at same time:** `res.json()` consumed the response body stream, then `catch` block tried `res.text()` on the already-read stream → "body stream already read". Fixed by reading raw text once, then `JSON.parse(text)`.

**Result:** Render still 502 → OOM persists (next section).

---

### Round 3: Still 502 — SSD alone is too large
**Diagnosis:** Even with shared slot, SSD-12 (100 MB file) may expand to ~200 MB in ONNX Runtime. Combined with startup overhead:
- CatBoost `.so` on Linux: ~100-150 MB (well-known large library)
- xgboost: ~20-30 MB
- lightgbm: ~15-20 MB
- Total boosting overhead: ~200 MB loaded at startup even when no training happens

**Fix:** Move xgboost, lightgbm, catboost to **lazy imports** inside `train_model`:
```python
# Removed from top-level:
# from xgboost import XGBClassifier, XGBRegressor
# from lightgbm import LGBMClassifier, LGBMRegressor
# from catboost import CatBoostClassifier, CatBoostRegressor

# Added inside train_model():
from xgboost import XGBClassifier, XGBRegressor          # noqa: PLC0415
from lightgbm import LGBMClassifier, LGBMRegressor        # noqa: PLC0415
from catboost import CatBoostClassifier, CatBoostRegressor  # noqa: PLC0415
```

**Memory budget after fix (estimated):**
| Component | Before | After |
|---|---|---|
| Python + FastAPI + sklearn | ~130 MB | ~130 MB |
| xgboost + lightgbm + catboost | ~200 MB | 0 MB (lazy) |
| onnxruntime + misc | ~50 MB | ~50 MB |
| pkl models (sklearn only) | ~30 MB | ~30 MB |
| **Startup total** | **~410 MB** | **~210 MB** |
| SSD on first detection call | — | +~100-200 MB |
| **Peak** | **>512 MB → OOM** | **~310-410 MB ✓** |

**Status at session end:** Fix deployed, awaiting confirmation from user.

---

## Open Question (User raised)
1. **Are catboost etc the definite culprit?** — Honest answer: No, not proven. CatBoost `.so` is genuinely large on Linux but exact number unconfirmed. SSD-12 itself could be 200+ MB in ONNX Runtime RAM. Both factors compound.

2. **Lightweight SSD alternative?** — TinyYOLOv3-11 (35 MB, MIT license, ONNX Model Zoo, same 80 COCO classes) is the best available option. SSD-MobileNetV2 exists (~20 MB) but is not pre-built in ONNX Model Zoo. YOLOv5n is 4 MB but AGPL-3.0.

**Pending decision:** Switch detection to TinyYOLOv3-11 if OOM persists.

---

## Commits This Session

| Hash | Description |
|---|---|
| `06709f3` | Add image segmentation: FCN-ResNet50 (Apache 2.0), Pascal VOC 21 classes |
| `7497bdd` | Fix 502: preload detection and segmentation models in background threads |
| `e0543f6` | Fix OOM: share single model slot for detection and segmentation |
| `2685e76` | Fix JS error: read response body once as text before JSON parsing |
| `2076cde` | Lazy-import xgboost/lightgbm/catboost to free ~200 MB at startup |

---

## Vision Sidebar — Complete

| Feature | Accent | Model | Status |
|---|---|---|---|
| Image Classifier | Pink `#e879f9` | MobileNetV2 / ResNet50 / SqueezeNet / GoogLeNet | ✅ Working |
| Image Processing | Orange `#fb923c` | PIL (no model) | ✅ Working |
| Object Detection | Sky-blue `#38bdf8` | SSD-12 (COCO 80 classes) | ⚠️ OOM under investigation |
| Image Segmentation | Violet `#a78bfa` | FCN-ResNet50 (Pascal VOC 21 classes) | ⚠️ OOM under investigation |

---

## Pending — Items Remaining

| # | Item |
|---|---|
| — | Confirm OOM fix works / switch to TinyYOLOv3 if not |
| 12 | Monitoring — Grafana + Prometheus |
| 13 | Data drift / model drift detection |
| 14 | MLflow experiment tracking |
| 16 | Data injection (DB, cloud, real-time) |
| 18 | E2E browser testing — Playwright |
| 19 | Full pipeline validation |
| 20 | CI/CD end-to-end automation |

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
- Boosting libraries (xgboost/lightgbm/catboost) must stay as lazy imports
