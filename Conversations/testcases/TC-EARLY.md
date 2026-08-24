# TC-EARLY — Early Conversations Test Cases (Pre-Part-Numbering, May 30–31)

Source: Conversation.md + Conversation_2026-05-30_*.md + Conversation_2026-05-31_*.md
Total: 60 test cases

---

### TC-EARLY-001
**Category:** Bug-Regression
**Test Name:** JS literal newline in single-quoted string does not break script
**Steps:**
1. Load the generated `index.html` in a browser (or open browser DevTools console)
2. Check the JavaScript console for syntax errors on page load
**Expected Result:** No JS SyntaxError; page loads and `checkServer()` runs without exceptions
**Automation Hint:** `page.goto(url); const errors = []; page.on('pageerror', e => errors.push(e)); await page.waitForLoadState('networkidle'); expect(errors).toHaveLength(0);`
**Source:** Conversation.md (commit `5ede74c`)

---

### TC-EARLY-002
**Category:** Bug-Regression
**Test Name:** `_fmt()` function defined before use — no TypeError masked as network error
**Steps:**
1. Open the Iris/Titanic/Diabetes predictor page
2. Enter valid feature values and click Predict
3. Observe the result panel
**Expected Result:** Prediction result and class labels appear correctly; no "cannot reach API server" error when the server is reachable
**Automation Hint:** `page.locator('#predictBtn').click(); await page.locator('#resVal').waitFor(); expect(page.locator('#resVal').textContent()).not.toContain('cannot reach');`
**Source:** Conversation.md (commit `dcbb6d8`)

---

### TC-EARLY-003
**Category:** Bug-Regression
**Test Name:** Empty form submission is blocked — does not return a prediction
**Steps:**
1. Open the predictor page
2. Do not fill in any fields
3. Click the Predict button (if enabled)
**Expected Result:** The form is not submitted; browser shows `required` field validation or the JS guard fires; no prediction result is shown
**Automation Hint:** `await page.locator('#predictBtn').click(); expect(page.locator('#resVal')).not.toBeVisible();` Also assert all inputs have `required` attribute.
**Source:** Conversation.md (commit `6db639f`)

---

### TC-EARLY-004
**Category:** Bug-Regression
**Test Name:** Browser-autofilled inputs do not appear white (dark styling override)
**Steps:**
1. Open the Titanic predictor page
2. Let the browser autofill fields (or simulate via DevTools)
3. Inspect the rendered background color of autofilled inputs
**Expected Result:** Autofilled inputs show dark background consistent with the glassmorphism theme, not plain white
**Automation Hint:** `page.evaluate("window.getComputedStyle(document.querySelector('input'), ':-webkit-autofill').getPropertyValue('background-color')")` — assert result is not `rgb(255, 255, 255)`
**Source:** Conversation.md (commit `73f25b1`)

---

### TC-EARLY-005
**Category:** Bug-Regression
**Test Name:** Server status bar recovers after mid-session timeout — health poll restarts
**Steps:**
1. Open the predictor page; wait for green server dot
2. Simulate server offline (stop uvicorn or block network)
3. Wait for the status bar to show red/offline
4. Restart the server
5. Wait ≤ 10 seconds
**Expected Result:** Status dot turns green again automatically; Predict button re-enables
**Automation Hint:** Mock `/health` to return 503, then restore it. Assert `page.locator('#srvDot')` CSS changes from offline to online color within timeout.
**Source:** Conversation.md (commit `4de1e73`)

---

### TC-EARLY-006
**Category:** Feature
**Test Name:** GET /health returns `{"status":"ok"}` when model is loaded
**Steps:**
1. Start the FastAPI server
2. `GET /health`
**Expected Result:** HTTP 200, body `{"status":"ok"}` (minimum)
**Automation Hint:** `pytest: resp = client.get("/health"); assert resp.status_code == 200; assert resp.json()["status"] == "ok"`
**Source:** Conversation.md

---

### TC-EARLY-007
**Category:** Feature
**Test Name:** POST /predict returns prediction and feature_importance
**Steps:**
1. `POST /predict` with a valid JSON payload containing all required feature fields
**Expected Result:** HTTP 200; response JSON contains `prediction`, `probabilities` (classification), and `feature_importance` (list of `{"feature": str, "importance": float}`)
**Automation Hint:** `pytest: resp = client.post("/predict", json={...}); data = resp.json(); assert "feature_importance" in data; assert isinstance(data["feature_importance"], list)`
**Source:** Conversation_2026-05-30_13-33.md (commit `88f1e85`)

---

### TC-EARLY-008
**Category:** Backend API
**Test Name:** GET /importance returns feature importance list with values 0–1
**Steps:**
1. `GET /importance`
**Expected Result:** HTTP 200; JSON list of objects, each with `feature` (string) and `importance` (float 0–1); list is non-empty
**Automation Hint:** `pytest: resp = client.get("/importance"); data = resp.json(); assert len(data) > 0; assert all(0 <= item["importance"] <= 1 for item in data)`
**Source:** Conversation_2026-05-30_13-33.md

---

### TC-EARLY-009
**Category:** Backend API
**Test Name:** POST /predict/upload accepts CSV and returns batch predictions with correct count
**Steps:**
1. Prepare a valid CSV file matching the model's feature columns (without target column)
2. `POST /predict/upload` with `multipart/form-data`
**Expected Result:** HTTP 200; JSON with keys `count` (integer) and `predictions` (list); `count` matches the number of rows in the CSV
**Automation Hint:** `pytest: with open("test_batch.csv", "rb") as f: resp = client.post("/predict/upload", files={"file": ("test.csv", f, "text/csv")}); assert resp.json()["count"] == expected_rows`
**Source:** Conversation.md / Conversation_2026-05-30_13-33.md

---

### TC-EARLY-010
**Category:** Backend API
**Test Name:** POST /predict/upload rejects non-CSV files with HTTP 400
**Steps:**
1. `POST /predict/upload` with a `.txt` or `.json` file
**Expected Result:** HTTP 400 error response
**Automation Hint:** `pytest: resp = client.post("/predict/upload", files={"file": ("bad.txt", b"not csv", "text/plain")}); assert resp.status_code == 400`
**Source:** Conversation.md

---

### TC-EARLY-011
**Category:** Feature
**Test Name:** Key Factors bar chart displays feature labels without `num__` / `cat__` prefix
**Steps:**
1. Submit a prediction on any predictor page
2. Inspect the Key Factors bar labels in the results panel
**Expected Result:** Labels show clean feature names (e.g. "Annual Income", not "num__annual_income")
**Automation Hint:** `const labels = await page.locator('#fiBars span').allTextContents(); labels.forEach(l => expect(l).not.toMatch(/^(num|cat)[\s_]/i));`
**Source:** Conversation_2026-05-30_13-33.md (commit `0858a49`)

---

### TC-EARLY-012
**Category:** Bug-Regression
**Test Name:** Regression prediction shows exactly 2 decimal places
**Steps:**
1. On the Insurance predictor page, submit a valid prediction
2. Observe the prediction value displayed
**Expected Result:** Prediction is formatted to exactly 2 decimal places (e.g. `847.48`, not `847.4838291...`)
**Automation Hint:** `const val = await page.locator('#resVal').textContent(); expect(val).toMatch(/^\$?\d+\.\d{2}$/);`
**Source:** Conversation_2026-05-30_13-33.md (commit `0858a49`)

---

### TC-EARLY-013
**Category:** Feature
**Test Name:** ID columns (Id, PassengerId) are absent from the prediction form
**Steps:**
1. Open the Iris predictor page and inspect all form inputs
2. Open the Titanic predictor page and inspect all form inputs
**Expected Result:** `Id` field not present in Iris form; `PassengerId` field not present in Titanic form
**Automation Hint:** `expect(page.locator('input[name="Id"]')).not.toBeVisible(); expect(page.locator('input[name="PassengerId"]')).not.toBeVisible();`
**Source:** Conversation_2026-05-30_13-33.md (commits `68e2b53`, `da153bd`)

---

### TC-EARLY-014
**Category:** Backend API
**Test Name:** GET /ranges returns feature bounds with min, max, step for all numeric fields
**Steps:**
1. `GET /ranges`
**Expected Result:** HTTP 200; JSON object with one key per numeric feature; each value has `min`, `max`, `step` fields
**Automation Hint:** `pytest: resp = client.get("/ranges"); data = resp.json(); assert len(data) > 0; for f, v in data.items(): assert "min" in v`
**Source:** Conversation_2026-05-30_13-33.md

---

### TC-EARLY-015
**Category:** Feature
**Test Name:** What-if sliders are present for each numeric input field
**Steps:**
1. Open any predictor page
2. Inspect the DOM for slider elements alongside number inputs
**Expected Result:** Each `<input type="number">` has a corresponding `<input type="range">` injected by `initSliders()`
**Automation Hint:** `const numInputs = await page.locator('input[type="number"]').count(); const rangeInputs = await page.locator('input[type="range"]').count(); expect(rangeInputs).toBeGreaterThanOrEqual(numInputs);`
**Source:** Conversation_2026-05-30_13-33.md

---

### TC-EARLY-016
**Category:** Bug-Regression
**Test Name:** Sliders do NOT trigger auto-predict on drag — only button click predicts
**Steps:**
1. Open any predictor page
2. Drag a slider without clicking Predict
3. Wait 1 second
**Expected Result:** No network request to `POST /predict` is made; result panel does not update
**Automation Hint:** Intercept network: `page.route("**/predict", route => { throw new Error("unexpected predict call"); }); await page.locator('input[type="range"]').first().fill("50"); await page.waitForTimeout(600);` — no error thrown
**Source:** Conversation_2026-05-30_15-27.md (commit `da9f2f6`)

---

### TC-EARLY-017
**Category:** Bug-Regression
**Test Name:** Number inputs enforce min/max bounds — out-of-range value is clamped on blur
**Steps:**
1. Open any predictor page after `/ranges` is loaded
2. Type a value below the minimum for a field (e.g. `-5` for Age)
3. Click elsewhere (blur the field)
**Expected Result:** Field value is clamped to the minimum valid value
**Automation Hint:** `await page.locator('input[name="Age"]').fill("-5"); await page.locator('body').click(); expect(await page.locator('input[name="Age"]').inputValue()).toBe("18");`
**Source:** Conversation_2026-05-30_15-27.md

---

### TC-EARLY-018
**Category:** Feature
**Test Name:** Annual Income field has no upper bound — values above dataset max are accepted
**Steps:**
1. On the Insurance predictor page, type `300000` into the Annual Income field
2. Tab away (blur)
**Expected Result:** Value remains `300000` — not clamped; no validation error
**Automation Hint:** `await page.locator('input[name="Annual Income"]').fill("300000"); await page.locator('body').click(); expect(await page.locator('input[name="Annual Income"]').inputValue()).toBe("300000");`
**Source:** Conversation_2026-05-30_15-27.md (commit `15d88c7`)

---

### TC-EARLY-019
**Category:** Feature
**Test Name:** Dark/light theme toggle persists across page reloads via localStorage
**Steps:**
1. Open the predictor page
2. Click `#themeToggle` to switch to light mode
3. Reload the page
**Expected Result:** Page loads in light mode; `data-theme="light"` is set on `<body>` before first paint
**Automation Hint:** `await page.locator('#themeToggle').click(); await page.reload(); const theme = await page.locator('body').getAttribute('data-theme'); expect(theme).toBe('light');`
**Source:** Conversation_2026-05-30_18-00.md (commits `efd1a2e`, `23d136d`, `e51b2e2`, `287828a`)

---

### TC-EARLY-020
**Category:** Bug-Regression
**Test Name:** Panel titles "Feature Inputs" and "Prediction Result" are visible in light mode
**Steps:**
1. Switch to light mode using `#themeToggle`
2. Observe the panel title text for both panels
**Expected Result:** Both titles are dark-colored (approximately `#0a1a35`), clearly readable on the light blue-grey background; not invisible
**Automation Hint:** `const color = await page.evaluate("getComputedStyle(document.getElementById('formPanelTitle')).color"); expect(color).not.toBe('rgb(255, 255, 255)');`
**Source:** Conversation_2026-05-30_18-00.md (commit `576fc02`)

---

### TC-EARLY-021
**Category:** Bug-Regression
**Test Name:** Sliders are excluded from the keyboard Tab order (tabIndex=-1)
**Steps:**
1. Open any predictor page
2. Click into the first number input
3. Press Tab repeatedly through all fields
**Expected Result:** Slider elements are skipped (all have `tabIndex=-1`); Tab moves only between number/select inputs and the Predict button
**Automation Hint:** `const sliders = page.locator('input[type="range"]'); for (const s of await sliders.all()) { expect(await s.getAttribute('tabindex')).toBe('-1'); }`
**Source:** Conversation_2026-05-30_18-00.md (commit `576fc02`)

---

### TC-EARLY-022
**Category:** Bug-Regression
**Test Name:** `<select>` inputs do not show wavy/chevron texture in light mode
**Steps:**
1. Switch to light mode
2. Inspect any `<select class="inp">` element
**Expected Result:** Select element has solid white background; no browser-native wavy texture visible
**Automation Hint:** `const bg = await page.evaluate("getComputedStyle(document.querySelector('select.inp')).backgroundColor"); expect(bg).toBe('rgb(255, 255, 255)');`
**Source:** Conversation_2026-05-30_18-00.md (commit `576fc02`)

---

### TC-EARLY-023
**Category:** Feature
**Test Name:** History table appears after 2 or more predictions and uses zebra striping
**Steps:**
1. Open the Insurance predictor page
2. Submit a prediction
3. Change a field value and submit a second prediction
4. Observe below the main grid
**Expected Result:** A history/comparison table appears with at least 2 rows; even rows have a distinct background color (zebra striping)
**Automation Hint:** `const table = page.locator('.hist-table'); await expect(table).toBeVisible(); const evenRows = table.locator('tbody tr:nth-child(even)'); expect(await evenRows.count()).toBeGreaterThanOrEqual(1);`
**Source:** Conversation_2026-05-30_20-00.md (commit `3da023d`)

---

### TC-EARLY-024
**Category:** Bug-Regression
**Test Name:** History table does not contain a "VS AVG" column
**Steps:**
1. Make 2 predictions on the Insurance predictor
2. Inspect the history table headers
**Expected Result:** No column with header "VS AVG" or "vs Avg" exists in the table
**Automation Hint:** `const headers = await page.locator('.hist-table thead th').allTextContents(); expect(headers.every(h => !h.toLowerCase().includes('vs avg'))).toBe(true);`
**Source:** Conversation_2026-05-30_20-00.md (commit `3da023d`)

---

### TC-EARLY-025
**Category:** Feature
**Test Name:** CI section label shows "Likely Premium Range" with "to" separator (Insurance)
**Steps:**
1. On the Insurance predictor, submit a valid prediction
2. Observe the confidence interval section label and format
**Expected Result:** Label reads "Likely Premium Range"; two values are separated by "to" (e.g. `705.67 to 2456.21`)
**Automation Hint:** `expect(page.locator('#ciSec')).toContainText('Likely Premium Range'); expect(page.locator('#ciSec')).toContainText(' to ');`
**Source:** Conversation_2026-05-30_20-00.md (commit `3da023d`)

---

### TC-EARLY-026
**Category:** Bug-Regression
**Test Name:** Field label does not show current value inline (`.sv` span removed)
**Steps:**
1. Open any predictor page
2. Type a number into any field (e.g. `5` in Sepal Length)
3. Inspect the label text above that field
**Expected Result:** Label shows only the field name (e.g. "Sepal Length Cm"), never the current value appended to it
**Automation Hint:** `await page.locator('input[name="SepalLengthCm"]').fill("5"); const lbl = await page.locator('.inp-lbl').first().textContent(); expect(lbl.trim()).not.toMatch(/\d/);`
**Source:** Conversation_2026-05-30_20-00.md (commits `8e6dfc8`, `4945320`)

---

### TC-EARLY-027
**Category:** Bug-Regression
**Test Name:** Input Summary shows each field exactly once — no duplication
**Steps:**
1. Fill in all fields on any predictor page
2. Submit a prediction
3. Inspect the Input Summary panel
**Expected Result:** Each submitted field appears exactly once in the Input Summary
**Automation Hint:** `const labels = await page.locator('.sum-lbl').allTextContents(); const unique = new Set(labels.map(l => l.trim()).filter(Boolean)); expect(labels.filter(Boolean).length).toBe(unique.size);`
**Source:** Conversation_2026-05-30_20-00.md (commits `8e6dfc8`, `4945320`)

---

### TC-EARLY-028
**Category:** Feature
**Test Name:** Input Summary has horizontal row separators between field pairs
**Steps:**
1. Submit a prediction and observe the Input Summary
**Expected Result:** Each `.sum-row` div has a visible `border-bottom` separator (not on the last row)
**Automation Hint:** `const rows = page.locator('.sum-row'); const count = await rows.count(); for (let i = 0; i < count - 1; i++) { const border = await rows.nth(i).evaluate(el => getComputedStyle(el).borderBottomWidth); expect(border).not.toBe('0px'); }`
**Source:** Conversation_2026-05-30_20-00.md

---

### TC-EARLY-029
**Category:** Feature
**Test Name:** Input Summary has a single continuous vertical divider between left and right columns
**Steps:**
1. Submit a prediction with at least 4 fields
2. Inspect the Input Summary layout
**Expected Result:** A single `div.sum-divider` element is present between `.sum-col` columns; it stretches the full height of the summary container
**Automation Hint:** `expect(page.locator('.sum-divider')).toHaveCount(1); const height = await page.locator('.sum-divider').evaluate(el => el.offsetHeight); expect(height).toBeGreaterThan(20);`
**Source:** Conversation_2026-05-31_00-00.md / Conversation_2026-05-31_01-00.md (commit `d5d9b88`)

---

### TC-EARLY-030
**Category:** Bug-Regression
**Test Name:** Annual Income accepts decimal values and values not multiples of 1000
**Steps:**
1. On the Insurance predictor, type `7500.50` into the Annual Income field
2. Click Predict
**Expected Result:** No browser validation error "nearest valid values are 7000 and 8000"; form submits and prediction is returned
**Automation Hint:** `await page.locator('input[name="Annual Income"]').fill("7500.50"); await page.locator('#predictBtn').click(); await page.locator('#resVal').waitFor(); expect(page.locator('#resVal')).toBeVisible();`
**Source:** Conversation_2026-05-31_00-00.md (commit `a9ea6ab`)

---

### TC-EARLY-031
**Category:** Bug-Regression
**Test Name:** Input Summary vertical divider is visible at opacity 0.22 (not invisible at 0.09)
**Steps:**
1. Submit a prediction in dark mode
2. Inspect the `.sum-divider` element's background color/opacity
**Expected Result:** The divider is visually distinguishable; computed background is `rgba(255,255,255, 0.22)` not `rgba(255,255,255, 0.09)`
**Automation Hint:** `const bg = await page.locator('.sum-divider').evaluate(el => getComputedStyle(el).backgroundColor); expect(bg).toContain('0.22');`
**Source:** Conversation_2026-05-31_00-00.md (commits `61b6e84`, `565a75f`, `6b8fe5b`, `37cf5bd`)

---

### TC-EARLY-032
**Category:** Feature
**Test Name:** Key Factors section shows ALL features (not limited to top 8)
**Steps:**
1. Submit a prediction on Insurance (8 features)
2. Count the Key Factors bar elements shown
**Expected Result:** All features (up to 15) are shown, not limited to 8; for Insurance all 8 feature bars are visible
**Automation Hint:** `const bars = await page.locator('#fiBars > div').count(); expect(bars).toBeGreaterThanOrEqual(8);`
**Source:** Conversation_2026-05-30_13-33.md (commit `0858a49`)

---

### TC-EARLY-033
**Category:** Backend API
**Test Name:** GET /metrics returns regression metrics for Insurance
**Steps:**
1. `GET /metrics` on the Insurance API
**Expected Result:** HTTP 200; JSON contains keys `r2`, `mae`, `rmse`, `target_mean`, `target_std`, `target_min`, `target_max`; all are numeric
**Automation Hint:** `pytest: resp = client.get("/metrics"); data = resp.json(); for k in ["r2","mae","rmse","target_mean","target_std"]: assert isinstance(data[k], float)`
**Source:** Conversation_2026-05-30_13-33.md

---

### TC-EARLY-034
**Category:** Backend API
**Test Name:** POST /predict returns ci_lower and ci_upper for regression (Insurance)
**Steps:**
1. `POST /predict` on Insurance API with a valid payload
**Expected Result:** JSON response contains `ci_lower` and `ci_upper`; `ci_lower < prediction < ci_upper`
**Automation Hint:** `pytest: data = client.post("/predict", json={...}).json(); assert data["ci_lower"] < data["prediction"] < data["ci_upper"]`
**Source:** Conversation_2026-05-30_13-33.md

---

### TC-EARLY-035
**Category:** Feature
**Test Name:** Server status dot turns green when API is reachable
**Steps:**
1. Start the API server
2. Open the predictor page
3. Wait for the health poll cycle (≤10 seconds)
**Expected Result:** Status indicator (`#srvDot`) shows green dot; label shows "online"; Predict button is enabled
**Automation Hint:** `await page.waitForFunction(() => document.querySelector('#predictBtn').disabled === false, { timeout: 15000 });`
**Source:** Conversation.md (v1.1.1)

---

### TC-EARLY-036
**Category:** Feature
**Test Name:** Predict button stays disabled until health poll confirms server ready
**Steps:**
1. Open the predictor page immediately after deployment (cold start)
2. Attempt to click Predict before health poll completes
**Expected Result:** Predict button is `disabled` until `GET /health` returns `{"status":"ok"}`
**Automation Hint:** `// On page load, before health resolves: expect(await page.locator('#predictBtn').isDisabled()).toBe(true);`
**Source:** Conversation.md (v1.2.0, commit `b8d22e4`)

---

### TC-EARLY-037
**Category:** Feature
**Test Name:** CamelCase column names are split into readable labels in the form
**Steps:**
1. Open the Iris predictor page
2. Inspect the label for the `SepalLengthCm` field
**Expected Result:** Label shows "Sepal Length Cm" (space-separated words), not "SepalLengthCm"
**Automation Hint:** `const labels = await page.locator('.inp-lbl').allTextContents(); expect(labels.some(l => l.includes('Sepal Length Cm'))).toBe(true);`
**Source:** Conversation.md (commit `543a41a`)

---

### TC-EARLY-038
**Category:** Feature
**Test Name:** Class labels in results are prettified — underscores/hyphens removed and title-cased
**Steps:**
1. Submit a prediction on the Iris predictor
2. Observe the class label displayed in the result
**Expected Result:** Classes show as "Iris Setosa", "Iris Versicolor", "Iris Virginica" — not "Iris-setosa" or "Iris_setosa"
**Automation Hint:** `const result = await page.locator('#resVal').textContent(); expect(result).not.toMatch(/[-_]/);`
**Source:** Conversation.md (commit `543a41a`)

---

### TC-EARLY-039
**Category:** Data
**Test Name:** Numeric inputs enforce minimum value of 0 (no negative predictions)
**Steps:**
1. On any predictor page, type `-1` into any numeric input
2. Submit the form or blur the field
**Expected Result:** Value is either rejected by `min="0"` attribute validation or clamped to `0`
**Automation Hint:** `await page.locator('input[type="number"]').first().fill("-1"); await page.locator('body').click(); const val = parseFloat(await page.locator('input[type="number"]').first().inputValue()); expect(val).toBeGreaterThanOrEqual(0);`
**Source:** Conversation.md (commit `4de1e73`)

---

### TC-EARLY-040
**Category:** Feature
**Test Name:** About strip shows Algorithm name and accuracy (not Task/Features count)
**Steps:**
1. Open any predictor page
2. Locate the "About" strip / mini-stat cards
**Expected Result:** Strip contains three cards: Algorithm, Accuracy, and Classes (not "Task", "Features")
**Automation Hint:** `const strip = await page.locator('.about-strip').textContent(); expect(strip).toContain('Algorithm'); expect(strip).toContain('Accuracy');`
**Source:** Conversation.md (commit `543a41a`)

---

### TC-EARLY-041
**Category:** Feature
**Test Name:** Domain badge shows domain name only — no "ML Model ·" prefix
**Steps:**
1. Open the Iris predictor page
2. Locate the hero badge in the header
**Expected Result:** Badge shows "Botanical" (or the domain name), not "ML Model · Botanical"
**Automation Hint:** `const badge = await page.locator('.hdr-badge').textContent(); expect(badge.trim()).not.toContain('ML Model');`
**Source:** Conversation.md (commit `543a41a`)

---

### TC-EARLY-042
**Category:** Feature
**Test Name:** Prediction comparison table shows changed cells highlighted
**Steps:**
1. Make two predictions with different field values
2. Inspect the second row in the history table
**Expected Result:** Cells whose values changed from the first prediction are highlighted (bold and/or white) compared to unchanged cells
**Automation Hint:** `const changedCells = page.locator('.hist-table tbody tr:nth-child(2) td.changed'); expect(await changedCells.count()).toBeGreaterThan(0);`
**Source:** Conversation_2026-05-30_13-33.md

---

### TC-EARLY-043
**Category:** Feature
**Test Name:** form has `autocomplete="off"` to prevent Tab interception
**Steps:**
1. Inspect the `<form id="pForm">` element
**Expected Result:** `<form id="pForm" autocomplete="off">` — `autocomplete` attribute is set to `off`
**Automation Hint:** `const autocomplete = await page.locator('#pForm').getAttribute('autocomplete'); expect(autocomplete).toBe('off');`
**Source:** Conversation_2026-05-30_18-00.md (commit `576fc02`)

---

### TC-EARLY-044
**Category:** Feature
**Test Name:** Benchmark range/average badge is absent from Insurance result panel
**Steps:**
1. Submit a prediction on Insurance
2. Inspect the result panel for benchmark/range elements
**Expected Result:** No `#resConf`, `#benchmarkBadge`, or "Below Average / Near Average / Above Average" text in result panel
**Automation Hint:** `expect(page.locator('#benchmarkBadge')).not.toBeAttached(); expect(page.locator('#resConf')).not.toBeAttached();`
**Source:** Conversation_2026-05-30_18-00.md (commit `576fc02`)

---

### TC-EARLY-045
**Category:** UI
**Test Name:** Light mode — Key Factors bar labels and CI labels are visible (not white-on-white)
**Steps:**
1. Switch to light mode
2. Submit a prediction
3. Observe Key Factors bar labels, CI label, Input Summary labels
**Expected Result:** All text labels in the result panel are dark-colored and readable
**Automation Hint:** `await page.locator('#themeToggle').click(); await submitPrediction(page); const fiLabelColor = await page.locator('#fiBars span').first().evaluate(el => getComputedStyle(el).color); expect(fiLabelColor).not.toBe('rgb(255, 255, 255)');`
**Source:** Conversation_2026-05-30_18-00.md (commit `7f100fa`)

---

### TC-EARLY-046
**Category:** Backend API
**Test Name:** GitHub Actions CI workflow exists and runs import smoke check
**Steps:**
1. Navigate to `.github/workflows/` in any deployed project repo
2. Verify `ci.yml` or `ci-deploy.yml` exists
3. Push a commit and check GitHub Actions runs
**Expected Result:** Workflow file exists; CI job runs `python -c "from app import app"` as smoke check; passes on valid codebase
**Automation Hint:** `assert os.path.exists(".github/workflows/ci.yml")` / `gh run list --limit 1 --json conclusion`
**Source:** Conversation.md (Session 3)

---

### TC-EARLY-047
**Category:** Bug-Regression
**Test Name:** No `rgba(#hex)` in generated CSS — all rgba calls use numeric RGB values
**Steps:**
1. Inspect the generated `index.html` source for any `rgba(` calls
**Expected Result:** No occurrence of `rgba(#` (hex inside rgba); all rgba calls use numeric RGB values
**Automation Hint:** `const content = fs.readFileSync('index.html', 'utf8'); expect(content).not.toMatch(/rgba\(#[0-9a-fA-F]/);`
**Source:** Conversation_2026-05-30_13-33.md (commit `1c7f01f`)

---

### TC-EARLY-048
**Category:** Feature
**Test Name:** `initSliders()` input number field shows placeholder with valid range
**Steps:**
1. Open the Insurance predictor page after `/ranges` loads
2. Inspect placeholder text on the Age number input
**Expected Result:** Placeholder shows the valid range, e.g. `"18 – 85"` or `"18 to 85"`
**Automation Hint:** `const ph = await page.locator('input[name="Age"]').getAttribute('placeholder'); expect(ph).toMatch(/18/);`
**Source:** Conversation_2026-05-30_15-27.md

---

### TC-EARLY-049
**Category:** Feature
**Test Name:** Annual Income placeholder shows "no upper limit" message
**Steps:**
1. Open the Insurance predictor page
2. Inspect the Annual Income field placeholder
**Expected Result:** Placeholder contains text indicating no upper cap, e.g. `"0+  (no upper limit)"`
**Automation Hint:** `const ph = await page.locator('input[name="Annual Income"]').getAttribute('placeholder'); expect(ph.toLowerCase()).toContain('no upper');`
**Source:** Conversation_2026-05-30_15-27.md (commit `15d88c7`)

---

### TC-EARLY-050
**Category:** Feature
**Test Name:** Docker run.sh pre-flight check exits with friendly error when Docker is not running
**Steps:**
1. Ensure Docker Desktop is closed
2. Run `./run.sh` from the `builds_bootstrap` directory
**Expected Result:** Script exits immediately with a human-readable error message instructing the user to open Docker Desktop
**Automation Hint:** `result = subprocess.run(["./run.sh"], capture_output=True, text=True); assert "Docker is not running" in result.stdout; assert result.returncode != 0`
**Source:** Conversation_2026-05-31_09-54.md (commit `7ead56d`)

---

### TC-EARLY-051
**Category:** Feature
**Test Name:** Pipeline runs without Claude dependency — `auto_pipeline.py` executes standalone
**Steps:**
1. Check `start.sh` for any `claude` command invocations: `grep -n "claude " start.sh`
**Expected Result:** No `claude .` or `claude` CLI invocation remains in `start.sh` or `auto_pipeline.py`
**Automation Hint:** `result = subprocess.run(["grep", "-n", "claude .", "start.sh"], capture_output=True); assert result.returncode != 0 or result.stdout == ""`
**Source:** Conversation_2026-05-31_09-54.md (commit `6e3e184`)

---

### TC-EARLY-052
**Category:** Feature
**Test Name:** LightGBM, XGBoost, CatBoost are in requirements.txt
**Steps:**
1. Read `requirements.txt` in `builds_bootstrap`
**Expected Result:** File contains `lightgbm>=4.3.0`, `xgboost>=2.0.0`, and `catboost>=1.2.0` (or equivalent version pins)
**Automation Hint:** `with open("requirements.txt") as f: content = f.read(); assert "lightgbm" in content; assert "xgboost" in content; assert "catboost" in content`
**Source:** Conversation_2026-05-31_09-54.md

---

### TC-EARLY-053
**Category:** Feature
**Test Name:** ML-Pipeline-Auto: Pydantic InputData uses Field(alias) for fields with spaces
**Steps:**
1. Start the generated FastAPI app where a feature column name contains a space
2. `POST /predict` with a JSON payload using the original column name (with space) as the key
**Expected Result:** HTTP 200; model accepts the original field name via alias; no Pydantic validation error
**Automation Hint:** `pytest: resp = client.post("/predict", json={"Annual Income": 50000, ...}); assert resp.status_code == 200`
**Source:** Conversation_2026-05-31_ML-Pipeline-Auto.md

---

### TC-EARLY-054
**Category:** Feature
**Test Name:** Categorical fields rendered as `<select>` dropdowns (not text/number inputs)
**Steps:**
1. Open a predictor page where a categorical field exists (e.g. Gender, Occupation in Insurance)
2. Inspect the input element for that field
**Expected Result:** Element is `<select>` with `<option>` elements for each unique categorical value
**Automation Hint:** `expect(page.locator('select[name="Gender"]')).toBeVisible(); const options = await page.locator('select[name="Gender"] option').count(); expect(options).toBeGreaterThan(1);`
**Source:** Conversation_2026-05-31_ML-Pipeline-Auto.md

---

### TC-EARLY-055
**Category:** Feature
**Test Name:** Feature ranges use domain-informed bounds (not raw dataset min/max)
**Steps:**
1. Inspect `feature_ranges.json` for Insurance
2. Check Age max, Credit Score max, and Insurance Duration max
**Expected Result:** `Age max = 85`, `Credit Score max = 850` (FICO max), `Insurance Duration max = 40`
**Automation Hint:** `with open("models/feature_ranges.json") as f: ranges = json.load(f); assert ranges["Age"]["max"] == 85; assert ranges["Credit Score"]["max"] == 850`
**Source:** Conversation_2026-05-30_15-27.md

---

### TC-EARLY-056
**Category:** E2E
**Test Name:** Full predict flow — fill form, click Predict, result panel populates
**Steps:**
1. Open the Iris predictor page
2. Fill in all feature fields with valid values
3. Click the Predict button
4. Wait for the result panel
**Expected Result:** `#resVal` shows a class name (e.g. "Iris Setosa"); `#fiBars` shows feature importance bars; `#probBars` shows confidence bars
**Automation Hint:** `await page.fill('input[name="SepalLengthCm"]', '5.1'); /* fill all fields */ await page.locator('#predictBtn').click(); await expect(page.locator('#resVal')).not.toBeEmpty({ timeout: 10000 });`
**Source:** Conversation.md (core feature)

---

### TC-EARLY-057
**Category:** E2E
**Test Name:** CSV batch upload — upload CSV — batch predictions appear
**Steps:**
1. Prepare a CSV with valid feature rows
2. Open any predictor page
3. Upload the CSV via the batch upload UI element
**Expected Result:** Predictions appear in the batch results area; rows are non-zero
**Automation Hint:** `await page.locator('#batchUpload').setInputFiles('test_batch.csv'); await page.locator('#batchResults').waitFor(); const rows = await page.locator('#batchResults tr').count(); expect(rows).toBeGreaterThan(0);`
**Source:** Conversation.md / Conversation_2026-05-30_13-33.md

---

### TC-EARLY-058
**Category:** UI
**Test Name:** Input Summary labels in light mode are readable (dark-colored, not white)
**Steps:**
1. Switch to light mode
2. Submit a prediction
3. Inspect `.sum-lbl` text color
**Expected Result:** `.sum-lbl` color in light mode is dark (not `rgba(255,255,255, 0.35)`)
**Automation Hint:** `await page.locator('#themeToggle').click(); await submitPrediction(page); const color = await page.locator('.sum-lbl').first().evaluate(el => getComputedStyle(el).color); expect(color).not.toContain('255, 255, 255');`
**Source:** Conversation_2026-05-30_20-00.md

---

### TC-EARLY-059
**Category:** Backend API
**Test Name:** POST /predict/upload — `python-multipart` is installed — no HTTP 422 error
**Steps:**
1. `POST /predict/upload` with a multipart/form-data request
**Expected Result:** HTTP 200 or 400 (content error), NOT HTTP 422 (Unprocessable Entity from missing multipart support)
**Automation Hint:** `pytest: resp = client.post("/predict/upload", files={"file": ("t.csv", b"col1\n1", "text/csv")}); assert resp.status_code != 422`
**Source:** Conversation.md (Session 3)

---

### TC-EARLY-060
**Category:** Feature
**Test Name:** `feature_importance.json` exists and contains normalized values 0–1
**Steps:**
1. Check that `models/feature_importance.json` exists in the project root
2. Load and inspect its contents
**Expected Result:** File exists; each entry has `feature` (string) and `importance` (float); maximum importance value is `1.0`; at least 3 entries
**Automation Hint:** `import json; data = json.load(open("models/feature_importance.json")); assert max(d["importance"] for d in data) == 1.0; assert len(data) >= 3`
**Source:** Conversation_2026-05-30_13-33.md
