# Conversation — 2026-06-04 | Vision Suite: Image Processing + Object Detection (Part 18)

**Date:** 2026-06-04
**Project:** ML-Unified

---

## Points Completed This Session

| # | Item | Status |
|---|---|---|
| 15b | Image Processing — 11 PIL operations, before/after comparison | ✅ Done |
| 15c | Object Detection — SSD-12 (Apache 2.0), COCO 80 classes | ✅ Done |
| — | Test quality fix — mock-based inference tests for classification + detection | ✅ Done |

**Updated score: 15 done (partial on 15), 5 pending.**

---

## 15b — Image Processing

### What was built
- `GET /image-operations` — returns 11 operations with their param specs
- `POST /process-image` — accepts image + operation, returns base64 PNG
- No new pip dependencies — Pillow already installed

### Operations
| ID | Label | Params |
|---|---|---|
| `grayscale` | Grayscale | none |
| `blur` | Gaussian Blur | radius (1–20) |
| `sharpen` | Sharpen | strength (1.0–5.0) |
| `edges` | Edge Detection | none (PIL FIND_EDGES) |
| `rotate` | Rotate | angle (−180 to +180°) |
| `brightness` | Brightness | factor (0.1–3.0) |
| `contrast` | Contrast | factor (0.1–3.0) |
| `flip_h` | Flip Horizontal | none |
| `flip_v` | Flip Vertical | none |
| `emboss` | Emboss | none |
| `invert` | Invert Colors | none |

### Frontend
- Orange accent (`#fb923c`) sidebar entry under Vision
- Operation chips — click to select, dynamic param inputs appear per operation
- Before/After side-by-side comparison
- Download button (anchor tag with base64 href)

### Backend detail
- Input images capped at 1200px longest side before processing (keeps response size reasonable)
- Params clamped server-side (blur_radius max 20, etc.)

---

## 15c — Object Detection

### Model
| Property | Value |
|---|---|
| Model | SSD-12 (Single Shot MultiBox Detector) |
| Backbone | ResNet-34 |
| License | Apache 2.0 ✓ |
| Source | ONNX Model Zoo |
| Size | ~100 MB |
| Classes | COCO 80 (person, car, cat, dog, chair, bottle, …) |
| Input | 1200×1200, PyTorch ImageNet normalisation |

### Endpoint
- `GET /detect-models` — returns model metadata
- `POST /detect-objects` — accepts image + confidence threshold, returns annotated image + JSON detections

### Response shape
```json
{
  "model": "ssd",
  "model_label": "SSD",
  "count": 2,
  "confidence_threshold": 0.3,
  "detections": [
    {
      "class_id": 1,
      "label": "person",
      "confidence": 0.92,
      "box": {"x1": 50, "y1": 30, "x2": 320, "y2": 480}
    }
  ],
  "image_b64": "data:image/png;base64,...",
  "orig_width": 640,
  "orig_height": 480
}
```

### Box coordinate handling
- Detects at runtime whether boxes are normalised [0,1] or absolute [0, 1200]
- Scales to original image dimensions in both cases
- Clamps to image bounds, skips degenerate boxes (x2 ≤ x1 or y2 ≤ y1)

### PIL drawing (server-side)
- Bounding boxes drawn with `ImageDraw.rectangle()` — width 3px
- Label + confidence printed on a filled colour rectangle above each box
- 12-colour palette, assigned by class ID

### Frontend
- Sky-blue accent (`#38bdf8`) sidebar entry under Vision
- Confidence threshold slider (5–90%)
- Annotated image shown full-width in result panel
- Colour-coded detection tags (one per class found)
- Download button
- Warning message when no objects detected above threshold

### First-call latency on Render free tier
~60–90 s (100 MB model download). Subsequent calls fast (model cached in memory).

---

## Test Quality Fix

### Problem identified
User asked: "don't you test the code?" — valid. Classification and detection tests only hit the 400 error path. The real inference code (preprocessing, softmax, box parsing, PIL drawing) was never executed in CI.

### Solution: mock-based inference tests
Mocked `onnxruntime.InferenceSession` so the full application pipeline runs without downloading models. `session.run()` is replaced; everything before and after it is real code.

### New tests added
| Test | What it verifies |
|---|---|
| `test_classify_image_inference` | Preprocessing → normalisation → CHW transpose → softmax → top-K → correct label |
| `test_classify_image_low_confidence` | Flat logits → `low_confidence: true` fires when top score ≈ 0.001 |
| `test_detect_objects_inference` | Box coordinate scaling → PIL ImageDraw → base64 PNG → correct label/confidence |
| `test_detect_objects_confidence_filter` | Score 0.2 excluded when threshold 0.5; score 0.9 included |

**Total: 36 tests (was 32).**

---

## Commits This Session

| Hash | Description |
|---|---|
| `6457890` | Add image processing: 11 PIL operations with before/after comparison |
| `b7ebdf4` | Add object detection: SSD-12 (Apache 2.0) with COCO 80 classes |
| `734cd72` | Fix ruff E702: split semicolon-joined assignments in detect_objects |
| `e08128e` | Strengthen tests: mock ONNX sessions to exercise real inference code |

---

## CI Failure This Session

**Commit `b7ebdf4` failed CI (ruff E702):**
- Cause: semicolon-joined assignments on one line, e.g. `y1 = b[0] * orig_h;  x1 = b[1] * orig_w`
- Fix: split to separate lines in commit `734cd72`
- Lesson: always run `ruff check` locally before pushing

---

## Files Modified

| File | Changes |
|---|---|
| `app.py` | Added `_IMG_OPERATIONS`, `POST /process-image`, `GET /image-operations`, `_COCO_CLASSES`, `_DETECTION_MODEL_CONFIGS`, `POST /detect-objects`, `GET /detect-models` |
| `frontend/index.html` | Image Processing panel + Object Detection panel + sidebar buttons + CSS |
| `tests/test_api.py` | 9 new tests (5 image processing + 4 vision inference/detection) |

---

## Pending — 5 Items Remaining

| # | Item |
|---|---|
| 15d | Image Segmentation (remaining vision task) |
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
