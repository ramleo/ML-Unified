# Conversation — 2026-06-19 — ML-Unified — Part 103

---

## Topics Covered

1. LFS fix for pkl files in Docker
2. Portfolio env var situation (what happens without `NEXT_PUBLIC_ML_UNIFIED_URL`)
3. Feature Engineering page — full redesign
4. Feature Selection page — improvements discussion
5. Additional FE techniques research

---

## 1. LFS Fix — pkl Files

**Problem:** `.gitattributes` had `services/ml-api/models/*.pkl filter=lfs diff=lfs merge=lfs -text`. The files in git HEAD were real binaries (not LFS pointers), but git's clean filter was converting working tree reads to LFS pointer stubs, creating spurious "modified" state and risking `COPY models/ models/` in Dockerfile copying pointer text instead of real content.

**Fix:**
- Removed LFS filter from `.gitattributes`, replaced with `-text` only (binary hint, no LFS)
- Ran `git rm --cached services/ml-api/models/*.pkl` to clear the index
- Re-staged as plain binary files
- Result: only `.gitattributes` showed as changed — pkl files re-staged identically to HEAD

**Commit:** `e8ba65d` — ML-Unified — *fix(models): remove LFS tracking from pkl files — commit as plain binaries*

**Why safe:** Files are 1.4 MB total. Plain binary commit is appropriate. `COPY models/ models/` now guaranteed to copy real pkl content on any build server.

---

## 2. Portfolio — What Happens Without the Env Var

`urls.ts` now has no fallback:
```ts
export const ML_UNIFIED_API = (process.env.NEXT_PUBLIC_ML_UNIFIED_URL ?? "").replace(/\/$/, "");
```

**If `NEXT_PUBLIC_ML_UNIFIED_URL` is not set on Vercel:**
- `ML_UNIFIED_API` = empty string `""`
- Launch App buttons open `""/?mode=ml` = current page with `?mode=ml` query — broken
- AutoML/SHAP/Optuna API calls fail

**Unaffected:** Feature Engineering, Preprocessing, Feature Selection — all client-side, no backend calls.

**Fix needed:** Set `NEXT_PUBLIC_ML_UNIFIED_URL` in Vercel environment variables to the backend URL, and create `.env.local` for local dev.

---

## 3. Upload Icon Centering Fix

**Problem:** Upload SVG in Feature Engineering drop zone was left-aligned. Parent used `textAlign: "center"` which doesn't center SVGs (inline elements).

**Fix:** Added `display: "block"` and `margin: "0 auto 1rem"` to the SVG style.

**Commit:** `8eb22c5` — ml-portfolio — *fix(feature-engineering): center upload icon in drop zone*

---

## 4. Feature Engineering — Full Redesign

### What was wrong with the original
- Wide `<table>` with 7 checkbox columns — last column ("Bin (Quantile)") cut off
- Horizontal scrollbar visible
- 4 separate floating CARD divs in left panel with 1rem gap between each
- `maxWidth: 1060` centered — on wide screens, large blank space on both sides
- No "Select All" per transform type
- Missing z-score and min-max transforms
- No data preview in results

### Changes implemented

**Commit `f62e29f`** — *feat(feature-engineering): elegant pill-chip transforms, unified sidebar, data preview*

#### Numeric Column Transforms — pill chip rows
- Replaced `<table>` entirely with a flex list
- Each row: `[column name 118px] [skew badge 36px] [pill chips wrapping]`
- Chips toggle on/off — filled+glowing when active, ghost when not
- No horizontal scroll; chips wrap naturally on any viewport width
- "Apply to all" header row above — click any chip to toggle that transform for every column at once

#### New transforms added
- `z-score` → `(x − μ) / σ` — outputs `colname_zscore`
- `min-max` → `(x − min) / (max − min)` → outputs `colname_minmax`

Short chip labels: `log1p`, `sqrt`, `z-score`, `min-max`, `pct rank`, `outlier`, `missing`, `bin=`, `bin~`

#### Left panel — unified sidebar
- 4 separate CARD divs → single unified card with `borderRadius: 14` and thin `rgba` dividers between sections
- More compact section headers (`SideLabel` component, uppercase)
- Tighter internal padding
- No wasted gap between sections

#### Results step — data preview
- After applying transforms, shows first 5 rows of new columns only in a scrollable mini-table
- Values rounded to 2 decimal places

**Commit `b330320`** — *fix(feature-engineering): remove maxWidth constraint, stretch panels to full height*
- Removed `maxWidth: 1060` and `margin: "0 auto"` from configure container — panels now fill full viewport width
- Left sidebar and right card both `flex: 1` vertically — stretch to fill height, no empty background below

---

## 5. Feature Engineering — Bug Fixes

**Commit `17f906c`** — *fix(feature-engineering): align chips, increase sidebar fonts, filter date cols, round preview*

### Chip alignment fix
"Apply to all" row chips were misaligned with per-column chips. Root cause: label `width: 158` vs column rows that had `118 (name) + 0.5rem gap + 36 (skew) = ~170px` before chips. Fix: changed header row to mirror the exact column row structure:
```jsx
<span style={{ width: 118 }}>Apply to all</span>
<div style={{ width: 36, flexShrink: 0 }} />   {/* spacer matching skew column */}
<div>chips...</div>
```

### Left panel font & spacing
- `SideLabel`: `0.59rem` → `0.67rem`
- Section padding: `0.85rem 1.2rem` → `1rem 1.3rem`
- Dataset stats font: bumped up, more gap between stats
- Toggle list gap: `0.32rem` → `0.45rem`
- Dropdown font: `0.72rem` → `0.78rem`

### Date Extraction — filter to actual date columns
Previous behavior: ALL categorical columns shown (Name, Sex, Ticket, Cabin, Embarked on Titanic) — none of which are dates.

Added `isLikelyDateCol()` heuristic:
```ts
function isLikelyDateCol(rawValues: string[]): boolean {
  const nonEmpty = rawValues.filter(v => { ... });
  if (nonEmpty.length === 0) return false;
  const sample = nonEmpty.slice(0, Math.min(nonEmpty.length, 20));
  const valid = sample.filter(v => v.length >= 6 && !isNaN(new Date(v).getTime()));
  return valid.length / sample.length > 0.7;
}
```

`dateLikeCols = catCols.filter(c => isLikelyDateCol(c.rawValues))` — Date Extraction section only appears when at least one column looks like a date. On Titanic: section is hidden entirely.

### Preview rounding
Values in the first-5-rows preview now rendered as `num.toFixed(2)` — e.g. `0.69` instead of `0.6931471805599453`.

---

## 6. Commits This Session

| Hash | Repo | Description |
|---|---|---|
| `e8ba65d` | ML-Unified | fix(models): remove LFS tracking from pkl files |
| `8eb22c5` | ml-portfolio | fix(feature-engineering): center upload icon in drop zone |
| `f62e29f` | ml-portfolio | feat(feature-engineering): pill-chip transforms, unified sidebar, data preview |
| `b330320` | ml-portfolio | fix(feature-engineering): remove maxWidth, stretch panels to full height |
| `17f906c` | ml-portfolio | fix(feature-engineering): align chips, fonts, filter date cols, round preview |

---

## 7. Additional FE Techniques — Research Results

Current tool has: log1p, sqrt, z-score, min-max, pct rank, outlier flag, missing flag, bin=, bin~, date extraction, interaction terms (A×B), polynomial cross-terms.

### High-value additions (all pure client-side JS)

| Technique | What it does | Priority |
|---|---|---|
| **Frequency encoding** | Replace each category with its row proportion | High |
| **Cyclical encoding** | sin/cos pairs for periodic features (hour, month, day-of-week) | High |
| **Ratio features (A÷B)** | Division complement to A×B | High |
| **Row-wise aggregates** | Row mean/max/min/std across selected column group | Medium |
| **Winsorization** | Cap values at 1st/99th percentile | Medium |
| **Boolean comparison** | `A > threshold` or `A > B` → 0/1 flag | Medium |

### Time-series features (require sort column)

**Lag / diff features:**
- User selects sort column (timestamp, row_id) + lag N + target columns
- `col_lag_1` = value from N rows back (after sorting)
- `col_diff_1` = `col[t] - col[t-1]`
- Implementation: sort rows by sort column, shift values array by N, fill first N with null

**Rolling window aggregates:**
- User selects sort column + window size N + aggregation (mean/std/min/max)
- `col_roll3_mean` = mean of last 3 rows
- Implementation: sliding window loop, pure JS

**Caveat:** Both make sense ONLY for time-ordered data. For general tabular datasets (Titanic, Iris), the output is meaningless. Should be implemented as an optional section clearly labeled "Time-ordered data only", disabled until user selects a sort column.

---

## 8. Pending — Feature Engineering

- Frequency encoding for categoricals
- Cyclical encoding (sin/cos) for periodic numeric columns
- Ratio features (A÷B)
- Lag/diff features (time-ordered data, requires sort column)
- Rolling window aggregates (time-ordered data, requires sort column)

## 9. Pending — Feature Selection

All previously discussed improvements still pending:
- Auto-run on settings change (debounced)
- Correlation pairs disclosure in drop reasons
- Live count preview on all 5 tabs
- Variance values in ranking table
