# Conversation — Part 169
**Date:** 2026-07-08  
**Topics:** Text-to-SQL — Visual Redesign (UI Polish Pass)  
**Commits (ml-portfolio):** `32a4d2b`

---

## Context

Continuation from Part 168. All "Better use of time" features were complete (notebook export, query history, NL filter). User asked how to make the UI more visually appealing.

---

## Visual Improvements — Discussion

8 items discussed and ranked by impact:

| # | Area | What |
|---|---|---|
| 1 | Query input bar | Glowing indigo border + gradient button pulse while running |
| 2 | Animated pipeline steps | Schema → SQL → Execute → Explain steps lighting up as SSE events fire |
| 3 | SQL card syntax highlight | Keywords indigo, strings emerald, numbers amber |
| 4 | Result table polish | Alternating row shading, hover highlight |
| 5 | Chart cards | Title typography, value labels |
| 6 | Stat card animation | Count-up from 0 (already existed) |
| 7 | Query history timeline | Left-border line + timestamps |
| 8 | Schema panel badges | Colored chips per column type |

**Decision:** implement items 1–3 first (main interaction path), then user asked for full page redesign.

---

## Approach

**Playwright before/after workflow:**
1. Screenshot idle state (before)
2. Apply code changes
3. Inject mock query results via `browser_evaluate` to simulate post-query state
4. Show live in open browser window

**Lesson learned:** `querySelector('.rounded-xl.border.p-4')` grabbed `DbConnectPanel` first (same classes), causing Playwright injection to accidentally style the "Chinook Demo" tab button with a gradient. Not a code bug — only a Playwright injection artifact.

---

## Implementation — Phase 1 (items 1–3)

### New: `PipelineStatus.tsx` (88 lines)

Animated 4-stage pipeline indicator: Schema → SQL → Execute → Explain

- Done stages: indigo pill + checkmark SVG
- Active stage: brighter pill + `animate-pulse` dot + indigo ring
- Inactive stages: dim gray
- Connector lines: indigo when passed, white/10 when pending
- Retry message shown below if present

Stage detection from props:
```tsx
const active = hasExplanation ? 3 : hasResults ? 2 : hasSql ? 1 : 0;
```

### `TextToSqlRunner.tsx` (stays at 400 lines)

- Import `PipelineStatus` (+1 line), removed 1 comment to compensate
- Query card: dynamic className — glows indigo (`shadow-[0_0_24px_rgba(99,102,241,0.08)]`) when `running`
- Textarea: `focus:border-indigo-500/50 focus:shadow-[0_0_0_3px_rgba(99,102,241,0.12)] transition-all`
- Ask button: `linear-gradient(135deg, #6366f1, #8b5cf6)` instead of flat ACCENT
- Replaced `{retryMsg && <p>...</p>}` with `<PipelineStatus .../>` (1→1 net)

### `QueryResultPanel.tsx` (316 lines)

- `highlightSQL(sql)` helper: regex-based tokeniser — double-quoted identifiers → emerald, string literals → emerald, numbers → amber, SQL keywords → indigo bold
- SQL card: border changed to `border-indigo-500/20`, label changed to `text-indigo-400/80`
- Table rows: `${i % 2 === 0 ? "bg-white/[0.02]" : ""}` alternating, `hover:bg-white/[0.07] transition-colors`

---

## Implementation — Phase 2 (full page redesign)

User asked for whole-page redesign after seeing Playwright preview.

### `SchemaPanel.tsx` (51 → 100 lines)

Full rewrite:
- `typeColor(t)` → returns `{ bg, text, label }` for INT (green), NUM (amber), TXT (blue), other (gray)
- "No DB loaded" state: SVG database icon + helper text
- Tables: rendered as collapsible cards with DB cylinder SVG icon, row count chip, animated expand arrow
- Columns: type badge (PK chip in indigo, or INT/NUM/TXT colored badge) + column name
- PK columns shown in indigo, search-matched columns in amber
- Toggle state via `Set<string>` instead of `<details>` (more controllable)
- Search box with magnifier SVG icon + X clear button

### `DbConnectPanel.tsx` (106 → 128 lines)

- Each tab gets an inline SVG icon (DB cylinder, upload arrow, grid, M-shape, server lines)
- Selected tab: `linear-gradient(135deg, rgba(99,102,241,0.18), rgba(139,92,246,0.12))` background + `box-shadow: 0 0 12px rgba(99,102,241,0.15)` glow
- All action buttons: `linear-gradient(135deg, #6366f1, #8b5cf6)` gradient
- Status line: pulsing indigo dot before text
- Overall card: `bg-black/30` darker glass feel

### `TextToSqlRunner.tsx` sidebar (stays at 400 lines)

- Sidebar width: `w-52` → `w-56`
- All sidebar cards: `border-white/8 bg-black/30` (darker, glassier)
- Schema section header: SVG chevron icon instead of `▾/▸` text
- "View Diagram" button: `text-[10px]` smaller, `hover:text-indigo-300`
- Sample questions: `"Try asking"` label in `text-indigo-400/50 tracking-widest`, chips with `hover:bg-indigo-500/8 hover:text-indigo-300`, `›` accent in `text-indigo-700 group-hover:text-indigo-400`
- Glossary: SVG chevron, darker textarea, `text-gray-700` hint

### `QueryResultPanel.tsx` (325 lines)

- Error card: added SVG warning circle icon + `flex items-start gap-2.5` layout
- Explanation card: `border-indigo-500/15 bg-indigo-950/20` tinted background, SVG info icon, `text-indigo-400/70` label in `tracking-widest`

---

## File Sizes After Redesign

| File | Lines |
|---|---|
| `TextToSqlRunner.tsx` | 400 |
| `QueryResultPanel.tsx` | 325 |
| `PipelineStatus.tsx` | 88 |
| `SchemaPanel.tsx` | 100 |
| `DbConnectPanel.tsx` | 128 |

---

## Commit

**`32a4d2b`** — `feat(text-to-sql): visual redesign — pipeline steps, SQL highlight, schema badges, DB tabs`

Frontend-only changes. No backend files modified → no HF upload needed.

---

## Pending Items

| Item | Notes |
|---|---|
| QueryHistoryPanel polish | Minor — timeline already decent |
| Chart card title typography | Low priority |
| Schema panel FK indicators | Future enhancement |
