# Conversation — 2026-06-17 — ML-Unified — Part 96

---

## Session Summary

Continued from Part 95. All work was in `ml-portfolio` AutoML modal (`AutoMLModal.tsx` + `MLCapabilities.tsx`). Series of UX bug fixes and polish across saved runs, state management, UI theme, and metric display.

---

## Completed This Session

### 1. Save Version — Silent on Click (`7c2c2c3`)

**Problem:** Clicking "Save Version" did nothing visibly — save was working but zero feedback.

**Fix:** Added `savedFlash` state. Button shows "Saved!" for 1.8s and goes slightly brighter, then reverts. Button is disabled during flash to prevent double-saves.

---

### 2. GitHub CI Failures — ruff E702 (`613e6c3`, HF deployed)

**Problem:** All ML-Unified commits showed `× 1/3` checks on GitHub. CI `test` job was failing at "Lint ml-api" step (ruff). Since `deploy` job `needs: test`, Render deploy hook was never called on any push.

**Root cause:** 24 `p.update(...); _model_idx += 1` one-liner semicolons in the AutoML classification + regression sections — ruff E702 "Multiple statements on one line".

**Fix:** Python script split all 24 lines into two. HF Space re-deployed.

---

### 3. ML-Unified UI Theme for AutoML Modal (`602d8d6`)

**Changes:**
- `ACCENT` changed from `#34d399` (green) to `#818cf8` (ML-Unified indigo)
- Modal backdrop: `rgba(2,8,22,0.92)` dark navy
- Modal container: solid `#0b1120` dark navy (no glass/green tint)
- Border: `rgba(129,140,248,0.14)` subtle indigo
- Gradient top bar: `#818cf8 → #38bdf8 → #34d399` (ML-Unified palette)
- Config stat cards: `rgba(17,24,39,0.65)` dark with indigo border
- Select/input backgrounds: `#111827`

---

### 4. Disable Save Version on Loaded Runs (`602d8d6`)

Added `isLoadedFromSaved` state:
- Set `true` when Load button clicked in Saved tab
- Set `false` on fresh train completion or Run Again
- Save Version button: dimmed, disabled, shows tooltip "Already saved — load is read-only"

---

### 5. Remove Gradient Top Bar + Round Metrics to 2dp (`35b8024`)

- Removed gradient top bar div entirely (user preferred clean top edge)
- All regression metrics (MAE, RMSE, R², Max Error, Median AE) → `toFixed(2)`
- All classification metrics (F1, precision, recall, ROC-AUC) → `toFixed(2)`
- Full Ranking scores and delta column → `toFixed(2)`
- Winner banner CV score → `toFixed(2)`

---

### 6. 5-Per-Dataset Cap on Saved Runs (`cb71b1f`)

**Feature:** Max 5 saved runs per dataset, LRU eviction.

- `handleSaveVersion` filters new list keeping only 5 most recent per `datasetName`
- Group header badge: `N / 5` (turns red `#f87171` at cap)
- Save Version button: shows `"5 / 5 Full"`, disabled, tooltip "delete a run first"
- Cap is per-dataset — multiple datasets can each have 5 runs

---

### 7. Reset to Upload After Save to Pipeline (`18163c4`)

Added `onSavedToPipeline` prop to `AutoMLModal`. When "Save to Pipeline" fires, parent clears `automlResult`/`automlHistory` → next open starts at upload.

| Action | Next open |
|---|---|
| Close mid-run (X) | Resumes results |
| Save to Pipeline | Fresh upload |

---

### 8. Correct Dataset Name in Saved Runs (`ac62e89`)

**Problem:** After modal reopen, `file` is null (File objects not serializable). Fallback was `trainResult.title` = model name ("My AutoML Model") not dataset name.

**Fix:** Stamp `fileName: file?.name` onto `TrainResult` at train time. Fallback chain: `file?.name → trainResult.fileName → trainResult.title`.

Also: Save Version now calls `onSavedToPipeline?.()` so closing after Save Version also starts fresh next open.

---

### 9. State Persists Bug — onResultChange Ref Churn (`ed4f6d7`)

**Root cause:** `onSavedToPipeline()` → `setAutomlResult(null)` → MLCapabilities re-renders → new inline `onResultChange` function reference → modal's `useEffect([trainResult, history, onResultChange])` saw new ref → fired → restored `automlResult` to non-null.

**Fix (two layers):**
1. `useCallback` in MLCapabilities for both `onResultChange` and `onSavedToPipeline` — stable references
2. Ref pattern in modal: `onResultChangeRef.current` — `onResultChange` removed from useEffect deps entirely

```tsx
const onResultChangeRef = useRef(onResultChange);
onResultChangeRef.current = onResultChange;
useEffect(() => {
  onResultChangeRef.current?.(trainResult, history);
}, [trainResult, history]); // no onResultChange in deps
```

---

### 10. Dynamic Training Time Estimate (`2509d7e`)

Replaced static "1–3 minutes" with a formula based on actual selected models and dataset size.

```
base_seconds_per_model:
  rows < 500    → 5s
  rows < 2000   → 12s
  rows < 10000  → 25s
  rows ≥ 10000  → 50s

slow_multiplier (1.8×): XGBoost, LightGBM, CatBoost, Gradient Boosting, SVM, SVR, Extra Trees
fast_multiplier (0.6×): Naive Bayes, Decision Tree, Ridge, Lasso, ElasticNet
+ 20% Render overhead buffer
range = lo (×0.8) to hi (×1.4) of total
```

Shows: `Running 5-fold CV on 7 algorithms across 891 rows. Estimated time: ~1 min–1.5 min (varies with server load).`
Range highlighted in indigo.

---

### 11. Loaded Runs Don't Persist to Parent (`901bce8`)

**Problem:** Loading a saved run → `setTrainResult(run.result)` → `onResultChange` effect fires → parent `automlResult` set → next open resumes on that loaded run.

**Fix:** Skip `onResultChange` when `isLoadedFromSaved` is true:

```tsx
useEffect(() => {
  if (!isLoadedFromSaved) {
    onResultChangeRef.current?.(trainResult, history);
  }
}, [trainResult, history, isLoadedFromSaved]);
```

**Full close-behaviour matrix:**

| Action before closing | Next "Try it" |
|---|---|
| Fresh train (no save) | Resumes results |
| Fresh train → Save Version | Fresh upload |
| Fresh train → Save to Pipeline | Fresh upload |
| Load from Saved → close | Fresh upload |

---

## Commits This Session

| Hash | Repo | Description |
|---|---|---|
| `7c2c2c3` | ml-portfolio | Save Version "Saved!" flash for 1.8s |
| `613e6c3` | ML-Unified | Fix ruff E702 — split 24 semicolon one-liners |
| HF re-deploy | HF Space | ruff fix deployed |
| `602d8d6` | ml-portfolio | ML-Unified UI theme + disable Save Version on loaded runs |
| `cb71b1f` | ml-portfolio | 5-per-dataset cap + N/5 badge + "5/5 Full" button |
| `18163c4` | ml-portfolio | Reset to upload after Save to Pipeline |
| `ac62e89` | ml-portfolio | Correct dataset name (fileName stamped) + Save Version clears parent |
| `ed4f6d7` | ml-portfolio | Fix onResultChange ref churn re-setting cleared state |
| `2509d7e` | ml-portfolio | Dynamic training time estimate |
| `35b8024` | ml-portfolio | Remove gradient top bar + all metrics to 2dp |
| `4789937` | ml-portfolio | Round winner banner + Full Ranking scores to 2dp |
| `901bce8` | ml-portfolio | Loaded runs skip onResultChange — don't persist to parent |

---

## Current State

### ml-portfolio
- Latest: `901bce8` — live on Vercel Production
- AutoML modal: complete feature set with all UX bugs resolved

### ML-Unified
- Latest: `613e6c3` — GitHub + HF Space (ruff fix)
- CI now passing (all 3 checks green)

---

## Pending Backlog

### ml-portfolio
- Step 3: remaining 6 card modals (Preprocessing, Feature Eng, Feature Select, Optuna, SHAP, Ensemble)
- Step 4: Pipeline builder UI
- Shared `ModalShell` component for consistent chrome across all card modals

### ML-Unified
- Fix `showAutoMLWizard()` in main frontend (line ~4566) — always starts fresh
- Phase 9: Ensemble / stacking
- Phase 10: Pipeline export (download as .pkl / Python script)
- Phase 11–13: Encoding options, GPU, SMOTE
- Retrain 80 Cereals model
- Verify AdaBoost winner-training branch exists in app.py

---

## Key Concepts / Decisions This Session

- **Stale closure / ref churn pattern**: inline callbacks in JSX create new references on every render; useEffect with those in deps re-fires spuriously. Fix: useCallback in parent + useRef in child.
- **isLoadedFromSaved gate**: prevents loaded results from polluting parent persist state; only fresh trains should resume.
- **fileName on TrainResult**: File objects can't be serialized; stamp filename at train time onto the result object so it survives modal unmount.
- **Per-dataset cap vs global cap**: 5 per dataset allows multiple datasets; global cap would silently evict unrelated work.
- **Ruff E702**: semicolons separating two statements on one line. Python linter enforces PEP 8 one-statement-per-line. CI `deploy` job depends on `test` — fixing ruff re-enables Render auto-deploy.
- **Dynamic estimate formula**: base seconds × model speed tier × dataset size factor × Render buffer. Meaningful for users; previously always wrong (always "1–3 min").

---

## Process Reminders
- NO EMOJIS ever
- Always report short git hash with every commit
- Always push to GitHub after every commit
- HF Space: upload root `app.py` via Python SDK — git push blocked by .pkl binaries
- TSC is always truth for TypeScript — never trust IDE diagnostics
