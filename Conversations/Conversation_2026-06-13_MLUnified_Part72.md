# Conversation — 2026-06-13 — ML-Unified — AutoML AI Explanation Dashboard Part 72

---

## Session Summary

Fixed the AI Explanation two-column dashboard (charts + SHAP border), and discovered the root HF deployment path bug that had been silently breaking all previous HF uploads.

---

## Issues Fixed

### Fix 1 — AI Explanation Charts Blank (Root Cause: CSS Transition Override)

**Problem:** Model CV Scores and Feature Importance bars were invisible in the explanation panel right column.

**Root cause (previous session):** Missing closing `}` on `_renderExplanationDashboard` caused a JS syntax error (commit `3684699` fixed this).

**Root cause (this session):** Even with the brace fixed, the bars used `.aml-algo-fill` CSS class which has `width: 0%; transition: width 0.75s`. When these elements were inserted into the DOM with inline `style="width:70%"`, some browsers start the transition from 0%→70%. There may have been an interaction causing them to stay invisible.

**Fix:** Replaced all explanation dashboard bar HTML with pure inline styles — no CSS class on fill divs, no transition dependency. Tracks and fills are built entirely with `style="..."` attributes.

```javascript
// Before (used shared CSS class with transition):
<div class="aml-algo-fill" style="width:${pct}%;${fill}"></div>

// After (pure inline, no class, no transition):
<div style="height:28px;background:rgba(255,255,255,0.08);border-radius:6px;overflow:hidden">
  <div style="height:100%;width:${pct}%;background:${fillBg};border-radius:6px"></div>
</div>
```

**Commit:** `2a29bad` (GitHub)

---

### Fix 2 — SHAP Analyzer Button Prominent Blue Border

**Problem:** SHAP Analyzer sidebar button had a full-opacity blue dashed border, much more prominent than AutoML button.

**Root cause:** `border-color:var(--accent-from)44` is invalid CSS — you cannot append a hex alpha value after a CSS variable reference. The browser ignored the opacity, rendering the border at full opacity.

**Fix:** Replaced with hardcoded 8-digit hex: `border-color:#818cf844` (27% opacity purple).

```html
<!-- Before (invalid CSS): -->
style="margin-top:0.35rem;border-color:var(--accent-from)44;color:var(--accent-from)"

<!-- After (valid hardcoded hex): -->
style="margin-top:0.35rem;border-color:#818cf844;color:#818cf8"
```

**Commit:** `c30d423` (GitHub)

---

### Fix 3 — CRITICAL: HF Space Deployment Was Using Wrong File Path

**Problem:** All uploads via `upload_file()` appeared to succeed but the live Space never reflected changes.

**Root cause:** The HF Space repo has a **different directory structure** from the GitHub monorepo:
- GitHub repo: `services/ml-api/frontend/index.html`
- HF Space repo: `frontend/index.html` (at repo root)

The `upload_file()` calls were uploading to `services/ml-api/frontend/index.html` which exists in the HF repo (as a dead file) but is NOT the file the Dockerfile copies. The Dockerfile at the HF root does `COPY frontend/ frontend/` — reading from the root-level `frontend/` only.

**How discovered:** Used Playwright to verify served HTML vs local file. Content hashes didn't match. Then used HF API to list the HF Space repo root and found `frontend/` at root, separate from `services/`.

**Fix:** Always upload to `frontend/index.html` (HF repo root):

```python
upload_file(
    path_or_fileobj='/Users/wrks/.../services/ml-api/frontend/index.html',
    path_in_repo='frontend/index.html',   # ← correct HF path
    repo_id='wram1708/ml-unified',
    repo_type='space',
    token='<REDACTED_HF_TOKEN>',
)
```

**HF commit:** `994c209`

---

## Playwright Usage (New Capability Discovered)

Used Playwright MCP tool to:
1. Navigate directly to `https://wram1708-ml-unified.hf.space/`
2. Evaluate JS (`getComputedStyle`) to check actual rendered border
3. Fetch page with `cache: 'no-store'` to bypass browser cache
4. Check which version of JS was running in the page

---

## HF Deployment Reference (Critical)

| Item | Value |
|------|-------|
| Space URL | https://huggingface.co/spaces/wram1708/ml-unified |
| Live URL | https://wram1708-ml-unified.hf.space/ |
| Token | `<REDACTED_HF_TOKEN>` (in git remote `hf`) |
| **Correct upload path** | `frontend/index.html` |
| **Wrong path (dead file)** | `services/ml-api/frontend/index.html` |
| Check build status | `curl -s "https://huggingface.co/api/spaces/wram1708/ml-unified"` |
| Force restart | `curl -X POST ".../restart?factory=true" -H "Authorization: Bearer <token>"` |

**Render:** Deploys from GitHub `main`. Uses `services/ml-api/frontend/index.html` — normal monorepo path. Git push to GitHub is sufficient.

---

## All Commits This Session

| Hash | Description | Where |
|------|-------------|-------|
| `3684699` | fix(automl): add missing closing brace on _renderExplanationDashboard | GitHub |
| `c30d423` | fix(ui): SHAP sidebar button border | GitHub |
| `2a29bad` | fix(automl): explanation bars use pure inline styles to bypass CSS transition issue | GitHub |
| `2f101e1` | fix: force rebuild marker comment | GitHub |
| `994c209` | fix(automl): inline bars + SHAP border — correct HF path | HF Space |

---

## Pending Items (Agreed Order)

| Phase | Item | Status |
|-------|------|--------|
| — | High-cardinality numeric column fix (`!c.is_numeric` in `_renderAutoMLStep1b`) | **Next up** |
| 2 | Task type detection improvement | Not started |
| 3 | Validation set split visibility | Not started |
| 4 | Resource estimation (RAM/time warning) | Not started |
| 5 | Feature Engineering step | Not started |
| 6 | SHAP values | Not started |
| 7 | Regression confidence intervals | Not started |
| 8 | Optuna hyperparameter tuning | Not started |
| 9 | Ensemble / stacking | Not started |
| 10 | Pipeline export | Not started |
| 11 | Encoding per-column | Not started |
| 12 | GPU toggle | Not started |
| 13 | SMOTE | Not started |

---

## High-Cardinality Fix (Next Session)

Add `!c.is_numeric` to the frontend filter in `_renderAutoMLStep1b()` to prevent numeric columns like Age and Fare from appearing in the "drop high-cardinality column" list:

```javascript
const highCardCols = a.columns.filter(c =>
  c.name !== effectiveTarget && !c.is_numeric && (c.nunique || 0) > 20
);
```
