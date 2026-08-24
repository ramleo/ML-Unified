# Conversation — Part 163
**Date:** 2026-07-06  
**Topics:** Text-to-SQL — Chart Fixes, Results Table, 5 Pending Items (3 completed)  
**Commits (ML-Unified):** `7bfb984` · `1a964a8` · `dd89b4f` · `0904338`  
**Commits (ml-portfolio):** `1e6b56d` · `8bb21fe` · `bed3ae9` · `b2e7ed9`

---

## Summary

Fixed area chart and scatter chart regressions, improved results table UX, and completed 3 of 5 pending Text-to-SQL items: SQL pre-validation, schema-linking, and session persistence. Also diagnosed and fixed a critical HF Space upload path error (wrong space).

---

## Bug Fixes

### 1. Area Chart Not Showing (was rendering as Scatter)

**Root cause — two issues:**

**Issue A:** The LLM for "monthly revenue trend" generates 3 columns `(Year, Month, Revenue)` — all numeric. `detect_visualization()` only handled 2-col time series, so 3-col fell through to `None` (no chart).

**Fix:** Added 3-col year+month handler in `_explain.py`:
```python
# year + month + value → area with "YYYY-MM" combined labels
if len(columns) == 3 and not text_cols:
    year_ok  = all(re.match(r"^(19|20)\d{2}$", y) for y in year_sample)
    month_ok = all(re.match(r"^\d{1,2}$", m) and 1 <= int(m) <= 12 ...)
    if year_ok and month_ok:
        combined = [f"{y}-{str(m).zfill(2)}" for y, m in zip(...)]
        return {"chart_type": "area", "labels": combined, ...}
```

**Issue B:** The area regex `\d{4}[-/]\d{2}` required YYYY-MM format — plain 4-digit years like `"2022"` didn't match. Extended to:
```python
r"\b(19|20)\d{2}([-/]\d{1,2})?\b"
```

**Sample question changed** from "monthly revenue trend across all years" → "What is the total revenue for each year?" (produces clean 2-col: Year + Revenue).

### 2. Scatter Chart Rendering as Multibar

**Root cause:** LLM was normalizing milliseconds to minutes (~48 min avg for video genres vs ~$1.99 price → ratio ≈ 24, below old threshold of 100).

**Fix:** Lowered `scale_ratio` threshold from `100 → 10` in `_explain.py`. With minutes still: 48/1.99 ≈ 24 > 10 → scatter fires.

**Sample question changed** to "What is the average track length in milliseconds vs average unit price per genre?" — explicit "in milliseconds" prevents unit normalization.

### 3. Critical: Wrong HF Space Upload

**What happened:** `_explain.py` was uploaded to `wram1708/ml-unified` (ml-api space) instead of `wram1708/ml-sql`. The fix was live in git but the HF container never received it — charts showed old behavior for an entire debugging cycle.

**Fix:**
- Uploaded `_explain.py` to correct space: `wram1708/ml-sql`
- Deleted the wrongly placed file from `wram1708/ml-unified`
- Updated memory with permanent rule: two spaces, two prefixes

**Rule (now in memory):**

| Service | HF Space | Strip prefix |
|---------|----------|--------------|
| ml-api | `wram1708/ml-unified` | `services/ml-api/` |
| ml-sql | `wram1708/ml-sql` | `services/ml-sql/` |

Git remote `hf` points to ml-unified only — always pass `repo_id` explicitly.

---

## Results Table Improvements

### Scrollable Table (all 100 rows)
- Removed `slice(0, 20)` — all returned rows now visible
- Added `max-h-80 overflow-y-auto` on the container
- Sticky column headers (`sticky top-0`) so columns stay visible while scrolling
- Removed "X more rows not shown" note

### Float Rounding to 2 Decimal Places
- Cell renderer: if value converts to a float and isn't already a whole integer → `toFixed(2)`
- `2911783.0384615385 → 2911783.04` · `0.9900000000000001 → 0.99`
- Integers, years, IDs, text pass through unchanged

---

## 5 Pending Items — Status After This Session

| # | Item | Status |
|---|------|--------|
| 1 | 500-row truncation warning | ✅ Done — amber warning when count ≥ 500; table scrollable showing all 100 rows |
| 2 | SQL pre-format validation | ✅ Done — 4 structural checks before DB hit |
| 3 | Schema-linking | ✅ Done — `link_tables()` in `_schema.py` |
| 4 | Session persistence | ✅ Done — JSON index + clear expired-session errors |
| 5 | Schema RAG (Phase 3) | ❌ Not started — MiniLM + BM25 for 50+ table DBs |

---

## Item Detail: SQL Pre-Format Validation (`_execute.py` commit `1a964a8`)

Four new checks in `validate_sql()` after the SELECT-only guard:

| Check | Catches |
|-------|---------|
| FROM clause required | `SELECT COUNT(*)` with no table |
| Balanced parentheses | Half-formed subqueries |
| Unmatched single quotes | Open string literals |
| Dangling keyword at end | LLM truncation mid-generation |

All raise `UnsafeQueryError` → feeds existing retry loop (LLM gets error context, tries again).

**Verified locally:**
```
BLOCKED  truncated — ends on FROM    →  Query appears truncated (ends on a keyword)
BLOCKED  no FROM clause              →  Query must contain a FROM clause
BLOCKED  unbalanced parens           →  Unbalanced parentheses
BLOCKED  unmatched quote             →  Unmatched single quote
PASS     SELECT * FROM Track LIMIT 10
PASS     SELECT Name, COUNT(*) FROM Artist GROUP BY Name
```

---

## Item Detail: Schema-Linking (`_schema.py` commit `dd89b4f`)

Added `link_tables(schema, question, top_k=6)`:

**Scoring per table:**
- +3 per question word matching table name
- +2 per question word matching a column name  
- +1 per question word matching a sample cell value

**FK expansion:** After picking top_k tables, include every table with a direct FK relationship (so JOINs remain possible).

**`schema_to_prompt_text()`** now always calls `link_tables()` when a question is provided — previously only fired for DBs with > 30 tables.

**Example:** "Which artists have the most albums?"
- `Artist` scores +3 (name match) · `Album` scores +3 (name match) → both selected
- FK: `Album.ArtistId → Artist` already covered
- LLM sees just 2 tables instead of all 11

---

## Item Detail: Session Persistence (`sql.py` commit `0904338`)

**Before:** `_sessions` dict wiped on any restart → users get `Unknown db_ref`.

**After:**
- SQLite uploads saved to `_UPLOAD_DIR / index.json` on every upload
- On startup, `_restore_sessions()` reads the index and reloads sessions whose files still exist
- 24-hour TTL — sessions older than 86,400s skipped on restore
- PostgreSQL conn_str intentionally NOT persisted (security risk)
- Clear error messages by session type:
  - `pg_*` → "PostgreSQL session expired. Please reconnect."
  - `upload_*` → "Uploaded DB session expired. Please re-upload."

**Limitation:** Full Docker container restarts wipe `/tmp` — SQLite file is lost even if index survives. True persistence requires HF Space persistent storage (paid feature, not available on free tier) or an external DB (e.g. Neon free Postgres).

---

## Remaining

| Item | Notes |
|------|-------|
| **Schema RAG (Phase 5)** | MiniLM + BM25 for 50+ table DBs — next item |
| **#47 Dockerize ml-vision** | ml-eda done; ml-vision still pending |
| **#43 Time series forecasting** | Prophet/ARIMA/LSTM — new microservice |
| **#42 Automated retraining** | Not started |
| **#39 Model versioning** | Not started |
| **#50 Batch predictions** | Vision, cap 10 images |
| **#45 E2E Playwright in CI** | Suite exists locally |
