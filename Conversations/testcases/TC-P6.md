# TC-P6 — Parts 91–110 Test Cases

Source: Conversation Parts 91–110
Total: 62 test cases

---

### TC-P6-001
**Category:** Bug-Regression
**Test Name:** CatBoost isolation — remaining models run if one model fails CV
**Steps:**
1. Upload a CSV that causes CatBoost to throw an exception during cross_val_score
2. Submit the AutoML train request
**Expected Result:** The other models (RF, XGBoost, LightGBM, Extra Trees) still complete CV and a winner is selected; error is logged but does not abort the run
**Automation Hint:** pytest — monkeypatch CatBoost's fit to raise; assert response contains a winner and cv_results has 4 entries
**Source:** Part91

---

### TC-P6-002
**Category:** Backend API
**Test Name:** /explain endpoint uses server env key when no user_api_key is supplied
**Steps:**
1. Ensure `GEMINI_API_KEY` is set in the server environment
2. POST to `/explain` with a valid `automl_data` payload and no `user_api_key` field
**Expected Result:** Response contains a non-empty `explanation` object with `why_won`, `score_analysis`, `key_drivers`, `recommendations`; `source` reflects the server-key provider
**Automation Hint:** pytest — set env var in fixture; assert all explanation fields present and non-empty
**Source:** Part91

---

### TC-P6-003
**Category:** Backend API
**Test Name:** /explain default provider falls back to Gemini 2.5 Flash
**Steps:**
1. POST to `/explain` with no `provider` field, server has only `GEMINI_API_KEY` set
**Expected Result:** `source` in response indicates `gemini-2.5` provider was used
**Automation Hint:** pytest — mock Gemini call, assert call args use gemini-2.5-flash model id
**Source:** Part91

---

### TC-P6-004
**Category:** Bug-Regression
**Test Name:** HF Space serves updated app.py after deleting stale __pycache__
**Steps:**
1. Upload new `app.py` to HF Space
2. Delete the `__pycache__/app.cpython-314.pyc` file from the HF repo
3. Factory-reboot the Space
4. GET `/health` from the Space URL
**Expected Result:** Health endpoint returns `{"status":"ok","models":[...]}` reflecting the new code, not cached bytecode behavior
**Automation Hint:** Playwright — after deploy, navigate to health URL and assert JSON matches expected shape
**Source:** Part92

---

### TC-P6-005
**Category:** Feature
**Test Name:** ExtraTrees participates in AutoML competition and can be elected winner
**Steps:**
1. Upload a classification CSV
2. POST to `/train`; allow all 5 models
3. Inspect `cv_results` in the response
**Expected Result:** `cv_results` contains an entry for "Extra Trees"; if it has the highest CV score it appears as `winner`
**Automation Hint:** pytest — use a small dataset where ExtraTrees is known-best; assert "Extra Trees" in cv_results keys
**Source:** Part92

---

### TC-P6-006
**Category:** Backend API
**Test Name:** _build_prompt includes fold scores and spread per model
**Steps:**
1. Trigger an AutoML run that reaches the LLM explanation step
2. Inspect the constructed prompt passed to the LLM provider
**Expected Result:** Prompt contains per-model fold score list and spread (max − min) for each model
**Automation Hint:** pytest — monkeypatch the LLM call and capture prompt; assert "spread" and individual fold scores present per model section
**Source:** Part92

---

### TC-P6-007
**Category:** Backend API
**Test Name:** /explain response includes model_comparison and actionable_insights fields
**Steps:**
1. POST to `/explain` with valid automl_data
**Expected Result:** Response `explanation` object contains `model_comparison` (list of `{algorithm, fitness_score, reason}`) and `actionable_insights` (list of `{title, detail}`)
**Automation Hint:** pytest — assert both keys present, model_comparison items have fitness_score 0–100
**Source:** Part92

---

### TC-P6-008
**Category:** Backend API
**Test Name:** Groq Mixtral provider works via groq-mixtral provider key
**Steps:**
1. Set `GROQ_API_KEY` in server env
2. POST to `/explain` with `provider: "groq-mixtral"`
**Expected Result:** LLM call uses `mixtral-8x7b-32768` model via Groq endpoint; explanation returned
**Automation Hint:** pytest — monkeypatch openai.OpenAI; assert model arg equals `mixtral-8x7b-32768`
**Source:** Part92

---

### TC-P6-009
**Category:** Feature
**Test Name:** /train accepts selected_models param and skips unselected models
**Steps:**
1. POST to `/train` with `selected_models: '["XGBoost","CatBoost"]'`
**Expected Result:** `cv_results` only contains XGBoost and CatBoost entries; Random Forest, LightGBM, Extra Trees absent
**Automation Hint:** pytest — assert set(cv_results.keys()) == {"XGBoost","CatBoost"}
**Source:** Part93

---

### TC-P6-010
**Category:** Backend API
**Test Name:** Custom LLM provider uses supplied base_url and model
**Steps:**
1. POST to `/explain` with `provider: "custom"`, `user_api_key: "test"`, `custom_base_url: "http://localhost:11434/v1"`, `custom_model: "llama3"`
**Expected Result:** Backend creates `openai.OpenAI(api_key="test", base_url="http://localhost:11434/v1")` and calls `llama3` model
**Automation Hint:** pytest — monkeypatch `openai.OpenAI`; assert constructor args and model arg match inputs
**Source:** Part93

---

### TC-P6-011
**Category:** Bug-Regression
**Test Name:** Run Again clears previous LLM analysis state
**Steps:**
1. Complete an AutoML run and generate LLM analysis
2. Click "Run Again"
3. Observe the AI Analysis box before generating new analysis
**Expected Result:** AI Analysis box is empty/reset; no stale explanation from the previous run is shown; llmProgress is 0
**Automation Hint:** Playwright — complete run, generate analysis, click Run Again, assert analysis container is empty
**Source:** Part94

---

### TC-P6-012
**Category:** Feature
**Test Name:** Model comparison rendered as SVG line chart with colour-coded dots
**Steps:**
1. Complete an AutoML run that returns `model_comparison` from LLM
2. Click Generate AI Analysis
3. Observe the "Model Fitness" chart
**Expected Result:** Chart is an SVG dot-and-line graph; dots colour-coded (green ≥80, yellow ≥60, red <60); score label above each dot; descriptions listed below
**Automation Hint:** Playwright — assert `<svg>` exists in the model comparison section; count dots
**Source:** Part94

---

### TC-P6-013
**Category:** Feature
**Test Name:** Model name override input appears when own API key is toggled for any provider
**Steps:**
1. Open AutoML modal to results step
2. Toggle "Use my API key" (own key button) with a non-custom provider (e.g. Gemini)
3. Observe the input fields shown
**Expected Result:** API key input and model name override input both appear; base URL input does NOT appear (base URL is custom-only)
**Automation Hint:** Playwright — toggle key, assert model-override input visible; assert base-url input not visible
**Source:** Part94

---

### TC-P6-014
**Category:** Bug-Regression
**Test Name:** Winner banner shows CV score as primary number, not test set score
**Steps:**
1. Run AutoML classification on any CSV
2. Observe the winner banner
**Expected Result:** Big number displayed is the 5-fold CV score; test set score shown as a secondary line ("Test set: X% (CV: Y%)")
**Automation Hint:** Playwright — compare winner banner primary value to cv_results winner score in API response
**Source:** Part95

---

### TC-P6-015
**Category:** Feature
**Test Name:** Full ranking table shows delta column relative to winner
**Steps:**
1. Run AutoML with 3+ models
2. Observe the Full Ranking table
**Expected Result:** Each non-winner row has a delta column showing the negative gap from the winner score (e.g. −2.05%); winner row has no delta or shows 0
**Automation Hint:** Playwright — assert delta cells contain negative values for non-winner rows
**Source:** Part95

---

### TC-P6-016
**Category:** Bug-Regression
**Test Name:** selectedModels stale closure — handleTrain sends correct model set
**Steps:**
1. Open AutoML modal and toggle off one model (e.g. CatBoost) in config step
2. Submit training
3. Inspect the FormData sent to /train
**Expected Result:** `selected_models` field excludes CatBoost; cv_results does not contain CatBoost
**Automation Hint:** Playwright + network intercept — assert selected_models in POST body matches the toggled state
**Source:** Part95

---

### TC-P6-017
**Category:** Bug-Regression
**Test Name:** GaussianNB with var_smoothing=1e-2 does not fail on OHE sparse columns
**Steps:**
1. POST to `/train` with a dataset containing high-cardinality categorical columns after OHE preprocessing
2. Include Naive Bayes in selected_models
**Expected Result:** Naive Bayes completes CV without throwing an exception; cv_results contains a NB entry
**Automation Hint:** pytest — use a dataset with rare category columns; assert "Naive Bayes" in cv_results
**Source:** Part95

---

### TC-P6-018
**Category:** Bug-Regression
**Test Name:** StandardScaler in AutoML preprocessing enables Logistic Regression and SVM to run
**Steps:**
1. POST to `/train` with a dataset with large-valued numeric features (e.g. income in thousands)
2. Include Logistic Regression in selected_models
**Expected Result:** Logistic Regression completes CV without numerical overflow; result appears in cv_results
**Automation Hint:** pytest — high-magnitude feature dataset; assert "Logistic Regression" in cv_results
**Source:** Part95

---

### TC-P6-019
**Category:** Feature
**Test Name:** AutoML results persist across modal close/reopen
**Steps:**
1. Run AutoML to completion
2. Close the modal
3. Click "Try it" on the AutoML card to reopen the modal
**Expected Result:** Modal reopens directly on the results step showing the previous run's results, without requiring re-upload or retraining
**Automation Hint:** Playwright — run, close, reopen, assert step is "results" and winner name visible
**Source:** Part95

---

### TC-P6-020
**Category:** Feature
**Test Name:** Save Version stores run in localStorage and persists across page refresh
**Steps:**
1. Complete an AutoML run
2. Click "Save Version"
3. Refresh the page
4. Open AutoML modal and navigate to "Saved" tab
**Expected Result:** The saved run is listed under the dataset name with run number, winner, CV score, and date; Load button visible
**Automation Hint:** Playwright — save, refresh, reopen, assert run listed in Saved tab
**Source:** Part95

---

### TC-P6-021
**Category:** Feature
**Test Name:** Loading a saved run restores results on results step
**Steps:**
1. Open AutoML modal → Saved tab
2. Click Load on a previously saved run
**Expected Result:** Modal switches to wizard view and displays the results step with the loaded run's metrics; winner banner and ranking table populated
**Automation Hint:** Playwright — load saved run, assert results step active and winner name matches saved run data
**Source:** Part95

---

### TC-P6-022
**Category:** Bug-Regression
**Test Name:** Save Version button shows "Saved!" flash for 1.8s then reverts
**Steps:**
1. Complete an AutoML run
2. Click "Save Version"
**Expected Result:** Button text changes to "Saved!" immediately; button is disabled during flash; after 1.8s text reverts and button re-enables
**Automation Hint:** Playwright — click Save Version, assert text changes to "Saved!" then reverts after 1.8s
**Source:** Part96

---

### TC-P6-023
**Category:** Bug-Regression
**Test Name:** ruff E702 — ML-Unified CI lint passes after splitting semicolon one-liners
**Steps:**
1. Push ML-Unified commit to GitHub
2. Observe CI workflow results
**Expected Result:** All 3 CI checks pass (lint, test, deploy); no E702 ruff errors in the lint step
**Automation Hint:** CI check — verify GitHub Actions `test` job status is green on latest ML-Unified commit
**Source:** Part96

---

### TC-P6-024
**Category:** Feature
**Test Name:** 5-per-dataset saved runs cap with LRU eviction
**Steps:**
1. Save 6 runs for the same dataset
**Expected Result:** Only 5 most recent runs are retained; oldest run is evicted; group header badge shows "5 / 5" in red; Save Version button disabled with tooltip "delete a run first"
**Automation Hint:** Playwright — save 6 runs for same CSV name, assert only 5 listed; assert button disabled
**Source:** Part96

---

### TC-P6-025
**Category:** Feature
**Test Name:** Save to Pipeline resets modal to upload step on next open
**Steps:**
1. Run AutoML to completion
2. Click "Save to Pipeline"
3. Close and reopen the modal
**Expected Result:** Modal starts at the upload step (fresh state), not the results step
**Automation Hint:** Playwright — save to pipeline, reopen, assert step is "upload"
**Source:** Part96

---

### TC-P6-026
**Category:** Bug-Regression
**Test Name:** Dataset name in saved runs uses actual filename, not model title
**Steps:**
1. Upload a CSV named "sales_data.csv" and run AutoML
2. Save the run
3. Open Saved tab
**Expected Result:** Group header shows "sales_data.csv", not "My AutoML Model" or any generic title
**Automation Hint:** Playwright — assert group header text matches original filename
**Source:** Part96

---

### TC-P6-027
**Category:** Bug-Regression
**Test Name:** onResultChange ref churn does not restore cleared parent state
**Steps:**
1. Run AutoML, then click "Save to Pipeline"
2. Observe that the parent state is cleared (modal would open to upload next time)
3. Inspect whether the useEffect fires and re-sets automlResult
**Expected Result:** Parent automlResult remains null after Save to Pipeline fires; next modal open starts at upload
**Automation Hint:** React Testing Library — mock onResultChange; assert it is NOT called after Save to Pipeline clears state
**Source:** Part96

---

### TC-P6-028
**Category:** Feature
**Test Name:** Dynamic training time estimate shown in config step
**Steps:**
1. Upload a CSV with 891 rows
2. Select 5 models in config step
3. Observe the training time estimate text
**Expected Result:** Estimate is shown as a calculated range (e.g. "~1 min–1.5 min") based on row count and model speed tiers, not static "1–3 minutes"
**Automation Hint:** Playwright — assert estimate text contains dynamic range values; change model selection and assert estimate updates
**Source:** Part96

---

### TC-P6-029
**Category:** Bug-Regression
**Test Name:** Loaded saved run does not propagate to parent automlResult
**Steps:**
1. Load a saved run from the Saved tab
2. Close the modal without fresh training
3. Reopen the modal
**Expected Result:** Modal opens to upload step (fresh), not the loaded run's results; loaded runs do not persist to parent
**Automation Hint:** Playwright — load, close, reopen, assert step is "upload"
**Source:** Part96

---

### TC-P6-030
**Category:** Feature
**Test Name:** ModalShell provides consistent chrome across card modals
**Steps:**
1. Open AutoML modal
2. Open Preprocessing modal (if in modal mode)
3. Compare backdrop, container, close button, and header structure
**Expected Result:** Both modals share identical backdrop (rgba dark), container styling, close button with hover state, eyebrow label, and h2 title format
**Automation Hint:** Playwright — screenshot both modals and compare header DOM structure programmatically
**Source:** Part97

---

### TC-P6-031
**Category:** Feature
**Test Name:** Preprocessing modal /analyze auto-runs immediately after CSV upload
**Steps:**
1. Open Preprocessing modal
2. Drag and drop a CSV file
**Expected Result:** The app immediately calls `/analyze` and transitions to the configure step with column info populated — no separate "Analyze" button needed
**Automation Hint:** Playwright + network intercept — assert POST to /analyze fires within 1s of file drop
**Source:** Part97

---

### TC-P6-032
**Category:** Feature
**Test Name:** Target encoding warning shown when no target column selected
**Steps:**
1. Navigate to /tools/preprocessing configure step after uploading a CSV
2. Set categorical encoding to "Target Encoding (requires target column)"
3. Leave target column selector empty
**Expected Result:** Warning banner appears inline; Preprocess button is disabled
**Automation Hint:** Playwright — set encoding to target, clear target selector, assert warning visible and preprocess button disabled
**Source:** Part98

---

### TC-P6-033
**Category:** Feature
**Test Name:** Before vs After comparison panel shows quantitative diffs per column
**Steps:**
1. Upload CSV with missing values and high skew
2. Configure preprocessing with imputation and skew fix enabled
3. Run preprocessing and view results
**Expected Result:** Comparison panel shows per-column cards with: missing filled count, mean change percentage, std change percentage, and skew change percentage in colour-coded bullets
**Automation Hint:** Playwright — assert diff footer bullets exist per column card; assert "missing → 0" text present when imputation applied
**Source:** Part98

---

### TC-P6-034
**Category:** Feature
**Test Name:** /tools/preprocessing is a full-page route accessible via direct URL
**Steps:**
1. Navigate directly to `/tools/preprocessing`
**Expected Result:** Page loads with sticky header showing "← Portfolio" back link, step indicator, and upload zone; no modal overlay
**Automation Hint:** Playwright — navigate to /tools/preprocessing, assert page header visible and step indicator present
**Source:** Part99

---

### TC-P6-035
**Category:** Feature
**Test Name:** Smart Recommendations panel auto-detects ID column and suggests dropping it
**Steps:**
1. Upload a CSV that has a column with near-unique values (e.g. PassengerId, nunique >= 97% of rows)
2. Navigate to configure step
**Expected Result:** Smart Recommendations sidebar shows a "drop" recommendation for that column with a red dot indicator and an Apply button
**Automation Hint:** Playwright — upload Titanic CSV, assert recommendation card for PassengerId is visible
**Source:** Part99

---

### TC-P6-036
**Category:** Feature
**Test Name:** "Train with AutoML" button on preprocessing results page passes cleaned CSV via sessionStorage
**Steps:**
1. Run preprocessing on a CSV
2. Click "Train with AutoML →" in the results step
**Expected Result:** Browser navigates to /tools/automl; automl page auto-loads the preprocessed CSV from sessionStorage under key "prep_handoff" without requiring manual upload
**Automation Hint:** Playwright — click button, assert navigation to /tools/automl; assert file is pre-loaded in AutoML wizard
**Source:** Part99

---

### TC-P6-037
**Category:** Feature
**Test Name:** Data Quality Score calculated and shown before/after preprocessing
**Steps:**
1. Upload a CSV with 20% missing values and several high-skew columns
2. Run preprocessing with imputation and skew fix
3. View results step
**Expected Result:** Quality score card shows Before score (lower) and After score (higher) with "+N pts" badge; colour-coded progress bars for both
**Automation Hint:** Playwright — assert quality score card visible with two numbers and a "+N pts" badge
**Source:** Part99

---

### TC-P6-038
**Category:** Feature
**Test Name:** ConstellationBackground displays on all /tools/* pages
**Steps:**
1. Navigate to /tools/preprocessing
2. Navigate to /tools/automl
3. Navigate to /tools/feature-engineering
**Expected Result:** Each page renders the canvas particle animation (floating dots with connecting lines) visible against the dark background
**Automation Hint:** Playwright — assert `<canvas>` element present on each tool page
**Source:** Part100

---

### TC-P6-039
**Category:** Bug-Regression
**Test Name:** DatasetOverview panel does not flex-collapse to zero height
**Steps:**
1. Upload a CSV on the preprocessing page
2. Navigate to configure step
3. Observe the Dataset Overview panel
**Expected Result:** Numeric distributions and missing values bars are visible; panel does not collapse to 0 height
**Automation Hint:** Playwright — assert DatasetOverview container has clientHeight > 0
**Source:** Part100

---

### TC-P6-040
**Category:** Feature
**Test Name:** Feature Engineering tool runs entirely client-side with no backend API calls
**Steps:**
1. Navigate to /tools/feature-engineering
2. Upload a CSV and apply several transforms
3. Monitor network requests during transform application
**Expected Result:** No API calls are made to the ML-Unified backend; all computation happens in browser; results available offline
**Automation Hint:** Playwright + network intercept — assert no XHR/fetch to ML_UNIFIED_API domain during transform apply
**Source:** Part101

---

### TC-P6-041
**Category:** Feature
**Test Name:** Feature Selection runs client-side (Variance, Correlation, etc.)
**Steps:**
1. Navigate to /tools/feature-selection
2. Upload a CSV and run Variance + Correlation selection
3. Monitor network requests
**Expected Result:** No backend calls made; selection runs in browser; kept/dropped columns displayed
**Automation Hint:** Playwright + network intercept — assert no backend calls during selection run
**Source:** Part101

---

### TC-P6-042
**Category:** Feature
**Test Name:** Preprocessing runs client-side including KNN and MICE imputation
**Steps:**
1. Navigate to /tools/preprocessing
2. Upload CSV with missing values
3. Set imputation to KNN, run preprocessing
4. Monitor network requests
**Expected Result:** No backend calls made; preprocessing runs in browser; cleaned CSV downloadable
**Automation Hint:** Playwright + network intercept — assert no backend calls; assert download link appears
**Source:** Part101

---

### TC-P6-043
**Category:** Bug-Regression
**Test Name:** HF model sync gates on HF_TOKEN not SPACE_ID — works on any platform
**Steps:**
1. Start the ML-Unified backend with `HF_TOKEN` set but `SPACE_ID` unset (simulating Render deployment)
2. Train a custom model via AutoML
3. Restart the container
**Expected Result:** `_upload_model_to_hf` runs at train time (uploading to HF); `_fetch_hf_models` runs at startup (downloading back); model available after restart
**Automation Hint:** pytest — set env HF_TOKEN only; monkeypatch HF API calls; assert upload called on train and download called on startup
**Source:** Part102

---

### TC-P6-044
**Category:** Bug-Regression
**Test Name:** pkl files committed as plain binaries — COPY models/ in Docker copies real content
**Steps:**
1. Build the ML-Unified Docker image from the repository
2. Start the container
3. GET /health
**Expected Result:** Health check returns all 4 built-in models loaded; no "model not found" errors from LFS pointer stubs
**Automation Hint:** Docker build + integration test — assert /health returns models list with all 4 entries
**Source:** Part103

---

### TC-P6-045
**Category:** Feature
**Test Name:** Feature Engineering pill chips — "Apply to all" toggles transform for every column
**Steps:**
1. Upload a CSV with multiple numeric columns
2. Click the "log1p" chip in the Apply to all header row
**Expected Result:** Every numeric column now has log1p selected (filled chip); clicking again deselects all
**Automation Hint:** Playwright — click apply-to-all log1p chip, assert all per-column log1p chips are active
**Source:** Part103

---

### TC-P6-046
**Category:** Feature
**Test Name:** Date Extraction section only shows columns that contain actual date values
**Steps:**
1. Upload Titanic CSV (no actual date columns; has string columns like Name, Sex, Ticket)
2. Navigate to feature engineering configure step
**Expected Result:** Date Extraction section is hidden entirely or shows no columns; non-date string columns (Name, Sex) are not listed as date candidates
**Automation Hint:** Playwright — upload Titanic, assert Date Extraction section empty or absent
**Source:** Part103 (Note: this behavior was reversed in Part104 — test should match final behavior from Part104 where all categoricals are shown)

---

### TC-P6-047
**Category:** Feature
**Test Name:** Winsorization chip caps column values at 1st/99th percentile
**Steps:**
1. Upload CSV with outlier values in a numeric column
2. Toggle the "winsor" chip for that column
3. Apply transforms and download
**Expected Result:** Output column `<colname>_winsor` has max value at the 99th percentile and min at the 1st percentile of the original column
**Automation Hint:** pytest (client-side logic) — assert output winsor column min/max equal 1st/99th percentile of input
**Source:** Part104

---

### TC-P6-048
**Category:** Feature
**Test Name:** Ratio feature (A÷B) is null-safe for division by zero
**Steps:**
1. Upload CSV where column B contains at least one zero value
2. Create a ratio feature A÷B
3. Apply and inspect output
**Expected Result:** Rows where B=0 produce null in the output `colA_div_colB` column; no JavaScript error or NaN propagation
**Automation Hint:** Unit test on feAlgorithms.ts — assert output contains null at zero-divisor row
**Source:** Part104

---

### TC-P6-049
**Category:** Feature
**Test Name:** Time-series lag features require sort column selection before enabling
**Steps:**
1. Navigate to Feature Engineering
2. Upload a CSV
3. Observe the Lag/Diff section before selecting a sort column
**Expected Result:** Lag/Diff controls are disabled until a sort column is selected; once sort column selected, lag N and column toggles become interactive
**Automation Hint:** Playwright — assert lag controls disabled initially; select sort column, assert controls enable
**Source:** Part104

---

### TC-P6-050
**Category:** Feature
**Test Name:** Categorical column distribution bars visible in Feature Engineering right panel
**Steps:**
1. Upload Titanic CSV
2. Navigate to configure step in Feature Engineering
3. Observe the right panel
**Expected Result:** "Categorical Columns" card shows per-column value distribution bars (e.g. Sex: male 63.6% / female 36.4%) with frequency percentages
**Automation Hint:** Playwright — assert categorical card visible; assert bar labels contain percentage values
**Source:** Part105

---

### TC-P6-051
**Category:** Feature
**Test Name:** AI Suggest (rule-based) auto-selects transforms based on skew and missing rate
**Steps:**
1. Upload CSV with a column having |skew| > 1.5 and another with >2% missing
2. Click "AI Suggest" button in Numeric Column Transforms header
**Expected Result:** log1p chip auto-selected for high-skew column; missing_flag chip auto-selected for column with >2% missing; previously selected chips are cleared first
**Automation Hint:** Playwright — click AI Suggest, assert log1p active for skewed column and missing chip active for column with missing data
**Source:** Part105

---

### TC-P6-052
**Category:** Feature
**Test Name:** Results step shows new feature distribution mini-histograms
**Steps:**
1. Apply log1p transform to a skewed column and apply transforms
2. Navigate to results step
**Expected Result:** A "New Feature Distributions" card is shown with one mini-histogram tile per new column, including min/max labels
**Automation Hint:** Playwright — assert distribution tiles present; count tiles equals number of new columns generated
**Source:** Part105

---

### TC-P6-053
**Category:** Feature
**Test Name:** AI chatbot floating bubble appears on all tool pages
**Steps:**
1. Navigate to /tools/feature-engineering
2. Navigate to /tools/preprocessing
3. Navigate to /tools/feature-selection
**Expected Result:** A floating chat bubble is fixed at bottom-right on all three pages; clicking opens a chat panel (360×520px)
**Automation Hint:** Playwright — assert chat bubble element visible on each tool page; click and assert panel opens
**Source:** Part106

---

### TC-P6-054
**Category:** Feature
**Test Name:** AI chatbot sends dataset context (column names, stats) in system prompt
**Steps:**
1. Upload Titanic CSV on /tools/feature-engineering
2. Open the AI chatbot
3. Ask a question about the data
**Expected Result:** AI response references specific column names from the uploaded dataset; does not give generic answers
**Automation Hint:** Playwright + network intercept — capture POST to /api/ai-tools; assert system prompt includes column names from the dataset
**Source:** Part106

---

### TC-P6-055
**Category:** Bug-Regression
**Test Name:** Gemini 503 auto-retries with gemini-3.5-flash silently
**Steps:**
1. Configure chat to use Gemini
2. Simulate a 503 response from the primary Gemini model
**Expected Result:** The API route silently retries with gemini-3.5-flash; user does not see an error on first 503
**Automation Hint:** pytest — mock Gemini to return 503 first then 200; assert final response is success and no error returned to client
**Source:** Part106

---

### TC-P6-056
**Category:** Bug-Regression
**Test Name:** Gemini 429 shows actionable rate limit message
**Steps:**
1. Configure chat to use Gemini
2. Trigger a 429 response from the Gemini API
**Expected Result:** Error message displayed includes "Rate limit reached" and a suggestion to wait or switch to Groq; not a generic "request failed" message
**Automation Hint:** pytest — mock 429 response; assert error string contains "Rate limit" and "Groq"
**Source:** Part106

---

### TC-P6-057
**Category:** Feature
**Test Name:** Feature Selection — 9 new methods available (Lasso, Ridge, Tree, PCA, UMAP, etc.)
**Steps:**
1. Navigate to /tools/feature-selection
2. Upload a CSV with a target column
3. Enable Lasso, Ridge, Tree Importance, PCA, UMAP methods
4. Run selection
**Expected Result:** Results include ranking table with Lasso/Ridge/Tree columns; PCA scree chart rendered; UMAP scatter rendered; no errors thrown
**Automation Hint:** Playwright — enable all new methods, run, assert ranking table, scree chart, and scatter visible
**Source:** Part107

---

### TC-P6-058
**Category:** Bug-Regression
**Test Name:** PCA scree chart cumulative line does not clip above chart ceiling
**Steps:**
1. Upload CSV with 5+ numeric features
2. Run PCA with 5 components
3. Observe the PCA scree chart
**Expected Result:** Cumulative variance line dots are all visible within the chart bounds; no dots clipped at the top edge
**Automation Hint:** Playwright — assert all cumulative SVG dots have y-coordinate > 0 (within chart area)
**Source:** Part108

---

### TC-P6-059
**Category:** Bug-Regression
**Test Name:** Correlation heatmap annotates cells with |r| > 0.4
**Steps:**
1. Upload Titanic CSV
2. Run feature selection with Correlation method enabled
3. View the Correlation Heatmap
**Expected Result:** Cells where |r| > 0.4 show the r value as text annotation; caption reads "Values shown when |r| > 0.4"
**Automation Hint:** Playwright — assert annotation text visible on Pclass/Fare cell (known r≈-0.55)
**Source:** Part108

---

### TC-P6-060
**Category:** Bug-Regression
**Test Name:** AI Suggest for Feature Selection does not truncate JSON (maxTokens: 2048)
**Steps:**
1. Upload a CSV with 10+ columns
2. Click "AI Suggest Methods" in Feature Selection
**Expected Result:** AI returns a valid complete JSON object mapping method opts; no "No JSON found" or truncation error displayed
**Automation Hint:** Playwright — click AI Suggest, assert no error message and at least one method is toggled
**Source:** Part109

---

### TC-P6-061
**Category:** Feature
**Test Name:** Factor Analysis (FA) loadings table shown in Feature Selection reduction tab
**Steps:**
1. Upload CSV with numeric features
2. Enable Factor Analysis in Feature Selection
3. Run selection
**Expected Result:** FA loadings table rendered with rows per feature and columns per factor; cells with |loading| > 0.5 shown in orange bold; Download CSV button present
**Automation Hint:** Playwright — enable FA, run, assert loadings table visible with at least one orange-bolded cell
**Source:** Part109

---

### TC-P6-062
**Category:** Feature
**Test Name:** LDA adaptive display — binary classification shows 1D histogram
**Steps:**
1. Upload a binary classification dataset (target with 2 classes, e.g. Titanic survived)
2. Enable LDA in Feature Selection
3. Run selection with that target column
**Expected Result:** LDA result shows a 1D histogram with dots on a horizontal LD1 axis coloured by class; NOT a 2D scatter
**Automation Hint:** Playwright — enable LDA with binary target, run, assert 1D histogram rendered (SVG with single axis); assert 2D scatter not present
**Source:** Part109

---

### TC-P6-063
**Category:** Feature
**Test Name:** LDA shows warning when target column is numeric or empty
**Steps:**
1. Upload a CSV
2. Enable LDA in Feature Selection
3. Set target to a continuous numeric column (e.g. Age)
4. Run selection
**Expected Result:** LDA section shows a warning chip "LDA requires a categorical target column"; no crash; other methods still run
**Automation Hint:** Playwright — set numeric target, run, assert LDA warning chip visible
**Source:** Part109

---

### TC-P6-064
**Category:** Feature
**Test Name:** Latent Dirichlet Allocation transform produces topic columns in Feature Engineering
**Steps:**
1. Upload a CSV with at least one text/string column containing multiple words per cell
2. Select that column in the LDA section of Feature Engineering
3. Set nTopics to 3 and run transforms
**Expected Result:** Three new columns `lda_topic_0`, `lda_topic_1`, `lda_topic_2` appear in the output; per-topic top word chips shown in results; no backend API call made
**Automation Hint:** Playwright + network intercept — apply LDA transform, assert 3 new topic columns in preview; assert no backend calls
**Source:** Part110

---
