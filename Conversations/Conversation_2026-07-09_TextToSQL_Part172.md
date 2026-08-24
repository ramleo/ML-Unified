# Conversation — Part 172
**Date:** 2026-07-09
**Topics:** Text-to-SQL — Chart removal, Viz detection fixes, Codebase cleanup, Follow-up suggestions feature
**Commits (ml-portfolio):** `ca7ff3e`, `ef05335`, `e8be260`, `8224f49`, `44c7d99`
**Commits (ML-Unified / ml-sql):** `65ee543`, `7470249`, `316c326`, `9818987`

---

## Context

Continuation from Part 171. Picked up remaining low-priority polish items, hit visualization bugs, removed chart feature entirely, and started creative feature additions.

---

## Fix: Conditional Label Rotation — `ca7ff3e`

**Problem:** BarChart and MultiBarChart always rotated x-labels -38° even with 3 short bars.

**Fix in `SqlChart.tsx`:**
- Added `avgLen` + `rotateLabels` computed per chart
- `rotateLabels = (cW / labels.length) < avgLen * 6.5` for BarChart
- `rotateLabels = gW < avgLen * 6.5` for MultiBarChart (uses group width)
- `textAnchor` and `transform` now conditional on `rotateLabels`
- Short sparse charts → labels horizontal; dense charts → labels rotate -38°

---

## Polish: Drill-down Hint + AreaChart Rotation — `ef05335`

**Drill-down hint:** Changed from 11px gray text to a small pill:
```tsx
<span className="ml-2 inline-flex items-center text-[10px] px-1.5 py-0.5 rounded-full border border-white/10 text-gray-500 font-normal">click bar to drill down</span>
```

**AreaChart:** Added conditional label rotation (same `avgLen * 6.5` formula) for x-labels on time-series charts.

---

## Bug: "Top 5 artists by album count" → Treemap

**Root cause 1:** LLM generated SQL without `LIMIT 5` → all artists returned → >12 rows → Treemap.

**Root cause 2:** Even with 5 rows, donut threshold was `≤7` rows → would show donut instead of bar.

**Fixes (`65ee543`, `7470249`):**
- `_explain.py`: Donut threshold `≤7` → `≤4` — so 5–7 rows fall through to bar/bar_h
- `_generate.py`: Added Chinook-specific few-shot: "Top 5 artists by number of albums → LIMIT 5"
- `_generate.py`: Added explicit rule: `"When the question says 'top N', 'top 5'... ALWAYS add LIMIT N"`

Both files uploaded to HF Space. Issue persisted across retests — user decided to remove charts entirely.

---

## Feature Removal: Charts Removed — `e8be260`

User decision after repeated viz bugs. Removed chart rendering fully from frontend.

**`QueryResultPanel.tsx`:**
- Removed all chart imports (`BarChart`, `HorizontalBarChart`, `AreaChart`, `ScatterChart`, `MultiBarChart`, `DonutChart`, `AnimatedStatCard`, `HeatmapChart`, `TreemapChart`)
- Removed `CHART_LABEL` constant, `Viz` interface
- Removed `viz` and `onDrillDown` from Props + destructuring
- Removed entire `{viz && (...)}` render block (~40 lines)

**`TextToSqlRunner.tsx`:**
- Removed `Viz` interface, `viz` state, `setViz(null)` reset, `suggestions` SSE handler
- Removed `drillDown` callback
- Removed `viz={viz}` and `onDrillDown={drillDown}` from QueryResultPanel props

Results: SQL card + results table + explanation only. No charts.

---

## Cleanup: Delete Chart Files + Backend Viz — `8224f49`, `316c326`

**`8224f49` (ml-portfolio):** Deleted `SqlChart.tsx` (316 lines) + `SqlChartExtras.tsx` (~200 lines) — both fully orphaned.

**`316c326` (ML-Unified):** Removed `detect_visualization` call from `sql.py`:
- Removed import of `detect_visualization` from `_explain`
- Removed the 4-line visualization SSE block from query pipeline

Uploaded `sql.py` to HF Space.

---

## Verification: Phase 3 Schema RAG — Already Done

User asked to verify if Schema RAG (Phase 3 from plan) was pending. Check found it was already implemented in `_schema.py`:
- `schema_rag_retrieve()` — BM25 keyword retrieval via `rank-bm25`
- `_RAG_THRESHOLD = 20` — auto-activates for DBs with >20 tables
- `rank-bm25>=0.2.2` in `requirements.txt`

Not vector/embedding-based but BM25 is wired and active. **Nothing pending.**

---

## Creative Features — Started

User asked "how can we make Text-to-SQL creative?" and chose to implement 4 features in order:

1. **Follow-up question suggestions** ← implemented this session
2. Surprise me button
3. Auto data story / insight
4. Query history as report

---

## Feature: Follow-up Question Suggestions — `9818987`, `44c7d99`

After each query, AI generates 3 follow-up question chips based on what was returned.

**Backend (`_generate.py`):**
```python
def _build_followup_prompt(question, sql, columns, rows_preview) -> str:
    # prompt: Q + SQL + columns + sample rows → ask for 3 follow-ups
    
async def generate_followup_suggestions(question, sql, columns, rows_preview, provider, key) -> list[str]:
    # calls LLM, parses 3 lines, returns list[str]
```

**Backend (`sql.py`):**
- Imported `generate_followup_suggestions`
- After explanation streaming completes:
```python
suggestions = await generate_followup_suggestions(...)
if suggestions:
    yield _sse({"type": "suggestions", "questions": suggestions})
yield _sse({"type": "done"})
```

**Frontend (`TextToSqlRunner.tsx`, 399 lines):**
- Added `const [suggestions, setSuggestions] = useState<string[]>([])`
- Reset `setSuggestions([])` on new query
- SSE handler: `else if (evt.type === "suggestions") setSuggestions(evt.questions ?? [])`
- Chip row rendered below QueryResultPanel:
```tsx
{suggestions.length > 0 && (
  <div className="flex flex-col gap-1.5">
    <p className="text-[9px] ... uppercase tracking-widest">You might also ask</p>
    <div className="flex flex-wrap gap-2">
      {suggestions.map((q, i) => (
        <button key={i} onClick={() => setQuestion(q)} className="... rounded-full border ...">
          {q}
        </button>
      ))}
    </div>
  </div>
)}
```

Clicking a chip loads the question into the input box (does not auto-run).

Both files uploaded to HF Space `wram1708/ml-sql`.

---

## File Sizes After Session

| File | Lines |
|------|-------|
| `TextToSqlRunner.tsx` (ml-portfolio) | 399 |
| `QueryResultPanel.tsx` (ml-portfolio) | 269 |
| `_generate.py` (ml-sql) | 341 |
| `sql.py` (ml-sql) | 401 |
| `_explain.py` (ml-sql) | 336 |

---

## Pending Creative Features

| # | Feature | Status |
|---|---------|--------|
| 1 | Follow-up question suggestions | ✓ Done (`44c7d99`, `9818987`) |
| 2 | "Surprise me" button | Pending |
| 3 | Auto data story / insight | Pending |
| 4 | Query history as report | Pending |
