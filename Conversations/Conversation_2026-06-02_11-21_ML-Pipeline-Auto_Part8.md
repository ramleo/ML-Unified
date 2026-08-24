# Conversation – 2026-06-02 11:21 (Part 8): 4 UI Fixes + Hero Light Theme Issue

---

## Fixes Completed This Session

### 1. Title → "Insurance Premium Predictor"
- `<title>` and hero `<h1>` changed from "Temp Insurance" to "Insurance Premium Predictor"
- Template (auto_pipeline.py): title now generated from `target_col` — e.g. "Premium Amount Predictor", "Species Predictor"

### 2. Tooltip Added to "About This Model"
- Always-visible `?` tooltip on the "ABOUT THIS MODEL" label
- Text: "MAE = Mean Absolute Error (avg prediction error). Est. Error = RMSE (root mean squared error)."
- CI section tooltip text updated to exactly match screenshot: "Your prediction falls within ±1σ (one standard deviation) of this range."

### 3. Dark bg-mesh Hidden in Light Mode
- Added `body.light .bg-mesh { opacity:0; }` — dark animated mesh no longer shows in light mode

### 4. Hero Overlay Lightened
- `body.light .hero` overlay reduced from `rgba(26,60,94,.70)` → `rgba(26,60,94,.35)`
- Template: `TMPL_HEADER_BG_LIGHT` new variable — extracts image URL from header_bg and applies lighter gradient

### 5. Panel Titles Visible in Light Mode
- Added CSS attribute selectors for `color:#fff;font-weight:700;font-size:1.05rem` and `.95rem`
- "Feature Inputs", "Prediction Result", "Prediction History" now dark in light mode

---

## Commits

| Hash | Repo | Description |
|---|---|---|
| `1fc1fac` | Temp-Insurance | Title, tooltip, hero lighter, panel titles |
| `358a10f` | Temp-Insurance | Tooltip text fix: "one standard deviation" |
| `10816da` | ML-Pipeline-Auto | Template: all 4 fixes + TMPL_HEADER_BG_LIGHT |
| `6c4bc76` | ML-Pipeline-Auto | Tooltip text fix |

---

## Pending — Hero Light Theme (NOT YET FIXED)

**Issue:** Hero in light mode is still too dark. The dark navy overlay at 35% opacity is still clearly dark-tinted.

**User feedback (critical):**
> "When ever you give option of light theme everything should be changed accordingly, also fonts should be clearly visible, even images shades should be according to light theme"

**Fix needed:**
1. Hero overlay: change to a **very light** tint — e.g. `rgba(255,255,255,.55)` (white/light blue, not dark navy at any opacity)
2. Hero title `<h1>`: must be **dark** (`#1a3a6b`) in light mode, not white
3. Hero subtitle `<p>`: dark color in light mode
4. Hero badge ("Insurance" pill): dark styled in light mode
5. Same fix must go into `auto_pipeline.py` template (`header_bg_light` computation + hero text CSS)

**User was frustrated** that I started reading files unnecessarily before making the change. Go straight to implementation next session.
