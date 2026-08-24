# Conversation — Part 164
**Date:** 2026-07-07  
**Topics:** Text-to-SQL — Multi-DB, Multi-turn, Interactive Visualizations, All 5 Pending Features  
**Commits (ML-Unified):** `78a5972` · `0b2fb90` · `bfc8da2` · `3551ed1` · `a9bebe1`  
**Commits (ml-portfolio):** `5f304a3` · `cfed503` · `ecf18dd`

---

## Summary

Extended the Text-to-SQL agent with 4-engine database support, multi-turn conversation memory, ID column filtering in visualizations, and all 5 pending interactive/visual features. Also modularized the 389-line frontend runner into 3 files.

---

## Feature 1 — MySQL + DuckDB/Parquet/CSV Support

**Backend files changed:** `_schema.py`, `_execute.py`, `sql.py`, `requirements.txt`

| Engine | Driver | How to connect |
|---|---|---|
| MySQL | `asyncmy` | MySQL tab → `mysql://user:pass@host:3306/db` |
| DuckDB | `duckdb` | Upload tab → `.duckdb` file |
| Parquet | `duckdb` | Upload tab → `.parquet` file (auto view) |
| CSV | `duckdb` | Upload tab → `.csv` file (auto view) |

Key details:
- MySQL: `SET SESSION TRANSACTION READ ONLY` + SELECT-only validation
- DuckDB `.duckdb` files: `read_only=True` connection
- DuckDB Parquet/CSV: in-memory connection with `CREATE VIEW data AS read_parquet(...)`
- `ConnectRequest.db_type` field routes MySQL vs PostgreSQL from same `/sql/connect` endpoint
- Session restore handles duckdb type alongside sqlite
- Expired-session error message added for `mysql_` prefix

**Frontend:** `TextToSqlRunner.tsx` split into 3 files (was 389 lines):
- `TextToSqlRunner.tsx` (221 lines) — state, SSE, layout
- `DbConnectPanel.tsx` (99 lines) — 4 tabs: Chinook Demo / Upload File / PostgreSQL / MySQL
- `QueryResultPanel.tsx` (152 lines) — SQL card + results + charts + explanation

---

## Feature 2 — Multi-turn Conversation

**What it is:** Each query carries the last 3 turns (question + SQL + result summary) injected into the LLM prompt. The LLM can resolve follow-up references like "those", "that", "instead", "filter by X".

**Backend:** `_generate.py` — `_build_sql_prompt()` + `generate_sql()` accept `history: list[dict]`; last 3 turns injected before the current question with an explicit instruction to use them for context.

**Backend:** `sql.py` — `QueryRequest.history` field (`list[dict]`, default `[]`); passed to `generate_sql`.

**Frontend:** `TextToSqlRunner.tsx`:
- `history` state (`HistoryTurn[]`) — appended after each successful query
- `historyPayload` built from last 4 turns, sent with each `/sql/query` request
- `result_summary` = `"N rows. Columns: X, Y. Sample: [...]"` for LLM context
- Conversation thread UI: strip above results showing past turns; click to expand SQL; Clear button

**Verified working:** 3-turn sequence:
1. "Show top 10 customers by total spending" → 10 rows
2. "Now show only those from Germany" → 4 rows, WHERE Country = 'Germany' added correctly
3. "Sort those by name instead of spending" → ORDER BY FirstName, LastName, no country filter lost

---

## Bug Fix — ID Columns in Visualizations

**Problem:** `CustomerId` (values 2, 36–38) same scale as `total_spending` (37–44) → scale ratio 1.15 → multibar chart instead of bar. CustomerId also appearing in SELECT unnecessarily.

**Fix 1 — `_explain.py`:** Added `_is_id_col()` — regex matching `*Id`, `*_id`, `*Key`, `*_no`, `*_code`, `*_num`. Filtered from `numeric_cols` before any chart detection. CustomerId/TrackId/InvoiceId etc. are never treated as chart metrics.

**Fix 2 — `_generate.py`:** Added prompt rule: *"Do NOT select ID/key columns unless the question specifically asks for them."*

---

## Feature 3 — Schema RAG Phase 3 (from Part 163 continuation)

**Commit:** `78a5972`

Added BM25 retrieval for large schemas (>20 tables) to `_schema.py`:
- `_table_doc(t)` — tokenizes table into BM25 document (name + columns + sample values)
- `schema_rag_retrieve(schema, question, top_k=8)` — BM25 index, score against question, FK-expand
- `_RAG_THRESHOLD = 20` — small DBs use `link_tables()` (fast, no dep); large DBs use BM25
- `rank-bm25>=0.2.2` added to `requirements.txt`

---

## 5 Pending Visual/AI Features (all shipped in commit `ecf18dd` / `a9bebe1`)

### 1. Animated Stat Card
**File:** `SqlChartExtras.tsx` — `AnimatedStatCard`

Count-up animation from 0 to final value via `requestAnimationFrame`, ease-out cubic (`1 - (1-t)³`), 1100ms duration. Replaces static `StatCard` for all `chart_type: "stat"` results.

### 2. Click-to-Drill (Interactive Bar Charts)
**File:** `SqlChart.tsx` — `onLabelClick` prop on `BarChart` + `HorizontalBarChart`

Bars show pointer cursor + `hover:opacity-75`. Clicking a bar calls `onLabelClick(label, value)`. In `TextToSqlRunner`, `drillDown` callback pre-fills the question input with `"Show me details where {colName} is "{label}""` — user can then press Enter to run. Works as a multi-turn follow-up.

### 3. Heatmap Chart
**Detection (`_explain.py`):** 2 text cols + 1 numeric col → `chart_type: "heatmap"` with `rows`, `cols`, `data` fields.

**Component (`SqlChartExtras.tsx`):** SVG grid, color intensity = `rgba(99,102,241, 0.08 + t*0.85)`, cell value labels shown when cells ≥ 30×20px, col headers rotated -40°, empty cells shown as near-transparent.

**Example query:** `"Show total sales by genre and billing country"`

### 4. Treemap Chart
**Detection (`_explain.py`):** 1 text + 1 numeric + >12 rows → `chart_type: "treemap"` (replaces crowded bar).

**Component (`SqlChartExtras.tsx`):** Slice-and-dice algorithm — recursive binary partition by value ratio, alternating horizontal/vertical splits. Rectangles colored by `SERIES_COLORS` with opacity proportional to value. Label + value overlaid when cell is large enough.

**Example query:** `"Show track count by genre"` (25 genres → treemap)

### 5. Few-shot Prompting from Query History
**File:** `TextToSqlRunner.tsx`

Every successful query appended to `localStorage` (key `ml_sql_fewshot`, last 20 pairs). On mount, loads stored pairs into `fewShot` state. Each new query prepends last 3 few-shot examples to `historyPayload` (marked with "Example." prefix), then the recent conversation turns. No backend changes — piggybacks on existing `history` field.

### 6. Business Glossary Upload
**Frontend:** Collapsible "Glossary" panel in the sidebar. Textarea for user to enter term definitions (`revenue: sum of invoice totals`). Value stored in `glossary` state, sent as `QueryRequest.glossary` field.

**Backend (`_generate.py`):** If `glossary` is non-empty, injected into prompt before conversation history: *"Business glossary (use these definitions for ambiguous terms/columns):"*

**Backend (`sql.py`):** `QueryRequest.glossary: str = ""` field, passed to `generate_sql`.

---

## File Sizes After This Session

| File | Lines |
|---|---|
| `TextToSqlRunner.tsx` | 322 |
| `QueryResultPanel.tsx` | 173 |
| `DbConnectPanel.tsx` | 99 |
| `SqlChart.tsx` | 300 |
| `SqlChartExtras.tsx` (new) | 186 |
| `_explain.py` | 304 |
| `_generate.py` | 207 |
| `_execute.py` | 276 |
| `_schema.py` | 383 |
| `sql.py` | 300 |

---

## Remaining Backlog

| Item | Notes |
|---|---|
| **#47 Dockerize ml-vision** | ml-eda done; ml-vision still pending |
| **#43 Time series forecasting** | Prophet/ARIMA/LSTM — new microservice |
| **#42 Automated retraining** | Not started |
| **#39 Model versioning** | Not started |
| **#50 Batch predictions (vision)** | Cap 10 images |
| **#45 E2E Playwright in CI** | Suite exists locally |

---

## Part 164 — Continued (same date, second context window)

**Commits:** `3847157` · `ed97d93` (backend) · `d5512c3` · `d047fdc` (frontend)

### Bug Fix 1 — Treemap not triggering for 2-column results

**Problem:** "Show track count by genre" (2 cols, 25 rows) showed a crowded bar chart instead of treemap.

**Root cause:** The treemap check (`if len(rows) > 12`) lived only in the multi-column path (3+ columns). 2-column results (`len(columns) == 2`) returned `bar` before ever reaching treemap logic.

**Fix (`_explain.py`):**
- Added `if len(rows) > 12 → treemap` inside the `len(columns) == 2` branch, before the `avg_len > 12 → bar_h` and final `bar` fallback.
- Extended labels/values slice from `:20` to `:50` in the 2-col branch to support treemap with up to 50 items.
- Boundary: ≤7 rows → donut, 8–12 rows → bar/bar_h, >12 rows → treemap.

---

### Bug Fix 2 — Bar click drill-down not visible

**Problem:** Clicking a bar appeared to do nothing.

**Root cause:** The click WAS working — it called `setQuestion(...)` — but the user was scrolled down to the chart area and didn't see the textarea at the top update.

**Fix (`TextToSqlRunner.tsx`):**
- Added `questionRef = useRef<HTMLTextAreaElement>()` and attached it to the textarea.
- `drillDown` callback now calls `questionRef.current?.scrollIntoView({ behavior: "smooth", block: "center" })` + `.focus()` after setting the question.

---

### Bug Fix 3 — Heatmap false positive for 1:1 record sets

**Problem:** "Show top 10 customers by total spending" returned `FirstName, LastName, TotalSpending` (2 text + 1 numeric) → triggered heatmap → showed a diagonal grid (one filled cell per row).

**Root cause:** The heatmap condition only checked `len(unique_rows) >= 2 and len(unique_cols) >= 2`. A "top N customers" result always satisfies this but is not a real cross-tabulation — every (FirstName, LastName) pair is unique.

**Fix (`_explain.py`):**
- Added `is_diagonal = (len(unique_rows) == len(rows) and len(unique_cols) == len(rows))`.
- If both axes are fully unique, skip heatmap and fall through to bar_h with concatenated labels (`"Helena Holý"`, `"Richard Cunningham"`, etc.).
- Real heatmaps (genre × country) are unaffected because genres repeat across countries.

---

### Bug Fix 4 — Heatmap column headers overlapping cells

**Problem:** Long column labels like "Zimmermann" (rotated -40°) visually overlapped the first row of cells and the row labels on the Y axis.

**Root cause:** `PT = 56` was hardcoded. A rotated text of width L drops `L × sin(40°)` pixels downward. "Zimmermann" at ~55px wide drops 35px — pushing it 29px into the cell area (cells start at PT = 56, text anchor at PT - 6 = 50, text bottom at 85).

**Fix (`SqlChartExtras.tsx`):**
```tsx
const maxColLen = Math.max(...cols.map(c => Math.min(String(c).length, 14)), 4);
const labelDropH = Math.ceil(maxColLen * 5.5 * Math.sin(40 * Math.PI / 180));
const PT = Math.max(40, labelDropH + 12);
const labelY = PT - labelDropH - 4; // text ends 4px above cells
```
Column headers now use `y={labelY}` with matching rotation pivot, so the rotated text clears the cell grid at any label length.

---

### Business Glossary — Explanation

The glossary lets users define custom term meanings injected into every SQL generation prompt. Useful when:
- Column names are cryptic (`UnitPrice` but user says "price")
- Business thresholds are encoded in questions ("big spender" = `Total > 40`)
- Ambiguous terms map to specific columns ("revenue" = `SUM(Invoice.Total)`)

Format: one definition per line, `term: definition`. Sent as `QueryRequest.glossary`, injected before conversation history in `_generate.py` prompt.

**Location in UI:** Left sidebar → collapsible "▸ Glossary" section below Sample Questions. Only visible on screens ≥1024px wide.

---

### Text-to-SQL Pending Items (as of end of this session)

**Text-to-SQL specific:**
| Item | Notes |
|---|---|
| MSSQL support | Discussed but not implemented |
| Export results | Download query results as CSV/JSON |
| Saved queries | Persist named queries (beyond few-shot 20-pair limit) |
| Schema search | Filter tables in schema panel by keyword |
| Pagination UI | Results capped at 500 with no page-through |
| Mobile layout | Sidebar hidden below 1024px; glossary/schema inaccessible on mobile |
| Query sharing | Shareable URL with pre-filled question + db_ref |

**Whole project backlog (unchanged):**

| # | Item |
|---|---|
| #47 | Dockerize ml-vision |
| #43 | Time series forecasting (Prophet/ARIMA) |
| #42 | Automated retraining pipeline |
| #39 | Model versioning + rollback |
| #50 | Batch predictions (vision, cap 10) |
| #45 | E2E Playwright tests in CI |
