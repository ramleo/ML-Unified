# Conversation — ML-Unified + ml-portfolio Part 117
**Date:** 2026-06-24

---

## Topics Covered

1. Test case generation (TC-P2) — continuation from Part 116
2. AI Suggest fix — rate limit + provider switch
3. FE tool — 3 new features (column search, transform recipe summary, DatasetEstimator verified)
4. Quick wins — Model Fitness tooltip, showAutoMLWizard fix, learning curve, regression CI
5. AutoML bug fixes — JSON parse hardening, error bleed fix
6. FE tool — 4 new transforms (datetime, polynomial, binning, ratio/diff)

---

## 1. Test Case Generation — TC-P2

Spawned 1 subagent to read Parts 16–33 and write test cases directly to disk.

- **TC-P2-A.md** — Parts 16–24, 75 TCs, 832 lines
- **TC-P2-B.md** — Parts 25–33, 83 TCs, 946 lines
- **Total:** 158 TCs
- **Agent stats:** 92,932 tokens | ~362s

Key lesson: subagents should write files directly to disk and return only a short confirmation — never return TC content to main thread.

---

## 2. AI Suggest — Rate Limit Fix

**Problem:** Gemini free tier (10 RPM) was causing intermittent 502 errors on AI Suggest buttons.

**Root cause sequence:**
1. Before fix: Vercel timed out at 10s → 502 (timeout masking the real error)
2. After `maxDuration=30` fix: Vercel waited → Gemini returned 429 → surfaced as "Rate limit reached"

**Fixes applied:**
- Added `export const maxDuration = 30` to `src/app/api/ai-tools/route.ts` — commit `525e43e`
- Switched `useFSAISuggest.ts` from `provider: "gemini"` → `provider: "groq"` — commit `0f5a478`
- Switched `useFEAISuggest.ts` default fallback from `"gemini"` → `"groq"` — commit `0f5a478`
- Decoupled FE AI Suggest from chat gear icon (removed localStorage read) — commit `dfd16d6`
- User added `GROQ_API_KEY` to Vercel environment variables

**Option 3 chosen:** AI Suggest always uses fixed server-side Groq key, independent of chat gear icon. Provider can be changed in future by editing one line in each hook file (`useFSAISuggest.ts:50`, `useFEAISuggest.ts:53`).

---

## 3. FE Tool — 3 Features (ml-portfolio)

Spawned 1 subagent. Files changed:

| File | Lines | Change |
|------|-------|--------|
| `NumericTransformsPanel.tsx` | 200 | Column search input (shown when 8+ cols) |
| `CategoricalPanel.tsx` | 154 | Column search input (shown when 8+ cols) |
| `feature-engineering/page.tsx` | 399 | Transform recipe summary banner |

- **Column search** — filters columns by name, case-insensitive, dark-themed
- **Transform recipe summary** — shows "Will apply: 3 log1p, 2 sqrt → ~5 cols" above Apply button
- **DatasetEstimator** — confirmed already present via FEUploadInfo at configure step (item #6 was stale)
- Commit: `525e43e`

---

## 4. Quick Wins — All 4 Completed

### #12 Model Fitness Tooltip
- Added `ⓘ` icon with `title` tooltip next to "MODEL FITNESS FOR THIS DATASET"
- Tooltip: "LLM-rated score (0–100) estimating how well this algorithm fits your dataset — higher is better. 90–100 = excellent fit. 60–89 = good, may benefit from tuning. Below 60 = poor fit."
- File: `src/components/AutoMLSteps/Step4Results.tsx`

### #15 Fix showAutoMLWizard()
- Old: checked `_lastAutoMLResult` → restored previous results page
- New: sets `_lastAutoMLResult = null` unconditionally → always calls `_startFreshAutoML()`
- File: `services/ml-api/frontend/index.html` (HF Space root `index.html`)
- Commit: `28e18b2`

### #32 Learning Curve Interpretation
- Added `interpretLearningCurve(gap, finalVal, numRows?)` to `feAlgorithms.ts` → `automlUtils.ts`
- Dataset-size-aware thresholds:
  - ≤200 rows: gap > 0.08 = overfitting, finalVal < 0.65 = underfitting
  - 201–1000 rows: gap > 0.12, finalVal < 0.70
  - >1000 rows: gap > 0.18, finalVal < 0.75
- Badge shown below metrics grid: green "Good fit", orange "Overfitting", yellow "Underfitting"
- Commit: `8d77e6f`

### #37 Regression Confidence Intervals
- Backend: 200-sample bootstrap CI on R² (if ≥0.60) or RMSE; stored as `ci_95: {lower, upper, metric}`
- Frontend: `WinnerMetricsGrid` shows subtitle "R² 95% CI: x.xx – x.xx" or "RMSE 95% CI: x.xx – x.xx"
- **HF Space path issue:** CI was uploaded to `services/ml-api/app.py` (wrong). Correct path is root `app.py`. Re-uploaded via HF Hub API.
- Commits: `1de7530` (backend), `8d77e6f` (frontend)

---

## 5. AutoML Bug Fixes

### Intermittent Raw JSON in AI Analysis
**Problem:** When `extractJson` failed, raw JSON string dumped into `why_won` field → shown as-is in UI.

**Fixes:**
1. `extractJson` now unwraps one-level wrapper objects (`{"analysis": {"why_won": ...}}`)
2. Added last-resort extraction: first `{` to last `}` scan
3. Fallback when parse fails: shows error banner + rule-based explanation (not raw text)
- Commit: `d464778` (+ linter auto-fix)

### LLM Error Bleeding into Upload Step
**Problem:** `useEffect(() => { if (llmError) setError(llmError); }, [llmError])` in `AutoMLModal.tsx` — AI analysis errors from Step 4 appeared on Step 1 (upload) when navigating back.
**Fix:** Removed that useEffect entirely.
- Commit: `d464778`

---

## 6. FE Tool — 4 New Transforms (ml-portfolio `/tools/feature-engineering`)

### Files Created/Modified

| File | Lines | Change |
|------|-------|--------|
| `src/lib/feAlgorithms.ts` | 116 | Split — types + helpers only (was 441 lines) |
| `src/lib/feTransforms.ts` | 314 | New — all transform logic + 4 new transforms |
| `src/components/FEPanels/NumericTransformsPanel.tsx` | 214 | Added Polynomial x² + Custom Binning sections |
| `src/components/FEPanels/DatetimePanel.tsx` | 51 | New — datetime column toggles |
| `src/components/FEPanels/RatioDiffPanel.tsx` | 86 | New — ratio/diff pair builder (up to 5 pairs) |
| `src/hooks/useFETransforms.ts` | 78 | Wired 4 new state params |
| `src/hooks/useFEFileLoad.ts` | 96 | Resets new state on file load |
| `src/app/tools/feature-engineering/page.tsx` | 269 | Slimmed 399→269, all new state wired |

### What Was Implemented

**#7 Date/datetime extraction**
- Detects columns where >80% of values parse as valid dates
- Per-column toggle in `DatetimePanel.tsx`
- Creates: `col_year`, `col_month`, `col_day`, `col_dayofweek`, `col_hour` (hour only if time present)

**#8 Polynomial features (degree 2)**
- Toggle x² per numeric column (only shown for cols with nunique > 5)
- Creates: `col_sq`
- UI in `NumericTransformsPanel.tsx` — "Polynomial: x² Squares" section

**#9 Binning**
- Enable + set bin count (3–20) per numeric column (only for cols with nunique > 10)
- Creates: `col_binN` with integer bin labels 0 to N-1
- UI in `NumericTransformsPanel.tsx` — "Custom Binning" section

**#10 Ratio/diff features**
- Pick col A + col B from numeric columns; add up to 5 pairs
- Creates: `col_a_div_col_b` (safe ratio, +1e-8 denominator) and `col_a_minus_col_b`
- UI in `RatioDiffPanel.tsx`

**Pending:** Commit + push to GitHub

---

## HF Space File Structure (Important)
- HF Space runs `app.py` from **root** (not `services/ml-api/app.py`)
- `index.html` served from `frontend/index.html` (HF root)
- `git push hf main` is broken — binary `.pkl` files rejected + protocol error
- **Workaround:** use `huggingface_hub.HfApi.upload_file()` to upload specific files

---

## pending.md Status After This Session

Newly marked ☑: 12, 15, 32, 37  
Items 7–10: implemented in HF Space AutoML FE step only → still pending for ml-portfolio FE tool (now implemented, pending commit)  
Items previously marked ☑: 1, 2, 3, 4, 5, 6, 11, 14, 34, 35, 36, 38, 48, 51

---

## Pending Work (Next Session)

1. Commit + push FE transform changes (items 7–10) to GitHub → mark ☑ in pending.md
2. Verify regression CI shows in fresh training run on HF Space
3. Next from pending.md: #13 (more ML algorithm pills — LR, SVM, KNN, Decision Tree, Naive Bayes, Ridge)
4. TC files still pending: TC-P3, TC-P5, TC-P6, TC-P7 + testcases.md master index
