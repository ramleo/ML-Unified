# Session: Text-to-SQL Teach the AI + Reasoning Panel — Part 180
**Date:** 2026-07-12
**Branch:** main
**Repos:** ml-portfolio (`src/app/tools/text-to-sql/`), ML-Unified (`services/ml-sql/`)

---

## Summary

Continued from Part 179. Added Auto-Insights to User Guide, fixed retry tab bug, fixed `t.trim` TypeError, designed and built the "Show Reasoning + Teach the AI" feature (Query Memory), and refactored `sql.py` into `_session_mgr.py`.

---

## User Guide Updates

### Auto-Insights section added (`7e6390d`)
New section between "Working with Results" and "Multi-Tab Workflow" covering all 6 insight types in a 2-column grid with severity colors.

### 4-row minimum callout made prominent (`a6291aa`)
Replaced buried footer text with an amber warning callout box: **"Requires at least 4 result rows"** with explanation. Previously easy to miss.

---

## Bug Fix — Retry Creates New Tab (`3e586dd`)

Every "Try again" click spawned a new tab (via `Date.now().toString()` tab ID). Fixed by adding `existingTabId?: string` param to `runQuery`. When set, patches the existing tab in-place instead of pushing to the tab list.

```tsx
onRetry={() => runQuery(activeTab?.question, activeTabId ?? undefined)}
```

---

## Bug Fix — `t.trim is not a function` (`5f89ab5`)

**Root causes:**
1. `ColumnProfileView.tsx` — `rawType.split("(")` crashes if backend returns `null` column type. Fixed: `(rawType ?? "")`.
2. Sample questions API — LLM could return non-string elements. Fixed: `.map((q: unknown) => String(q))`.
3. `runQuery` — defensive coerce: `const activeQ = String(questionOverride ?? question)`.

---

## New Feature — Show Reasoning + Teach the AI (Query Memory)

**Commits:** `e685ec4` (frontend), `56b300a` (backend + HF upload)

### Design decisions

- **CoT is manual** (on-demand) — no extra LLM tokens unless user clicks "Show Reasoning"
- **Correction UX**: textarea is the primary CTA, "Fix & Re-run" button stays disabled until user types — prevents confusion that clicking alone auto-corrects
- **Name**: "Teach the AI" (user immediately knows they must provide input)
- **Persistence**: per-database (corrections from CSV don't leak into Chinook queries)

### User flow

1. User runs query → SQL + results appear
2. **AI Reasoning panel** visible below SQL → click "Show Reasoning" → AI streams step-by-step reasoning (intent, columns chosen, assumptions made)
3. User spots wrong assumption → types correction in "Teach the AI" textarea
4. "Fix & Re-run" activates → correction saved to localStorage + query re-runs with correction injected into LLM prompt
5. Green badge shows saved correction; ✕ deletes it
6. **Next time same question is asked on same DB** → correction is automatically included in prompt, AI gives correct SQL from the start

### Files created/modified

| File | Action | Lines |
|---|---|---|
| `_corrections.ts` | New — localStorage utility | 28 |
| `ReasoningPanel.tsx` | New — UI component | 167 |
| `QueryResultPanel.tsx` | +import + props + JSX | 400 |
| `TextToSqlRunner.tsx` | +import + correction in fetch + onRerun prop | 396 |
| `routers/_session_mgr.py` | New — extracted from sql.py | 87 |
| `routers/sql.py` | Refactored + correction field + /sql/reason | 322 |
| `routers/_generate.py` | +correction param in prompt builder | 353 |
| `services/ml-sql/app.py` | Updated import for preload_chinook | 23 |

### Backend changes

**`/sql/query`** — `QueryRequest` now accepts `correction: str = ""`. When non-empty, injected into the SQL generation prompt as:
```
USER CORRECTION — apply this when generating the SQL:
<correction text>
```

**`/sql/reason`** (new endpoint) — streams AI reasoning for why it generated a specific SQL:
```python
prompt = (
    f"Question: {question}\nSQL generated: {sql}\nResult columns: {cols}\n\n"
    "Explain your step-by-step reasoning..."
)
```
Uses existing `stream_explanation()` from `_explain.py`. Zero new LLM infrastructure needed.

**`_session_mgr.py`** (new) — extracted from `sql.py` to bring it from 416 → 322 lines:
- `_sessions` dict + `check_rate_limit()`
- `save_session_index()`, `restore_sessions()`
- `exec_session()`, `preload_chinook()`

### Frontend — `_corrections.ts`

```ts
getCorrection(dbRef, question)   // read from localStorage
saveCorrection(dbRef, question, correction)  // write
deleteCorrection(dbRef, question)            // remove
```

Key: normalized question (`trim().toLowerCase().slice(0, 100)`), partitioned by `dbRef`.

### Frontend — `ReasoningPanel.tsx`

- On mount: loads existing correction for current question from localStorage
- "Show Reasoning" → streams `/sql/reason` SSE
- Streaming cursor (blinking block) while loading
- "Teach the AI" section appears after reasoning loads
- Textarea placeholder: *"Something wrong? Tell the AI what it got wrong — e.g. revenue means UnitPrice × Quantity"*
- "Fix & Re-run" button: amber color when active, grey + disabled when empty
- On submit: `saveCorrection()` → `onRerun()` → `runQuery()` reads correction via `getCorrection()` in fetch body

---

## Rate Limit Explanation (no code change)

Groq free tier: ~6K tokens/min + daily cap. Switching to Cohere also rate-limited because all providers share the same backend API keys across all visitors. 60s resets per-minute limit only; daily limit resets at midnight UTC.

---

## Commits

| Hash | Repo | Description |
|---|---|---|
| `7e6390d` | ml-portfolio | docs(sql): add Auto-Insights section to User Guide modal |
| `a6291aa` | ml-portfolio | docs(sql): make 4-row minimum callout prominent |
| `3e586dd` | ml-portfolio | fix(sql): retry reuses current tab instead of creating a new one |
| `5f89ab5` | ml-portfolio | fix(sql): guard null rawType in ColumnProfileView; coerce non-string question |
| `1827909` | ml-portfolio | feat(sql): Auto-Insights panel |
| `e685ec4` | ml-portfolio | feat(sql): Show Reasoning + Teach the AI (Query Memory) |
| `56b300a` | ML-Unified | feat(ml-sql): correction injection + /sql/reason; refactor sql.py → _session_mgr.py |

---

## File Sizes (end of session)

| File | Lines |
|---|---|
| `TextToSqlRunner.tsx` | 396 |
| `QueryResultPanel.tsx` | 400 |
| `ReasoningPanel.tsx` | 167 (new) |
| `AutoInsights.tsx` | 189 |
| `_corrections.ts` | 28 (new) |
| `UserGuideModal.tsx` | 354 |
| `routers/sql.py` | 322 (was 416) |
| `routers/_session_mgr.py` | 87 (new) |
| `routers/_generate.py` | 353 |

---

## Pending / Next

- **#3 Column Lineage Graph** — DAG showing which source columns feed each result column (no extra LLM calls)
- **#9 Result Pinning** — deferred from Part 176
- **Real-Time Analytics Dashboard** — plan in `temporal-gliding-pascal.md`, needs Supabase setup first
- **Add Teach the AI to User Guide** — document the new Query Memory feature
