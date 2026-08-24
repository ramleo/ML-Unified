# Conversation — 2026-06-18 — ML-Unified — Part 99

---

## Session Summary

Continuation from Part 98. Focus: migrating Preprocessing and AutoML from inline modals to dedicated full-page routes in `ml-portfolio`. Added three new UX features to the Preprocessing tool.

---

## Design Decision

User asked whether a dedicated page or a modal popup is better for the ML tools. Assistant recommended **dedicated pages** because:
- The preprocessing flow (upload → overview → configure → process → before/after comparison) had grown too complex for a modal
- New features (recommendations sidebar, presets, quality score) need more horizontal space
- Full-page routes look like real tools, not portfolio demos
- Avoids scroll-within-modal and cramped layout issues

User confirmed: "please proceed."

---

## Completed This Session

### 1. `/tools/preprocessing` — Full Page (`bda7a57`)

**File created:** `src/app/tools/preprocessing/page.tsx`

Complete rewrite of the preprocessing flow as a dedicated Next.js page route. Key new features:

#### Smart Recommendations Panel (new)

Sticky left sidebar (300px, `position: sticky, top: 5rem`) that auto-analyzes the uploaded dataset and generates actionable advice:
- **ID column detection**: `nunique >= rows * 0.97` → suggests dropping (e.g., PassengerId)
- **High-skew detection**: `|skew| >= 1` per numeric column → suggests enabling Fix Skewness
- **Heavy missing detection**: `missing / rows > 0.15` → suggests switching to KNN imputation
- **High-cardinality categoricals**: `nunique > 30` → warns about OHE explosion, suggests Frequency encoding
- **Standardization suggestion**: shown when numeric columns exist

Each recommendation card:
- Color-coded dot indicator (red=drop, cyan=skew, amber=missing, purple=encoding, green=standardize)
- Title + brief description
- **Apply** button that wires directly into config state
- Green checkmark replaces button when the recommendation has been applied (derived from current state, not tracked separately)

#### One-Click Presets (new)

Pill buttons in a bar at the top of the configure step:

| Preset | Config |
|---|---|
| Quick Clean | removeDups=true, mean impute, no encoding changes |
| ML Ready | KNN impute, outlier removal, skew fix, OHE, Z-score |
| Custom | defaults; any manual change reverts to this |

Active preset highlighted with cyan border. Any manual slider/select change sets activePreset → "custom".

#### Data Quality Score (new)

Shown prominently at the top of the results step. Formula:
- Missing penalty: `min(45, missing_rate * 2.5 * 100)` — 10% missing = -25 pts
- High-skew penalty: `min(35, (high_skew_cols / numeric_cols) * 70)` — all cols skewed = -35 pts
- Missing column penalty: `min(20, (cols_with_missing / total_cols) * 40)`
- Score = `max(0, 100 - sum(penalties))`

Displayed as:
- Before score (big number, color-coded) → arrow → After score (big number)
- "+N pts" badge in green if improvement
- Two progress bars (Before vs After, same color scale)

Score color scale: 85+ = green, 70-84 = amber, 50-69 = orange, <50 = red

#### Pass to AutoML Button (new)

In the results step alongside the Download button. Stores cleaned CSV in `sessionStorage` under key `prep_handoff` as `{ csv_b64, filename }`, then navigates to `/tools/automl`.

#### Layout Changes

**Configure step** (two-column):
```
[Stats bar: rows · cols · missing] [Preset buttons — right-aligned]
[Left sidebar 300px: SmartRecommendations (sticky)] | [Right: DatasetOverview + all config controls]
```

**Results step** (`maxWidth: 960`):
```
[Data Quality Score card (full width)]
[4-column summary grid: Rows / Columns / Features / Missing]
[Before vs After comparison (up to 10 columns, wider 240px bells)]
[Download] [Train with AutoML →]
[Process Another Dataset]
```

**Page header** (sticky, blur backdrop):
- `← Portfolio` back link (navigates to `/#capabilities`)
- Eyebrow pill `ML Capabilities` + `Data Preprocessing` title
- Step indicator (Upload / Configure / Processing / Results)

DatasetOverview shows up to 12 numeric columns (was 8 in modal).
ComparisonView shows up to 10 columns (was 7) with wider 240px bell curves.

---

### 2. `/tools/automl` — Full Page (`bda7a57`)

**File created:** `src/app/tools/automl/page.tsx`

Thin wrapper over `AutoMLModal` with `isPage={true}`:
- Sticky page header with `← Portfolio` back button
- Content container with card background (`rgba(17,24,39,0.80)`, border, 20px radius)
- Wrapped in `PipelineProvider` (AutoML needs pipeline context)

**sessionStorage handoff**: On mount, checks `sessionStorage.getItem("prep_handoff")`. If present:
- Removes from sessionStorage
- Decodes base64 → `Uint8Array` → `Blob` → `File`
- Triggers `handleFile(file)` to auto-load the preprocessed CSV

---

### 3. AutoMLModal — `isPage` prop (`bda7a57`)

**File modified:** `src/components/modals/AutoMLModal.tsx`

Added `isPage?: boolean` prop (default `false`).

When `isPage = true`:
- All modal content is assigned to `const inner = (<>...</>)` instead of `return (<ModalShell>...</ModalShell>)`
- Returns `inner` directly (no backdrop, no container, no header)

When `isPage = false` (default, existing behavior):
- Returns `<ModalShell onClose={onClose} title="AutoML Pipeline" accent={ACCENT}>{inner}</ModalShell>`

---

### 4. MLCapabilities — Router Navigation (`bda7a57`)

**File modified:** `src/components/MLCapabilities.tsx`

Removed:
- `PreprocessingModal` import and mounting
- `AutoMLModal` import and mounting
- `openModal` state, `automlResult`, `automlHistory`, `handleAutomlResultChange`, `handleAutomlSaved`
- `PipelineProvider` wrapper (AutoML page has its own)
- `useCallback` and `useState` for modal management

Added:
- `useRouter` from `next/navigation`
- `router.push(\`/tools/${cap.id}\`)` on both scroll and grid layout `onRunHere` callbacks

`"Try it"` button on modalEnabled cards now navigates to `/tools/preprocessing` or `/tools/automl`.

---

## Commit

| Hash | Repo | Description |
|---|---|---|
| `bda7a57` | ml-portfolio | feat(tools): dedicated pages for Preprocessing and AutoML with smart UX |

Pushed to GitHub (`ramleo/ML-Portfolio` main). Vercel deployment triggered automatically.

---

## Current State

### ml-portfolio
- Latest: `bda7a57` — deploying to Vercel Production
- Preprocessing tool: `/tools/preprocessing` — full page, 3 new features
- AutoML tool: `/tools/automl` — full page
- 5 card modals remaining (no `modalEnabled`): Feature Eng, Feature Select, Optuna, SHAP, Ensemble

### ML-Unified
- Latest: `613e6c3` — unchanged this session

---

## Architecture Patterns Established

- **`/tools/<id>` page convention**: each ML capability with `modalEnabled: true` now has a dedicated route
- **Smart Recommendations pattern**: `useMemo` over `analyzed` + current config state; "applied" status derived from state (not tracked separately)
- **Presets pattern**: `PRESETS` constant maps key → config; `activePreset` state set to "custom" on any manual change
- **Quality Score formula**: missing rate + high-skew ratio + missing-cols ratio → 0-100
- **sessionStorage handoff**: `prep_handoff` key stores `{ csv_b64, filename }`; AutoML page reads it on mount and clears immediately

---

## Pending Backlog

### ml-portfolio — Step 3 card modals (5 remaining)
- Feature Engineering (`#38bdf8`)
- Feature Selection (`#fb923c`)
- Optuna Tuning (`#a78bfa`)
- SHAP Explainability (`#f59e0b`)
- Ensemble Methods (`#f472b6`)

### ml-portfolio — Step 4
- Pipeline builder UI

### ML-Unified
- Fix `showAutoMLWizard()` in main frontend (line ~4566)
- Phase 9: Ensemble / stacking
- Phase 10: Pipeline export
- Phase 11–13: Encoding options, GPU, SMOTE
- Retrain 80 Cereals model
- Verify AdaBoost winner-training branch exists in app.py

---

## Process Reminders
- NO EMOJIS ever
- Always report short git hash with every commit
- Always push to GitHub after every commit
- HF Space: upload root `app.py` via Python SDK — git push blocked by .pkl binaries
- TSC is always truth for TypeScript — never trust IDE diagnostics
