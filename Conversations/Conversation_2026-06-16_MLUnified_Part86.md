# Conversation — 2026-06-16 — ML-Unified — Part 86

---

## Session Summary

Fixed multiple resource estimate card issues, introduced Playwright screenshot verification workflow.

---

## Issues Fixed

### 1. 80 Cereals model vanished (explanation only)
Trained before app.py was deployed to HF Space — `_upload_model_to_hf` never ran. User needs to retrain now that app.py is live.

### 2. Total RAM visually in AutoML Time section (commit `6cff914`)
Added `sectionSep` (2px border) between RAM block and Time block in `_updateResourceCard`.

### 3. Resource estimate doesn't reflect FE-derived columns (commit `c2a13d2`)
- Added `_countFEDerivedCols()` — reads `_automlFeatureEng` and counts all numeric transforms, date features, interaction terms, polynomial pairs
- `_updateResourceCard` recomputes `_estimateResources` with `origCols + feDerived` on every render
- Stored `_amlResBase = { rows, nCols, nCatCols }` in RAF callback for recomputation
- Added "FE Columns" row to card

### 4. Trials not changing time estimate (commit `e77ddc2`)
- Added `Math.max(1.5, ...)` floor to `oneTrialSecs` — small datasets computed ~0.004s/trial → rounded to 0
- Moved FE Columns row to top of card (it was appearing after Total Time, looked like part of time section)

### 5. FE Columns showed only derived count (commit `f18bf7d`)
Changed to `"N original + M derived = total"` format.

### 6. Total Time and CV Folds cramped — no separator (commit `eac3084`)
Added `${doTune ? sepRow : ''}` after `${timeRows}` in `grid.innerHTML`.

---

## Playwright Verification Workflow (new process)

From this session forward: UI changes must be screenshot-verified with Playwright before deploying.

Process:
1. Apply fix to local file
2. Start local uvicorn server (`python -m uvicorn app:app --port 7861`)
3. Use Playwright MCP to navigate, interact, and screenshot
4. Show screenshot in conversation
5. Only deploy after user approves

Verified in this session:
- Resource card with Optuna ON: correct bifurcated layout
- Trials 10 → 20 → 30: Optuna Time and Total Time update correctly

| Trials | Optuna Time | Total Time |
|--------|-------------|------------|
| 10 | +~15s | ~28s |
| 20 | +~30s | ~43s |
| 30 | +~45s | ~58s |

---

## All Commits This Session

| Hash | Description | GitHub | HF |
|------|-------------|--------|----|
| `6cff914` | fix(automl): section separator between RAM and Time blocks | ✓ | ✓ |
| `c2a13d2` | feat(automl): resource estimate reflects FE-derived columns in real time | ✓ | ✓ |
| `e77ddc2` | fix(automl): min 1.5s/trial floor; FE Columns row moved to top | ✓ | ✓ |
| `f18bf7d` | fix(automl): columns row shows original + derived = total | ✓ | ✓ |
| `eac3084` | fix(automl): separator after Total Time; trials update live | ✓ | ✓ |

---

## Pending Items

| Priority | Item | Status |
|----------|------|--------|
| Next | Phase 9: Ensemble / stacking | Not started |
| Low | Phase 10: Pipeline export | Not started |
| Low | Phase 11: Encoding per-column | Not started |
| Low | Phase 12: GPU toggle | Not started |
| Low | Phase 13: SMOTE | Not started |
| User action | Retrain 80 Cereals model (lost before app.py was on HF) | Pending |

---

## Playwright Rules (saved to memory)

- **Maximize window** immediately after `browser_navigate`, before any screenshots
- **Close browser** after user confirms deploy — use `browser_close`
- Memory saved: `feedback_playwright_workflow.md`

---

## Process Notes

- HF refreshing frequently today: caused by multiple app.py + requirements.txt uploads triggering full Space rebuilds (optuna install)
- Login prompt appears daily: Claude Code auth token expiry — expected behavior, just re-login
- Local server for Playwright testing: `cd services/ml-api && python -m uvicorn app:app --port 7861`
