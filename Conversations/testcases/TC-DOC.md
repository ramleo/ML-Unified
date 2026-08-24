# TC-DOC — Backend API, E2E, and Vision Test Cases

Source: E2E_Test_Documentation.md, Testing_Complete_Guide.md, services/ml-api/README.md  
Total: 75 test cases

---

## E2E / UI Tests

### TC-DOC-001
**Category:** E2E / UI  
**Test Name:** Page title contains "ML"  
**Steps:**
1. Launch the app at `http://localhost:8765`
2. Read the browser tab title

**Expected Result:** Title contains the string "ML"

---

### TC-DOC-002
**Category:** E2E / UI  
**Test Name:** Sidebar shows all four supervised model buttons  
**Steps:**
1. Open app root
2. Check for elements `#btn-iris`, `#btn-titanic`, `#btn-diabetes`, `#btn-insurance`

**Expected Result:** All four elements exist (exactly one each)

---

### TC-DOC-003
**Category:** E2E / UI  
**Test Name:** Sidebar shows unsupervised tool buttons (K-Means, DBSCAN)  
**Steps:**
1. Open app root
2. Wait up to 5s for `#ubtn-kmeans`
3. Wait up to 5s for `#ubtn-dbscan`

**Expected Result:** Both elements are present in the DOM

---

### TC-DOC-004
**Category:** E2E / UI  
**Test Name:** EDA and Clean buttons appear in `?mode=eda`  
**Steps:**
1. Navigate to `/?mode=eda`
2. Wait up to 8s for `#ebtn-eda`
3. Wait up to 5s for `#ebtn-clean`

**Expected Result:** Both buttons are rendered (only when `APP_MODE === 'eda'`)

---

### TC-DOC-005
**Category:** E2E / UI  
**Test Name:** Empty state is visible before model selection  
**Steps:**
1. Open app root (no model clicked)
2. Assert `#emptyState` count == 1
3. Assert `#emptyState` is visible

**Expected Result:** Empty-state prompt is visible and present in DOM

---

### TC-DOC-006
**Category:** E2E / UI  
**Test Name:** Iris prediction returns non-empty result panel  
**Steps:**
1. Click `#btn-iris`, wait for `activeModel.id === 'iris'`
2. Fill: `SepalLengthCm=5.1`, `SepalWidthCm=3.5`, `PetalLengthCm=1.4`, `PetalWidthCm=0.2`
3. Click `#predictBtn`
4. Wait up to 15s for `#resultState` to be visible
5. Read `#resultBody` inner text

**Expected Result:** `#resultBody` inner text is not empty

---

### TC-DOC-007
**Category:** E2E / UI  
**Test Name:** Iris prediction result contains a valid species name  
**Steps:**
1–4. Same as TC-DOC-006
5. Read `#resultBody` inner text

**Expected Result:** Text contains one of: `Setosa`, `Versicolor`, `Virginica`

---

### TC-DOC-008
**Category:** E2E / UI  
**Test Name:** SHAP panel completes after iris prediction  
**Steps:**
1. Select iris model, fill Setosa sample values, click predict
2. Wait up to 15s for `#resultState` visible
3. Wait up to 30s for either `.shap-bar-fill` or `.shap-loading` inside `#shapBody`
4. Assert `#shapPanel` is visible

**Expected Result:** `#shapPanel` is visible and SHAP is either rendering bars or still loading — not absent

---

### TC-DOC-009
**Category:** E2E / UI  
**Test Name:** Titanic prediction returns a survival result  
**Steps:**
1. Click `#btn-titanic`, wait for `activeModel.id === 'titanic'`
2. Select: `Pclass=3`, `Sex=male`, `Embarked=S`
3. Fill: `Age=22`, `SibSp=1`, `Parch=0`, `Fare=7.25`
4. Click `#predictBtn`
5. Wait up to 15s for `#resultState` visible

**Expected Result:** Result body contains one of: `Survived`, `Did not survive`, `0`, `1`

---

### TC-DOC-010
**Category:** E2E / UI  
**Test Name:** Diabetes prediction returns non-empty result panel  
**Steps:**
1. Click `#btn-diabetes`, wait for `activeModel.id === 'diabetes'`
2. Fill: `Pregnancies=6`, `Glucose=148`, `BloodPressure=72`, `SkinThickness=35`, `Insulin=0`, `BMI=33.6`, `DiabetesPedigreeFunction=0.627`, `Age=50`
3. Click `#predictBtn`
4. Wait up to 15s for `#resultState` visible

**Expected Result:** `#resultBody` inner text is not empty

---

### TC-DOC-011
**Category:** E2E / UI  
**Test Name:** Out-of-range field value triggers validation error  
**Steps:**
1. Select diabetes model
2. Enter a value outside the schema `[min, max]` range in any number input
3. Click `#predictBtn`

**Expected Result:** A "Please fill in all fields" validation error is shown; no prediction made

---

### TC-DOC-012
**Category:** E2E / UI  
**Test Name:** Drift tab opens and drift view is visible  
**Steps:**
1. Select iris model, wait for `activeModel.id === 'iris'`
2. Click `#tabDrift`
3. Wait up to 8s for `#driftBody`
4. Assert `#driftView` visible

**Expected Result:** Drift view panel is displayed

---

### TC-DOC-013
**Category:** E2E / Data  
**Test Name:** Uploading iris CSV to drift panel renders metrics  
**Steps:**
1. Open drift tab for iris model
2. Call `_switchDriftMode('upload')` via JS, wait for `#driftUploadZone`
3. Set `iris.csv` on `#driftFileInput`
4. Wait up to 20s for `#driftBody` text to contain `OVERALL DRIFT` or `Could not analyse`

**Expected Result:** `#driftBody` inner text is not empty

---

### TC-DOC-014
**Category:** E2E / Data  
**Test Name:** Drift result includes iris column names  
**Steps:**
1–4. Same as TC-DOC-013
5. Assert `Could not analyse` is NOT in result body
6. Assert at least one of `Sepal`, `Petal`, `SepalLength`, `PetalLength` appears

**Expected Result:** Drift result body contains iris column name(s)

---

### TC-DOC-015
**Category:** E2E / UI  
**Test Name:** Clean & Export panel opens on button click  
**Steps:**
1. Navigate to `/?mode=eda`
2. Click `#ebtn-clean`
3. Wait up to 8s for `#cleanOptions`

**Expected Result:** `#cleanOptions` is visible  
**Note:** Skip unless `ML_EDA_URL` is set

---

### TC-DOC-016
**Category:** E2E / Data  
**Test Name:** Uploading CSV to Clean & Export renders all option sections  
**Steps:**
1. Open Clean & Export panel
2. Click `#cleanOptions` to open file chooser, set `iris.csv`
3. Wait up to 30s for `.shap-header` inside `#cleanOptions`
4. Assert `#cleanOptions` inner text contains: `Duplicate rows`, `Columns to drop`, `Missing value`, `Outlier`, `Power transform`

**Expected Result:** All five cleaning-option section labels are present  
**Note:** Skip unless `ML_EDA_URL` is set

---

### TC-DOC-017
**Category:** E2E / UI  
**Test Name:** Clean & Export panel title is correct after upload  
**Steps:**
1. Open Clean & Export panel, upload `iris.csv`
2. Wait for `.shap-header` inside `#cleanOptions`
3. Read `.shap-title` text

**Expected Result:** `.shap-title` text equals `"🧹 Clean & Export"`

---

### TC-DOC-018
**Category:** E2E / Data  
**Test Name:** Submitting clean form triggers CSV file download  
**Steps:**
1. Open Clean & Export panel, upload `iris.csv`
2. Wait for options to render
3. Click `#sc-submit` while listening for download event

**Expected Result:** Downloaded file suggested filename ends with `.csv`  
**Note:** Skip unless `ML_EDA_URL` is set

---

### TC-DOC-067
**Category:** E2E / UI  
**Test Name:** Insurance model prediction returns a result  
**Steps:**
1. Click `#btn-insurance`, wait for `activeModel.id === 'insurance'`
2. Fill valid insurance feature values
3. Click `#predictBtn`
4. Wait up to 15s for `#resultState` visible

**Expected Result:** `#resultBody` inner text is not empty  
**Note:** Coverage gap — insurance has no E2E coverage currently

---

### TC-DOC-068
**Category:** E2E / UI  
**Test Name:** K-Means clustering UI renders results  
**Steps:**
1. Click `#ubtn-kmeans`
2. Upload or provide a clustering dataset
3. Run clustering

**Expected Result:** Clustering result plot or stats are displayed  
**Note:** Coverage gap — no UI coverage for clustering tab

---

### TC-DOC-069
**Category:** E2E / UI  
**Test Name:** SHAP bars actually render (not just spinner)  
**Steps:**
1. Select iris model, fill Setosa sample, click predict
2. Wait for `#resultState` visible
3. Wait up to 30s specifically for `.shap-bar-fill` inside `#shapBody`

**Expected Result:** `.shap-bar-fill` elements are present — spinner alone must NOT be accepted as passing

---

### TC-DOC-070
**Category:** E2E / UI  
**Test Name:** Predicting on nonexistent model shows error in UI  
**Steps:**
1. Trigger a prediction for a model ID that does not exist (via manipulated JS call)

**Expected Result:** UI shows an error state — no crash, no blank screen

---

### TC-DOC-071
**Category:** E2E / UI  
**Test Name:** Submitting empty form fields shows validation error  
**Steps:**
1. Select any model
2. Leave one or more required fields empty
3. Click `#predictBtn`

**Expected Result:** A validation error message is displayed; prediction is not sent

---

### TC-DOC-072
**Category:** E2E / UI  
**Test Name:** App behaves gracefully when backend server is unreachable  
**Steps:**
1. Stop the ml-api server
2. Open the app
3. Attempt to load models or make a prediction

**Expected Result:** App displays a meaningful error state — no crash, no blank white page

---

### TC-DOC-073
**Category:** Backend API  
**Test Name:** Predict API responds within 500ms  
**Steps:**
1. POST `/predict/iris` with valid features
2. Measure response time

**Expected Result:** Response received in under 500ms  
**Note:** Performance baseline

---

### TC-DOC-074
**Category:** Backend API / E2E  
**Test Name:** JS form field names match API schema field names  
**Steps:**
1. GET `/schemas/<model_id>` and collect field names from `fields` array
2. Inspect rendered form inputs and collect their `name` attributes

**Expected Result:** Every field name in the API schema has a matching `name` attribute in the DOM form; no mismatches

---

### TC-DOC-075
**Category:** E2E / UI  
**Test Name:** Auto-selected model on load is `diabetes`  
**Steps:**
1. Open app root at `http://localhost:8765`
2. Evaluate `activeModel?.id` in the browser

**Expected Result:** `activeModel.id` equals `"diabetes"` without any user interaction

---

## Backend API Tests

### TC-DOC-019
**Category:** Backend API  
**Test Name:** `/metrics` returns valid structure on fresh service  
**Steps:**
1. Start a fresh TestClient with the app
2. GET `/metrics`

**Expected Result:** Response contains `service name`, `uptime`, `error rate`, and `endpoints` list

---

### TC-DOC-020
**Category:** Backend API  
**Test Name:** `/metrics` records requests after a call to `/models`  
**Steps:**
1. Call GET `/models`
2. Call GET `/metrics`

**Expected Result:** The metrics log reflects the `/models` request

---

### TC-DOC-021
**Category:** Backend API  
**Test Name:** `/health` returns ok status with at least 4 models loaded  
**Steps:**
1. GET `/health`

**Expected Result:** Response has `status: ok` and a `models` list with at least 4 entries

---

### TC-DOC-022
**Category:** Backend API  
**Test Name:** `/app-config` returns default response containing `vision_url`  
**Steps:**
1. GET `/app-config` (no env var set)

**Expected Result:** Response body contains `vision_url` key

---

### TC-DOC-023
**Category:** Backend API  
**Test Name:** `/app-config` reflects `ML_VISION_URL` env var  
**Steps:**
1. Set `ML_VISION_URL` environment variable to a custom URL
2. GET `/app-config`

**Expected Result:** Response `vision_url` value matches the env var

---

### TC-DOC-024
**Category:** Backend API  
**Test Name:** `/models` lists all four supervised models  
**Steps:**
1. GET `/models`

**Expected Result:** Response list contains entries for `iris`, `titanic`, `diabetes`, `insurance`

---

### TC-DOC-025
**Category:** Backend API  
**Test Name:** Each model entry has required metadata fields  
**Steps:**
1. GET `/models`
2. Inspect each model object

**Expected Result:** Each entry has `title`, `task`, `accent`, `metric` fields

---

### TC-DOC-026
**Category:** Backend API  
**Test Name:** `/schemas/iris` returns correct schema structure  
**Steps:**
1. GET `/schemas/iris`

**Expected Result:** Response has `id`, `task=classification`, 4 fields, and a `sample`

---

### TC-DOC-027
**Category:** Backend API  
**Test Name:** `/schemas/insurance` returns regression schema  
**Steps:**
1. GET `/schemas/insurance`

**Expected Result:** Response has `task=regression` and a `fields` list

---

### TC-DOC-028
**Category:** Backend API  
**Test Name:** `/schemas/nonexistent` returns HTTP 404  
**Steps:**
1. GET `/schemas/nonexistent`

**Expected Result:** HTTP 404 response

---

### TC-DOC-029
**Category:** Backend API  
**Test Name:** Iris prediction returns class probabilities summing to 1.0  
**Steps:**
1. POST `/predict/iris` with valid Setosa feature values

**Expected Result:** Response has `prediction` and `probabilities` (3 values that sum to 1.0)

---

### TC-DOC-030
**Category:** Backend API  
**Test Name:** Iris prediction label is a valid species name  
**Steps:**
1. POST `/predict/iris` with Virginica sample feature values

**Expected Result:** `prediction` value is one of: `Iris-setosa`, `Iris-versicolor`, `Iris-virginica`

---

### TC-DOC-031
**Category:** Backend API  
**Test Name:** Titanic prediction returns prediction and probabilities  
**Steps:**
1. POST `/predict/titanic` with valid passenger features

**Expected Result:** Response has `prediction` and `probabilities` keys

---

### TC-DOC-032
**Category:** Backend API  
**Test Name:** Diabetes prediction returns a prediction key  
**Steps:**
1. POST `/predict/diabetes` with valid diabetes feature values

**Expected Result:** Response contains `prediction` key

---

### TC-DOC-033
**Category:** Backend API  
**Test Name:** Insurance prediction returns a positive float  
**Steps:**
1. POST `/predict/insurance` with valid insurance features

**Expected Result:** `prediction` value is a positive float

---

### TC-DOC-034
**Category:** Backend API  
**Test Name:** Predicting on nonexistent model returns HTTP 404  
**Steps:**
1. POST `/predict/nonexistent_model` with any payload

**Expected Result:** HTTP 404 response

---

### TC-DOC-035
**Category:** Backend API / Data  
**Test Name:** CSV upload with binary target suggests classification  
**Steps:**
1. POST to CSV analysis endpoint with a CSV whose target column has binary values

**Expected Result:** Response `suggested_task` equals `"classification"`

---

### TC-DOC-036
**Category:** Backend API / Data  
**Test Name:** CSV upload with continuous float target suggests regression  
**Steps:**
1. POST to CSV analysis endpoint with a CSV whose target column has continuous float values

**Expected Result:** Response `suggested_task` equals `"regression"`

---

### TC-DOC-037
**Category:** Backend API / Data  
**Test Name:** CSV analysis endpoint handles garbage bytes gracefully  
**Steps:**
1. POST garbage/invalid bytes to the CSV analysis endpoint

**Expected Result:** Response is HTTP 200 or HTTP 400 — no crash or 500 error

---

### TC-DOC-038
**Category:** Backend API  
**Test Name:** K-Means clustering returns plot_data and stats with correct cluster count  
**Steps:**
1. POST to unsupervised endpoint with a 3-cluster CSV and `algorithm=kmeans`, `n_clusters=3`
2. Parse SSE response stream

**Expected Result:** Response has `plot_data` and `stats.n_clusters == 3`

---

### TC-DOC-039
**Category:** Backend API  
**Test Name:** PCA returns plot_data  
**Steps:**
1. POST to unsupervised endpoint with `algorithm=pca`
2. Parse SSE response stream

**Expected Result:** Response contains `plot_data`

---

### TC-DOC-040
**Category:** Backend API  
**Test Name:** DBSCAN returns plot_data  
**Steps:**
1. POST to unsupervised endpoint with `algorithm=dbscan`
2. Parse SSE response stream

**Expected Result:** Response contains `plot_data`

---

### TC-DOC-041
**Category:** Backend API  
**Test Name:** Training a classifier creates a usable model  
**Steps:**
1. POST to `/train` with a classification CSV and `task=classification`
2. GET `/models` — verify new model ID appears
3. POST `/predict/<new_model_id>` with a sample row
4. DELETE or clean up the model

**Expected Result:** Model is listed after training; prediction returns a result; model is removed during cleanup

---

### TC-DOC-042
**Category:** Backend API  
**Test Name:** Training a regressor uses MAE metric  
**Steps:**
1. POST to `/train` with a regression CSV and `task=regression`
2. Check returned metadata — confirm `metric` label is `"MAE"`
3. POST `/predict/<new_model_id>` with a sample row

**Expected Result:** Metric is "MAE"; prediction value is a float

---

### TC-DOC-043
**Category:** Backend API  
**Test Name:** Training with `task=invalid_task` returns HTTP 400  
**Steps:**
1. POST to `/train` with a valid CSV and `task=invalid_task`

**Expected Result:** HTTP 400 response

---

### TC-DOC-044
**Category:** Backend API  
**Test Name:** Training with nonexistent target column returns HTTP 400  
**Steps:**
1. POST to `/train` with a valid CSV and a `target` column name not in the CSV

**Expected Result:** HTTP 400 response

---

## Backend API / Vision Tests

### TC-DOC-045
**Category:** Backend API / Vision  
**Test Name:** Vision `/health` returns ok status and correct service name  
**Steps:**
1. GET `/health` on the ml-vision service

**Expected Result:** Response has `status: ok` and `service: ml-vision`

---

### TC-DOC-046
**Category:** Backend API / Vision  
**Test Name:** Vision `/metrics` returns valid structure  
**Steps:**
1. GET `/metrics` on ml-vision

**Expected Result:** Response contains `uptime`, `avg_ms`, `p95_ms`, `error_rate`

---

### TC-DOC-047
**Category:** Backend API / Vision  
**Test Name:** Vision `/metrics` records requests made to the service  
**Steps:**
1. Make any request to ml-vision
2. GET `/metrics`

**Expected Result:** Metrics log reflects the prior request

---

### TC-DOC-048
**Category:** Backend API / Vision  
**Test Name:** `/image-models` lists required image classification models  
**Steps:**
1. GET `/image-models`

**Expected Result:** Response lists `mobilenetv2`, `resnet50`, `squeezenet`, `googlenet` with required fields

---

### TC-DOC-049
**Category:** Backend API / Vision  
**Test Name:** `/imagenet-classes` returns classes list with matching total count  
**Steps:**
1. GET `/imagenet-classes`

**Expected Result:** `total == len(classes)` in response

---

### TC-DOC-050
**Category:** Backend API / Vision  
**Test Name:** Classifying image with unknown model name returns HTTP 400  
**Steps:**
1. POST to image classification endpoint with `model=unknown_model`

**Expected Result:** HTTP 400 response

---

### TC-DOC-051
**Category:** Backend API / Vision  
**Test Name:** Image classification returns correct top prediction at high confidence  
**Steps:**
1. Mock ONNX session to return logits for class 207 (golden retriever)
2. POST a test image to the classify endpoint

**Expected Result:** Top prediction is "golden retriever" with confidence > 99%

---

### TC-DOC-052
**Category:** Backend API / Vision  
**Test Name:** Flat logits trigger `low_confidence` flag  
**Steps:**
1. Mock ONNX to return equal logits across all classes
2. POST a test image to the classify endpoint

**Expected Result:** Response has `low_confidence: true`

---

### TC-DOC-053
**Category:** Backend API / Vision  
**Test Name:** `/image-operations` lists all expected operations with metadata  
**Steps:**
1. GET `/image-operations`

**Expected Result:** Response lists `grayscale`, `blur`, `sharpen`, `edges`, `rotate` — each with `id`, `label`, `params`

---

### TC-DOC-054
**Category:** Backend API / Vision  
**Test Name:** Grayscale operation returns valid base64 PNG with correct dimensions  
**Steps:**
1. POST a test image to the process endpoint with `operation=grayscale`

**Expected Result:** Response includes a valid base64-encoded PNG with unchanged dimensions

---

### TC-DOC-055
**Category:** Backend API / Vision  
**Test Name:** Blur operation includes `radius` in `params_used`  
**Steps:**
1. POST a test image to the process endpoint with `operation=blur`

**Expected Result:** Response `params_used` contains `radius`

---

### TC-DOC-056
**Category:** Backend API / Vision  
**Test Name:** 90-degree rotation of 64×32 image produces 32×64 output  
**Steps:**
1. POST a 64×32 test image with `operation=rotate`, `angle=90`

**Expected Result:** Output image dimensions are 32×64

---

### TC-DOC-057
**Category:** Backend API / Vision  
**Test Name:** Unknown image processing operation returns HTTP 400  
**Steps:**
1. POST a test image with `operation=unknown_operation`

**Expected Result:** HTTP 400 response

---

### TC-DOC-058
**Category:** Backend API / Vision  
**Test Name:** `/detect-models` lists tiny_yolov3 with required fields  
**Steps:**
1. GET `/detect-models`

**Expected Result:** Response includes `tiny_yolov3` entry with required metadata fields

---

### TC-DOC-059
**Category:** Backend API / Vision  
**Test Name:** Object detection with unknown model returns HTTP 400  
**Steps:**
1. POST to object detection endpoint with `model=unknown_model`

**Expected Result:** HTTP 400 response

---

### TC-DOC-060
**Category:** Backend API / Vision  
**Test Name:** Object detection inference returns one "person" box at 95% confidence  
**Steps:**
1. Mock ONNX to return one detection for "person" at 95% confidence
2. POST a test image to the detect endpoint

**Expected Result:** Response has `count=1`, `image_b64` set, and a box for "person" with ~95% confidence and valid coordinates

---

### TC-DOC-061
**Category:** Backend API / Vision  
**Test Name:** Confidence threshold filters low-confidence detections  
**Steps:**
1. Mock ONNX to return two detections: one at 0.9 confidence, one at 0.2 confidence
2. POST with `threshold=0.5`

**Expected Result:** Only the 0.9-confidence detection is returned (`count=1`)

---

### TC-DOC-062
**Category:** Backend API / Vision  
**Test Name:** `/seg-models` lists at least 2 models  
**Steps:**
1. GET `/seg-models`

**Expected Result:** Response has at least 2 models; `segformer_b0` and `color_segmentation` are present

---

### TC-DOC-063
**Category:** Backend API / Vision  
**Test Name:** Colour segmentation returns valid base64 image and classes  
**Steps:**
1. POST a test image to the segment endpoint with `model=color_segmentation`

**Expected Result:** Response has a valid base64 image and `classes` list where each item has a percentage

---

### TC-DOC-064
**Category:** Backend API / Vision  
**Test Name:** Uniform-colour image produces at least one colour region  
**Steps:**
1. POST a uniform single-colour image to the segment endpoint with `model=color_segmentation`

**Expected Result:** `classes` list has at least one entry

---

### TC-DOC-065
**Category:** Backend API / Vision  
**Test Name:** Segmentation with unknown model returns HTTP 400  
**Steps:**
1. POST a test image to the segment endpoint with `model=unknown_model`

**Expected Result:** HTTP 400 response

---

### TC-DOC-066
**Category:** Backend API / Vision  
**Test Name:** SegFormer inference with class 2 dominant returns "sky" in classes_found  
**Steps:**
1. Mock ONNX to return class 2 as the dominant class
2. POST a test image to the segment endpoint with `model=segformer_b0`

**Expected Result:** `classes_found` contains `"sky"`
