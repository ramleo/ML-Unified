# Conversation — 2026-06-29 — Pipeline Context, Downloads, SHAP Params (Part 136)

## Summary
Continued from Part 135. Fixed CSV context wiring gaps across AutoML, Optuna, SHAP, Ensemble. Added model/params downloads. Implemented Optuna-tuned params usage in SHAP.

---

## Key Work Done

### 1. AutoML CsvFromContextBanner (commit 1aabba7)
- AutoMLModal refactored: 412 → 270 lines (extracted useAutoMLSavedRuns + useAutoMLTrain hooks)
- Added `onReady` prop to expose `handleFile` trigger to page.tsx
- page.tsx: replaced broken `fileRef` with `triggerRef` via `onReady`
- Banner shows "Using FS-selected data · N rows · M cols" with explicit "Use this data →" button

### 2. Optuna / SHAP / Ensemble banners (commit a30c7a2)
- OptunaRunner: 419 → 305 lines (extracted OptunaStepBar + OptunaConfigForm)
- Added `onReady` prop to OptunaRunner, ShapRunner, EnsembleRunner
- All three page.tsx files updated with banner + triggerRef pattern
- Same context chain: fsCsvB64 → feCsvB64 → preprocessedCsvB64 → csvB64

### 3. SHAP pre-select tunedModel (commit e1ed444)
- ShapRunner reads `state.tunedModel` first, then falls back to `state.automlWinner`

### 4. Auto-write automlWinner + remove Save to Pipeline (commit 6c5ab27)
- automlWinner + automlRanking written to context on training completion
- "Save to Pipeline" button removed from Step4Results
- No manual action needed to pass winner to Optuna/SHAP/Ensemble

### 5. Model download + Optuna params download (commits 4d2befc, 47183aa)
- Backend: `GET /model/{model_id}/download` → returns trained pipeline .pkl
- Backend: SHAP endpoint reads `model_params` from request body, returns as `used_params`
- Frontend: "Download Model (.pkl)" button in AutoML Step4Results
- Frontend: "Download Params (JSON)" button in Optuna results (after fix 676bee0)
- Fix: `optuna_params` → `best_params` field mapping in OptunaRunner SSE result parser

### 6. SHAP preset params (commits 0f5c288, 6469c6c)
- SHAP configure step: "Use Optuna-tuned parameters (auto-detected)" checkbox
- Auto-populated from `state.tunedModel.params` when available
- "Upload params JSON" button for manual file upload
- Backend: `preset_params_json` Form field in `/train` → passed through clf/reg → rebuilds winner model with those params

---

## Commits

| Hash | Repo | Description |
|------|------|-------------|
| 1aabba7 | ml-portfolio | AutoML banner + modularize AutoMLModal |
| a30c7a2 | ml-portfolio | Optuna/SHAP/Ensemble banners + modularize OptunaRunner |
| e1ed444 | ml-portfolio | SHAP pre-select tunedModel first |
| 6c5ab27 | ml-portfolio | Auto-write automlWinner on completion; remove Save to Pipeline |
| 4d2befc | ml-portfolio | Download Model + Download Params buttons |
| 676bee0 | ml-portfolio | Fix optuna_params → best_params field mapping |
| 0f5c288 | ml-portfolio | SHAP preset params UI (checkbox + upload JSON) |
| 47183aa | ML-Unified | GET /model/{id}/download + SHAP used_params passthrough |
| 6469c6c | ML-Unified | preset_params_json support in /train endpoint |

---

## Issues / Mistakes
- AutoML banner was raised 3 times before being fixed
- Download Params button was added without verifying field name (`optuna_params` vs `best_params`) — button never rendered until fix
- SHAP upload params option was missing initially — only backend + download were done, upload side was forgotten
- Multiple instances of claiming something was done without verifying first

---

## Pipeline Context Flow (as built)
1. Preprocessing → stores `csvB64`, `preprocessedCsvB64`
2. Feature Engineering → stores `feCsvB64`
3. Feature Selection → stores `fsCsvB64`, `selectedFeatures`
4. AutoML → stores `automlWinner`, `automlRanking` (on train completion, no button needed)
5. Optuna → reads `automlWinner` to pre-select model; stores `tunedModel` (with `params`)
6. SHAP → reads `tunedModel` (Optuna params auto-detected) or `automlWinner`; sends `preset_params_json` to backend
7. Ensemble → reads `automlRanking` to pre-select top 3 models
