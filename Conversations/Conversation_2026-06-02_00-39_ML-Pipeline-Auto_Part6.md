# Conversation – 2026-06-02 00:39 (Part 6): CI Visual Redesign + Dynamic Badge Label

---

## Issues & Tasks This Session

---

### 1. Screenshot Reference — Light Theme Visual Review

**User shared:** Screenshot of the Insurance Premium Predictor in light mode showing:
- "LIKELY PREMIUM RANGE (?)" section with a fill-from-left progress bar and a thumb dot
- "● ESTIMATED PREMIUM" badge label (derived from the target column name)
- Clean white glass cards, blue sliders, visible feature importance bars

**Request:** "just go through the screenshot for light theme and study it, see how beautiful it is, I want it like that."

---

### 2. CI Section — Visual Redesign

**Problem:** The existing CI section showed:
- Header: "Confidence Interval (±1σ · ~68%)" with tooltip
- Values: `[lo] range [hi]` in muted text
- Track: full-width semi-transparent gradient overlay + small dot at prediction position

**Target (from screenshot):** "LIKELY PREMIUM RANGE (?)" with:
- Larger, bolder range values (`lo` — `to` — `hi`)
- A track that fills from the **left edge to the prediction position** (gradient blue)
- A dot/thumb at the prediction position (blue, white border, glow)

**HTML changes to `ciSec`:**
```html
<!-- Before -->
<div id="ciSec" ...>
  <div style="...">Confidence Interval <span>(±1σ · ~68%)</span><span class="tip-wrap">...</span></div>
  <div style="...;font-size:.8rem;color:rgba(255,255,255,.5)..."><span id="ciLower">—</span><span>range</span><span id="ciUpper">—</span></div>
  <div style="height:8px;...">
    <div style="...width:100%;background:linear-gradient(90deg,#1565c059,#1565c099)"></div>
    <div id="ciDot" style="...width:12px;height:12px;background:#1565c0..."></div>
  </div>
</div>

<!-- After -->
<div id="ciSec" ...>
  <div id="ciHeader" style="...">Predicted Range<span class="tip-wrap">...</span></div>
  <div style="...;font-size:.88rem;font-weight:600;color:rgba(255,255,255,.75)...">
    <span id="ciLower">—</span>
    <span style="color:rgba(255,255,255,.25);font-size:.72rem;font-weight:400">to</span>
    <span id="ciUpper">—</span>
  </div>
  <div style="height:8px;...">
    <div id="ciFill" style="...;width:50%;background:linear-gradient(90deg,#1565c0,#2979ff);transition:width .4s ease"></div>
    <div id="ciDot" style="...;width:14px;height:14px;background:#2979ff;border:2px solid rgba(255,255,255,.75);...transition:left .4s ease;box-shadow:0 0 8px rgba(41,121,255,.55)"></div>
  </div>
</div>
```

**JS changes (CI section):**
```javascript
// Before:
var leftPct = hi > lo ? ((pred-lo)/(hi-lo)*0.8) : 0.5;
document.getElementById('ciDot').style.left = Math.max(5,Math.min(95,leftPct*100)).toFixed(1)+'%';

// After:
var rawPct = hi > lo ? (pred-lo)/(hi-lo) : 0.5;
var dotPct = Math.max(5,Math.min(92,rawPct*100)).toFixed(1);
document.getElementById('ciFill').style.width = dotPct+'%';
document.getElementById('ciDot').style.left = dotPct+'%';
```

Key changes: removed the `*0.8` factor; both `ciFill` width and `ciDot` left are set to the same percentage.

---

### 3. Dynamic Badge Label + CI Header from Target Name

**Problem:** Badge always showed "Estimated Value" (regression) or "Classified" (classification).
Screenshot shows "ESTIMATED PREMIUM" — derived from the target column name.

**Fix — `metrics.json`:** Added `"target"` field:
```json
{
  "task": "regression",
  "algorithm": "XGBoost",
  "target": "Premium Amount",
  ...
}
```

**Fix — JS (page load, metrics fetch):**
```javascript
var _resLabelText = '';  // new global

// In fetch('/metrics') callback:
if(m.target){
  var _t = m.target.replace(/[_\-]/g,' ').replace(/\b\w/g, function(c){ return c.toUpperCase(); });
  _resLabelText = (m.task === 'regression' ? 'Estimated ' : 'Predicted ') + _t;
  var _ch = document.getElementById('ciHeader');
  if(_ch) _ch.textContent = 'Likely ' + _t + ' Range';
}

// In predict response handler:
resLabel.textContent = _resLabelText || 'Estimated Value';  // regression
resLabel.textContent = _resLabelText || 'Classified';       // classification
```

**Result:**
- Insurance (target: "Premium Amount") → badge: **"Estimated Premium Amount"**, CI header: **"Likely Premium Amount Range"**
- Iris (target: "species") → badge: **"Predicted Species"**, CI header: not shown (classification)

---

### 4. Classification Now Writes `metrics.json`

**Problem:** Classification projects never wrote `models/metrics.json`. The `/metrics` endpoint returned `{}`, so algorithm and target label were never shown.

**Fix in `auto_pipeline.py`:**
```python
if task_type == 'classification':
    try:
        import json as _jsc
        _mpc = MODELS_DIR / 'metrics.json'
        _classes_out = [str(c) for c in label_encoder.classes_] if label_encoder is not None else []
        _mpc.write_text(_jsc.dumps({
            'task': 'classification',
            'algorithm': best_name,
            'target': target_col,
            'accuracy': round(metrics.get('accuracy', 0), 4),
            'classes': _classes_out
        }, indent=2))
    except Exception as _mce:
        _warn(f'Classification metrics save skipped: {_mce}')
```

---

## Files Changed

| File | Change |
|---|---|
| `Temp-Insurance/models/metrics.json` | Added `"target": "Premium Amount"` |
| `Temp-Insurance/index.html` | CI HTML redesign, `_resLabelText` global, dynamic badge + CI header |
| `ML-Pipeline-Auto/auto_pipeline.py` | `target` in regression metrics; classification metrics.json; template CI + badge updates |
| `ML-Pipeline-Auto/bootstrap.py` | Re-embedded updated auto_pipeline.py |

---

## Commits

| Hash | Repo | Description |
|---|---|---|
| `47982e8` | Temp-Insurance | UI: dynamic 'Likely X Range' CI bar with fill + badge label from target name |
| `66121cc` | ML-Pipeline-Auto | UI: dynamic CI range label + fill bar, badge from target name, classification metrics |

Both pushed to GitHub (`ramleo/Temp-Insurance`, `ramleo/ML-Pipeline-Auto`).
