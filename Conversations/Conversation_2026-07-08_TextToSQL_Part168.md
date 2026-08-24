# Conversation — Part 168
**Date:** 2026-07-08  
**Topics:** Text-to-SQL — Natural Language Column Filter, Filter Syntax Fix, Heatmap 1:1 Detection Fix  
**Commits (ml-portfolio):** `945a581` · `066cc78`  
**Commits (ML-Unified):** `c84b846` · `4d685ba` · `23c82cf` · `ce583ac` · `290b1da`

---

## Feature — Natural Language Column Filter

**Files:** `services/ml-sql/routers/_generate.py`, `services/ml-sql/routers/sql.py`, `src/app/tools/text-to-sql/QueryResultPanel.tsx`, `src/app/tools/text-to-sql/TextToSqlRunner.tsx`  
**Commits:** `c84b846` (backend) · `945a581` (frontend)

### Backend

`_generate.py` additions:
- `_build_filter_prompt(filter_text, columns)` — prompt showing columns pre-quoted, asks LLM to return a bare WHERE expression (no keyword, no semicolon)
- `_ensure_quoted(expr, columns)` — post-processor that wraps any unquoted multi-word column name in double-quotes (defense against LLM dropping quotes)
- `generate_filter_expr(filter_text, columns, provider, key)` — calls LLM, strips markdown/semicolons, runs `_ensure_quoted`

`sql.py` additions:
- `_exec_session(session, sql)` — extracted helper replacing repeated if/elif execution chains in `page_results` and `_run_pipeline` (freed ~16 lines to stay under 400-line cap)
- `FilterRequest` model: `{sql, db_ref, filter_text, columns, provider}`
- `POST /sql/filter` — validates original SQL, calls LLM for WHERE expr, wraps as `SELECT * FROM (...) AS _filtered WHERE {expr}`, paginates page 1, returns `{filtered_sql, filter_expr, ...}`

### Frontend

`QueryResultPanel.tsx`:
- Added `useState`, `useEffect` imports
- Props: `onFilter?`, `onClearFilter?`, `filterActive?`
- Local state: `filterText`, `filterLoading`
- `useEffect` clears `filterText` when `filterActive` → false (new query or clear)
- Filter bar below results table: input + "Filter" button + "× Clear" button
- "Filter active" amber badge in results header

`TextToSqlRunner.tsx`:
- `activeFilter` state, `originalSqlRef` ref (tracks LLM-generated SQL before any filter)
- `filterResults` callback: POST to `/sql/filter`, updates `results`/`currentSqlRef`/`activeFilter`
- `clearFilter` callback: restores `currentSqlRef` to `originalSqlRef`, resets `activeFilter`, calls `changePage(1)`
- Reset `originalSqlRef.current` and `activeFilter` on new query

### Pagination after filter
`currentSqlRef` is set to `data.filtered_sql` after a successful filter, so subsequent `changePage` calls paginate the filtered dataset correctly.

---

## Fix — Filter Syntax Error (Multi-Word Column Aliases)

**File:** `services/ml-sql/routers/_generate.py`  
**Commit:** `4d685ba`

**Bug:** LLM generated `Total Revenue > 50` (unquoted). SQLite parsed `Total` as column name, choked on `Revenue`.

**Fix (two layers):**
1. `_build_filter_prompt` now shows columns pre-quoted: `"Country", "Total Revenue"` — LLM mirrors the quoting format
2. `_ensure_quoted()` post-processor scans expression for multi-word column names (those with spaces) and wraps any unquoted occurrence: `Total Revenue > 50` → `"Total Revenue" > 50`

---

## Fix — Filter Error Surfacing

**File:** `src/app/tools/text-to-sql/TextToSqlRunner.tsx`  
**Commit:** `066cc78`

`catch { /* ignore */ }` was swallowing all errors silently. Replaced with:
- `if (data.error) { setError(data.error); return; }` — backend errors shown in UI
- `catch (e) { setError("Filter failed: " + e.message); }` — network/parse errors shown

---

## Fix — Heatmap 1:1 Detection (3 iterations)

**File:** `services/ml-sql/routers/_explain.py`  
**Commits:** `23c82cf` · `ce583ac` · `290b1da`

### Background
`detect_visualization` in `_explain.py` chooses the chart type. For 2 text cols + 1 numeric, it tries a heatmap. A prior fix (`ed97d93`) attempted to skip heatmap for 1:1 mappings (FirstName × LastName) but was broken.

### Iteration 1 — Wrong (pair set)  
`len(set(zip(row_vals, col_vals2))) == len(rows)` — always true for GROUP BY results where every pair is unique. Would have killed Genre × Country heatmaps too.

### Iteration 2 — Wrong (AND instead of OR)  
`len(set(row_vals)) == len(rows) AND len(set(col_vals2)) == len(rows)` — correct logic but used AND. When FirstName has even one duplicate (e.g., two customers named "Dan"), the row axis check passes and the heatmap renders despite LastName being 100% unique.

### Iteration 3 — Correct (`290b1da`)  
```python
n = len(rows)
bad = (len(set(row_vals)) >= n * 0.8 or len(set(col_vals2)) >= n * 0.8)
if len(unique_rows) >= 2 and len(unique_cols) >= 2 and not bad:
    # render heatmap
```

**Rule:** skip heatmap if EITHER axis has ≥ 80% uniqueness relative to row count.

| Scenario | Row uniqueness | Col uniqueness | Result |
|---|---|---|---|
| All 59 customers | FirstName 97% | LastName 100% | Skip → bar chart |
| Top 10 customers | FirstName 100% | LastName 100% | Skip → bar chart |
| Genre × Country (300 rows) | Genre 8% | Country 8% | Heatmap shown |

**Root cause of all three failures:** the original `is_diagonal` check used capped lists (`unique_rows[:20]`, `unique_cols[:15]`) so it broke when `len(rows) > 20`. All fixes use `set()` on the full uncapped lists.

---

## File Sizes After This Session

| File | Lines |
|---|---|
| `TextToSqlRunner.tsx` | 400 |
| `QueryResultPanel.tsx` | 300 |
| `sql.py` | 397 |
| `_generate.py` | 251 |
| `_explain.py` | 313 |

---

## Pending Items

| Item | Notes |
|---|---|
| — | All "Better use of time" features complete |

---

## Visual Improvements Backlog

Discussed but not yet implemented. Ranked by impact:

| # | Area | What to do |
|---|---|---|
| 1 | **Query input bar** | Glowing indigo border + gradient bg on focus; "Ask" button gradient pulse animation while running |
| 2 | **Animated pipeline steps** | Horizontal progress bar with 4 stage icons (Schema → SQL → Execute → Explain) that light up as SSE events fire; replaces plain status string |
| 3 | **SQL card syntax highlight** | Regex-based keyword highlighting — keywords indigo, strings green, numbers amber |
| 4 | **Result table polish** | Alternating row shading, sort-arrow column headers (visual only), subtle left-border accent on first column |
| 5 | **Chart cards** | Proper chart title typography, subtle grid, value labels on bars |
| 6 | **Stat card animation** | Count-up animation from 0 on single-value results |
| 7 | **Query history timeline** | Vertical left-border line + timestamps to look like a conversation log |
| 8 | **Schema panel badges** | Colored chips per column type (TEXT, INTEGER, REAL) instead of plain text |

Suggested first pass: items 1 + 2 + 3 (main interaction path).
