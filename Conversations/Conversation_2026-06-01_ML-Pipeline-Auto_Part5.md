# Conversation – 2026-06-01 (Part 5): UI Fixes — Algorithm, Tooltip, Light Theme

---

## Issues & Tasks This Session

---

### 1. Algorithm Card Showing "—"

**Problem:** The "About This Model" section showed `—` for Algorithm because `best_name` was computed during training but never saved to `cfg["best_model"]`, so `cfg.get("best_model", "—")` always returned `"—"`.

**Fix — `auto_pipeline.py` (pipeline):**
- After selecting `best_name`, now saves it to cfg and writes config immediately:
  ```python
  cfg["best_model"] = best_name
  CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
  ```
- Adds `"algorithm": best_name` to `metrics.json` output:
  ```python
  _metrics_out = {
      'task': 'regression',
      'algorithm': best_name,
      ...
  }
  ```

**Fix — `index.html` template:**
- Added `id="algoValue"` to the Algorithm value div
- In the `/metrics` fetch JS, populate from `m.algorithm`:
  ```javascript
  var av = document.getElementById('algoValue');
  if (av && m.algorithm) { av.textContent = m.algorithm; }
  ```

**Fix — Temp-Insurance project:**
- Added `"algorithm": "XGBoost"` directly to `models/metrics.json` (XGBoost was the winning model per `docs/auto_summary.md`)

---

### 2. Remove "Range: 229 – 2054 (±1σ)" and "Near Average"

**Problem:** Below the big prediction value:
- `resConf` showed `"Range: 229 – 2054 (±1σ)"` — redundant with the CI section below
- `benchmarkBadge` showed "Near Average" / "Above Average" / "Below Average"

**Fix:** Both removed in `index.html` and `auto_pipeline.py` template:
```javascript
// Before:
resConf.textContent = 'Range: ' + lo.toFixed(0) + ' – ' + hi.toFixed(0) + '  (±1σ)';

// After:
resConf.textContent = '';
```
The entire `benchmarkBadge` population block (target_mean comparison, sig calculation, badge color logic) was deleted. The hidden `<div id="benchmarkBadge">` HTML element remains but is never shown.

---

### 3. Confidence Interval — Tooltip Added

**Reference:** ML-Insurance-with-Frontend (`ML-Insurance_with-Frontend_20260529_130733/index.html`) which uses `tip-wrap` / `tip-icon` / `tip-box` pattern.

**CSS added:**
```css
.tip-wrap { position:relative; display:inline-flex; align-items:center; margin-left:6px; }
.tip-icon {
  cursor:help; color:rgba(255,255,255,.35); font-size:.65rem; font-weight:700;
  border:1px solid rgba(255,255,255,.22); border-radius:50%;
  width:14px; height:14px; display:inline-flex; align-items:center; justify-content:center;
}
.tip-box {
  display:none; position:absolute; bottom:calc(100% + 6px); left:50%; transform:translateX(-50%);
  background:rgba(15,25,45,.95); border:1px solid rgba(255,255,255,.12); border-radius:8px;
  padding:8px 12px; color:rgba(255,255,255,.82); font-size:.74rem; white-space:nowrap;
  z-index:99; box-shadow:0 4px 16px rgba(0,0,0,.5);
}
.tip-wrap:hover .tip-box { display:block; }
body.light .tip-icon { color:rgba(0,0,0,.4); border-color:rgba(0,0,0,.2); }
body.light .tip-box  { background:rgba(255,255,255,.97); border-color:rgba(0,0,0,.12); color:#334155; }
```

**HTML change to CI section header:**
```html
<!-- Before -->
<div>Confidence Interval <span>(±1σ · ~68%)</span></div>

<!-- After -->
<div style="display:flex;align-items:center">
  Confidence Interval
  <span>(±1σ · ~68%)</span>
  <span class="tip-wrap">
    <span class="tip-icon">?</span>
    <span class="tip-box">Your prediction falls within ±1σ (one standard deviation) of this range.</span>
  </span>
</div>
```

---

### 4. Light Theme — Invisible Text Fixed

**Problem:** Many elements in the result panel use hardcoded `rgba(255,255,255,x)` inline styles. On dark mode these are fine, but in light mode (white glass background) they become invisible.

**Affected elements:**
- Section labels: "Confidence Interval", "Key Factors", "Input Summary", "Class Probabilities"
- Panel subtitles: "Output from your trained model", "No prediction yet", "Fill in the form..."
- Feature importance bar labels and percentage values
- CI section background, track bar, range values
- Section containers (Input Summary, CI section)

**Approach:** Two-part fix:

**Part A — CSS attribute selectors** (catch all inline rgba white styles):
```css
body.light [style*='color:rgba(255,255,255,.28)'] { color:#64748b !important; }
body.light [style*='color:rgba(255,255,255,.25)'] { color:#94a3b8 !important; }
body.light [style*='color:rgba(255,255,255,.38)'] { color:#64748b !important; }
body.light [style*='color:rgba(255,255,255,.45)'] { color:#64748b !important; }
body.light [style*='color:rgba(255,255,255,.5);']  { color:#475569 !important; }
body.light [style*='color:rgba(255,255,255,.22)'] { color:#94a3b8 !important; }
body.light [style*='color:rgba(255,255,255,.3)']  { color:#94a3b8 !important; }
body.light [style*='background:rgba(255,255,255,.04)'] {
  background:rgba(0,0,0,.04) !important; border-color:rgba(0,0,0,.1) !important;
}
body.light [style*='background:rgba(255,255,255,.06)'] { background:rgba(0,0,0,.08) !important; }
body.light #ciLower, body.light #ciUpper { color:#334155 !important; }
body.light .mini-stat div { color:#64748b !important; }
```

**Part B — CSS classes for dynamically generated fiBars** (JS-generated elements can't be caught by static attribute selectors):
```css
/* New CSS classes replacing inline styles */
.fi-row { margin-bottom:7px; }
.fi-label-row { display:flex; justify-content:space-between; font-size:.76rem; margin-bottom:3px; }
.fi-lbl  { color:rgba(255,255,255,.6); }
.fi-pct  { color:rgba(255,255,255,.4); }
.fi-track { height:5px; background:rgba(255,255,255,.08); border-radius:99px; }
.fi-fill  { height:5px; border-radius:99px; background:linear-gradient(90deg,#1565c0,#2979ff); }
/* Light overrides */
body.light .fi-lbl   { color:#334155 !important; }
body.light .fi-pct   { color:#64748b !important; }
body.light .fi-track { background:rgba(0,0,0,.08) !important; }
```

**JS change — fiBars generation:**
```javascript
// Before (inline rgba white colors):
return '<div style="margin-bottom:7px">...<span style="color:rgba(255,255,255,.6)">'+lbl+'</span>...'

// After (CSS classes):
return '<div class="fi-row"><div class="fi-label-row"><span class="fi-lbl">'+lbl+
       '</span><span class="fi-pct">'+pct+'%</span></div>'+
       '<div class="fi-track"><div class="fi-fill" style="width:'+pct+'%"></div></div></div>';
```

---

## Commits This Session

| Hash | Repo | Description |
|---|---|---|
| `392619b` | Temp-Insurance | Fix UI: algorithm, remove range/badge, CI tooltip, light theme |
| `b7ed3db` | ML-Pipeline-Auto | Fix UI: algorithm display, CI tooltip, light theme overrides |

---

## Files Changed This Session

| File | Change |
|---|---|
| `Temp-Insurance/models/metrics.json` | Added `"algorithm": "XGBoost"` |
| `Temp-Insurance/index.html` | All 4 fixes applied |
| `ML-Pipeline-Auto/auto_pipeline.py` | Pipeline saves algorithm; template gets all 4 fixes |
| `ML-Pipeline-Auto/bootstrap.py` | Re-embedded updated auto_pipeline.py |
