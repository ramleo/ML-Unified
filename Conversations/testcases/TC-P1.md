# TC-P1 — Parts 1–15 Test Cases

Source: Conversation Parts 1–15 (2026-06-01 through 2026-06-04)
Total: 92 test cases
Tokens used: ~52,416 | Duration: ~242s

---

### TC-P1-001
**Category:** Backend API
**Test Name:** Health endpoint returns status and loaded model list
**Steps:**
1. Send `GET /health` to ml-api
**Expected Result:** `200 OK` with JSON body `{ "status": "ok", "models": [...] }` — at minimum iris, titanic, diabetes, insurance entries present
**Automation Hint:** `pytest` + `httpx.AsyncClient`; assert `resp.status_code == 200` and `len(resp.json()["models"]) >= 4`
**Source:** Part15

---

### TC-P1-002
**Category:** Backend API
**Test Name:** `/models` lists all registered models with required fields
**Steps:**
1. Send `GET /models`
**Expected Result:** JSON array where each item contains `id`, `title`, `task`, `accent`; at minimum ids `iris`, `titanic`, `diabetes`, `insurance` are present
**Automation Hint:** `pytest`; assert every item has all 4 keys; assert `{m["id"] for m in resp.json()} >= {"iris","titanic","diabetes","insurance"}`
**Source:** Part12, Part15

---

### TC-P1-003
**Category:** Backend API
**Test Name:** `/schemas/{model_id}` returns full schema for iris
**Steps:**
1. Send `GET /schemas/iris`
**Expected Result:** `200 OK` with JSON containing `fields` array (4 items), `sample` object with 4 keys, `output.type == "classification"`, `output.class_names` non-empty
**Automation Hint:** `pytest`; assert `len(resp.json()["fields"]) == 4`; assert `resp.json()["output"]["type"] == "classification"`
**Source:** Part12, Part15

---

### TC-P1-004
**Category:** Backend API
**Test Name:** `/schemas/{model_id}` returns full schema for insurance
**Steps:**
1. Send `GET /schemas/insurance`
**Expected Result:** `200 OK` with JSON containing `output.type == "regression"`, `output.target_col == "Premium Amount"`, `ensure_cols` list including `psd_year` etc.
**Automation Hint:** `pytest`; assert `resp.json()["output"]["target_col"] == "Premium Amount"`; assert `"psd_year" in resp.json()["ensure_cols"]`
**Source:** Part12, Part15

---

### TC-P1-005
**Category:** Backend API
**Test Name:** `/schemas/{model_id}` returns 404 for unknown model
**Steps:**
1. Send `GET /schemas/nonexistent_model_xyz`
**Expected Result:** `404 Not Found`
**Automation Hint:** `pytest`; assert `resp.status_code == 404`
**Source:** Part15

---

### TC-P1-006
**Category:** Backend API
**Test Name:** Iris classification — predict Iris-setosa sample
**Steps:**
1. Send `POST /predict/iris` with body `{"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2}`
**Expected Result:** `200 OK`; `prediction` is `"Iris-setosa"` (or index 0); `probabilities` present with setosa confidence >= 0.95
**Automation Hint:** `pytest`; `assert "setosa" in str(resp.json()["prediction"]).lower()`
**Source:** Part9, Part15

---

### TC-P1-007
**Category:** Backend API
**Test Name:** Iris classification — predict Iris-virginica sample
**Steps:**
1. Send `POST /predict/iris` with body `{"sepal_length": 6.3, "sepal_width": 3.3, "petal_length": 6.0, "petal_width": 2.5}`
**Expected Result:** Prediction resolves to `"Iris-virginica"`
**Automation Hint:** `pytest`; `assert "virginica" in str(resp.json()["prediction"]).lower()`
**Source:** Part15

---

### TC-P1-008
**Category:** Backend API
**Test Name:** Titanic classification — female 1st class predicts Survived
**Steps:**
1. Send `POST /predict/titanic` with body `{"Pclass": 1, "Sex": "female", "Age": 38, "SibSp": 1, "Parch": 0, "Fare": 71.28, "Embarked": "C"}`
**Expected Result:** `prediction` is `1` or `"Survived"`; confidence >= 0.80
**Automation Hint:** `pytest`; assert predicted class label contains "survived" (case-insensitive)
**Source:** Part9, Part15

---

### TC-P1-009
**Category:** Backend API
**Test Name:** Diabetes classification — low-risk sample predicts Non-Diabetic
**Steps:**
1. Send `POST /predict/diabetes` with body `{"Pregnancies": 1, "Glucose": 89, "BloodPressure": 66, "SkinThickness": 23, "Insulin": 94, "BMI": 28.1, "DiabetesPedigreeFunction": 0.167, "Age": 21}`
**Expected Result:** `prediction` resolves to `"Non-Diabetic"` or `0`
**Automation Hint:** `pytest`; assert `str(resp.json()["prediction"]).lower()` contains "non" or equals `"0"`
**Source:** Part9, Part15

---

### TC-P1-010
**Category:** Backend API
**Test Name:** Insurance regression — sample returns numeric premium
**Steps:**
1. Send `POST /predict/insurance` with a valid JSON payload containing all required fields
**Expected Result:** `200 OK`; `prediction` is a positive float; no `probabilities` key in response
**Automation Hint:** `pytest`; `assert isinstance(resp.json()["prediction"], (int, float))` and `resp.json()["prediction"] > 0`
**Source:** Part15

---

### TC-P1-011
**Category:** Bug-Regression
**Test Name:** POST /predict returns 200 not 404 (Body() vs Request.json() fix)
**Steps:**
1. Send `POST /predict/iris` with a valid JSON payload `{"sepal_length": 5.1, ...}`
**Expected Result:** `200 OK` — never `404`
**Automation Hint:** `pytest`; assert `resp.status_code == 200` not `404`
**Source:** Part12

---

### TC-P1-012
**Category:** Backend API
**Test Name:** `/predict/{model_id}` returns 404 for unknown model
**Steps:**
1. Send `POST /predict/does_not_exist` with any JSON body
**Expected Result:** `404 Not Found`
**Automation Hint:** `pytest`; assert `resp.status_code == 404`
**Source:** Part15

---

### TC-P1-013
**Category:** Backend API
**Test Name:** `/analyze` CSV endpoint detects classification dataset correctly
**Steps:**
1. Upload Iris CSV to `POST /analyze`
**Expected Result:** Response includes `columns` list, `suggested_target`, and `task_type == "classification"`
**Automation Hint:** `pytest`; open iris CSV as bytes, post as multipart; assert `resp.json()["task_type"] == "classification"`
**Source:** Part15

---

### TC-P1-014
**Category:** Backend API
**Test Name:** `/analyze` CSV endpoint detects regression dataset correctly
**Steps:**
1. Upload Insurance CSV to `POST /analyze`
**Expected Result:** `task_type == "regression"` suggested
**Automation Hint:** `pytest`; assert `resp.json()["task_type"] == "regression"`
**Source:** Part15

---

### TC-P1-015
**Category:** Backend API
**Test Name:** `/analyze` returns error for non-CSV file
**Steps:**
1. Upload a `.txt` or `.jpg` file to `POST /analyze`
**Expected Result:** `400` or `422` error — not a server crash
**Automation Hint:** `pytest`; assert `resp.status_code in (400, 422)`
**Source:** Part15

---

### TC-P1-016
**Category:** Backend API
**Test Name:** `/unsupervised` K-Means returns clusters and silhouette score
**Steps:**
1. Send `POST /unsupervised` with algorithm `"K-Means"`, n_clusters `3`, upload `test_clusters.csv`
**Expected Result:** Response contains `plot_data` with 3 distinct cluster IDs; `stats.n_clusters == 3`; `stats.silhouette > 0`
**Automation Hint:** `pytest`; assert `resp.json()["stats"]["n_clusters"] == 3`
**Source:** Part15

---

### TC-P1-017
**Category:** Backend API
**Test Name:** `/unsupervised` PCA returns 2D plot data
**Steps:**
1. Send `POST /unsupervised` with algorithm `"PCA"`, n_dims `2`, upload any numeric CSV
**Expected Result:** `plot_data` list with `x`, `y` per point; `stats` contains `variance_pc1` and `variance_pc2`
**Automation Hint:** `pytest`; assert `"x" in resp.json()["plot_data"][0]`; assert `"variance_pc1" in resp.json()["stats"]`
**Source:** Part15

---

### TC-P1-018
**Category:** Bug-Regression
**Test Name:** DBSCAN on default eps returns non-zero clusters for test_clusters.csv (PCA-space fix)
**Steps:**
1. Send `POST /unsupervised` with algorithm `"DBSCAN"`, eps `0.5`, min_samples `3`, upload `test_clusters.csv`
**Expected Result:** `stats.n_clusters == 3` — NOT `0`
**Automation Hint:** `pytest`; assert `resp.json()["stats"]["n_clusters"] == 3`; regression guard against returning `0`
**Source:** Part14

---

### TC-P1-019
**Category:** Backend API
**Test Name:** `/unsupervised` DBSCAN returns n_clusters and n_noise stats
**Steps:**
1. Send `POST /unsupervised` with algorithm `"DBSCAN"` and any numeric CSV
**Expected Result:** Response `stats` object contains both `n_clusters` and `n_noise` integer fields
**Automation Hint:** `pytest`; assert `"n_clusters" in resp.json()["stats"]` and `"n_noise" in resp.json()["stats"]`
**Source:** Part14, Part15

---

### TC-P1-020
**Category:** Backend API
**Test Name:** `/train` endpoint registers new model and returns accuracy/MAE
**Steps:**
1. Upload a CSV with a classification target to `POST /train` with `model_name`, `target_col`, `task_type=classification`, `algorithm=Random Forest`
2. Call `GET /models`
**Expected Result:** Step 1 returns `{ "accuracy": <float>, "model_id": <str> }`; Step 2 shows newly registered model
**Automation Hint:** `pytest`; assert new model id appears in `/models` response after training
**Source:** Part12

---

### TC-P1-021
**Category:** Bug-Regression
**Test Name:** `/train` sets `output.target_col` in auto-generated schema
**Steps:**
1. Train a model via `POST /train` with `target_col = "MyTarget"`
2. Retrieve `GET /schemas/{model_id}`
**Expected Result:** Schema `output.target_col == "MyTarget"` — never missing or hardcoded
**Automation Hint:** `pytest`; assert `resp.json()["output"]["target_col"] == "MyTarget"`
**Source:** Part12

---

### TC-P1-022
**Category:** Bug-Regression
**Test Name:** `/metrics` endpoint returns `algorithm` field (not "—")
**Steps:**
1. Send `GET /metrics` for any trained model
**Expected Result:** JSON includes `"algorithm"` key with a non-empty string (e.g. `"XGBoost"`, `"Random Forest"`)
**Automation Hint:** `pytest`; assert `resp.json().get("algorithm") not in (None, "", "—")`
**Source:** Part5

---

### TC-P1-023
**Category:** Bug-Regression
**Test Name:** Classification models write `metrics.json` with task, algorithm, target, accuracy, classes
**Steps:**
1. Train a classification pipeline
2. Read `models/metrics.json`
**Expected Result:** JSON contains `task`, `algorithm`, `target`, `accuracy`, `classes` — none missing
**Automation Hint:** `pytest`; assert `set(["task","algorithm","target","accuracy","classes"]).issubset(set(data.keys()))`
**Source:** Part6

---

### TC-P1-024
**Category:** Backend API
**Test Name:** `/` (root) route returns `Cache-Control: no-cache` header
**Steps:**
1. Send `GET /` to the ML-Unified backend
**Expected Result:** Response header includes `Cache-Control: no-cache, no-store, must-revalidate`
**Automation Hint:** `pytest`; assert `"no-cache" in resp.headers.get("cache-control", "")`
**Source:** Part12

---

### TC-P1-025
**Category:** Bug-Regression
**Test Name:** Titanic schema includes `ensure_cols` with Name and Ticket
**Steps:**
1. Send `GET /schemas/titanic`
**Expected Result:** Response JSON has `"ensure_cols"` field containing at least `["Name", "Ticket"]`
**Automation Hint:** `pytest`; assert `"Name" in resp.json()["ensure_cols"]` and `"Ticket" in resp.json()["ensure_cols"]`
**Source:** Part12

---

### TC-P1-026
**Category:** Bug-Regression
**Test Name:** Insurance schema includes `ensure_cols` with psd_* date columns
**Steps:**
1. Send `GET /schemas/insurance`
**Expected Result:** `ensure_cols` contains `"psd_year"`, `"psd_month"`, `"psd_day"`, `"psd_day_of_week"`, `"Customer Feedback"`
**Automation Hint:** `pytest`; assert all expected keys in `resp.json()["ensure_cols"]`
**Source:** Part12

---

### TC-P1-027
**Category:** Backend API
**Test Name:** XGBoost algorithm available for classification training
**Steps:**
1. Send `POST /train` with `algorithm = "XGBoost"`, `task_type = "classification"`, and a valid CSV
**Expected Result:** Training succeeds; `accuracy` returned; model registered in sidebar
**Automation Hint:** `pytest`; assert `resp.status_code == 200` and `"accuracy" in resp.json()`
**Source:** Part13

---

### TC-P1-028
**Category:** Backend API
**Test Name:** LightGBM algorithm available for regression training
**Steps:**
1. Send `POST /train` with `algorithm = "LightGBM"`, `task_type = "regression"`, and a numeric CSV
**Expected Result:** Training succeeds; `mae` or equivalent metric returned
**Automation Hint:** `pytest`; assert `resp.status_code == 200`
**Source:** Part13

---

### TC-P1-029
**Category:** Backend API
**Test Name:** CatBoost algorithm available for classification training
**Steps:**
1. Send `POST /train` with `algorithm = "CatBoost"`, `task_type = "classification"`, and a valid CSV
**Expected Result:** Training succeeds, model registered
**Automation Hint:** `pytest`; assert `resp.status_code == 200`
**Source:** Part13

---

### TC-P1-030
**Category:** Bug-Regression
**Test Name:** render.yaml PYTHON_VERSION is quoted string not float
**Steps:**
1. Inspect `render.yaml` in the ML-Unified repo
2. Parse the YAML and check the PYTHON_VERSION value type
**Expected Result:** PYTHON_VERSION value is a string `"3.11.0"` — not float `3.11`
**Automation Hint:** `pytest`; `import yaml; data = yaml.safe_load(...); assert isinstance(data["envVars"]["PYTHON_VERSION"], str)`
**Source:** Part12

---

### TC-P1-031
**Category:** Data
**Test Name:** Auto-train drops 100%-unique string columns (ID column removal)
**Steps:**
1. Upload a CSV with a column where every row value is unique (e.g. `Name`, `ID`)
2. Call `POST /train`
3. Retrieve the generated schema
**Expected Result:** The 100%-unique column does not appear in schema `fields` list
**Automation Hint:** `pytest`; build CSV with an id column; assert id column name not in `[f["name"] for f in schema["fields"]]`
**Source:** Part12

---

### TC-P1-032
**Category:** Data
**Test Name:** Date columns excluded from generated app.py and index.html form fields
**Steps:**
1. Run `auto_pipeline.py` on Insurance CSV (which has `Policy Start Date`)
2. Check generated `index.html` for `Policy Start Date` field
3. Check generated `app.py` for `Policy Start Date` in `InputData`
**Expected Result:** `Policy Start Date` does not appear as a form input or Pydantic field
**Automation Hint:** `pytest`; assert `"Policy Start Date" not in open("index.html").read()` (in form inputs)
**Source:** Part3

---

### TC-P1-033
**Category:** Data
**Test Name:** Date column detection by name pattern matches common variants
**Steps:**
1. Pass columns named `date`, `timestamp`, `datetime`, `event_dt`, `dt_start` to `_is_date_col()`
**Expected Result:** All return `True`; none appear in categorical features
**Automation Hint:** `pytest`; mock a DataFrame with those column names and assert `_is_date_col(col, df)` returns `True` for each
**Source:** Part3

---

### TC-P1-034
**Category:** Data
**Test Name:** Date column detection by value pattern (ISO format majority)
**Steps:**
1. Create a column with 30 values like `"2024-01-15"` and 5 non-date values
2. Pass to `_is_date_col()`
**Expected Result:** Returns `True` (>50% of sample values match ISO date pattern)
**Automation Hint:** `pytest`; assert `_is_date_col("some_col", df_with_dates) == True`
**Source:** Part3

---

### TC-P1-035
**Category:** Data
**Test Name:** Income/amount columns get no upper limit (`max: null`) in feature_ranges.json
**Steps:**
1. Run `auto_pipeline.py` on a dataset with `Annual Income` column
2. Read `models/feature_ranges.json`
**Expected Result:** `feature_ranges["Annual Income"]["max"]` is `null`; `slider_max` is set to a reasonable value
**Automation Hint:** `pytest`; assert `ranges["Annual Income"]["max"] is None`; assert `ranges["Annual Income"]["slider_max"] > 0`
**Source:** Part3

---

### TC-P1-036
**Category:** Data
**Test Name:** Integer-valued columns get step=1 in feature ranges
**Steps:**
1. Run pipeline on a dataset with `Age` (integer values)
2. Check `feature_ranges.json`
**Expected Result:** `Age` entry has `"step": 1`; `min` and `max` are whole integers
**Automation Hint:** `pytest`; assert `ranges["Age"]["step"] == 1`; assert `ranges["Age"]["min"] == int(ranges["Age"]["min"])`
**Source:** Part3

---

### TC-P1-037
**Category:** Data
**Test Name:** Float-valued columns get step=0.1 in feature ranges
**Steps:**
1. Run pipeline on dataset with `BMI` (float values)
2. Check `feature_ranges.json`
**Expected Result:** `BMI` entry has `"step": 0.1`
**Automation Hint:** `pytest`; assert `ranges["BMI"]["step"] == 0.1`
**Source:** Part3

---

### TC-P1-038
**Category:** Data
**Test Name:** Categorical columns with known uniques generate `<select>` dropdowns
**Steps:**
1. Run `auto_pipeline.py` on Insurance CSV
2. Read generated `index.html`
**Expected Result:** `<select>` elements are present for each categorical column with `<option>` values matching unique values from training data; placeholder `<option value="" disabled selected>Select…</option>` present
**Automation Hint:** `pytest`; parse HTML with BeautifulSoup; assert `soup.find("select", {"name": "Gender"})` is not None
**Source:** Part1

---

### TC-P1-039
**Category:** Data
**Test Name:** Pydantic v2 `Field(alias)` used for column names with spaces
**Steps:**
1. Run `auto_pipeline.py` on Insurance CSV
2. Inspect generated `app.py`
**Expected Result:** `from pydantic import BaseModel, Field` present; columns with spaces use `Field(None, alias="Original Name")`; `model_config = {"populate_by_name": True}` present; `model_dump(by_alias=True)` used (not deprecated `data.dict()`)
**Automation Hint:** `pytest`; `assert "Field" in open("app.py").read()`; `assert "model_dump" in open("app.py").read()`; `assert "data.dict()" not in open("app.py").read()`
**Source:** Part1

---

### TC-P1-040
**Category:** Data
**Test Name:** ID columns not present in generated frontend or app.py
**Steps:**
1. Run `auto_pipeline.py` on Insurance CSV (has `id` column)
2. Inspect `index.html` and `app.py`
**Expected Result:** No form field for `id`; `app.py` has no `id` field in `InputData`
**Automation Hint:** `pytest`; assert `"id" not in [f.name for f in pydantic_model.__fields__.values()]`
**Source:** Part1

---

### TC-P1-041
**Category:** Data
**Test Name:** Titanic Age slider step=1 (not 0.1 or fractional)
**Steps:**
1. Check `ML-Titanic/models/feature_ranges.json`
**Expected Result:** `Age.step == 1` and `Age.min == 0` (was previously 0.42 / 0.1 which caused browser step-validation errors)
**Automation Hint:** `pytest`; `assert ranges["Age"]["step"] == 1`; `assert ranges["Age"]["min"] == 0`
**Source:** Part9

---

### TC-P1-042
**Category:** E2E
**Test Name:** Page loads and sidebar shows model list
**Steps:**
1. Navigate to `https://ml-unified.onrender.com`
2. Wait for sidebar to render
**Expected Result:** Sidebar contains at least 4 model entries (Iris, Titanic, Diabetes, Insurance)
**Automation Hint:** Playwright; `await page.locator('.sidebar-item').count() >= 4`
**Source:** Part12

---

### TC-P1-043
**Category:** E2E
**Test Name:** Selecting a model loads its form dynamically
**Steps:**
1. Navigate to ML-Unified
2. Click "Iris Species Classifier" in sidebar
3. Wait for form to render
**Expected Result:** Form appears with 4 numeric inputs; no other fields
**Automation Hint:** Playwright; `page.locator('input[type="number"]').count() == 4`
**Source:** Part12

---

### TC-P1-044
**Category:** E2E
**Test Name:** Categorical fields render as `<select>` dropdowns (not text inputs)
**Steps:**
1. Select Insurance model in ML-Unified
2. Inspect form
**Expected Result:** Gender, Marital Status, Education Level, etc. all render as `<select>` elements, not `<input type="text">`
**Automation Hint:** Playwright; `await page.locator('select').count() >= 9`
**Source:** Part1, Part9

---

### TC-P1-045
**Category:** E2E
**Test Name:** Fill Sample button populates all form fields
**Steps:**
1. Navigate to any model (e.g. Iris)
2. Click "Fill Sample" button
3. Check form values
**Expected Result:** All numeric inputs contain non-empty, valid values; no field is blank
**Automation Hint:** Playwright; `await page.click('button:has-text("Fill Sample")')`; then first input value is not empty
**Source:** Part9, Part10

---

### TC-P1-046
**Category:** E2E
**Test Name:** Predict button submits form and shows result panel
**Steps:**
1. Fill sample via Fill Sample button
2. Click "Predict"
3. Wait for result panel
**Expected Result:** Result panel becomes visible; shows prediction value or class label; `emptyState` is hidden
**Automation Hint:** Playwright; `await page.click('#pBtn')`; `await page.locator('#resultState').wait_for(state="visible")`
**Source:** Part10

---

### TC-P1-047
**Category:** Bug-Regression
**Test Name:** Predict fires only on button click, NOT on keystroke or slider move
**Steps:**
1. Navigate to any model form
2. Type digits into a numeric field
3. Move a slider
4. Monitor network requests
**Expected Result:** Zero `/predict` API calls triggered by typing or slider movement
**Automation Hint:** Playwright; intercept requests; filter for `/predict`; assert none fired before button click
**Source:** Part2

---

### TC-P1-048
**Category:** Bug-Regression
**Test Name:** Clear button hides result panel and resets all fields
**Steps:**
1. Fill sample and click Predict
2. Wait for result to appear
3. Click "Clear" button
**Expected Result:** All form inputs are blank/reset; result panel is hidden; `emptyState` is visible
**Automation Hint:** Playwright; after clear: `await page.locator('#resultState').wait_for(state="hidden")`; `await page.locator('#emptyState').wait_for(state="visible")`
**Source:** Part3, Part10

---

### TC-P1-049
**Category:** Bug-Regression
**Test Name:** Number spinner arrows not visible on input fields
**Steps:**
1. Load any model form
2. Inspect numeric input fields visually
**Expected Result:** Browser native up/down spinner buttons are not visible on any `<input type="number">` field
**Automation Hint:** Playwright CSS check; `getComputedStyle(document.querySelector('input[type=number]'), '::-webkit-inner-spin-button').display == "none"`
**Source:** Part3

---

### TC-P1-050
**Category:** Bug-Regression
**Test Name:** Tab key advances to next field in one press (sliders are not tab-focusable)
**Steps:**
1. Load Insurance model form
2. Focus first numeric input
3. Press Tab once
**Expected Result:** Focus moves to the next logical field (not to the hidden slider behind it)
**Automation Hint:** Playwright; `await page.keyboard.press("Tab")`; verify focus is on a `.inp` element and not on `input[type=range]`
**Source:** Part3

---

### TC-P1-051
**Category:** Bug-Regression
**Test Name:** Blue value display span NOT shown next to field labels
**Steps:**
1. Load any model form
2. Inspect field label elements
**Expected Result:** No blue "current value" span (`sv` span) adjacent to field labels
**Automation Hint:** Playwright; `await page.locator('.sv').count() == 0`
**Source:** Part3

---

### TC-P1-052
**Category:** Bug-Regression
**Test Name:** Annual Income field accepts values > 0 without showing "Expected 0 – null" error
**Steps:**
1. Load Insurance form
2. Enter `1000000` in Annual Income field
3. Blur (Tab away)
**Expected Result:** No red border; no error message containing "null"; field accepts the value silently
**Automation Hint:** Playwright; `await page.fill('input[name="annual_income"]', "1000000")`; assert no `.err` element visible
**Source:** Part4

---

### TC-P1-053
**Category:** Feature
**Test Name:** Dark/Light theme toggle persists across page reload
**Steps:**
1. Load the ML-Unified app (dark mode default)
2. Click the moon/sun toggle button to switch to light mode
3. Reload the page
**Expected Result:** Light mode is still active after reload; `body` has `class="light"`
**Automation Hint:** Playwright; `page.evaluate("localStorage.getItem('theme')")`; assert == `"light"` after toggle; reload and assert `page.locator("body.light")` is visible
**Source:** Part4

---

### TC-P1-054
**Category:** Feature
**Test Name:** Dark animated mesh background hidden in light mode
**Steps:**
1. Switch to light mode
2. Check `.bg-mesh` element
**Expected Result:** `.bg-mesh` has `opacity: 0` in light mode
**Automation Hint:** Playwright; `page.evaluate("getComputedStyle(document.querySelector('.bg-mesh')).opacity")` == `"0"` when `body.light` active
**Source:** Part8

---

### TC-P1-055
**Category:** Bug-Regression
**Test Name:** Light mode — hero text is dark (not white on white)
**Steps:**
1. Switch to light mode
2. Inspect hero section H1 and subtitle paragraph
**Expected Result:** Hero `<h1>` color is dark; subtitle `<p>` is dark; not white/invisible
**Automation Hint:** Playwright; `page.evaluate("getComputedStyle(document.querySelector('.hero-h1')).color")` should not be `rgb(255, 255, 255)`
**Source:** Part8, Part9

---

### TC-P1-056
**Category:** Bug-Regression
**Test Name:** Feature importance bars visible in light mode
**Steps:**
1. Run a prediction
2. Switch to light mode
3. Inspect Key Factors / feature importance bars
**Expected Result:** Feature importance bar labels and percentages are dark and visible
**Automation Hint:** Playwright; assert feature importance rows are not invisible (check color is not white and opacity > 0)
**Source:** Part5

---

### TC-P1-057
**Category:** Feature
**Test Name:** Confidence Interval section shows tooltip on hover
**Steps:**
1. Make a prediction on a regression model
2. Hover over the `?` tooltip icon next to "Predicted Range"
**Expected Result:** Tooltip box becomes visible with text containing "±1σ" and "standard deviation"
**Automation Hint:** Playwright; `await page.hover('.tip-icon')`; `await page.locator('.tip-box').wait_for(state="visible")`
**Source:** Part5

---

### TC-P1-058
**Category:** Bug-Regression
**Test Name:** Tooltip `?` icon remains after prediction updates CI header text
**Steps:**
1. Load a regression model form
2. Fill sample and predict
3. Check the CI section header
**Expected Result:** `?` tooltip icon still visible in CI header after prediction
**Automation Hint:** Playwright; after predict: `await page.locator('.tip-icon').count() >= 1`
**Source:** Part9

---

### TC-P1-059
**Category:** Feature
**Test Name:** CI bar fill animates from left to prediction position
**Steps:**
1. Submit a prediction for Insurance model
2. Observe the CI section
**Expected Result:** `#ciFill` width is set to a percentage matching the prediction position within [CI_lower, CI_upper]
**Automation Hint:** Playwright; `page.evaluate("document.getElementById('ciFill').style.width")` returns non-zero percent string after prediction
**Source:** Part6

---

### TC-P1-060
**Category:** Feature
**Test Name:** Result badge shows dynamic label from target column name
**Steps:**
1. Load Insurance model
2. Submit a prediction
**Expected Result:** Result badge label reads "Estimated Premium Amount" (derived from `metrics.json` `target` field + task type prefix), NOT "Estimated Value"
**Automation Hint:** Playwright; `await page.locator('#resLabel').text_content()` contains "Premium Amount"
**Source:** Part6

---

### TC-P1-061
**Category:** Feature
**Test Name:** CI header shows "Likely [Target] Range" dynamically
**Steps:**
1. Load Insurance model and predict
2. Inspect CI section header text
**Expected Result:** CI header reads "Likely Premium Amount Range" (or similar), NOT hardcoded "Confidence Interval"
**Automation Hint:** Playwright; `await page.locator('#ciHeaderTxt').text_content()` contains "Premium Amount"
**Source:** Part6

---

### TC-P1-062
**Category:** Bug-Regression
**Test Name:** "Range: X – Y (±1σ)" text removed from result panel
**Steps:**
1. Submit a prediction for any regression model
2. Inspect `#resConf` element
**Expected Result:** `#resConf` is empty string — not displaying range or (±1σ) text
**Automation Hint:** Playwright; `await page.locator('#resConf').text_content() == ""`
**Source:** Part5

---

### TC-P1-063
**Category:** Bug-Regression
**Test Name:** "Near Average" / "Above Average" benchmark badge not shown
**Steps:**
1. Submit a regression prediction
2. Inspect `#benchmarkBadge` element
**Expected Result:** `#benchmarkBadge` is hidden / not displayed
**Automation Hint:** Playwright; `await page.locator('#benchmarkBadge').is_visible() == False`
**Source:** Part5

---

### TC-P1-064
**Category:** Feature
**Test Name:** Input summary shows two-column layout with vertical divider
**Steps:**
1. Fill sample and predict on Insurance model
2. Inspect input summary section
**Expected Result:** Summary has `.sum-col` left column, `.sum-divider` vertical line, `.sum-col` right column
**Automation Hint:** Playwright; `await page.locator('.sum-divider').count() == 1`; `await page.locator('.sum-col').count() == 2`
**Source:** Part3

---

### TC-P1-065
**Category:** Feature
**Test Name:** "About This Model" tooltip shows MAE and RMSE definitions
**Steps:**
1. Load any model
2. Hover over the `?` tooltip on "ABOUT THIS MODEL"
**Expected Result:** Tooltip text contains "MAE = Mean Absolute Error" and "RMSE"
**Automation Hint:** Playwright; `await page.hover('.about-tooltip-icon')`; `await page.locator('.tip-box').text_content()` contains "Mean Absolute Error"
**Source:** Part8

---

### TC-P1-066
**Category:** Feature
**Test Name:** Train New Model wizard — 3-step flow completes successfully
**Steps:**
1. Click "Train New Model" in sidebar
2. Step 1: Upload a CSV file
3. Step 2: Set model name, target column, task type, algorithm, accent color
4. Step 3: Wait for training spinner → success screen
5. Click "Use Model"
**Expected Result:** New model appears in sidebar; no error shown during training
**Automation Hint:** Playwright; after "Use Model": `await page.locator('.sidebar-item:last-child').text_content()` contains custom model name
**Source:** Part12

---

### TC-P1-067
**Category:** Feature
**Test Name:** Train wizard `suggestTask()` updates task type when target column changes
**Steps:**
1. Open Train wizard, upload CSV with mixed columns
2. Select a categorical target column
3. Change to a numeric target column
**Expected Result:** Task type radio auto-updates: categorical → "classification"; numeric → "regression"
**Automation Hint:** Playwright; change select value, assert radio button state changes accordingly
**Source:** Part12

---

### TC-P1-068
**Category:** Feature
**Test Name:** Unsupervised Analysis section visible in sidebar with 4 algorithm buttons
**Steps:**
1. Load ML-Unified app
2. Locate "Unsupervised Analysis" section in sidebar
**Expected Result:** Sidebar shows "Unsupervised Analysis" heading with 4 buttons: K-Means, DBSCAN, t-SNE, PCA
**Automation Hint:** Playwright; assert `page.locator('text=Unsupervised Analysis').count() >= 1`; assert 4 algorithm buttons visible
**Source:** Part12

---

### TC-P1-069
**Category:** Feature
**Test Name:** Clicking unsupervised algorithm shows dedicated panel with CSV upload
**Steps:**
1. Click "K-Means" in Unsupervised Analysis section
**Expected Result:** Main area shows K-Means panel with: algorithm description, CSV file upload control, n_clusters parameter input, Run K-Means button
**Automation Hint:** Playwright; `await page.click('text=K-Means')`; `await page.locator('input[type=file]').wait_for()`
**Source:** Part12

---

### TC-P1-070
**Category:** Feature
**Test Name:** 2D/3D toggle available for all unsupervised algorithms
**Steps:**
1. Click any unsupervised algorithm
2. Inspect params section
**Expected Result:** 2D/3D radio or toggle buttons present in the algorithm panel
**Automation Hint:** Playwright; assert 2D and 3D option buttons/radios are present in the panel
**Source:** Part12

---

### TC-P1-071
**Category:** Feature
**Test Name:** DBSCAN shows "eps too small" hint when 0 clusters returned
**Steps:**
1. Open DBSCAN panel
2. Upload a multi-column dataset with eps set very small (e.g. 0.001)
3. Run DBSCAN
**Expected Result:** UI shows a yellow hint "eps too small" or "try increasing eps" message
**Automation Hint:** Playwright; assert `page.locator('text=eps').is_visible()` when n_clusters == 0
**Source:** Part12

---

### TC-P1-072
**Category:** Bug-Regression
**Test Name:** DBSCAN StandardScaler applied — scaled features sent to algorithm (not raw)
**Steps:**
1. Prepare a CSV with columns of very different scales (e.g. age 0-80, income 0-200000)
2. Run DBSCAN via `/unsupervised` with eps=0.5
**Expected Result:** DBSCAN returns non-zero clusters; raw unscaled distances would make eps=0.5 meaningless
**Automation Hint:** `pytest`; use mixed-scale CSV; assert `resp.json()["stats"]["n_clusters"] > 0`
**Source:** Part13

---

### TC-P1-073
**Category:** Bug-Regression
**Test Name:** PCA label shows "n_components" not "Dimensions"
**Steps:**
1. Open PCA panel in Unsupervised Analysis
2. Inspect parameter control label
**Expected Result:** Label reads "n_components — components to extract" with options 2 and 3
**Automation Hint:** Playwright; `await page.locator('text=n_components').count() >= 1`
**Source:** Part13

---

### TC-P1-074
**Category:** Feature
**Test Name:** Generated `app.py` has no syntax errors
**Steps:**
1. Run `auto_pipeline.py` on any CSV
2. Run `python -m py_compile output/app.py`
**Expected Result:** Zero syntax errors
**Automation Hint:** `pytest`; `subprocess.run(["python", "-m", "py_compile", "app.py"], check=True)`
**Source:** Part1

---

### TC-P1-075
**Category:** Feature
**Test Name:** Generated `model.pkl` and `feature_ranges.json` files exist after pipeline run
**Steps:**
1. Run `auto_pipeline.py` on Insurance CSV
2. Check output directory
**Expected Result:** `models/model.pkl` exists; `models/feature_ranges.json` exists; both are non-empty
**Automation Hint:** `pytest`; `assert Path("models/model.pkl").exists()` and `Path("models/feature_ranges.json").stat().st_size > 0`
**Source:** Part1

---

### TC-P1-076
**Category:** Bug-Regression
**Test Name:** Target column prompt loops until non-empty input provided
**Steps:**
1. Run `start.sh` or `init.py`
2. Press Enter without typing a target column name
3. Type a valid column name on second prompt
**Expected Result:** Tool shows a warning and re-prompts; does NOT proceed with empty target column
**Automation Hint:** `pytest` + `subprocess` with stdin piped; pipe `"\n"` then `"Price\n"`; assert pipeline runs with `target_col == "Price"`
**Source:** Part1

---

### TC-P1-077
**Category:** Bug-Regression
**Test Name:** CSV path whitespace stripped before processing
**Steps:**
1. Run `start.sh` with CSV path that has leading/trailing spaces
**Expected Result:** Pipeline loads the CSV correctly; no "file not found" error due to whitespace
**Automation Hint:** `pytest`; pipe input with spaces; assert no FileNotFoundError
**Source:** Part1

---

### TC-P1-078
**Category:** Bug-Regression
**Test Name:** `bootstrap.py` includes Render API key prompt (not only `init.py`)
**Steps:**
1. Run `python3 bootstrap.py`
2. Select "Render" as deployment platform
**Expected Result:** Wizard asks for Render API key; key stored in `.ml_config.json`
**Automation Hint:** `pytest`; mock wizard stdin; assert `.ml_config.json` contains `render_api_key` key after run
**Source:** Part2

---

### TC-P1-079
**Category:** Bug-Regression
**Test Name:** pip install uses `--no-cache-dir` to suppress cache warnings
**Steps:**
1. Run `bootstrap.py` in a clean environment
2. Observe pip output
**Expected Result:** No `WARNING: Cache entry deserialization failed` messages in stdout/stderr
**Automation Hint:** `pytest`; capture subprocess output; assert "Cache entry deserialization" not in stderr
**Source:** Part2

---

### TC-P1-080
**Category:** Feature
**Test Name:** Render API auto-deployment — service created via API if key is provided
**Steps:**
1. Provide a valid Render API key in wizard
2. Run `_deploy_render()` logic
**Expected Result:** `GET https://api.render.com/v1/owners` called → owner ID retrieved; `POST https://api.render.com/v1/services` called → service creation attempted; live URL printed
**Automation Hint:** `pytest` with `requests_mock`; mock Render API endpoints; assert both calls are made with correct headers
**Source:** Part1

---

### TC-P1-081
**Category:** Feature
**Test Name:** Render deployment falls back to manual instructions when no API key given
**Steps:**
1. Leave Render API key blank in wizard
2. Complete pipeline run
**Expected Result:** No API calls made; manual deployment instructions are printed to stdout; no exception raised
**Automation Hint:** `pytest`; pipe empty key; capture stdout; assert instructions string present; assert no requests made to api.render.com
**Source:** Part1

---

### TC-P1-082
**Category:** Feature
**Test Name:** `metrics.json` includes `target` field for regression models
**Steps:**
1. Run pipeline on a regression dataset
2. Read `models/metrics.json`
**Expected Result:** JSON has `"target"` key with the target column name
**Automation Hint:** `pytest`; assert `json.load(f)["target"] == expected_target_col`
**Source:** Part6

---

### TC-P1-083
**Category:** Feature
**Test Name:** `metrics.json` includes `algorithm` field for regression models
**Steps:**
1. Run pipeline on any dataset
2. Read `models/metrics.json`
**Expected Result:** JSON has `"algorithm"` key (e.g. `"XGBoost"`) — not `None` or `"—"`
**Automation Hint:** `pytest`; assert `json.load(f).get("algorithm") not in (None, "", "—")`
**Source:** Part5

---

### TC-P1-084
**Category:** E2E
**Test Name:** Portfolio page loads and shows ML-Unified platform card
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app`
**Expected Result:** Page loads; at least one project card visible; "Launch App" button links to `https://ml-unified.onrender.com`
**Automation Hint:** Playwright; `await page.locator('a[href*="ml-unified.onrender.com"]').count() >= 1`
**Source:** Part10, Part12

---

### TC-P1-085
**Category:** Feature
**Test Name:** Portfolio theme toggle persists across reload (no-flash)
**Steps:**
1. Toggle to light mode on portfolio
2. Reload page
**Expected Result:** Light mode is immediately applied on reload without a flash of dark mode
**Automation Hint:** Playwright; toggle light; reload; assert `body.light` class within 100ms of navigation; no FOUC
**Source:** Part10

---

### TC-P1-086
**Category:** Feature
**Test Name:** Portfolio "Launch App" buttons open Render URLs in new tab
**Steps:**
1. Navigate to portfolio
2. Click any "Launch App" button
**Expected Result:** New browser tab opens to the correct Render URL
**Automation Hint:** Playwright; `page.expect_popup()`; assert new page URL contains "onrender.com"
**Source:** Part10

---

### TC-P1-087
**Category:** Bug-Regression
**Test Name:** Portfolio build passes TypeScript type check (no type errors)
**Steps:**
1. Run `npm run build` and `tsc --noEmit` in `ml-portfolio` directory
**Expected Result:** Both commands exit 0 — no TypeScript or build errors
**Automation Hint:** GitHub Actions CI; `pytest` via subprocess; assert returncode == 0
**Source:** Part15

---

### TC-P1-088
**Category:** Feature
**Test Name:** Portfolio hero displays "AIRaML" branding (not "Ramleo")
**Steps:**
1. Navigate to portfolio
2. Inspect hero section
**Expected Result:** Hero contains "AIRaML" text; "Ramleo" does not appear in hero
**Automation Hint:** Playwright; `await page.locator('text=AIRaML').count() >= 1`; `await page.locator('text=Ramleo').count() == 0`
**Source:** Part12

---

### TC-P1-089
**Category:** Feature
**Test Name:** GitHub Actions CI runs ruff lint on `app.py` with no errors
**Steps:**
1. Push to `main` branch of ML-Unified
2. Observe CI workflow
**Expected Result:** `ruff check app.py` passes (exit 0)
**Automation Hint:** GitHub Actions; assert job "test" step "ruff" exits 0
**Source:** Part15

---

### TC-P1-090
**Category:** Feature
**Test Name:** GitHub Actions CI runs all 18 pytest tests on push
**Steps:**
1. Push to ML-Unified `main` branch
2. Observe CI "test" job
**Expected Result:** `pytest tests/ -v` reports 18 passed, 0 failed
**Automation Hint:** GitHub Actions; assert job exits 0 and output matches "18 passed"
**Source:** Part15

---

### TC-P1-091
**Category:** Feature
**Test Name:** GitHub Actions deploy job only runs when test job passes
**Steps:**
1. Introduce a failing test
2. Push to main
3. Observe deploy job
**Expected Result:** Deploy job does NOT trigger when test job fails
**Automation Hint:** GitHub Actions; assert deploy job has `needs: test` and is skipped when test fails
**Source:** Part15

---

### TC-P1-092
**Category:** Feature
**Test Name:** ML-Portfolio CI build job runs `npm ci`, `tsc --noEmit`, `npm run build` on push
**Steps:**
1. Push to ML-Portfolio `main` branch
**Expected Result:** All three steps pass; build artifact generated; no TypeScript errors
**Automation Hint:** GitHub Actions; assert job exits 0
**Source:** Part15
