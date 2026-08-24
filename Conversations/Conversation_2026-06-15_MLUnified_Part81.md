# Conversation — 2026-06-15 — ML-Unified — SHAP Fix + FE UI Bugs Part 81

---

## Session Summary

Continued from Part 80. Fixed SHAP/What-If, FE UI scroll, chip badge, SHAP note placement, and the FE pkl persistence issue on HF Space. SHAP is now working.

---

## Issues Fixed This Session

### 1. SHAP note placement (commit `9c58470`)
`_shapInfoHTML` ("Why only N features?") moved from after bars to before bars — now visible immediately when SHAP loads. What-If already had it before chips; SHAP now matches.

### 2. Chip badge update on click (commit `9c58470`)
`_toggleFEChipNum` previously only updated chip visual in-place — badge never refreshed. Fixed: now calls `_renderAutoMLStep1c(true)` to re-render with updated badge.

### 3. Scroll restore (commit `9c58470` → refined in `1b56ba6` → `d7b7b6d`)
Single `requestAnimationFrame` wasn't enough — upgraded to double-RAF (`requestAnimationFrame(() => requestAnimationFrame(...))`) so browser has two paint cycles to establish layout before scrollTop is restored.

### 4. Total derived count (commit `1b56ba6`)
Added "Total: N derived columns will be added" summary below all numeric transform rows. Computed via IIFE summing all active chips + bin methods across all columns.

### 5. Binning triggers badge re-render (commit `d7b7b6d`)
`_setBinMethod` previously updated button styles in-place — badge never updated when bin method changed. Fixed: now calls `_renderAutoMLStep1c(true)`.

### 6. Polynomial inner list scroll (commit `d7b7b6d`)
Root cause identified: TWO scroll containers were resetting:
- `#main.scrollTop` (page scroll) — captured/restored via double-RAF
- Inner 140px polynomial checklist — no id, destroyed/recreated on every re-render

Fix: added `id="polyColList"` to inner div; both `_feScr` and `_polyScr` captured before re-render, both restored in double-RAF.

### 7. FE pkl persistence across HF restarts (commits `f866664`)

**Root cause:** `titanic_fe.pkl` was never in `_HF_PKL_FILES`, so `_fetch_hf_models()` never downloaded it on restart. After restart, `_load()` fell back to `FeatureEngineeringTransformer({})` (empty config), skipping FE entirely. ColumnTransformer then failed with "columns are missing".

**Fix:**
- `_fetch_hf_models()` now scans SCHEMA_DIR for all `.json` files and tries to download their `_fe.pkl` from HF XET
- New `_upload_model_to_hf(model_id)` function: called after every `/train` save — uploads pipeline.pkl, fe.pkl, labels.pkl, schema.json to HF XET
- Requires `HF_TOKEN` secret set in HF Space Settings → Repository secrets (write token)

**After user set HF_TOKEN and retrained:** SHAP now works ✓

### 8. Debug session (commit `3126e44` → reverted)
Temporarily surfaced FE transform exception in SHAP error message to diagnose the issue. Reverted after SHAP confirmed working.

---

## Gemini/Groq LLM Issue (not fixed, investigation only)

- `gemini-3.5-flash` is valid and working (released May 19, 2026)
- `gemini-2.5-flash` and Groq `llama-3.3-70b-versatile` stopped working "since yesterday"
- Code itself is syntactically correct
- The `except Exception: return None` in `_llm_explanation` silently eats errors
- Likely a provider-side change (model deprecation/rename) or API key issue
- User said "only check, don't modify" — not fixed

---

## All Commits This Session

| Hash | Description | GitHub | HF |
|------|-------------|--------|----|
| `9c58470` | fix(ui): SHAP note above bars; chip click re-renders badge; rAF scroll restore | ✓ | ✓ |
| `1b56ba6` | fix(fe-ui): double-RAF scroll restore; total derived count below numeric section | ✓ | ✓ |
| `f866664` | fix(train): upload fe.pkl to HF XET after training; fetch fe.pkl on startup | ✓ | ✓ |
| `d7b7b6d` | fix(fe-ui): bin method triggers re-render; preserve polyColList inner scroll | ✓ | ✓ |
| `3126e44` | debug(shap): surface FE transform exception (temporary) | ✓ | ✓ |
| pending | revert(shap): restore silent FE error handling | pending | pending |

---

## HF Token Setup
- User added `HF_TOKEN` to HF Space Secrets (Settings → Repository secrets)
- Token needs **write** access to the Space
- After retraining, `_upload_model_to_hf()` uploads pkl files automatically

---

## SHAP Result (after fix)
New Titanic model (LightGBM, 0.868 score) shows:
- Fare: -0.874 (most negative impact)
- Sex_male: -0.507
- Embarked_S: -0.201
- Various Cabin columns: +0.000 (low importance)

Feature selection dropped Age, Pclass, SibSp from the final model this time.

---

## Pending Items

| Phase | Item | Status |
|-------|------|--------|
| — | Revert debug shap.py (commit + push + HF upload) | **Next** |
| — | Verify What-If works after retrain | **Next** |
| — | Fix gemini-2.5 and groq LLM (user to investigate model names) | Deferred |
| — | Show all FE-derived SHAP bars separately (e.g. "Age_rank ↳ from Age") | Planned |
| 7 | Regression confidence intervals | Not started |
| 8 | Optuna hyperparameter tuning | Not started |
| 9 | Ensemble / stacking | Not started |
| 10 | Pipeline export | Not started |
| 11 | Encoding per-column | Not started |
| 12 | GPU toggle | Not started |
| 13 | SMOTE | Not started |
