# TC-REC — Recent Regression & Feature Tests (Parts 113–116)

Source: Conversation_Part113–116.md  
Total: 24 test cases

---

### TC-REC-001
**Category:** Bug-Regression | AutoML  
**Test Name:** Back button in Feature Engineering returns to "Before we begin", not Upload  
**Steps:**
1. Open ML-Unified HF Space (`https://wram1708-ml-unified.hf.space`)
2. Upload a CSV file on the AutoML Model Selection (upload) screen — Step 1
3. Complete Step 1 and proceed to "Before we begin" (Step 0 — target column / dataset name)
4. Proceed to Feature Engineering (Step 1c)
5. Click the **Back** button on the Feature Engineering screen

**Expected Result:** Wizard navigates back to "Before we begin" (`_renderAutoMLStep0()`), NOT to the Upload screen. Re-upload is NOT triggered.  
**Source:** Part116, Part115

---

### TC-REC-002
**Category:** Bug-Regression | AutoML  
**Test Name:** Back button in Data Quality & Preprocessing returns to Feature Engineering, not Upload  
**Steps:**
1. Open ML-Unified HF Space
2. Upload a CSV file and complete the upload step
3. Complete "Before we begin" (target column, dataset name)
4. Complete Feature Engineering
5. Proceed to Data Quality & Preprocessing (Step 1b)
6. Click the **Back** button (check both Back button locations — lines 5011 and 5030)

**Expected Result:** Wizard navigates back to Feature Engineering (`_renderAutoMLStep1c()`). No data is lost. Re-upload NOT triggered.  
**Source:** Part116, Part115

---

### TC-REC-003
**Category:** Bug-Regression | AutoML  
**Test Name:** AutoML wizard step order is Upload → Before we begin → Feature Engineering → DQ&P → Run AutoML  
**Steps:**
1. Open ML-Unified HF Space
2. Upload a CSV file
3. Record which screen appears after upload (should be "Before we begin")
4. Click Next through each step and record the sequence

**Expected Result:** Step sequence is exactly:
- Step 1: AutoML: Model Selection (upload)
- Step 0: Before we begin (target column, dataset name)
- Step 1c: Feature Engineering
- Step 1b: Data Quality & Preprocessing
- Step 2: Run AutoML  
**Source:** Part116

---

### TC-REC-004
**Category:** Bug-Regression | UI  
**Test Name:** AI Explanation content is fully hidden on training completion until "Get AI Explanation" is clicked  
**Steps:**
1. Open ML-Unified HF Space
2. Upload a CSV, configure AutoML settings, and run training to completion
3. Observe the right panel immediately after training completes — before clicking any button

**Expected Result:** The right panel shows NO explanation content: no "WHY IT WON" text, no charts, no rule-based explanation. Panel remains empty or shows only a prompt/button.  
**Source:** Part116

---

### TC-REC-005
**Category:** Bug-Regression | UI  
**Test Name:** Clicking "Get AI Explanation" reveals explanation content after training  
**Steps:**
1. Open ML-Unified HF Space
2. Upload a CSV, run AutoML to completion
3. Confirm the right panel is empty (per TC-REC-004)
4. Click the **Get AI Explanation** button

**Expected Result:** After clicking, the AI explanation content (WHY IT WON text and/or charts) becomes visible.  
**Source:** Part116

---

### TC-REC-006
**Category:** Bug-Regression | Backend  
**Test Name:** Cohere API call uses model `command-a-03-2025`, not deprecated `command-r-plus`  
**Steps:**
1. Open ml-portfolio AutoML tool
2. Click "Use my API key" and enter Cohere base URL `https://api.cohere.com/compatibility/v1`
3. Observe the placeholder hint text in the model name field
4. Enter `command-a-03-2025` as the model name and run AI analysis

**Expected Result:** Placeholder hint shows `command-a-03-2025` (not `command-r-plus`). API call succeeds without a "model was removed" error.  
**Source:** Part116

---

### TC-REC-007
**Category:** Bug-Regression | UI  
**Test Name:** Progress label shows correct provider name when using custom base URL  
**Steps:**
1. Open ml-portfolio AutoML tool
2. Enter a Cohere API key and base URL with model `command-a-03-2025`
3. Run AutoML AI analysis and observe the progress label during loading

**Expected Result:** Progress label shows `"Asking command-a-03-2025…"`, NOT `"Asking Gemini 2.5 Flash…"` or any other incorrect provider name.  
**Source:** Part116

---

### TC-REC-008
**Category:** Bug-Regression | UI  
**Test Name:** Switching away from custom base URL stops routing to custom provider  
**Steps:**
1. Open ml-portfolio AutoML tool
2. Enter a Cohere API key and base URL, then run an AI analysis call
3. Hide or clear the API key input (switch back to default provider, e.g. Gemini)
4. Run another AI analysis call and observe the progress label and routing

**Expected Result:** Second call uses the default provider label (e.g. `"Asking Gemini 2.5 Flash…"`) and does NOT route to Cohere. No stale `customLLMUrl` used when key input is hidden.  
**Source:** Part116

---

### TC-REC-009
**Category:** Bug-Regression | AutoML  
**Test Name:** ml-portfolio AutoML page does not crash when using Gemini or Cohere  
**Steps:**
1. Open ml-portfolio AutoML tool at `/tools/automl`
2. Upload a CSV file and complete all wizard steps
3. On Step 4 (Results), select Gemini 2.5 Flash (or Cohere with custom key)
4. Click to generate AI analysis
5. Observe the page — wait for results or an error

**Expected Result:** Page renders fully without a Chrome "This page couldn't load" crash. Results or a user-visible error message are shown. The tab does not die.  
**Source:** Part116

---

### TC-REC-010
**Category:** Bug-Regression | AutoML  
**Test Name:** ModelComparisonChart renders without TypeError when model_comparison has `algorithm` field  
**Steps:**
1. Open ml-portfolio AutoML tool
2. Run a full AutoML pipeline to Step 4 (Results) with any LLM provider
3. Observe the Model Comparison Chart in the results

**Expected Result:** Model Comparison Chart renders without error. Each entry has `algorithm`, `fitness_score`, and `reason` fields. No uncaught TypeError referencing `.replace()` on `undefined`.  
**Source:** Part116

---

### TC-REC-011
**Category:** Bug-Regression | AutoML  
**Test Name:** LLM response with string instead of array for model_comparison does not crash the page  
**Steps:**
1. In a test/dev environment, simulate an LLM response where `model_comparison` is a string (not an array)
2. Pass this response through the `extractJson` + `toArr()` normalization path in ml-portfolio
3. Observe the Results page

**Expected Result:** `toArr()` normalizes the string/object to an array. The page does not crash. Either a chart is rendered or a graceful empty state is shown.  
**Source:** Part116

---

### TC-REC-012
**Category:** Bug-Regression | AutoML  
**Test Name:** `/tools/automl` error boundary catches render errors and shows "Try again" button  
**Steps:**
1. Open ml-portfolio at `/tools/automl`
2. Simulate or trigger a render-level error (e.g., pass malformed data causing a component exception)
3. Observe the page

**Expected Result:** Instead of a blank Chrome tab, a custom error UI is shown with a "Try again" button from `error.tsx`.  
**Source:** Part116

---

### TC-REC-013
**Category:** Bug-Regression | AutoML  
**Test Name:** HF Space training progresses to 100% without stalling at 93%  
**Steps:**
1. Open ML-Unified HF Space
2. Upload a CSV and run AutoML training
3. Monitor the progress bar percentage
4. Wait for training to reach 100%

**Expected Result:** Training progresses to 100% without stalling. The SSE stream closes cleanly after training.  
**Source:** Part115

---

### TC-REC-014
**Category:** Bug-Regression | AutoML  
**Test Name:** AI Analysis results panel shows LLM errors inline, not silently  
**Steps:**
1. Open ml-portfolio AutoML tool
2. Enter an invalid API key or use a provider that will return an error
3. Run through all steps to Step 4 (Results) and trigger AI analysis

**Expected Result:** A red inline error banner appears showing the LLM error message. Page remains usable.  
**Source:** Part115

---

### TC-REC-015
**Category:** Bug-Regression | Backend  
**Test Name:** Groq provider uses updated model IDs  
**Steps:**
1. Open ml-portfolio AutoML tool
2. Select Groq as the provider with a valid Groq API key
3. Select model `llama-3.3-70b-versatile` (or `llama-3.1-8b-instant`)
4. Run AI analysis

**Expected Result:** API call succeeds without "model not found" or deprecation error. Old model IDs `llama3-70b-8192` and `llama3-8b-8192` are NOT used.  
**Source:** Part115, Part114

---

### TC-REC-016
**Category:** Feature | AutoML  
**Test Name:** "Use my API key" flow accepts any OpenAI-compatible provider via base URL  
**Steps:**
1. Open ml-portfolio AutoML tool, proceed to Step 4 (Results)
2. Click "Use my API key"
3. Enter a Cohere API key, base URL `https://api.cohere.com/compatibility/v1`, and model `command-a-03-2025`
4. Run AI analysis

**Expected Result:** Base URL input field is visible when "Use my API key" is active. Request is routed to the custom base URL using the OpenAI-compatible path. Results returned from Cohere.  
**Source:** Part115

---

### TC-REC-017
**Category:** Feature | AutoML  
**Test Name:** AI analysis request sends `baseUrl` only when both API key AND base URL are non-empty  
**Steps:**
1. Open ml-portfolio AutoML tool, "Use my API key" active
2. Enter a base URL but leave the API key field empty — run analysis
3. Clear the base URL but enter a valid key — run analysis
4. Enter both a valid key and base URL — run analysis

**Expected Result:**
- Case 1 (URL only, no key): request does NOT send `baseUrl`
- Case 2 (key only, no URL): request uses selected provider's default routing
- Case 3 (both filled): request sends `baseUrl` and routes to custom provider  
**Source:** Part116

---

### TC-REC-018
**Category:** Feature | UI  
**Test Name:** Gemini AI analysis returns full JSON with maxTokens 3000  
**Steps:**
1. Open ml-portfolio AutoML tool
2. Select Gemini 2.5 Flash as the provider
3. Upload a CSV with enough complexity to require a full 6-field JSON response
4. Run AI analysis on Step 4

**Expected Result:** AI analysis results fully parsed and all 6 expected fields populated. No raw JSON text shown, no truncation error.  
**Source:** Part115

---

### TC-REC-019
**Category:** Feature | UI  
**Test Name:** DatasetEstimator shows Recommended RAM and CPU cores  
**Steps:**
1. Open ml-portfolio Feature Selection tool
2. Upload a CSV file
3. Observe the DatasetEstimator component on the upload card

**Expected Result:** DatasetEstimator shows CPU core count and a "Recommended RAM" value (derived from peak memory × 3). Does NOT display raw `navigator.deviceMemory` value.  
**Source:** Part114

---

### TC-REC-020
**Category:** Feature | UI  
**Test Name:** DatasetEstimator appears in AutoML config step and Preprocessing left sidebar  
**Steps:**
1. Open ml-portfolio AutoML tool, upload a CSV, proceed to the config step (Step 2)
2. Observe the DatasetEstimator component
3. Open ml-portfolio Preprocessing tool, upload a CSV, open the configure panel
4. Observe the left sidebar for the DatasetEstimator

**Expected Result:** DatasetEstimator visible and showing time/memory estimates in both locations.  
**Source:** Part114

---

### TC-REC-021
**Category:** Feature | UI  
**Test Name:** Web Workers run UMAP, FA, and Gibbs LDA off the main thread (tab does not freeze)  
**Steps:**
1. Open ml-portfolio Feature Selection tool
2. Upload a CSV with 500+ rows and 10+ columns
3. Enable UMAP and Factor Analysis
4. Click Run / compute
5. Interact with the tab (click buttons, scroll) while computation runs

**Expected Result:** Browser tab remains responsive during UMAP and FA computation. Results appear after completion without the tab having frozen.  
**Source:** Part114

---

### TC-REC-022
**Category:** Feature | UI  
**Test Name:** Preprocessing right panel is scrollable and shows all 4 toggles  
**Steps:**
1. Open ml-portfolio Preprocessing tool
2. Upload a CSV and open the configure step
3. In the right panel, observe whether all 4 toggles are visible
4. If needed, scroll down in the right panel

**Expected Result:** All 4 toggles are accessible by scrolling. The right panel scrolls independently.  
**Source:** Part114

---

### TC-REC-023
**Category:** Feature | AutoML  
**Test Name:** ML-Unified Launch App button points to HF Space, not Render  
**Steps:**
1. Open ml-portfolio at the main tools registry or project cards page
2. Find the ML-Unified entry
3. Click the **Launch App** button

**Expected Result:** Browser navigates to `https://wram1708-ml-unified.hf.space` (or equivalent HF Space URL), NOT any `onrender.com` URL.  
**Source:** Part115

---

### TC-REC-024
**Category:** Feature | Backend  
**Test Name:** Streaming CSV parse handles large files without loading entire file into memory  
**Steps:**
1. Open ml-portfolio Preprocessing, Feature Engineering, or Feature Selection tool
2. Upload a CSV file larger than 10MB (e.g., 50MB test file)
3. Allow the file to parse and observe memory behavior

**Expected Result:** File parses successfully using streaming 64KB chunks. Peak memory is significantly less than 2× file size. Quoted fields and `\r\n` line endings are handled correctly.  
**Source:** Part114
