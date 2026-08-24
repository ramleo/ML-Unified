# Conversation — 2026-06-14 — ML-Unified — AutoML Phases 3-5 Part 76

---

## Session Summary

Continued AutoML improvements: Phase 3 (validation split visibility), Phase 4 (resource estimation + GPU detection + adaptive learning curve), Phase 5 (Feature Engineering step). Also fixed multiple UI bugs: wizard stepper accent, scrollbar theming, accent swatch tooltips, input background, explain rendering crash, progress label misleading text, and default accent color.

---

## Fixes & Features This Session

### Fix 1 — Wizard Stepper Active Step Uses Active Accent

`.wizard-step.active` was using `var(--accent)` (static indigo), not `var(--active-accent)`. Higher specificity than `.wizard *` rule caused Step 1 "Upload" label to show in indigo while other steps showed correct orange.

**Fix:** Changed `.wizard-step.active` and `.wizard-step.active .wizard-step-num` to use `var(--active-accent, var(--accent-from))`.

**Commit:** `11b3cbf`

---

### Feature 2 — Phase 3: Validation Set Split Visibility

**Backend:** Added `n_train` and `n_test` to `automl_result` in both classification and regression paths after `train_test_split()`.

**Frontend:** Added "Split" row to Training Info panel: `624 train · 156 test`.

**Commit:** `e00ba0e`

---

### Feature 3 — Themed Scrollbar + Accent Swatch Tooltip

**Scrollbar:**
- `.sidebar` and `.main` now have thin 4px scrollbar
- Thumb: `color-mix(in srgb, var(--accent) 35%, transparent)` — adapts to theme automatically
- Track: transparent
- Firefox: `scrollbar-width: thin`

**Swatch tooltip:**
- Added `ACCENT_NAMES` map (`#818cf8` → "Indigo", etc.)
- `_swatchTip(c)` helper returns `"Indigo · #818cf8"`
- All 3 swatch render locations updated with `data-tip` attribute
- CSS `::after` tooltip appears on hover

**Commit:** `82f113c`

---

### Feature 4 — Phase 4: Resource Estimation + GPU + Adaptive Learning Curve

**Backend:**
- `_detect_gpu()` — tries torch then nvidia-smi, returns `{available, name}`
- `/system-info` GET endpoint returns `{gpu: ...}`
- Learning curve uses `cv=3` if rows > 5,000 (instead of 5)
- Learning curve wrapped in try/except — sets `lc_skip_reason` on failure
- `gpu` field added to both classification and regression `automl_result`
- `lc_cv_folds` added to `automl_result`
- Row-count skip (> 20K) removed — rely on OOM/timeout catch instead

**Frontend:**
- `_estimateResources(rows, nCols, nCatCols)` — computes RAM, time, LC folds
- Resource card on Configure page (Step 2): Est. RAM, Est. Time, CV Folds, Learning Curve, GPU
- GPU fetched async from `/system-info` on page load
- Results page: Learning curve panel shows "unavailable" card with reason if `lc_skip_reason` set
- Training Info: added GPU row and updated Validation row to show LC folds

**Commits:** `347be55`, `ae27e01`

---

### Fix 5 — Dataset Name Input Background

Root cause 1: `background:transparent` on input was showing white modal background.
Root cause 2: `color-scheme` not set — browser forced light input background.
Root cause 3: `-webkit-box-shadow` inset trick needed to override browser defaults.

**Final fix:** `background:var(--bg-glass)` + `-webkit-box-shadow:0 0 0 1000px var(--bg-glass) inset` on the input.
Added `color-scheme: dark/light` to all 6 theme CSS blocks.

**Commits:** `15b4f44`, `1031fee`, `7d9c8b6`, `6fda2ec`

---

### Fix 6 — Explain Rendering Crash Showing Wrong Error

**Root cause:** `automl?.lc_skip_reason` inside `_renderExplanationDashboard` — `automl` is not in scope of that function, causing ReferenceError. The outer fetch try/catch caught the rendering error and showed "Request failed — check your key" even when API call succeeded.

**Fix:**
- Added inner try/catch around rendering only — errors logged to console, not shown to user
- Pass `lc_skip_reason` and `lc_cv_folds` via `vizData` object to `_renderExplanationDashboard` in both call sites
- Changed `automl?.lc_skip_reason` → `viz.lc_skip_reason` inside the function

**Commit:** `a48517a`

---

### Fix 7 — Progress Labels for AI Explanation

`['Sending context…', 'Model is thinking…', 'Generating explanation…', 'Almost done…']` → `['Sending context…', 'Model is thinking…', 'Generating AI explanation…', 'Finalising AI explanation…']`

"Almost done…" was misleading — user saw it then got an error, thinking training failed.

**Commit:** `2cddf32`

---

### Fix 8 — Default Accent Color: Violet

Reordered `ACCENT_PALETTE_DEFAULT` to put `#a78bfa` (Violet) first.
Called `selectAccent(defaultSwatch)` in `_renderAutoMLStep1()` after HTML is set, so violet is applied immediately on page load.

**Commits:** `6cce65c`, `284e3a9`

---

### Feature 9 — Phase 5: Feature Engineering Step

**New wizard step** between Preprocessing and Configure (`_renderAutoMLStep1c()`).

**UI:**
- Per-column transform chips for each numeric column (excluding target):
  - **log1p** — adds `{col}_log` column
  - **bin** — adds `{col}_bin` column (5 bins via `pd.cut`)
- **Polynomial features (degree 2)** global checkbox — adds interaction columns
  - Warning shown if > 8 numeric columns
- Toggle chips highlight in accent color when selected
- "Skip →" — clears selections, goes to Configure
- "Apply & Configure →" — keeps selections, goes to Configure

**Backend `_apply_feature_engineering(df, fe_config)`:**
- Applied to full dataframe before X/y split
- log1p: `np.log1p(col.clip(lower=0))` 
- bin: `pd.cut(col, bins=5, labels=False, duplicates='drop')`
- poly: `PolynomialFeatures(degree=2, interaction_only=True)` — only interaction cols added (those with space in name)
- Only applies polynomial if 1 < numeric_cols ≤ 15 (safety limit)
- Entire FE step wrapped in try/except — silently skipped on failure

**Flow change:**
- "No, skip →" (skip preprocessing) now goes to `_renderAutoMLStep1c()` instead of `_renderAutoMLStep2()`
- "Yes, Configure AutoML →" (after preprocessing) now goes to `_renderAutoMLStep1c()`
- `_automlFeatureEng` global persists selections

**Commit:** `02c368b`

---

## All Commits This Session

| Hash | Description | GitHub | HF |
|------|-------------|--------|-----|
| `11b3cbf` | fix(ui): active wizard step label uses active-accent | ✓ | ✓ |
| `e00ba0e` | feat(automl): show train/test split counts in Training Info | ✓ | ✓ |
| `82f113c` | feat(ui): themed scrollbar + accent swatch tooltip on hover | ✓ | ✓ |
| `347be55` | feat(automl): resource estimation, GPU detection, adaptive LC | ✓ | ✓ |
| `ae27e01` | fix(automl): remove 20K row skip, rely on OOM/timeout catch | ✓ | ✓ |
| `15b4f44` | fix(ui): dataset name input uses theme background | ✓ | ✓ |
| `1031fee` | fix(ui): color-scheme per theme; isolate explain render error | ✓ | ✓ |
| `a48517a` | fix(automl): lc_skip_reason via vizData; match input bg | ✓ | ✓ |
| `2cddf32` | fix(ui): replace 'Almost done' with accurate progress labels | ✓ | ✓ |
| `6cce65c` | feat(automl): Violet as default accent color | ✓ | ✓ |
| `284e3a9` | fix(automl): apply default accent swatch on step 1 render | ✓ | ✓ |
| `7d9c8b6` | fix(ui): webkit-box-shadow to override browser input background | ✓ | ✓ |
| `6fda2ec` | fix(ui): remove webkit-text-fill-color overriding placeholder | ✓ | ✓ |
| `02c368b` | feat(automl): Phase 5 — Feature Engineering step | ✓ | ✓ |

---

## Pending Items

| Phase | Item | Status |
|-------|------|--------|
| 6 | SHAP values | Not started |
| 7 | Regression confidence intervals | Not started |
| 8 | Optuna hyperparameter tuning | Not started |
| 9 | Ensemble / stacking | Not started |
| 10 | Pipeline export | Not started |
| 11 | Encoding per-column | Not started |
| 12 | GPU toggle | Not started |
| 13 | SMOTE | Not started |

---

## Key Technical Notes

- `_renderExplanationDashboard` does not have `automl` in scope — pass extra fields via `vizData`
- `color-scheme: dark/light` per theme block tells browser to render form controls in correct color scheme
- `-webkit-box-shadow: 0 0 0 1000px var(--bg-glass) inset` overrides Chrome's forced input background
- `_apply_feature_engineering` must be called before `df.drop(columns=[target_col])` — it operates on the full df
- Polynomial features: `interaction_only=True` keeps column count manageable; only add cols with space in name
- Learning curve: `cv=3` if rows > 5K; try/except sets `lc_skip_reason` on failure
- `selectAccent(defaultSwatch)` must be called after `innerHTML` is set (DOM must exist)
