# Conversation — 2026-06-08 | ML Unified Features (Part 42)

**Date:** 2026-06-08
**Projects:** ML-Unified (Render)
**Continued from:** Part 41

---

## Commits This Session

| Hash | Repo | Summary |
|---|---|---|
| `d1a5faf` | ML-Unified | Redesign confidence bar chart — winner badge, column layout, staggered animation |
| `692c12a` | ML-Unified | Add Training tab — feature importance bars + GBM loss curve |
| `a52ef94` | ML-Unified | Fix insurance schema: model label was 'Gradient Boosting', actual pkl is RandomForestRegressor |
| `749e266` | ML-Unified | Replace Training tab with What-if analysis |
| `fef04e7` | ML-Unified | Add side-by-side Original | Result layout to Object Detection and Segmentation |
| `e730d1d` | ML-Unified | Add vision ambient themes — blob colors shift per section with 1.5s transition |
| `167017a` | ML-Unified | Extend ambient themes to all sections — every section shifts blob colors |
| `c69ea47` | ML-Unified | Add batch image classification — multi-upload grid with per-card results |

---

## Feature: #8 Confidence Bar Chart Redesign (`d1a5faf`)

**Problem:** Thin 6px pill bars with fixed 140px name column — functional but basic.

**Changes:**
- Column layout — class name + percentage on one row, bar below (removes fixed 140px width constraint)
- Bar height 6px → 10px with 6px border-radius
- Predicted class highlighted: accent-tinted track, full-opacity fill, "Predicted" pill badge
- Non-predicted bars at 66% accent opacity for clear visual hierarchy
- Staggered entrance animation (80ms per bar)

---

## Feature: #10 Training Tab → replaced by What-if Analysis

### Training Tab (initial, `692c12a`) — later replaced

Built `GET /training/{model_id}` endpoint returning feature importances + GBM loss curve. Added third tab "Training" alongside Predict | Pipeline. Showed feature importance bars and SVG sparkline for Titanic GBM.

**Why replaced:** Feature importance duplicated SHAP (already shows per-prediction feature impact). Training curve only worked for Titanic (only GBM stores `train_score_`). Tab was weak for 3 of 4 models.

### What-if Tab (`749e266`)

Replaced Training tab with **What-if Analysis** — holds all inputs at sample values, varies one feature across its range, plots how the prediction shifts.

**Mechanics:**
- Feature chips let user select any input field (default: first numeric field)
- Numeric features: 20 evenly spaced sweep points, parallel `/predict` calls, SVG line chart with gradient fill + dots + dashed "sample" marker
- Categorical features: one call per option, rendered as bars
- Binary classification: class-1 probability on Y axis
- Multiclass: max probability (top class confidence) on Y axis
- Regression: raw predicted value on Y axis
- Tab icon: sliders (two horizontal lines with circle handles)
- Lazy-loaded per model on first click, cached until model switch

---

## Bug Fix: Insurance Schema Mislabeled (`a52ef94`)

`schemas/insurance.json` had `"model": "Gradient Boosting"` but the actual pkl contained a `RandomForestRegressor`. Fixed to `"model": "Random Forest"`.

**Root cause:** Schema was hand-written and didn't match the actual trained estimator.

---

## Feature: #14 Side-by-Side Vision Results (`fef04e7`)

**Before:** Object Detection and Segmentation showed only the result image (annotated/overlay). Image Processing already had side-by-side.

**After:** All three panels use `.ip-before-after` layout:
- Detection: Original | Detected (bounding boxes)
- Segmentation: Original | Segmented (overlay)

Reused existing `.ip-before-after` / `.ip-image-box` / `.ip-image-result` CSS. `detImageURL` and `segImageURL` (already stored at upload time) used as the original panel source.

---

## Feature: #16 Vision Ambient Themes (`e730d1d` + `167017a`)

### Phase 1 — Vision only (`e730d1d`)

Global ambient blobs (`.bg-blob-1`, `.bg-blob-2`) shift color when switching vision sections:

| Section | Blob color |
|---|---|
| Image Classifier | Fuchsia rgba(232,121,249) |
| Image Processing | Orange rgba(251,146,60) |
| Object Detection | Sky blue rgba(56,189,248) — lowered opacity (was 0.17→0.11) |
| Image Segmentation | Violet rgba(167,139,250) |

Added `transition: background 1.5s ease` to `.bg-blob` CSS.

`setAmbientTheme(c1, c2)` helper updates blob inline styles. `AMBIENT_DEFAULT` stores the default indigo/sky pair for reset.

**Light mode fix:** `setAmbientTheme` halves opacity (×0.45) in light mode to prevent color punching through. Sky blue opacity also reduced at source (0.17→0.11) as it's inherently high-luminance.

### Phase 2 — All sections (`167017a`)

Extended to every section:

- Added `hexToRgba(hex, alpha)` helper to convert model accent hex → rgba
- Added `setAmbientFromAccent(hex)` convenience wrapper (0.14 / 0.09 opacity pair)
- ML Models: blobs shift to model accent on select (green/Diabetes, sky/Titanic, indigo/Iris, amber/Insurance). User-trained models use their assigned accent from palette.
- Unsupervised/Clustering: blobs shift to algorithm accent (indigo/K-Means, sky/DBSCAN, pink/t-SNE, green/PCA)
- EDA: green (#34d399) wash
- All early `setAmbientTheme(...AMBIENT_DEFAULT)` resets removed in favour of per-section `setAmbientFromAccent` calls

---

## Feature: #15 Batch Image Classification (`c69ea47`)

**Before:** Classifier accepted one image at a time, showed single result with top-K bars.

**After:** Multi-upload batch classify.

**UX flow:**
1. Upload zone accepts `multiple` images (click or drag-drop)
2. Thumbnail grid renders immediately — each card shows square-cropped image + "Ready" status
3. Toolbar shows: image count + "Classify All →" + "✕ Clear"
4. Click Classify All — progress bar appears ("3 / 8 classified…"), cards update in-place sequentially
5. Each completed card shows: top prediction label, confidence %, top-2 runner-ups
6. Card borders: fuchsia (success), amber (low confidence), red (error)

**CSS classes:** `.batch-grid`, `.batch-card`, `.batch-card-img`, `.batch-card-body`, `.batch-card-filename`, `.batch-card-status`, `.batch-card-top-label`, `.batch-card-top-conf`, `.batch-card-top2`, `.batch-card--done`, `.batch-card--low`, `.batch-card--error`

**JS:** `handleBatchFiles()`, `addBatchFiles()`, `renderBatchGrid()`, `clearBatch()`, `runBatchClassify()`, `_updateBatchCard()`, `_updateBatchProgress()`

Images processed sequentially to avoid overwhelming Render free tier.

**Note:** `renderVisionResult()` (single-image result function) is now dead code — kept but never called.

---

## Decisions / Deferred

### What-if tab replacing Training
- Feature importance removed (duplicates SHAP)
- Training loss removed (only Titanic GBM had it)
- What-if is unique, self-contained (only needs /predict), interactive

### Batch for Object Detection + Segmentation — deferred
**Why deferred:** Detection/segmentation result is a full annotated image (not a label). Batch would need a scrollable list of before/after pairs rather than a grid — heavier UX, different interaction pattern.

**Planned design when implemented:**
- List layout (not grid) — each item needs full width for two images
- Items start collapsed (filename + status), expand when result arrives
- Cap at 10 images
- Same sequential processing + progress bar as classifier batch

---

## Standing Rules (unchanged)

- Conversation logs: `ML-Iris/Conversations/Conversation_YYYY-MM-DD_Topic_PartXX.md`
- Never expose `ramleo84@gmail.com` publicly
- `vision_cache/` and `.mcp.json` must never be committed
- Always run `ruff check` + `pytest` before pushing ML-Unified
- User-facing errors: plain English only
- Every project launched from portfolio inherits active palette via `?palette=xxx`
- After commit: always push or ask to push

---

## Pending Tasks

| # | Item | Status |
|---|---|---|
| 8 | Prediction confidence bar chart | ✅ Done this session |
| 10 | Training tab → What-if analysis | ✅ Done this session |
| 14 | Side-by-side vision results | ✅ Done this session |
| 15 | Batch image classification | ✅ Done this session |
| 16 | Vision ambient themes | ✅ Done this session |
| — | Extend ambient themes to all sections | ✅ Done this session |
| 21 | Batch predict — Object Detection + Segmentation | Deferred (scrollable before/after list) |
| 11 | Cleaned CSV download | Deferred |
| 12 | EDA microservice extraction | Pending |
| 13 | 35 EDA unit tests | Pending |
| 17 | Mobile bottom tab bar | Pending (do before public sharing) |
| 18 | Data drift detection | Pending |
| 19 | MLflow experiment tracking | Pending |
| 20 | Playwright E2E tests | Pending |
