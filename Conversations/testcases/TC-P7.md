# TC-P7 — Parts 111–124 Test Cases

Source: Conversation Parts 111–124 (AutoML Wizard + Optuna Tool)
Total: 52 test cases

---

### TC-P7-001
**Category:** Bug-Regression
**Test Name:** Learning Curve Y-axis xInset — data points do not touch Y-axis labels
**Steps:**
1. Open the Optuna tool on ml-portfolio (`/tools/optuna`)
2. Upload a CSV dataset and configure training
3. Click "Run Optuna Tuning" to trigger training
4. Once results load, scroll to the Learning Curve chart
5. Inspect the leftmost data point (first training size) relative to the Y-axis label
**Expected Result:** The leftmost data point circle is inset 10px from the Y-axis label area and does not visually overlap or touch the Y-axis labels. The chart remains full width.
**Automation Hint:** Playwright — measure bounding box of first LC chart circle vs Y-axis label group; assert `circleLeft - labelRight >= 6px`
**Source:** Part124

---

### TC-P7-002
**Category:** Bug-Regression
**Test Name:** Regression training — SSE error event surfaced in frontend
**Steps:**
1. Open the AutoML wizard and upload a regression dataset (continuous target column)
2. Configure Step 2 and click "Run AutoML"
3. Simulate a backend crash by temporarily causing a server error (e.g., disconnect network after SSE starts)
4. Observe the progress indicator in the wizard
**Expected Result:** The frontend displays a red error banner with the server error message (e.g., "Server error: …") instead of freezing at -1% or showing a blank progress state.
**Automation Hint:** pytest — mock SSE stream to send `{"done": true, "error": "test error", "pct": -1}`; assert frontend error state is set; Playwright — assert `.error-banner` contains "Server error"
**Source:** Part124

---

### TC-P7-003
**Category:** Backend API
**Test Name:** opt_metric NameError in regression — _fill_automl_reg_metrics accepts opt_metric param
**Steps:**
1. POST to `/train` with a regression dataset, `task=regression`, and `opt_metric=auto`
2. Wait for SSE stream to complete
3. Check that the stream ends with `{"done": true, "error": null}` and not an error event
**Expected Result:** Training completes successfully without a `NameError: name 'opt_metric' is not defined` error. The `_fill_automl_reg_metrics` function receives `opt_metric` as a parameter.
**Automation Hint:** pytest — call `/train` endpoint with regression dataset; assert response SSE stream has no `error` field; inspect `automl_reg.py` that `_fill_automl_reg_metrics` signature includes `opt_metric="auto"`
**Source:** Part124

---

### TC-P7-004
**Category:** Backend API
**Test Name:** Regression secondary metric CV uses KFold not StratifiedKFold
**Steps:**
1. POST to `/train` with a regression dataset and `secondary_metric=mae` (or any regression secondary metric)
2. Wait for training to complete
3. Inspect backend logs or verify no `ValueError: Supported target types: binary, multiclass. Got continuous` error occurs
**Expected Result:** The secondary metric cross-validation for regression uses `KFold`, not `StratifiedKFold`. Training completes without a cross-validation target type error.
**Automation Hint:** pytest — in `automl_reg.py`/`automl_helpers.py` unit test, call the secondary metric CV block with a continuous `y` array; assert no ValueError is raised; grep `automl_helpers.py` for KFold branch conditioned on `task == "regression"`
**Source:** Part124

---

### TC-P7-005
**Category:** Bug-Regression
**Test Name:** Learning Curve Y-axis — no [0,1] clamp for regression metrics
**Steps:**
1. Open the Optuna tool and train on a regression dataset where RMSE is expected to be > 1 (e.g., a housing price dataset with RMSE ~ 50,000)
2. Wait for results and view the Learning Curve chart
3. Observe the Y-axis range and the position of the validation score line
**Expected Result:** The Y-axis maximum is not clamped to 1.0. Both train and validation score lines are fully visible within the chart. The Y-axis range adapts to the actual metric values (e.g., 0 to 60,000 for RMSE).
**Automation Hint:** Playwright — after training with regression data, assert LC chart Y-axis upper label is > 1; assert validation line path `d` attribute contains y-coordinates within visible SVG bounds
**Source:** Part124

---

### TC-P7-006
**Category:** Bug-Regression
**Test Name:** Learning Curve gap% direction fix for lower-is-better regression metrics
**Steps:**
1. Open the Optuna tool and train on a regression dataset with RMSE as the optimization metric
2. View the Learning Curve chart and the gap interpretation note below it
3. Intentionally use a small dataset to induce overfitting (train RMSE << val RMSE)
**Expected Result:** The gap interpretation correctly identifies overfitting when validation RMSE > train RMSE (lower-is-better). The gap percentage is computed as `(val - train) / max(|train|, |val|) * 100` and is always positive when overfitting. The warning "overfitting" badge appears when this relative gap > 10%.
**Automation Hint:** Unit test `metricLabel`-based direction detection: for `"rmse"` label, assert `lowerIsBetter = true`; assert `rawGap = lastVal - lastTrain` when overfitting
**Source:** Part124

---

### TC-P7-007
**Category:** Feature
**Test Name:** Per-column categorical encoding — One-Hot selection
**Steps:**
1. Open the AutoML wizard and upload a CSV with categorical columns
2. Navigate to Step 2 (Configure)
3. Locate the "Categorical Encoding" section
4. Set encoding for one categorical column to "One-Hot"
5. Click "Run AutoML" and wait for completion
**Expected Result:** The selected column is one-hot encoded. The trained model uses OHE for that column. No errors occur during preprocessing.
**Automation Hint:** Playwright — select "One-Hot" for a categorical col dropdown in Step2; assert FormData sent to `/train` contains `col_encoding_json` with `{"col_name": "onehot"}`; pytest — call `build_cat_transformers` with onehot encoding; assert OHE is in the pipeline for that column
**Source:** Part124

---

### TC-P7-008
**Category:** Feature
**Test Name:** Per-column categorical encoding — Ordinal selection
**Steps:**
1. Upload a CSV with categorical columns in the AutoML wizard
2. In Step 2, set encoding for a categorical column to "Ordinal"
3. Complete training
**Expected Result:** That column is ordinal-encoded (integer labels 0, 1, 2…). Training succeeds.
**Automation Hint:** pytest — `build_cat_transformers(["col"], {"col": "ordinal"})` returns a pipeline step containing `OrdinalEncoder` for that column
**Source:** Part124

---

### TC-P7-009
**Category:** Feature
**Test Name:** Per-column categorical encoding — Frequency selection
**Steps:**
1. Upload a CSV with categorical columns in the AutoML wizard
2. In Step 2, set encoding for a categorical column to "Frequency"
3. Complete training
**Expected Result:** That column is frequency-encoded (values replaced by their relative frequency in the training set). Training succeeds. No pickle error occurs.
**Automation Hint:** pytest — `build_cat_transformers(["col"], {"col": "frequency"})` returns a pipeline with `_FreqEnc` (module-level class, picklable). Call `joblib.dump` on the returned transformer and assert no `AttributeError: Can't pickle local object` is raised.
**Source:** Part124

---

### TC-P7-010
**Category:** Bug-Regression
**Test Name:** FrequencyEncoder pickle error — local class moved to module level
**Steps:**
1. Upload a CSV dataset in the AutoML wizard with a categorical column encoded as "Frequency"
2. Run AutoML to completion
3. Verify that the model is saved successfully (no pickle error in the SSE stream or backend logs)
**Expected Result:** `_FreqEnc` is defined at module level in `automl_preprocess_helpers.py`. `joblib.dump` on a pipeline containing `_FreqEnc` completes without `AttributeError: Can't pickle local object '_FreqEnc'`.
**Automation Hint:** pytest — import `_FreqEnc` from `automl_preprocess_helpers`; assert `import pickle; pickle.dumps(_FreqEnc())` succeeds
**Source:** Part124

---

### TC-P7-011
**Category:** Feature
**Test Name:** Drop columns checkbox — AutoML wizard Step 2
**Steps:**
1. Upload a CSV in the AutoML wizard (use Titanic dataset with PassengerId, Ticket, Name columns)
2. Navigate to Step 2 Configure
3. Locate the "Drop Columns" section; check PassengerId and Ticket checkboxes
4. Complete training
**Expected Result:** The "Drop Columns" checkbox list is visible between categorical encoding and model name sections. Checked columns are highlighted. The FormData sent to `/train` contains `drop_cols_json=["PassengerId","Ticket"]`. The model trains without those columns.
**Automation Hint:** Playwright — assert Step 2 contains a scrollable checklist; check two boxes; intercept POST to `/train`; assert `drop_cols_json` field contains the checked column names
**Source:** Part124

---

### TC-P7-012
**Category:** Bug-Regression
**Test Name:** Stale closure in handleTrain — dropCols and colEncodings in deps array
**Steps:**
1. Open the AutoML wizard and upload a dataset with categorical columns
2. In Step 2, check two columns to drop and set encoding for another column
3. Click "Run AutoML"
4. Verify the POST payload to `/train` contains the current dropdown/checkbox state (not stale initial values)
**Expected Result:** The FormData sent to `/train` reflects the current `dropCols` and `colEncodings` state at the time of clicking "Run AutoML" — not stale initial values from the first render.
**Automation Hint:** Playwright — change dropCols selection after initial mount; click Run; intercept request; assert the `drop_cols_json` matches the latest selection, not an empty array
**Source:** Part124

---

### TC-P7-013
**Category:** Bug-Regression
**Test Name:** Error state cleared when navigating Back in AutoML wizard
**Steps:**
1. Open the AutoML wizard and trigger a training error (e.g., malformed CSV)
2. Observe the error message on the current step
3. Click the "Back" button to return to the previous step
4. Check whether the error message is still visible
**Expected Result:** Clicking Back clears the error state. The previous step renders without any error banner from the prior failed training attempt.
**Automation Hint:** Playwright — trigger an error; assert `.error-banner` is visible; click Back; assert `.error-banner` is NOT present on the previous step
**Source:** Part124

---

### TC-P7-014
**Category:** Feature
**Test Name:** n_trials cap raised from 50 to 200 in Optuna tool
**Steps:**
1. Open the Optuna tool on ml-portfolio
2. Configure training with tuning enabled
3. Inspect the backend or the n_trials field to confirm the maximum number of trials is 200
**Expected Result:** The Optuna backend runs up to 200 trials (not 50). The trial history chart can display up to 200 data points without error.
**Automation Hint:** pytest — inspect `automl_helpers.py`/`_optuna_tune` function; assert `n_trials=200` or the configurable cap is >= 200; Playwright — check UI display of trial count after full run
**Source:** Part119, Part124

---

### TC-P7-015
**Category:** Backend API
**Test Name:** Pydantic v2 bool Form field — tune=true actually enables tuning
**Steps:**
1. POST to `/train` with `tune=true` (as a string, as sent in multipart/form-data)
2. Verify Optuna tuning actually runs (check SSE stream for tuning progress messages)
**Expected Result:** `tune` is correctly coerced from string `"true"` to `True`. Optuna tuning runs (not skipped with default params). The SSE stream includes Optuna trial progress events.
**Automation Hint:** pytest — call the endpoint with `tune="true"` in FormData; assert `best_params` in the result is not the default fallback; assert `optuna_trials` list has entries
**Source:** Part119

---

### TC-P7-016
**Category:** Backend API
**Test Name:** Pydantic v2 bool Form field — use_smote=true actually enables SMOTE
**Steps:**
1. POST to `/train` with `use_smote=true` (string) on an imbalanced classification dataset
2. Verify SMOTE is applied (class distribution should be balanced before model training)
**Expected Result:** `use_smote` coerces from `"true"` to `True`. SMOTE oversampling is applied and the model trains on a balanced dataset.
**Automation Hint:** pytest — call endpoint with `use_smote="true"`; assert no `imbalanced-learn` import error; verify in backend code that `use_smote: str = Form("false")` with manual conversion is used (not `bool = Form(False)`)
**Source:** Part119

---

### TC-P7-017
**Category:** Backend API
**Test Name:** Optuna _optuna_tune returns 4 values — callers unpack correctly
**Steps:**
1. POST to `/train` with `tune=true` for a classification dataset
2. Wait for the SSE stream to complete
3. Check the result for `best_params`, `optuna_trials`, and `param_importance` fields
**Expected Result:** `_optuna_tune` returns `(best_params, best_val, optuna_trials, param_importance)`. Both `automl_clf.py` and `automl_reg.py` unpack all 4 values. No `ValueError: not enough values to unpack` occurs.
**Automation Hint:** pytest — unit test `_optuna_tune` return value; assert it returns a 4-tuple; assert calling code unpacks 4 variables
**Source:** Part119

---

### TC-P7-018
**Category:** Backend API
**Test Name:** roc_auc multiclass — uses roc_auc_ovr scorer in Optuna objective
**Steps:**
1. Upload a multiclass classification dataset (3+ classes) in the Optuna tool
2. Select "ROC-AUC" as the optimization metric
3. Run Optuna tuning and wait for completion
**Expected Result:** Optuna trials do not fail with `ValueError: multi_class must be in ('ovo', 'ovr')`. Tuning completes successfully with `roc_auc_ovr` scorer for multiclass targets.
**Automation Hint:** pytest — call the Optuna objective with a 3-class dataset and `opt_metric="roc_auc"`; assert no ValueError is raised; assert scorer used is `"roc_auc_ovr"` when `len(unique(y)) > 2`
**Source:** Part122, Part123

---

### TC-P7-019
**Category:** Backend API
**Test Name:** roc_auc sklearn 1.4 is_classifier() bypass — uses cross_val_predict + manual roc_auc_score
**Steps:**
1. Upload a classification dataset using XGBoost or CatBoost as the winning model
2. Run Optuna tuning with `opt_metric=roc_auc`
3. Verify all trials complete without `"Pipeline should either be a classifier..."` error
**Expected Result:** For `roc_auc`/`roc_auc_ovr` metrics, the code uses `cross_val_predict(..., method='predict_proba')` directly and computes `roc_auc_score` manually — bypassing the sklearn 1.4 `is_classifier()` type check.
**Automation Hint:** pytest — call Optuna objective with XGBoost pipeline and binary dataset; assert no `ValueError` about classifier type; assert trial value is a valid float in [0, 1]
**Source:** Part123

---

### TC-P7-020
**Category:** Backend API
**Test Name:** Learning curve roc_auc scorer — sklearn 1.4 is_classifier() bypass
**Steps:**
1. Train a model via the Optuna tool with `opt_metric=roc_auc`
2. Wait for learning curve to be computed
3. Check SSE stream for any `ValueError` related to `is_classifier`
**Expected Result:** Learning curve computation uses a raw callable scorer (not string `"roc_auc"`) so `is_classifier()` is never called. No errors occur. Learning curve data (`train_scores`, `val_scores`) is present in the result.
**Automation Hint:** pytest — call `_compute_learning_curve(estimator, X, y, scoring="roc_auc")` with XGBoost pipeline; assert returned arrays are non-empty floats; assert no exception
**Source:** Part123

---

### TC-P7-021
**Category:** Backend API
**Test Name:** NaN in SSE payload — _sanitize() prevents JSON.parse failure
**Steps:**
1. Trigger a scenario where a trial score is NaN (e.g., all-NaN cross-validation fold scores on a bad dataset)
2. Observe the SSE stream
3. Check that the browser frontend does not freeze at any percentage
**Expected Result:** `_sanitize()` in `progress.py` replaces NaN/Inf values with `None` before `json.dumps`. The SSE event is valid JSON. The frontend never receives an unparseable SSE event.
**Automation Hint:** pytest — call `_sanitize({"value": float("nan"), "nested": [float("inf")]})` and assert no NaN/Inf appear in `json.dumps` output; assert result is valid JSON
**Source:** Part122

---

### TC-P7-022
**Category:** Backend API
**Test Name:** NaN trial history filtered from trial_history and secondary_trials
**Steps:**
1. Run Optuna tuning where some trials return NaN scores (minority class fold issue)
2. Check the `optuna_trials` and `optuna_secondary_trials` in the result JSON
**Expected Result:** NaN values are filtered from `trial_history` and `secondary_trials` in `automl_helpers.py`. The trial history chart only receives valid float score entries.
**Automation Hint:** pytest — run Optuna with a dataset where first 5 trials return NaN; assert `result["optuna_trials"]` contains no NaN values; assert `result["optuna_secondary_trials"]` contains no NaN values
**Source:** Part122

---

### TC-P7-023
**Category:** Backend API
**Test Name:** sklearn 1.4 error_score — cross_val_score uses error_score='raise' explicitly
**Steps:**
1. Run Optuna tuning on a dataset that would cause `cross_val_score` to fail on a fold
2. Verify the error is captured and surfaced, not silently swallowed as NaN
**Expected Result:** `cross_val_score` is called with `error_score='raise'` so sklearn 1.4's default NaN-silencing behavior is bypassed. Fold errors are caught in a try/except around the whole call and raise `optuna.TrialPruned()`.
**Automation Hint:** pytest — mock `cross_val_score` to raise a `ValueError`; assert the Optuna objective catches it and calls `_first_error.append(str(err))`; assert trial is pruned
**Source:** Part123

---

### TC-P7-024
**Category:** Backend API
**Test Name:** Optuna minority class fold adjustment — StratifiedKFold splits reduced to minority count
**Steps:**
1. Upload a highly imbalanced classification dataset where minority class has 3 rows
2. Run Optuna tuning with `n_splits=5` (default)
3. Check backend does not crash with "Cannot have number of splits n_splits=5 greater than number of samples"
**Expected Result:** Before the Optuna objective, minority class count is detected. If `minority_count < n_splits`, `StratifiedKFold` is reduced to `max(2, minority_count)`. Training completes without split errors.
**Automation Hint:** pytest — create dataset with 3 minority class rows; call Optuna objective; assert no `ValueError` about splits; assert `n_splits` used is ≤ 3
**Source:** Part123

---

### TC-P7-025
**Category:** Backend API
**Test Name:** Optuna all-trials-failed error — includes actual cause
**Steps:**
1. Run Optuna tuning with a dataset that causes all trials to fail (e.g., unsuitable scoring for the task)
2. Check the SSE stream for the error message
**Expected Result:** When all trials fail, the RuntimeError message includes `"Cause: <actual exception text>"` so the user gets actionable information, not just "All Optuna trials failed".
**Automation Hint:** pytest — mock Optuna objective to fail on all 10 trials; assert `RuntimeError` message contains "Cause:" with the first exception detail
**Source:** Part123

---

### TC-P7-026
**Category:** Feature
**Test Name:** Optuna drop columns — form field accepted by backend
**Steps:**
1. Open the Optuna tool (`/tools/optuna`) and upload a dataset
2. In Step 2, check columns to drop (e.g., PassengerId, Name)
3. Run Optuna tuning
**Expected Result:** The `/train` endpoint receives `drop_cols_json` as a JSON string list. The dropped columns are excluded from the feature matrix before Optuna tuning. Training completes without errors.
**Automation Hint:** Playwright — check two drop-column boxes in OptunaRunner Step 2; intercept POST; assert `drop_cols_json` is `'["PassengerId","Name"]'`; pytest — assert columns are absent from `X` in the training function
**Source:** Part120, Part124

---

### TC-P7-027
**Category:** Feature
**Test Name:** Optuna optimization metric selection — passed to _optuna_tune
**Steps:**
1. Open the Optuna tool and upload a classification dataset
2. In Step 2, select "F1 Weighted" from the optimization metric dropdown
3. Run Optuna tuning
4. Check the result for `optuna_primary_metric` field
**Expected Result:** The selected metric is mapped to the correct sklearn scoring string (`"f1_weighted"`) and passed through to `_optuna_tune`. The result contains `optuna_primary_metric: "f1_weighted"`.
**Automation Hint:** pytest — call `/train` with `opt_metric=f1_weighted`; assert trial scores reflect F1 Weighted (not accuracy or ROC-AUC); assert `optuna_primary_metric` in result equals `"f1_weighted"`
**Source:** Part120

---

### TC-P7-028
**Category:** Feature
**Test Name:** Optuna AI explanation endpoint — /optuna-explain
**Steps:**
1. Complete an Optuna training run on ml-portfolio
2. In the AI Explanation section of OptunaResults, select a provider (e.g., Groq) and enter an API key
3. Click "Get AI Explanation"
4. Wait for the explanation to load
**Expected Result:** POST to `/optuna-explain` succeeds. The response contains `{"explanation": "...", "error": null}`. The explanation is rendered as formatted HTML (markdown converted). No raw JSON or provider errors are shown.
**Automation Hint:** pytest — POST to `/optuna-explain` with valid test data and API key; assert response JSON has `"explanation"` as non-empty string; Playwright — assert `.ai-explanation` div contains rendered heading tags, not raw `##` markdown
**Source:** Part120

---

### TC-P7-029
**Category:** Feature
**Test Name:** Optuna AI explanation — LLM error surfaced instead of generic message
**Steps:**
1. Open Optuna results and click "Get AI Explanation" with an invalid or expired API key
2. Wait for the request to complete
**Expected Result:** The actual LLM error message (e.g., "Invalid API key" or "Rate limit exceeded") is displayed in the UI instead of a generic "Something went wrong" message. The `/optuna-explain` response contains `{"explanation": null, "error": "...actual error..."}`.
**Automation Hint:** pytest — POST to `/optuna-explain` with an invalid API key; assert response `"error"` field is non-null and contains provider error text; Playwright — assert error text is visible in the AI explanation section
**Source:** Part121

---

### TC-P7-030
**Category:** Feature
**Test Name:** Optuna sampler selection — QMC sampler runs without error
**Steps:**
1. Open the Optuna tool and configure training
2. Select "QMC (Quasi-Monte Carlo)" from the sampler dropdown
3. Run Optuna tuning
4. Check the result for `optuna_sampler` field
**Expected Result:** Optuna uses `QMCSampler` (Sobol). Training completes without `ModuleNotFoundError`. The result contains `optuna_sampler: "qmc"`. The Bayesian Optimization Summary badge shows "QMC".
**Automation Hint:** pytest — call `_optuna_tune` with `sampler="qmc"`; assert `QMCSampler` is used; assert no import errors for `cmaes` or `torch`
**Source:** Part121

---

### TC-P7-031
**Category:** Feature
**Test Name:** Optuna secondary metric tracking — stored per trial
**Steps:**
1. Open the Optuna tool and select a secondary metric (e.g., "F1 Macro" for classification)
2. Run Optuna tuning
3. View the Trial History chart
**Expected Result:** The Trial History chart shows a green dashed overlay line for the secondary metric, with a legend entry. The result JSON contains `optuna_secondary_metric: "f1_macro"` and `optuna_secondary_trials: [{trial, value}, ...]`.
**Automation Hint:** pytest — call `/train` with `secondary_metric=f1_macro`; assert result has `optuna_secondary_trials` list with `len > 0`; assert no NaN in secondary trial values; Playwright — assert green dashed line visible in trial history SVG
**Source:** Part121

---

### TC-P7-032
**Category:** Feature
**Test Name:** Optuna secondary metric for regression — uses KFold not StratifiedKFold
**Steps:**
1. Open the Optuna tool and upload a regression dataset
2. Select "MAE" or "RMSE" as the secondary metric
3. Run Optuna tuning
**Expected Result:** The secondary metric cross-validation uses `KFold` (not `StratifiedKFold`). No `ValueError: Supported target types: binary, multiclass. Got continuous` error occurs.
**Automation Hint:** pytest — in `automl_helpers.py` objective function, assert that for `task="regression"`, secondary CV uses `KFold(n_splits=2)` not `StratifiedKFold`
**Source:** Part124

---

### TC-P7-033
**Category:** Feature
**Test Name:** Optuna learning curve chart — train vs validation lines displayed
**Steps:**
1. Complete an Optuna training run
2. View the Learning Curve chart in the results
**Expected Result:** The chart shows two lines: solid for training scores and dashed for validation scores. The X-axis shows training set sizes. The Y-axis label reflects the actual optimization metric (not hardcoded "F1").
**Automation Hint:** Playwright — assert LearningCurveChart SVG contains exactly 2 path elements (train + val); assert Y-axis label text matches selected opt_metric display name
**Source:** Part121, Part124

---

### TC-P7-034
**Category:** Feature
**Test Name:** Optuna learning curve — responsive SVG uses useRef pixel measurement
**Steps:**
1. Open the Optuna results page in a narrow viewport (e.g., 800px wide)
2. Expand to wide viewport (1400px)
3. Observe the Learning Curve chart at both widths
**Expected Result:** The chart redraws correctly at both widths. Circles remain circular, text remains readable. No distortion or overflow. The chart uses `useRef` to measure actual pixel width and computes coordinates in real pixels (no `preserveAspectRatio` issues).
**Automation Hint:** Playwright — resize viewport to 800px; take screenshot; resize to 1400px; take screenshot; assert no visual overflow in either case; assert SVG circle `r` attribute is the same in both screenshots
**Source:** Part123

---

### TC-P7-035
**Category:** Feature
**Test Name:** Learning curve gap interpretation — overfitting warning for classification
**Steps:**
1. Train a classification model via the Optuna tool using a very small dataset (< 200 rows)
2. View the Learning Curve chart
3. Observe the interpretation note below the chart
**Expected Result:** If the train-val gap > 10% (relative), a red warning "Overfitting detected" badge appears. If gap < 3%, a green "Generalizes well" badge appears. If in between, a gray "Moderate variance" note appears.
**Automation Hint:** Unit test — call `interpretLCGap(trainScore=0.95, valScore=0.70, lowerIsBetter=false)`; assert returns "overfitting"; call with `(0.82, 0.81, false)`; assert "generalizes_well"
**Source:** Part122

---

### TC-P7-036
**Category:** Feature
**Test Name:** Metric label formatting — no raw underscore keys shown
**Steps:**
1. Complete an Optuna run with `opt_metric=f1_weighted` and `secondary_metric=roc_auc`
2. View the winner metric cards and the trial history legend
**Expected Result:** All metric labels use human-readable display names: `"F1 Weighted"` (not `"F1_WEIGHTED"`), `"ROC-AUC"` (not `"ROC_AUC"`), `"R²"` (not `"r2"`). The `textTransform: uppercase` CSS is not applied to metric card labels.
**Automation Hint:** Playwright — assert winner card label text does not contain underscore characters; assert "ROC-AUC" appears (not "ROC_AUC"); assert "F1 Weighted" appears (not "F1_WEIGHTED")
**Source:** Part122

---

### TC-P7-037
**Category:** Feature
**Test Name:** Primary and secondary metric cards visually distinguished
**Steps:**
1. Run Optuna with a primary metric (ROC-AUC) and a secondary metric (F1 Macro)
2. View the winner metrics grid in OptunaResults
**Expected Result:** The primary metric card has a purple tint, border, and "★" label with hover tooltip. The secondary metric card has a green border and "◆" label with hover tooltip. Other metric cards have no special styling.
**Automation Hint:** Playwright — assert primary metric card has `border-color` matching purple; assert secondary metric card has `border-color` matching green; assert "★" text is present in primary card; assert "◆" text in secondary card
**Source:** Part121

---

### TC-P7-038
**Category:** Feature
**Test Name:** f1_macro always included in classification winner_metrics
**Steps:**
1. Run classification training via the Optuna tool
2. View the winner metrics grid
**Expected Result:** `f1_macro` is always present in `winner_metrics` for classification tasks, even when it was not the primary or secondary metric. The metric card shows an F1 Macro value.
**Automation Hint:** pytest — run classification training; assert `result["winner_metrics"]["f1_macro"]` is a valid float in [0, 1]
**Source:** Part121

---

### TC-P7-039
**Category:** Feature
**Test Name:** Regression winner metrics — mae/rmse/r2 always present
**Steps:**
1. Run regression training via the Optuna tool
2. View the winner metrics grid
**Expected Result:** `mae`, `rmse`, and `r2` are all present in `winner_metrics` for regression tasks regardless of the optimization metric chosen. No conditional gating on `r2 >= 0.60`.
**Automation Hint:** pytest — run regression training; assert `result["winner_metrics"]` contains `"mae"`, `"rmse"`, and `"r2"` keys with valid float values
**Source:** Part121

---

### TC-P7-040
**Category:** Feature
**Test Name:** Optuna Trial History chart — dynamic primary metric label in legend
**Steps:**
1. Run Optuna with `opt_metric=roc_auc`
2. View the Trial History chart legend
**Expected Result:** The trial score legend entry reads "ROC-AUC" (not the generic "Trial scores"). The legend reflects the actual `optuna_primary_metric` value.
**Automation Hint:** Playwright — assert trial history chart legend text contains "ROC-AUC" (or the actual metric display name) when `opt_metric=roc_auc` was selected
**Source:** Part121

---

### TC-P7-041
**Category:** Feature
**Test Name:** Optuna dynamic sampler description text
**Steps:**
1. Run Optuna with TPE sampler; view the "Bayesian Optimization Summary" section description
2. Re-run with QMC sampler; view the same section
**Expected Result:** When TPE is used, the description explains Tree Parzen Estimator. When QMC is used, the description explains Quasi-Monte Carlo / Sobol sampling. The text is not hardcoded to one sampler.
**Automation Hint:** Playwright — run with QMC; assert description section text contains "Quasi" or "Sobol"; run with TPE; assert text contains "Parzen" or "TPE"
**Source:** Part121

---

### TC-P7-042
**Category:** Feature
**Test Name:** Progress bar — no backwards jump from CV phase to Optuna phase
**Steps:**
1. Open the AutoML wizard and start a training run with tuning enabled
2. Observe the progress bar percentage throughout the entire run
**Expected Result:** The progress bar never decreases. After CV testing steps complete (up to ~55%), Optuna starts at 58%. The progress is monotonically non-decreasing from 0% to 100%.
**Automation Hint:** Playwright — capture all SSE `pct` values via `EventSource`; assert the array is non-decreasing; assert no value goes from 70 to 65 (the specific backwards jump that was fixed)
**Source:** Part122

---

### TC-P7-043
**Category:** Feature
**Test Name:** Granular save steps — no freeze at 93% during model serialization
**Steps:**
1. Run AutoML on a large dataset to produce a large model
2. Observe the progress bar after 90%
**Expected Result:** Instead of a single jump from 93% to done (with potential freeze during `joblib.dump`), the progress shows: 92% "Saving schema", 94% "Saving pipeline", 97% "Finalizing". No extended freeze period.
**Automation Hint:** Playwright — capture SSE events after 90%; assert events include pct values of approximately 92, 94, 97 before `done: true`
**Source:** Part122

---

### TC-P7-044
**Category:** Feature
**Test Name:** LLM explanation timeout — 45-second limit on all providers
**Steps:**
1. Trigger a `/optuna-explain` request that hangs (mock a slow LLM provider)
2. Verify the request times out after 45 seconds rather than hanging indefinitely
**Expected Result:** All LLM provider SDK calls in `_llm_explanation_raw` have `timeout=45`. Anthropic SDK calls are wrapped in `ThreadPoolExecutor` with a 45s timeout. A `TimeoutError` is caught and returned as an error response, not an unhandled hang.
**Automation Hint:** pytest — mock the LLM client to sleep for 60 seconds; call `_llm_explanation_raw` with `timeout=45`; assert it returns within ~46 seconds with an error, not after 60 seconds
**Source:** Part122

---

### TC-P7-045
**Category:** Feature
**Test Name:** Keep-Alive ping — HF Space stays awake
**Steps:**
1. Open the ml-portfolio app
2. Monitor network requests over the first 10 minutes
**Expected Result:** A `GET /health` ping is sent on page load and every 4 minutes thereafter. The `KeepAlive.tsx` component is present in the root layout.
**Automation Hint:** Playwright — intercept requests; wait 5 minutes; assert at least 2 `GET /health` requests were made; assert first request occurs within 5 seconds of page load
**Source:** Part119

---

### TC-P7-046
**Category:** E2E
**Test Name:** Optuna tool — full E2E training flow with tuning enabled
**Steps:**
1. Navigate to `/tools/optuna` on ml-portfolio
2. Upload the Titanic CSV dataset
3. In Step 2, select target column "Survived", enable tuning, select "ROC-AUC" metric, choose "QMC" sampler
4. Click "Run Optuna Tuning" and wait for SSE stream to complete
5. Verify all result sections are populated
**Expected Result:** Training completes without errors. OptunaResults shows: Bayesian Optimization Summary, Trial History chart, Learning Curve chart, Hyperparameter Importance bars, Best Tuned Parameters table, Winner Metrics grid, Feature Importance bars.
**Automation Hint:** Playwright full E2E — upload file; fill all Step 2 fields; click Run; wait for `done: true` SSE; assert all 6 result sections are visible and non-empty
**Source:** Part119, Part120, Part121

---

### TC-P7-047
**Category:** E2E
**Test Name:** AutoML wizard — full regression training E2E with per-column encoding and drop columns
**Steps:**
1. Navigate to the ML-Unified AutoML wizard
2. Upload a regression CSV dataset with mixed categorical and numeric columns
3. Set target column to the continuous target
4. In Step 2, drop one irrelevant column; set one categorical column to "Ordinal" encoding
5. Click "Run AutoML" and wait for completion
6. Verify results page shows regression metrics (MAE, RMSE, R²)
**Expected Result:** Training completes without errors. Drop column is excluded from the model. Ordinal encoding is applied to the specified column. Results show MAE, RMSE, R² values. No -1% progress display.
**Automation Hint:** Playwright — full wizard flow; intercept `/train` POST; assert `drop_cols_json` and `col_encoding_json` are present; assert results page shows MAE/RMSE/R²
**Source:** Part124

---

### TC-P7-048
**Category:** Backend API
**Test Name:** HF Space file upload — strip services/ml-api/ prefix from path_in_repo
**Steps:**
1. After a backend commit, upload `services/ml-api/app.py` to HF Space using the `huggingface_hub` API
2. Verify the file appears at the root `app.py` path on HF Space (not under `services/ml-api/app.py`)
**Expected Result:** The `path_in_repo` parameter strips the `services/ml-api/` prefix. The file is available at the HF Space root as `app.py`. The HF Space container reads the updated file.
**Automation Hint:** Integration test — after upload, call `hf_api.list_repo_files(repo_id="wram1708/ml-unified", repo_type="space")`; assert `"app.py"` is in the list; assert `"services/ml-api/app.py"` is NOT in the list
**Source:** Part119

---

### TC-P7-049
**Category:** Backend API
**Test Name:** Optuna multivariate TPE — multivariate=True in TPESampler
**Steps:**
1. Run Optuna tuning with TPE sampler
2. Verify the TPE sampler is instantiated with `multivariate=True`
**Expected Result:** The `TPESampler` is created with `multivariate=True`. This models parameter correlations jointly (e.g., learning_rate and n_estimators are tuned together). No errors occur on instantiation.
**Automation Hint:** pytest — inspect `automl_helpers.py`; assert `TPESampler(multivariate=True, ...)` is in the source; unit test that instantiation with `multivariate=True` succeeds
**Source:** Part119

---

### TC-P7-050
**Category:** Backend API
**Test Name:** Optuna MedianPruner — bad trials pruned early
**Steps:**
1. Run Optuna tuning with a dataset where some configurations perform poorly
2. Observe trial history — early-stopped (pruned) trials should be excluded from results
**Expected Result:** `MedianPruner` is added as a pruner to the Optuna study. Trials performing below the median at intermediate steps are pruned. No errors on pruner instantiation or during optimization.
**Automation Hint:** pytest — inspect `automl_helpers.py`; assert `MedianPruner()` is added to study; run optimization; assert some trials have `trial.state == optuna.trial.TrialState.PRUNED`
**Source:** Part119

---

### TC-P7-051
**Category:** UI
**Test Name:** Optuna AI explanation progress bar — simulated increment, caps at 88%, jumps to 100%
**Steps:**
1. Click "Get AI Explanation" in OptunaResults
2. Observe the progress bar behavior while the request is in flight
3. Note behavior when the response arrives
**Expected Result:** Progress bar increments by ~6% every 500ms. It caps at 88% while waiting. On response receipt, it immediately jumps to 100%. After 300ms, the explanation text appears (replacing the progress bar).
**Automation Hint:** Playwright — click "Get AI Explanation"; assert progress bar value is between 30–88% after 3 seconds; mock response after 5s; assert progress bar reaches 100% and then explanation text is visible
**Source:** Part120

---

### TC-P7-052
**Category:** UI
**Test Name:** Optuna results markdown rendering — headings, bold, italic, hr rendered as HTML
**Steps:**
1. Complete an Optuna AI explanation request where the LLM returns markdown text
2. View the AI Explanation section
**Expected Result:** The explanation is rendered as HTML: `###` headings become `<h3>`, `**bold**` becomes `<strong>`, `*italic*` becomes `<em>`, `---` becomes `<hr>`. Raw markdown syntax (`##`, `**`, `*`, `---`) is not visible in the output.
**Automation Hint:** Playwright — assert `.ai-explanation` section contains `<h3>` or `<strong>` HTML elements; assert no raw `**` or `##` text is visible in the rendered page
**Source:** Part120
