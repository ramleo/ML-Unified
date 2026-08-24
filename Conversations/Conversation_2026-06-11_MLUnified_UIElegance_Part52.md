# Conversation — 2026-06-11 — ML-Unified UI Elegance — Part 52

---

## Session Summary

Continuation from Part 51. Investigated "Loading models..." hang, found root cause (TDZ bug),
fixed it, but uncovered a second issue (port scan timeout on Render). Rolled back all changes
to `d8e62dd` baseline. App confirmed working after rollback.

---

## Root Causes Found

### 1. JavaScript TDZ Bug (Frontend)

**Error in browser console:**
```
Uncaught ReferenceError: Cannot access 'THEMES' before initialization
    at setThemeChoice (line 1661)
    at setTheme (line 1690)
    at line 1641
    at line 1649
```

**Cause:** During ui-elegance, a full theme system (`const THEMES = {...}`) was added after an
existing IIFE that called `setTheme()`. The IIFE ran before `const THEMES` was declared —
JavaScript temporal dead zone (TDZ) crash. `init()` never ran, so `/models` was never fetched,
so "Loading models..." hung forever.

**Fix attempted (commit `e1a4a8b`):** Deleted the stale IIFE (lines 1637-1649) since the second
IIFE at line 1696 already handled the same logic correctly after `THEMES` was declared.

**Why fix didn't take effect:** The Render deploy for `e1a4a8b` failed (port scan timeout),
so Render kept serving the old broken version.

---

### 2. Port Scan Timeout (Backend)

**Render log:**
```
==> Port scan timeout reached, no open ports detected. Bind your service to at least one port.
```

**Cause:** After the lazy loading commit (`510ba19`), uvicorn never bound to a port within
Render's timeout window. The server was likely crashing during startup before it could listen.
Root cause of the crash was not fully diagnosed — most likely the lazy loading `app.py` change
introduced a startup error (e.g. `_load()` failing before the server could bind).

**Effect:** Every deploy after `510ba19` failed at the deployment stage (build succeeded,
deploy failed). Render kept serving the last successful deploy (the one with the TDZ bug).

---

## Commits This Session

| Hash | Description |
|------|-------------|
| `e1a4a8b` | fix: remove stale IIFE causing TDZ crash — deploy FAILED (port scan timeout) |
| `8e70e62` | revert: rollback frontend and backend to pre-ui-elegance state (d8e62dd) |

---

## Rollback Details

Rolled back to `d8e62dd` (last commit before ui-elegance branch):

```bash
git checkout d8e62dd -- services/ml-api/frontend/index.html \
                        services/ml-api/app.py \
                        services/ml-api/routers/shap.py \
                        services/ml-api/routers/pipeline.py \
                        services/ml-api/routers/drift.py
git commit -m "revert: rollback frontend and backend to pre-ui-elegance state (d8e62dd)"
git push origin main
```

Files restored to baseline:
- `services/ml-api/frontend/index.html` — pre-ui-elegance UI
- `services/ml-api/app.py` — original startup (no lazy loading)
- `services/ml-api/routers/shap.py` — original
- `services/ml-api/routers/pipeline.py` — original
- `services/ml-api/routers/drift.py` — original

**App confirmed working after rollback** — models load correctly.

---

## What Was Lost (can be re-applied)

All ui-elegance commits are still in git history. Changes to re-apply carefully:

### Frontend (index.html)
1. oklch smooth gradient transitions
2. btn-primary uses model accent (`--active-accent`)
3. Eyebrow/metric use theme color (`--accent-from`), inline style removed from JS template
4. Transparent cards — Outcome, Feature Impact, Pipeline, What-if, Drift
5. Remove result-accent-bar (green left-edge artifact)
6. Cold-start UX: spinner + "Server waking up" message after 5s
7. **TDZ fix**: move the early `setTheme()` IIFE to AFTER `const THEMES` declaration

### Backend (app.py + routers)
- Lazy model loading (`_load()` only loads schemas/labels; `_ensure_pipeline()` loads pkl on demand)
- Must verify this doesn't cause port scan timeout before deploying

---

## Lessons Learned

1. **Test each backend change on Render separately** — lazy loading caused a port scan timeout
   that blocked all subsequent deploys
2. **Render port scan timeout = server never started** — check uvicorn startup logs, not just build
3. **Browser cache** — hard refresh (Cmd+Shift+R) doesn't always clear; check Network tab
   to confirm which file version is being served
4. **Render keeps old version on failed deploy** — if deploy fails, old broken version stays live
5. **TDZ (Temporal Dead Zone)**: `const`/`let` variables throw ReferenceError if accessed before
   their declaration line executes — even if the accessing code is in a hoisted function

---

## Plan for Re-applying UI Elegance

Apply and test on Render one commit at a time:
1. Frontend CSS changes (safe, no JS ordering issues)
2. Frontend JS changes (remove inline styles from renderMain template)
3. TDZ fix (move IIFE, don't delete it)
4. Cold-start UX message
5. Backend lazy loading LAST — verify server starts before merging

---

## Current State

- `main` branch on GitHub: `8e70e62` (rollback to d8e62dd baseline)
- Render: deployed and live, models loading correctly
- All ui-elegance work preserved in git history (commits `1ba43c0` through `e1a4a8b`)
