# Conversation — 2026-06-17 — ML-Unified — Part 95

---

## Session Summary

Resumed from Part 94. Fixed multiple AutoML bugs reported via screenshots, added UX improvements, and built a Saved Runs feature.

---

## Completed This Session

### 1. Winner Banner — CV/Test Score Consistency (`478da62`)

**Problem:** Winner banner showed test set score as the big number; Full Ranking showed CV score. Users saw discrepancy (e.g. 76.95% vs 66.40%).

**Fix:** Big number in winner banner now shows 5-fold CV score (consistent with Full Ranking). Test set shown as secondary line: "Test set: 66.40% (CV: 76.95%)". Explained to user why test set is lower (overfitting signal) and why CV is used for selection (unbiased).

### 2. Enhanced Full Ranking Table (`884f574`)

**Change:** Replaced uniform bar chart with gradient opacity ranking:
- #1 (winner): full `ACCENT` brightness, green score, WINNER outline badge
- #2: 65% opacity, #3: 45%, #4: 30%, #5+: 20%
- Added **delta column** showing gap from winner (e.g. −2.05% for classification, +0.xxxx for regression)

Showed user Playwright mockup of both Option 1 (enhanced horizontal) and Option 2 (vertical bar with 45° labels). User chose Option 1.

### 3. AI Analysis Visual Improvements (`478da62`)

- Chart shown first (model fitness) for visual impact
- "Why [winner] won" section with left-accent border on `score_analysis`
- Actionable insights as bullet-dot cards
- Model fitness subtitle: color-coded ranges (green 90–100, yellow 60–89, red below 60)

### 4. Collapsible AI Analysis (`3751a41`)

- Header label + chevron is a toggle button; chevron rotates on expand/collapse
- Section collapsed by default; auto-expands when generation starts (`handleGenerateAnalysis` calls `setAnalysisExpanded(true)`)
- Key input fields moved **outside** the collapse wrapper so "Use my API key" works whether collapsed or not (`ebc3200`)
- Progress bar now visible on first Generate (was only showing on Regenerate — fixed in `4ec8852`)

### 5. Logistic Regression / Model Selection Bug (`354c8a6`)

**Root cause:** `selectedModels` was missing from `handleTrain`'s `useCallback` dependency array. Stale closure captured the initial set (5 defaults). Any model added after upload was silently dropped from the request.

**Fix:** Added `selectedModels` to dep array. One word change, critical bug.

### 6. Naive Bayes Silent Failure (Backend `18f1583`, HF `e544459`)

**Root cause:** `GaussianNB()` default `var_smoothing=1e-9`. After `StandardScaler` + OHE, rare category columns have near-zero variance in some folds → division by zero → exception silently caught → NB dropped from `cv_results`.

**Fix:** `GaussianNB(var_smoothing=1e-2)` — adds enough smoothing for real-world sparse OHE features. Tree models unaffected.

### 7. StandardScaler in AutoML Preprocessing (Backend `aa243d6`, HF `32dd2c3`)

**Root cause:** AutoML preprocessing pipeline at line 1740 had `SimpleImputer` only — no `StandardScaler`. Logistic Regression, SVM, KNN fail with numerical overflow on large-valued features; exception silently caught.

**Fix:** Added `("scaler", StandardScaler())` to the numerical sub-pipeline. Tree-based models (RF, XGBoost, etc.) are scale-invariant — no effect on them.

### 8. Persist AutoML Results Across Modal Close/Reopen (`e93523a`)

**Problem:** AutoML modal unmounts on close (conditional render). All state lost — user must re-upload and retrain (1–3 min).

**Fix:** Lifted `trainResult` and `history` to `MLCapabilities.tsx`. `AutoMLModal` accepts `initialResult`/`initialHistory`/`onResultChange` props. On mount, if `initialResult` exists, starts on `step = "results"`. Parent holds state in `automlResult`/`automlHistory`. Exported `TrainResult` and `HistoryEntry` types.

### 9. Saved Runs Tab with localStorage (`b12271a`)

**Feature:** Full saved-runs system within the AutoML modal.

- Modal header now has **New Run / Saved** tabs (underline style)
- "Saved" tab shows count badge when runs exist
- Results step has new **"Save Version"** button (ghost-accent, distinct from "Save to Pipeline")
- Saved view groups runs by uploaded filename, each group collapsible with chevron
- Each run row: run number · winner · CV score · date · **Load** button · **X** delete
- **Load** restores `trainResult`, sets `step = "results"`, switches back to wizard
- All saved runs written to `localStorage` under key `"automl_saved_runs"` — survives page refresh
- `SavedRun` type added; `expandedDatasets` Set state for per-dataset collapse

---

## Concepts Explained to User

**Test set vs CV score:**
- 80/20 split at start; CV runs on 80%, test set held out
- CV score used for model selection (unbiased); test set used for final honest evaluation
- Using test set to select winner = test set leakage (inflated reported score)
- 10% gap (76.95% CV → 66.40% test) signals some overfitting

**Why NB had var_smoothing issue:**
- GaussianNB assumes Gaussian features; OHE columns are binary (0/1)
- Rare category → near-zero variance in a fold → divide by zero
- 1e-9 default insufficient; 1e-2 stabilises without meaningful accuracy loss

**Why not vertical bar chart:**
- Long model names (Random Forest, Gradient Boosting) require 45° rotation → hard to read
- Loses leaderboard feel (#1/#2/WINNER badge have no natural home)
- Gets very cramped with 8–12 models

**Why persist results (showAutoMLWizard fix):**
- Modal unmounts on close = state destroyed
- User runs 1–3 min competition, closes to check something, reopens → blank screen
- Lifted state survives unmount; user lands back on results view

---

## Commits This Session

| Hash | Repo | Description |
|---|---|---|
| `478da62` | ml-portfolio | CV scoring in winner banner + AI analysis visual improvements |
| `884f574` | ml-portfolio | Enhanced ranking table: gradient bars + delta column |
| `3751a41` | ml-portfolio | Collapsible AI analysis section |
| `ebc3200` | ml-portfolio | Key input always visible outside collapse |
| `354c8a6` | ml-portfolio | selectedModels added to handleTrain dep array |
| `4ec8852` | ml-portfolio | Expand analysis on Generate start (not complete) |
| `e93523a` | ml-portfolio | Persist trainResult/history across modal close/reopen |
| `b12271a` | ml-portfolio | Saved Runs tab + Save Version button + localStorage |
| `aa243d6` | ML-Unified | StandardScaler in AutoML preprocessing |
| `18f1583` | ML-Unified | GaussianNB var_smoothing=1e-2 |
| HF `32dd2c3` | HF Space | StandardScaler fix deployed |
| HF `e544459` | HF Space | GaussianNB fix deployed |

---

## Current State

### ml-portfolio
- Latest: `b12271a` — live on Vercel Production
- AutoML feature set: model competition, LLM analysis, collapsible UI, saved runs, result persistence

### ML-Unified
- Latest: `18f1583` — pushed to GitHub
- HF Space: running `e544459` (latest)

---

## Pending Backlog

### ml-portfolio
- Step 3: remaining 6 card modals (Preprocessing, Feature Eng, Feature Select, Optuna, SHAP, Ensemble)
- Step 4: Pipeline builder UI

### ML-Unified
- Fix `showAutoMLWizard()` in main frontend — always starts fresh (line ~4566)
- Phase 9: Ensemble / stacking (combine top AutoML models)
- Phase 10: Pipeline export (download as .pkl / Python script)
- Phase 11–13: Encoding options, GPU, SMOTE
- Retrain 80 Cereals model
- Verify AdaBoost winner-training branch exists in app.py

---

## Process Reminders
- NO EMOJIS ever
- Always report short git hash with every commit
- Always push to GitHub after every commit
- HF Space: upload root `app.py` via Python SDK — git push blocked by .pkl binary files
- Playwright: maximize window (1440x900), close after deploy confirmation
