# TC-PEND / TC-BUG / TC-ARCH — Pending Features, EDA Bugs, Architecture

Source: pending.md, EDA_Bug_Log.md, Microservices_Architecture_Notes.md  
Total: 47 test cases

---

## Feature Tests (TC-PEND)

### TC-PEND-001
**Category:** Feature  
**Test Name:** Column search within Feature Engineering transforms panel  
**Steps:**
1. Upload a CSV with 50+ columns to the AutoML/Feature Engineering wizard
2. Navigate to the Feature Engineering configure step
3. Type a partial column name into the column search input

**Expected Result:** The transforms panel filters and displays only matching columns in real time  
**Source:** pending.md — item 4

---

### TC-PEND-002
**Category:** Feature  
**Test Name:** Transform recipe summary displayed before applying  
**Steps:**
1. Upload a CSV with mixed column types
2. Navigate to Feature Engineering configure step
3. Select multiple transforms (e.g., log1p, frequency encoding, one-hot)
4. Click "Preview" or equivalent recipe summary trigger before confirming

**Expected Result:** Summary shows number and type of columns to be added (e.g., "will add 23 columns: 7 log1p, 5 freq…"). No transforms applied until confirmed.  
**Source:** pending.md — item 5

---

### TC-PEND-003
**Category:** Feature  
**Test Name:** DatasetEstimator present in Feature Engineering configure step  
**Steps:**
1. Upload a CSV
2. Navigate to the Feature Engineering configure step
3. Inspect UI for DatasetEstimator component

**Expected Result:** DatasetEstimator is visible and functional in the FE configure step, consistent with AutoML and Preprocessing steps  
**Source:** pending.md — item 6

---

### TC-PEND-004
**Category:** Feature  
**Test Name:** Date/datetime column extraction in Feature Engineering  
**Steps:**
1. Upload a CSV with a date/datetime column
2. Navigate to Feature Engineering configure step
3. Select the datetime column and choose "Extract date parts"
4. Apply the transform

**Expected Result:** New columns created (year, month, day, day_of_week, hour). Original column retained or dropped per UI option.  
**Source:** pending.md — item 7

---

### TC-PEND-005
**Category:** Feature  
**Test Name:** Polynomial features (degree 2) in Feature Engineering  
**Steps:**
1. Upload a CSV with numeric columns
2. Navigate to Feature Engineering configure step
3. Select two or more numeric columns and choose "Polynomial features (degree 2)"
4. Apply the transform

**Expected Result:** New interaction and squared columns added (e.g., col_A^2, col_A*col_B). Column count increases accordingly.  
**Source:** pending.md — item 8

---

### TC-PEND-006
**Category:** Feature  
**Test Name:** Binning transform in Feature Engineering  
**Steps:**
1. Upload a CSV with a continuous numeric column
2. Navigate to Feature Engineering configure step
3. Select the column and choose "Binning" with a specified number of bins
4. Apply the transform

**Expected Result:** A new binned (categorical/ordinal) column is added. Values fall into specified bin ranges. Original column retained.  
**Source:** pending.md — item 9

---

### TC-PEND-007
**Category:** Feature  
**Test Name:** Ratio/diff/group-aggregation transforms in Feature Engineering  
**Steps:**
1. Upload a CSV with multiple numeric columns and at least one categorical grouping column
2. Navigate to Feature Engineering configure step
3. Select two numeric columns, choose "Ratio" — verify new ratio column appears
4. Select two numeric columns, choose "Diff" — verify new diff column appears
5. Select numeric + group column, choose "Group aggregation (mean)" — verify aggregated column appears

**Expected Result:** Each derived column added with a descriptive name. No original columns dropped unless explicitly chosen.  
**Source:** pending.md — item 10

---

### TC-PEND-008
**Category:** Bug-Regression  
**Test Name:** AI Suggest returns valid JSON in Feature Selection (5 consecutive runs)  
**Steps:**
1. Upload a CSV with a clearly defined target column
2. Navigate to Feature Selection step
3. Click "AI Suggest"
4. Repeat 5 times across different datasets (few columns, many columns, all-numeric, mixed types)

**Expected Result:** Every response parses as valid JSON. No "no valid JSON" error shown. Suggested feature set displayed without error.  
**Source:** pending.md — item 11

---

### TC-PEND-009
**Category:** Feature  
**Test Name:** Model Fitness score tooltip explains 0–100 scale  
**Steps:**
1. Complete an AutoML training run
2. Navigate to results view containing the Model Fitness score
3. Hover over or click the Model Fitness score/badge

**Expected Result:** A tooltip appears explaining the 0–100 scale as an LLM-rated score, with description of what high vs. low scores mean.  
**Source:** pending.md — item 12

---

### TC-PEND-010
**Category:** Feature  
**Test Name:** Extended ML algorithm pills visible and selectable in AutoML  
**Steps:**
1. Upload a CSV and navigate to AutoML algorithm selection
2. Inspect the available algorithm pills/toggles

**Expected Result:** Pills present for at least: Logistic Regression, SVM, KNN, Decision Tree, Naive Bayes, Ridge — in addition to existing RF/XGB/LGB/CatBoost options. Each pill toggleable.  
**Source:** pending.md — item 13

---

### TC-PEND-011
**Category:** Bug-Regression  
**Test Name:** showAutoMLWizard() always starts a fresh wizard  
**Steps:**
1. Complete an AutoML training run so a result is stored
2. Close or dismiss the wizard
3. Click the button that triggers `showAutoMLWizard()` again

**Expected Result:** Wizard opens at Step 1 (upload/configure) with no pre-populated result from previous run.  
**Source:** pending.md — item 15

---

### TC-PEND-012
**Category:** Feature  
**Test Name:** Optuna Tuning page is interactive (backend-connected)  
**Steps:**
1. Navigate to the Optuna Tuning tool page
2. Upload a dataset and configure tuning parameters
3. Click "Run Tuning"

**Expected Result:** Page calls backend `/tune` endpoint, displays live trial progress, shows best hyperparameter set on completion. Not a static showcase.  
**Source:** pending.md — item 16

---

### TC-PEND-013
**Category:** Feature  
**Test Name:** SHAP Explainability page is interactive (backend-connected)  
**Steps:**
1. Navigate to the SHAP Explainability tool page
2. Upload a trained model or CSV, trigger SHAP computation

**Expected Result:** Page calls backend `/shap` endpoint, renders SHAP bar charts for actual feature contributions. Not a static showcase.  
**Source:** pending.md — item 17

---

### TC-PEND-014
**Category:** Feature  
**Test Name:** Ensemble Methods page is interactive (backend-connected)  
**Steps:**
1. Navigate to the Ensemble Methods tool page
2. Upload a dataset and select ensemble method (e.g., Voting, Stacking)
3. Click "Train Ensemble"

**Expected Result:** Page calls backend ensemble endpoint, trains ensemble, displays performance results. Not a static showcase.  
**Source:** pending.md — item 18

---

### TC-PEND-015
**Category:** Feature  
**Test Name:** MLPipelineState data contract carries all required fields  
**Steps:**
1. Complete a full AutoML run (upload CSV → select target → train → tune → compute SHAP)
2. Inspect the `MLPipelineState` object in browser console

**Expected Result:** Object contains all required fields: `csv`, `columns`, `target`, `model`, `tunedModel`, `shapValues`. No field undefined after its step completes.  
**Source:** pending.md — item 19

---

### TC-PEND-016
**Category:** Feature  
**Test Name:** Phase 3 drift detection compares V1 baseline vs. V2+ batches  
**Steps:**
1. Train a model on an initial dataset (V1 baseline stored)
2. Submit a second batch of data (V2)
3. Navigate to the drift monitoring view

**Expected Result:** Drift computed between V1 (training baseline) and V2 (new batch), metrics shown per feature. Subsequent batches compare to the previous batch.  
**Source:** pending.md — item 23

---

### TC-PEND-017
**Category:** Feature  
**Test Name:** Pipeline export downloads trained model as .pkl or Python script  
**Steps:**
1. Complete an AutoML training run
2. Navigate to the export/download section
3. Click "Export as .pkl" — verify download
4. Click "Export as Python script" — verify download

**Expected Result:** `.pkl` file contains the trained model. `.py` script has full inference pipeline (preprocessing + model) and is runnable standalone.  
**Source:** pending.md — item 26

---

### TC-PEND-018
**Category:** Feature  
**Test Name:** SHAP bars for FE-derived features show parent label  
**Steps:**
1. Upload a CSV, apply Feature Engineering transforms (e.g., rank encoding on "Age")
2. Train a model
3. Navigate to the SHAP values tab

**Expected Result:** FE-derived features (e.g., "Age_rank") appear in SHAP bar chart with parent label annotation (e.g., "Age_rank ↳ from Age").  
**Source:** pending.md — item 30

---

### TC-PEND-019
**Category:** Feature  
**Test Name:** "Why only X features?" collapsible present in SHAP and What-If tabs  
**Steps:**
1. Complete an AutoML training run with feature selection active
2. Navigate to the SHAP tab — look for collapsible section
3. Repeat for the What-If tab

**Expected Result:** Both SHAP and What-If tabs display a collapsible "Why only X features?" section explaining which features were selected.  
**Source:** pending.md — item 31

---

### TC-PEND-020
**Category:** Bug-Regression  
**Test Name:** Learning curve interpretation uses correct small-dataset thresholds  
**Steps:**
1. Upload a very small dataset (50–200 rows)
2. Train a model
3. Navigate to the learning curve chart
4. Inspect the interpretation/annotation overlaid on the chart

**Expected Result:** Interpretation correctly flags overfitting or underfitting. Thresholds are not too lenient — 50-row dataset with diverging curves does not show "good fit" annotation.  
**Source:** pending.md — item 32

---

### TC-PEND-021
**Category:** Feature  
**Test Name:** Categorical actual frequencies stored in schema JSON at train time  
**Steps:**
1. Upload a CSV with categorical columns and train a model
2. Inspect stored schema JSON in `data/` directory

**Expected Result:** Schema JSON contains per-category frequency counts for each categorical column (not just unique value lists). Used as baseline in drift detection.  
**Source:** pending.md — item 33

---

### TC-PEND-022
**Category:** Bug-Regression  
**Test Name:** Regression confidence intervals visible in Performance tab  
**Steps:**
1. Upload a regression dataset and train a model
2. Navigate to the Performance tab
3. Inspect predictions vs. actuals chart or metrics table

**Expected Result:** Confidence intervals (e.g., 95% CI bands) shown alongside regression predictions.  
**Source:** pending.md — item 37

---

### TC-PEND-023
**Category:** Feature  
**Test Name:** Playwright E2E tests wired into CI pipeline  
**Steps:**
1. Submit a pull request or trigger a CI run
2. Observe CI pipeline execution

**Expected Result:** Playwright test suite runs automatically as part of CI. All existing local tests pass. CI build fails if any Playwright test fails.  
**Source:** pending.md — item 45

---

### TC-PEND-024
**Category:** Feature  
**Test Name:** ml-eda and ml-vision Dockerfiles present and buildable  
**Steps:**
1. Navigate to `services/ml-eda/` and `services/ml-vision/` directories
2. Run `docker build` for each

**Expected Result:** Both directories have complete Dockerfiles. Each image builds successfully. Containers start and expose correct ports.  
**Source:** pending.md — item 47

---

### TC-PEND-025
**Category:** Feature  
**Test Name:** Playwright automated test covers CSV upload, 4 toggles, DatasetEstimator, sampling indicators  
**Steps:**
1. Run the Playwright automated test suite for ml-portfolio
2. Observe test: upload a CSV file
3. Observe test: verify 4 feature toggles are present and interactive
4. Observe test: verify DatasetEstimator component is placed correctly
5. Observe test: verify sampling indicators appear in FS result cards

**Expected Result:** All four assertions pass without flakiness.  
**Source:** pending.md — item 52

---

### TC-PEND-026
**Category:** Feature  
**Test Name:** Batch predictions support up to 10 images with before/after layout  
**Steps:**
1. Navigate to Object Detection or Segmentation tool
2. Upload 10 images for batch prediction
3. Attempt to upload an 11th image
4. Observe the results layout

**Expected Result:** Up to 10 images accepted and processed. 11th image rejected with a cap message. Results in before/after side-by-side layout.  
**Source:** pending.md — item 50

---

## EDA Bug Regression Tests (TC-BUG)

### TC-BUG-001
**Category:** Bug-Regression  
**Test Name:** Distribution chart images present (not blank) in HTML export  
**Steps:**
1. Upload a CSV with multiple numeric columns
2. Run EDA Explorer to generate distribution charts
3. Click "Export HTML"
4. Open the downloaded HTML file
5. Inspect each distribution chart section

**Expected Result:** All distribution chart images render correctly. No blank or missing image placeholders. Sequential capture loop (not `Promise.all`) confirmed in use.  
**Source:** EDA_Bug_Log.md — BUG-001

---

### TC-BUG-002
**Category:** Bug-Regression  
**Test Name:** Distribution chart images present (not blank) in PDF export  
**Steps:**
1. Upload a CSV with multiple numeric columns
2. Run EDA Explorer to generate distribution charts
3. Click "Export PDF"
4. Open the generated PDF/blob URL
5. Inspect each distribution chart

**Expected Result:** All distribution charts rendered at full resolution in PDF. No charts blank or at incorrect height (160px). Restore failure does not discard a captured image.  
**Source:** EDA_Bug_Log.md — BUG-001

---

### TC-BUG-003
**Category:** Bug-Regression  
**Test Name:** Histogram shows correct bar distribution for clustered data  
**Steps:**
1. Upload a CSV with a column having highly clustered values (e.g., sodium, sugars)
2. Open EDA Explorer
3. Navigate to Distributions section for the clustered column

**Expected Result:** Histogram shows multiple bars with appropriate widths via Plotly auto-binning. Not a single full-height bar. `type: 'histogram'` with `autobinx: true` confirmed.  
**Source:** EDA_Bug_Log.md — BUG-002

---

### TC-BUG-004
**Category:** Bug-Regression  
**Test Name:** Histogram shows visible bars for spread data  
**Steps:**
1. Upload a CSV with a column having widely spread values (e.g., calories, protein)
2. Open EDA Explorer
3. Navigate to Distributions section for the spread column

**Expected Result:** Histogram shows visible bars. No near-invisible bars from fixed narrow bin widths. Plotly auto-binning produces readable bar heights.  
**Source:** EDA_Bug_Log.md — BUG-002

---

### TC-BUG-005
**Category:** Bug-Regression  
**Test Name:** PCA 3D chart renders correctly (no blank chart area)  
**Steps:**
1. Upload a CSV with multiple numeric columns and at least one categorical column
2. Open EDA Explorer
3. Navigate to PCA 3D section
4. Select a categorical column for "Color by"

**Expected Result:** PCA 3D scatter chart renders with colored data points corresponding to category labels. No blank chart area. No "No file chosen" tooltip.  
**Source:** EDA_Bug_Log.md — BUG-003

---

### TC-BUG-006
**Category:** Bug-Regression  
**Test Name:** PCA "Color by" dropdown works for all categorical columns (not just the first)  
**Steps:**
1. Upload a CSV with multiple categorical columns
2. Open EDA Explorer and navigate to PCA 3D section
3. Select the first categorical column from "Color by" — verify chart colors update
4. Select the second categorical column — verify chart colors update
5. Select a third categorical column — verify chart colors update

**Expected Result:** Every column in "Color by" triggers a chart re-color. No column after the first silently ignored. Backend sends `cat_color_map` for all applicable columns.  
**Source:** EDA_Bug_Log.md — BUG-004

---

### TC-BUG-007
**Category:** Bug-Regression  
**Test Name:** PCA "Color by" includes low-cardinality numeric columns (2–15 unique values)  
**Steps:**
1. Upload a CSV containing a numeric column with 5 unique values
2. Open EDA Explorer and navigate to PCA 3D section
3. Open the "Color by" dropdown

**Expected Result:** The low-cardinality numeric column is available in "Color by" dropdown. Selecting it re-colors the chart correctly.  
**Source:** EDA_Bug_Log.md — BUG-004

---

### TC-BUG-008
**Category:** Bug-Regression  
**Test Name:** Original EDA tab remains interactive while PDF is generated  
**Steps:**
1. Upload a CSV and run EDA Explorer
2. Click "Export PDF"
3. Immediately attempt to scroll and interact with the EDA Explorer page

**Expected Result:** EDA Explorer page remains fully responsive. PDF opens in a new tab (blob URL), not via `window.print()`.  
**Source:** EDA_Bug_Log.md — BUG-005

---

### TC-BUG-009
**Category:** Bug-Regression  
**Test Name:** Lasso and box select buttons absent from chart modeBar  
**Steps:**
1. Upload a CSV and open EDA Explorer
2. Hover over any chart to reveal the Plotly modeBar
3. Inspect available modeBar buttons

**Expected Result:** Neither "Lasso Select" nor "Box Select" buttons are present. Double-clicking any chart resets zoom/state.  
**Source:** EDA_Bug_Log.md — BUG-006

---

### TC-BUG-010
**Category:** Bug-Regression  
**Test Name:** No misleading CSV re-download button in EDA overview  
**Steps:**
1. Upload a CSV and open EDA Explorer
2. Navigate to the Overview section
3. Inspect the available action buttons

**Expected Result:** No "⬇ CSV" or "Download CSV" button present in the overview. The button that formerly re-downloaded the unchanged uploaded file has been removed.  
**Source:** EDA_Bug_Log.md — BUG-007

---

### TC-BUG-011
**Category:** Bug-Regression  
**Test Name:** PDF export renders charts as embedded PNGs (not live UI print)  
**Steps:**
1. Upload a CSV and run EDA Explorer
2. Click "Export PDF"
3. Open the new tab (blob URL)
4. Inspect the page — check chart rendering and background styles

**Expected Result:** Export page contains charts as embedded PNG images. Glassmorphism backgrounds and `backdrop-filter` are not present. A "Save as PDF" button is embedded in the export page.  
**Source:** EDA_Bug_Log.md — BUG-008

---

## Architecture Tests (TC-ARCH)

### TC-ARCH-001
**Category:** Architecture  
**Test Name:** Training endpoint does not block inference endpoint under concurrent load  
**Steps:**
1. Submit a long-running `/train` request (large dataset, many AutoML trials)
2. While training is in progress, submit a `/predict/{model_id}` request
3. Measure response time of the prediction request

**Expected Result:** `/predict` response returned within acceptable latency (under 2 seconds) while training runs. Training does not block prediction requests.  
**Source:** Microservices_Architecture_Notes.md — Training Service

---

### TC-ARCH-002
**Category:** Architecture  
**Test Name:** Training endpoint returns a job ID for async polling  
**Steps:**
1. Submit a POST to `/train` with a valid dataset and configuration
2. Capture the response body
3. Poll the job status endpoint using the returned job ID until completion

**Expected Result:** `/train` returns a `job_id` immediately (non-blocking). Polling endpoint returns status updates (`queued`, `running`, `complete`, `failed`).  
**Source:** Microservices_Architecture_Notes.md — Training Service

---

### TC-ARCH-003
**Category:** Architecture  
**Test Name:** SHAP computation does not block prediction endpoint  
**Steps:**
1. Submit a `/shap/{model_id}` request for a large model
2. While SHAP is computing, submit a `/predict/{model_id}` request
3. Measure prediction response time

**Expected Result:** Prediction completes within normal latency. SHAP computation runs in isolation and does not degrade prediction performance.  
**Source:** Microservices_Architecture_Notes.md — SHAP / Explainability Service

---

### TC-ARCH-004
**Category:** Architecture  
**Test Name:** AutoML parallel trials produce correct aggregated winner  
**Steps:**
1. Configure an AutoML run with RF, XGB, LGB, and CatBoost enabled
2. Submit the training request (targeting parallel worker architecture)
3. Retrieve the final AutoML result

**Expected Result:** All four models evaluated. Winner is the model with the best cross-validation metric. Results from all parallel workers correctly aggregated. No race condition.  
**Source:** Microservices_Architecture_Notes.md — AutoML Service

---

### TC-ARCH-005
**Category:** Architecture  
**Test Name:** LLM explanation service handles provider-specific auth and rate limiting independently  
**Steps:**
1. Configure system with Anthropic API key
2. Submit an `/automl-explain` request
3. Simulate a rate limit response from Anthropic
4. Repeat with OpenAI key and Gemini key

**Expected Result:** Each provider's auth managed independently. Rate limit errors trigger retry/fallback logic without affecting other providers or endpoints.  
**Source:** Microservices_Architecture_Notes.md — LLM Explanation Service

---

### TC-ARCH-006
**Category:** Architecture  
**Test Name:** Model storage service correctly versions and retrieves models  
**Steps:**
1. Train two successive models on the same dataset (V1 and V2)
2. Retrieve V1 via model ID — verify its predictions
3. Retrieve V2 via model ID — verify its predictions differ from V1

**Expected Result:** Both model versions stored and retrievable independently. V1 and V2 predictions differ where expected. No version collision.  
**Source:** Microservices_Architecture_Notes.md — Model Storage / Persistence Service

---

### TC-ARCH-007
**Category:** Architecture  
**Test Name:** Feature Engineering transformer is consistent between training and inference  
**Steps:**
1. Train a model with Feature Engineering transforms applied (e.g., log1p, one-hot)
2. Note the FE transformer configuration used during training
3. Submit a single-row prediction via `/predict/{model_id}`
4. Confirm the same FE transforms are applied to the input before inference

**Expected Result:** Prediction endpoint applies identical FE transformer (same bins, encodings, column order) as used during training. No feature mismatch errors.  
**Source:** Microservices_Architecture_Notes.md — Feature Engineering Service

---

### TC-ARCH-008
**Category:** Architecture  
**Test Name:** Clustering/unsupervised endpoints operate independently of supervised ML state  
**Steps:**
1. Call `/kmeans` without any prior training run
2. Call `/pca` without any prior training run
3. Confirm neither endpoint requires a trained supervised model

**Expected Result:** Clustering and PCA endpoints return results without dependency on supervised model state. No "model not found" errors from supervised model lookup.  
**Source:** Microservices_Architecture_Notes.md — Clustering / Unsupervised Service

---

### TC-ARCH-009
**Category:** Architecture  
**Test Name:** Drift monitoring endpoint returns results without blocking training or inference  
**Steps:**
1. Simultaneously submit: a `/train` request, a `/predict` request, and a `/drift` request
2. Measure response times for all three

**Expected Result:** All three endpoints respond independently within expected latency bounds.  
**Source:** Microservices_Architecture_Notes.md — Monitoring / Drift Service

---

### TC-ARCH-010
**Category:** Architecture  
**Test Name:** app.py line count stays below 1500 before microservices split  
**Steps:**
1. Run `wc -l services/ml-api/app.py`
2. Check current line count

**Expected Result:** File is under 1500 lines. At or above 1500 lines triggers the mandatory refactor split into routers/config, inference, monitoring + shared/.  
**Source:** Microservices_Architecture_Notes.md / pending.md — item 46
