# Conversation — 2026-06-16 — ML-Unified — Part 84

---

## Session Summary

Continued from Part 83. Fixed two bugs reported by user: (1) newly trained model disappears on page refresh, (2) newly trained model vanishes when Sample Projects dropdown is toggled.

---

## Issues Fixed This Session

### Bug 1: New model disappears on page refresh

**Root cause:** `app.py` was never uploaded to HF Space — all backend changes from Part 83 (actuals saving, `_upload_model_to_hf`, delete endpoint fix) existed only on GitHub, not on the running HF Space. So after training, `_upload_model_to_hf` never ran, model was never persisted to HF XET, and disappeared on restart/refresh.

**Fix:** Uploaded `services/ml-api/app.py` directly to HF Space at `path_in_repo='services/ml-api/app.py'`. Space restarted with the current app.py. Now `_upload_model_to_hf` will run after every `/train` call, persisting pipeline/fe/labels/schema/actuals to HF XET.

**Action required from user:** Retrain a model to confirm persistence across page refresh.

---

### Bug 2: New model vanishes when Sample Projects dropdown is toggled (commit `b627119`)

**Symptom:** After training a custom model, it appears in the sidebar. Clicking Sample Projects dropdown to close it hides the custom model too.

**Root cause:** `_modelBtnHTML(m, hidden)` always added `sample-item` CSS class to every button. `toggleSampleProjects()` runs `document.querySelectorAll('#sidebar .sample-item').forEach(el => el.classList.toggle('hidden', isOpen))` — which caught custom model buttons too.

**Fix:**
- Added `isSample` parameter to `_modelBtnHTML(m, hidden, isSample)`
- Only adds `sample-item` class when `isSample=true`
- Custom models called with `customModels.map(m => _modelBtnHTML(m, false, false))`
- Builtin models called with `builtinModels.map(m => _modelBtnHTML(m, !samplesOpen, true))`

**Before:**
```javascript
function _modelBtnHTML(m, hidden) {
  return `<button class="model-btn sample-item${hidden ? ' hidden' : ''}" ...>`;
}
const customSection = ... + customModels.map(_modelBtnHTML).join('');
```

**After:**
```javascript
function _modelBtnHTML(m, hidden, isSample) {
  return `<button class="model-btn${isSample ? ' sample-item' : ''}${hidden ? ' hidden' : ''}" ...>`;
}
const customSection = ... + customModels.map(m => _modelBtnHTML(m, false, false)).join('');
// builtins:
builtinModels.map(m => _modelBtnHTML(m, !samplesOpen, true)).join('')
```

---

## All Commits This Session

| Hash | Description | GitHub | HF frontend | HF app.py |
|------|-------------|--------|-------------|-----------|
| `b627119` | fix(sidebar): custom model buttons no longer hidden when Sample Projects toggled | ✓ | ✓ | — |
| — | (no commit) app.py uploaded directly to HF Space | — | — | ✓ |

---

## State at End of Session

| Feature | Status |
|---------|--------|
| Bug 2: custom models hidden by toggle | **Fixed** ✓ |
| Bug 1: model disappears on refresh | **Fixed** (app.py live on HF — user needs to retrain once to confirm) |
| Performance tab (Phase 7 scatter plot) | Code complete in app.py, now live on HF — works for regression models retrained after this session |
| Phase 8–13 | Not started |

---

## Pending Items

| Priority | Item | Status |
|----------|------|--------|
| **Next** | User to retrain a regression model to confirm Bug 1 fix + Performance tab | Awaiting user |
| Medium | Phase 8: Optuna hyperparameter tuning | Not started |
| Medium | Phase 9: Ensemble / stacking | Not started |
| Low | Phase 10: Pipeline export | Not started |
| Low | Phase 11: Encoding per-column | Not started |
| Low | Phase 12: GPU toggle | Not started |
| Low | Phase 13: SMOTE | Not started |

---

## Critical Behavioral Notes (carry forward)

- Always report short git hash with every commit
- Always push to GitHub (`git push origin main`) after every commit
- Always upload to HF Space after every commit:
  - Frontend: `path_in_repo='frontend/index.html'`
  - Backend: `path_in_repo='services/ml-api/app.py'` ← CRITICAL, missed for entire Part 83 session
- HF token: `<REDACTED_HF_TOKEN>`, repo: `wram1708/ml-unified`
- Ruff: `/Users/wrks/Downloads/Claude-documentation/Projects/ML-Unified/.venv/bin/ruff` — run before every app.py commit
