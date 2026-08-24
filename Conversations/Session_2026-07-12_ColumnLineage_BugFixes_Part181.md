# Session: Column Lineage Graph + Bug Fixes — Part 181
**Date:** 2026-07-12
**Branch:** main
**Repos:** ml-portfolio (`src/app/tools/text-to-sql/`), ML-Unified (`services/ml-sql/`)

---

## Summary

Fixed HF Space crash, fixed upload error UX, added AI Reasoning markdown rendering, built Column Lineage Graph feature, fixed multiple parser bugs discovered via Playwright.

---

## Bug Fix — HF Space `RUNTIME_ERROR` (ml-sql)

**Root cause:** All previous ml-sql uploads were going to `wram1708/ml-unified` (wrong space). The `wram1708/ml-sql` Space was running stale code missing `count_rows_remote` (added in commit `74f94a0`). Error: `ImportError: cannot import name 'count_rows_remote' from 'routers._execute'`.

**Fix:** Re-uploaded all 11 ml-sql backend files to the correct space `wram1708/ml-sql`. Factory restart triggered a full rebuild.

**Root cause of wrong uploads:** Previous sessions used `repo_id="wram1708/ml-unified"` for ml-sql files — blindly following CLAUDE.md rule without checking which Space actually hosts ml-sql.

**Memory updated:** `feedback_hf_upload_path.md` — added CRITICAL note with the exact mistake and how to verify with Playwright health check.

**HF Space mapping (definitive):**
| Service | HF Space | Strip prefix |
|---------|----------|--------------|
| ml-api | `wram1708/ml-unified` | `services/ml-api/` |
| ml-sql | `wram1708/ml-sql` | `services/ml-sql/` |

---

## Bug Fix — Upload Error UX (`5d349ee`)

**Problem:** HF Space returns plain text `"Your space is warming up..."` when cold. `res.json()` threw `SyntaxError: Unexpected token 'Y'...` shown to user.

**Fix:** Read response as text first, then try JSON parse. If parse fails → show `"Backend is waking up — wait ~15s and try again"`. Applied to both `uploadDb` and `connectRemote` in `TextToSqlRunner.tsx`.

---

## Fix — AI Reasoning Markdown Rendering (`9ed3cab`)

**Problem:** Reasoning panel showed raw `**bold**` and `* bullet` syntax as plain text.

**Fix:** Added `renderMd()` function in `ReasoningPanel.tsx` — splits on newlines, converts `**text**` to `<strong>`, handles sub-bullet indentation.

---

## Feature — Column Lineage Graph (`da57b7a` + fixes)

Shows a violet SVG DAG mapping source table.columns → output column names. Pure frontend, no backend call, no new dependencies. Appears between AI Reasoning and Auto-Insights panels, collapsed by default.

### Design
- Left nodes: source columns (colored by table)
- Right nodes: output column names
- Bezier curves connecting them
- Click header to expand/collapse
- Shows `N sources → N outputs` in header
- Table color legend below the graph
- Returns `null` (hidden) if no lineage detected

### SQL Parser — `parseLineage()`

Handles:
- Qualified refs: `ar.Name` → `{table: Artist, column: Name}`
- Bare refs: `Name` (no alias)
- Aliased: `ar.Name AS Artist` → output = `Artist`
- Functions: `COUNT(DISTINCT Title) AS album_count` → output = `album_count`, source = `Title`
- Quoted identifiers: `"Name"` → stripped to `Name`
- Multiline SQL: `\nFROM` (all whitespace before FROM, not just space)
- All SQL dialects (no backend needed)

### Bugs Fixed During Development

| Commit | Bug | Fix |
|--------|-----|-----|
| `4f30091` | `\nFROM` not detected — parser returned `[]` | Changed FROM detection to check `\s` (any whitespace) before FROM, not just space |
| `91fb057` | Top nodes clipped at SVG edge | `PAD 14 → 24` so first node rect starts at y=2 not y=-3 |
| `91fb057` | Font too large in nodes | `9px → 7px` column names, `6px → 5.5px` table labels |
| `91fb057` | `?` and `count` output names | Replaced `$`-anchored regex with right-to-left depth-aware `extractAlias()` |
| `c476029` | `"Name"` → `?` | Strip `"`, `'`, `` ` `` from identifiers before parsing |
| `c476029` | `COUNT(DISTINCT "Title")` → `count` | Extract bare column from function body after removing DISTINCT |

### Playwright Debug Session

Used Playwright to open the live app, run "Show me top 5 artists by total album count", and read the actual generated SQL via `document.querySelector('pre').innerText`. Discovered LLM generated `"Name"` (quoted identifiers) not `ar.Name` style, which exposed the quote-stripping bug.

Actual SQL that exposed the bug:
```sql
SELECT "Name", COUNT(DISTINCT "Title") AS album_count 
FROM Artist 
JOIN Album ON Artist.ArtistId = Album.ArtistId 
GROUP BY "Name" 
ORDER BY album_count DESC 
LIMIT 5
```

---

## Commits

| Hash | Repo | Description |
|------|------|-------------|
| `5d349ee` | ml-portfolio | fix(sql): friendly "backend waking up" message on HF cold start |
| `9ed3cab` | ml-portfolio | fix(sql): render AI reasoning as markdown |
| `da57b7a` | ml-portfolio | feat(sql): Column Lineage Graph — SVG DAG |
| `4f30091` | ml-portfolio | fix(sql): lineage parser — handle newlines before FROM |
| `91fb057` | ml-portfolio | fix(sql): lineage — top clipping, font size, alias extraction |
| `904d4d4` | ml-portfolio | fix(sql): lineage — right-to-left alias extractor + smaller font |
| `c476029` | ml-portfolio | fix(sql): lineage — strip quoted identifiers, extract bare cols from function args |

---

## File Sizes (end of session)

| File | Lines |
|------|-------|
| `ColumnLineageGraph.tsx` | ~170 (new) |
| `QueryResultPanel.tsx` | 403 |
| `ReasoningPanel.tsx` | 183 |
| `TextToSqlRunner.tsx` | 402 |

---

## Pending / Next

- **#9 Result Pinning** — pin any result tab to survive "Clear All"
- **Add Teach the AI + Column Lineage to User Guide**
- **Real-Time Analytics Dashboard** — plan in `temporal-gliding-pascal.md`, needs Supabase setup first
- **Fix `wram1708/ml-unified` Space** — ml-sql files were accidentally uploaded there; may need cleanup
