# Conversation — Part 167
**Date:** 2026-07-07  
**Topics:** Text-to-SQL — Server-side Pagination, MSSQL Support, Notebook Export, History Timeline, HF Space Build Fix  
**Commits (ml-portfolio):** `9ec94c7` · `e6d7d38` · `132f550` · `7f86ca1` · `ec4d9c3`  
**Commits (ML-Unified):** `fa29438` · `9e31a30` · `b4f9c80` · `c96fb0f`

---

## Feature 1 — Server-side Pagination

**Files:** `services/ml-sql/routers/_execute.py`, `services/ml-sql/routers/sql.py`, `src/app/tools/text-to-sql/QueryResultPanel.tsx`, `src/app/tools/text-to-sql/TextToSqlRunner.tsx`  
**Commits:** `fa29438` (backend), `9ec94c7` (frontend)

### Why option 2 (server-side) over option 1 (client-side)

Client-side "load more" only reveals pre-fetched rows — still capped at 500. Server-side properly handles unlimited result sets via `LIMIT/OFFSET` wrapping. Backend always paginates first query at page 1 (50 rows); subsequent pages use a dedicated lightweight `/sql/page` endpoint with no LLM involved.

### Backend changes (`_execute.py`)

- `QueryResult` dataclass gets `total_count: int = -1` field (-1 = unknown)
- `paginate_sql(sql, page, page_size)` — wraps any SQL: `SELECT * FROM (...) AS _paged LIMIT n OFFSET m`, strips trailing LIMIT from inner query first
- `_count_sql(sql)` — wraps as `SELECT COUNT(*) FROM (...) AS _cnt`
- `count_rows_sqlite(db_path, sql)` — runs count query, returns int (-1 on error)
- `result_to_dict` — conditionally includes `total_count` in output

### Backend changes (`sql.py`)

- `_run_pipeline`: switched from 500-row cap to `paginate_sql(sql, 1, 50)` for first page; runs `count_rows_sqlite` after execute; includes `total_count`, `page`, `page_size` in results SSE event
- `POST /sql/page` endpoint: takes `{sql, db_ref, page, page_size}`, validates SQL, runs count + paginated execute, returns JSON (no SSE — no LLM involved)

### Frontend changes

`TextToSqlRunner`:
- `currentPage` state, `totalCount` state, `currentSqlRef` ref
- `changePage(page)` callback: POST to `/sql/page`, update `results` + `currentPage`
- Reset page/count on new query

`QueryResultPanel`:
- Prev/Next buttons at bottom of results table
- "Rows X–Y of Z" label
- Disabled state on first/last page

**Test:** "List all tracks with their album name, artist name, and duration in minutes" → 3,503 rows, "Rows 1–50 of 3503" with working Prev/Next.

---

## Feature 2 — MSSQL (SQL Server) Support

**Files:** `services/ml-sql/routers/_schema_mssql.py` (new), `services/ml-sql/routers/_execute.py`, `services/ml-sql/routers/sql.py`, `services/ml-sql/requirements.txt`, `services/ml-sql/Dockerfile`, `src/app/tools/text-to-sql/DbConnectPanel.tsx`, `src/app/tools/text-to-sql/TextToSqlRunner.tsx`  
**Commits:** `9e31a30` (backend), `e6d7d38` (frontend)

### Architecture decision

`_schema.py` was at 383 lines (over the 350-line modularize threshold). Created `_schema_mssql.py` as a separate file rather than touching `_schema.py`.

### `_schema_mssql.py`

Uses `pymssql` wrapped in `asyncio.to_thread` (same pattern as DuckDB). INFORMATION_SCHEMA queries for tables, columns, PKs. FKs skipped (MSSQL FK introspection is complex; acceptable limitation). `mssql://user:pass@host:1433/db` connection string format.

### `_execute.py` additions

- `paginate_mssql_sql(sql, page, page_size)` — MSSQL uses `OFFSET x ROWS FETCH NEXT y ROWS ONLY` instead of `LIMIT/OFFSET`. Strips `ORDER BY` from inner query (MSSQL doesn't allow it in subqueries without TOP). Outer query uses `ORDER BY (SELECT NULL)` as required placeholder.
- `execute_mssql(conn_str, sql)` — `pymssql` via `asyncio.to_thread`

### Build failure & fix

**Problem:** Originally used `aiomssql` which requires `freetds-dev` + gcc to compile on `python:3.11-slim`. Docker build failed with exit code 1 at pip install step.

**Fix:** Replaced `aiomssql` with `pymssql` — ships pre-built binary wheels with bundled FreeTDS, no system dependencies needed. Removed `freetds-dev` apt install from Dockerfile.

### Frontend

`DbConnectPanel`: added "SQL Server" tab to TABS array, `mssqlConn`/`setMssqlConn`/`connectMssql` props, `mssql://` placeholder in input.

`TextToSqlRunner`: `mssqlConn` state, `connectRemote` type updated to include `"mssql"`.

---

## Fix — HF Space Cold-Start Error Message

**File:** `src/app/tools/text-to-sql/TextToSqlRunner.tsx`  
**Commit:** `7f86ca1`

When HF Space is cold-starting, it returns an HTML "Your space is starting..." page. The old code called `res.json()` directly, producing a raw JSON parse error shown to the user.

Fix: call `res.json().catch(() => { throw new Error("Backend warming up — wait 30s and click Load Schema again.") })`. Also checks `res.ok` before throwing with the error from `data.error` or HTTP status.

---

## Feature 3 — Export Query as Jupyter Notebook

**Files:** `src/app/tools/text-to-sql/QueryResultPanel.tsx`, `src/app/tools/text-to-sql/TextToSqlRunner.tsx`  
**Commit:** `132f550`

`.ipynb` button appears in results header alongside CSV / JSON. Generates a valid Jupyter notebook JSON with:
1. Markdown cell: question as `# Title`
2. Code cell: `import sqlite3, pandas; conn = sqlite3.connect('chinook.db'); df = pd.read_sql_query("""<sql>""", conn); df`
3. Markdown cell: explanation (if present)

`exportNotebook()` is a module-level function in `QueryResultPanel.tsx`. Uses existing `downloadFile()` helper. `question` passed as new optional prop from `TextToSqlRunner`.

---

## Feature 4 — Visual Query History Timeline

**Files:** `src/app/tools/text-to-sql/QueryHistoryPanel.tsx` (new), `src/app/tools/text-to-sql/TextToSqlRunner.tsx`  
**Commit:** `ec4d9c3`

Extracted from 32-line inline block in `TextToSqlRunner` into `QueryHistoryPanel.tsx`.

### Design

- Vertical timeline line (left side, `w-px bg-white/10`)
- Colored dot per turn based on row count:
  - Gray: 0 rows
  - Green (`#10b981`): < 10 rows
  - Indigo (`#6366f1`): 10–99 rows
  - Amber (`#f59e0b`): 100+ rows
- Row count badge + mini horizontal bar (relative to session max)
- Click to expand: shows SQL + "↑ Re-use this question" button
- Re-use click: populates question input + closes expansion

### `TextToSqlRunner` cleanup

- Removed `expandedTurn` / `setExpandedTurn` state (moved into component)
- Replaced 32-line inline block with 5-line `<QueryHistoryPanel>` usage
- Net: -26 lines (374 total, well under 400 limit)

---

## File Sizes After This Session

| File | Lines |
|---|---|
| `TextToSqlRunner.tsx` | 374 |
| `QueryResultPanel.tsx` | 258 |
| `QueryHistoryPanel.tsx` (new) | 84 |
| `SchemaDiagram.tsx` | 333 |
| `SchemaPanel.tsx` | 51 |
| `MobileSidebar.tsx` | 68 |
| `_execute.py` | 335 |
| `sql.py` | 361 |
| `_schema_mssql.py` (new) | 75 |

---

## Pending Items (Text-to-SQL)

| Item | Notes |
|---|---|
| Natural language column filter | "show only rows where revenue > 1000" in plain English, appended to existing SQL |

## Dropped Items

| Item | Reason |
|---|---|
| Saved/named queries | Low value — few-shot history already persists; Chinook queries covered by sample chips |
