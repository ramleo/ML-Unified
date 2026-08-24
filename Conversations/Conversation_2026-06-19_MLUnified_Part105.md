# Conversation — 2026-06-19 — ML-Unified — Part 105

---

## Topics Covered

1. Feature Engineering — Categorical columns card with live distribution bars
2. Feature Engineering — Sidebar scroll fix (merged overflow:hidden wrapper)
3. Feature Engineering — 3 remaining FE techniques implemented
4. Feature Engineering — Mini SVG histograms + AI Suggest + Results distribution viz
5. Feature Engineering — Compact inline transform key

---

## 1. Categorical Columns Card — Right Panel

**Commit `1f33b8b`** — ml-portfolio — *feat(feature-engineering): categorical columns card with value distribution bars*

### Problem
- Frequency encoding section in sidebar was unclear — "Replaces each value with its share of total rows" is too abstract
- Right panel had large empty space (only numeric transforms card)
- Sidebar scroll was broken again (intermediate `overflow: hidden` div blocked mouse/trackpad events)

### Solution
- Removed Frequency Encoding + Date Extraction sections from sidebar
- Added "Categorical Columns" card to right panel showing:
  - Column name + unique count + missing count
  - Value distribution bars (computed from actual data) — bars light blue, turn cyan when Freq Encoding is on
  - `○ Freq Encoding → col_freq` chip and `○ Date Extract` chip per column
  - Date parts selector at bottom of card when any date col active
- Freq encoding is now self-evident: Sex → male 63.6% / female 36.4% visible before toggling
- Bar color: `rgba(99,153,219,0.45)` inactive → `ACCENT` active

### Sidebar scroll root cause
The inner card had `overflow: hidden` (for borderRadius clipping). This div sat between the user's scroll input and the outer `overflowY: auto` wrapper. On macOS, scroll events did not propagate through `overflow: hidden` to the scrollable ancestor.

**Fix:** Collapsed both divs into one — the outer scrollable wrapper now also carries the card styles (`background`, `border`, `borderRadius`). No intermediate element. Confirmed via Playwright: `scrollHeight (1010) > clientHeight (829)` and trackpad scroll works.

---

## 2. Three Remaining FE Techniques

**Commit `890b0de`** — ml-portfolio — *feat(feature-engineering): cyclical encoding, row aggregates, boolean > mean*

### Cyclical Encoding
- Sidebar section "Cyclical Encoding"
- Toggle per numeric column + period dropdown (7/12/24/31/52/365)
- Outputs `col_sin` + `col_cos` (sin(2π·x/period) and cos(2π·x/period))
- Sub-label shows output names when toggled on
- State: `cyclicCols: Record<string, number>` (column → period)

### Row Aggregates
- Sidebar section "Row Aggregates"
- Aggregation dropdown (mean/max/min/std/sum) + toggle list of numeric columns
- Output: `row_<fn>` (single new column, row-wise stat across selected columns)
- Live hint shows output column name when 2+ columns selected
- Warns if only 1 column selected

### Boolean > mean chip
- New chip `> mean` in NUM_TRANSFORMS
- Outputs `col_above_mean`: 1 if value > column mean, else 0
- No extra UI needed — fits naturally in the chip row

### Full technique checklist now complete:
| Technique | Status |
|---|---|
| Frequency encoding | ✅ |
| Winsorization | ✅ |
| Ratio features (A÷B) | ✅ |
| Lag/Diff | ✅ |
| Rolling Window | ✅ |
| Cyclical encoding (sin/cos) | ✅ |
| Row-wise aggregates | ✅ |
| Boolean > mean | ✅ |

---

## 3. Mini SVG Histograms + AI Suggest + Distribution Viz

**Commit `496f9ca`** — ml-portfolio — *feat(feature-engineering): mini histograms, AI Suggest, distribution viz*

### MiniHistogram component
```tsx
function MiniHistogram({ values, bins = 14, width = 66, height = 22, color = ACCENT }) {
  // bins the values, renders as SVG rect bars
  // bar height = count / maxCount * height
}
```
- Pure browser, no dependencies
- Used in configure table and results page

### Configure step changes
- Skew column expanded from 44px → 84px
- Now shows: `MiniHistogram` (66×22px, bars colored by skew severity) + `skew X.X` label below
- Bar color: orange (#f59e0b99) for |skew|>1.5, slate for >0.5, green for low skew

### ✨ AI Suggest button
- Inline in the Numeric Column Transforms card header (right side)
- Runs `aiSuggest()` callback on click
- Heuristic logic:
  - `skew > 1.5` → log1p
  - `0.5 < skew ≤ 1.5` → sqrt
  - `missing% > 2%` → missing_flag
  - `IQR outlier% > 3%` → winsor
- Clears existing selections and applies AI picks

### Results step — New Feature Distributions
- New card between "New Columns Added" and "Preview" sections
- Auto-fill grid (`minmax(160px, 1fr)`) — one tile per new column
- Each tile: column name + MiniHistogram (18 bins, 140×34px) + min/max labels
- Shows output distribution so user can visually verify transform worked

---

## 4. Compact Inline Transform Key

**Commit `404ad22`** — ml-portfolio — *feat(feature-engineering): compact inline transform key above chip table*

- Flowing inline paragraph above the chip table showing chip name (dim cyan) + description (grey) + `·` separator
- Wraps naturally with panel width, no grid whitespace
- 2-column grid version (`38afd16`) was rejected and reverted (`7ddca06`) before this

---

## 5. Commits This Session

| Hash | Repo | Description |
|---|---|---|
| `1f33b8b` | ml-portfolio | feat: categorical columns card, sidebar scroll fix |
| `890b0de` | ml-portfolio | feat: cyclical encoding, row aggregates, boolean > mean |
| `38afd16` | ml-portfolio | feat: transform legend (2-col grid — reverted) |
| `7ddca06` | ml-portfolio | revert: remove transform legend grid |
| `404ad22` | ml-portfolio | feat: compact inline transform key |
| `496f9ca` | ml-portfolio | feat: mini histograms, AI Suggest, distributions viz |

---

## 6. Pending

### Feature Engineering (ml-portfolio)
- No remaining items from the original technique list — all 8 implemented
- Potential future: one-hot encoding, target encoding, transform presets, column search

### Feature Selection (ml-portfolio)
- Auto-run on settings change (debounced ~300ms)
- Correlation pairs disclosure in drop reasons
- Live count preview on all 5 tabs
- Variance values visible in ranking table

### ML-Unified backlog
- Phase 9: Ensemble/stacking
- Phase 10: Pipeline export (.pkl / Python script)
- Fix `showAutoMLWizard()` always starting fresh (line ~4566)
- Verify AdaBoost winner-training branch exists in app.py
- Retrain 80 Cereals model
