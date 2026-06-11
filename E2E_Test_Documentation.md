# E2E Test Documentation — ML-Unified

**Framework:** Playwright (Python) + pytest  
**Location:** `tests/e2e/`  
**Run command:** `.venv/bin/python3 -m pytest tests/e2e/ -v`

---

## Quick Reference

| Command | Use |
|---------|-----|
| `.venv/bin/python3 -m pytest tests/e2e/ -v` | Full suite, headless |
| `.venv/bin/python3 -m pytest tests/e2e/ -v --headed` | Full suite, browser visible |
| `.venv/bin/python3 -m pytest tests/e2e/ -v --headed --slowmo 800` | Headed + slowed for visual debugging |
| `.venv/bin/python3 -m pytest tests/e2e/test_inference.py -v` | Inference tests only |
| `.venv/bin/python3 -m pytest tests/e2e/ -k "iris" -v` | Tests matching "iris" |

**Total:** 17 tests — 13 always run, 4 skip unless `ML_EDA_URL` is configured.

---

## Infrastructure — `conftest.py`

### `ml_api_server` *(session-scoped)*

Starts the ml-api FastAPI server on `localhost:8765` once for the entire test session.

- Launches `uvicorn app:app` in `services/ml-api/` using the venv Python
- Waits up to 30s for `/health` to respond (server startup)
- Waits up to 120s for `/health` to report ≥ 4 models loaded (background model loading)
- Tears down the process after all tests complete
- Raises `RuntimeError` if either wait deadline is exceeded

### `browser_session` *(session-scoped)*

Creates a single Chromium browser instance reused across all tests.

- Respects `--headed` CLI flag — browser window opens when flag is passed
- Respects `--slowmo` CLI flag — slows all interactions by N milliseconds
- Closed after all tests complete

### `page` *(function-scoped)*

Creates a fresh browser context and page for each individual test.

- Navigates to `http://localhost:8765` with `wait_until="networkidle"`
- Context (cookies, storage, history) is isolated per test
- Closed after each test

> **Design note:** Each test gets a clean page state. The app auto-selects the first model alphabetically (`diabetes`) on load. All helpers that select a specific model use `page.wait_for_function("activeModel?.id === '<model_id>'")`  rather than `wait_for_selector("#predictBtn")`, because `#predictBtn` already exists in the DOM from the auto-selection before the target model is clicked.

### `iris_csv` / `titanic_csv` *(function-scoped)*

Write minimal sample CSVs to `tmp_path` and return the file path as a string.

- `iris_csv`: 5 rows, columns: `Id, SepalLengthCm, SepalWidthCm, PetalLengthCm, PetalWidthCm`
- `titanic_csv`: 5 rows, columns: `PassengerId, Pclass, Name, Sex, Age, SibSp, Parch, Ticket, Fare, Cabin, Embarked`

---

## Test Files

### `test_home.py` — Page Load & Sidebar (5 tests)

Tests that the app loads correctly and the sidebar is populated.

---

#### `test_page_title`

**What it checks:** The browser tab title contains "ML".

**Steps:**
1. Open app root (handled by `page` fixture)
2. Assert `page.title()` contains `"ML"`

---

#### `test_sidebar_has_supervised_models`

**What it checks:** All four supervised model buttons are present in the sidebar.

**Steps:**
1. Open app root
2. For each model ID in `(iris, titanic, diabetes, insurance)`:
   - Assert exactly one element with `#btn-<model_id>` exists

---

#### `test_sidebar_has_unsupervised_tools`

**What it checks:** K-Means and DBSCAN tool buttons are present in the sidebar.

**Steps:**
1. Open app root
2. Wait for `#ubtn-kmeans` (up to 5s)
3. Wait for `#ubtn-dbscan` (up to 5s)

---

#### `test_sidebar_has_data_tools`

**What it checks:** EDA and Clean & Export buttons appear when `?mode=eda` is active.

**Steps:**
1. Navigate to `/?mode=eda`
2. Wait for `#ebtn-eda` (up to 8s)
3. Wait for `#ebtn-clean` (up to 5s)

> **Note:** These buttons are only rendered when `APP_MODE === 'eda'`, which is activated via the `?mode=eda` URL parameter.

---

#### `test_empty_state_shown_on_load`

**What it checks:** The empty-state prompt is visible before any model is selected.

**Steps:**
1. Open app root
2. Assert `#emptyState` exists (count == 1)
3. Assert `#emptyState` is visible

---

### `test_inference.py` — Single-Row Prediction (5 tests)

Tests the full prediction flow: select model → fill form → predict → verify result.

---

#### `test_iris_predict_returns_result`

**What it checks:** Submitting valid iris features returns a non-empty result panel.

**Steps:**
1. Click `#btn-iris`, wait for `activeModel.id === 'iris'`
2. Fill: `SepalLengthCm=5.1`, `SepalWidthCm=3.5`, `PetalLengthCm=1.4`, `PetalWidthCm=0.2`
3. Click `#predictBtn`
4. Wait for `#resultState` to become visible (up to 15s)
5. Assert `#resultBody` inner text is not empty

---

#### `test_iris_predict_shows_species`

**What it checks:** The result for the iris Setosa sample contains a species name.

**Steps:**
1–4. Same as above
5. Assert result body contains one of: `Setosa`, `Versicolor`, `Virginica`

---

#### `test_iris_predict_shows_shap`

**What it checks:** After a successful prediction the SHAP panel completes (shows bars or an error state — not stuck on spinner).

**Steps:**
1. Select iris model, fill and submit the same Setosa sample
2. Wait for `#resultState` visible (up to 15s)
3. Wait (up to 30s) for either:
   - `.shap-bar-fill` element inside `#shapBody` (bars rendered), OR
   - `.shap-loading` element inside `#shapBody` (loading indicator — SHAP still processing)
4. Assert `#shapPanel` is visible

> **Note:** SHAP uses server-sent events (SSE). `#shapPanel` becomes visible immediately showing a spinner; bars only appear after the SSE stream completes. The test accepts either state to avoid a 30s timeout on slower machines.

---

#### `test_titanic_predict_returns_result`

**What it checks:** Submitting a valid Titanic row returns a survival prediction.

**Steps:**
1. Click `#btn-titanic`, wait for `activeModel.id === 'titanic'`
2. Select: `Pclass=3`, `Sex=male`, `Embarked=S`
3. Fill: `Age=22`, `SibSp=1`, `Parch=0`, `Fare=7.25`
4. Click `#predictBtn`
5. Wait for `#resultState` visible (up to 15s)
6. Assert result body contains one of: `Survived`, `Did not survive`, `0`, `1`

---

#### `test_diabetes_predict_returns_result`

**What it checks:** Submitting valid diabetes features returns a non-empty result panel.

**Steps:**
1. Click `#btn-diabetes`, wait for `activeModel.id === 'diabetes'`
2. Fill all 8 fields with sample values within each field's `[min, max]` range:
   - `Pregnancies=6`, `Glucose=148`, `BloodPressure=72`, `SkinThickness=35`
   - `Insulin=0`, `BMI=33.6`, `DiabetesPedigreeFunction=0.627`, `Age=50`
3. Click `#predictBtn`
4. Wait for `#resultState` visible (up to 15s)
5. Assert result body is not empty

> **Note:** All values must be within each field's schema-defined `[min, max]` range. Browser number inputs with HTML `min` validation will silently reject out-of-range values, leaving the field empty and causing a "Please fill in all fields" error.

---

### `test_drift.py` — Drift Monitor (3 tests)

Tests the drift monitoring flow: open the Drift tab, switch to upload mode, upload a CSV, verify metrics render.

---

#### `test_drift_tab_opens`

**What it checks:** Clicking the Drift tab opens the drift view.

**Steps:**
1. Select iris model, wait for `activeModel.id === 'iris'`
2. Click `#tabDrift`
3. Wait for `#driftBody` (up to 8s)
4. Assert `#driftView` is visible

---

#### `test_drift_upload_renders_metrics`

**What it checks:** Uploading an iris CSV produces a populated drift metrics panel.

**Steps:**
1. Open drift tab (as above)
2. Call `_switchDriftMode('upload')` via `page.evaluate()`, wait for `#driftUploadZone`
3. Set `iris.csv` on `#driftFileInput`
4. Wait (up to 20s) for `#driftBody` inner text to contain `OVERALL DRIFT` or `Could not analyse`
5. Assert `#driftBody` inner text is not empty

> **Note:** Drift panel defaults to "predictions" mode on load. `_switchDriftMode('upload')` is a JS function exposed on `window` that switches the panel mode. File is set directly on the hidden `<input type="file">` rather than simulating a drag-and-drop.

---

#### `test_drift_upload_shows_column_metrics`

**What it checks:** The drift result includes iris column names (Sepal/Petal features), confirming per-column statistics were computed.

**Steps:**
1–4. Same as `test_drift_upload_renders_metrics`
5. Assert `Could not analyse` is NOT in the result body
6. Assert at least one of `Sepal`, `Petal`, `SepalLength`, `PetalLength` appears in the result body

---

### `test_clean.py` — Clean & Export (4 tests, conditional)

Tests the Clean & Export panel. All four tests are **automatically skipped** unless `ML_EDA_URL` is set in the environment and the ml-eda service is reachable.

**Prerequisite:**
```bash
export ML_EDA_URL=http://localhost:8000   # or wherever ml-eda is running
```

---

#### `test_clean_panel_opens`

**What it checks:** Clicking the Clean & Export sidebar button opens the options panel.

**Steps:**
1. Navigate to `/?mode=eda` (handled within the test by the `page` fixture + `?mode=eda` navigation)
2. Click `#ebtn-clean`
3. Wait for `#cleanOptions` (up to 8s)
4. Assert `#cleanOptions` is visible

---

#### `test_clean_upload_renders_options`

**What it checks:** Uploading a CSV triggers analysis and the options panel renders with the correct title.

**Steps:**
1. Open clean panel
2. Click `#cleanOptions` to trigger the file chooser
3. Set `iris.csv` via the file chooser
4. Wait for `.shap-header` inside `#cleanOptions` (up to 30s — analysis runs server-side)
5. Assert `.shap-title` text equals `"🧹 Clean & Export"`

---

#### `test_clean_upload_shows_sections`

**What it checks:** After upload, all five cleaning-option sections are rendered.

**Steps:**
1–4. Same upload flow as above
5. Assert `#cleanOptions` inner text contains all of:
   - `Duplicate rows`
   - `Columns to drop`
   - `Missing value`
   - `Outlier`
   - `Power transform`

---

#### `test_clean_submit_downloads_csv`

**What it checks:** Submitting the clean form triggers a CSV file download.

**Steps:**
1–4. Same upload flow
5. Click `#sc-submit` while listening for a download event
6. Assert the downloaded file's suggested filename ends with `.csv`

---

## Adding New Tests

When a new feature is added or an existing one is changed, update or add tests following these conventions:

1. **Model selection** — always use `_select_model(page, "model_id")` (defined in `test_inference.py`) or inline `page.wait_for_function(f"activeModel?.id === '{model_id}'")`; never rely on `wait_for_selector("#predictBtn")` alone.
2. **Waits** — prefer `wait_for_function` for conditions based on JS state; use `wait_for_selector` for DOM presence/visibility.
3. **Form fills** — always use `page.fill()` for text/number inputs and `page.select_option()` for dropdowns; do not use `page.evaluate()` to set form values (browser validation can silently clear them).
4. **Conditional tests** — gate tests on optional services using `pytest.mark.skipif` (see `test_clean.py` pattern).
5. **New fixtures** — add session-scoped fixtures to `conftest.py`; keep function-scoped (per-test) state in the test file itself.
