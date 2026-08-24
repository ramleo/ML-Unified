# TC-P5 — Parts 66–90 Test Cases

Source: Conversation Parts 66–90
Total: 72 test cases

---

### TC-P5-001
**Category:** Feature
**Test Name:** AutoML 3-model CV classification — winner selection by F1
**Steps:**
1. Upload an imbalanced CSV (minority class < 20%) to AutoML wizard
2. Select target column and task = Classification
3. Click Run AutoML
4. Inspect results report
**Expected Result:** AutoML runs 5-fold CV on RF, XGBoost, LightGBM, CatBoost; winner selected by F1-macro (not accuracy); winner name shown in hero card with F1-macro score
**Automation Hint:** pytest — POST `/train` with `algorithm=AutoML`, task=classification, imbalanced dataset; assert `automl.selection_metric == "F1-macro"` and `automl.winner` in response
**Source:** Part66, Part70

---

### TC-P5-002
**Category:** Feature
**Test Name:** AutoML 3-model CV regression — winner selection by MAE
**Steps:**
1. Upload a numeric regression CSV to AutoML wizard
2. Select target column and task = Regression
3. Click Run AutoML
4. Inspect results report
**Expected Result:** AutoML runs 5-fold CV; winner selected by lowest MAE; hero card shows MAE value; RMSE always shown; R² shown only if ≥ 0.60
**Automation Hint:** pytest — POST `/train` with `algorithm=AutoML`, task=regression; assert `automl.selection_metric` contains "MAE" and R² absent when R² < 0.60
**Source:** Part66

---

### TC-P5-003
**Category:** Feature
**Test Name:** AutoML subsampling on large datasets
**Steps:**
1. Upload a CSV with > 5000 rows to AutoML
2. Run AutoML with classification task
**Expected Result:** CV runs on 5000-row subsample; winner retrained on full dataset; no timeout; result includes both CV score and full-data training
**Automation Hint:** pytest — mock `_cv_sample` to verify 5000 rows passed to CV; assert final model trained on all rows
**Source:** Part66

---

### TC-P5-004
**Category:** Feature
**Test Name:** AutoML feature importance aggregated back to original columns
**Steps:**
1. Upload a CSV with categorical columns to AutoML
2. Run AutoML with OHE encoding active
3. Inspect feature importance section of report
**Expected Result:** Feature importance bars show original column names (e.g. "Embarked"), not OHE-expanded names (e.g. "Embarked_S", "Embarked_C"); values are summed per original feature
**Automation Hint:** pytest — check `automl.feature_importance` keys do not contain OHE-suffix patterns; all keys must be in original column list
**Source:** Part66

---

### TC-P5-005
**Category:** Bug-Regression
**Test Name:** "Get AI Explanation" with empty key shows error message
**Steps:**
1. Complete AutoML training to reach results page
2. Leave API key input blank
3. Click "Get AI Explanation"
**Expected Result:** Error message "Please enter your Anthropic API key first." is shown; no network request is made
**Automation Hint:** Playwright — assert error div is visible after clicking button with empty input; assert no fetch to `/explain` endpoint
**Source:** Part66

---

### TC-P5-006
**Category:** Feature
**Test Name:** AutoML results persisted on navigation away and back
**Steps:**
1. Complete AutoML training to reach results page
2. Click another sidebar section (e.g. Predict)
3. Click AutoML in sidebar
**Expected Result:** Results page is restored; "New Analysis" button is visible; user does not have to re-upload and re-train
**Automation Hint:** Playwright — after training, navigate to Predict, navigate back to AutoML; assert hero card content matches original training result
**Source:** Part66

---

### TC-P5-007
**Category:** Bug-Regression
**Test Name:** Graceful startup when pkl files are missing
**Steps:**
1. Start the backend with models directory empty (no .pkl files)
2. Navigate to the app sidebar
**Expected Result:** App starts without crash; supervised models section is empty or shows no models; no 500 error on load
**Automation Hint:** pytest — start app with `MODEL_DIR` pointing to empty directory; GET `/`; assert 200 response
**Source:** Part67

---

### TC-P5-008
**Category:** Bug-Regression
**Test Name:** Drift high-cardinality column shows note instead of per-value bars
**Steps:**
1. Upload a dataset to Drift that contains a column with > 20 unique values (e.g. Ticket, Name)
2. Run drift analysis
3. Inspect that column's drift card
**Expected Result:** Column shows "High-cardinality column — N unique values in training, M in recent data. Per-value drift not shown." instead of 500+ zero-value bars
**Automation Hint:** pytest — POST `/drift/compare` with a column having > 20 unique values; assert response field `high_cardinality: true` and no `options` array
**Source:** Part67

---

### TC-P5-009
**Category:** UI
**Test Name:** AutoML dashboard hero shows winner with F1 score
**Steps:**
1. Run AutoML classification
2. Inspect the hero card at the top of the results dashboard
**Expected Result:** Hero shows: winner algorithm name, score as F1 (not accuracy), subtitle "Outperformed [others] on N-fold CV · Classification [IMBALANCED · F1-MACRO]" when imbalanced, or plain F1 (weighted) label when balanced
**Automation Hint:** Playwright — inspect `.aml-hero-name` and `.aml-hero-score` text content after AutoML run
**Source:** Part67, Part70

---

### TC-P5-010
**Category:** UI
**Test Name:** Prediction confidence bars are taller and show winner row highlighted
**Steps:**
1. Run a classification prediction for a model with multiple classes
2. Inspect the probability / confidence bars section
**Expected Result:** Bars are 22px tall (not 8px); winner row has accent-tinted background; card has header "Confidence / probability per class"
**Automation Hint:** Playwright — `getComputedStyle(.proba-bar-wrap).height` should return "22px"
**Source:** Part67

---

### TC-P5-011
**Category:** Feature
**Test Name:** Multi-provider AI explanation — Anthropic works
**Steps:**
1. Complete AutoML training
2. Select "Anthropic" from provider dropdown
3. Enter a valid Anthropic API key
4. Click "Get AI Explanation"
**Expected Result:** Explanation renders with 4 sections: Why [Model] Won, What the Scores Tell Us, Key Drivers, Recommendations; AI badge shows; "Regenerate" button replaces "Get AI Explanation"
**Automation Hint:** pytest — POST `/explain` with `provider=anthropic` and valid key; assert response `source == "user_key"` and `explanation` has 4 sections
**Source:** Part68

---

### TC-P5-012
**Category:** Feature
**Test Name:** Multi-provider AI explanation — Groq (Llama) works
**Steps:**
1. Complete AutoML training
2. Select "Groq (Llama)" from provider dropdown
3. Enter a valid Groq API key
4. Click "Get AI Explanation"
**Expected Result:** Explanation rendered successfully; badge shows; no error shown
**Automation Hint:** pytest — POST `/explain` with `provider=groq` and valid key; assert `source == "user_key"`
**Source:** Part68

---

### TC-P5-013
**Category:** Feature
**Test Name:** AI explanation animated progress bar fills then hides on success
**Steps:**
1. Complete AutoML training
2. Enter API key and click "Get AI Explanation"
3. Observe progress bar behavior
**Expected Result:** Bar fills 0%→85% while waiting; snaps to 100% on completion; "Done!" label shown; bar hides after ~1.2 seconds; explanation text appears
**Automation Hint:** Playwright — observe progress bar element transitions; after completion assert bar is `display:none` and explanation div is visible
**Source:** Part68

---

### TC-P5-014
**Category:** Bug-Regression
**Test Name:** AI explanation error message shown only after progress bar hides
**Steps:**
1. Complete AutoML training
2. Enter an invalid API key
3. Click "Get AI Explanation"
**Expected Result:** Progress bar turns red and hides after ~2 seconds; error message appears AFTER bar is hidden, not during the animated fill
**Automation Hint:** Playwright — intercept `/explain` to return 401; assert error div not visible while bar is visible; assert error div visible after bar hides
**Source:** Part68

---

### TC-P5-015
**Category:** Feature
**Test Name:** Regenerate resets progress bar to 0 instantly without visible jump
**Steps:**
1. Get an AI explanation (success)
2. Click "Regenerate"
3. Observe progress bar
**Expected Result:** Bar resets to 0% instantly (no visible 100→0 transition); then fills again from 0 for the new request
**Automation Hint:** Playwright — after first explanation, click Regenerate; assert bar width is 0% before new animation begins (check computed width < 5%)
**Source:** Part68

---

### TC-P5-016
**Category:** Feature
**Test Name:** Enter key in API key input triggers AI explanation
**Steps:**
1. Complete AutoML training
2. Type a valid API key into the key input field
3. Press Enter key
**Expected Result:** AI explanation request fires; same behavior as clicking "Get AI Explanation"
**Automation Hint:** Playwright — fill key input, press `Enter`; assert progress bar becomes visible
**Source:** Part68

---

### TC-P5-017
**Category:** Feature
**Test Name:** Clean & Export → AutoML handoff via Yes/No prompt
**Steps:**
1. Upload CSV to Clean & Export
2. Apply cleaning (any operation)
3. Observe the prompt card in the success summary
4. Click "Yes, Train with AutoML"
**Expected Result:** Prompt card shows "Would you like to train a model with this cleaned data using AutoML?"; clicking Yes jumps directly to AutoML Step 0 (Before We Begin); no re-upload needed
**Automation Hint:** Playwright — after clean operation, assert handoff prompt card is visible; click Yes; assert AutoML wizard is shown at Step 0 with cleaned file pre-loaded
**Source:** Part68, Part69

---

### TC-P5-018
**Category:** Feature
**Test Name:** AutoML Step 0 — dataset name and target column pre-selection
**Steps:**
1. Upload CSV to AutoML wizard
2. AutoML Step 0 ("Before We Begin") card renders
3. Enter a dataset name and select a target column
4. Click Continue
**Expected Result:** Card renders with optional name input and target dropdown listing all columns with "(numeric)" or "(categorical)" labels; selected target pre-fills Step 2 (Configure)
**Automation Hint:** Playwright — verify dropdown options include dtype labels; after Continue, Step 2 target dropdown pre-selected
**Source:** Part69

---

### TC-P5-019
**Category:** Bug-Regression
**Test Name:** Step 0 card is visible (not opacity:0)
**Steps:**
1. Navigate to AutoML wizard
2. Upload a CSV file
3. Observe the Step 0 card render
**Expected Result:** Card is fully visible immediately; no invisible/transparent state
**Automation Hint:** Playwright — assert `getComputedStyle(.eda-section-card.eda-visible).opacity == "1"` immediately after card renders
**Source:** Part69

---

### TC-P5-020
**Category:** Bug-Regression
**Test Name:** Bool dtype columns do not crash preprocessing
**Steps:**
1. Upload a CSV that contains boolean (True/False) columns to AutoML
2. Run preprocessing step
**Expected Result:** Preprocessing completes without error; bool columns are cast to int8 (0/1) before imputation
**Automation Hint:** pytest — POST `/automl/preprocess` with a CSV containing a bool column; assert 200 response with no `detail` error
**Source:** Part69

---

### TC-P5-021
**Category:** Feature
**Test Name:** AutoML preprocessing — 9 imputation methods available
**Steps:**
1. Start AutoML preprocessing step
2. Open the "Handle Missing Values" numeric dropdown
**Expected Result:** Dropdown shows: Median (default), Mean, Mode, KNN (k=5), MICE, Forward fill, Backward fill, Constant (0), Drop rows; KNN and MICE show warning note about slow performance
**Automation Hint:** Playwright — assert select option values: `median`, `mean`, `mode`, `knn`, `mice`, `ffill`, `bfill`, `constant`, `drop`
**Source:** Part69

---

### TC-P5-022
**Category:** Feature
**Test Name:** AutoML preprocessing — feature selection top-K enforced correctly
**Steps:**
1. Start AutoML preprocessing with K=10
2. Select "SelectKBest" as feature selection method
3. Apply preprocessing
**Expected Result:** Preprocessing response shows `features_after = 10` (not > K); column count breakdown is correct
**Automation Hint:** pytest — POST `/automl/preprocess` with `feature_selection={method:"kbest", top_k:10}` and a dataset with > 10 numeric features; assert `features_after <= 10`
**Source:** Part69

---

### TC-P5-023
**Category:** Bug-Regression
**Test Name:** Feature selection works without target for variance and correlation methods
**Steps:**
1. Skip Step 0 (no target selected)
2. In preprocessing, select "Variance Threshold" as feature selection method
3. Apply preprocessing
**Expected Result:** Variance threshold runs and reduces features; no error about missing target column
**Automation Hint:** pytest — POST `/automl/preprocess` with `feature_selection={method:"variance", top_k:5}` and no `target_col`; assert `features_after <= 5`
**Source:** Part69

---

### TC-P5-024
**Category:** Bug-Regression
**Test Name:** CI test for classification metric uses F1 decimal format
**Steps:**
1. Run CI test suite (GitHub Actions)
2. Check `test_train_classification` result
**Expected Result:** Test passes; assertion checks `float(metric) >= 0.0` and `metricLabel in ("F1 (weighted)", "F1-macro", "Accuracy")` — not the old "%" pattern
**Automation Hint:** pytest — run `test_train_classification`; assert no assertion error
**Source:** Part69

---

### TC-P5-025
**Category:** Feature
**Test Name:** F1 weighted as hero metric for balanced classification
**Steps:**
1. Upload a balanced dataset (minority class ≥ 20%) to AutoML
2. Run AutoML with task = Classification
3. Inspect hero card metric label
**Expected Result:** Hero card shows "F1 (weighted)" as label; accuracy shown as secondary metric only
**Automation Hint:** pytest — POST `/train` with balanced CSV, `algorithm=AutoML`; assert `automl.metric_label == "F1 (weighted)"`
**Source:** Part70

---

### TC-P5-026
**Category:** Feature
**Test Name:** AutoML preprocessing animated progress bar — 5 stages
**Steps:**
1. In AutoML, enable preprocessing and click "Apply Preprocessing"
2. Observe the progress bar below the buttons
**Expected Result:** Progress bar appears with 5 stages: "Analyzing data…" (10%), "Handling missing values…" (30%), "Encoding categorical columns…" (55%), "Treating outliers & skewness…" (72%), "Running feature selection…" (85%); bar turns green on success
**Automation Hint:** Playwright — after clicking Apply, assert `#amlPrepProgress` is visible and step pills cycle through active states
**Source:** Part70

---

### TC-P5-027
**Category:** Feature
**Test Name:** High-cardinality categorical columns shown for user drop decision
**Steps:**
1. Upload Titanic CSV to AutoML
2. Enable preprocessing
3. Observe Step 1.5
**Expected Result:** Columns with > 20 unique values that are categorical (NOT numeric) appear in a yellow warning box; each listed with unique count; pre-checked to drop; user can uncheck to keep
**Automation Hint:** Playwright — assert "Columns to consider dropping" box shows Ticket, Name but NOT Age, Fare
**Source:** Part70

---

### TC-P5-028
**Category:** Bug-Regression
**Test Name:** Numeric columns (Age, Fare) excluded from high-cardinality drop list
**Steps:**
1. Upload Titanic CSV to AutoML
2. Enable preprocessing
3. Observe the "Columns to consider dropping" section
**Expected Result:** Age and Fare do NOT appear in the high-cardinality drop list (they are numeric); only text columns like Ticket and Name are shown
**Automation Hint:** Playwright — assert no list item in `.aml-drop-col` has value "Age" or "Fare"
**Source:** Part71, Part73

---

### TC-P5-029
**Category:** Feature
**Test Name:** AutoML CV upgraded to 5-fold with CatBoost as 4th model
**Steps:**
1. Run AutoML on any classification dataset
2. Inspect the "Models Tested" stat and algo comparison section
**Expected Result:** Shows "5-fold CV", 4 models (RF, XGB, LGB, CAT), "5" in the MODELS TESTED stat tile
**Automation Hint:** pytest — POST `/train` with `algorithm=AutoML`; assert `len(automl.cv_results) == 4` and each model has 5 CV scores
**Source:** Part71

---

### TC-P5-030
**Category:** Bug-Regression
**Test Name:** Imbalanced datasets use class_weight="balanced" in RF and LightGBM
**Steps:**
1. Upload a dataset where minority class < 20%
2. Run AutoML classification
**Expected Result:** RF and LightGBM CV models use `class_weight="balanced"`; final winner also trained with balanced weight; F1-macro used as selection metric
**Automation Hint:** pytest — assert `class_weight="balanced"` in estimator params when `is_imbal=True`
**Source:** Part71

---

### TC-P5-031
**Category:** Bug-Regression
**Test Name:** AutoML Results stepper step turns green (not purple) when complete
**Steps:**
1. Run AutoML to completion
2. Observe the 3-step progress stepper at top of page
**Expected Result:** Upload (step 1) and Configure (step 2) show green checkmarks; Results step is green (done), not purple (active)
**Automation Hint:** Playwright — after training completes, assert Results step has class `done` not `active`
**Source:** Part71

---

### TC-P5-032
**Category:** Bug-Regression
**Test Name:** SHAP Analyzer sidebar button border uses valid CSS (not invalid CSS variable + hex alpha)
**Steps:**
1. Load the app
2. Inspect the SHAP Analyzer sidebar button border
**Expected Result:** SHAP button border uses hardcoded 8-digit hex color (`#818cf844`) — 27% opacity; border is subtle, matching AutoML button prominence
**Automation Hint:** Playwright — `getComputedStyle(shapBtn).borderColor` should not be full-opacity; opacity should be ~27%
**Source:** Part72

---

### TC-P5-033
**Category:** Bug-Regression
**Test Name:** HF Space frontend upload uses correct root path
**Steps:**
1. Make a change to `services/ml-api/frontend/index.html`
2. Upload to HF Space using the standard upload script
**Expected Result:** File is uploaded to `frontend/index.html` (HF repo root), NOT `services/ml-api/frontend/index.html`; live HF Space reflects the change after rebuild
**Automation Hint:** Manual — after upload, fetch live HF Space URL and verify content hash matches local file
**Source:** Part72

---

### TC-P5-034
**Category:** Feature
**Test Name:** AI explanation dashboard shows only after LLM use (not always)
**Steps:**
1. Complete AutoML training
2. Observe explanation section before clicking "Get AI Explanation"
3. Click "Get AI Explanation" with valid key
4. Observe explanation section after
**Expected Result:** Before LLM use: plain rule-based text only; After LLM use: full 2-column dashboard (AI text panels left, training results right) renders
**Automation Hint:** Playwright — before API call, assert `#amlExplanation` contains plain `<p>` text; after call, assert dashboard columns visible
**Source:** Part73

---

### TC-P5-035
**Category:** Feature
**Test Name:** Separate numeric and categorical imputation strategies
**Steps:**
1. Start AutoML preprocessing
2. Enable "Handle Missing Values"
3. Observe the imputation controls
**Expected Result:** Two separate dropdowns appear: one for numeric imputation (9 options including KNN, MICE) and one for categorical imputation (5 options including Mode, Constant "Unknown")
**Automation Hint:** Playwright — assert two select elements with IDs `amlPrepMissingNum` and `amlPrepMissingCat` are visible
**Source:** Part73

---

### TC-P5-036
**Category:** Feature
**Test Name:** Improved task type detection uses column dtype
**Steps:**
1. Upload a CSV to AutoML Step 0
2. Select a target column that is an integer with 2 unique values
3. Observe the auto-detected task type hint
**Expected Result:** Hint shows "Auto-detected: Integer column · 2 unique values → Classification"; radio button pre-selects Classification
**Automation Hint:** Playwright — assert `#amlTaskHint` text contains "Integer column" and "Classification"
**Source:** Part73

---

### TC-P5-037
**Category:** Feature
**Test Name:** Numeric ID columns detected and pre-checked for dropping
**Steps:**
1. Upload Titanic CSV (with PassengerId) to AutoML
2. Enable preprocessing
3. Observe drop-columns section
**Expected Result:** PassengerId appears in drop list with label "numeric ID · 891 unique"; pre-checked; separate from categorical high-cardinality columns
**Automation Hint:** Playwright — assert `.aml-drop-col[value="PassengerId"]` exists and is checked; label contains "numeric ID"
**Source:** Part73

---

### TC-P5-038
**Category:** Feature
**Test Name:** Column count breakdown shows dropped + OHE expansion detail
**Steps:**
1. Run AutoML preprocessing with OHE encoding and drop some columns
2. Check the preprocessing complete card
**Expected Result:** Shows e.g. "Columns: 12 → 11 (−4 dropped, +5 OHE)" instead of just "12 → 11"
**Automation Hint:** Playwright — assert preprocessing complete card text matches pattern "(−N dropped, +M OHE)"
**Source:** Part73

---

### TC-P5-039
**Category:** Feature
**Test Name:** Configure stepper turns green after preprocessing complete
**Steps:**
1. Complete AutoML preprocessing step
2. Observe the wizard stepper
**Expected Result:** Upload step shows green checkmark; Configure step shows green checkmark; Results step remains as next step (not yet active)
**Automation Hint:** Playwright — after preprocessing complete card appears, assert stepper `.wizard-step[data-step="2"]` has class `done`
**Source:** Part73

---

### TC-P5-040
**Category:** Feature
**Test Name:** AI explanation dashboard — confusion matrix SVG for classification
**Steps:**
1. Run AutoML classification with valid API key for AI explanation
2. Click "Get AI Explanation"
3. Observe right column of explanation dashboard
**Expected Result:** Confusion matrix SVG renders with diagonal cells in accent color; class names labelled on axes; visible in results
**Automation Hint:** Playwright — assert SVG element inside right column explanation dashboard is present; diagonal cells have accent fill color
**Source:** Part74

---

### TC-P5-041
**Category:** Feature
**Test Name:** AI explanation dashboard — scatter plot SVG for regression
**Steps:**
1. Run AutoML regression with valid API key
2. Click "Get AI Explanation"
3. Observe right column
**Expected Result:** Predicted vs Actual scatter plot renders with ±1 RMSE shaded band and perfect diagonal reference line
**Automation Hint:** Playwright — assert SVG with class `scatter-svg` or similar is present in right column after explanation loads
**Source:** Part74

---

### TC-P5-042
**Category:** Feature
**Test Name:** Learning curve SVG renders in AI explanation dashboard
**Steps:**
1. Run AutoML (classification or regression) with valid API key
2. Click "Get AI Explanation"
3. Observe right column bottom section
**Expected Result:** Learning curve SVG shows solid train line, dashed validation line, shaded gap; displayed below Winner Model Metrics
**Automation Hint:** Playwright — assert learning curve SVG element is visible in explanation dashboard right column
**Source:** Part74

---

### TC-P5-043
**Category:** Bug-Regression
**Test Name:** app.py backend changes deployed to HF Space (not just frontend)
**Steps:**
1. Make a backend change to `services/ml-api/app.py`
2. Run the HF upload script
**Expected Result:** Both `frontend/index.html` AND `app.py` are uploaded to HF Space; HF Space rebuilds and reflects the backend change
**Automation Hint:** Manual — after upload, call a new backend endpoint; assert it returns expected response (not 404)
**Source:** Part74

---

### TC-P5-044
**Category:** UI
**Test Name:** AutoML wizard active step label uses active accent color
**Steps:**
1. Navigate to AutoML wizard
2. Select a non-default accent color (e.g. orange)
3. Observe the active wizard step label
**Expected Result:** Active step label and step number circle use the selected accent color (`var(--active-accent)`), not the static default indigo
**Automation Hint:** Playwright — select orange accent; assert `.wizard-step.active .wizard-step-num` computed color matches selected accent
**Source:** Part76

---

### TC-P5-045
**Category:** Feature
**Test Name:** Validation split counts visible in Training Info
**Steps:**
1. Run AutoML training on any dataset
2. Inspect Training Info panel in results
**Expected Result:** "Split" row shows e.g. "624 train · 156 test" (actual train/test split counts from `train_test_split`)
**Automation Hint:** pytest — assert `automl_result` contains `n_train` and `n_test` keys with positive integers
**Source:** Part76

---

### TC-P5-046
**Category:** Feature
**Test Name:** Resource estimation card on Configure page
**Steps:**
1. Complete AutoML Step 0
2. Navigate to Configure page (Step 2)
3. Observe resource card
**Expected Result:** Card shows: Est. RAM, Est. Time, CV Folds, Learning Curve, GPU availability; values update when trial count changes
**Automation Hint:** Playwright — assert resource card is visible on Step 2; changing Optuna trials from 10→30 updates "Total Time" field
**Source:** Part76, Part86

---

### TC-P5-047
**Category:** Feature
**Test Name:** Feature Engineering step — log1p and binning per column
**Steps:**
1. Complete AutoML Steps 0-1.5
2. On Feature Engineering step, find numeric columns
3. Toggle "log1p" chip for Age column
4. Set binning to "Quantile" for Fare column
5. Proceed to Configure
**Expected Result:** `fe_config` includes `{numeric: {Age: {log1p: true}, Fare: {bin: "quantile", bin_n: 5}}}`; after training, `Age_log` and `Fare_bin` columns appear in features
**Automation Hint:** pytest — POST `/automl/preprocess` with `fe_config` containing log1p and bin config; assert preprocessed CSV has `Age_log` and `Fare_bin` columns
**Source:** Part76

---

### TC-P5-048
**Category:** Feature
**Test Name:** Feature Engineering step — polynomial interactions per column
**Steps:**
1. On Feature Engineering step, go to Polynomial Interactions section
2. Select "Age" and "Fare" columns using chip toggles
3. Observe interaction term count
4. Proceed and train
**Expected Result:** Count shows "1 interaction term will be added" (C(2,2)=1); after training `Age Fare` column present in feature set
**Automation Hint:** pytest — POST `/automl/preprocess` with `fe_config={poly_cols:["Age","Fare"]}`; assert preprocessed CSV contains `Age Fare`
**Source:** Part76, Part77

---

### TC-P5-049
**Category:** Bug-Regression
**Test Name:** FeatureEngineeringTransformer does not cause What-If column mismatch
**Steps:**
1. Train an AutoML model with Feature Engineering (rank transforms active)
2. Navigate to the What-If tab on results page
3. Change a feature value and click "Sweep"
**Expected Result:** What-If sweep completes without "columns are missing" error; prediction curve renders
**Automation Hint:** pytest — train with FE; POST `/predict` with pre_fe_cols only; assert 200 response with `prediction` value
**Source:** Part77, Part79

---

### TC-P5-050
**Category:** Feature
**Test Name:** Wizard order: Feature Engineering before Preprocessing
**Steps:**
1. Upload CSV to AutoML
2. Complete Step 0
3. Observe which step appears next
**Expected Result:** Step order is: Upload → Step 0 → Feature Engineering → Data Quality & Preprocessing → Configure; FE step appears BEFORE preprocessing so feature selection operates on FE-derived columns
**Automation Hint:** Playwright — after Step 0, assert FE step is rendered (not preprocessing step); after FE, preprocessing renders
**Source:** Part77

---

### TC-P5-051
**Category:** Bug-Regression
**Test Name:** Preprocessing revert restores original analysis and file
**Steps:**
1. Upload Titanic CSV to AutoML
2. Run preprocessing (drops PassengerId)
3. Click "← Revert" button
4. Observe the drop-columns section
**Expected Result:** PassengerId reappears in the drop list; auto-detected ID columns are shown again based on original file data
**Automation Hint:** Playwright — after preprocessing, click Revert; assert PassengerId is present in drop list again
**Source:** Part78

---

### TC-P5-052
**Category:** Feature
**Test Name:** Feature Engineering moved to preprocessing step — feature selection operates on FE columns
**Steps:**
1. Configure FE with polynomial interactions
2. Run preprocessing with top_k=5 feature selection
3. Inspect features_after count
**Expected Result:** Feature selection runs AFTER FE; `features_after` reflects top_k of the post-FE column set (which may include polynomial terms)
**Automation Hint:** pytest — POST `/automl/preprocess` with `fe_config` and `feature_selection={method:"kbest",top_k:5}`; assert `features_after <= 5`
**Source:** Part78

---

### TC-P5-053
**Category:** Bug-Regression
**Test Name:** SHAP computation works after Feature Engineering
**Steps:**
1. Train AutoML model with Feature Engineering active (rank transforms)
2. Navigate to SHAP Analysis tab on results page
3. Generate SHAP explanation
**Expected Result:** SHAP bars render without "columns are missing" error; all original schema columns show SHAP values; FE-derived contributions merged into parent bars
**Automation Hint:** pytest — train with FE; POST `/shap` with model ID and sample row; assert 200 with `shap_values` array
**Source:** Part79, Part81

---

### TC-P5-054
**Category:** Bug-Regression
**Test Name:** String numeric values coerced before FE transform at prediction time
**Steps:**
1. Train AutoML model with rank transforms
2. Send a prediction where numeric columns arrive as strings (e.g. Pclass="3")
3. Check prediction result
**Expected Result:** Prediction succeeds; `pd.to_numeric(errors='ignore')` converts string numerics to float; rank transforms compute correctly; no type error
**Automation Hint:** pytest — POST `/predict` with `{"Pclass": "3", "Age": "28.0"}`; assert 200 and valid prediction
**Source:** Part79

---

### TC-P5-055
**Category:** Bug-Regression
**Test Name:** FE globals cleared on "New Analysis"
**Steps:**
1. Run AutoML with Feature Engineering (e.g. log1p on Age)
2. Click "New Analysis" on results page
3. Navigate to Feature Engineering step again
**Expected Result:** FE step shows no selections active; `_automlFeatureEng` is reset; `automlFEB64` is empty; prior run's settings do not bleed into new run
**Automation Hint:** Playwright — after new analysis, navigate to FE step; assert no chip is highlighted as selected
**Source:** Part79

---

### TC-P5-056
**Category:** Feature
**Test Name:** Training Info shows actual post-FE feature count
**Steps:**
1. Run AutoML with Feature Engineering creating 7 derived columns
2. Inspect Training Info "Features" row
**Expected Result:** Shows total trained features (e.g. 15), not just original schema columns (8); tooltip explains breakdown: "N original + M auto-created by FE"
**Automation Hint:** Playwright — hover ⓘ icon next to Features in Training Info; assert tooltip shows original + derived split
**Source:** Part79

---

### TC-P5-057
**Category:** Feature
**Test Name:** Learning curve dynamic interpretation text
**Steps:**
1. Run AutoML training
2. Inspect the learning curve panel below the results dashboard
**Expected Result:** Plain-English interpretation appears below chart (e.g. "Generalises well. More data could push performance higher." or "Overfitting. Adding more data should help close the gap.")
**Automation Hint:** pytest — assert `automl.learning_curve` data present; Playwright — assert learning curve panel has text below the SVG
**Source:** Part79

---

### TC-P5-058
**Category:** Bug-Regression
**Test Name:** Missing pre_fe_cols filled with real sample values (not NaN) at inference
**Steps:**
1. Run AutoML with FE active; feature selection drops Pclass from schema
2. Send a SHAP or What-If request (which does not include Pclass in input)
**Expected Result:** Missing Pclass is filled with the training-time median value (e.g. 3.0) before FE transform; FE-derived columns like Pclass_rank computed correctly; no NaN-based wrong results
**Automation Hint:** pytest — check `schema.pre_fe_sample` exists after training; in `/predict`, assert Pclass filled with median when not provided
**Source:** Part80

---

### TC-P5-059
**Category:** Bug-Regression
**Test Name:** Polynomial interaction names computed without get_feature_names_out
**Steps:**
1. Train AutoML model with polynomial interactions (Age, Fare)
2. Send a prediction
**Expected Result:** Prediction succeeds; interaction column `Age Fare` computed via `combinations()` not `get_feature_names_out()`; no sklearn deserialization error
**Automation Hint:** pytest — train with poly_cols=["Age","Fare"]; POST `/predict`; assert 200 with valid prediction
**Source:** Part80

---

### TC-P5-060
**Category:** Bug-Regression
**Test Name:** FE UI scroll preserved when toggling poly chips or bin method
**Steps:**
1. Navigate to Feature Engineering step with many numeric columns
2. Scroll down in the page
3. Toggle a polynomial chip or change a bin method
**Expected Result:** Page scroll position is preserved; page does not jump back to top; polynomial checklist inner scroll also preserved
**Automation Hint:** Playwright — scroll to bottom; click poly chip; assert `document.getElementById('main').scrollTop` remains unchanged
**Source:** Part80, Part81

---

### TC-P5-061
**Category:** Feature
**Test Name:** FE numeric transform row shows "+N derived" badge
**Steps:**
1. Navigate to Feature Engineering step
2. Enable log1p and rank chips for a column; set bin to Quantile
3. Observe column row
**Expected Result:** Column row shows "+3 derived" badge (1 log1p + 1 rank + 1 bin = 3)
**Automation Hint:** Playwright — assert badge span contains "+3 derived" text for the configured column
**Source:** Part80

---

### TC-P5-062
**Category:** Bug-Regression
**Test Name:** FE pkl loaded from HF XET on Space restart
**Steps:**
1. Train an AutoML model with Feature Engineering on HF Space
2. Restart the HF Space (factory restart)
3. Run SHAP or prediction with the retrained model
**Expected Result:** `{model_id}_fe.pkl` is re-downloaded from HF XET on startup via `_fetch_hf_models()`; SHAP/prediction works without "columns are missing" error
**Automation Hint:** Integration — restart HF Space; call `/shap` endpoint; assert no FE-related column mismatch error
**Source:** Part81

---

### TC-P5-063
**Category:** Bug-Regression
**Test Name:** Custom model not hidden when Sample Projects dropdown toggled
**Steps:**
1. Train a custom model via AutoML (appears in sidebar)
2. Click "Sample Projects" dropdown to collapse it
3. Click "Sample Projects" dropdown again to expand it
**Expected Result:** Custom model button remains visible throughout; only built-in sample project buttons are hidden/shown by the toggle
**Automation Hint:** Playwright — train model; click Sample Projects toggle to close; assert custom model button is still visible (no `.hidden` class)
**Source:** Part84

---

### TC-P5-064
**Category:** Bug-Regression
**Test Name:** Trained model persists across page refresh (HF Space)
**Steps:**
1. Train a model on HF Space
2. Hard-refresh the page (Ctrl+Shift+R)
3. Check sidebar
**Expected Result:** Trained model appears in sidebar after refresh; `_upload_model_to_hf()` runs after every `/train` call, persisting pipeline/fe/labels/schema to HF XET
**Automation Hint:** Integration — train model via API; restart Space; GET `/models`; assert trained model still listed
**Source:** Part84

---

### TC-P5-065
**Category:** Feature
**Test Name:** Optuna hyperparameter tuning — checkbox and trial picker in Configure
**Steps:**
1. Navigate to AutoML Configure step (Step 2)
2. Enable "Tune hyperparameters with Optuna" checkbox
3. Observe trial count options
**Expected Result:** Trial count pill options appear (10 / 20 / 30); default is 10; enabling also updates subtitle and resource estimation card
**Automation Hint:** Playwright — check Optuna checkbox; assert trial count pills visible with 10 selected by default
**Source:** Part85

---

### TC-P5-066
**Category:** Feature
**Test Name:** Optuna tuning result shows best params in results card
**Steps:**
1. Run AutoML with Optuna enabled (10 trials)
2. Inspect the results dashboard
**Expected Result:** Results show "Optuna Tuning — Best Params" section with parameter chips; best CV score displayed; winning algorithm's optimized params visible
**Automation Hint:** pytest — POST `/train` with `tune=True, n_trials=10, algorithm=AutoML`; assert `automl.optuna_params` dict and `automl.optuna_best_score` in response
**Source:** Part85

---

### TC-P5-067
**Category:** Feature
**Test Name:** Optuna tuning progress updates appear in training stream
**Steps:**
1. Run AutoML with Optuna enabled
2. Observe the progress bar and subtitle during training
**Expected Result:** Progress shows "Winner found. Tuning with Optuna (10 trials)…" at ~65%; per-trial updates follow; "Tuning done. Training with best params…" at ~78%
**Automation Hint:** Playwright — observe SSE stream events; assert pct increases from 65 to 78 with Optuna-related messages
**Source:** Part85

---

### TC-P5-068
**Category:** Feature
**Test Name:** Resource card reflects FE-derived column count in real time
**Steps:**
1. Navigate to AutoML Configure step
2. Enable Feature Engineering with several transforms
3. Return to Configure and observe resource card
**Expected Result:** Resource card shows "FE Columns: N original + M derived = total"; Est. RAM and Est. Time reflect FE column expansion
**Automation Hint:** Playwright — configure FE transforms; navigate to Configure; assert resource card "FE Columns" row shows correct derived count
**Source:** Part86

---

### TC-P5-069
**Category:** Feature
**Test Name:** Optuna trial count change updates time estimate live
**Steps:**
1. Enable Optuna on Configure page
2. Change trial count from 10 → 20 → 30
3. Observe resource card Total Time
**Expected Result:** Total Time increases as trials increase (e.g. 10 trials ≈ +15s, 20 ≈ +30s, 30 ≈ +45s over base time); no zero/NaN values shown
**Automation Hint:** Playwright — assert Total Time row value increases monotonically with trial count; minimum 1.5s per trial floor enforced
**Source:** Part86

---

### TC-P5-070
**Category:** Bug-Regression
**Test Name:** Sidebar buttons not compressed by flex-shrink
**Steps:**
1. Load the app with many sidebar items (20+ buttons)
2. Inspect sidebar button heights
**Expected Result:** Each `.model-btn` renders at its natural height (≥ 44px); content (title and subtitle text) is fully visible; sidebar scrolls for overflow instead of compressing items
**Automation Hint:** Playwright — `getBoundingClientRect().height` for `.model-btn` elements should be > 40px; `getComputedStyle(.model-btn).flexShrink == "0"`
**Source:** Part83

---

### TC-P5-071
**Category:** Feature
**Test Name:** AutoML wizard always starts fresh (does not restore last result on "AutoML" click)
**Steps:**
1. Run AutoML to completion
2. Click on another section (e.g. Predict)
3. Click AutoML sidebar button again
**Expected Result:** AutoML wizard starts at Step 1 (Upload); last result accessible only via explicit "View Last Result" button — wizard does not skip to results automatically
**Automation Hint:** Playwright — after training, navigate away, return to AutoML; assert wizard Step 1 is shown, not results page
**Source:** Part89

---

### TC-P5-072
**Category:** Feature
**Test Name:** ml-portfolio MLCapabilities section renders 5+ cards in horizontal scroll strip
**Steps:**
1. Navigate to ml-portfolio at `/`
2. Scroll to MLCapabilities section
**Expected Result:** 5 capability cards render in horizontal scroll strip (odd count → scroll layout); all cards have equal height; "Launch App" button on each; "Run here" ghost button on AutoML card only
**Automation Hint:** Playwright — navigate to ml-portfolio; assert MLCapabilities section exists; all `.cap-card` have same height (via getBoundingClientRect); AutoML card has "Run here" button
**Source:** Part88, Part90

---
