# Conversation — Part 161
**Date:** 2026-07-06  
**Topics:** Text-to-SQL Agent — Real-World Portfolio Project (#new)  
**Commits:** `3b795ba` `cebc49a` (ML-Unified) · `f0e94b4` `f862e70` (ml-portfolio)

---

## Summary

Planned and built the Text-to-SQL Agent as a new standalone portfolio microservice. Converts natural language questions to SQL, executes them on a real database (Chinook demo, SQLite upload, or PostgreSQL), streams a plain-English explanation, and auto-generates a chart from the result shape.

---

## Work Done

### 1. Planning

- Reviewed existing infrastructure (5 LLM providers, RAG pipeline with LangGraph, ml-eda/ml-vision microservice pattern)
- Confirmed no SQL/DB dependencies existed yet — clean slate
- Selected Text-to-SQL as real-world portfolio project (high interview value, demonstrable live)
- User confirmed: ml-sql microservice inside ML-Unified ecosystem + all 3 DB sources (Chinook / SQLite upload / PostgreSQL)
- Wrote full plan to `/Users/wrks/.claude/plans/temporal-gliding-pascal.md`

### 2. Security Guardrails (added after initial commit on user request)

`services/ml-sql/routers/_execute.py` hardened with:
- **SQLite URI read-only mode** — `aiosqlite.connect("file:path?mode=ro", uri=True)` — DB physically cannot be modified even if a dangerous query slips through
- **PostgreSQL read-only transaction** — `SET TRANSACTION READ ONLY` + always rolled back at DB level
- **Multi-statement block** — detects semicolons between statements (stops `SELECT 1; DROP TABLE foo`)
- **Both comment styles stripped** — `--` and `/* */` before keyword scan
- **Expanded blocked keywords** — DROP, DELETE, INSERT, UPDATE, CREATE, ALTER, TRUNCATE, EXEC, EXECUTE, GRANT, REVOKE, REPLACE, MERGE, UPSERT, LOAD, ATTACH, DETACH, PRAGMA, VACUUM, ANALYZE, EXPLAIN

### 3. New Microservice — `services/ml-sql/`

```
services/ml-sql/
├── app.py                    21 lines  — FastAPI init + lifespan Chinook preload
├── Dockerfile                          — same pattern as ml-eda
├── requirements.txt                    — fastapi, uvicorn, httpx, aiosqlite, asyncpg, sqlparse
├── data/
│   └── chinook.db            984KB     — Chinook music store (11 tables, ~3.5k rows)
└── routers/
    ├── __init__.py
    ├── _schema.py            178 lines — SQLite + PostgreSQL introspection (tables, cols, PKs, FKs, sample rows)
    ├── _generate.py          129 lines — Non-streaming SQL generation (Groq/Gemini/Cohere)
    ├── _execute.py           149 lines — Safety guard + aiosqlite/asyncpg execution
    ├── _explain.py           200 lines — SSE explanation streaming + auto-viz detection
    └── sql.py                188 lines — Thin router with 3-attempt agentic retry loop
```

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Status + demo DB table count |
| `GET` | `/sql/schema` | Schema JSON for any db_ref |
| `POST` | `/sql/upload` | Upload SQLite .db → returns db_ref + schema |
| `POST` | `/sql/connect` | PostgreSQL connection string → returns db_ref + schema |
| `POST` | `/sql/query` | SSE: NL question → SQL → execute → explanation → visualization |

**SSE protocol:**
```
data: {"type": "schema_loaded", "tables": 11, "columns": 47}
data: {"type": "retry",         "attempt": 2, "error": "..."}
data: {"type": "sql_generated", "sql": "SELECT ..."}
data: {"type": "results",       "columns": [...], "rows": [...], "count": N, "exec_time_ms": N}
data: {"type": "visualization", "chart_type": "bar", "labels": [...], "values": [...]}
data: {"type": "token",         "text": "..."}   ← streamed explanation
data: {"type": "done"}
```

**Key implementation details:**
- `_schema.py`: Introspects SQLite with `PRAGMA table_info` / `PRAGMA foreign_key_list` and PostgreSQL with `information_schema`; formats compact schema text for LLM prompt; filters relevant tables by keyword overlap for large DBs (50+ tables)
- `_generate.py`: Non-streaming API calls (Groq OpenAI-compat, Gemini generateContent, Cohere v2 chat); `_extract_sql()` strips ` ```sql ``` ` markdown fences and finds first SELECT/WITH block; low temperature (0.1) for deterministic SQL
- `_execute.py`: sqlparse validates SELECT-only; `_inject_limit()` appends `LIMIT 500` if absent; row limit 500; returns `QueryResult` dataclass
- `_explain.py`: `detect_visualization()` checks column types — 1 text + 1 numeric → bar, 2 numeric + time pattern → line, 2 numeric → scatter; streaming explanation via same SSE pattern as `_suggest.py`
- `sql.py`: In-memory `_sessions` dict maps `db_ref → {type, path/conn_str, schema}`; `"chinook"` preloaded at startup; uploaded files stored in `/tmp/ml_sql_sessions/`

### 4. HF Space Deployment

- Created `wram1708/ml-sql` HF Space (Docker, public)
- Uploaded all 10 files including `data/chinook.db` (984KB)
- Set `ML_SQL_URL=https://wram1708-ml-sql.hf.space` as Variable on `wram1708/ml-unified`
- User added `GROQ_API_KEY` to ml-sql secrets
- Verified live: `GET /health` → `{"status":"ok","demo_db":"chinook.db","tables":11}`

### 5. ml-portfolio Frontend

**New files:**

| File | Lines | Contents |
|------|-------|---------|
| `src/app/tools/text-to-sql/page.tsx` | 53 | Thin page wrapper with ConstellationBackground + ToolsAIChat |
| `src/app/tools/text-to-sql/TextToSqlRunner.tsx` | 349 | Full pipeline UI — schema panel, DB source tabs, query input, results, chart, explanation |
| `src/app/tools/text-to-sql/SqlChart.tsx` | 87 | Inline SVG BarChart + LineChart components |

**UI layout:**
```
┌─────────────────────────────────────────────────────┐
│ Schema Panel (left)     │ Main Area (right)          │
│ ▶ Album (347 rows)      │ [Chinook Demo | Upload | PG]│
│ ▶ Artist (275 rows)     │ [NL question textbox]       │
│ ▶ Track (3503 rows)     │ [Provider ▾] [Ask button]   │
│ ...                     │ ─────────────────────────── │
│ SAMPLE QUESTIONS        │ Generated SQL (code card)   │
│ › Top 5 artists...      │ Results table               │
│ › Monthly revenue...    │ SVG chart (auto-detected)   │
│                         │ Explanation (streamed)      │
└─────────────────────────────────────────────────────┘
```

**Modified:**
- `src/config/urls.ts` — added `ML_SQL_API` from `NEXT_PUBLIC_ML_SQL_URL`
- `src/data/capabilities.ts` — added text-to-sql capability card (accent `#6366f1`, 3 LLM providers)

### 6. Playwright Test

- Loaded page → page rendered correctly (all 3 DB tabs, sample questions, query input)
- Schema load failed with JSON parse error — root cause: `NEXT_PUBLIC_ML_SQL_URL` not yet baked into Vercel build (Next.js `NEXT_PUBLIC_*` vars are embedded at build time)
- Triggered redeploy via empty commit `f862e70`

---

## Files Changed

| File | Repo | Change |
|------|------|--------|
| `services/ml-sql/app.py` | ML-Unified | New |
| `services/ml-sql/Dockerfile` | ML-Unified | New |
| `services/ml-sql/requirements.txt` | ML-Unified | New |
| `services/ml-sql/data/chinook.db` | ML-Unified | New (binary, 984KB) |
| `services/ml-sql/routers/_schema.py` | ML-Unified | New |
| `services/ml-sql/routers/_generate.py` | ML-Unified | New |
| `services/ml-sql/routers/_execute.py` | ML-Unified | New (hardened) |
| `services/ml-sql/routers/_explain.py` | ML-Unified | New |
| `services/ml-sql/routers/sql.py` | ML-Unified | New |
| `src/app/tools/text-to-sql/page.tsx` | ml-portfolio | New |
| `src/app/tools/text-to-sql/TextToSqlRunner.tsx` | ml-portfolio | New |
| `src/app/tools/text-to-sql/SqlChart.tsx` | ml-portfolio | New |
| `src/config/urls.ts` | ml-portfolio | Added ML_SQL_API |
| `src/data/capabilities.ts` | ml-portfolio | Added text-to-sql card |

---

### 7. End-to-End Playwright Verification

After user confirmed `NEXT_PUBLIC_ML_SQL_URL` was set in Vercel:

- Loaded `https://ml-portfolio-rho.vercel.app/tools/text-to-sql`
- Clicked **Load Schema** → 11 Chinook tables appeared in schema panel with row counts (Album 347, Artist 275, Track 3,503, InvoiceLine 2,240, PlaylistTrack 8,715, ...)
- Clicked sample question "Show me the top 5 artists by total album count" → Ask
- Full pipeline ran end-to-end:

| Stage | Result |
|-------|--------|
| Generated SQL | Correct `SELECT T1.Name, COUNT(T2.AlbumId) AS TotalAlbums FROM Artist AS T1 INNER JOIN Album AS T2 ON T1.ArtistId = T2.ArtistId GROUP BY T1.Name ORDER BY TotalAlbums DESC LIMIT 5` |
| Results | 5 rows · 1.7ms — Iron Maiden 21, Led Zeppelin 14, Deep Purple 11, U2 10, Metallica 10 |
| Bar chart | Auto-detected from result shape (1 text col + 1 numeric col), rendered inline SVG |
| Explanation | "The results show the top 5 artists with the most albums, with Iron Maiden leading the list with 21 albums. Following closely are iconic bands like Led Zeppelin with 14 albums, and Deep Purple with 11 albums. Metallica and U2 are tied for fourth place, each having released 10 albums." |

---

### 8. PostgreSQL Option — Explained

**How it works:**
1. Paste any PostgreSQL connection string (e.g. `postgresql://user:password@host:5432/dbname`) → click Connect
2. Backend calls `POST /sql/connect` → `asyncpg` connects, introspects all tables in `public` schema (columns, PKs, FKs, sample rows) → returns a `db_ref` token
3. All subsequent `/sql/query` calls use that `db_ref` — conn string held in memory on ml-sql server only, never written to disk
4. Questions asked in plain English exactly as with Chinook; SQL generated against the actual schema

**Practical use cases:**
- Connect to own Supabase / Railway / Neon / Render Postgres DB
- Demo against a real production-like dataset during an interview
- Query any cloud DB that's publicly accessible

**Limitations:**
- Session is in-memory only — if ml-sql HF Space restarts (free tier sleeps after inactivity), session is lost and reconnection is needed
- No SSL/TLS cert validation configured yet (asyncpg defaults — works fine with most cloud providers)
- Connection string includes password in plaintext → only use with a read-only DB user or throwaway credential
- Best for portfolio demo: point at a real Supabase/Neon project with interesting data

---

## Pending After This Session

| Item | Notes |
|------|-------|
| Set `NEXT_PUBLIC_ML_SQL_URL` in Vercel env vars | Required for frontend to reach ml-sql; triggers redeploy |
| Phase 2 — Polish | Auto-viz for scatter, upload .db UI refinement, retry animation |
| Phase 3 — Schema RAG | Embed schema for large DBs (50+ tables) using MiniLM + BM25 |
| #39 Model versioning + rollback | Not started |
| #42 Automated retraining pipeline | Not started |
| #43 Time series forecasting | Prophet/ARIMA/LSTM |
| #45 E2E Playwright in CI | Suite exists locally |
| #47 Dockerize ml-vision | ml-eda done; ml-vision still pending |
| #50 Batch predictions (vision) | Not started |