# Conversation — Part 171
**Date:** 2026-07-09
**Topics:** Text-to-SQL — Saved Queries, FK Indicators, Error UX, History Polish, Chart Typography, Viz Detection Fix, _generate.py Modularization
**Commits (ml-portfolio):** `70fd9a2`, `5d02a3d`, `9578d49`, `432cbb5`, `5ec0b5c`, `8525cae`, `45e9e40`, `705d20d`
**Commits (ML-Unified / ml-sql):** `330fd3f`, `d613258`

---

## Context

Continuation from Part 170. Picked up pending items #4–#8 from the Text-to-SQL backlog in order, then fixed chart visualization bugs discovered during testing.

---

## Feature: Saved/Named Queries (#4) — `70fd9a2`

New `SavedQueriesPanel.tsx` (88 lines) in desktop sidebar below Glossary.

- **Save button** appears after a query runs (floppy disk SVG)
- Saves immediately with question text as name (first 60 chars), deduplicates by question
- 1.5s "✓ Saved" green confirmation flash
- Saved list: click to reload question, hover to reveal SVG ✕ delete
- Persists to `localStorage` key `ml_sql_saved`, cap 20 entries
- TextToSqlRunner.tsx: compressed QueryHistoryPanel JSX (3→1 line) to stay at 399 lines

---

## Feature: Schema FK Indicators (#5) — `5d02a3d`, `9578d49`, `432cbb5`

**`5d02a3d`** — FK indicators in SchemaPanel:
- FK columns get a violet **FK** badge instead of type badge
- Hover tooltip shows full target: `→ Album.AlbumId`
- Column name styled `violet-300`
- Dim `→ Album` label at end of row

**`9578d49`** — FK visibility fix:
- Badge: `#6d28d940` bg + `#c4b5fd` text (was near-invisible `#7c3aed22`)
- Column name: `text-violet-300` full opacity
- Arrow label: `text-violet-400/70` (was `text-violet-900/80` = near-black on dark bg)

**`432cbb5`** — Font size bump across SchemaPanel:
- 8px→9px (badges), 9px→10px (row count), 10px→11px (table/column names, search)

---

## Feature: Better Provider-Fail Error UX (#6) — `5ec0b5c`

Added `onRetry` and `provider` props to `QueryResultPanel`.

| Error type | UI shown |
|---|---|
| `_API_KEY not configured` | Error + "Groq key isn't configured — switch provider in the dropdown." |
| `All providers failed` | Error only (already retried internally) |
| Rate limit / timeout / execution error | Error + **Try again** button with refresh SVG icon |

---

## Feature: QueryHistoryPanel Polish (#7) — `8525cae`

- **Relative timestamps** (`just now` / `2m ago` / `1h ago`) shown under Q{n} label
- `HistoryTurn` gains optional `timestamp` field, set to `Date.now()` on each query
- Old turns from localStorage (no timestamp) show Q{n} only — graceful degradation
- Timeline connector line: `bg-white/10` → `bg-white/20` (more visible)

---

## Feature: Chart Title Typography + MultiBarChart Annotations (#8) — `45e9e40`

- Chart card title: `text-xs gray uppercase` → `text-sm white/75 tracking-tight`
- Drill-down hint: `normal-case` with `·` separator
- MultiBarChart: wrap bars in `<g>` + value labels above each bar (when bar tall/wide enough)
- Axis labels (xLabel/yLabel): fontSize 10→11 across all chart types

---

## Bug Fix: Visualization Detection — Year Columns → Heatmap — `330fd3f`

**Root cause:** Queries returning `(Country, Year, Revenue)` hit the `len(numeric_cols) == 2` scale ratio check: `max(2011, 127) / min(2011, 127) ≈ 15.8 > 10` → Scatter Plot.

**Fix in `_explain.py`:**
- Added `_is_year_col(vals)` — detects integer values in 1900–2099 range
- When one of two numeric cols is a year, pivots it as heatmap column axis:
  `(Country, Year, Revenue)` → **Heatmap** (Country × Year → Revenue)
- Scale ratio scatter path only fires when neither col is a year

---

## Bug Fix: MultiBarChart Label Rotation — `705d20d`

- MultiBarChart x-labels now rotate -38° (same as BarChart) when rendered
- `textAnchor="end"`, `slice(0, 14)` to match BarChart behavior
- Prevents overlap with dense label sets (e.g. 25 Chinook genres)

---

## Refactor: _generate.py Modularization + Cross-Dimensional Few-Shot — `d613258`

**Problem:** `_generate.py` was at 357 lines (over 350 modularize threshold). Could not add few-shot examples.

**Split:**
- **`_providers.py`** (new, 65 lines): `_PROVIDERS` registry + `get_provider_cfg` + `_call_groq/gemini/cohere`
- **`_generate.py`** (303 lines, was 357): imports from `_providers`, all prompt/SQL logic stays

**New few-shot example added:**
```
Q: Show number of tracks per genre and media type.
A: SELECT g.Name AS "Genre", mt.Name AS "Media Type", COUNT(t.TrackId) AS "Track Count"
   FROM Genre g JOIN Track t ON g.GenreId = t.GenreId
   JOIN MediaType mt ON t.MediaTypeId = mt.MediaTypeId
   GROUP BY g.Name, mt.Name ORDER BY "Genre", "Track Count" DESC
```

Teaches LLM to keep dimensions as separate columns (not concatenated labels), enabling heatmap detection instead of treemap fallback.

---

## File Sizes After Session

| File | Lines |
|---|---|
| `TextToSqlRunner.tsx` (ml-portfolio) | 399 |
| `QueryResultPanel.tsx` (ml-portfolio) | 344 |
| `SchemaPanel.tsx` (ml-portfolio) | 108 |
| `QueryHistoryPanel.tsx` (ml-portfolio) | 93 |
| `SavedQueriesPanel.tsx` (ml-portfolio) | 88 |
| `SqlChart.tsx` (ml-portfolio) | 308 |
| `_generate.py` (ml-sql) | 303 |
| `_providers.py` (ml-sql) | 65 |
| `_explain.py` (ml-sql) | 336 |

---

## Pending Items

| # | Item | Notes |
|---|------|-------|
| — | Follow-up button prominence | Currently 11px gray at bottom; may need pill border |
| — | Cross-dimensional viz (treemap→heatmap) | ✓ Verified — heatmap confirmed on live HF Space |
| — | AreaChart label rotation | Only shows subset of labels; lower priority |
| — | Data-driven label rotation for BarChart | Always rotates even with 3 short bars; should be conditional on `(chartWidth / labels.length) < avgLabelLen * 6.5` |

---

## Post-Save Q&A (2026-07-09 continuation)

**User:** whats next in text to sql?

**Answer:** Numbered backlog (#4–#8) fully done. Pending chart quality items:
1. Cross-dimensional viz test — run "Compare number of tracks per genre across top 3 media types" on live HF Space to confirm heatmap (no code needed, just verification of `d613258` few-shot)
2. Data-driven label rotation — BarChart always rotates even with sparse short labels; should be conditional
3. Follow-up button prominence — low priority
4. AreaChart label rotation — low priority

**User:** what is Cross-dimensional viz test?

**Answer:** The issue was the LLM concatenating Genre + MediaType into one label column (→ 2-col result → Treemap). Correct SQL should keep them as separate columns (2 text + 1 numeric → Heatmap). Fix was adding a few-shot example in `_generate.py` (`d613258`). The test is just running that question on HF Space to confirm heatmap now appears instead of treemap.
