# Conversation — 2026-06-11 — ML-Unified UI Elegance — Part 51

---

## Session Summary

Continuation of UI elegance work. All changes on `ui-elegance` branch, then merged to `main`.

---

## Commits This Session (all on `ui-elegance` → merged to `main`)

| Hash | Description |
|------|-------------|
| `1ba43c0` | Smooth gradient transitions using oklch perceptual color space |
| `4ba005d` | btn-primary uses model accent so Predict button matches Fill Sample |
| `de1f239` | Eyebrow/metric use theme color (var(--accent-from)); accent bar uses CSS var gradient |
| `edeb3a8` | Result and SHAP cards use translucent glass (55% opacity + backdrop-blur) — DIDN'T WORK visually |
| `3030bba` | Result and SHAP cards fully transparent, only subtle border remains |
| `805bce3` | Remove result-accent-bar — was causing green left-edge artifact on transparent card |
| `c2e24fe` | Transparent backgrounds for Pipeline, What-if and Drift panels |
| `186f172` | Cold-start UX: show spinner + "Server waking up" message after 5s |
| `510ba19` | Lazy-load model pipelines on first request (perf: cut cold-start time) — backend |

---

## Detailed Frontend CSS/JS Changes

### 1. Gradient Transitions — oklch (`1ba43c0`)

Changed all `linear-gradient` calls from sRGB to oklch for perceptually smooth hue transitions:

```css
/* Before */
.gradient-top-bar { background: linear-gradient(90deg, var(--accent-from), var(--accent-via), var(--accent-to)); }
.gradient-text { background: linear-gradient(135deg, var(--accent-from) 0%, var(--accent-via) 50%, var(--accent-to) 100%); }
.nav-logo-mark { background: linear-gradient(135deg, var(--accent-from), var(--accent-via), var(--accent-to)); }
.btn-primary { background: linear-gradient(135deg, var(--accent-from), var(--accent-via)); }

/* After */
.gradient-top-bar { background: linear-gradient(in oklch to right, var(--accent-from), var(--accent-via), var(--accent-to)); }
.gradient-text { background: linear-gradient(in oklch 135deg, var(--accent-from) 0%, var(--accent-via) 50%, var(--accent-to) 100%); }
.nav-logo-mark { background: linear-gradient(in oklch 135deg, var(--accent-from), var(--accent-via), var(--accent-to)); }
.btn-primary { background: linear-gradient(in oklch 135deg, var(--accent-from), var(--accent-via)); }
```

### 2. btn-primary Uses Model Accent (`4ba005d`)

The Predict button was using theme gradient while Fill Sample used model accent — looked jarring.

```css
/* Before */
.btn-primary { background: linear-gradient(in oklch 135deg, var(--accent-from), var(--accent-via)); color: #fff; box-shadow: 0 4px 16px color-mix(in srgb, var(--accent-from) 35%, transparent); }

/* After */
.btn-primary { background: var(--active-accent, var(--accent-from)); color: #fff; box-shadow: 0 2px 10px color-mix(in srgb, var(--active-accent, var(--accent-from)) 20%, transparent); }
```

This makes Predict button match Fill Sample (both use model accent color).

### 3. Eyebrow + Metric Use Theme Color (`de1f239`)

**Problem**: `renderMain()` JS template had inline `style="color:${m.accent}"` which overrode CSS variables.

**Fix — CSS:**
```css
.model-eyebrow {
  font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.1em; margin-bottom: 0.55rem;
  color: var(--accent-from);  /* ADDED */
}
.metric-val { font-size: 1.75rem; font-weight: 800; line-height: 1; color: var(--accent-from); }  /* ADDED color */
```

**Fix — JS (in renderMain() template literal):**
```js
// Before:
<div class="model-eyebrow" style="color:${m.accent}">...</div>
<div class="metric-val" style="color:${m.accent}">${m.metric}</div>

// After (inline style removed so CSS var takes effect):
<div class="model-eyebrow">...</div>
<div class="metric-val">${m.metric}</div>
```

**Accent bar changed from hardcoded hex to CSS var gradient:**
```css
/* Before */
.result-accent-bar { height: 3px; }
/* In JS: style="background:${m.accent}" */

/* After */
.result-accent-bar { height: 3px; background: linear-gradient(in oklch to right, var(--active-accent, var(--accent-from)), color-mix(in srgb, var(--active-accent, var(--accent-from)) 30%, transparent)); }
/* In JS: style attribute removed entirely */
```

### 4. Transparent Cards (`3030bba`, `805bce3`, `c2e24fe`)

**Outcome card (.result-state):**
```css
/* Before */
.result-state {
  display: none;
  background: var(--bg-card);
  border: 1px solid var(--border2);
  border-radius: 16px; overflow: hidden;
  box-shadow: var(--shadow-lg);
}

/* After */
.result-state {
  display: none;
  background: transparent;
  border: 1px solid var(--border2);
  border-radius: 16px; overflow: hidden;
  box-shadow: none;
}
```

**SHAP Feature Impact panel (.shap-panel):**
```css
/* Before */
.shap-panel {
  display: none;
  margin-top: 0.6rem;
  background: var(--bg-card);
  border: 1px solid var(--border2);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: var(--shadow-lg);
}

/* After */
.shap-panel {
  display: none;
  margin-top: 0.6rem;
  background: transparent;
  border: 1px solid var(--border2);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: none;
}
```

**Result accent bar removed (`805bce3`):**
```css
.result-accent-bar { display: none; }
```

**Pipeline cards (`c2e24fe`):**
```css
/* Before */
.pipe-card {
  background: var(--bg-card);
  border: 1px solid var(--border2);
  border-left: 3px solid var(--active-accent, var(--accent-from));
  box-shadow: var(--shadow);
}
.pipe-card-header { background: color-mix(in srgb, var(--active-accent, var(--accent-from)) 5%, transparent); }
.pipe-branch { background: var(--bg); border: 1px solid var(--border2); }

/* After */
.pipe-card { background: transparent; border: 1px solid var(--border2); box-shadow: none; }
.pipe-card-header { background: transparent; }
.pipe-branch { background: transparent; border: 1px solid var(--border2); }
```

**What-if cards (`c2e24fe`):**
```css
/* Before */
.train-card { background: var(--bg-card); border: 1px solid var(--border2); border-radius: 14px; padding: 1.25rem 1.35rem; margin-bottom: 1.25rem; box-shadow: var(--shadow); }

/* After */
.train-card { background: transparent; border: 1px solid var(--border2); border-radius: 14px; padding: 1.25rem 1.35rem; margin-bottom: 1.25rem; }
```

**Drift cards (`c2e24fe`):**
```css
/* Before */
.drift-summary { background: var(--bg-glass); backdrop-filter: blur(6px); }
.drift-feature { background: var(--bg-card); }

/* After */
.drift-summary { background: transparent; }
.drift-feature { background: transparent; }
```

---

## Key Design Decisions Reached

1. **Theme controls**: eyebrow text, metric value, tab underlines, nav, global UI → `var(--accent-from)`
2. **Model controls**: prediction outcome color, SHAP bars, confidence bars, Predict/Fill Sample buttons → `var(--active-accent)`
3. **Cards**: fully transparent, only border outlines — content floats on ambient background
4. **Gradients**: oklch color space for all multi-stop gradients

---

## Issues Encountered

### Green left-edge line on Outcome card
- **Cause**: `result-accent-bar` with `linear-gradient(to right, green, transparent)` read as left accent
- **Fix**: `display: none` on `.result-accent-bar`

### Eyebrow still showing model color after CSS fix
- **Cause**: inline `style="color:${m.accent}"` in JS template overrode CSS class
- **Fix**: removed inline style from JS, CSS var takes effect

### 55% transparent cards showed no difference
- **Cause**: `--bg-card` and `--bg` are both very dark, 55% opacity of dark on dark = looks same
- **Fix**: `background: transparent` entirely

### Model accent bleeding into theme (Titanic cyan showing in Forest green)
- **Cause**: `setProperty('--accent', modelMeta.accent)` in JS overriding theme CSS
- **Fix**: removed, model only sets `--model-accent` and `--active-accent`

---

## Backend Changes (KEEP THESE)

### shap.py — LinearExplainer zero baseline
```python
# Before (all-zero SHAP values for Iris):
explainer = shap.LinearExplainer(model, X_prep)

# After:
explainer = shap.LinearExplainer(model, np.zeros_like(X_prep))
```

### app.py — Lazy model loading
```python
def _load():
    """Load only schemas at startup — pipelines are loaded lazily on first request."""
    for fname in sorted(os.listdir(SCHEMA_DIR)):
        if not fname.endswith(".json"):
            continue
        mid    = fname[:-5]
        schema = json.load(open(os.path.join(SCHEMA_DIR, fname)))
        le_path = os.path.join(MODEL_DIR, f"{mid}_labels.pkl")
        le = joblib.load(le_path) if os.path.exists(le_path) else None
        MODELS[mid] = {
            "pipeline": None,   # loaded on first predict/shap request
            "le":       le,
            "classes":  le.classes_.tolist() if le is not None else None,
            "schema":   schema,
        }

def _ensure_pipeline(mid: str):
    """Load and cache the pipeline pkl on first use."""
    if MODELS[mid]["pipeline"] is None:
        MODELS[mid]["pipeline"] = joblib.load(
            os.path.join(MODEL_DIR, f"{mid}_pipeline.pkl")
        )
```

`_ensure_pipeline(model_id)` called in:
- `app.py` → `predict()` endpoint
- `routers/shap.py` → `compute_shap()`
- `routers/pipeline.py` → `get_pipeline()`
- `routers/drift.py` → `get_drift()` and `upload_drift()`

---

## Pending — Rollback Plan

User wants to rollback frontend UI to `d8e62dd` (last commit before ui-elegance) while keeping:
- `shap.py` LinearExplainer fix
- `app.py` lazy loading
- `routers/` `_ensure_pipeline` calls

**Strategy**: restore `index.html` from `d8e62dd`, keep all backend files as-is.
```bash
git checkout d8e62dd -- services/ml-api/frontend/index.html
git commit -m "revert: restore index.html to pre-ui-elegance state"
git push origin main
```

---

## Pending Tasks (after rollback)

- #22 Dockerize full application
- #20 Playwright E2E tests
- Deferred: #19 MLflow, #11 Cleaned CSV download, #21 Batch predict Vision
