# TC-P9 — Parts 173–200 Test Cases (Round 5)

**Generated:** 2026-08-22
**Parts covered:** 173–200 (Text-to-SQL feature sprint, Real-Time Analytics dashboard, index.html split + HF Space tracking, Vision fixes, Document Intelligence build)
**Total:** 128 test cases
**Status:** Complete for available logs — Parts 158–172 have no session logs in `Conversations/` (a real gap, separate from missing test cases; nothing to derive TCs from for that range)

---

## Text-to-SQL — On-Demand Explanation

---

### TC-P9-001
**Category:** Feature
**Test Name:** Query results no longer trigger an automatic AI explanation
**Steps:**
1. Run any query in Text-to-SQL
2. Observe the SSE stream after `results`
**Expected Result:** Stream ends at `done` immediately after `results` — no `token` events fire without user action
**Automation Hint:** pytest — assert no LLM call is made between `results` and `done` events
**Source:** Part173

### TC-P9-002
**Category:** Feature
**Test Name:** "Explain with AI" button triggers on-demand explanation
**Steps:**
1. Run a query, wait for results
2. Click "Explain with AI"
**Expected Result:** Button disappears, spinner "Generating explanation…" shows, then an indigo explanation card with text + suggestion chips appears
**Automation Hint:** Playwright — click button, assert spinner then card appear
**Source:** Part173

### TC-P9-003
**Category:** Bug-Regression
**Test Name:** Explain rate-limit error shown inline, not in main error block
**Steps:**
1. Trigger a rate limit on `/sql/explain` (e.g. rapid repeated clicks)
**Expected Result:** Red inline error appears below the "Explain with AI" button; the main query error block is untouched
**Automation Hint:** Mock 429 from `/sql/explain`, assert inline error element, not global error banner
**Source:** Part173

### TC-P9-004
**Category:** Bug-Regression
**Test Name:** New query clears previous explanation state
**Steps:**
1. Run query A, click Explain, wait for explanation
2. Run query B in the same tab
**Expected Result:** Explanation card, loading state, and error state all reset — no stale explanation from query A shown alongside query B's results
**Automation Hint:** Playwright — assert explanation card absent immediately after query B's `results` event
**Source:** Part173

### TC-P9-005
**Category:** UI
**Test Name:** Clear (×) button on question textarea only shows when non-empty
**Steps:**
1. Load Text-to-SQL with empty question input
2. Type text into the question input
3. Click the × button
**Expected Result:** × button hidden when input empty, visible after typing, clicking it clears the textarea back to empty
**Automation Hint:** Playwright — assert button visibility toggles with input value; click clears text
**Source:** Part173

---

## Real-Time Analytics — Core Infrastructure

---

### TC-P9-006
**Category:** Feature
**Test Name:** Page view fires POST /api/track and inserts a Supabase row
**Steps:**
1. Load any ml-portfolio page
2. Check Supabase `events` table for a new row
**Expected Result:** A row with `type: "page_view"`, a `session_id`, and `path` matching the loaded page is inserted
**Automation Hint:** pytest/integration — mock Supabase insert, assert called with correct type/path
**Source:** Part174

### TC-P9-007
**Category:** Feature
**Test Name:** Analytics dashboard updates live via Supabase Realtime, no polling
**Steps:**
1. Open `/tools/realtime-analytics` in tab A
2. In tab B, trigger a `page_view` event on any page
**Expected Result:** Tab A's live feed, stat cards, and charts update within ~1s without a page reload or interval-based fetch
**Automation Hint:** Playwright — two contexts, assert feed row count increases in tab A after tab B action
**Source:** Part174

### TC-P9-008
**Category:** Backend API
**Test Name:** /api/events/recent returns last 50 events ordered by created_at descending
**Steps:**
1. `GET /api/events/recent` with >50 events in the table
**Expected Result:** Response contains exactly 50 events, first one is the most recent by `created_at`
**Automation Hint:** pytest — assert `len(response) == 50` and `response[0].created_at >= response[1].created_at`
**Source:** Part174

### TC-P9-009
**Category:** Data
**Test Name:** Anonymous session ID persists via localStorage across page loads
**Steps:**
1. Load a page, read `localStorage` session UUID
2. Reload the page
**Expected Result:** Same UUID persists; a new one is only generated if localStorage was empty
**Automation Hint:** Playwright — read localStorage before/after reload, assert equality
**Source:** Part174

---

## Text-to-SQL — Pagination, Charts, Manual Editor, Tracking

---

### TC-P9-010
**Category:** Bug-Regression
**Test Name:** User's LIMIT clause is respected in paginated queries
**Steps:**
1. Ask a question that generates SQL with `LIMIT 5`
2. Inspect the returned row count and the row-count badge
**Expected Result:** Exactly 5 rows returned (or fewer if the table has fewer), not the default page size of 50; badge reflects the correct total count
**Automation Hint:** pytest — call `/sql/query` with a prompt generating `LIMIT 5`, assert `len(rows) <= 5`
**Source:** Part175

### TC-P9-011
**Category:** UI
**Test Name:** All SQL chart types are capped at 200px height
**Steps:**
1. Run a query that produces each chart type (Bar, Grouped Bar, Line, Area, Scatter, Donut)
**Expected Result:** No chart SVG exceeds 200px height (donut capped at 180px); charts don't stretch the result card
**Automation Hint:** Playwright — `getBoundingClientRect().height` on each chart SVG, assert `<= 200`
**Source:** Part175

### TC-P9-012
**Category:** Feature
**Test Name:** Manual SQL editor shows "Edited" badge only after real divergence
**Steps:**
1. Run a query, click "Edit" on the generated SQL
2. Click "Done" without changing anything
3. Click "Edit" again, change one character
**Expected Result:** No "Edited" badge after step 2 (no divergence); amber "Edited" badge appears after step 3
**Automation Hint:** Playwright — assert badge absent/present at each step
**Source:** Part175

### TC-P9-013
**Category:** Feature
**Test Name:** "Run edited SQL" re-executes via /sql/page and updates results in place
**Steps:**
1. Edit generated SQL to change a `LIMIT` value
2. Click "Run edited SQL"
**Expected Result:** Results table updates to reflect the new SQL without spawning a new tab or losing the edit state
**Automation Hint:** Playwright — assert row count changes to match new LIMIT, tab count unchanged
**Source:** Part175

### TC-P9-014
**Category:** Feature
**Test Name:** Editor resets when a new AI query is run
**Steps:**
1. Edit SQL, see "Edited" badge
2. Ask a new question (not retry)
**Expected Result:** Editor collapses back to syntax-highlighted view, "Edited" badge is gone for the new query
**Automation Hint:** Playwright — assert editor state resets on new `generatedSql` prop change
**Source:** Part175

### TC-P9-015
**Category:** Feature
**Test Name:** tool_open event fires on every tool page mount
**Steps:**
1. Visit each of the 12 tool pages once
**Expected Result:** Each visit fires exactly one `tool_open` POST to `/api/track` with the correct `tool` name in meta
**Automation Hint:** Playwright — intercept `/api/track` requests, assert one `tool_open` per page with correct meta.tool
**Source:** Part175

### TC-P9-016
**Category:** Feature
**Test Name:** query_run event fires with row count and provider on successful SQL execution
**Steps:**
1. Run a query successfully in Text-to-SQL
2. Inspect the tracked event
**Expected Result:** `query_run` event fired with `meta.provider` and row count matching the actual result set
**Automation Hint:** Playwright — intercept `/api/track`, assert `type=="query_run"` and meta fields present
**Source:** Part175

### TC-P9-017
**Category:** Backend API
**Test Name:** Remote DB (Postgres/MySQL/SQL Server) pagination shows correct total count
**Steps:**
1. Connect a Postgres/MySQL/SQL Server database
2. Run a query returning more rows than one page
**Expected Result:** "Showing X of Y rows" shows the real total count, not `-1`
**Automation Hint:** pytest — call `count_rows_remote` against each dialect, assert count matches a known table's row count
**Source:** Part178

---

## Text-to-SQL — Multi-Tab Results

---

### TC-P9-018
**Category:** Feature
**Test Name:** Each question spawns an isolated result tab
**Steps:**
1. Ask question A, then question B (different tab, not retry)
**Expected Result:** Two tabs exist, each with its own SQL, results, pagination, and filter state — switching tabs doesn't leak state between them
**Automation Hint:** Playwright — run two distinct queries, assert two tab elements, switch and verify SQL panel content differs
**Source:** Part176

### TC-P9-019
**Category:** Data
**Test Name:** Max 5 tabs; oldest unpinned tab evicted on 6th question
**Steps:**
1. Ask 6 distinct questions in sequence, none pinned
**Expected Result:** Exactly 5 tabs remain; the oldest (1st question's tab) is evicted
**Automation Hint:** Playwright — run 6 queries, assert tab count == 5 and tab 1's content is gone
**Source:** Part176

### TC-P9-020
**Category:** Feature
**Test Name:** Pinned tabs are exempt from the 5-tab eviction limit
**Steps:**
1. Pin tab 1 (star icon)
2. Ask 5 more distinct questions
**Expected Result:** Tab 1 remains despite exceeding what would otherwise be the 5-tab cap
**Automation Hint:** Playwright — pin first tab, run 5 more queries, assert pinned tab still present
**Source:** Part176

### TC-P9-021
**Category:** Bug-Regression
**Test Name:** Ask button does not throw MouseEvent-related TypeError
**Steps:**
1. Type a question, click the Ask button
**Expected Result:** Query runs normally; no `TypeError: t.trim is not a function` in console
**Automation Hint:** Playwright — assert no console errors after click; regression test for `onClick={() => onSubmit()}` not `onClick={onSubmit}`
**Source:** Part176

### TC-P9-022
**Category:** Bug-Regression
**Test Name:** SQL Explain does not hallucinate "no results" when data exists
**Steps:**
1. Run a query with results, click "Explain with AI"
**Expected Result:** Explanation references the actual returned data, does not claim "there are no results to display"
**Automation Hint:** pytest — call `/sql/explain` with non-empty columns/rows, assert prompt payload includes real row data
**Source:** Part176

### TC-P9-023
**Category:** Feature
**Test Name:** MD export downloads a file instead of silently copying to clipboard
**Steps:**
1. Run a query, click the MD export button
**Expected Result:** `results.md` downloads directly; no reliance on clipboard permission
**Automation Hint:** Playwright — intercept download event, assert filename `results.md`
**Source:** Part176

### TC-P9-024
**Category:** Data
**Test Name:** Tab state persists across page reload via sessionStorage
**Steps:**
1. Open 2 tabs with different queries
2. Reload the page
**Expected Result:** Both tabs and their `activeTabId` are restored exactly as before reload
**Automation Hint:** Playwright — reload, assert tab count and active tab question text match pre-reload state
**Source:** Part176

### TC-P9-025
**Category:** Feature
**Test Name:** Column sort toggles asc/desc and sorts by correct type
**Steps:**
1. Run a query with a numeric and a string column
2. Click the numeric column header twice, then the string column header
**Expected Result:** First click sorts ascending numerically, second click descending; string column sorts lexicographically; nulls sort last in all cases
**Automation Hint:** pytest/unit — feed a mixed-null array into the sort function, assert null values are at the end
**Source:** Part176

### TC-P9-026
**Category:** Feature
**Test Name:** Chart type override persists and shows manual/reset badge
**Steps:**
1. Run a query, override the auto-detected chart type via a type pill
**Expected Result:** Chart re-renders as the selected type; "manual · reset" badge shown; clicking "reset" restores auto-detected type
**Automation Hint:** Playwright — click a chart-type pill, assert badge text and chart type change
**Source:** Part176

### TC-P9-027
**Category:** Feature
**Test Name:** Schema autocomplete suggests tables/columns after 2 characters
**Steps:**
1. Type "invoic" into the question input
**Expected Result:** Dropdown shows matching schema entries (e.g. Invoice, InvoiceId, InvoiceDate) each tagged "table" or "col"; Tab completes, ↑↓ navigates, Esc dismisses
**Automation Hint:** Playwright — type partial text, assert dropdown items and badges appear
**Source:** Part176

### TC-P9-028
**Category:** Feature
**Test Name:** Keyboard shortcuts focus input and run query globally
**Steps:**
1. Press Ctrl/Cmd+K anywhere on the page
2. Type a question, press Ctrl/Cmd+Enter
**Expected Result:** Cmd+K focuses the question textarea; Cmd+Enter runs the query even without prior focus loss issues (uses ref to avoid stale closure)
**Automation Hint:** Playwright — press key combos, assert focus and query execution
**Source:** Part176

### TC-P9-029
**Category:** Feature
**Test Name:** SQL diff view shows red/green line diff between original and edited SQL
**Steps:**
1. Edit generated SQL
2. Click the "Edited · diff" badge
**Expected Result:** A diff view renders showing removed lines in red, added lines in green
**Automation Hint:** pytest/unit — feed two SQL strings into `SqlDiff`, assert diff output contains both add/remove markers
**Source:** Part176

### TC-P9-030
**Category:** Feature
**Test Name:** First-time walkthrough dismissal persists via localStorage
**Steps:**
1. Load Text-to-SQL for the first time, complete or skip the walkthrough
2. Reload the page
**Expected Result:** Walkthrough does not reappear; `localStorage.ml_sql_walked` is set
**Automation Hint:** Playwright — clear localStorage, load page, dismiss tour, reload, assert tour absent
**Source:** Part176

---

## Text-to-SQL — Multi-Tab Bug Fixes (Post-Verification)

---

### TC-P9-031
**Category:** Bug-Regression
**Test Name:** No React hydration mismatch on page load with existing sessionStorage tabs
**Steps:**
1. Have tabs saved in sessionStorage from a prior session
2. Reload the page
**Expected Result:** No React #418 hydration error in console; tabs appear after mount via a client-side restore effect, not during SSR
**Automation Hint:** Playwright — reload with pre-seeded sessionStorage, assert zero console errors matching "Hydration" or "#418"
**Source:** Part177

### TC-P9-032
**Category:** Bug-Regression
**Test Name:** Chart type override persists per-tab across tab switches
**Steps:**
1. In tab A, override chart type to Bar
2. Switch to tab B, then back to tab A
**Expected Result:** Tab A still shows "BAR CHART · manual · reset" — override was not reset by the tab switch
**Automation Hint:** Playwright — switch tabs twice, assert override badge still present on return
**Source:** Part177

### TC-P9-033
**Category:** Bug-Regression
**Test Name:** Question textarea syncs to the active tab's question on tab switch
**Steps:**
1. Ask question A (tab 1), ask question B (tab 2)
2. Click tab 1
**Expected Result:** Textarea shows question A's text, not B's or leftover typed text
**Automation Hint:** Playwright — click tab 1 after creating tab 2, assert textarea value equals question A
**Source:** Part177

---

## Text-to-SQL — Walkthrough, Glossary, ER Diagram, User Guide

---

### TC-P9-034
**Category:** UI
**Test Name:** Walkthrough tooltip stays within viewport for late steps
**Steps:**
1. Advance the walkthrough to step 4 (near bottom of sidebar)
**Expected Result:** Tooltip card is fully visible, not clipped at the bottom of the viewport
**Automation Hint:** Playwright — assert tooltip `getBoundingClientRect().bottom <= window.innerHeight`
**Source:** Part178

### TC-P9-035
**Category:** Bug-Regression
**Test Name:** Glossary field clears when switching from Chinook to CSV upload
**Steps:**
1. Use the Chinook demo, note any glossary placeholder
2. Upload a CSV file instead
**Expected Result:** Glossary textarea is empty (real content, not a Chinook-specific placeholder implying leftover data)
**Automation Hint:** Playwright — assert `glossary` state is `""` after `uploadDb`/`connectRemote`
**Source:** Part178

### TC-P9-036
**Category:** Feature
**Test Name:** Single-table CSV upload shows Column Profile view instead of empty ER diagram
**Steps:**
1. Upload a single-table CSV with no foreign keys
**Expected Result:** `ColumnProfileView` renders (type-colored icons, badges, distribution bar) instead of a near-empty ER diagram canvas
**Automation Hint:** Playwright — assert `ColumnProfileView` element present when `names.length === 1 && foreign_keys.length === 0`
**Source:** Part178

### TC-P9-037
**Category:** Feature
**Test Name:** User Guide modal covers all major features
**Steps:**
1. Click "User Guide" in the sidebar
**Expected Result:** Modal opens with sections for Getting Started, Connecting Data, AI Providers, Working with Results, Multi-Tab Workflow, SQL Panel, AI Explanation, Schema & Glossary, History & Saved, Keyboard Shortcuts, Tips & Tricks
**Automation Hint:** Playwright — assert all named section headings are present in the modal DOM
**Source:** Part178

---

## Text-to-SQL — Auto-Insights

---

### TC-P9-038
**Category:** Feature
**Test Name:** Auto-Insights panel surfaces null, outlier, dominant, unique-key, constant, and skew insights
**Steps:**
1. Run a query returning ≥4 rows with a mix of null values, an outlier, and a dominant categorical value
**Expected Result:** Insights panel shows up to 8 ranked insights covering the detected categories, each with correct severity coloring
**Automation Hint:** pytest/unit — call `computeInsights()` with a crafted dataset, assert expected insight types are present
**Source:** Part179

### TC-P9-039
**Category:** Data
**Test Name:** Auto-Insights panel is hidden for fewer than 4 result rows
**Steps:**
1. Run a query returning 3 rows
**Expected Result:** No Auto-Insights panel rendered (guard returns `[]` for `rows.length < 4`)
**Automation Hint:** pytest/unit — call `computeInsights()` with a 3-row array, assert returns `[]`
**Source:** Part179

### TC-P9-040
**Category:** Bug-Regression
**Test Name:** Retry ("Try again") reuses the current tab instead of creating a new one
**Steps:**
1. Run a query that errors
2. Click "Try again" 3 times
**Expected Result:** Tab count stays at 1 — no ghost tabs with the same question are created
**Automation Hint:** Playwright — click retry 3 times, assert `tabs.length === 1`
**Source:** Part179

### TC-P9-041
**Category:** Bug-Regression
**Test Name:** ColumnProfileView does not crash on a null column type
**Steps:**
1. Upload a CSV with a column whose backend-inferred type is `null`
**Expected Result:** Column Profile renders without a `t.trim is not a function` TypeError; falls back to an empty/unknown type label
**Automation Hint:** pytest/unit — call `getTypeMeta(null)`, assert it doesn't throw
**Source:** Part179

### TC-P9-042
**Category:** Bug-Regression
**Test Name:** Non-string sample question does not crash "Surprise Me"
**Steps:**
1. Mock `/sql/sample-questions` returning a non-string element
2. Click "Surprise Me"
**Expected Result:** Question runs without throwing; non-string values are coerced via `String()` before use
**Automation Hint:** pytest/unit — pass a non-string value through the sanitization map, assert result is a string
**Source:** Part179

---

## Text-to-SQL — Teach the AI (Query Memory) + Reasoning

---

### TC-P9-043
**Category:** Feature
**Test Name:** "Show Reasoning" streams AI reasoning without auto-firing on every query
**Steps:**
1. Run a query, observe SQL panel
2. Click "Show Reasoning"
**Expected Result:** No reasoning call happens until the button is clicked; clicking streams step-by-step reasoning text
**Automation Hint:** Playwright — assert no `/sql/reason` request until "Show Reasoning" is clicked
**Source:** Part180

### TC-P9-044
**Category:** Feature
**Test Name:** "Fix & Re-run" stays disabled until a correction is typed
**Steps:**
1. Open the Reasoning panel's "Teach the AI" section
2. Leave the textarea empty
**Expected Result:** "Fix & Re-run" button is greyed out / disabled; typing any text enables it (amber)
**Automation Hint:** Playwright — assert `disabled` attribute toggles based on textarea content
**Source:** Part180

### TC-P9-045
**Category:** Feature
**Test Name:** Saved correction is automatically applied on the same question + database next time
**Steps:**
1. Ask a question, save a correction via "Fix & Re-run"
2. Ask the exact same question again on the same database
**Expected Result:** The correction is included in the LLM prompt automatically; a green badge shows the saved correction
**Automation Hint:** pytest — assert `getCorrection(dbRef, question)` returns the saved text and is injected into the `/sql/query` payload
**Source:** Part180

### TC-P9-046
**Category:** Data
**Test Name:** Corrections are scoped per-database, not shared globally
**Steps:**
1. Save a correction while using the Chinook demo
2. Switch to a CSV upload, ask the same question text
**Expected Result:** No correction applied — corrections from Chinook do not leak into the CSV database's queries
**Automation Hint:** pytest/unit — assert `getCorrection` keys by `dbRef`, returns `null` for a different `dbRef`
**Source:** Part180

### TC-P9-047
**Category:** Backend API
**Test Name:** /sql/reason streams step-by-step reasoning for a given SQL
**Steps:**
1. `POST /sql/reason` with `{question, sql, columns}`
**Expected Result:** SSE stream of reasoning tokens describing intent, columns chosen, and assumptions made
**Automation Hint:** pytest — call endpoint, assert streamed text is non-empty and references the input SQL's tables/columns
**Source:** Part180

---

## Text-to-SQL — Column Lineage Graph

---

### TC-P9-048
**Category:** Feature
**Test Name:** Column Lineage Graph renders source→output DAG for a JOIN query
**Steps:**
1. Run a query with an aliased JOIN and aggregation (e.g. `ar.Name`, `COUNT(DISTINCT Title) AS album_count`)
**Expected Result:** Lineage panel shows source columns on the left, output columns on the right, connected by curves; hidden entirely if no lineage detected
**Automation Hint:** pytest/unit — call `parseLineage()` on the SQL string, assert correct source→output pairs
**Source:** Part181

### TC-P9-049
**Category:** Bug-Regression
**Test Name:** Lineage parser handles SQL with newlines before FROM
**Steps:**
1. Run a query where generated SQL has `\nFROM` (newline, not space)
**Expected Result:** Lineage graph still parses correctly — not empty
**Automation Hint:** pytest/unit — call `parseLineage()` with a multiline SQL string, assert non-empty result
**Source:** Part181

### TC-P9-050
**Category:** Bug-Regression
**Test Name:** Lineage parser strips quoted identifiers correctly
**Steps:**
1. Run a query where the LLM generates `"Name"` (double-quoted identifier)
**Expected Result:** Output column shows `Name`, not `?`
**Automation Hint:** pytest/unit — `parseLineage('SELECT "Name" FROM Artist')`, assert output label is `Name`
**Source:** Part181

### TC-P9-051
**Category:** Bug-Regression
**Test Name:** Lineage parser handles quoted multi-word aliases
**Steps:**
1. Run a query generating `COUNT(t.TrackId) AS "Track Count"`
**Expected Result:** Output node labeled `Track Count`, not `count`
**Automation Hint:** pytest/unit — `extractAlias()` on that fragment, assert result is `"Track Count"`
**Source:** Part182

### TC-P9-052
**Category:** UI
**Test Name:** Lineage SVG does not scale up font size on wide containers
**Steps:**
1. Open lineage graph on a wide viewport (~900px container)
**Expected Result:** SVG renders at its natural 460px max-width; font stays legible, not oversized
**Automation Hint:** Playwright — assert computed font size of a lineage label stays near the authored value regardless of container width
**Source:** Part182

---

## Real-Time Analytics — Session Path, Sparkline, Funnel, Geo

---

### TC-P9-053
**Category:** Bug-Regression
**Test Name:** Session path panel shows the real error instead of a silent "No events found"
**Steps:**
1. Force `/api/events/session/{id}` to return an error response
2. Click "trace" on a live feed event
**Expected Result:** The actual error message is shown in the panel, not a generic "No events found"
**Automation Hint:** Mock API error response, assert panel renders the error text, not the empty-state copy
**Source:** Part183

### TC-P9-054
**Category:** Bug-Regression
**Test Name:** Session route does not break when optional Supabase columns are missing
**Steps:**
1. Query `/api/events/session/{id}` against a table missing `duration_ms`/`meta` columns
**Expected Result:** Route still returns data (uses `select("*")`), does not 500
**Automation Hint:** pytest — assert the route selects `*` and gracefully handles absent fields
**Source:** Part183

### TC-P9-055
**Category:** Bug-Regression
**Test Name:** Sparkline shows data even when all events are older than 30 minutes
**Steps:**
1. Have events only from 4+ hours ago
2. Load the dashboard
**Expected Result:** Sparkline shows today's events bucketed by hour, not "No data yet"
**Automation Hint:** Seed events from 4h ago, assert sparkline chart has non-zero bars
**Source:** Part183

### TC-P9-056
**Category:** Feature
**Test Name:** Session path groups consecutive same-type-and-path events into a collapsible card
**Steps:**
1. Trace a session with 4 consecutive `page_view /` events followed by a different event
**Expected Result:** The 4 repeated events collapse into one card with a `×4` badge; clicking expands to show all 4 with timestamps
**Automation Hint:** pytest/unit — call `groupEvents()` on a crafted event array, assert grouping and count
**Source:** Part183

### TC-P9-057
**Category:** UI
**Test Name:** Session ID shown in live feed to disambiguate same-country events
**Steps:**
1. Load the live feed with events from the same country but different sessions
**Expected Result:** Each row shows the first 8 chars of `session_id`; clicking "trace" highlights only rows with a matching session ID
**Automation Hint:** Playwright — assert only rows with matching session-id prefix turn green after trace click
**Source:** Part183

### TC-P9-058
**Category:** Feature
**Test Name:** Date range picker updates all dashboard panels consistently
**Steps:**
1. Switch range from "Today" to "7 days"
**Expected Result:** Sparkline switches to daily buckets, "Active Now" label becomes "Unique Sessions", all panel labels update to reflect the new range
**Automation Hint:** Playwright — click range pill, assert sparkline bucket count and stat card label text change
**Source:** Part184

### TC-P9-059
**Category:** Feature
**Test Name:** Custom calendar range picker selects a valid start/end and re-fetches stats
**Steps:**
1. Open the calendar, click a start date, then an end date
**Expected Result:** Range confirmed, stats API called with `?start=...&end=...`, single-day selection uses hourly buckets, multi-day uses daily buckets
**Automation Hint:** Playwright — select two different dates, assert the request URL includes both start and end params
**Source:** Part184

### TC-P9-060
**Category:** Bug-Regression
**Test Name:** Top Referrers dedupes by hostname+pathname, not full URL with query params
**Steps:**
1. Generate referrer events for the same page with different query strings
**Expected Result:** They're grouped into a single row (same hostname+pathname), not shown as separate duplicate-looking rows
**Automation Hint:** pytest — feed URLs differing only by query string into the aggregation, assert single grouped count
**Source:** Part184

### TC-P9-061
**Category:** Feature
**Test Name:** Bounce rate correctly counts single-event sessions
**Steps:**
1. Seed 10 sessions: 3 with exactly 1 event, 7 with 2+ events
**Expected Result:** Bounce rate stat card shows 30% (3/10)
**Automation Hint:** pytest — feed the session-event-count map into the bounce rate calc, assert `bounce_rate == 30`
**Source:** Part185

### TC-P9-062
**Category:** Feature
**Test Name:** Average session duration computed from tool_close duration_ms only
**Steps:**
1. Seed `tool_close` events with `duration_ms` values, plus other event types with no duration
**Expected Result:** Avg Duration stat card averages only the `tool_close` durations, ignores other event types
**Automation Hint:** pytest — assert the avg calc filters `type === "tool_close" && duration_ms > 0"`
**Source:** Part185

### TC-P9-063
**Category:** UI
**Test Name:** Avg Duration card shows placeholder text before any tool_close data exists
**Steps:**
1. Load dashboard with zero `tool_close` events
**Expected Result:** Card shows "—" and "no tool_close data yet" instead of a misleading `0s`
**Automation Hint:** Playwright — assert card text matches the no-data placeholder when stats API returns null avg
**Source:** Part185

### TC-P9-064
**Category:** Feature
**Test Name:** Time per Tool row only renders when tool_close data with duration exists
**Steps:**
1. Open a session trace for a session with no `tool_close` events
2. Open a session trace for one that has them
**Expected Result:** First trace shows no "Time per Tool" row; second shows purple pills per tool summing time correctly
**Automation Hint:** pytest/unit — call the time-per-tool aggregator on both event sets, assert empty vs populated result
**Source:** Part185

### TC-P9-065
**Category:** Bug-Regression
**Test Name:** Live feed row click-to-expand works regardless of event ID type
**Steps:**
1. Receive a live feed event via Supabase Realtime WebSocket (ID delivered as string)
2. Click the row
**Expected Result:** Row expands correctly — expand key is `session_id + created_at`, not a numeric ID comparison that fails on string IDs
**Automation Hint:** Playwright — click a realtime-delivered row, assert it expands
**Source:** Part188

### TC-P9-066
**Category:** Feature
**Test Name:** Live feed filters by event type and country
**Steps:**
1. Load a feed with mixed event types and countries
2. Click a type filter pill, then a country filter pill
**Expected Result:** Feed shows only matching rows; "All" resets both filters; empty state differs ("No events match filter" vs "Waiting for events…")
**Automation Hint:** Playwright — apply filters, assert visible row count and content match the filter criteria
**Source:** Part186

### TC-P9-067
**Category:** Feature
**Test Name:** Per-tool query success rate bars color-code by threshold
**Steps:**
1. Seed query_run events per tool with success rates of 95%, 80%, and 50%
**Expected Result:** Bars render green (≥90%), amber (70–89%), and red (<70%) respectively
**Automation Hint:** pytest/unit — feed each rate into the color-selection function, assert correct color returned
**Source:** Part186

### TC-P9-068
**Category:** Feature
**Test Name:** CSV export downloads events matching the active date range
**Steps:**
1. Select a date range, click "Export CSV"
**Expected Result:** Downloaded file's filename includes the range and date; row count matches events in that range; `meta` field is valid JSON per row
**Automation Hint:** Playwright — intercept the download, parse CSV, assert row count matches the range's known event count
**Source:** Part186

### TC-P9-069
**Category:** Feature
**Test Name:** Session trace drawer opens as a right-side overlay without shifting page content
**Steps:**
1. Click "trace" on a live feed row
**Expected Result:** A 320px right-side drawer slides in with a blurred backdrop; underlying dashboard content does not reflow or shift position
**Automation Hint:** Playwright — capture bounding rect of a dashboard element before/after opening drawer, assert unchanged
**Source:** Part186

### TC-P9-070
**Category:** Feature
**Test Name:** Sparkline and Geo Map show tooltips on hover
**Steps:**
1. Hover a sparkline data point
2. Hover a geo map country dot
**Expected Result:** Sparkline shows `{minute} · {count} events`; geo map shows `{country} · {count}`
**Automation Hint:** Playwright — dispatch mouseenter, assert tooltip text content
**Source:** Part187

### TC-P9-071
**Category:** Feature
**Test Name:** Activity Heatmap always reflects the last 7 days regardless of range selector
**Steps:**
1. Set the dashboard range to "30 days"
2. Inspect the Activity Heatmap section
**Expected Result:** Heatmap still shows only the last 7 days of data, unaffected by the 30-day selector
**Automation Hint:** pytest — assert heatmap query always uses a fixed 7-day window independent of the `range` param
**Source:** Part187

### TC-P9-072
**Category:** Feature
**Test Name:** Auto-refresh only runs when range is "today"
**Steps:**
1. Set range to "today", wait 60s
2. Set range to "7 days", wait 60s
**Expected Result:** Stats silently re-fetch every 60s only in the "today" case; no background refresh for other ranges
**Automation Hint:** Mock timers — assert fetch call count increments only when range === "today"
**Source:** Part187

### TC-P9-073
**Category:** Feature
**Test Name:** Event detail drawer expands inline on live feed row click, shows all meta fields
**Steps:**
1. Click a live feed row with `query_run` type
**Expected Result:** Inline drawer shows full timestamp, referrer, duration, and every key/value in `meta`; clicking again collapses it
**Automation Hint:** Playwright — click row, assert detail panel contains expected meta keys; click again, assert collapse
**Source:** Part187

---

## Real-Time Analytics — Tracking Expansion

---

### TC-P9-074
**Category:** Feature
**Test Name:** useToolTracking fires tool_open on mount and tool_close with duration on unmount
**Steps:**
1. Navigate to a tool page, wait, then navigate away
**Expected Result:** `tool_open` fires on mount; `tool_close` fires on unmount with `duration_ms` roughly matching time spent
**Automation Hint:** Playwright — navigate in/out, intercept `/api/track`, assert both events fire with correct `tool` name
**Source:** Part185

### TC-P9-075
**Category:** Feature
**Test Name:** query_run fires with success:false and duration on query failure
**Steps:**
1. Trigger a Text-to-SQL query that errors
**Expected Result:** A `query_run` event fires with `success: false` and a `duration_ms` field — previously only successes were tracked
**Automation Hint:** Mock a query error, intercept `/api/track`, assert `meta.success === false`
**Source:** Part185

### TC-P9-076
**Category:** Feature
**Test Name:** AI provider usage breakdown reflects real query_run provider meta
**Steps:**
1. Run queries via Groq, Gemini, and Cohere providers
**Expected Result:** Provider Usage bar chart shows correct counts per provider, always visible even with only one provider used
**Automation Hint:** pytest — seed events with varying `meta.provider`, assert stats API groups counts correctly
**Source:** Part188

### TC-P9-077
**Category:** Feature
**Test Name:** Error events are tracked from SQL, Ensemble, and Drift failure paths
**Steps:**
1. Force a query error in Text-to-SQL, an analyze/train error in Ensemble, and a detection error in Drift
**Expected Result:** Each fires an `error` event with the correct `tool` and `error_type` in meta
**Automation Hint:** Mock each failure path, intercept `/api/track`, assert 3 distinct error events with correct meta
**Source:** Part188

---

## Analytics — index.html Split & HF Space Tracking

---

### TC-P9-078
**Category:** Bug-Regression
**Test Name:** fetchWithRetry does not retry on HTTP error status, only on network failure
**Steps:**
1. Mock a `500` HTTP response (not a network error)
2. Mock a network-level connection failure
**Expected Result:** The 500 response is returned immediately to the caller (no retry loop); the network failure triggers the retry-with-backoff loop
**Automation Hint:** pytest/unit — call `fetchWithRetry` with each mock, assert retry count is 0 for the 500 case and >0 for the network failure case
**Source:** Part189

### TC-P9-079
**Category:** E2E
**Test Name:** Splitting index.html into 3 files preserves all existing URLs
**Steps:**
1. Visit `/`, `/?mode=eda`, `/?mode=vision` on the HF Space
**Expected Result:** Each URL serves the correct app (ML Unified / EDA / Vision) with no broken links from the portfolio
**Automation Hint:** Playwright — navigate to each URL, assert the correct app's distinguishing UI element is present
**Source:** Part190, Part191

### TC-P9-080
**Category:** Feature
**Test Name:** EDA and Vision pages load without waiting on /models
**Steps:**
1. Visit `/?mode=eda` and `/?mode=vision` with a cold backend
**Expected Result:** Both apps render their UI immediately (`init()` calls `selectEDA()`/`selectVision()` directly, no `/models` fetch dependency)
**Automation Hint:** Mock `/models` as slow/hanging, assert EDA/Vision UI still renders promptly
**Source:** Part190
**Note:** Verifier — split was PLANNED in Part190, implemented in Part191; TC targets the implemented behavior.

### TC-P9-081
**Category:** Bug-Regression
**Test Name:** Sidebar tool buttons present on eda.html and vision.html after split
**Steps:**
1. Load `/?mode=eda`
2. Load `/?mode=vision`
**Expected Result:** Left sidebar shows the correct tool buttons for each page (EDA Explorer/Clean & Export for EDA; Classifier/Processing/Detection/Segmentation for Vision) — not missing after the file split
**Automation Hint:** Playwright — assert sidebar button elements exist and are clickable on both pages
**Source:** Part191

### TC-P9-082
**Category:** Bug-Regression
**Test Name:** /api/track accepts cross-origin POST from the HF Space domain
**Steps:**
1. Send an `OPTIONS` preflight to `/api/track` from a different origin
2. Send the actual `POST`
**Expected Result:** `OPTIONS` returns 204 with CORS headers; `POST` succeeds and is not silently dropped
**Automation Hint:** pytest — call the route with `Origin` header set to the HF Space domain, assert 204/200 with `Access-Control-Allow-Origin`
**Source:** Part191

### TC-P9-083
**Category:** Bug-Regression
**Test Name:** HF Space Docker build does not crash on missing aiofiles dependency
**Steps:**
1. Build the Docker image after adding a `StaticFiles` mount
**Expected Result:** Build succeeds; `aiofiles` is present in `requirements.txt`
**Automation Hint:** CI — assert `aiofiles` appears in `requirements.txt` (regression guard for the exact dependency name)
**Source:** Part191

### TC-P9-084
**Category:** Feature
**Test Name:** HF Space Tools dashboard section shows per-app event breakdown
**Steps:**
1. Generate events from ML Unified, EDA, and Vision apps
2. Load the analytics dashboard
**Expected Result:** A 3-column (or stacked) section shows each app's total event count and a per-action mini bar chart; falls back to "No HF Space activity" when empty
**Automation Hint:** pytest — seed events with `meta.tool` in {ml-unified, eda, vision}, assert stats API groups them correctly
**Source:** Part191

### TC-P9-085
**Category:** Bug-Regression
**Test Name:** _track() path field shows clean route, not raw query string
**Steps:**
1. Trigger a tracked event from the EDA app
2. Trigger one from the Vision app
**Expected Result:** Tracked `path` shows `/eda` and `/vision` respectively, not `/?mode=eda`/`/?mode=vision`
**Automation Hint:** pytest — assert the `_track()` path builder maps `APP_MODE` to a clean route string
**Source:** Part192

### TC-P9-086
**Category:** Bug-Regression
**Test Name:** Vision model cache directory is writable in the HF Docker container
**Steps:**
1. Start the container as the non-root `appuser`
2. Trigger a vision model download
**Expected Result:** No `PermissionError`; cache writes succeed under `/tmp/vision_cache`
**Automation Hint:** pytest — assert `VISION_CACHE_DIR` resolves to a path under `/tmp`, not `/app`
**Source:** Part192

### TC-P9-087
**Category:** Bug-Regression
**Test Name:** Vision model download has a timeout and doesn't hang indefinitely
**Steps:**
1. Simulate a stalled download connection
**Expected Result:** Download fails after 120s with a clear error, does not hang for 8-11 minutes
**Automation Hint:** pytest — mock a stalled `httpx.stream`, assert `download_model()` raises within the timeout window
**Source:** Part192

### TC-P9-088
**Category:** Bug-Regression
**Test Name:** ONNX session loads with basic optimization, not full graph optimization
**Steps:**
1. Load a vision ONNX model
2. Measure session creation time
**Expected Result:** Session loads in seconds, not minutes — `ORT_ENABLE_BASIC` is used, not `ORT_ENABLE_ALL`
**Automation Hint:** pytest — assert `ort_session()` sets `graph_optimization_level == ORT_ENABLE_BASIC`
**Source:** Part192

### TC-P9-089
**Category:** Bug-Regression
**Test Name:** Vision detection/segmentation progress bar renders during processing
**Steps:**
1. Upload an image for object detection
**Expected Result:** A progress bar updates during processing (SSE helpers present in `common.js`), not just a static "Detecting..." spinner
**Automation Hint:** Playwright — assert progress bar element exists and its width/text updates over time
**Source:** Part192

### TC-P9-090
**Category:** Feature
**Test Name:** Optuna tool tracks upload, run start, run complete, and error events
**Steps:**
1. Upload a CSV in Optuna, start a study, let it complete
2. Force a study failure separately
**Expected Result:** 4 distinct tracked events fire in order: `tool_open` (upload), `query_run` (start), `query_run` (complete with winner/metric), `error` (failure case)
**Automation Hint:** Playwright — intercept `/api/track` across the flow, assert event sequence and meta fields
**Source:** Part192

---

## Real-Time Analytics — Design Language, Portfolio Tools, AI Explain

---

### TC-P9-091
**Category:** Feature
**Test Name:** Portfolio Tools section aggregates events for all 9 portfolio tools
**Steps:**
1. Generate `tool_open`/`query_run` events across automl, preprocessing, feature-engineering, feature-selection, optuna, shap, drift, ensemble, text-to-sql
**Expected Result:** Dashboard's Portfolio Tools section shows a card per tool with correct event counts, "other" actions filtered from the breakdown
**Automation Hint:** pytest — seed events per tool, assert stats API's `portfolioTools` aggregation matches expected counts
**Source:** Part193

### TC-P9-092
**Category:** UI
**Test Name:** TOP badge appears on the tool/app with the most events
**Steps:**
1. Seed HF Tools and Portfolio Tools data with one clear leader in each
**Expected Result:** The leading tool card in each section shows a "TOP" badge; others do not
**Automation Hint:** pytest/unit — feed counts into the top-tool selector, assert only the max-count tool is flagged
**Source:** Part194

### TC-P9-093
**Category:** Bug-Regression
**Test Name:** Device donut chart handles a single-device dataset without breaking
**Steps:**
1. Seed only desktop page_view events (single category)
2. Load the "Visitors by Device" section
**Expected Result:** Renders a simple chip row, not a broken/invisible SVG arc (100% single-segment donuts break arc math)
**Automation Hint:** pytest/unit — feed single-category data into the donut renderer, assert it switches to chip-row mode
**Source:** Part194

### TC-P9-094
**Category:** Feature
**Test Name:** AI Explain panel only generates on manual trigger, not automatically
**Steps:**
1. Load the analytics dashboard
2. Click "AI Explain" / "Generate Explanation"
**Expected Result:** No LLM call happens on load; clicking triggers `POST /api/ai-explain` and renders a formatted explanation with a Regenerate option
**Automation Hint:** Playwright — assert no `/api/ai-explain` call before the click; assert one call after
**Source:** Part194

### TC-P9-095
**Category:** Feature
**Test Name:** AI Explain provider cascades Anthropic → Gemini → Groq
**Steps:**
1. Disable the Anthropic key, trigger AI Explain
2. Disable Anthropic and Gemini keys, trigger AI Explain
**Expected Result:** First case falls back to Gemini; second case falls back to Groq; explanation still generated either way
**Automation Hint:** pytest — mock missing keys in sequence, assert the correct fallback provider is called
**Source:** Part194

### TC-P9-096
**Category:** Feature
**Test Name:** Generate Report downloads a markdown file with real dashboard data
**Steps:**
1. Click "Generate Report" on the summary card
**Expected Result:** A `.md` file downloads containing a summary table, funnel, top pages, HF/portfolio tool breakdowns, AI model usage, and top countries matching the current range
**Automation Hint:** pytest/unit — call `generateMarkdownReport(stats, rangeLabel)`, assert all expected sections appear in the output string
**Source:** Part194

### TC-P9-097
**Category:** UI
**Test Name:** Friendly tool names shown instead of raw paths across Top Pages, Live Feed, and Summary Card
**Steps:**
1. Generate events for `/tools/text-to-sql` and `/eda`
2. View Top Pages bar, Live Feed, and Summary Card's "Top Page" row
**Expected Result:** All three show a human-readable label (e.g. "Text → SQL", "EDA"), not the raw path string
**Automation Hint:** pytest/unit — call `pathLabel()` on each known path, assert expected friendly names
**Source:** Part195

---

## Document Intelligence — Extraction, Bounding Boxes, Validation

---

### TC-P9-098
**Category:** Feature
**Test Name:** Digital PDF extraction uses text layer, scanned PDF falls back to vision
**Steps:**
1. Upload a digital (text-layer) PDF
2. Upload a scanned image-only PDF
**Expected Result:** Digital PDF uses PyMuPDF4LLM text extraction; scanned PDF routes to Vision-based extraction; both return extracted fields
**Automation Hint:** pytest — call `/document/analyze` with each PDF type, assert the correct extraction path is taken (mock/spy on each function)
**Source:** Part196

### TC-P9-099
**Category:** Feature
**Test Name:** All 8 document types have distinct field schemas
**Steps:**
1. `GET /document/types`
**Expected Result:** Response lists Invoice, Receipt, Contract, Resume/CV, Medical Report, Bank Statement, ID Card, Purchase Order, each with its own field schema
**Automation Hint:** pytest — assert 8 distinct type entries, each with a non-empty, type-specific field list
**Source:** Part196

### TC-P9-100
**Category:** Bug-Regression
**Test Name:** Root page background does not block the constellation canvas
**Steps:**
1. Load `/tools/realtime-analytics` and `/tools/text-to-sql`
**Expected Result:** Constellation dot/line background is visible behind cards, not hidden by a solid opaque root background
**Automation Hint:** Playwright — sample a pixel behind a translucent card, assert it's not the flat opaque root color
**Source:** Part196

### TC-P9-101
**Category:** UI
**Test Name:** Scanning line animation plays during document processing
**Steps:**
1. Upload a document, observe the preview panel during processing
**Expected Result:** A cyan gradient bar sweeps top-to-bottom on the document preview while extraction is in progress
**Automation Hint:** Playwright — assert the scan-line element has the `scanLine` animation applied while `processing === true`
**Source:** Part196

### TC-P9-102
**Category:** Feature
**Test Name:** Extracted fields stream in one-by-one via SSE with staggered animation
**Steps:**
1. Upload a document and watch the fields panel
**Expected Result:** Fields appear individually over time (not all at once), each with a fade+slide pop-in
**Automation Hint:** Playwright — assert field DOM nodes appear at increasing timestamps, not simultaneously
**Source:** Part196

### TC-P9-103
**Category:** Feature
**Test Name:** Confidence rings color-code by threshold and show a percentage
**Steps:**
1. Extract fields with confidence values above 0.9, between 0.7-0.9, and below 0.7
**Expected Result:** Rings render green, amber, and red respectively; each ring's text shows a "%" suffix (e.g. "90%")
**Automation Hint:** pytest/unit — feed each confidence value into the ring color selector, assert correct color band
**Source:** Part196, Part197

### TC-P9-104
**Category:** Bug-Regression
**Test Name:** Resume extraction captures work experience, projects, and certifications, not just contact fields
**Steps:**
1. Upload a multi-page resume PDF
**Expected Result:** Extracted fields include work_experience, projects, certifications, achievements — not limited to the original 9 contact-only fields
**Automation Hint:** pytest — call the resume schema/extraction with a sample resume, assert expanded field set is present
**Source:** Part197

### TC-P9-105
**Category:** Bug-Regression
**Test Name:** Text extraction covers the full multi-page document, not just page 1
**Steps:**
1. Upload a 3+ page PDF with distinct content per page
**Expected Result:** Extracted text includes content from all pages up to the 10000-character limit, not truncated at page 1
**Automation Hint:** pytest — assert extracted text length/content spans beyond what page 1 alone would produce
**Source:** Part197

### TC-P9-106
**Category:** Feature
**Test Name:** Dynamic section extraction captures arbitrary document headers beyond the predefined schema
**Steps:**
1. Upload a resume with a section header not in the predefined schema (e.g. "Volunteer Work")
**Expected Result:** The extra section is captured as a dynamic field using the LLM-provided label
**Automation Hint:** pytest — feed a document with a novel header through `_normalize_fields`, assert it's retained as an extra field
**Source:** Part197

### TC-P9-107
**Category:** Bug-Regression
**Test Name:** Visual (image-embedded) content extraction sends one page per Vision API call
**Steps:**
1. Upload a resume with a graphical career timeline spanning multiple pages
**Expected Result:** Each page is sent as a separate Vision API call (not all pages bundled into one oversized request)
**Automation Hint:** pytest — mock the Vision API, assert it's called once per page, not once total with all images
**Source:** Part197

### TC-P9-108
**Category:** Bug-Regression
**Test Name:** All extracted pages appear in the document preview, not just page 1
**Steps:**
1. Upload a multi-page document
**Expected Result:** Preview panel shows every page stacked vertically with page-number badges, scrollable
**Automation Hint:** Playwright — assert the number of rendered page-image elements matches the document's actual page count
**Source:** Part197

### TC-P9-109
**Category:** Bug-Regression
**Test Name:** SSE stream correctly buffers large base64 image events split across TCP chunks
**Steps:**
1. Upload a document whose `done` event payload (with embedded page images) exceeds a single stream read
**Expected Result:** The document preview populates correctly — no silent JSON parse failure from a truncated line
**Automation Hint:** pytest — simulate a chunked SSE response split mid-JSON, assert the client correctly reassembles it before parsing
**Source:** Part197

### TC-P9-110
**Category:** Bug-Regression
**Test Name:** Null-string field values ("null", "none", "n/a") are treated as empty, not real data
**Steps:**
1. Have the text-extraction LLM return `"career_timeline": "null"` as a string
2. Run visual extraction for the same field
**Expected Result:** The literal string "null" does not block the visual extraction merge — visual data still overwrites it
**Automation Hint:** pytest/unit — feed `"null"` through `_normalize_fields`, assert it's treated as empty/falsy, not truthy
**Source:** Part198

### TC-P9-111
**Category:** Bug-Regression
**Test Name:** Visual extraction is told which specific fields are still missing
**Steps:**
1. Extract a document where text extraction found 8/10 fields
2. Run visual extraction
**Expected Result:** The visual prompt explicitly names the 2 missing fields as priority targets, not a generic "extract everything" prompt
**Automation Hint:** pytest — assert `_visual_prompt` includes the `missing_names` list passed to it
**Source:** Part198

### TC-P9-112
**Category:** Bug-Regression
**Test Name:** Vision extraction runs off the async event loop
**Steps:**
1. Trigger a document analysis that requires visual extraction
2. Measure whether other concurrent requests are blocked during vision processing
**Expected Result:** Vision extraction runs in a thread pool executor — other API requests are not blocked while it runs
**Automation Hint:** pytest/async — assert `extract_visual_sections` is dispatched via `run_in_executor`, not called directly in the async generator
**Source:** Part198

### TC-P9-113
**Category:** Bug-Regression
**Test Name:** Visual extraction retries on 429 rate limit with backoff, and falls back providers on exhaustion
**Steps:**
1. Mock repeated 429 responses from the primary vision provider
**Expected Result:** Retries occur with increasing backoff (5s/10s/15s); after continued failure, falls back to the secondary provider (Groq Vision primary, Gemini fallback per final config)
**Automation Hint:** pytest — mock 429s then a success on fallback, assert retry count and final provider used
**Source:** Part198

### TC-P9-114
**Category:** Feature
**Test Name:** Document export supports JSON, CSV, and Excel formats
**Steps:**
1. Extract a document, use the export dropdown for each format
**Expected Result:** JSON includes document_type/exported_at/field_count plus per-field label+confidence; CSV has Field Name/Label/Value/Confidence% columns; Excel opens natively (SpreadsheetML XML)
**Automation Hint:** Playwright — trigger each export, parse/open the downloaded file, assert expected structure per format
**Source:** Part198

### TC-P9-115
**Category:** Feature
**Test Name:** Table extraction produces clean line-item data for invoices/statements
**Steps:**
1. Upload an invoice PDF containing a bordered line-item table
**Expected Result:** `extract_tables_markdown()` produces a markdown pipe-table appended to the document text; extracted line items are structured, not flattened noise
**Automation Hint:** pytest — call `extract_tables_markdown()` on a known table-containing PDF, assert markdown table structure in output
**Source:** Part198

### TC-P9-116
**Category:** Feature
**Test Name:** Agentic self-correction flags invoice arithmetic mismatches
**Steps:**
1. Extract an invoice where `total ≠ subtotal + tax`
**Expected Result:** Both `subtotal` and `total` fields get a "Flagged" validation badge with a note describing the discrepancy
**Automation Hint:** pytest — call `validate_and_correct()` with a mismatched subtotal/tax/total, assert both fields flagged
**Source:** Part199

### TC-P9-117
**Category:** Feature
**Test Name:** Rule-based validation flags malformed dates, emails, and low-confidence fields
**Steps:**
1. Extract a document with an invalid date format, a malformed email, and a field with confidence < 0.55
**Expected Result:** Each gets an appropriate validation status: date/email format issues flagged, low-confidence fields marked `low_confidence`
**Automation Hint:** pytest/unit — run Pass 1 rule checks against crafted bad values, assert correct validation status per field
**Source:** Part199

### TC-P9-118
**Category:** Feature
**Test Name:** LLM consistency pass can correct a field value in-place
**Steps:**
1. Extract a document with a cross-field inconsistency an LLM pass would catch (e.g. swapped name/company fields)
**Expected Result:** The corrected value is applied before streaming to the frontend; field shows a "Corrected" badge with an explanatory note
**Automation Hint:** pytest — mock the LLM consistency response with a correction, assert the field's final value matches the correction
**Source:** Part199

### TC-P9-119
**Category:** UI
**Test Name:** Validation badges render with correct icon/color per status
**Steps:**
1. Extract a document producing at least one flagged, one corrected, and one low-confidence field
**Expected Result:** Flagged = amber pill + triangle icon; Corrected = indigo pill + star icon; Low confidence = red pill + circle icon; hovering shows the note as a tooltip
**Automation Hint:** Playwright — assert each badge's class/color and tooltip content matches its validation status
**Source:** Part199

### TC-P9-120
**Category:** UI
**Test Name:** Footer shows "N need review" count when non-OK fields exist
**Steps:**
1. Extract a document with 2 flagged fields and the rest OK
**Expected Result:** Footer shows "2 need review" in amber; footer is absent or shows nothing when all fields are OK
**Automation Hint:** Playwright — assert footer text matches the count of non-"ok" validation statuses
**Source:** Part199

### TC-P9-121
**Category:** Bug-Regression
**Test Name:** Bounding box search finds reformatted/combined LLM values via delimiter and word-level fallback
**Steps:**
1. Extract a field where the LLM combines PDF text differently than it appears verbatim (e.g. "Bank: X | Account: Y" → "X, Account: Y")
**Expected Result:** A bounding box is still found via the delimiter-split or word-level fallback tiers, not just exact substring match
**Automation Hint:** pytest — call `search_bbox_in_doc()` with a reformatted value against a PDF containing the original text, assert a bbox is returned
**Source:** Part199

### TC-P9-122
**Category:** Bug-Regression
**Test Name:** Single-character tokens are not incorrectly filtered from bbox word-fallback
**Steps:**
1. Search for bbox of a value like "Widget A" where "A" is a single character
**Expected Result:** "A" is retained in the fallback word search, not dropped as noise — full label found, not a truncated "Widget"
**Automation Hint:** pytest/unit — call `_tier4_keep` style filter on `"A"`, assert it's not excluded solely for length 1 when it's alphabetic
**Source:** Part199

### TC-P9-123
**Category:** Bug-Regression
**Test Name:** Bounding box for table/array fields (e.g. line items) covers the full row, not just the description column
**Steps:**
1. Extract an invoice's line-items field
**Expected Result:** The bounding box spans description through amount columns (uses `find_tables()` layout detection or a wide fallback), not a narrow box covering only text words
**Automation Hint:** pytest — assert bbox width for a table-array field is above a reasonable page-width threshold (e.g. >15%)
**Source:** Part200

### TC-P9-124
**Category:** Bug-Regression
**Test Name:** Bounding box for long numeric identifiers (e.g. account numbers) is not dropped as noise
**Steps:**
1. Extract a bank statement's account number field (e.g. "12345678")
**Expected Result:** The long digit string is included in the bbox search candidates, not excluded by an overly aggressive "numeric noise" filter
**Automation Hint:** pytest/unit — call the keep-filter on `"12345678"`, assert it's retained (only short integers ≤4 chars are excluded)
**Source:** Part200

### TC-P9-125
**Category:** Bug-Regression
**Test Name:** Groq rate-limit exhaustion surfaces a real error, not a silently empty result
**Steps:**
1. Exhaust the Groq daily token quota
2. Attempt a document extraction
**Expected Result:** A clear rate-limit error is surfaced (via a debug path or user-facing message), not swallowed into an empty `""` return that looks like a code bug
**Automation Hint:** pytest — mock a 429 from Groq without a blanket try/except, assert the raw error message is captured for logging/diagnosis
**Source:** Part200

### TC-P9-126
**Category:** Bug-Regression
**Test Name:** Analyze step in the processing rail turns green (done) when extraction completes
**Steps:**
1. Run a full document analysis end-to-end
**Expected Result:** All 4 steps (Extract, Classify, Analyze, Validate) show a completed/green state — Analyze doesn't stay stuck at the pending (○) state
**Automation Hint:** Playwright — assert the "analyze" step element reaches the "done" visual state after the SSE stream completes
**Source:** Part200

---

## Backend / CI

---

### TC-P9-127
**Category:** Architecture
**Test Name:** CI installs the same ML package versions the pickled models were trained with
**Steps:**
1. Run the CI pipeline
2. Load a pickled model (e.g. titanic) inside the CI environment
**Expected Result:** Model loads without a `No module named '_loss'`-style version-mismatch error — `scikit-learn`, `pandas`, `numpy`, etc. versions in `requirements.txt` match those used to pickle the models
**Automation Hint:** pytest — assert `sklearn.__version__` in CI matches the pinned version in `requirements.txt`
**Source:** Part198

### TC-P9-128
**Category:** Architecture
**Test Name:** Vision routes are merged into ml-unified without requiring a separate HF Space
**Steps:**
1. Call `/classify-image`, `/detect-objects`, `/segment-image` against the `wram1708/ml-unified` Space
**Expected Result:** All three endpoints respond correctly from the single merged Space — no dependency on a nonexistent `wram1708/ml-vision` Space
**Automation Hint:** pytest — hit each vision endpoint against the ml-unified base URL, assert 200 responses
**Source:** Part191

---

## Pending Test Cases (carried forward, unbuilt at time of writing)

These reflect backlog items still open at the end of Part 200 — write TCs once built:

| Item | Notes |
|------|-------|
| Result pinning (Text-to-SQL) | Deferred since Part 176 — pin a result value into the next question |
| LLM Fine-tuning Pipeline | Not started — needs GPU/paid tier |
| Time Series Forecasting | Not started |
| Multimodal RAG | Not started (built much later, has its own TC coverage gap too) |
| Temperature=0 for Groq extraction | Reduce field non-determinism in Document Intelligence |
| Career timeline extraction verification | Left unverified after Groq Vision switch (Part199-200) |
| Session trace UI Option A vs B decision | User never chose between side-drawer and full-width mockups before drawer was built directly in Part186 — confirm which shipped matches an actual decision, not a default |

---

## Coverage Note

Parts 158–172 (15 sessions) have **no session logs at all** in `Conversations/` — this is a gap in the logging practice itself, not just in test-case coverage. If those logs exist elsewhere or can be reconstructed from git history (`git log` between the relevant dates), test cases for that range should be added as a follow-up. Parts 201–249 remain uncovered and are the next range for a future TC-P10 round.
