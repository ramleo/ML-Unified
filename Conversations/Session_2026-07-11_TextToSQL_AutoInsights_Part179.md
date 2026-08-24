# Session: Text-to-SQL Auto-Insights & Bug Fixes — Part 179
**Date:** 2026-07-11
**Branch:** main
**Repos:** ml-portfolio (`src/app/tools/text-to-sql/`)

---

## Summary

Continued from Part 178. Implemented Auto-Insights (#5 from mind-blowing feature research), fixed retry tab-spawning bug, and fixed `t.trim is not a function` TypeError.

---

## New Feature — Auto-Insights Panel

**Files:** new `AutoInsights.tsx`, `QueryResultPanel.tsx` (+2 lines)
**Commit:** `1827909`

After every query, automatically scans result rows client-side (no backend call) and surfaces up to 8 ranked insights in a collapsible emerald panel below the results table.

### Insight types detected

| Type | Example | Severity |
|---|---|---|
| **null** | `billing_state` — 38% null (19 of 50) | warn if >30%, info if >5% |
| **outlier** | `total` — 2 outliers — 13.86 to 25.86 | warn |
| **dominant** | `billing_country` — "USA" in 53% of rows | info |
| **unique_key** | `invoice_id` — 100% distinct — likely a key | info |
| **constant** | `status` — constant — every row = "active" | note |
| **skew** | `revenue` — range 1 → 450 (450× spread) | info |

### Implementation details
- `computeInsights()` — pure function, no hooks, no side effects
- Guards: `rows.length < 4` → returns `[]` (too small to be meaningful)
- Scoring: ranked by interestingness score, top 8 shown
- Outlier detection: Z-score > 2.5 threshold, capped at 10% of rows
- Dominance threshold: top value appears in >40% of non-null rows
- Header shows warning badge count if any severity=warn insights exist
- Collapsible (starts open)

### Integration
- `QueryResultPanel.tsx` gets import + 1 JSX line (now 391 lines, under 400 cap)
- `AutoInsights.tsx`: 189 lines

---

## Bug Fix — Retry Creates New Tab

**File:** `TextToSqlRunner.tsx`
**Commit:** `3e586dd`

### Problem
Every click of "Try again" called `runQuery()` which always created a new tab (via `Date.now().toString()` tab ID). Clicking retry 4 times = 4 ghost tabs with same question.

### Fix
Added `existingTabId?: string` parameter to `runQuery`. When passed:
- Reuses that tab ID
- Calls `patchTab(tabId, { sql: null, results: null, error: null, ... })` to reset state in-place
- Does NOT push to the tab list

`onRetry` prop wired as:
```tsx
onRetry={() => runQuery(activeTab?.question, activeTabId ?? undefined)}
```

---

## Bug Fix — `t.trim is not a function` TypeError

**Files:** `ColumnProfileView.tsx`, `TextToSqlRunner.tsx`
**Commit:** `5f89ab5`

### Root cause
Two places where external (backend) data could arrive as non-string at runtime despite TypeScript types:

1. **`ColumnProfileView.tsx`** — `getTypeMeta(rawType)` and `TypeIcon({ rawType })` both called `rawType.split("(")[0].toUpperCase().trim()`. If backend returns a column with `type: null` (unknown CSV column type), this crashes.

2. **Sample questions** — `/sql/sample-questions` returns LLM-generated strings. If LLM returns non-string elements, `setDynQ(d.questions)` stores them, and clicking "Surprise me" passes a non-string to `runQuery()` → `activeQ.trim()` throws.

### Fix
```tsx
// ColumnProfileView.tsx
const base = (rawType ?? "").split("(")[0].toUpperCase().trim();
```

```tsx
// TextToSqlRunner.tsx — sample questions sanitization
setDynQ(d.questions.map((q: unknown) => String(q)));

// TextToSqlRunner.tsx — runQuery defensive coerce
const activeQ = String(questionOverride ?? question);
```

---

## Rate Limit Explanation (no code change needed)

User asked why Groq rate-limited after 4 queries and why switching to Cohere also showed rate limit:

- **Groq free tier**: ~6K tokens/min AND daily cap. 4 queries burns the daily cap fast. 60s resets per-minute, not per-day.
- **Shared keys**: All visitors to the portfolio share the same backend API keys. Cohere's trial key has ~1,000 req/month total.
- **Resolution**: Wait until midnight UTC for daily reset, or get paid API keys.

---

## Auto-Insights Not Visible for CSV (explanation, no code change)

User asked why Auto-Insights didn't appear for CSV uploads. Two reasons:
1. Auto-Insights only appears in the **query results panel** — requires running a query first, not just uploading.
2. The panel guards `rows.length < 4`, so very small CSVs would be skipped.

No code change made (user didn't request auto-query after upload).

---

## Commits

| Hash | Repo | Description |
|---|---|---|
| `1827909` | ml-portfolio | feat(sql): Auto-Insights panel — surface nulls, outliers, dominant values, and skew |
| `3e586dd` | ml-portfolio | fix(sql): retry reuses current tab instead of creating a new one |
| `5f89ab5` | ml-portfolio | fix(sql): guard null rawType in ColumnProfileView and coerce non-string question in runQuery |

---

## File Sizes (end of session)

| File | Lines |
|---|---|
| `TextToSqlRunner.tsx` | 394 |
| `QueryResultPanel.tsx` | 391 |
| `AutoInsights.tsx` | 189 (new) |
| `ColumnProfileView.tsx` | 95 |

---

## Pending / Next

- **#2 Streamed Chain-of-Thought** — next recommended from the mind-blowing list
- **#3 Column Lineage Graph** — after CoT
- **#9 Result Pinning** — deferred from Part 176
- **Real-Time Analytics Dashboard** — plan in `temporal-gliding-pascal.md`, needs Supabase setup first
