# TC-P4 — Parts 51–65 Test Cases

Source: Conversation Parts 51–65
Total: 90 test cases
Tokens used: ~39,262 | Duration: ~238s

---

### TC-P4-001
**Category:** Bug-Regression
**Test Name:** TDZ crash — THEMES accessed before declaration
**Steps:**
1. Open the ML-Unified frontend in a browser (Chrome/Chromium)
2. Open DevTools → Console tab
3. Hard refresh the page (Cmd+Shift+R)
**Expected Result:** No `ReferenceError: Cannot access 'THEMES' before initialization` in the console. The model list loads within 10 seconds.
**Automation Hint:** `page.on('console', ...)` filter for `ReferenceError`; assert `page.locator('#modelList .model-btn').count() >= 4`
**Source:** Part52

---

### TC-P4-002
**Category:** Bug-Regression
**Test Name:** "Loading models…" hangs forever after TDZ crash
**Steps:**
1. Navigate to the app root
2. Wait up to 15 seconds
3. Check whether the sidebar model buttons are rendered
**Expected Result:** Sidebar model buttons appear within 15 seconds; "Loading models..." spinner disappears.
**Automation Hint:** `page.wait_for_selector('.model-btn', timeout=15000)`; assert count >= 4
**Source:** Part52

---

### TC-P4-003
**Category:** Bug-Regression
**Test Name:** SHAP zero baseline — Iris LinearExplainer returns non-zero SHAP values
**Steps:**
1. Select the Iris model
2. Click "Fill Sample"
3. Click "Predict"
4. Wait for the SHAP Feature Impact panel to load
5. Inspect the SHAP bar values
**Expected Result:** At least one `.shap-bar-fill` element has a non-zero width (not all bars empty/zero).
**Automation Hint:** `page.locator('.shap-bar-fill[data-pct]').first()` — assert `data-pct` attribute != `"0"`
**Source:** Part53, Part51

---

### TC-P4-004
**Category:** UI
**Test Name:** btn-primary (Predict button) uses model accent color, not theme gradient
**Steps:**
1. Select the Titanic model (accent: cyan)
2. Inspect the "Predict" button background color
3. Switch to the Iris model (accent: different color)
4. Inspect the "Predict" button background color again
**Expected Result:** The Predict button background matches the model's accent color (`--active-accent`). Color changes when switching models.
**Automation Hint:** `page.evaluate("getComputedStyle(document.querySelector('#predictBtn')).background")` — assert contains model accent hue
**Source:** Part51, Part53

---

### TC-P4-005
**Category:** UI
**Test Name:** Model eyebrow and metric value use theme color, not model accent
**Steps:**
1. Select any model
2. Inspect the `.model-eyebrow` element computed color
3. Inspect the `.metric-val` element computed color
4. Switch themes
5. Re-inspect both elements
**Expected Result:** `.model-eyebrow` and `.metric-val` colors reflect `var(--accent-from)` (theme color). Color changes with theme switch, not with model switch.
**Automation Hint:** `page.evaluate("getComputedStyle(document.querySelector('.model-eyebrow')).color")` — assert changes after theme click
**Source:** Part51, Part53

---

### TC-P4-006
**Category:** Bug-Regression
**Test Name:** Green left-edge artifact absent from Outcome card
**Steps:**
1. Select any model
2. Click "Fill Sample" then "Predict"
3. Wait for `#resultState` to become visible
4. Visually inspect / check CSS of the result card left edge
**Expected Result:** No green accent bar appears on the left edge of the result card. `.result-accent-bar` should have `display: none`.
**Automation Hint:** `page.locator('.result-accent-bar').evaluate("el => getComputedStyle(el).display")` — assert `"none"`
**Source:** Part51, Part53

---

### TC-P4-007
**Category:** UI
**Test Name:** Result card and SHAP panel are fully transparent (no solid background)
**Steps:**
1. Select any model, predict
2. Inspect CSS of `#resultState` and `.shap-panel`
**Expected Result:** Both elements have `background: transparent` and `box-shadow: none`.
**Automation Hint:** `page.evaluate("getComputedStyle(document.querySelector('#resultState')).backgroundColor")` — assert `"rgba(0, 0, 0, 0)"` or `"transparent"`
**Source:** Part51, Part53

---

### TC-P4-008
**Category:** UI
**Test Name:** Pipeline, What-if, and Drift cards are transparent
**Steps:**
1. Select a model
2. Navigate to the Pipeline tab, What-if tab, and Drift tab in turn
3. Inspect `.pipe-card`, `.train-card`, `.drift-summary`, `.drift-feature` background
**Expected Result:** All four elements have `background: transparent` and `box-shadow: none`.
**Automation Hint:** `page.evaluate("getComputedStyle(document.querySelector('.pipe-card')).backgroundColor")` — assert transparent for each selector
**Source:** Part51, Part53

---

### TC-P4-009
**Category:** Feature
**Test Name:** Cold-start UX — "Server waking up" message appears after 5 seconds
**Steps:**
1. With the backend cold, navigate to the app root
2. Wait 6 seconds without the model list loading
**Expected Result:** A spinner and "Server waking up" message is visible to the user after 5 seconds of loading.
**Automation Hint:** Mock slow `/models` response with a 6s delay; assert cold-start message is visible after `page.wait_for_timeout(6000)`
**Source:** Part51, Part53

---

### TC-P4-010
**Category:** Feature
**Test Name:** Multi-theme picker renders 6 theme options
**Steps:**
1. Open the app
2. Locate the theme picker UI element
**Expected Result:** At least 6 theme options are available: dark, light, midnight, ocean, sunset, forest.
**Automation Hint:** `page.locator('[data-theme]').count()` — assert >= 6
**Source:** Part53

---

### TC-P4-011
**Category:** Feature
**Test Name:** Theme switch updates gradient colors across UI
**Steps:**
1. Open the app (default theme: dark)
2. Note the nav logo mark color
3. Click the "ocean" theme
4. Note the nav logo mark color again
**Expected Result:** The gradient color of `.nav-logo-mark`, `.gradient-top-bar`, and `.gradient-text` changes when a new theme is selected.
**Automation Hint:** Capture `getComputedStyle(document.querySelector('.gradient-top-bar')).background` before and after theme click — assert they differ
**Source:** Part53

---

### TC-P4-012
**Category:** Bug-Regression
**Test Name:** Model accent does not bleed into theme accent (theme isolation)
**Steps:**
1. Set theme to "forest" (green)
2. Select the Titanic model (cyan accent)
3. Check the nav logo mark, gradient top bar, and eyebrow colors
**Expected Result:** Nav/gradient colors remain green (forest theme). Only the Predict button and SHAP bars use cyan (model accent).
**Automation Hint:** After selecting Titanic: `page.evaluate("getComputedStyle(document.querySelector('.gradient-top-bar')).backgroundImage")` — assert still contains forest green hue, not cyan
**Source:** Part51, Part53

---

### TC-P4-013
**Category:** Bug-Regression
**Test Name:** Uvicorn binds immediately — no port scan timeout on startup
**Steps:**
1. Deploy the ml-api service
2. Send an HTTP GET to `/health` within 5 seconds of starting the process
**Expected Result:** `/health` returns 200 within 5 seconds even if models are still loading. The server does not block on `_load()` before binding.
**Automation Hint:** `requests.get('http://localhost:8765/health', timeout=5)` immediately after process spawn — assert `status_code == 200`
**Source:** Part57

---

### TC-P4-014
**Category:** Backend API
**Test Name:** /health endpoint returns model list after background thread loads models
**Steps:**
1. Start ml-api server
2. Wait up to 60 seconds
3. GET `/health`
**Expected Result:** Response JSON contains a `models` key with a list of at least 4 model IDs.
**Automation Hint:** `pytest` fixture waits for `GET /health` to return `models` list with `len >= 4`; assert `len(resp.json()['models']) >= 4`
**Source:** Part57, Part59

---

### TC-P4-015
**Category:** Feature
**Test Name:** Clean & Export — animated progress bar appears during CSV analysis
**Steps:**
1. Navigate to the EDA / Clean & Export section
2. Upload a CSV file
**Expected Result:** An animated progress bar appears with 5 named steps: "Parsing CSV", "Profiling columns", "Computing statistics", "Detecting outliers", "Generating insights". Bar advances every ~900ms. Snaps to 100% on completion.
**Automation Hint:** After file upload trigger: `page.locator('#sc-progress, .sc-progress')` is visible; assert label text changes within 2s
**Source:** Part56

---

### TC-P4-016
**Category:** Feature
**Test Name:** Clean & Export — duplicate rows section shows badge count
**Steps:**
1. Upload a CSV with known duplicate rows to Clean & Export
2. Wait for analysis to complete
**Expected Result:** A "Duplicate rows" section appears with a count badge (e.g. "6 found"). Dedup checkbox is ON by default when duplicates exist.
**Automation Hint:** `page.locator('#sc-dedup-badge, [data-testid="dedup-count"]').inner_text()` — assert contains a number > 0; checkbox `#sc-dedup` should be `checked`
**Source:** Part56

---

### TC-P4-017
**Category:** Feature
**Test Name:** Clean & Export — columns to drop list pre-populated with auto-detected ID columns
**Steps:**
1. Upload a CSV containing a column with > 95% unique values (e.g. PassengerId)
2. Wait for analysis
3. Inspect the "Columns to drop" section
**Expected Result:** The detected high-uniqueness column(s) appear in the drop list with a reason label. All are checked by default.
**Automation Hint:** `page.locator('#sc-dropcol-list .shap-feat-name').first().inner_text()` — assert it is the ID column name
**Source:** Part56

---

### TC-P4-018
**Category:** Feature
**Test Name:** Clean & Export — per-column imputation checkboxes rendered per missing-value column
**Steps:**
1. Upload a CSV with multiple columns that have missing values
2. Wait for analysis
3. Inspect the "Missing value imputation" section
**Expected Result:** Each column with `missing > 0` appears as an individual checkbox row.
**Automation Hint:** Count `page.locator('#sc-impute-rows .shap-row').count()` — assert equals number of columns with missing values
**Source:** Part56

---

### TC-P4-019
**Category:** Feature
**Test Name:** Clean & Export — per-column outlier removal checkboxes rendered
**Steps:**
1. Upload a CSV with numeric columns containing outliers (IQR-detected)
2. Wait for analysis
3. Inspect the "Outlier removal" section
**Expected Result:** Each column with `outliers > 0` appears as a checkbox row.
**Automation Hint:** `page.locator('#sc-outlier-rows .shap-row').count()` — assert > 0 when outlier columns exist
**Source:** Part56

---

### TC-P4-020
**Category:** Feature
**Test Name:** Clean & Export — per-column power transform checkboxes for skewed columns
**Steps:**
1. Upload a CSV with numeric columns where `|skew| > 0.5`
2. Wait for analysis
3. Inspect the "Power transform" section
**Expected Result:** Each skewed column appears as a checkbox row. Yeo-Johnson method is used.
**Automation Hint:** `page.locator('#sc-power-rows .shap-row').count()` — assert > 0 for skewed data
**Source:** Part56

---

### TC-P4-021
**Category:** Feature
**Test Name:** EDA Explorer — Outliers and Skewness sub-panels use SHAP-style bars
**Steps:**
1. Upload a CSV with numeric columns
2. Run EDA analysis
3. Navigate to the "Statistics" section
**Expected Result:** Two sub-panels appear: "Outliers (IQR)" and "Skewness", each using `_barRow` helper with `.shap-row` classes.
**Automation Hint:** `page.locator('.eda-stats-section .shap-row').count()` — assert > 0
**Source:** Part56

---

### TC-P4-022
**Category:** Feature
**Test Name:** Clean & Export card is transparent — blends with ambient background
**Steps:**
1. Upload a CSV and reach the Clean & Export panel
2. Inspect the outer card element CSS
**Expected Result:** The Clean & Export card has `background: transparent` and `box-shadow: none`.
**Automation Hint:** `page.evaluate("getComputedStyle(document.querySelector('.sc-card, .shap-panel')).backgroundColor")` — assert `"rgba(0, 0, 0, 0)"`
**Source:** Part56, Part57

---

### TC-P4-023
**Category:** Bug-Regression
**Test Name:** Left-anchor bars for outlier % (not center-anchored)
**Steps:**
1. Upload a CSV with outlier columns
2. Inspect the outlier bar rows in Clean & Export
**Expected Result:** Outlier % bars are left-anchored (fill from left edge), not center-anchored.
**Automation Hint:** Assert `.shap-bar-center` divider is absent from outlier rows; the fill element starts at `left: 0%` not `left: 50%`
**Source:** Part59

---

### TC-P4-024
**Category:** Bug-Regression
**Test Name:** Left-anchor bars for missing % (not center-anchored)
**Steps:**
1. Upload a CSV with columns having missing values
2. Inspect the imputation/missing-% bar rows in Clean & Export
**Expected Result:** Missing % bars are left-anchored.
**Automation Hint:** Same as TC-P4-023 — check absence of `.shap-bar-center` in imputation rows
**Source:** Part59

---

### TC-P4-025
**Category:** UI
**Test Name:** Skew bars remain center-anchored (bidirectional)
**Steps:**
1. Upload a CSV with both positively and negatively skewed columns
2. Inspect skew bar rows
**Expected Result:** Skew bars are center-anchored. Negative skew bars extend leftward from center; positive skew bars extend rightward.
**Automation Hint:** Assert `.shap-bar-center` divider IS present in skew rows
**Source:** Part59

---

### TC-P4-026
**Category:** Bug-Regression
**Test Name:** Drop-column rows have no red-tinted background (transparent style)
**Steps:**
1. Upload a CSV with auto-detected ID columns
2. Inspect the "Columns to drop" rows
**Expected Result:** Drop-column rows have no `background: rgba(248,113,113,...)` or red border. Rows are transparent with column name in red text only.
**Automation Hint:** `page.evaluate("getComputedStyle(document.querySelector('#sc-dropcol-list .shap-row')).backgroundColor")` — assert transparent/none
**Source:** Part58

---

### TC-P4-027
**Category:** Bug-Regression
**Test Name:** Dynamically-added drop column rows match transparent style
**Steps:**
1. Upload a CSV
2. In the "Columns to drop" section, use the dropdown to manually add a column
3. Inspect the newly added row
**Expected Result:** The manually-added row has the same transparent layout as template rows.
**Automation Hint:** `page.select_option('#sc-dropcol-dropdown', 'SomeColumn')` then click add — assert new row has no background color
**Source:** Part58

---

### TC-P4-028
**Category:** UI
**Test Name:** Bar row gap increased — bars have breathing room (not dense block)
**Steps:**
1. Upload a CSV with multiple outlier/missing columns
2. Inspect the bar container spacing
**Expected Result:** Individual bar rows have visible vertical gap of approximately `0.5rem`.
**Automation Hint:** `page.evaluate("getComputedStyle(document.querySelector('.sc-bar-container')).gap")` — assert value >= "0.5rem"
**Source:** Part58

---

### TC-P4-029
**Category:** E2E
**Test Name:** Home page loads with correct title
**Steps:**
1. Navigate to the app root URL
2. Check the page title
**Expected Result:** Page title is present and not empty/default.
**Automation Hint:** `assert "ML" in page.title()`
**Source:** Part59, Part61

---

### TC-P4-030
**Category:** E2E
**Test Name:** Sidebar has supervised model buttons
**Steps:**
1. Navigate to the app root
2. Wait for models to load
3. Check sidebar for supervised model buttons
**Expected Result:** At least one supervised model button is visible in the sidebar.
**Automation Hint:** `page.locator('.model-btn').count() >= 1`
**Source:** Part59, Part61

---

### TC-P4-031
**Category:** E2E
**Test Name:** Sidebar has unsupervised tools buttons
**Steps:**
1. Navigate to the app root
2. Wait for models to load
3. Check sidebar for unsupervised tools
**Expected Result:** At least one unsupervised tool button is visible.
**Automation Hint:** `page.locator('[data-category="unsupervised"]').count() >= 1`
**Source:** Part59, Part61

---

### TC-P4-032
**Category:** E2E
**Test Name:** Sidebar has data tools buttons
**Steps:**
1. Navigate to the app root
2. Check sidebar for data tools section
**Expected Result:** At least one data tool button (e.g. EDA, Clean & Export) is visible.
**Automation Hint:** `page.locator('[data-category="data"]').count() >= 1`
**Source:** Part59, Part61

---

### TC-P4-033
**Category:** E2E
**Test Name:** Empty state shown on initial load (no model selected)
**Steps:**
1. Navigate to the app root
2. Do not click any model
3. Check the main content area
**Expected Result:** An empty/welcome state is shown in the main content area before any model is selected.
**Automation Hint:** `page.locator('#emptyState, [data-testid="empty-state"]').is_visible()`
**Source:** Part59, Part61

---

### TC-P4-034
**Category:** E2E
**Test Name:** Iris predict returns a result
**Steps:**
1. Navigate to the app
2. Select the Iris model
3. Fill all input fields with valid sample values
4. Click "Predict"
5. Wait up to 15 seconds
**Expected Result:** `#resultState` becomes visible. A prediction label is displayed.
**Automation Hint:** `page.locator('#resultState').wait_for(state='visible', timeout=15000)`
**Source:** Part59, Part61

---

### TC-P4-035
**Category:** E2E
**Test Name:** Iris predict shows species name in result
**Steps:**
1. Select the Iris model
2. Fill sample values for a setosa specimen
3. Click "Predict"
4. Wait for result
**Expected Result:** The result label contains a recognized Iris species name (setosa, versicolor, or virginica).
**Automation Hint:** `assert any(s in page.locator('#resultLabel').inner_text() for s in ['setosa','versicolor','virginica'])`
**Source:** Part59, Part61

---

### TC-P4-036
**Category:** E2E
**Test Name:** Iris predict shows SHAP feature impact bars
**Steps:**
1. Select the Iris model
2. Fill sample values
3. Click "Predict"
4. Wait for SHAP panel to render
**Expected Result:** `.shap-bar-fill` elements appear inside `#shapBody`. SHAP bars are non-zero.
**Automation Hint:** `page.locator('#shapBody .shap-bar-fill').wait_for(timeout=30000)`
**Source:** Part59, Part61

---

### TC-P4-037
**Category:** E2E
**Test Name:** Titanic predict returns a result
**Steps:**
1. Select the Titanic model
2. Fill all input fields with valid values
3. Click "Predict"
4. Wait up to 15 seconds
**Expected Result:** `#resultState` becomes visible with a survived/not-survived prediction.
**Automation Hint:** `page.locator('#resultState').wait_for(state='visible', timeout=15000)`
**Source:** Part59, Part61

---

### TC-P4-038
**Category:** E2E
**Test Name:** Diabetes predict returns a result
**Steps:**
1. Select the Diabetes model
2. Fill all 8 fields
3. Click "Predict"
4. Wait up to 15 seconds
**Expected Result:** `#resultState` becomes visible with a diabetic/non-diabetic prediction.
**Automation Hint:** Fill each field via `page.fill()` (not JS evaluate); `page.locator('#resultState').wait_for(state='visible', timeout=15000)`
**Source:** Part59, Part60, Part61

---

### TC-P4-039
**Category:** E2E
**Test Name:** Drift tab opens for Iris model
**Steps:**
1. Select the Iris model
2. Click the "Drift" tab
**Expected Result:** The Drift panel becomes visible/active.
**Automation Hint:** `page.click('[data-tab="drift"]')` then `page.locator('#driftPanel, .drift-container').wait_for(state='visible')`
**Source:** Part59, Part61

---

### TC-P4-040
**Category:** E2E
**Test Name:** Drift upload renders metrics for Iris
**Steps:**
1. Select the Iris model
2. Navigate to Drift tab
3. Upload an Iris-format CSV
4. Wait for response
**Expected Result:** Drift metrics section renders — distance scores or p-values are shown for at least one feature.
**Automation Hint:** `page.locator('.drift-summary, .drift-metric').wait_for(state='visible', timeout=15000)`
**Source:** Part59, Part61

---

### TC-P4-041
**Category:** E2E
**Test Name:** Drift upload shows Iris column metrics (not stale model's fields)
**Steps:**
1. Select the Iris model
2. Upload an Iris CSV to the Drift tab
3. Check which feature names appear in the drift result
**Expected Result:** Drift result shows Iris feature names (sepal_length, sepal_width, petal_length, petal_width).
**Automation Hint:** `page.locator('.drift-feature-label').first().inner_text()` — assert one of the four Iris field names
**Source:** Part59, Part60, Part61

---

### TC-P4-042
**Category:** Bug-Regression
**Test Name:** Playwright --headed flag actually opens a visible browser window
**Steps:**
1. Run `pytest tests/e2e/ --headed`
2. Observe whether a browser window opens
**Expected Result:** A Chromium browser window opens and tests run visibly.
**Automation Hint:** Manual verification; assert `pytestconfig.getoption("--headed")` is used in the `browser_session` fixture and `headless=not headed` is passed
**Source:** Part61

---

### TC-P4-043
**Category:** Bug-Regression
**Test Name:** --slowmo flag controls interaction speed
**Steps:**
1. Run `pytest tests/e2e/ --headed --slowmo 800`
2. Observe browser interactions
**Expected Result:** Browser interactions are slowed by ~800ms each.
**Automation Hint:** Assert `pytestconfig.getoption("--slowmo")` is wired to `slow_mo` parameter in `pw.chromium.launch(headless=not headed, slow_mo=800)`
**Source:** Part61

---

### TC-P4-044
**Category:** Bug-Regression
**Test Name:** Model selection uses activeModel check to avoid race
**Steps:**
1. Start the app (diabetes model auto-selected)
2. Programmatically select the Iris model in tests
3. Verify Iris fields are shown, not diabetes fields
**Expected Result:** `_select_model` correctly waits for `activeModel?.id === 'iris'` before filling fields.
**Automation Hint:** `page.wait_for_function("activeModel?.id === 'iris'")` — assert passes without timeout
**Source:** Part61

---

### TC-P4-045
**Category:** Bug-Regression
**Test Name:** Form fill uses page.fill() not JS evaluate (avoids input validation clearing)
**Steps:**
1. Select the Diabetes model
2. Fill BMI field with value `33.6` using Playwright's `page.fill()`
3. Click Predict
**Expected Result:** Predict fires with BMI=33.6. Result is returned.
**Automation Hint:** `page.fill('#field-BMI', '33.6')` — assert `page.input_value('#field-BMI') == '33.6'` before clicking predict
**Source:** Part60

---

### TC-P4-046
**Category:** Backend API
**Test Name:** POST /eda/clean — dedup removes duplicate rows
**Steps:**
1. POST to `/eda/clean` with a CSV containing 3 duplicate rows and `{"dedup": true}`
2. Check response
**Expected Result:** Response `summary.rows_after = rows_before - 3`. Downloaded CSV has no duplicate rows.
**Automation Hint:** `pytest` — `requests.post(EDA_URL+'/eda/clean', files={'file': csv_bytes}, data={'config': json.dumps({'dedup': True})})`; assert `resp.json()['summary']['rows_after'] == expected`
**Source:** Part55, Part56

---

### TC-P4-047
**Category:** Backend API
**Test Name:** POST /eda/clean — drop_cols drops specified columns
**Steps:**
1. POST to `/eda/clean` with a 5-column CSV and `{"drop_cols": ["PassengerId"]}`
**Expected Result:** Downloaded CSV has 4 columns. `summary.cols_dropped` contains "PassengerId".
**Automation Hint:** `pytest` — parse response CSV; assert `"PassengerId" not in response_df.columns`
**Source:** Part55, Part56

---

### TC-P4-048
**Category:** Backend API
**Test Name:** POST /eda/clean — column-specific imputation via imputation.cols
**Steps:**
1. POST to `/eda/clean` with a CSV where columns A and B have missing values, but only column A is in `imputation.cols`
**Expected Result:** Column A is imputed. Column B retains its missing values in the output CSV.
**Automation Hint:** `pytest` — parse response CSV; assert `response_df['A'].isna().sum() == 0` and `response_df['B'].isna().sum() > 0`
**Source:** Part56

---

### TC-P4-049
**Category:** Backend API
**Test Name:** POST /eda/clean — power_transform accepts dict form {enabled, cols}
**Steps:**
1. POST to `/eda/clean` with `{"power_transform": {"enabled": true, "cols": ["colA"]}}`
**Expected Result:** Yeo-Johnson transform applied to colA only. Summary reflects transformation.
**Automation Hint:** `pytest` — assert response CSV colA distribution differs from input
**Source:** Part56

---

### TC-P4-050
**Category:** Bug-Regression
**Test Name:** POST /eda/clean — 404 Not Found no longer returned (ml-eda included in CI/deploy)
**Steps:**
1. Push a change to `main` branch
2. Confirm CI deploys ml-eda
3. POST to `/eda/clean` with a CSV
**Expected Result:** HTTP 200 response (not 404). The `/eda/clean` route is live.
**Automation Hint:** `requests.post(EDA_URL+'/eda/clean', ...)` — assert `status_code != 404`
**Source:** Part62

---

### TC-P4-051
**Category:** Feature
**Test Name:** ml-eda included in CI lint step
**Steps:**
1. Introduce a ruff lint error in `services/ml-eda/app.py`
2. Push to main
**Expected Result:** CI `test` job fails at the `ruff check services/ml-eda/app.py` step.
**Automation Hint:** Check `.github/workflows/ci.yml` contains `ruff check services/ml-eda/`; GitHub Actions integration test
**Source:** Part62

---

### TC-P4-052
**Category:** Feature
**Test Name:** ml-eda included in CI pytest step (35 tests run)
**Steps:**
1. Push to main
2. Check GitHub Actions `test` job
**Expected Result:** `pytest services/ml-eda/tests/` runs and reports 35 passed.
**Automation Hint:** GitHub Actions log assertion — `35 passed` in pytest output for ml-eda step
**Source:** Part62

---

### TC-P4-053
**Category:** Bug-Regression
**Test Name:** Numeric imputation dropdown applies only numeric methods
**Steps:**
1. Upload a CSV with both numeric and categorical missing columns
2. In the imputation section, check the numeric dropdown options
**Expected Result:** Numeric dropdown (`sc-impute-num`) offers: None, Median, Mean, KNN (k=5), MICE, Interpolate, Forward fill, Backward fill, Constant. Categorical options NOT in numeric dropdown.
**Automation Hint:** `page.locator('#sc-impute-num option').all_inner_texts()` — assert contains "Median" but not "Mode"
**Source:** Part62

---

### TC-P4-054
**Category:** Bug-Regression
**Test Name:** Categorical imputation dropdown applies only categorical methods
**Steps:**
1. Upload a CSV with categorical missing columns
2. Check the categorical imputation dropdown options
**Expected Result:** Categorical dropdown offers: None, Mode, Constant, Forward fill, Backward fill. Numeric-only methods NOT in categorical dropdown.
**Automation Hint:** `page.locator('#sc-impute-cat option').all_inner_texts()` — assert contains "Mode" but not "Mean"
**Source:** Part62

---

### TC-P4-055
**Category:** Backend API
**Test Name:** POST /eda/clean — numeric_method + cat_method handled separately
**Steps:**
1. POST to `/eda/clean` with `{"imputation": {"numeric_method": "median", "cat_method": "mode", "cols": [...]}}`
**Expected Result:** Numeric columns imputed with median; categorical columns imputed with mode. No error.
**Automation Hint:** `pytest` — create mixed-type CSV; assert numeric NaN count = 0 and categorical NaN count = 0 in response CSV
**Source:** Part62

---

### TC-P4-056
**Category:** Feature
**Test Name:** Clean & Export submit shows animated progress bar (not spinner text)
**Steps:**
1. Upload a CSV, configure clean options
2. Click "Clean & Download CSV"
3. Observe the area below the button
**Expected Result:** An animated progress bar appears (not just "Processing…" text). Stages cycle through phases. Progress bar hides after completion.
**Automation Hint:** `page.locator('#sc-progress')` is visible after button click; assert label text is not just "Processing…"
**Source:** Part62

---

### TC-P4-057
**Category:** Bug-Regression
**Test Name:** Clean & Export header shows filename prominently (not faint right-aligned text)
**Steps:**
1. Upload "Titanic-Dataset.csv" to Clean & Export
2. Inspect the panel header
**Expected Result:** Filename "Titanic-Dataset.csv" is visible below the panel title in cyan (`#22d3ee`), `font-weight: 600`, not faint.
**Automation Hint:** `page.locator('.sc-filename, [data-testid="sc-filename"]').inner_text()` — assert "Titanic-Dataset.csv"; check color is cyan
**Source:** Part63

---

### TC-P4-058
**Category:** Bug-Regression
**Test Name:** Long filename truncates with ellipsis and shows full name on hover
**Steps:**
1. Upload a file with a very long filename (> 340px rendered width)
2. Inspect the filename display
**Expected Result:** Filename is truncated with ellipsis. Hovering shows the full filename via `title` attribute.
**Automation Hint:** `page.locator('.sc-filename').get_attribute('title')` — assert equals the full filename string
**Source:** Part63

---

### TC-P4-059
**Category:** Feature
**Test Name:** Duplicate rows collapsible table — "Show duplicate rows" link appears when dupes exist
**Steps:**
1. Upload a CSV with known duplicate rows
2. Wait for analysis
3. Check the duplicate rows section
**Expected Result:** A "Show duplicate rows" toggle/link appears below the count badge.
**Automation Hint:** `page.locator('[data-testid="sc-show-dupes"], .sc-dupes-toggle').is_visible()` — assert True
**Source:** Part65

---

### TC-P4-060
**Category:** Feature
**Test Name:** Duplicate rows table shows correct rows on toggle click
**Steps:**
1. Upload a CSV with 6 duplicate rows
2. Click "Show duplicate rows"
3. Count rows in the expanded table
**Expected Result:** Exactly 6 rows appear in the table (the rows that would be removed, using `keep='first'`).
**Automation Hint:** `page.click('.sc-dupes-toggle')` then `page.locator('.sc-dupes-table tr').count()` — assert == 6 (plus 1 header)
**Source:** Part65

---

### TC-P4-061
**Category:** Bug-Regression
**Test Name:** Duplicate rows count matches table row count (keep='first' fix)
**Steps:**
1. Upload a CSV where a row appears 3 times (so 2 duplicates)
2. Check the badge count and the table row count
**Expected Result:** Badge says "2 found" and table contains exactly 2 rows.
**Automation Hint:** `badge_count = int(page.locator('.sc-dedup-badge').inner_text().split()[0])` — assert equals `page.locator('.sc-dupes-table tbody tr').count()`
**Source:** Part65

---

### TC-P4-062
**Category:** Feature
**Test Name:** Duplicate rows table is horizontally scrollable for wide datasets
**Steps:**
1. Upload a CSV with many columns (>10) and duplicate rows
2. Toggle the duplicate rows display
**Expected Result:** The table container is horizontally scrollable. No content is clipped.
**Automation Hint:** `page.locator('.sc-dupes-table-container').evaluate("el => el.scrollWidth > el.clientWidth")` — assert True for wide CSVs
**Source:** Part65

---

### TC-P4-063
**Category:** Feature
**Test Name:** Duplicate rows table truncated at 50 with note
**Steps:**
1. Upload a CSV with 120 duplicate rows
2. Toggle duplicate rows display
**Expected Result:** Table shows exactly 50 rows with a note such as "showing first 50 of 120".
**Automation Hint:** `page.locator('.sc-dupes-table tbody tr').count()` — assert == 50; `page.locator('.sc-dupes-truncate-note').inner_text()` — assert contains "50 of 120"
**Source:** Part65

---

### TC-P4-064
**Category:** Feature
**Test Name:** Null values in duplicate rows table render as italic grey "null"
**Steps:**
1. Upload a CSV with duplicate rows containing null values
2. Toggle duplicate rows display
**Expected Result:** Null values in the table are displayed as italic grey "null" text, not as empty cells or "None".
**Automation Hint:** `page.locator('.sc-dupes-table td.null-val, .sc-dupes-table td i').first().inner_text()` — assert "null"
**Source:** Part65

---

### TC-P4-065
**Category:** Feature
**Test Name:** Model quality gate — CI model-quality job runs as parallel non-blocking job
**Steps:**
1. Push a change to main
2. Check GitHub Actions workflow
**Expected Result:** A `model-quality` job runs in parallel with the `test` job. The `deploy` job only requires `test`. A quality gate failure does not block deploy.
**Automation Hint:** Inspect `.github/workflows/ci.yml` — assert `model-quality` job has `continue-on-error: true` and `deploy` job has `needs: [test]`
**Source:** Part65

---

### TC-P4-066
**Category:** Feature
**Test Name:** Quality gate script scores Iris model above threshold
**Steps:**
1. Run `python scripts/check_model_quality.py` locally
2. Check output for Iris
**Expected Result:** Iris classification accuracy >= 80% on holdout. Script prints "PASS" for iris.
**Automation Hint:** `pytest` — `subprocess.run(['python', 'scripts/check_model_quality.py'])` — assert `returncode == 0`; check stdout for "PASS iris"
**Source:** Part65

---

### TC-P4-067
**Category:** Feature
**Test Name:** Quality gate script scores Insurance model within MAE threshold
**Steps:**
1. Run `python scripts/check_model_quality.py`
**Expected Result:** Insurance model MAE <= 100. Script prints "PASS" for insurance.
**Automation Hint:** Assert stdout contains "PASS insurance" and MAE value <= 100
**Source:** Part65

---

### TC-P4-068
**Category:** Feature
**Test Name:** Quality gate script exits non-zero when any model fails threshold
**Steps:**
1. Temporarily lower the iris threshold to 99% in `check_model_quality.py`
2. Run the script
**Expected Result:** Script exits with code 1. At least one model shows "FAIL" in output.
**Automation Hint:** `result = subprocess.run([...])` — assert `result.returncode == 1` and "FAIL" in `result.stdout`
**Source:** Part65

---

### TC-P4-069
**Category:** Backend API
**Test Name:** GET /eda returns duplicate_rows field in response
**Steps:**
1. POST a CSV with duplicate rows to `/eda`
2. Check the response JSON
**Expected Result:** Response JSON contains `duplicate_rows` key with an array of row objects (the extra copies, up to 50).
**Automation Hint:** `resp = requests.post(EDA_URL+'/eda', files={'file': csv_with_dupes}); assert 'duplicate_rows' in resp.json()`
**Source:** Part65

---

### TC-P4-070
**Category:** Backend API
**Test Name:** /eda duplicate_rows uses keep='first' — contains only rows-to-be-removed
**Steps:**
1. POST a CSV where row X appears 3 times
2. Check `duplicate_rows` in response
**Expected Result:** `duplicate_rows` contains exactly 2 entries (the 2nd and 3rd occurrences), not 3 (all copies).
**Automation Hint:** `assert len(resp.json()['duplicate_rows']) == 2`
**Source:** Part65

---

### TC-P4-071
**Category:** E2E
**Test Name:** Clean & Export tests skipped gracefully when ML_EDA_URL not set
**Steps:**
1. Ensure `ML_EDA_URL` env var is not set
2. Run `pytest tests/e2e/test_clean.py`
**Expected Result:** All 4 clean tests are reported as SKIPPED, not failed or errored.
**Automation Hint:** `pytest tests/e2e/test_clean.py -v` — assert all results are `SKIPPED`
**Source:** Part59, Part61

---

### TC-P4-072
**Category:** Backend API
**Test Name:** Server returns 404 for unknown model on predict
**Steps:**
1. POST to `/predict/nonexistentmodel` (before or after background thread finishes loading)
**Expected Result:** HTTP 404 Not Found response. Server does not crash.
**Automation Hint:** `requests.post(url+'/predict/nonexistent', json={})` — assert `status_code == 404`
**Source:** Part57

---

### TC-P4-073
**Category:** Feature
**Test Name:** CI three-service lint+test pipeline runs on push to main
**Steps:**
1. Push any change to main
2. Check GitHub Actions
**Expected Result:** CI `test` job runs ruff lint and pytest for all three services: ml-api, ml-vision, ml-eda.
**Automation Hint:** Inspect `.github/workflows/ci.yml` — assert three `ruff check` and three `pytest` commands exist
**Source:** Part62

---

### TC-P4-074
**Category:** Data
**Test Name:** Iris holdout fixture — 30 rows, 10 per class
**Steps:**
1. Load `services/ml-api/tests/fixtures/iris_holdout.csv`
2. Check row counts per class
**Expected Result:** 30 total rows, 10 setosa, 10 versicolor, 10 virginica.
**Automation Hint:** `pytest` — `pd.read_csv('...iris_holdout.csv')['target'].value_counts()` — assert all three classes have count == 10
**Source:** Part65

---

### TC-P4-075
**Category:** Data
**Test Name:** Diabetes holdout fixture — 30 rows with true labels
**Steps:**
1. Load `services/ml-api/tests/fixtures/diabetes_holdout.csv`
2. Check structure
**Expected Result:** 30 rows, 8 feature columns, 1 label column with binary (0/1) values.
**Automation Hint:** `df = pd.read_csv('...diabetes_holdout.csv'); assert len(df) == 30; assert df['Outcome'].isin([0,1]).all()`
**Source:** Part65

---

### TC-P4-076
**Category:** Backend API
**Test Name:** POST /eda/clean — summary JSON included in response
**Steps:**
1. POST to `/eda/clean` with dedup, drop, and imputation options
2. Check response
**Expected Result:** Response JSON contains `summary` with fields: `rows_before`, `rows_after`, `cols_dropped`, `missing_before`, `missing_after`, `outliers_removed`.
**Automation Hint:** `resp.json()['summary'].keys()` — assert all 6 keys present
**Source:** Part55

---

### TC-P4-077
**Category:** Backend API
**Test Name:** POST /eda/clean — slow methods (KNN, MICE) return results without timeout
**Steps:**
1. POST to `/eda/clean` with a 100-row numeric CSV and `{"imputation": {"numeric_method": "knn", "knn_k": 5}}`
2. Wait up to 60 seconds
**Expected Result:** HTTP 200 response with cleaned CSV. No 500 error or timeout.
**Automation Hint:** `resp = requests.post(EDA_URL+'/eda/clean', ..., timeout=60)` — assert `status_code == 200`
**Source:** Part55

---

### TC-P4-078
**Category:** Feature
**Test Name:** EDA bars animate into view on scroll (IntersectionObserver)
**Steps:**
1. Upload a large CSV and run EDA
2. Scroll down to bring a collapsed section card into view
**Expected Result:** SHAP-style bars in that section animate (fill from zero to their value) when the card scrolls into viewport.
**Automation Hint:** `page.evaluate("document.querySelector('.shap-bar-fill').style.width")` before and after scroll — assert width changes from "0%" to a non-zero value
**Source:** Part56

---

### TC-P4-079
**Category:** Feature
**Test Name:** CI model-quality job runs as parallel non-blocking job
**Steps:**
1. Push any change to main
2. Check GitHub Actions workflow structure
**Expected Result:** `model-quality` job runs alongside `test` job; does not block deploy
**Automation Hint:** Check `needs` key in workflow YAML
**Source:** Part65

---

### TC-P4-080
**Category:** Feature
**Test Name:** Titanic holdout fixture — 30 rows with true survival labels
**Steps:**
1. Load `services/ml-api/tests/fixtures/titanic_holdout.csv`
2. Check structure
**Expected Result:** 30 rows, Titanic feature columns, 1 Survived label column with binary values.
**Automation Hint:** `df = pd.read_csv('...titanic_holdout.csv'); assert len(df) == 30; assert df['Survived'].isin([0,1]).all()`
**Source:** Part65

---

### TC-P4-081
**Category:** Feature
**Test Name:** Insurance holdout fixture — 15 rows with regression baseline labels
**Steps:**
1. Load `services/ml-api/tests/fixtures/insurance_holdout.csv`
2. Check structure
**Expected Result:** 15 rows with insurance feature columns and a baseline prediction column.
**Automation Hint:** `df = pd.read_csv('...insurance_holdout.csv'); assert len(df) == 15`
**Source:** Part65

---

### TC-P4-082
**Category:** Backend API
**Test Name:** POST /eda/clean — legacy 'method' key still works (backward compat)
**Steps:**
1. POST to `/eda/clean` with `{"imputation": {"method": "mean"}}`
**Expected Result:** HTTP 200. Mean imputation applied to numeric columns. No KeyError raised.
**Automation Hint:** `pytest` — `assert resp.status_code == 200`
**Source:** Part62

---

### TC-P4-083
**Category:** Feature
**Test Name:** Quality gate script scores Diabetes model above threshold
**Steps:**
1. Run `python scripts/check_model_quality.py`
**Expected Result:** Diabetes model accuracy >= 70% on holdout. Script prints "PASS" for diabetes.
**Automation Hint:** Assert stdout contains "PASS diabetes" and accuracy value >= 0.70
**Source:** Part65

---

### TC-P4-084
**Category:** Feature
**Test Name:** Quality gate script scores Titanic model above threshold
**Steps:**
1. Run `python scripts/check_model_quality.py`
**Expected Result:** Titanic model accuracy >= 70% on holdout. Script prints "PASS" for titanic.
**Automation Hint:** Assert stdout contains "PASS titanic" and accuracy >= 0.70
**Source:** Part65

---

### TC-P4-085
**Category:** Backend API
**Test Name:** POST /eda/clean — backward compat: drop_id_cols accepted as alias for drop_cols
**Steps:**
1. POST to `/eda/clean` with `{"drop_id_cols": ["PassengerId"]}`
**Expected Result:** Same behavior as `drop_cols` — PassengerId column is dropped.
**Automation Hint:** `pytest` — assert same response structure as TC-P4-047 but using `drop_id_cols` key
**Source:** Part56

---

### TC-P4-086
**Category:** Feature
**Test Name:** ml-eda deploy triggered by CI when RENDER_EDA_DEPLOY_HOOK_URL secret is set
**Steps:**
1. Set `RENDER_EDA_DEPLOY_HOOK_URL` in GitHub Secrets
2. Push to main
3. Check GitHub Actions deploy job
**Expected Result:** CI deploy job calls the ml-eda Render deploy hook.
**Automation Hint:** Verify deploy step in `.github/workflows/ci.yml` calls the hook URL when env var is set
**Source:** Part62

---

### TC-P4-087
**Category:** Backend API
**Test Name:** POST /eda/clean — column-specific outlier removal via outliers.cols
**Steps:**
1. POST to `/eda/clean` with numeric columns C (outliers) and D (outliers), only C in `outliers.cols`
**Expected Result:** Column C has outliers removed. Column D is unchanged.
**Automation Hint:** `pytest` — compare outlier count before/after for each column
**Source:** Part56

---

### TC-P4-088
**Category:** Backend API
**Test Name:** POST /eda/clean — power_transform backward compat with plain bool
**Steps:**
1. POST to `/eda/clean` with `{"power_transform": true}`
**Expected Result:** Yeo-Johnson applied to all numeric columns. No error raised.
**Automation Hint:** `pytest` — assert `resp.status_code == 200` and `resp.json()['summary']` is present
**Source:** Part56

---

### TC-P4-089
**Category:** Feature
**Test Name:** Broom SVG icon used in Clean & Export header (not emoji)
**Steps:**
1. Open Clean & Export panel
2. Inspect the panel title markup
**Expected Result:** An inline SVG broom icon appears next to "Clean & Export" title text. No 🧹 emoji present.
**Automation Hint:** `page.locator('.shap-header svg').count() >= 1`; assert `page.locator('.shap-title').inner_html()` contains `<svg`
**Source:** Part63

---

### TC-P4-090
**Category:** Feature
**Test Name:** File SVG icon used next to filename (not emoji)
**Steps:**
1. Open Clean & Export panel with a file uploaded
2. Inspect the filename markup
**Expected Result:** An inline SVG file/document icon appears next to the filename. No 📄 emoji present.
**Automation Hint:** `page.locator('[data-testid="sc-filename"] svg').count() >= 1`; assert no emoji character in `inner_html()`
**Source:** Part63
