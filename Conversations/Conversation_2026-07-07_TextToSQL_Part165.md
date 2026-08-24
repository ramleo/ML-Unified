# Conversation — Part 165
**Date:** 2026-07-07  
**Topics:** Text-to-SQL — Schema ERD Diagram, CSV/JSON Export, Responsiveness Fixes  
**Commits (ml-portfolio):** `6f57094` · `ca0f1b8` · `b5edfa5` · `f3fb4b9` · `48322a0`

---

## Summary

Five features/fixes shipped across two files (`SchemaDiagram.tsx` new, `TextToSqlRunner.tsx`, `QueryResultPanel.tsx`). No backend changes — all frontend.

---

## Feature 1 — Interactive Schema ERD Diagram

**New file:** `src/app/tools/text-to-sql/SchemaDiagram.tsx` (318 lines)  
**Commit:** `6f57094`

Full-screen SVG ERD viewer triggered from the schema panel sidebar.

| Feature | Detail |
|---|---|
| **Auto-layout** | Tables placed in 4-column grid on open |
| **Table cards** | Draggable via pointer capture; each gets a unique color from 12-color palette; left color bar |
| **Columns** | PK = gold key icon, FK = indigo link icon, alternating row tint, type abbreviation right-aligned |
| **FK lines** | Bezier curves from FK column row to PK column row in referenced table |
| **Click-to-select** | Click table to highlight it + connected tables; unrelated tables + lines dim to 18% opacity |
| **Pan** | Drag SVG background |
| **Zoom** | Scroll wheel (0.18×–2.5×) |
| **Reset** | Snaps all tables back to auto-layout, clears selection |
| **Dot-grid** | Subtle dot pattern background |
| **Legend** | PK / FK / relationship line icons in footer |

**Why no backend changes:** `schema_to_dict()` already returns `foreign_keys` per table (`_schema.py` line 380). Only needed to add `foreign_keys?` to the TypeScript `SchemaTable` interface.

---

## Feature 2 — CSV / JSON Export

**File:** `src/app/tools/text-to-sql/QueryResultPanel.tsx`  
**Commit:** `ca0f1b8`

Two buttons added to the Results panel header (right-aligned, appear as soon as any query returns rows):

- **CSV** — RFC 4180 compliant escaping (commas, quotes, newlines in cell values handled). Null → empty string. Downloads as `results.csv`.
- **JSON** — Array of objects keyed by column name. Downloads as `results.json`.

Entirely client-side — no backend involved. Helpers:
```tsx
function csvEscape(v: unknown): string { ... }   // RFC 4180
function downloadFile(content, name, mime) { ... } // Blob + <a> click
```

---

## Fix 1 — Auto-load Chinook Schema on Mount

**File:** `src/app/tools/text-to-sql/TextToSqlRunner.tsx`  
**Commit:** `b5edfa5`

Before: schema was `null` until the user clicked "Load Schema" in `DbConnectPanel`. The "View Diagram" button (`{schema && ...}`) was therefore invisible on first load.

Fix: one `useEffect` placed after `loadDemoSchema` is defined:
```tsx
useEffect(() => { loadDemoSchema(); }, [loadDemoSchema]);
```

Schema panel and diagram button now appear immediately when the page loads.

---

## Fix 2 — "View Diagram" Button Visibility

**File:** `src/app/tools/text-to-sql/TextToSqlRunner.tsx`  
**Commit:** `f3fb4b9`

Original trigger was a 13×13px gray SVG icon in the schema panel header — easy to miss and only on desktop (sidebar is `hidden lg:flex`).

Replaced with a full-width labeled "View Diagram" button below the Schema heading in the sidebar.

---

## Fix 3 — Arrowheads Visible + Mobile Access

**Files:** `SchemaDiagram.tsx`, `TextToSqlRunner.tsx`  
**Commit:** `48322a0`  
**Verified with Playwright** (desktop 1440px + mobile 390px)

### Arrowheads hidden (root cause)

SVG renders in painter's order: edges first, table cards on top. SVG `<marker>` arrowheads at the path endpoint were covered by the table card `<rect>` rendered afterwards → invisible.

**Fix:** Split rendering into 3 passes inside the `<g>` transform group:
1. **Pass 1** — bezier paths (behind tables), no arrowheads, stroke opacity bumped `0.22 → 0.45`
2. **Pass 2** — table cards (same as before)
3. **Pass 3** — arrowhead `<polygon>` elements rendered after cards, always on top

Arrowhead geometry (polygon tip sits on card edge, pointing inward):
```tsx
const pts = fromRight
  ? `${tx},${ty} ${tx+8},${ty-5} ${tx+8},${ty+5}`   // pointing left
  : `${tx},${ty} ${tx-8},${ty-5} ${tx-8},${ty+5}`;   // pointing right
```

Also removed SVG `<marker>` definitions (no longer needed).

### Mobile responsiveness

The sidebar is `hidden lg:flex` — completely invisible below 1024px. "View Diagram" button was unreachable on mobile.

**Fix:** Added a second trigger button in the main content column with `lg:hidden` (visible only on mobile/tablet, hidden when sidebar is shown):
```tsx
{schema && (
  <button onClick={() => setDiagramOpen(true)} className="lg:hidden w-full ...">
    View Schema Diagram
  </button>
)}
```

**Playwright verification:**
- Desktop (1440px): arrowheads visible at every FK connection point
- Mobile (390px): "View Schema Diagram" button present, diagram opens with full pan/zoom/drag

---

## Pending Items (Text-to-SQL)

| Item | Notes |
|---|---|
| MSSQL support | Discussed, not implemented |
| Saved queries | Named queries beyond 20-pair few-shot |
| Schema search | Filter tables in schema panel by keyword |
| Pagination UI | Results capped at 500, no page-through |
| Mobile layout | Sidebar glossary/schema still inaccessible on mobile |
| Query sharing | Shareable URL with pre-filled question + db_ref |

## File Sizes After This Session

| File | Lines |
|---|---|
| `SchemaDiagram.tsx` (new) | 336 |
| `TextToSqlRunner.tsx` | 362 |
| `QueryResultPanel.tsx` | 193 |
