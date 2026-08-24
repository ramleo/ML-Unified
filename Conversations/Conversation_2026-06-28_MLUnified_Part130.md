# Conversation_2026-06-28_MLUnified_Part130

Continuation from Part 129.

---

## Pipeline Builder — A/B Compare Fix, FE Redesign, Preprocessing Details

### Commits This Session

#### ml-portfolio (frontend)

| Commit | Description |
|---|---|
| `551a95b` | feat(pipeline-builder): A/B Compare — per-pipeline config, ABRunner animation, extract TargetDropdown |
| `f9083bc` | fix(pipeline-builder): chain stage CSVs in A/B mode — FE sees preprocessed columns only |
| `e61b7aa` | fix(pipeline-builder): A/B modal — parse columns from chained CSV; store + show stage results |
| `0c46962` | feat(pipeline-builder): preprocess results — cols before/after, dropped cols, imputed/skewed/clipped per-column details |
| `f5ed837` | fix(pipeline-builder): FE key mismatch; add interactions, polynomial, Yeo-Johnson, binning |
| `6ecf3e8` | fix(pipeline-builder): exclude target column from FE/preprocessing column lists |

#### ML-Unified (backend)

| Commit | Description |
|---|---|
| `8d4c5d7` | feat(pipeline-builder): preprocess — per-column imputation, skew, outlier details in response |

HF Space uploaded: `stages.py` → `routers/pipeline_builder/stages.py`

---

## A/B Compare — Full Fix

### What Was Broken
- **Configure buttons were no-ops** — `ABPanel.tsx` passed `onOpen={() => {}}` to every `StageCard`. No modal ever opened.
- **Both pipelines always identical** — `handleRunAB` sent `{ csv_b64, target, task_type }` with no pipeline configs. Backend `/compare` ran default config for both → same score always.
- **No animation** — nothing showed while comparison was running.

### Fix: ABPanel.tsx rewrite + ABRunner.tsx

**New state in ABPanel:**
- `configA / configB` — per-pipeline stage configs (initialized from `DEFAULT_CONFIGS`)
- `configuredA / configuredB` — Sets tracking which stages have been run
- `stageCsvsA / stageCsvsB` — output CSV from each completed stage (for chaining)
- `stageResultsA / stageResultsB` — stored `StageResult` per stage (for `existingResult`)
- `activeModal: { stageId, pipeline: "a" | "b" } | null`

**CSV chaining (getInputCsv):**
```tsx
function getInputCsv(stageId: string, pipeline: "a" | "b"): string {
  const csvs = pipeline === "a" ? stageCsvsA : stageCsvsB;
  const idx = STAGE_ORDER.indexOf(stageId);
  for (let i = idx - 1; i >= 0; i--) {
    const prev = csvs[STAGE_ORDER[i]];
    if (prev) return prev;
  }
  return csvB64 ?? "";
}
```

**Column parsing from chained CSV:**
```tsx
function parseCsvColumns(b64: string): string[] {
  try {
    const text = atob(b64);
    const firstLine = text.split("\n")[0];
    return firstLine.split(",").map((c) => c.trim().replace(/^"|"$/g, "")).filter(Boolean);
  } catch { return []; }
}
```
Used so FE modal shows only columns that exist after preprocessing (dropped columns gone).

**onComplete now:**
1. Stores `StageResult` in `stageResultsA/B` → `existingResult` shows on reopen
2. Stores `outputCsvB64` in `stageCsvsA/B` → next stage sees chained data
3. Marks stage as configured → `StageCard` shows "done" status

**handleRunAB now passes configs:**
```tsx
const buildSpec = (cfg) => ({
  preprocess: cfg["preprocessing"] ?? null,
  fe: cfg["feature-eng"] ?? null,
  fs: cfg["feature-select"] ?? null,
  automl: cfg["automl"] ?? null,
});
body: JSON.stringify({ csv_b64, target, task_type, pipeline_a: buildSpec(configA), pipeline_b: buildSpec(configB) })
```
Backend `/compare` already accepted `pipeline_a / pipeline_b` — frontend just never sent them.

**StageModal — onConfigCapture:**
Added optional prop `onConfigCapture?: (config: Record<string, unknown>) => void` fired at start of `handleRun` before the API call. Used in ABPanel to capture each pipeline's config independently.

### ABRunner.tsx (new, 207 lines)

Shows while `abRunning === true`. Two columns (Pipeline A `#38bdf8` | Pipeline B `#a78bfa`) with 4 stage nodes each. Simulated progress via `useEffect` + 900ms interval incrementing `simStep` 0→8 (A stages 0-3, B stages 4-7). Each node shows: pulse ring + breathing dot (running), filled + checkmark SVG (done), hollow dot (pending). Connector traveling beam when active, fills solid when done. Scan-line sweep across panel.

### Extracted TargetDropdown

Moved `TargetDropdown` (inline in page.tsx, ~43 lines) to `src/components/pipeline/TargetDropdown.tsx`. page.tsx reduced from 409 → 374 lines.

---

## Preprocessing Results — Per-Column Details

### Backend changes (stages.py, commit `8d4c5d7`)

Added to `PreprocessResponse`:
```python
dropped_cols: List[str] = []
imputed_cols: Dict[str, int] = {}   # {col: n_missing_filled}
skewed_cols: List[str] = []          # columns where skew > 0.75, log1p applied
outlier_clipped_cols: List[str] = [] # columns where clip() changed values
```

Tracking in the function:
- Capture `missing_per_col = df_feat.isna().sum()` BEFORE imputation
- After imputation: `imputed_cols = {col: n for col in ... if n > 0}`
- Outlier: store `before = df_feat[col].copy()`, compare after clip → if any changed, add to list
- Skewness: if `skew() > 0.75`, apply log1p and append to `skewed_cols`

### Frontend changes (StageModal.tsx, commit `0c46962`)

Preprocessing `renderResults` now shows:
- **6 stat tiles** (2×3 grid): Rows before, Rows after, Cols before, Cols after, Missing filled, Duplicates removed
- **Dropped columns** (red tags): `cfg.drop_cols` list
- **Imputed per-column** (cyan tags): `Age (177)`, `Embarked (2)` — count of NaN filled
- **Skewness corrected** (purple tags): columns where log1p was applied
- **Outlier-clipped** (amber tags): columns where clipping changed values
- Sections only render when list is non-empty

---

## Feature Engineering — Root Bug Fix + Redesign

### Root Bug: Key Mismatch (commit `f5ed837`)

`StageConfigForms.tsx` stored transforms as `column_transforms` (UI key) but `FEConfig` has field `transforms`. Pydantic silently ignored unknown key → `cfg.transforms` always `None` → nothing ran → "No new columns added."

Same issue: `date_columns` (UI) vs `date_cols` (backend).

**Fix:** renamed both to match backend: `transforms` and `date_cols`.

### FE Form Redesign

**Removed:** `outlier_flag`, `missing_flag` from column transforms (they belong to preprocessing, not FE — and are meaningless after imputation/outlier removal).

**Added/fixed column transforms:**
- `log1p` — natural log of column + 1
- `sqrt` — square root
- `Yeo-Johnson` — power transform (handles negative values, robust normalization)
- `Equal bins` — equal-width discretization into 5 bins
- `Quantile bins` — quantile-based discretization into 5 bins

**New: InteractionPicker component**
- Two dropdowns (Col A, Col B) + "+ Add" button
- Renders removable `Age × Fare` style tags
- Sends `interactions: string[][]` to backend (already supported)

**New: Polynomial expansion**
- Checkbox multi-select of columns (≥2 required)
- Degree 2 or 3 radio (only shows when ≥2 columns selected)
- Sends `poly_cols` and `poly_degree` to backend (already supported)

**Date columns:**
- Fixed key: `date_cols` (was `date_columns`)
- Date parts picker now only shows when ≥1 date column is selected

### Target Column Exclusion (commit `6ecf3e8`)

Added `target: string` prop to `StageConfigForm`. All 5 column lists now use `featureCols = columns.filter(c => c !== target)`:
1. Preprocessing — Drop columns list
2. FE — Column transforms list
3. FE — InteractionPicker dropdowns
4. FE — Polynomial expansion checkboxes
5. FE — Date columns list

Target column was being shown as a selectable feature everywhere before this fix.

---

## Design Discussions

### FE vs Preprocessing overlap
User correctly identified that `missing_flag` and `log1p` in FE are meaningless after preprocessing:
- If missing values were imputed, `missing_flag` produces all-zero column
- If "Fix skewness" was applied in preprocessing, applying log1p in FE double-transforms
- `outlier_flag` after clipping flags values already within normal range

Decision: Remove `outlier_flag` and `missing_flag` from FE. Keep only transformations that create genuinely new features regardless of preprocessing state.

### FE concepts clarified
- FE = creating new information: polynomial features, column interactions, log/power transforms of distribution shape, date decomposition, binning
- Preprocessing = cleaning: imputation, deduplication, outlier removal, column dropping
- These are distinct jobs. Overlap in log1p/sqrt is acceptable (creates new column in FE vs modifies in-place in preprocessing).

---

## Architecture Notes

### A/B Compare data flow (final state)
```
Upload CSV → ABPanel
  Pipeline A:
    Preprocessing modal → stores stageCsvsA["preprocessing"]
    FE modal → getInputCsv() → stageCsvsA["preprocessing"] → stores stageCsvsA["feature-eng"]
    FS modal → getInputCsv() → stageCsvsA["feature-eng"] → stores stageCsvsA["feature-select"]
    AutoML modal → getInputCsv() → stageCsvsA["feature-select"]
  Pipeline B: (same, independent)
  Run A/B → sends pipeline_a spec + pipeline_b spec → backend /compare
```

### parseCsvColumns pattern
Used to derive column list from a chained CSV without a separate API call. Fast (just parse first line of base64-decoded text). Used in ABPanel to ensure FE/FS/AutoML modals show correct columns after upstream stages modify the schema.

---

## File Line Counts (end of session)

| File | Lines |
|---|---|
| `page.tsx` | 374 |
| `ABPanel.tsx` | 204 |
| `ABRunner.tsx` | 207 |
| `TargetDropdown.tsx` | 79 |
| `StageModal.tsx` | 379 |
| `StageConfigForms.tsx` | 399 |
| `stages.py` | 393 |

---

## Pending

1. **Verify FE fix end-to-end** — test transforms create new columns, interactions work, poly expansion works
2. **Score gap verification** — test Express mode after dtype fix to confirm 82.68% ≈ Pipeline Builder
3. **#23 Drift Detection v2**
4. **#24 RAG AI explanation**
5. **#33 Categorical frequencies in schema JSON**
6. **#39-44 MLOps items**
7. **#45 E2E Playwright CI**
8. **#47 Dockerize ml-eda + ml-vision**
9. **#50 Batch predictions**
10. **TC-PEND: 47 open TCs**
