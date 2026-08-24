# TC-P8 — Parts 125–157 Test Cases (Round 4)

**Generated:** 2026-07-05  
**Parts covered:** 125–157 (RAG pipeline, Chat AI, Drift, AutoML Pipeline, Feature Eng, Ensemble, SHAP, Optuna, KB quality)  
**Total:** 90 test cases  
**Status:** Complete — full coverage for Parts 125–157

---

## RAG Pipeline — Backend

---

### TC-P8-001
**Category:** Feature  
**Test Name:** `/rag/health` returns indexed chunk count after startup  
**Steps:**
1. Start the ML-Unified FastAPI server
2. `GET /rag/health`
**Expected Result:** `{ "status": "ok", "chunks_indexed": N }` where N > 0 (KB docs indexed at startup)  
**Automation Hint:** `pytest` — assert `response.json()["chunks_indexed"] > 0`  
**Source:** Part125

---

### TC-P8-002
**Category:** Feature  
**Test Name:** `/rag/query` streams SSE source, token, and done events  
**Steps:**
1. `POST /rag/query` with `{ "query": "what is XGBoost?", "provider": "groq", ... }`
2. Parse the SSE stream
**Expected Result:** Stream contains at least one `{"type":"source"}` event, one or more `{"type":"token"}` events, and exactly one `{"type":"done"}` event  
**Automation Hint:** Read SSE lines, collect `type` values; assert all three present  
**Source:** Part125

---

### TC-P8-003
**Category:** Feature  
**Test Name:** `/rag/query` done event includes metadata fields  
**Steps:**
1. `POST /rag/query` with a valid query
2. Parse done event from SSE stream
**Expected Result:** Done event contains `latency_ms`, `chunks_retrieved`, `cache_hit`, `answer_source`, `confidence`, `embedding_used`  
**Automation Hint:** `assert all(k in done_event for k in ["latency_ms","chunks_retrieved","cache_hit","answer_source","confidence"])`  
**Source:** Part125

---

### TC-P8-004
**Category:** Feature  
**Test Name:** BM25 + dense hybrid retrieval returns more candidates than dense-only  
**Steps:**
1. Query `/rag/query` with `embedding_model: "minilm"`
2. Check `candidates_retrieved` in done event
**Expected Result:** `candidates_retrieved` > 5 (RRF merges both lists; more candidates than either alone)  
**Automation Hint:** Parse done event `candidates_retrieved` field; assert > 5  
**Source:** Part130

---

### TC-P8-005
**Category:** Feature  
**Test Name:** Query expansion generates alternate phrasings  
**Steps:**
1. `POST /rag/query` with a short ambiguous query
2. Parse done event `expanded_queries` field
**Expected Result:** `expanded_queries` contains at least 1 alternate phrasing different from the original query  
**Automation Hint:** `assert len(done["expanded_queries"]) >= 1`  
**Source:** Part130

---

### TC-P8-006
**Category:** Feature  
**Test Name:** Semantic cache returns `cache_hit: true` on identical query  
**Steps:**
1. `POST /rag/query` with query Q (first call — cache miss)
2. `POST /rag/query` with the same query Q (second call)
3. Check done event of second call
**Expected Result:** Second call done event has `cache_hit: true`; response arrives faster than first call  
**Automation Hint:** Record `latency_ms` both calls; assert second `latency_ms` < first; assert `cache_hit == true`  
**Source:** Part130

---

### TC-P8-007
**Category:** Bug-Regression  
**Test Name:** Semantic cache is bypassed when `force_web: true`  
**Steps:**
1. `POST /rag/query` with query Q (first call — populates cache)
2. `POST /rag/query` with same query Q and `force_web: true`
3. Check done event of second call
**Expected Result:** Second call has `cache_hit: false`; `answer_source` is `"web"`  
**Automation Hint:** assert `done["cache_hit"] == False` and `done["answer_source"] == "web"`  
**Source:** Part157

---

### TC-P8-008
**Category:** Feature  
**Test Name:** CRAG triggers web fallback when KB retrieval confidence is low  
**Steps:**
1. `POST /rag/query` with a query on a topic not in the knowledge base (e.g. "latest React 19 features")
2. Parse done event
**Expected Result:** `done["web_fallback_used"] == true`; at least one source event has `source` starting with `"web:"`  
**Automation Hint:** assert `done["web_fallback_used"] == True`  
**Source:** Part143

---

### TC-P8-009
**Category:** Feature  
**Test Name:** `/rag/ingest` accepts markdown file and indexes chunks  
**Steps:**
1. `POST /rag/ingest` with a `.md` file upload and a `session_id`
2. `GET /rag/uploads` for that session
3. `POST /rag/query` with a query about content in that file
**Expected Result:** Ingest returns 200; uploads list includes the filename; query retrieves chunks from the uploaded file  
**Automation Hint:** pytest with `httpx` multipart upload  
**Source:** Part138

---

### TC-P8-010
**Category:** Feature  
**Test Name:** Tiered retrieval returns uploaded doc chunks first when session has uploads  
**Steps:**
1. Ingest a document for `session_id = "test-session"`
2. `POST /rag/query` with `session_id: "test-session"` and a query matching uploaded content
3. Parse source events
**Expected Result:** First source event chunk has `uploaded: true`; `answer_source` is `"uploaded_doc"`  
**Automation Hint:** assert first source event doc matches uploaded content  
**Source:** Part157

---

### TC-P8-011
**Category:** Feature  
**Test Name:** Tiered retrieval falls back to KB when uploaded doc score < 0.15  
**Steps:**
1. Ingest a document for `session_id = "test-session"`
2. `POST /rag/query` with a query completely unrelated to the uploaded doc but present in KB
3. Parse done event
**Expected Result:** `answer_source` is `"knowledge_base"` (not `"uploaded_doc"`); KB chunks returned  
**Automation Hint:** assert `done["answer_source"] == "knowledge_base"`  
**Source:** Part157

---

### TC-P8-012
**Category:** Feature  
**Test Name:** `/rag/agent` endpoint streams SSE with same event types as `/rag/query`  
**Steps:**
1. `POST /rag/agent` with a complex multi-step query
2. Parse SSE stream
**Expected Result:** Stream contains `source`, `token`, and `done` event types; done event includes `answer_source` and `confidence`  
**Automation Hint:** Same SSE parse as TC-P8-002; assert done has `answer_source`  
**Source:** Part145

---

### TC-P8-013
**Category:** Feature  
**Test Name:** `force_web: true` on `/rag/agent` triggers web-only sources  
**Steps:**
1. `POST /rag/agent` with `force_web: true` and any query
2. Parse done event
**Expected Result:** `answer_source` is `"web"`; source events contain web URLs  
**Automation Hint:** assert `done["answer_source"] == "web"`  
**Source:** Part157

---

### TC-P8-014
**Category:** Feature  
**Test Name:** Semantic cache key is dataset-specific (ctx_hash isolation)  
**Steps:**
1. `POST /rag/query` with query Q and `tool_context: "dataset A stats"`  (populates cache)
2. `POST /rag/query` with same query Q and `tool_context: "dataset B stats"` (different context)
3. Check second call done event
**Expected Result:** Second call is a cache miss (`cache_hit: false`) — different `tool_context` produces different cache key  
**Automation Hint:** assert `done["cache_hit"] == False` on second call  
**Source:** Part130

---

### TC-P8-015
**Category:** Bug-Regression  
**Test Name:** KB docs are indexed at startup (DATA_DIR relative path fix)  
**Steps:**
1. Start server; `GET /rag/health`
**Expected Result:** `chunks_indexed > 0` — confirms `data/knowledge_base/*.md` is loaded (not `/data/` absolute path which fails outside Docker)  
**Automation Hint:** assert `response.json()["chunks_indexed"] > 0`  
**Source:** Part139

---

## Chat AI Frontend

---

### TC-P8-016
**Category:** Feature  
**Test Name:** Answer source badge shows correct label for each source type  
**Steps:**
1. Open ToolsAIChat; ask a question that returns KB answer → badge shows "Knowledge Base"
2. Ask with uploaded doc loaded → badge shows "Your Doc"
3. Ask with dataset context → badge shows "Dataset"
4. Ask with force_web active → badge shows "Web"
**Expected Result:** Each scenario shows the correct label from `SOURCE_LABELS` map  
**Automation Hint:** Playwright — assert badge text per scenario  
**Source:** Part150

---

### TC-P8-017
**Category:** Feature  
**Test Name:** Confidence badge color matches level  
**Steps:**
1. Trigger a HIGH confidence response; inspect badge
2. Trigger a MEDIUM confidence response; inspect badge
3. Trigger a LOW confidence response; inspect badge
**Expected Result:** HIGH = green (#34d399), MEDIUM = amber (#f59e0b), LOW = red (#f87171)  
**Automation Hint:** Playwright — `getComputedStyle` on badge element; assert `color` value  
**Source:** Part150

---

### TC-P8-018
**Category:** Bug-Regression  
**Test Name:** Sources panel is hidden when answer_source is "dataset"  
**Steps:**
1. Load a CSV dataset in a tool page with ToolsAIChat
2. Ask a question answered from dataset context
3. Inspect the chat response area
**Expected Result:** Sources panel (collapsed/expanded toggle) is not rendered; badge shows "Dataset"  
**Automation Hint:** Playwright — assert sources toggle button not present in DOM  
**Source:** Part157

---

### TC-P8-019
**Category:** Bug-Regression  
**Test Name:** "Dataset" badge shown (not "Knowledge Base") when has_dataset=true  
**Steps:**
1. Load a CSV in a tool page
2. Ask a general ML question via ToolsAIChat
3. Observe badge label
**Expected Result:** Badge shows "Dataset", not "Knowledge Base", even if KB chunks were used as supplementary context  
**Automation Hint:** Playwright — assert badge text === "Dataset"  
**Source:** Part157

---

### TC-P8-020
**Category:** Feature  
**Test Name:** Web override toggle button activates and shows amber highlight  
**Steps:**
1. Open ToolsAIChat on any tool page
2. Click the globe/web override button
**Expected Result:** Button background turns amber (#f59e0b22); title changes to "Web override active..."  
**Automation Hint:** Playwright — click button; assert `background` style contains `f59e0b`  
**Source:** Part157

---

### TC-P8-021
**Category:** Feature  
**Test Name:** Web override sends `force_web: true` in request and returns web sources  
**Steps:**
1. Activate web override toggle
2. Send any query
3. Observe sources panel
**Expected Result:** Sources panel shows web URLs; badge shows "Web"; sources are from live web not KB  
**Automation Hint:** Playwright — intercept network request; assert body contains `force_web: true`  
**Source:** Part157

---

### TC-P8-022
**Category:** Feature  
**Test Name:** "How I Searched" section shows expanded queries and candidate count  
**Steps:**
1. Ask a question via ToolsAIChat (non-cached response)
2. Click "How I Searched" toggle below the response
**Expected Result:** Expanded queries list shows alternate phrasings; "X candidates → reranked to Y chunks" shown  
**Automation Hint:** Playwright — click How I Searched button; assert query variant rows visible  
**Source:** Part150

---

### TC-P8-023
**Category:** Feature  
**Test Name:** "Cached" badge appears on semantic cache hit  
**Steps:**
1. Send query Q via ToolsAIChat (first call)
2. Send same query Q again (second call)
**Expected Result:** Second response shows green "CACHED" badge in sources row  
**Automation Hint:** Playwright — assert `.cached-badge` or element with text "Cached" visible  
**Source:** Part130

---

### TC-P8-024
**Category:** Feature  
**Test Name:** Deep Search mode (agent endpoint) shows "How I Searched" with rewrite iterations  
**Steps:**
1. Enable Deep Search toggle in ToolsAIChat settings
2. Ask a complex multi-hop question
3. Expand "How I Searched"
**Expected Result:** Expanded queries section shows multiple query variants from agent rewrite loop  
**Automation Hint:** Playwright — count query variant rows; assert > 1  
**Source:** Part145

---

### TC-P8-025
**Category:** Feature  
**Test Name:** Jina v3 toggle sends `embedding_model: "jina"` in request  
**Steps:**
1. Open ToolsAIChat settings panel
2. Toggle Jina v3 on
3. Send a query; intercept network request
**Expected Result:** Request body contains `"embedding_model": "jina"`  
**Automation Hint:** Playwright network intercept; assert request JSON field  
**Source:** Part141

---

## Drift Detection

---

### TC-P8-026
**Category:** Feature  
**Test Name:** `GET /drift/{model_id}` returns drift score for trained model  
**Steps:**
1. Train a model; make 10+ predictions via `/predict`
2. `GET /drift/{model_id}`
**Expected Result:** Response has `overall_score`, `overall_level`, `n_recent`, `features` array  
**Automation Hint:** pytest — assert all fields present; `n_recent >= 10`  
**Source:** Part151

---

### TC-P8-027
**Category:** Feature  
**Test Name:** Batch CSV upload computes drift vs training baseline  
**Steps:**
1. Train a model
2. `POST /drift/{model_id}/upload` with a CSV of new data
3. Inspect response
**Expected Result:** Response has `overall_score`, `source: "upload"`, `filename`, `features` with PSI scores per column  
**Automation Hint:** pytest multipart upload; assert `source == "upload"` and `features` non-empty  
**Source:** Part152

---

### TC-P8-028
**Category:** Feature  
**Test Name:** Drift snapshot saved to history after upload  
**Steps:**
1. Upload drift CSV for model
2. `GET /drift/{model_id}/history`
**Expected Result:** History contains at least 1 snapshot with `ts`, `overall_score`, `overall_level`, `features`  
**Automation Hint:** pytest — assert `len(history) >= 1`  
**Source:** Part152

---

### TC-P8-029
**Category:** Feature  
**Test Name:** Batch label appears in history snapshot  
**Steps:**
1. `POST /drift/{model_id}/upload?label=Week3` with a CSV
2. `GET /drift/{model_id}/history`
**Expected Result:** Latest snapshot in history has `label: "Week3"`  
**Automation Hint:** pytest — assert `history[-1]["label"] == "Week3"`  
**Source:** Part153

---

### TC-P8-030
**Category:** Feature  
**Test Name:** Drift trend chart renders in UI with multiple snapshots  
**Steps:**
1. Upload 3 drift CSVs for a model
2. Navigate to Drift page in ml-unified frontend
3. Select the model
**Expected Result:** Trend chart shows 3 data points (one per upload); overall score line visible  
**Automation Hint:** Playwright — assert chart canvas present; count data points  
**Source:** Part153

---

### TC-P8-031
**Category:** Feature  
**Test Name:** Correlation matrix shown when 2+ numeric features present  
**Steps:**
1. Upload a drift CSV with 3+ numeric columns
2. Observe drift results in UI
**Expected Result:** Correlation matrix section visible; cell values between -1 and 1  
**Automation Hint:** Playwright — assert correlation matrix table rendered  
**Source:** Part153

---

### TC-P8-032
**Category:** Feature  
**Test Name:** Drift LLM explain endpoint streams SSE tokens  
**Steps:**
1. `POST /drift/{model_id}/explain` with drift result JSON in body and `provider=groq`
2. Parse SSE stream
**Expected Result:** Stream contains token events; final response is a natural language explanation of drift findings  
**Automation Hint:** pytest SSE parse; assert at least 1 token event received  
**Source:** Part151

---

### TC-P8-033
**Category:** Feature  
**Test Name:** Drift chat context includes per-column stats (not just overall score)  
**Steps:**
1. Navigate to Drift page with a model loaded and drift computed
2. Open ToolsAIChat and ask "which feature drifted most?"
**Expected Result:** AI response references specific column names and their drift scores (not just "there is drift")  
**Automation Hint:** Playwright — assert response text contains a column name from the model schema  
**Source:** Part156

---

## AutoML Pipeline & Pipeline Builder

---

### TC-P8-034
**Category:** Feature  
**Test Name:** PipelineContext persists across page navigation  
**Steps:**
1. Run AutoML wizard; complete training
2. Navigate away; navigate to /tools/pipeline-builder
3. Inspect pipeline state
**Expected Result:** `automlWinner` and `automlRanking` are populated from the completed AutoML run  
**Automation Hint:** Playwright — navigate to pipeline builder; assert winner card shows algorithm name  
**Source:** Part127

---

### TC-P8-035
**Category:** Feature  
**Test Name:** CsvFromContextBanner appears on tool pages when pipeline CSV is available  
**Steps:**
1. Complete AutoML preprocessing step (populates `csvB64` in context)
2. Navigate to /tools/feature-engineering
**Expected Result:** CsvFromContextBanner appears at top of page offering to load CSV from pipeline  
**Automation Hint:** Playwright — assert banner element visible  
**Source:** Part136

---

### TC-P8-036
**Category:** Feature  
**Test Name:** Download winner model returns a `.pkl` file  
**Steps:**
1. Train a model via AutoML
2. Click "Download Model" button in Step 4 Results
**Expected Result:** Browser triggers download of `[model_id]_pipeline.pkl`  
**Automation Hint:** Playwright — listen for download event; assert filename ends with `.pkl`  
**Source:** Part136

---

### TC-P8-037
**Category:** Feature  
**Test Name:** Download Optuna params returns valid JSON  
**Steps:**
1. Run Optuna tuning on a model
2. Click "Download Params" button
**Expected Result:** Browser downloads a `.json` file containing `best_params` object  
**Automation Hint:** Playwright — intercept download; parse JSON; assert `best_params` key present  
**Source:** Part136

---

### TC-P8-038
**Category:** Feature  
**Test Name:** AutoML winner auto-written to PipelineContext on training completion  
**Steps:**
1. Run AutoML wizard to completion
2. Check PipelineContext state (via localStorage or pipeline builder page)
**Expected Result:** `automlWinner` populated automatically without needing to click "Save to Pipeline"  
**Automation Hint:** Playwright — after training completes, navigate to pipeline builder; assert winner card non-empty  
**Source:** Part136

---

### TC-P8-039
**Category:** Feature  
**Test Name:** Pipeline builder cards show correct locked/ready/done states  
**Steps:**
1. Navigate to /tools/pipeline-builder with fresh state
2. Observe card states
**Expected Result:** Only Preprocessing card is in "ready" state; all subsequent cards are "locked"  
**Automation Hint:** Playwright — assert first card has ready indicator; remaining cards have locked indicator  
**Source:** Part127

---

## Feature Engineering

---

### TC-P8-040
**Category:** Feature  
**Test Name:** DatetimePanel creates `_year`, `_month`, `_day`, `_dayofweek` columns from datetime column  
**Steps:**
1. Upload a CSV with a datetime column in Feature Engineering
2. Select the datetime column in DatetimePanel
3. Apply transform
**Expected Result:** Output CSV contains `colname_year`, `colname_month`, `colname_day`, `colname_dayofweek` columns  
**Automation Hint:** pytest backend — verify output columns; or Playwright — check result table headers  
**Source:** Part125

---

### TC-P8-041
**Category:** Feature  
**Test Name:** RatioDiffPanel creates ratio and diff columns for a column pair  
**Steps:**
1. Select columns A and B in RatioDiffPanel
2. Apply transform
**Expected Result:** Output CSV contains `A_div_B` and `A_minus_B` columns  
**Automation Hint:** Playwright — assert new column names in result preview  
**Source:** Part125

---

### TC-P8-042
**Category:** Feature  
**Test Name:** Binning creates `col_binN` column with correct bin count  
**Steps:**
1. Select a numeric column; set bins = 5
2. Apply binning transform
**Expected Result:** Output column `colname_bin5` present; values are integers 0–4  
**Automation Hint:** pytest backend — assert `col_bin5` in output; unique values in [0,1,2,3,4]  
**Source:** Part125

---

### TC-P8-043
**Category:** Feature  
**Test Name:** Polynomial feature creates `col_sq` column  
**Steps:**
1. Select a numeric column in polynomial section
2. Apply degree-2 transform
**Expected Result:** Output CSV contains `colname_sq`; values equal original values squared  
**Automation Hint:** pytest — assert `col_sq` ≈ `col ** 2` for sampled rows  
**Source:** Part125

---

## Ensemble Methods

---

### TC-P8-044
**Category:** Bug-Regression  
**Test Name:** Ensemble leaderboard shows algorithm name (not blank)  
**Steps:**
1. Navigate to /tools/ensemble
2. Upload a CSV; select 3 algorithms; run ensemble
3. Inspect leaderboard
**Expected Result:** Each leaderboard row shows a non-empty algorithm name (e.g. "Random Forest", "XGBoost")  
**Automation Hint:** Playwright — assert leaderboard rows have non-empty name text  
**Source:** Part137

---

### TC-P8-045
**Category:** Bug-Regression  
**Test Name:** Ensemble rank shows SVG medal ribbon (not emoji)  
**Steps:**
1. Run ensemble; inspect top 3 leaderboard rows
**Expected Result:** Rank column shows SVG ribbon icons (gold/silver/bronze), not 🥇🥈🥉 emoji  
**Automation Hint:** Playwright — assert `<svg>` element present in rank cell; assert no emoji text node  
**Source:** Part137

---

### TC-P8-046
**Category:** Bug-Regression  
**Test Name:** Ensemble accent color matches page theme (not hardcoded green)  
**Steps:**
1. Navigate to /tools/ensemble (page accent is pink #f472b6)
2. Run ensemble; inspect leaderboard bar colors and button borders
**Expected Result:** Progress bars and accent elements use pink (#f472b6), not the old hardcoded #10b981 green  
**Automation Hint:** Playwright — assert fill/border color on leaderboard bars contains `f472b6`  
**Source:** Part137

---

### TC-P8-047
**Category:** Feature  
**Test Name:** Ensemble leaderboard shows CV score per algorithm  
**Steps:**
1. Run ensemble with 3 algorithms
2. Inspect leaderboard rows
**Expected Result:** Each row shows a numeric CV score (e.g. accuracy or R²)  
**Automation Hint:** Playwright — assert score cell text matches `\d+\.\d+` pattern  
**Source:** Part137

---

## RAG Pipeline — Edge Cases & Error Handling

---

### TC-P8-048
**Category:** Feature  
**Test Name:** Duplicate ingest of same file returns 409  
**Steps:**
1. `POST /rag/ingest` with file `guide.md` for `session_id = "s1"`
2. `POST /rag/ingest` with the same file and same session_id again
**Expected Result:** Second call returns HTTP 409 with message indicating duplicate  
**Automation Hint:** pytest — assert `response.status_code == 409`  
**Source:** Part138

---

### TC-P8-049
**Category:** Feature  
**Test Name:** `DELETE /rag/uploads/{source}` removes chunks from index  
**Steps:**
1. Ingest a document; verify it appears in `/rag/uploads`
2. `DELETE /rag/uploads/{source_name}`
3. Query about content from that document
**Expected Result:** Delete returns 200; document no longer in uploads list; query no longer retrieves chunks from it  
**Automation Hint:** pytest — assert source absent from uploads list after delete  
**Source:** Part138

---

### TC-P8-050
**Category:** Feature  
**Test Name:** `/rag/ingest` accepts PDF file and indexes its text  
**Steps:**
1. `POST /rag/ingest` with a small PDF file
2. Query for content known to be in that PDF
**Expected Result:** Ingest returns 200; query retrieves at least one chunk with source matching the PDF filename  
**Automation Hint:** pytest multipart upload with `files={"file": ("test.pdf", pdf_bytes, "application/pdf")}`  
**Source:** Part138

---

### TC-P8-051
**Category:** Feature  
**Test Name:** Session isolation — session A cannot retrieve session B's uploaded chunks  
**Steps:**
1. Ingest document D1 for `session_id = "session-A"`
2. `POST /rag/query` with `session_id = "session-B"` querying D1 content
**Expected Result:** Response does not contain chunks from D1; `answer_source` is `"knowledge_base"` or `"none"`, not `"uploaded_doc"`  
**Automation Hint:** pytest — assert no source event references D1 filename  
**Source:** Part146

---

### TC-P8-052
**Category:** Feature  
**Test Name:** `/rag/query` returns error when no API key provided for selected provider  
**Steps:**
1. `POST /rag/query` with `provider: "groq"`, `user_key: ""`, and no GROQ_API_KEY env var set
**Expected Result:** SSE stream contains `{"type": "error", "message": "No API key for provider 'groq'."}` event  
**Automation Hint:** pytest — assert error event present in SSE stream  
**Source:** Part125

---

### TC-P8-053
**Category:** Bug-Regression  
**Test Name:** Provider error tokens not stored in semantic cache  
**Steps:**
1. `POST /rag/query` with an invalid API key (triggers provider error string like `[Groq error 401]`)
2. `POST /rag/query` with same query and a valid key
**Expected Result:** Second call is a fresh generation (not cached error); `cache_hit: false`  
**Automation Hint:** pytest — assert second call `cache_hit == False` and response is valid text  
**Source:** Part130

---

### TC-P8-054
**Category:** Feature  
**Test Name:** Semantic cache is provider-specific (groq cache miss when switching to claude)  
**Steps:**
1. `POST /rag/query` with query Q and `provider: "groq"` (populates groq cache)
2. `POST /rag/query` with same query Q and `provider: "claude"`
**Expected Result:** Second call `cache_hit: false` — cache entries are keyed by provider  
**Automation Hint:** pytest — assert `done["cache_hit"] == False` on second call  
**Source:** Part130

---

### TC-P8-055
**Category:** Feature  
**Test Name:** RAGAS eval endpoint returns faithfulness and relevancy scores  
**Steps:**
1. `POST /rag/eval-run` with a small QA test set (3–5 question/answer pairs)
2. Inspect response
**Expected Result:** Response contains `faithfulness`, `answer_relevancy`, `context_precision` scores as floats 0–1  
**Automation Hint:** pytest — assert all metric keys present; values in [0, 1]  
**Source:** Part147

---

### TC-P8-056
**Category:** Feature  
**Test Name:** `/rag/eval-history` returns past evaluation runs  
**Steps:**
1. Run `/rag/eval-run` twice
2. `GET /rag/eval-history`
**Expected Result:** History contains at least 2 entries with timestamps and scores  
**Automation Hint:** pytest — assert `len(history) >= 2`  
**Source:** Part147

---

### TC-P8-057
**Category:** Feature  
**Test Name:** Jina v3 embedding used when `embedding_model: "jina"` and jina is ready  
**Steps:**
1. Trigger Jina loading via `POST /rag/prepare-jina`; wait for ready
2. `POST /rag/query` with `embedding_model: "jina"`
3. Check done event
**Expected Result:** `done["embedding_used"] == "jina"`  
**Automation Hint:** pytest — assert `done["embedding_used"] == "jina"`  
**Source:** Part141

---

### TC-P8-058
**Category:** Feature  
**Test Name:** `/rag/prepare-jina` returns `loading` then eventually `ready`  
**Steps:**
1. `POST /rag/prepare-jina` (triggers background load)
2. Poll `GET /rag/health` until `jina_ready: true`
**Expected Result:** First prepare call returns `{"status": "loading"}`; health eventually shows `jina_ready: true`  
**Automation Hint:** pytest — assert first response status is "loading"; poll health with timeout  
**Source:** Part141

---

## Chat AI Frontend — Additional

---

### TC-P8-059
**Category:** Feature  
**Test Name:** RagSourceCard shows source filename and text excerpt  
**Steps:**
1. Ask a question via ToolsAIChat; expand Sources panel
2. Inspect each source card
**Expected Result:** Each card shows the filename (e.g. `xgboost_guide.md`) and a short text excerpt from the chunk  
**Automation Hint:** Playwright — assert source card text content non-empty; filename visible  
**Source:** Part138

---

### TC-P8-060
**Category:** Bug-Regression  
**Test Name:** Settings panel scroll works (preventDefault on wheel event)  
**Steps:**
1. Open ToolsAIChat settings panel (gear icon)
2. Scroll within the settings panel
**Expected Result:** Settings panel scrolls; page behind does not scroll simultaneously  
**Automation Hint:** Playwright — scroll inside settings panel; assert page `scrollY` unchanged  
**Source:** Part150

---

### TC-P8-061
**Category:** Feature  
**Test Name:** Upload document button in ToolsAIChat triggers `/rag/ingest`  
**Steps:**
1. Open ToolsAIChat
2. Click upload document button; select a `.txt` file
**Expected Result:** Network request to `POST /rag/ingest` fired; success confirmation shown in UI  
**Automation Hint:** Playwright — intercept network; assert `/rag/ingest` called with multipart body  
**Source:** Part138

---

### TC-P8-062
**Category:** Feature  
**Test Name:** Latency is displayed in sources row  
**Steps:**
1. Ask a question via ToolsAIChat (non-cached)
2. Inspect the sources row below the response
**Expected Result:** A latency indicator like `1.2s` or `340ms` is visible in the sources row  
**Automation Hint:** Playwright — assert element with text matching `\d+(ms|s)` present  
**Source:** Part150

---

### TC-P8-063
**Category:** Feature  
**Test Name:** Web override toggle resets to off after page reload  
**Steps:**
1. Activate web override toggle
2. Reload the page
3. Check toggle state
**Expected Result:** Web override toggle is off (state not persisted across reload — `useState` default is false)  
**Automation Hint:** Playwright — reload; assert globe button background is not amber  
**Source:** Part157

---

## Drift Detection — Additional

---

### TC-P8-064
**Category:** Feature  
**Test Name:** Per-feature drift level assigned correctly (low/medium/high)  
**Steps:**
1. Upload a drift CSV where one column has large distribution shift
2. Inspect `features` array in response
**Expected Result:** Feature with large shift has `drift_level: "high"`; stable features have `drift_level: "low"`  
**Automation Hint:** pytest — assert shifted column `drift_level == "high"`  
**Source:** Part151

---

### TC-P8-065
**Category:** Feature  
**Test Name:** Baseline source field shows "training" when pipeline has StandardScaler  
**Steps:**
1. Train a model with numeric features (StandardScaler applied)
2. `GET /drift/{model_id}`
**Expected Result:** Response `baseline: "training"` (extracted from fitted scaler, not schema fallback)  
**Automation Hint:** pytest — assert `response.json()["baseline"] == "training"`  
**Source:** Part151

---

### TC-P8-066
**Category:** Feature  
**Test Name:** Drift buffer persists across server restart  
**Steps:**
1. Make 5 predictions for a model
2. Restart the server
3. `GET /drift/{model_id}`
**Expected Result:** `n_recent >= 5` — buffer loaded from `data/drift_buffer.json` on startup  
**Automation Hint:** pytest — restart server process; assert `n_recent >= 5`  
**Source:** Part151

---

### TC-P8-067
**Category:** Feature  
**Test Name:** Percentile shift shown per feature in drift UI  
**Steps:**
1. Upload a drift CSV; navigate to Drift page
2. Expand a feature row
**Expected Result:** Percentile shift values (P10, P50, P90) shown for current vs baseline  
**Automation Hint:** Playwright — assert percentile shift section visible in feature detail  
**Source:** Part153

---

## AutoML Pipeline — Additional

---

### TC-P8-068
**Category:** Feature  
**Test Name:** SHAP uses Optuna-tuned params when preset checkbox enabled  
**Steps:**
1. Run Optuna; download params JSON
2. Navigate to SHAP; check "Use tuned params" checkbox; upload the JSON
3. Run SHAP
**Expected Result:** SHAP backend receives `preset_params_json`; model built with tuned params; feature importance shown  
**Automation Hint:** Playwright — intercept `/shap/*/train`; assert form data contains `preset_params_json`  
**Source:** Part136

---

### TC-P8-069
**Category:** Feature  
**Test Name:** Optuna pre-selects model from `automlWinner` context  
**Steps:**
1. Complete AutoML; note winner algorithm
2. Navigate to /tools/optuna
3. Observe model selector
**Expected Result:** Model dropdown pre-selected to winner algorithm from PipelineContext  
**Automation Hint:** Playwright — assert model select value matches `automlWinner.algorithm`  
**Source:** Part136

---

### TC-P8-070
**Category:** Feature  
**Test Name:** Ensemble pre-selects top 3 algorithms from `automlRanking`  
**Steps:**
1. Complete AutoML; note top 3 ranked algorithms
2. Navigate to /tools/ensemble
3. Observe algorithm pill selections
**Expected Result:** Top 3 algorithm pills are pre-selected matching AutoML ranking  
**Automation Hint:** Playwright — assert 3 pills have selected state; names match automlRanking top 3  
**Source:** Part136

---

### TC-P8-071
**Category:** Feature  
**Test Name:** Per-column encoding options applied in AutoML preprocessing  
**Steps:**
1. In AutoML Step 2, set column A to "onehot", column B to "frequency"
2. Complete AutoML training
3. Check trained pipeline
**Expected Result:** Pipeline applies OneHotEncoder to A and FrequencyEncoder to B (not default LabelEncoder for all)  
**Automation Hint:** pytest — inspect `pipeline.named_steps["prep"].transformers_`; verify encoder types per column  
**Source:** Part127

---

### TC-P8-072
**Category:** Feature  
**Test Name:** Pipeline builder progress bar advances as stages complete  
**Steps:**
1. Navigate to /tools/pipeline-builder
2. Complete Preprocessing stage
3. Observe progress bar
**Expected Result:** Progress bar advances from 0% to ~14% (1 of 7 stages done)  
**Automation Hint:** Playwright — assert progress bar width increases after stage completion  
**Source:** Part127

---

### TC-P8-073
**Category:** Feature  
**Test Name:** Pipeline reset clears all context and returns cards to initial state  
**Steps:**
1. Complete 3 pipeline stages
2. Click Reset button on pipeline builder
**Expected Result:** All cards return to locked/initial state; PipelineContext cleared; localStorage entry removed  
**Automation Hint:** Playwright — after reset, assert all cards except first are locked  
**Source:** Part127

---

## Feature Engineering — Additional

---

### TC-P8-074
**Category:** Feature  
**Test Name:** Column search input appears when dataset has 8+ columns  
**Steps:**
1. Upload a CSV with 10 columns to Feature Engineering
2. Observe NumericTransformsPanel
**Expected Result:** Search input visible above column list  
**Automation Hint:** Playwright — assert search input present in transforms panel  
**Source:** Part125

---

### TC-P8-075
**Category:** Feature  
**Test Name:** Transform recipe summary banner shows pending operations before apply  
**Steps:**
1. Select log1p on 2 columns and sqrt on 1 column
2. Observe the summary banner
**Expected Result:** Banner shows text like "Will apply: 2 log1p, 1 sqrt → ~3 cols"  
**Automation Hint:** Playwright — assert banner text matches expected summary pattern  
**Source:** Part125

---

### TC-P8-076
**Category:** Feature  
**Test Name:** One-hot encoding creates binary indicator columns per unique value  
**Steps:**
1. Select a categorical column with 3 unique values (e.g. "red", "blue", "green")
2. Apply one-hot encoding
**Expected Result:** Output has 3 new binary columns: `col_red`, `col_blue`, `col_green`; original column removed or kept per setting  
**Automation Hint:** pytest — assert 3 indicator columns present; values in [0, 1]  
**Source:** Part125

---

### TC-P8-077
**Category:** Feature  
**Test Name:** Target encoding maps category to mean of target column  
**Steps:**
1. Select a categorical column and a numeric target column
2. Apply target encoding
**Expected Result:** Encoded column values equal the mean target value per category (within tolerance)  
**Automation Hint:** pytest — compute group means manually; assert encoded values match  
**Source:** Part125

---

### TC-P8-078
**Category:** Feature  
**Test Name:** "Normalize all" transform preset applies MinMaxScaler to all numeric columns  
**Steps:**
1. Upload a CSV with numeric columns
2. Click "Normalize all" preset
3. Apply transforms
**Expected Result:** All numeric columns scaled to [0, 1] range  
**Automation Hint:** pytest — assert all numeric column max ≈ 1.0 and min ≈ 0.0  
**Source:** Part125

---

## KB Quality & RAG Accuracy

---

### TC-P8-079
**Category:** Feature  
**Test Name:** KB covers XGBoost topic — query returns relevant chunks  
**Steps:**
1. `POST /rag/query` with `"what are the key hyperparameters for XGBoost?"`
2. Inspect source events
**Expected Result:** At least one source chunk is from `xgboost_guide.md`  
**Automation Hint:** pytest — assert any source event doc `source` contains `xgboost`  
**Source:** Part144

---

### TC-P8-080
**Category:** Feature  
**Test Name:** KB covers SHAP topic — query returns relevant chunks  
**Steps:**
1. `POST /rag/query` with `"how do I interpret SHAP values?"`
2. Inspect source events
**Expected Result:** At least one source chunk is from `shap_interpretation.md`  
**Automation Hint:** pytest — assert source contains `shap`  
**Source:** Part144

---

### TC-P8-081
**Category:** Feature  
**Test Name:** KB covers imbalanced data topic  
**Steps:**
1. `POST /rag/query` with `"how should I handle class imbalance with SMOTE?"`
2. Inspect source events
**Expected Result:** At least one source chunk is from `imbalanced_data.md`  
**Automation Hint:** pytest — assert source contains `imbalanced`  
**Source:** Part144

---

### TC-P8-082
**Category:** Feature  
**Test Name:** `answer_source` is `"knowledge_base"` for pure KB query with no dataset  
**Steps:**
1. `POST /rag/query` with a ML question; `tool_context: ""` (no dataset); no session uploads
**Expected Result:** `done["answer_source"] == "knowledge_base"`  
**Automation Hint:** pytest — assert `answer_source == "knowledge_base"`  
**Source:** Part150

---

### TC-P8-083
**Category:** Feature  
**Test Name:** `answer_source` is `"none"` when no KB chunks retrieved and no dataset  
**Steps:**
1. Ensure KB is empty (or query with completely out-of-domain topic and CRAG disabled)
2. `POST /rag/query` with `tool_context: ""`
**Expected Result:** `done["answer_source"] == "none"`  
**Automation Hint:** pytest — assert `answer_source == "none"` when chunks empty  
**Source:** Part150

---

## SHAP Explainability Page

---

### TC-P8-084
**Category:** Feature  
**Test Name:** SHAP importance bars render for each feature  
**Steps:**
1. Navigate to /tools/shap
2. Upload a CSV; select a model; run SHAP
3. Inspect results
**Expected Result:** One horizontal bar per feature; bars proportional to importance scores  
**Automation Hint:** Playwright — assert N bar elements where N = number of features  
**Source:** Part125

---

### TC-P8-085
**Category:** Feature  
**Test Name:** SHAP shows parent label for FE-derived features  
**Steps:**
1. Run SHAP on a dataset that went through Feature Engineering (e.g. has `Age_sq`)
2. Inspect the feature importance chart
**Expected Result:** `Age_sq` bar shows "↳ from Age" label beneath it  
**Automation Hint:** Playwright — assert derived feature row contains parent label text  
**Source:** Part125

---

## Optuna Tuning Page

---

### TC-P8-086
**Category:** Feature  
**Test Name:** Optuna streams trial results during training  
**Steps:**
1. Navigate to /tools/optuna
2. Upload a CSV; configure model + n_trials = 5; start
3. Observe results as they stream
**Expected Result:** Trial results appear one by one during training (not all at once at end)  
**Automation Hint:** Playwright — assert result rows appear incrementally while progress indicator active  
**Source:** Part125

---

### TC-P8-087
**Category:** Feature  
**Test Name:** Optuna best trial params available for download after completion  
**Steps:**
1. Run Optuna to completion
2. Click "Download Params" button
**Expected Result:** JSON file downloaded containing `best_params` object with algorithm-specific keys  
**Automation Hint:** Playwright — listen for download; parse JSON; assert `best_params` has at least one key  
**Source:** Part136

---

## AutoML Wizard

---

### TC-P8-088
**Category:** Feature  
**Test Name:** SMOTE applied when dataset is imbalanced  
**Steps:**
1. Upload a CSV with severe class imbalance (minority class < 20% and >= 20 samples)
2. Run AutoML classification
3. Inspect training logs or model metadata
**Expected Result:** Training applies SMOTE oversampling; minority class count increases in training set  
**Automation Hint:** pytest — check model metadata for `smote_applied: true` or SSE log mentions SMOTE  
**Source:** Part129

---

### TC-P8-089
**Category:** Feature  
**Test Name:** Regression confidence intervals shown in results  
**Steps:**
1. Train a regression model via AutoML
2. Navigate to Step 4 Results
**Expected Result:** R² and RMSE metrics show 95% CI ranges (e.g. "R²: 0.82 – 0.87")  
**Automation Hint:** Playwright — assert CI text present in metrics grid  
**Source:** Part125

---

### TC-P8-090
**Category:** Feature  
**Test Name:** RAG KB badge shown in AutoML explain response  
**Steps:**
1. Train a model; navigate to explanation panel
2. Click "Generate Explanation"
3. Observe the explanation response
**Expected Result:** KB badge visible indicating explanation was grounded with retrieved KB context  
**Automation Hint:** Playwright — assert KB badge element present alongside explanation text  
**Source:** Part144
