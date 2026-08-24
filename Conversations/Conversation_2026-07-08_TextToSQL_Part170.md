# Conversation — Part 170
**Date:** 2026-07-08  
**Topics:** Text-to-SQL — Few-shot examples, Top-N fix, Auto sample questions, Follow-up UI, Timeout fix  
**Commits (ml-portfolio):** `02d90d7`, `5260f64`, `d0c7658`, `0919d41`  
**Commits (ML-Unified / ml-sql):** `a38c30b`, `fa1ad98`, `078608a`, `1f5ba43`

---

## Context

Continuation from Part 169 (visual redesign). User tested a query and found "top 3 artists in each genre" returned more than 3. Root cause: LLM using `ORDER BY + LIMIT` instead of `ROW_NUMBER PARTITION BY`.

---

## Fix 1 — 10 Few-Shot SQL Examples (`a38c30b`)

Added 10 examples to `_FEW_SHOT` in `_generate.py` covering patterns LLMs commonly get wrong:

| # | Pattern | Key SQL |
|---|---------|---------|
| 1 | Top N per group | `ROW_NUMBER() OVER (PARTITION BY ...)` |
| 2 | Cumulative total | `SUM() OVER (ORDER BY ... ROWS UNBOUNDED PRECEDING)` |
| 3 | Period comparison | `LAG()` + `NULLIF` |
| 4 | % of total | Scalar subquery in denominator |
| 5 | No-match rows | `LEFT JOIN ... WHERE ... IS NULL` |
| 6 | Pattern matching | `LIKE '%x%'` |
| 7 | Date grouping (SQLite) | `strftime('%Y-%m', ...)` |
| 8 | Filter on aggregates | `HAVING COUNT(*) > N` |
| 9 | Self-join hierarchy | Aliased self-join |
| 10 | Tie-breaking | `ORDER BY col1 DESC, col2 ASC` |

Generic table names (`sales`, `products`) used so examples work on any uploaded DB.

---

## Fix 2 — Chinook-Specific Example + Hard Rule (`fa1ad98`)

Generic examples didn't bridge to Chinook's `Genre/Track/Album/Artist` join chain. Added:

1. **Exact Chinook example** — `Genre → Track → Album → Artist` with `ROW_NUMBER PARTITION BY g.Name`
2. **Hard rule in prompt** — "For 'top N per group' questions, ALWAYS use `ROW_NUMBER() OVER (PARTITION BY ...)` in a CTE — never `ORDER BY + LIMIT` alone"

---

## Fix 3 — Runtime Pattern Detection (`078608a`)

Regex fires on any question matching `top \d+ ... per/each/in each/within/for each`:

```python
_TOP_N_PER_GROUP_RE = re.compile(
    r"\btop\s+\d+\s+.{0,40}\b(per|each|in\s+each|by\s+each|within|for\s+each)\b",
    re.IGNORECASE,
)
```

When matched, injects a targeted CTE instruction right before the user question (highest LLM attention position). Works for any schema, not just Chinook.

---

## AI Accuracy Disclaimer (`02d90d7`, frontend)

Added persistent note in query card below PipelineStatus:

> "SQL is AI-generated — accuracy depends on the LLM. Verify results before use."

Implemented by replacing the share-button block (5 lines) with a flex row containing both disclaimer + share button (5 lines). Net zero line change. TextToSqlRunner.tsx stays at 400 lines.

---

## Schema RAG — Already Done

Discovered `_schema.py` already had full Schema RAG implemented:
- `link_tables()` — keyword overlap scoring for ≤20 tables
- `schema_rag_retrieve()` — BM25 (`rank_bm25`) for >20 tables  
- `schema_to_prompt_text(schema, question)` — auto-routes based on table count
- Wired in `sql.py` line 330 with the question parameter

Nothing to build. Moved to #2.

---

## Feature: Auto Sample Questions from Schema (`1f5ba43` backend, `5260f64` frontend)

### Backend — `_generate.py`

New `generate_sample_questions(schema, provider, key)`:
- Builds compact schema text → asks LLM for exactly 5 analyst questions
- Parses response line-by-line, strips numbering, returns up to 5 items ≥10 chars
- Falls back to `[]` on any exception

New GET endpoint in `sql.py`:
```
GET /sql/sample-questions?db_ref=xxx&provider=groq
→ {"questions": ["...", "...", "...", "...", "..."]}
```

### Frontend — `TextToSqlRunner.tsx`

```tsx
const [dynQ, setDynQ] = useState(SAMPLE_QUESTIONS);
useEffect(() => {
  if (dbRef === "chinook") { setDynQ(SAMPLE_QUESTIONS); return; }
  fetch(`${ML_SQL_API}/sql/sample-questions?db_ref=${dbRef}&provider=${provider}`)
    .then(r => r.json()).then(d => { if (d.questions?.length) setDynQ(d.questions); }).catch(() => {});
}, [dbRef, provider]);
```

- Chinook → keeps hardcoded 5 questions
- Uploaded / connected DB → sidebar "Try asking" chips update to schema-aware questions
- `SAMPLE_QUESTIONS` usages in sidebar + MobileSidebar replaced with `dynQ`

Line budget: compressed fewShot useEffect from 6→1 line, removed JSX comment → freed 6 lines for 5 new lines.

---

## Feature: Multi-Turn Follow-up UI (`d0c7658`, frontend)

### What was already working
Backend already passes `history` context on every query. Users just didn't know.

### What was added
1. **Follow-up button** — appears below results after any completed query:
   ```
   ↩ Ask a follow-up — this query's context is retained
   ```
   Clicking scrolls to + focuses the textarea.

2. **Dynamic placeholder** — textarea shows "Ask a follow-up or new question…" when results exist.

Both are purely UI — no backend changes needed.

Line budget: removed 3 blank lines between callbacks, collapsed QueryHistoryPanel JSX → freed 5 lines for 5 new lines.

---

## Bug Fix: HF Space Sleeping + Query Hang (`0919d41`, frontend)

### Root cause
HF free Spaces sleep after ~15 min of inactivity. When sleeping:
- `/sql/schema` returns 206 (wakeup proxy response)
- `/sql/query` POST hangs indefinitely
- No timeout on fetch → UI stuck in "Running…" forever
- Ask button not blocked when schema is null → users could query before schema loaded

### Fixes

**1. 90-second AbortController timeout:**
```tsx
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 90_000);
// passed as signal: controller.signal to fetch
// catch: AbortError → "Backend is waking up — wait 30 seconds and try again."
// finally: clearTimeout(timeoutId)
```

**2. Ask button disabled when no schema:**
```tsx
disabled={running || !question.trim() || !schema}
// label: !schema → "Load DB", running → "Running…", else → "Ask"
```

### Playwright investigation
- Opened portfolio, clicked Load Schema, submitted query
- Network: `/sql/schema` returned 206, `/sql/query` POST pending with no response
- Console: 0 errors, 0 warnings — purely a backend sleeping issue
- HF Space stage: `APP_STARTING`
- Direct health endpoint: timed out at 60s
- Fix: restarted space via `api.restart_space()`, polled until 200 OK (15s)
- Re-tested: full pipeline ran successfully

---

## Playwright Test Result (Post-Fix)

Query: "Show me the top 5 artists by total album count"

- Schema panel: 11 tables with row counts ✓
- Pipeline: Schema ✓ → SQL ✓ → Execute ✓ → Explain ✓
- SQL highlighted (indigo keywords, emerald identifiers) ✓
- Results: 50 rows, 3.1ms ✓
- Treemap chart auto-detected ✓
- Explanation streamed ✓
- History: "1 TURN" badge ✓
- Follow-up button visible at bottom ✓

---

## File Sizes After Session

| File | Lines |
|---|---|
| `_generate.py` (ml-sql) | 357 |
| `sql.py` (ml-sql) | 396 |
| `TextToSqlRunner.tsx` | 399 |

---

## Pending Items

| # | Item | Priority | Notes |
|---|------|----------|-------|
| 4 | Saved/named queries | Medium | Persist beyond session — localStorage bookmarks |
| 5 | Schema FK indicators | Medium | `foreign_keys` already in schema response, not rendered |
| 6 | Better provider-fail error UX | Low | Show which provider failed, "Try again" button |
| 7 | QueryHistoryPanel polish | Low | Left-border timeline, relative timestamps |
| 8 | Chart title typography | Low | Larger label, value annotations on bars |
| — | Follow-up button prominence | UX | Currently very subtle (11px gray); may need pill border |
