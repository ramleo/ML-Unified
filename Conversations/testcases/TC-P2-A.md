# TC-P2-A — Test Cases (Parts 16–24)

> Coverage: CI/CD pipeline · Image Classification · Image Processing · Object Detection · Image Segmentation · OOM/timeout fixes · Microservices split · SegFormer-B0 · Theme sync · Sidebar mode filtering · Live Metrics panel

---

### TC-P2-001
**Category:** Backend  
**Test Name:** CI pipeline blocks deploy when lint fails  
**Steps:**
1. Introduce a ruff lint error (e.g. `import os, sys` on one line) in `services/ml-api/app.py`
2. Push to main branch on GitHub
3. Monitor `.github/workflows/ci.yml` Actions run
**Expected Result:** `ruff check` step fails; `deploy` job is skipped (not triggered); Render deploy hook is NOT called  
**Source:** Part16

---

### TC-P2-002
**Category:** Backend  
**Test Name:** CI pipeline blocks deploy when unit tests fail  
**Steps:**
1. Edit `services/ml-api/tests/test_api.py` — change a passing assertion to fail (e.g. `assert response.status_code == 999`)
2. Push to a PR branch on GitHub
3. Monitor Actions run
**Expected Result:** `pytest` step fails; `deploy` job is skipped; PR shows a failed check status  
**Source:** Part16

---

### TC-P2-003
**Category:** Backend  
**Test Name:** CI cache busts when requirements.txt changes  
**Steps:**
1. Add a comment line to `requirements.txt` (changes the file hash)
2. Push to main
3. In GitHub Actions run, check pip cache restore key
**Expected Result:** Cache miss occurs; pip reinstalls all packages from scratch; CI succeeds  
**Source:** Part17

---

### TC-P2-004
**Category:** Backend  
**Test Name:** GET /health returns 200  
**Steps:**
1. `GET https://ml-unified.onrender.com/health`
**Expected Result:** HTTP 200; response body contains `{"status": "ok"}` or equivalent health payload  
**Source:** Part16

---

### TC-P2-005
**Category:** Backend  
**Test Name:** GET /models returns expected model fields  
**Steps:**
1. `GET https://ml-unified.onrender.com/models`
**Expected Result:** HTTP 200; JSON array; each item contains at minimum `id`, `name`, and `task` fields  
**Source:** Part16

---

### TC-P2-006
**Category:** Backend  
**Test Name:** GET /schemas/{id} — valid model returns schema  
**Steps:**
1. `GET https://ml-unified.onrender.com/schemas/iris`
**Expected Result:** HTTP 200; JSON schema describing Iris features (sepal_length, sepal_width, petal_length, petal_width)  
**Source:** Part16

---

### TC-P2-007
**Category:** Backend  
**Test Name:** GET /schemas/{id} — unknown model returns 404  
**Steps:**
1. `GET https://ml-unified.onrender.com/schemas/nonexistent_model`
**Expected Result:** HTTP 404; JSON with a descriptive error message  
**Source:** Part16

---

### TC-P2-008
**Category:** Backend  
**Test Name:** POST /predict/iris — valid Setosa input  
**Steps:**
1. `POST https://ml-unified.onrender.com/predict/iris`
2. Body: `{"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2}`
**Expected Result:** HTTP 200; `prediction` field = `"Iris-setosa"` (or `"setosa"`)  
**Source:** Part16

---

### TC-P2-009
**Category:** Backend  
**Test Name:** POST /predict/iris — valid Virginica input  
**Steps:**
1. `POST https://ml-unified.onrender.com/predict/iris`
2. Body: `{"sepal_length": 6.3, "sepal_width": 3.3, "petal_length": 6.0, "petal_width": 2.5}`
**Expected Result:** HTTP 200; `prediction` field = `"Iris-virginica"` (or `"virginica"`)  
**Source:** Part16

---

### TC-P2-010
**Category:** Backend  
**Test Name:** POST /predict/{id} — unknown model returns 404  
**Steps:**
1. `POST https://ml-unified.onrender.com/predict/fake_model`
2. Body: `{"feature1": 1.0}`
**Expected Result:** HTTP 404; error detail describes model not found  
**Source:** Part16

---

### TC-P2-011
**Category:** Backend  
**Test Name:** POST /analyze — valid CSV classification file  
**Steps:**
1. Prepare a CSV with a mix of numeric + categorical columns and a binary target
2. `POST https://ml-unified.onrender.com/analyze` with multipart form-data containing the CSV
**Expected Result:** HTTP 200; response includes `task`, `rows`, `cols`, and `suggested_models` fields  
**Source:** Part16

---

### TC-P2-012
**Category:** Backend  
**Test Name:** POST /analyze — invalid file type returns 400  
**Steps:**
1. `POST https://ml-unified.onrender.com/analyze` with a `.txt` file instead of CSV
**Expected Result:** HTTP 400 or 422; descriptive error message  
**Source:** Part16

---

### TC-P2-013
**Category:** Backend  
**Test Name:** POST /unsupervised — KMeans returns cluster assignments  
**Steps:**
1. Prepare a numeric-only CSV (e.g. 2-feature dataset)
2. `POST https://ml-unified.onrender.com/unsupervised` with body `{"algorithm": "kmeans", "n_clusters": 3}` + CSV upload
**Expected Result:** HTTP 200; response includes cluster labels and visualization data  
**Source:** Part16

---

### TC-P2-014
**Category:** Backend  
**Test Name:** POST /train — classification task trains and registers model  
**Steps:**
1. Upload a CSV with a categorical target column
2. `POST https://ml-unified.onrender.com/train` with `{"target": "<col>", "task": "classification", "algorithm": "random_forest"}`
**Expected Result:** HTTP 200; returns a new `model_id`; new model appears in `GET /models` response  
**Source:** Part16

---

### TC-P2-015
**Category:** Backend  
**Test Name:** POST /train — invalid task type returns error  
**Steps:**
1. `POST https://ml-unified.onrender.com/train` with `{"task": "invalid_task_type"}`
**Expected Result:** HTTP 422 or 400; error describes invalid task  
**Source:** Part16

---

### TC-P2-016
**Category:** Backend  
**Test Name:** POST /train — missing target column returns error  
**Steps:**
1. Upload a CSV
2. `POST https://ml-unified.onrender.com/train` with `{"task": "classification"}` (no `target` field)
**Expected Result:** HTTP 422; error indicates target column is required  
**Source:** Part16

---

### TC-P2-017
**Category:** Backend  
**Test Name:** GET /image-models returns 4 model IDs  
**Steps:**
1. `GET <VISION_API>/image-models`
**Expected Result:** HTTP 200; JSON array with exactly 4 items; `id` values include `mobilenetv2`, `resnet50`, `squeezenet`, `googlenet`  
**Source:** Part17

---

### TC-P2-018
**Category:** Backend  
**Test Name:** GET /imagenet-classes returns 200 or graceful 500  
**Steps:**
1. `GET <VISION_API>/imagenet-classes`
**Expected Result:** HTTP 200 with an array of 1000 class names OR HTTP 500 with a meaningful error (never a crash without response)  
**Source:** Part17

---

### TC-P2-019
**Category:** Backend  
**Test Name:** POST /classify-image — unknown model returns 400  
**Steps:**
1. `POST <VISION_API>/classify-image` with a valid image file and `model=unknown_model`
**Expected Result:** HTTP 400; error message references the invalid model name  
**Source:** Part17

---

### TC-P2-020
**Category:** Backend  
**Test Name:** POST /classify-image — mobilenetv2 inference returns top predictions  
**Steps:**
1. Upload a JPEG photo of a dog (golden retriever recommended)
2. `POST <VISION_API>/classify-image` with `model=mobilenetv2`
**Expected Result:** HTTP 200; `predictions` array present; `rank: 1` item has `label` and `confidence` > 0; `low_confidence` is a boolean  
**Source:** Part17

---

### TC-P2-021
**Category:** Backend  
**Test Name:** POST /classify-image — low confidence flag fires for out-of-distribution image  
**Steps:**
1. Upload an image of human text / a document (not in ImageNet categories)
2. `POST <VISION_API>/classify-image` with `model=mobilenetv2`
**Expected Result:** HTTP 200; `low_confidence: true`; UI would show yellow warning banner  
**Source:** Part17

---

### TC-P2-022
**Category:** UI  
**Test Name:** Image Classifier — low confidence banner displayed in UI  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=vision`
2. Click "Image Classifier" in sidebar
3. Upload an out-of-distribution image (e.g. a handwritten text page)
4. Click Classify
**Expected Result:** Yellow warning banner appears with "Best guesses (unreliable)" or equivalent text; confidence bars still shown  
**Source:** Part17

---

### TC-P2-023
**Category:** UI  
**Test Name:** Image Classifier — 4 model chips displayed and selectable  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=vision`
2. Click "Image Classifier" in sidebar
**Expected Result:** 4 chips visible: MobileNetV2, ResNet50, SqueezeNet 1.1, GoogLeNet; clicking each chip selects it (highlighted)  
**Source:** Part17

---

### TC-P2-024
**Category:** UI  
**Test Name:** Image Classifier — category browser shows 1000 categories and is searchable  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=vision`
2. Click "Image Classifier"
3. Click "Browse 1,000 categories ▸" toggle
4. Type "dog" in the search box
**Expected Result:** Browser expands; initial count shows 1000 categories; after typing "dog" the visible items filter to dog-related categories  
**Source:** Part17

---

### TC-P2-025
**Category:** Backend  
**Test Name:** GET /image-operations returns 11 operations  
**Steps:**
1. `GET <VISION_API>/image-operations`
**Expected Result:** HTTP 200; JSON array with 11 items; IDs include `grayscale`, `blur`, `sharpen`, `edges`, `rotate`, `brightness`, `contrast`, `flip_h`, `flip_v`, `emboss`, `invert`  
**Source:** Part18

---

### TC-P2-026
**Category:** Backend  
**Test Name:** POST /process-image — grayscale operation returns base64 PNG  
**Steps:**
1. Upload any JPEG image
2. `POST <VISION_API>/process-image` with `operation=grayscale`
**Expected Result:** HTTP 200; response body contains `image_b64` field starting with `data:image/png;base64,`  
**Source:** Part18

---

### TC-P2-027
**Category:** Backend  
**Test Name:** POST /process-image — blur radius is clamped server-side  
**Steps:**
1. Upload any JPEG image
2. `POST <VISION_API>/process-image` with `operation=blur` and `radius=999` (above max)
**Expected Result:** HTTP 200 (no crash); image returned; radius effectively clamped to 20  
**Source:** Part18

---

### TC-P2-028
**Category:** UI  
**Test Name:** Image Processing — before/after comparison displayed  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=vision`
2. Click "Image Processing" in sidebar
3. Upload an image and select "Grayscale" operation
4. Click Apply
**Expected Result:** Before/after side-by-side images displayed; original in color on left, grayscale result on right  
**Source:** Part18

---

### TC-P2-029
**Category:** UI  
**Test Name:** Image Processing — operation param inputs appear dynamically  
**Steps:**
1. Navigate to Image Processing panel
2. Click "Blur" chip
**Expected Result:** A numeric input for "radius (1–20)" appears below the chip selector  
**Source:** Part18

---

### TC-P2-030
**Category:** UI  
**Test Name:** Image Processing — download button present and functional  
**Steps:**
1. Upload an image, select any operation, click Apply
2. Inspect the result panel for a download button
**Expected Result:** Download button present; clicking it initiates a file download of the processed image as PNG  
**Source:** Part18

---

### TC-P2-031
**Category:** Backend  
**Test Name:** GET /detect-models returns SSD/YOLO model metadata  
**Steps:**
1. `GET <VISION_API>/detect-models`
**Expected Result:** HTTP 200; JSON array containing detection model entry (currently `tiny_yolov3`); each item has `id`, `label`, `classes` fields  
**Source:** Part18, Part20

---

### TC-P2-032
**Category:** Backend  
**Test Name:** POST /detect-objects — confidence filter excludes low-score detections  
**Steps:**
1. Upload a test image
2. `POST <VISION_API>/detect-objects` with `confidence_threshold=0.9` (very high)
**Expected Result:** HTTP 200; `detections` array contains only items with `confidence >= 0.9`; lower-scoring detections absent  
**Source:** Part18

---

### TC-P2-033
**Category:** Backend  
**Test Name:** POST /detect-objects — response includes annotated image  
**Steps:**
1. Upload an image known to contain a person and a car
2. `POST <VISION_API>/detect-objects` with `confidence_threshold=0.3`
**Expected Result:** HTTP 200; `image_b64` field present; `detections` array has entries with `label`, `confidence`, `box` (x1, y1, x2, y2); `count` matches len(detections)  
**Source:** Part18

---

### TC-P2-034
**Category:** Bug-Regression  
**Test Name:** TinyYOLOv3 letterbox preprocessing — aspect-ratio-preserving resize  
**Steps:**
1. Upload a wide landscape image (e.g. 640×300) to Object Detection
2. Submit with `confidence_threshold=0.15`
**Expected Result:** Detections are returned (model does not return zero detections); aspect ratio is not distorted — bounding boxes map to correct pixel positions in original image  
**Source:** Part20 (BUG: simple stretch caused 0 detections; fix: letterbox resize with grey padding)

---

### TC-P2-035
**Category:** Bug-Regression  
**Test Name:** TinyYOLOv3 — indices shape (0,) does not crash  
**Steps:**
1. Upload an image with no detectable objects (e.g. blank white image)
2. `POST <VISION_API>/detect-objects` with `confidence_threshold=0.3`
**Expected Result:** HTTP 200; `count: 0`; `detections: []`; no 500 error  
**Source:** Part20 (BUG: `indices_raw.ndim < 2` edge case caused IndexError)

---

### TC-P2-036
**Category:** Bug-Regression  
**Test Name:** Detection 500 error — all postprocessing wrapped in try/except  
**Steps:**
1. `POST <VISION_API>/detect-objects` with a valid image
**Expected Result:** HTTP 200 or a JSON error response; never HTTP 500 with `{"detail": "Internal Server Error"}` and no usable message  
**Source:** Part20 (BUG: FastAPI default handler masked real exception)

---

### TC-P2-037
**Category:** UI  
**Test Name:** Object Detection — retry loop stops after 3 attempts  
**Steps:**
1. Navigate to Object Detection panel with ml-vision service offline (simulate 503)
2. Observe retry behavior
**Expected Result:** Banner shows "attempt 1/3", "attempt 2/3", "attempt 3/3"; after third failure shows permanent red error; no infinite loop  
**Source:** Part20

---

### TC-P2-038
**Category:** UI  
**Test Name:** Object Detection — Stop button cancels retry countdown  
**Steps:**
1. Trigger a detection request when ml-vision returns 503
2. Click the "Stop" button during the 30-second countdown
**Expected Result:** Countdown clears immediately; no further retry; error state resets  
**Source:** Part20

---

### TC-P2-039
**Category:** UI  
**Test Name:** Object Detection — progress bar shows upload + inference phases  
**Steps:**
1. Upload a moderately large image (>500KB) to Object Detection
2. Click Detect Objects and watch the progress bar
**Expected Result:** Progress bar starts at 0%, advances to ~30% during upload (real XHR events), then animates to ~90% during inference, snaps to 100% on completion  
**Source:** Part20

---

### TC-P2-040
**Category:** UI  
**Test Name:** Object Detection — COCO class browser is searchable  
**Steps:**
1. Navigate to Object Detection panel
2. Click "Browse 80 COCO classes ▸"
3. Type "person" in the search field
**Expected Result:** Browser expands; initial count = 80; after typing "person" the visible list filters to matching entries  
**Source:** Part20

---

### TC-P2-041
**Category:** Backend  
**Test Name:** GET /seg-models returns segmentation model metadata  
**Steps:**
1. `GET <VISION_API>/seg-models`
**Expected Result:** HTTP 200; JSON array includes both `segformer_b0` and `color_segmentation` model entries  
**Source:** Part19, Part22

---

### TC-P2-042
**Category:** Backend  
**Test Name:** POST /segment-image — SegFormer-B0 returns class breakdown  
**Steps:**
1. Upload an outdoor scene photo (person + sky + vegetation)
2. `POST <VISION_API>/segment-image` with `model_name=segformer_b0`
**Expected Result:** HTTP 200; `classes_found` array has entries with `label`, `pixel_count`, `percentage`, `color`; `image_b64` is a valid base64 PNG  
**Source:** Part22

---

### TC-P2-043
**Category:** Backend  
**Test Name:** POST /segment-image — color_segmentation fallback works  
**Steps:**
1. Upload any image
2. `POST <VISION_API>/segment-image` with `model_name=color_segmentation`
**Expected Result:** HTTP 200; `classes_found` array with up to 12 colour-region entries (e.g. "vegetation", "sky/water", "shadow/dark"); valid `image_b64`  
**Source:** Part21, Part22

---

### TC-P2-044
**Category:** Backend  
**Test Name:** POST /segment-image — unknown model returns 400  
**Steps:**
1. `POST <VISION_API>/segment-image` with `model_name=fake_model`
**Expected Result:** HTTP 400; error message references the unknown model  
**Source:** Part19, Part22

---

### TC-P2-045
**Category:** Bug-Regression  
**Test Name:** Shared vision cache — loading segmentation evicts detection model  
**Steps:**
1. `POST <VISION_API>/detect-objects` (loads TinyYOLOv3 into memory)
2. `POST <VISION_API>/segment-image` with `model_name=segformer_b0` (should load SegFormer)
3. `POST <VISION_API>/detect-objects` again
**Expected Result:** All three requests succeed; no OOM error; second call evicts the detection model and loads SegFormer; third call evicts SegFormer and reloads YOLOv3  
**Source:** Part19 (shared `_large_vision_cache` slot prevents two large ONNX models in RAM)

---

### TC-P2-046
**Category:** Bug-Regression  
**Test Name:** xgboost/lightgbm/catboost are lazy-imported (not at startup)  
**Steps:**
1. Deploy or restart the ml-api service
2. Monitor startup memory or check logs
3. Call `GET /health` immediately
**Expected Result:** Service starts in < 512 MB RAM; xgboost/lightgbm/catboost are NOT imported at module level; health check returns 200 without triggering any boosting library imports  
**Source:** Part19 (fix: moved booster imports inside `train_model()`)

---

### TC-P2-047
**Category:** Bug-Regression  
**Test Name:** JS response body stream read once — no "body stream already read" error  
**Steps:**
1. Open browser DevTools console
2. Navigate to Object Detection panel
3. Submit a detection request that returns an error response
**Expected Result:** Console does NOT show "body stream already read" or `TypeError: Failed to execute 'json' on 'Response'` error; error is handled gracefully  
**Source:** Part19 (BUG: `res.json()` consumed stream; catch block tried `res.text()` on same stream)

---

### TC-P2-048
**Category:** Bug-Regression  
**Test Name:** VISION_API defined and used for all vision endpoint calls  
**Steps:**
1. Open browser DevTools Network tab
2. Navigate to `https://ml-unified.onrender.com/?mode=vision`
3. Classify an image, detect objects, segment an image
**Expected Result:** All vision API calls go to the ml-vision service URL (not ml-api URL); no `Uncaught ReferenceError: VISION_API is not defined` in console  
**Source:** Part21 (BUG: `index.html` edits never committed; VISION_API undefined)

---

### TC-P2-049
**Category:** Bug-Regression  
**Test Name:** Server-side ML_VISION_URL injection into HTML  
**Steps:**
1. `GET https://ml-unified.onrender.com/` (raw HTML response)
2. Inspect the HTML source
**Expected Result:** `let VISION_API = 'https://ml-vision.onrender.com';` (or equivalent) is present in the HTML, populated server-side with `ML_VISION_URL` env var; not the empty string `''`  
**Source:** Part21 (fix: `index()` endpoint reads env var and replaces placeholder)

---

### TC-P2-050
**Category:** Bug-Regression  
**Test Name:** CI — secrets context not used in step-level if: condition  
**Steps:**
1. Review `.github/workflows/ci.yml` source
2. Check that no `if: ${{ secrets.* }}` expressions exist at the step level
**Expected Result:** Workflow file is valid; no `Unrecognized named-value: 'secrets'` error; the ml-vision deploy step uses `env:` + shell-level check (`if [ -z "$VISION_HOOK" ]`) instead  
**Source:** Part21

---

### TC-P2-051
**Category:** Bug-Regression  
**Test Name:** Segmentation 503 guard — warmup not complete returns 503 not crash  
**Steps:**
1. Restart ml-vision service
2. Immediately call `POST <VISION_API>/segment-image` (before warmup completes)
**Expected Result:** HTTP 503 with a message indicating the model is warming up; service does NOT crash or return 502  
**Source:** Part21, Part22

---

### TC-P2-052
**Category:** UI  
**Test Name:** Segmentation panel — retry countdown shows 30 seconds  
**Steps:**
1. Trigger segmentation when ml-vision returns 503
2. Observe the retry banner
**Expected Result:** Banner text shows "Auto-retrying in 30s… (attempt 1/3)"; countdown is 30 seconds (not 20); size hint shows "~4.4 MB" (not "~135 MB")  
**Source:** Part22 (fix: countdown corrected from 20s to 30s; size updated from FCN to SegFormer)

---

### TC-P2-053
**Category:** UI  
**Test Name:** Segmentation panel — ADE20K class browser has 150 entries  
**Steps:**
1. Navigate to Image Segmentation panel
2. Click "Browse 150 ADE20K classes ▸"
3. Count visible entries or check rendered count label
**Expected Result:** Browser expands; count shows "150 classes"; entries include "wall", "building", "sky", "person", "car"  
**Source:** Part22

---

### TC-P2-054
**Category:** UI  
**Test Name:** Segmentation panel — ADE20K class browser is searchable  
**Steps:**
1. Open ADE20K class browser in Segmentation panel
2. Type "car" in the search input
**Expected Result:** List filters to show only matching entries; count label updates to "N of 150 matching"  
**Source:** Part22

---

### TC-P2-055
**Category:** UI  
**Test Name:** Segmentation panel — subtitle updated from FCN/VOC to SegFormer/ADE20K  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=vision`
2. Inspect the Image Segmentation sidebar button and panel subtitle
**Expected Result:** Sidebar shows "SegFormer-B0 · ADE20K 150 classes"; panel subtitle does NOT say "FCN-ResNet50 / Pascal VOC 21" anywhere  
**Source:** Part22 (stale text fix)

---

### TC-P2-056
**Category:** Feature  
**Test Name:** ?mode=vision sidebar shows only Vision sections  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=vision`
2. Inspect the sidebar
**Expected Result:** Sidebar shows only Vision items (Image Classifier, Image Processing, Object Detection, Image Segmentation); Supervised/Unsupervised ML sections are hidden  
**Source:** Part22, Part23

---

### TC-P2-057
**Category:** Feature  
**Test Name:** ?mode=ml sidebar shows only ML sections  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=ml`
2. Inspect the sidebar
**Expected Result:** Sidebar shows only Supervised and Unsupervised ML sections; Vision section is hidden; Train button is visible  
**Source:** Part22, Part23

---

### TC-P2-058
**Category:** Feature  
**Test Name:** ?mode=vision changes nav title to "ML Vision"  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=vision`
2. Read the page heading/navbar title
**Expected Result:** Nav title reads "ML Vision"; subtitle reads "Computer Vision Platform"  
**Source:** Part22, Part23

---

### TC-P2-059
**Category:** Feature  
**Test Name:** ?mode=vision default panel is Image Classifier (not Diabetes)  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=vision`
**Expected Result:** Image Classifier panel loads by default; Diabetes prediction form is NOT shown  
**Source:** Part24 (BUG: `init()` always called `selectModel(allModels[0].id)` even in vision mode)

---

### TC-P2-060
**Category:** Bug-Regression  
**Test Name:** Theme does not revert to dark on page refresh  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=vision&theme=light`
2. Confirm light theme is applied
3. Press F5 / Cmd+R to refresh the page
**Expected Result:** Light theme persists after refresh; `?theme=` parameter has been stripped from URL; `localStorage` retains the theme  
**Source:** Part24 (BUG: `?theme=dark` in URL overrode localStorage on every refresh)

---

### TC-P2-061
**Category:** Bug-Regression  
**Test Name:** Theme sync — Portfolio Launch App passes current theme  
**Steps:**
1. Set Portfolio (ml-portfolio-rho.vercel.app) to light theme
2. Click "Launch App" on any project card
**Expected Result:** ML Unified opens with light theme applied; URL contains `?theme=light`; after load the `?theme=` param is stripped from the URL  
**Source:** Part23, Part24

---

### TC-P2-062
**Category:** Bug-Regression  
**Test Name:** Theme sync — ML Unified Portfolio link passes current theme  
**Steps:**
1. Toggle ML Unified to light theme
2. Click the "Portfolio" link in the navbar
**Expected Result:** Portfolio opens with light theme; URL contains `?theme=light`; after load the `?theme=` param is stripped  
**Source:** Part23, Part24

---

### TC-P2-063
**Category:** Feature  
**Test Name:** GET /metrics — ml-api returns valid schema  
**Steps:**
1. `GET https://ml-unified.onrender.com/metrics`
**Expected Result:** HTTP 200; JSON includes `service: "ml-api"`, `uptime_s` (integer), `total_requests` (integer), `avg_ms` (float), `p95_ms` (float), `error_rate` (float), `endpoints` (array)  
**Source:** Part23

---

### TC-P2-064
**Category:** Feature  
**Test Name:** GET /metrics — ml-vision returns valid schema  
**Steps:**
1. `GET <VISION_API>/metrics`
**Expected Result:** HTTP 200; JSON includes `service: "ml-vision"`, same fields as ml-api metrics; `endpoints` contains at least one entry after a vision request  
**Source:** Part23

---

### TC-P2-065
**Category:** Feature  
**Test Name:** Metrics panel — /health and /metrics calls excluded from request log  
**Steps:**
1. Call `GET /health` and `GET /metrics` multiple times on ml-api
2. Check `GET /metrics` response
**Expected Result:** `total_requests` count does NOT include health check or metrics calls; these paths are in `_SKIP_PATHS`  
**Source:** Part23

---

### TC-P2-066
**Category:** Bug-Regression  
**Test Name:** ml-vision favicon.ico excluded from metrics error rate  
**Steps:**
1. Load `https://ml-unified.onrender.com/?mode=vision` in a browser (triggers automatic favicon.ico request to ml-vision)
2. Call `GET <VISION_API>/metrics`
**Expected Result:** `error_rate` is 0.0 (or very low); `/favicon.ico` requests do NOT appear in the error log  
**Source:** Part25 (BUG: browser auto-requested /favicon.ico → 404 → 100% error rate)

---

### TC-P2-067
**Category:** Bug-Regression  
**Test Name:** Metrics panel stats chips do not wrap in light theme  
**Steps:**
1. Toggle to light theme
2. Open Live Metrics panel
3. Resize browser to 1024px wide
**Expected Result:** All 5 stat chips remain on one row; none wraps to a second line (grid layout, not flex-wrap)  
**Source:** Part25 (BUG: `flex-wrap:wrap` caused chips to overflow to new row)

---

### TC-P2-068
**Category:** Feature  
**Test Name:** Metrics panel — mode-specific: ?mode=ml shows only ML Unified  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=ml`
2. Click "Live Metrics" in sidebar
**Expected Result:** Panel shows only "ML UNIFIED" section; ML Vision section is absent  
**Source:** Part25

---

### TC-P2-069
**Category:** Feature  
**Test Name:** Metrics panel — mode-specific: ?mode=vision shows only ML Vision  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=vision`
2. Click "Live Metrics" in sidebar
**Expected Result:** Panel shows only "ML VISION" section; ML Unified section is absent  
**Source:** Part25

---

### TC-P2-070
**Category:** Feature  
**Test Name:** Metrics panel — Details toggle hides/shows endpoint breakdown  
**Steps:**
1. Open Live Metrics panel
2. Observe initial state of endpoint details
3. Click "Details ▾" button
**Expected Result:** Endpoint rows are hidden by default; clicking Details expands them; chevron changes from ▾ to ▴; state persists across 30-second auto-refresh  
**Source:** Part25

---

### TC-P2-071
**Category:** Feature  
**Test Name:** Metrics panel — known items pre-populated before first request  
**Steps:**
1. Open a fresh deployment with no prior requests
2. Open Live Metrics panel and expand Details
**Expected Result:** Known items (Iris, Titanic, Diabetes, Insurance, Training, Clustering for ml; Classifier, Processing, Detection, Segmentation for vision) are all listed, dimmed, with `—` placeholder  
**Source:** Part25

---

### TC-P2-072
**Category:** Feature  
**Test Name:** Metrics panel — internal paths hidden from Details  
**Steps:**
1. Make API calls that trigger `/models`, `/image-models`, `/detect-models`, `/seg-models`
2. Open Live Metrics panel, expand Details
**Expected Result:** `/models`, `/image-models`, `/detect-models`, `/seg-models`, `/imagenet-classes`, `/image-operations` do NOT appear in the Details endpoint list  
**Source:** Part25

---

### TC-P2-073
**Category:** Feature  
**Test Name:** Metrics panel — browser tab title is correct per mode  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=vision` — check browser tab title
2. Navigate to `https://ml-unified.onrender.com/?mode=ml` — check browser tab title
**Expected Result:** vision mode: title = "ML Vision — Computer Vision Platform"; ml mode: title = "ML Unified — Multi-Model Predictor"  
**Source:** Part25 (BUG: title was always "ML Unified" regardless of mode)

---

### TC-P2-074
**Category:** Feature  
**Test Name:** Metrics panel — Raw JSON button opens /metrics in new tab  
**Steps:**
1. Open Live Metrics panel
2. Click the "↗" (Raw JSON) button next to a service name
**Expected Result:** New browser tab opens showing the raw `/metrics` JSON response for that service  
**Source:** Part25

---

### TC-P2-075
**Category:** Feature  
**Test Name:** Metrics panel — pre-fetched on page load, opens instantly  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/`
2. Wait 3 seconds (pre-fetch completes)
3. Click "Live Metrics"
**Expected Result:** Panel opens with data visible immediately; no loading spinner on open (data was pre-fetched on `window load`)  
**Source:** Part25 (BUG: metrics only fetched on panel open causing visible delay)

---
