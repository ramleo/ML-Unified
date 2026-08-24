# Conversation — 2026-06-19 — ML-Unified — Part 104

---

## Topics Covered

1. Feature Engineering — new techniques added (winsor, ratio, frequency encoding, lag/diff, rolling window)
2. Feature Engineering — UI fixes (date extraction restored, + button, left panel redesign)
3. Feature Engineering — alignment and scrolling fixes
4. Feature Engineering — enhancement suggestions

---

## 1. New FE Techniques Added

**Commit `05bb4c3`** — ml-portfolio — *feat(feature-engineering): add winsor, ratio features, frequency encoding, lag/diff, rolling window*

### Winsor chip (numeric transforms)
- New chip in the per-column transform row
- Caps values at 1st/99th percentile → `colname_winsor`

### Column Combinations (left sidebar)
- **Ratio Features (A÷B)** — select two numeric columns, generates `colA_div_colB`
- Division is null-safe (div-by-zero → null)
- Uses same selector UI as interaction terms

### Frequency Encoding (left sidebar)
- Toggle per categorical column → `colname_freq`
- Replaces each category value with its proportion in the column
- e.g. Sex: male → 0.65, female → 0.35

### Time-Series Features (left sidebar)
- Select a sort column first (disabled until selected)
- **Lag / Diff**: choose N (1–10), toggle +diff option, pick numeric columns → `col_lagN`, `col_diffN`
- **Rolling Window**: choose N (2–20), aggregation (mean/std/min/max), pick columns → `col_rollN_mean` etc.
- Sort handles both numeric and string/date columns
- Sort order computed once, shared between lag and rolling sections

---

## 2. UI Fixes — Left Panel Redesign

**Commit `f085843`** — ml-portfolio — *fix(feature-engineering): merge interaction+ratio into Column Combinations, restore Date Extraction, fix + button*

### Column Combinations section
- Merged "Interaction Terms (A×B)" and "Ratio Features (A÷B)" into one section
- Each sub-row shows output column hint: `→ colA_x_colB` / `→ colA_div_colB`
- Both + buttons now use same neutral ghost style (no more mismatched cyan/purple)

### Date Extraction restored
- Removed `isLikelyDateCol()` filter — was incorrectly hiding the entire section on Titanic
- Now shows ALL categorical columns as toggle options
- Description: "Toggle columns that contain dates → extracts year, month, day etc."

### Polynomial Cross-Terms & Frequency Encoding
- Replaced chip-button selection with Toggle + column name rows (consistent with Date Extraction section)
- More informative descriptions:
  - Polynomial: "Generates every pairwise A×B product" + live count → "→ 6 new columns"
  - Frequency: "Replaces each value with its share of total rows. e.g. Sex: male → 0.65, female → 0.35"

---

## 3. Alignment and Scrolling Fixes

**Commit `3874741`** — ml-portfolio — *fix(feature-engineering): align apply-to-all chips, fix + overflow, replace poly/freq chips with toggles*
- `SELECT_STYLE` got `minWidth: 0` to allow selects to shrink and prevent + button overflow
- Apply-to-all label changed from `<span>` to `<div>` for proper width enforcement

**Commit `1afe31b`** — ml-portfolio — *fix(feature-engineering): fix sidebar scrolling, use CSS grid for pixel-perfect chip alignment*
- Sidebar scrolling: removed `flex: 1` from inner card and `display: flex / flexDirection: column` from outer wrapper — card now grows with content and outer div scrolls
- Applied CSS Grid (`gridTemplateColumns: "118px 36px 1fr"`) to transforms section — guaranteed column alignment

**Commit `31d17a3`** — ml-portfolio — *fix(feature-engineering): use HTML table for guaranteed chip column alignment, increase chip gap*
- Replaced CSS grid with HTML `<table tableLayout="fixed">` + `<colgroup>` — browser spec guarantees column width sharing between thead (Apply to all) and tbody (per-column rows)
- Chip gap increased from `0.22rem` (~3.5px) to `0.4rem` (~6.4px) for better visual separation

---

## 4. Commits This Session

| Hash | Repo | Description |
|---|---|---|
| `05bb4c3` | ml-portfolio | feat(feature-engineering): winsor, ratio, freq encoding, lag/diff, rolling window |
| `f085843` | ml-portfolio | fix(feature-engineering): Column Combinations merge, Date Extraction restored, + button |
| `3874741` | ml-portfolio | fix(feature-engineering): align chips, fix + overflow, toggles for poly/freq |
| `1afe31b` | ml-portfolio | fix(feature-engineering): sidebar scrolling, CSS grid alignment |
| `31d17a3` | ml-portfolio | fix(feature-engineering): HTML table alignment, chip gap increase |

---

## 5. Enhancement Suggestions Discussed (Not Yet Implemented)

### High priority
| Feature | Output | Why |
|---|---|---|
| **One-hot encoding** | Binary indicator columns per unique value | Most common categorical transform; needed for linear models |
| **Target encoding** | Category → mean of target column | Powerful for tree models with high-cardinality categoricals |
| **Cyclical encoding** | sin/cos pairs for periodic columns | Prevents Dec→Jan being 11 steps away; important for time features |

### Medium priority
| Feature | Output | Why |
|---|---|---|
| **Row-wise aggregates** | Mean/max/min/std across column group | Common in financial/health datasets |
| **Transform presets** | One-click "Skew correction", "Normalize all", "Tree-ready" | Saves setup time for common workflows |

### UX improvements
- Column search (useful at 50+ columns)
- Transform recipe summary before applying (e.g. "will add 23 columns: 7 log1p, 5 freq, 11 interactions")

---

## 6. Pending — Feature Selection

All previously discussed improvements still pending:
- Auto-run on settings change (debounced ~300ms)
- Correlation pairs disclosure in drop reasons (show which feature + r value)
- Live count preview on all 5 tabs
- Variance values visible in ranking table
