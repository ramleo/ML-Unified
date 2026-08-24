# Conversation — 2026-06-17 — ML-Unified — Part 94

---

## Session Summary

Resumed from Part 93. Deployed all pending features from previous session, then fixed 3 issues reported by user via screenshots. Identified 3 UX gaps for future work.

---

## Completed This Session

### 1. Resumed and deployed pending work from Part 93

All 5 features were already implemented locally (uncommitted). After compact:

| Hash | Repo | Description |
|---|---|---|
| `5e11d30` | ml-portfolio | ML model selection toggles + custom LLM endpoint + model comparison chart |
| `da09aae` | ML-Unified | ML model selection + custom LLM endpoint in backend |
| `39d4007` | ml-portfolio | Line chart + Run Again fix + model override field |
| `e07773a` | ML-Unified | custom_model overrides default model for all LLM providers |
| HF `d656f30` | HF Space | app.py from da09aae uploaded |
| HF `50fb6ab` | HF Space | app.py from e07773a uploaded |

### 2. Three user-reported issues fixed (commit `39d4007`)

**Issue 1 — Run Again shows stale analysis from previous run:**
- Root cause: `llmExp` state never cleared when "Run Again" clicked
- Fix: added `setLlmExp(null); setLlmProgress(0)` to Run Again onClick (line 896)

**Issue 2 — Bar chart still showing (user wanted line graph):**
- Root cause: `ModelComparisonChart` used horizontal CSS bars
- Fix: replaced with SVG dot-and-line chart. X-axis = model names (sorted by score desc), Y-axis = 0-100. Dots colour-coded (green ≥80, yellow ≥60, red <60). Score number above each dot. Grid lines at 0/25/50/75/100. Descriptions listed below chart with coloured dot indicators.

**Issue 3 — No model name field when using own key with non-custom provider:**
- Root cause: model name input only rendered when `llmProvider === "custom"`
- Fix: split into two conditions:
  - Base URL input: still `llmProvider === "custom"` only
  - Model name input: `showKeyInput || llmProvider === "custom"` — shows whenever own key is toggled
- Placeholder adapts: "Model override (optional, e.g. gpt-4o, claude-opus-4-8)" for standard providers
- Backend (`e07773a`): each provider branch now uses `custom_model or "default"` pattern

### 3. Confirmed live

- Line chart visible in screenshot (green/yellow/red dots, descending line)
- Vercel deployment `39d4007` confirmed Production/Ready

---

## UX Gaps Identified (deferred, analysis only)

### 1. Model fitness — no explanation
- "Model Fitness for this Dataset" heading gives no context for the 0-100 score
- Users don't know it's LLM-rated, based on CV accuracy + fold stability
- Fix options: subtitle under heading, or info icon with tooltip
- Suggested copy: "Fitness is an LLM-rated 0-100 score based on cross-validation accuracy and fold stability."

### 2. No option to add ML models
- Config step has toggles to select from existing 5 — cannot add new algorithm types
- Recommended approach: **curated additions** (not free-form entry)
- Candidates: Logistic Regression, SVM, KNN, Decision Tree, Naive Bayes, Ridge
- Each needs: frontend pill toggle + backend CV block + winner branch

### 3. Own key UX is unclear
- "Own key" button label is cryptic
- No per-provider hint for where to get the key
- No explanation of why to use own key vs server key
- Fix: rename to "Use my API key", add per-provider hint (e.g. "aistudio.google.com"), add one-liner about rate limits

---

## Current State

### ml-portfolio
- Latest: `39d4007` — live on Vercel Production
- All AutoML features complete: ML toggles, LLM dropdown, custom endpoint, own key + model, line chart, Run Again fix

### ML-Unified
- Latest: `e07773a` — pushed to GitHub
- HF Space: running latest app.py, health OK

---

## Pending Items (Longer Term)

### ml-portfolio — Steps 3-4
- Step 3: Remaining 6 card modals (Preprocessing, Feature Eng, Feature Select, Optuna, SHAP, Ensemble)
- Step 4: Pipeline builder UI
- UX gaps above (model fitness tooltip, add ML models, own key clarity)

### ML-Unified — Queued
- Fix `showAutoMLWizard()` — always start fresh (line ~4566)
- Phase 9: Ensemble / stacking
- Phase 10–13: Pipeline export, Encoding, GPU, SMOTE
- Retrain 80 Cereals model

---

## Process Reminders
- NO EMOJIS ever
- Always report short git hash with every commit
- Always push to GitHub after every commit
- HF Space: upload root `app.py` via Python SDK (git push blocked by .pkl binary files)
- Playwright: maximize window (1440x900), close after deploy confirmation
