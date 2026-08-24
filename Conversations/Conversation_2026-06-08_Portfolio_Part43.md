# Conversation — 2026-06-08 | ML Unified Features (Part 43)

**Date:** 2026-06-08
**Projects:** ML-Unified (Render)
**Continued from:** Part 42

---

## Commits This Session

| Hash | Repo | Summary |
|---|---|---|
| `4278d2c` | ML-Unified | Add mobile bottom tab bar — replaces horizontal sidebar with fixed nav + chip strip |
| `4430080` | ML-Unified | Add data drift detection — Drift tab with per-feature shift analysis |
| `7205a89` | ML-Unified | Replace emoji drift icons with SVG — checkmark, wave, alert circle |
| `14f4845` | ML-Unified | Add dataset upload to drift tab — POST /drift/{model_id}/upload + mode toggle |

---

## Feature: #17 Mobile Bottom Tab Bar (`4278d2c`)

**Problem:** On mobile (≤640px), the sidebar collapsed into a horizontal scrolling row of buttons — cramped and hard to use.

**Solution:** Replace entirely with a fixed bottom tab bar + sticky chip strip.

### Structure

- **Sidebar** — hidden on mobile (`display:none !important`)
- **Bottom tab bar** — fixed at bottom, 5 tabs: Models | Vision | Cluster | EDA | Tools
- **Mobile strip** — fixed at `top:56px` (just below nav), shows sub-options per active tab
- **Tools sheet** — slide-up bottom sheet with Train New Model / SHAP Analyzer / Live Metrics

### Tab behaviour

| Tab | Strip shows | Action |
|---|---|---|
| Models | Chip per model (Diabetes, Titanic, Iris, Insurance + user-trained) | Tapping chip selects that model |
| Vision | Classifier / Processing / Detection / Segment chips | Tapping chip switches Vision sub-panel |
| Cluster | K-Means / DBSCAN / t-SNE / PCA chips | Tapping chip selects algorithm |
| EDA | No strip | Navigates to EDA |
| Tools | No strip | Opens slide-up sheet |

### Key implementation details

- `syncBottomTab(tab)` — called by all select functions (`selectModel`, `selectVision`, etc.) to keep bottom bar in sync with content
- `activateBottomTab(tab)` — called by bottom tab button taps; handles navigation + strip update
- `_mobileVisionPanel` — tracks which vision sub-panel is active so Vision strip highlights the right chip
- `MOBILE_STRIPS` — object of functions that generate chip HTML per tab (models/vision/cluster); EDA/Tools have no strip
- `body.mobile-has-strip` class — toggled when strip is visible; triggers `padding-top` on `.main` to avoid content going behind the fixed strip
- Active chip uses `--chip-accent` CSS custom property (per-model/algo color, not global)
- Active tab uses global `--active-accent` (set by section select functions)
- Tools sheet: `.tools-sheet-overlay` + `.tools-sheet`; overlay click closes; `transform:translateY` slide animation
- iOS safe area: `env(safe-area-inset-bottom)` on bottom bar and tools sheet

---

## Feature: #18 Data Drift Detection (`4430080`, `7205a89`, `14f4845`)

### Backend — `routers/drift.py`

New router with two endpoints:

**`GET /drift/{model_id}`** — drift from rolling prediction buffer
- `record_input(model_id, fields)` called by `/predict` on every prediction
- Stores last 200 inputs per model in `collections.deque`
- Computes drift vs schema-derived baseline

**`POST /drift/{model_id}/upload`** — drift from uploaded CSV
- Accepts CSV file, parses with pandas
- Same `_compute_drift()` logic
- Response includes `source: "upload"` and `filename`

**`_compute_drift(schema, rows)`** — shared helper:

- **Numeric fields:** reference baseline = midpoint ± σ (σ = range/6, so 3σ spans full range). Drift = z-score of recent mean, normalised 0–1, saturates at 3σ
- **Categorical fields:** reference baseline = uniform over all options. Drift = mean absolute deviation from uniform
- Drift levels: low / medium / high (different thresholds per type)
- Returns: `n_recent`, `overall_score`, `overall_level`, `baseline: "schema"`, `features[]`

### Bug fix: emoji removal (`7205a89`)

Summary card initially used ✓ / 〰️ / ⚠️ as icons. Replaced with inline SVG:
- Low: green checkmark
- Medium: amber wave line
- High: red alert circle

### Frontend — Drift tab

4th model tab "Drift" added alongside Predict / Pipeline / What-if.

**Mode toggle** — segmented control at top:
- **From predictions** — fetches `GET /drift/{model_id}`, shows rolling buffer drift
- **Upload dataset** — shows drag-drop zone; on file select posts to `POST /drift/{model_id}/upload`

**Drift panel content:**
- Summary card: overall level SVG icon + badge (low/medium/high)
- Per-feature rows:
  - Numeric: score bar + "Expected: mean ± std" vs "Recent (N): mean ± std"
  - Categorical: per-option bar chart — ref (grey) vs recent (accent color) — with % label
- Footer note: "Baseline estimated from field ranges · N rows from filename.csv" (upload) or "N recent predictions in window" (buffer)
- Empty state: shown when buffer has 0 predictions (predictions mode)

**Always re-fetches** on tab open — no caching, so drift reflects latest predictions.

**CSS classes:** `.drift-summary`, `.drift-badge--low/medium/high`, `.drift-feature`, `.drift-score-fill--low/medium/high`, `.drift-cat-bar-ref`, `.drift-cat-bar-recent`, `.drift-mode-bar`, `.drift-mode-btn`, `.drift-upload-zone`

---

## Decisions

- **No real training CSVs available** — built-in model source data not stored in the service. Schema field ranges used as baseline instead. Labeled as "Baseline estimated from field ranges" in footer.
- **Emojis removed** — user feedback: no emojis in the UI. SVG icons used throughout.
- **Upload mode added** — more robust than prediction buffer (doesn't reset on server restart, works with real production data)

---

## Standing Rules (unchanged)

- Conversation logs: `ML-Iris/Conversations/Conversation_YYYY-MM-DD_Topic_PartXX.md`
- Never expose `ramleo84@gmail.com` publicly
- `vision_cache/` and `.mcp.json` must never be committed
- Always run `ruff check` + `pytest` before pushing ML-Unified
- User-facing errors: plain English only
- No emojis in UI or code output
- After commit: always push or ask to push

---

## Pending Tasks

| # | Item | Status |
|---|---|---|
| 17 | Mobile bottom tab bar | Done this session |
| 18 | Data drift detection | Done this session |
| 13 | 35 EDA unit tests | Pending |
| 19 | MLflow experiment tracking | Pending |
| 20 | Playwright E2E tests | Pending |
| 12 | EDA microservice extraction | Deferred |
| 21 | Batch predict — Object Detection + Segmentation | Deferred |
| 11 | Cleaned CSV download | Deferred |
