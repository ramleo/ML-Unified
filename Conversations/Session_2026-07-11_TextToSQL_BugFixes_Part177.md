# Session: Text-to-SQL Bug Fixes + Feature Verification — Part 177
**Date:** 2026-07-11
**Branch:** main
**Repos:** ml-portfolio (`src/app/tools/text-to-sql/`)

---

## Summary

Tested all 10 features from Part 176 using Playwright, found 3 bugs, fixed them all, then ran a full visual Playwright demo of every feature.

---

## Playwright Test Results (features verified)

| Feature | Result |
|---|---|
| Walkthrough (6-step spotlight) | ✅ Step 1 & 2 spotlit correctly |
| Schema autocomplete dropdown | ✅ "invoic" → Invoice/InvoiceId/InvoiceDate/InvoiceLine |
| Templates sidebar (6 templates) | ✅ Expands, click fills textarea |
| Ask button | ✅ Query runs, SQL + results load |
| History panel (collapsible) | ✅ Toggle works, shows Q1 with timestamp + row count |
| Chart type pills | ✅ Auto-detect, manual override with "manual · reset" badge |
| Multi-tab (2 tabs) | ✅ Each tab isolated, independent SQL/results |
| Tab switch + question sync | ✅ Textarea updates to active tab's question on switch |
| Column sort | ✅ Click header → ↑/↓ indicator, data re-sorted |
| Chart override persists | ✅ "BAR CHART · manual · reset" shown after switching |
| MD export | ✅ results.md downloaded |
| Tab persistence across reload | ✅ All tabs restored from sessionStorage after page reload |
| Cmd+K shortcut | ✅ Focused textarea |
| Cmd+Enter shortcut | ✅ Fired query |

---

## Bugs Found & Fixed (`cf4cc62`)

### Bug 1 — React #418 Hydration Error
**File:** `TextToSqlRunner.tsx`

`useState(() => sessionStorage.getItem(...))` lazy initializer ran on SSR (where `sessionStorage` doesn't exist), returning `[]` from the catch. Then on the client it returned the stored tabs — server/client HTML mismatch → React #418.

**Fix:** Initialize `tabs = []` and `activeTabId = null` (both server and client see the same empty state). Added `hydrated` state and a mount `useEffect` that restores from sessionStorage after hydration. Save effects guarded by `if (!hydrated) return` so they don't wipe sessionStorage before restore completes.

### Bug 2 — Chart Type Override Not Persisted Per Tab
**File:** `SqlChart.tsx`, `QueryResultPanel.tsx`, `TextToSqlRunner.tsx`

`overrideType` was local state inside `SqlChart`. When you switched tabs and came back, the component re-rendered with new props and the override reset to `null`.

**Fix:** 
- Added `chartOverride?: CT | null` field to `ResultTab` interface in `_types.ts`
- `SqlChart` now accepts `overrideType` and `onOverrideChange` as controlled props instead of local state
- `QueryResultPanel` passes them through
- `TextToSqlRunner` passes `activeTab.chartOverride` and `onChartOverride={t => patchTab(activeTabId, { chartOverride: t })}` so the override is stored in the tab

### Bug 3 — Question Input Not Synced on Tab Switch
**File:** `TextToSqlRunner.tsx`

Clicking an existing tab didn't update the textarea to show that tab's question. The input always showed whatever was last typed.

**Fix:** Added `useEffect` on `activeTabId` that reads `tabsRef.current.find(t => t.id === activeTabId)?.question` and calls `setQuestion()`. `tabsRef` is a ref kept in sync with `tabs` so the effect doesn't need `tabs` as a dependency (avoiding stale re-runs on every result update).

---

## Refactor: `_types.ts` Extracted

**Why:** After adding hydration state + tabsRef + question sync + CT import, `TextToSqlRunner.tsx` hit 415 lines.

**What moved to `_types.ts`:**
- `Provider` type
- `HistoryTurn` interface
- `FKRel` interface
- `SchemaTable` interface
- `Results` type
- `ResultTab` interface (with new `chartOverride` field)
- `SAMPLE_QUESTIONS` constant

Result: `TextToSqlRunner.tsx` down to 384 lines.

---

## Commit

| Hash | Description |
|------|-------------|
| `cf4cc62` | fix(sql): hydration error, chart override per tab, question sync on tab switch |

---

## File Sizes (end of session)

| File | Lines |
|---|---|
| `TextToSqlRunner.tsx` | 384 |
| `QueryResultPanel.tsx` | 388 |
| `SqlChart.tsx` | 359 |
| `_types.ts` | 33 (new) |
| `QuestionInput.tsx` | 173 |
| `TabBar.tsx` | 55 |
| `WalkthroughTooltip.tsx` | 118 |
| `DesktopSidebar.tsx` | 115 |
| `QueryHistoryPanel.tsx` | 103 |
| `_utils.tsx` | 87 |

---

## Playwright Feature Demo (visual tour)

Ran a full visual demo of all 10 features in the live deployed site:
1. Walkthrough spotlight — dark overlay with hole at question input
2. Schema autocomplete — "invoic" → 4 suggestions with TABLE/COL badges
3. Templates sidebar — 6 parameterised templates
4. Query + results — SQL, table, export buttons
5. History panel — collapsible, Q1 entry with timestamp
6. Chart type pills — auto Key Metrics, switched to Bar with "manual · reset"
7. Multi-tab — 2 tabs in tab bar, each isolated
8. Tab switch + question sync — textarea updated on tab click
9. Column sort — ↑ indicator on header click
10. Chart override per tab — "BAR CHART · manual · reset" badge
