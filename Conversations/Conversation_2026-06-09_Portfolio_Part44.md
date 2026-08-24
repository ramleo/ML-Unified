# Conversation — 2026-06-09 | ML Unified Features (Part 44)

**Date:** 2026-06-09
**Projects:** ML-Unified (Render)
**Continued from:** Part 43

---

## Commits This Session

| Hash | Repo | Summary |
|---|---|---|
| `14f4845` | ML-Unified | Add dataset upload to drift tab — POST /drift/{model_id}/upload + mode toggle |
| `9934a19` | ML-Unified | Improve drift baseline — extract mean/std from trained sklearn pipeline |

---

## Feature: Dataset Upload for Drift Tab (`14f4845`)

Added a second mode to the Drift tab alongside the rolling prediction buffer.

**Mode toggle** — segmented control at top of Drift tab:
- **From predictions** — existing rolling buffer behaviour
- **Upload dataset** — drag-drop or click to browse a CSV; posts to `POST /drift/{model_id}/upload`

**Backend — `POST /drift/{model_id}/upload`:**
- Accepts a CSV file, parses with pandas
- Passes all rows through the same `_compute_drift()` helper as the GET endpoint
- Response adds `source: "upload"` and `filename` fields
- Footer note adapts: "N rows from filename.csv" vs "N recent predictions in window"

**Refactor:** `_compute_drift(schema, rows)` extracted as shared helper used by both endpoints.

**CSS:** `.drift-mode-bar`, `.drift-mode-btn`, `.drift-upload-zone`, `.drift-upload-label`, `.drift-upload-sub`

---

## Improvement: Better Drift Baseline (`9934a19`)

**Problem:** Previous baseline used schema field range midpoint as "expected mean" — e.g., Annual Income [0, 500,000] → expected mean = 250,000. Real training distributions are skewed; this made normal inputs look drifted and extreme inputs look normal.

**Solution:** Extract real training statistics from the fitted sklearn pipeline at model load time.

**Extraction priority (in `_extract_pipeline_stats`):**
1. **StandardScaler** found → use `mean_` (actual training mean) and `scale_` (actual training std) — most accurate
2. **SimpleImputer** found (no scaler) → use `statistics_` (training median as center), schema range for std — much better than midpoint
3. **Neither** → fall back to schema range midpoint (same as before)

**Caching:** Stats are extracted once per model and stored in `_baseline_cache` dict. No repeated pipeline introspection.

**Categorical fields:** Still use uniform baseline — OHE does not store category frequencies.

**Frontend:** Footer note updates to "Numeric baseline from training data" when pipeline stats are used, vs "Numeric baseline estimated from field ranges" for fallback.

**`_step(transformer, name)`** — helper to safely get a named step from a Pipeline.

---

## Scope for Future Drift Improvements (discussed, not implemented)

Ranked by impact:

| Priority | Item | Notes |
|---|---|---|
| High | Categorical actual frequencies | OHE doesn't store them; need to pre-compute and store in schema |
| High | KS test instead of z-score | Tests full distribution shape, not just mean; requires storing training histograms |
| High | Distribution histogram UI | Visual overlay of training vs recent — most immediately legible |
| Medium | PSI metric | Industry-standard (finance/insurance); PSI < 0.1 / 0.1–0.2 / > 0.2 thresholds |
| Medium | Persistent buffer | Survive Render restarts; SQLite or JSON file |
| Medium | Drift trend over time | Is drift increasing or stable? |
| Low | Feature correlation drift, missing value patterns | More advanced |

---

## Key Decisions

- **No emojis in UI** — user rule; SVG icons used throughout
- **Drift is a portfolio showcase** — architecturally correct but not production-grade; the baseline improvement makes the numeric scores meaningful
- **Categorical baseline stays uniform** — OHE limitation; can be improved by storing frequencies in schema JSON at train time

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
| 18 | Data drift — categorical frequencies | Potential next improvement |
| 18 | Data drift — histogram UI | Potential next improvement |
| 18 | Data drift — persistent buffer | Potential next improvement |
| 13 | 35 EDA unit tests | Pending |
| 19 | MLflow experiment tracking | Pending |
| 20 | Playwright E2E tests | Pending |
| 12 | EDA microservice extraction | Deferred |
| 21 | Batch predict — Object Detection + Segmentation | Deferred |
| 11 | Cleaned CSV download | Deferred |
