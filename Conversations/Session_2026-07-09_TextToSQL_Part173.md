# Session: Text-to-SQL — Part 173
**Date:** 2026-07-09 / 2026-07-10  
**Branch:** main  
**Repos:** ML-Unified (`services/ml-sql/`) + ml-portfolio (`src/app/tools/text-to-sql/`)

---

## Summary

Continuation of Part 172. Completed the on-demand AI explanation feature, fixed all remaining TypeScript errors from the explanation refactor, and added a clear button to the question textarea.

---

## Work Done

### 1. On-demand "Explain with AI" — Backend (`sql.py`)

- **Removed** auto-explanation streaming from `_run_pipeline` entirely. The query SSE stream now ends at `results → done` with no LLM call after results.
- **Added** `POST /sql/explain` endpoint that:
  - Accepts `{ question, sql, columns, rows, provider }`
  - Streams tokens via existing `stream_explanation()` helper
  - Calls `generate_followup_suggestions()` after explanation completes
  - Catches `RateLimitError` and sends it as an SSE error event
- **Commit:** `6a16f9a`
- **HF Upload:** `routers/sql.py` → `wram1708/ml-sql`

### 2. On-demand "Explain with AI" — Frontend (`QueryResultPanel.tsx`)

- Removed `explanation: string` from `Props` interface
- Added local state: `localExpl`, `explLoading`, `explErr`, `suggestions`
- Added `useEffect` to reset explanation state when `results` changes (new query clears old explanation)
- Added `fetchExplanation()` — `POST /sql/explain`, reads SSE stream, accumulates tokens into `localExpl`, captures `suggestions`
- **UI flow:**
  - Results shown → "Explain with AI" button appears below chart
  - Click → button disappears, spinner "Generating explanation…" shown
  - On success → indigo explanation card with text + suggestion chips
  - On rate limit → red inline error below button
- Follow-up suggestion chips moved from `TextToSqlRunner` into the explanation card in `QueryResultPanel`
- `exportNotebook()` now uses `localExpl` instead of prop-passed `explanation`

### 3. TextToSqlRunner.tsx cleanup

- Removed `explanation` and `suggestions` state (`useState`)
- Removed `setExplanation`, `setSuggestions` from reset line
- Removed SSE `token` and `suggestions` handlers
- Removed `explanation={explanation}` prop from `<QueryResultPanel>`
- Removed suggestions render block (moved to QueryResultPanel)
- Fixed `(results || explanation) && !running` → `results && !running`
- **Commit:** `9220781`

### 4. Clear button for question textarea

- Wrapped textarea in a `relative` div
- Added `×` SVG button (absolute top-right) that only renders when `question !== ""`
- Clicking it calls `setQuestion("")`
- Added `pr-7` to textarea so text doesn't overlap the button
- **Commit:** `0d17f6d`

---

## Commits

| Hash | Repo | Description |
|------|------|-------------|
| `6a16f9a` | ML-Unified | feat(ml-sql): on-demand /sql/explain endpoint; remove auto-explanation from query pipeline |
| `9220781` | ml-portfolio | feat(text-to-sql): on-demand AI explanation button — no auto-explain |
| `0d17f6d` | ml-portfolio | feat(text-to-sql): add clear (×) button to question textarea |

---

## Files Changed

| File | Change |
|------|--------|
| `services/ml-sql/routers/sql.py` | Removed auto-explain from pipeline; added `/sql/explain` endpoint + `_stream_explain()` |
| `src/app/tools/text-to-sql/QueryResultPanel.tsx` | Self-contained explanation state + fetch + on-demand UI |
| `src/app/tools/text-to-sql/TextToSqlRunner.tsx` | Removed explanation/suggestions state; added clear button to textarea |

---

## Architecture After This Session

```
POST /sql/query  →  schema_loaded → [retry] → sql_generated → results → done
                    (no LLM call after results)

POST /sql/explain  →  token (×N) → suggestions → done
                      (only fires when user clicks "Explain with AI")
```

Rate limit errors now only surface where they're triggered:
- Query rate limit → shown in the main error block
- Explain rate limit → shown inline below the "Explain with AI" button

---

## Pending / Backlog

- Creative Feature #3: Auto data story / insight
- Creative Feature #4: Query history as report
- Suggestion chips in explanation card are display-only (clicking does not run the query) — could wire them up like the sidebar chips
