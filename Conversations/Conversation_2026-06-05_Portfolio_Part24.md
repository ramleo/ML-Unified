# Conversation — 2026-06-05 | Bug Fixes: Theme Refresh + Wrong Panel on Load (Part 24)

**Date:** 2026-06-05
**Project:** ML-Unified · ml-portfolio

---

## Points Completed This Session

| # | Item | Status |
|---|---|---|
| 1 | Fix theme reverting to dark on page refresh | ✅ Done |
| 2 | Fix wrong panel (Diabetes) shown in ?mode=vision on load | ✅ Done |

---

## 1. Theme Reverts to Dark on Refresh — Root Cause & Fix

### Root Cause
When the portfolio opens ML Unified via "Launch App", it appends `?theme=dark` (or `?theme=light`) to the URL:
```
https://ml-unified.onrender.com/?mode=vision&theme=dark
```

The URL param `?theme=dark` stays in the browser's address bar. On every page refresh, the theme IIFE re-reads it and overrides whatever the user manually set via the toggle — so toggling to light and refreshing always went back to dark.

Same issue existed on the portfolio side when ML Unified passed `?theme=` back via the Portfolio link.

### Fix — `history.replaceState` after first apply

After reading and applying `?theme=` from the URL, immediately strip it using `history.replaceState`. Subsequent refreshes see no `?theme=` param and fall through to `localStorage`.

**ML Unified — `services/ml-api/frontend/index.html`:**
```js
(function () {
  const params   = new URLSearchParams(window.location.search);
  const urlTheme = params.get('theme');
  if (urlTheme === 'light' || urlTheme === 'dark') {
    setTheme(urlTheme);
    try { localStorage.setItem('theme', urlTheme); } catch(e) {}
    // Strip ?theme= so refresh uses localStorage, not the stale param
    params.delete('theme');
    const qs = params.toString();
    history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''));
  } else {
    try { if (localStorage.getItem('theme') === 'light') setTheme('light'); } catch(e) {}
  }
})();
```

**ml-portfolio — `src/components/ThemeToggle.tsx`:**
```tsx
useEffect(() => {
  const params   = new URLSearchParams(window.location.search);
  const urlTheme = params.get("theme");
  let dark: boolean;
  if (urlTheme === "light" || urlTheme === "dark") {
    dark = urlTheme === "dark";
    localStorage.setItem("theme", urlTheme);
    // Strip ?theme= so refresh uses localStorage
    params.delete("theme");
    const qs = params.toString();
    window.history.replaceState(null, "", window.location.pathname + (qs ? "?" + qs : ""));
  } else {
    const stored = localStorage.getItem("theme");
    dark = stored !== "light";
  }
  setIsDark(dark);
  document.documentElement.classList.toggle("light", !dark);
}, []);
```

### Result
- First visit from portfolio: `?theme=light` applied → stripped from URL → `?mode=vision` remains
- Toggle theme manually → saved to localStorage
- Refresh → no URL param → reads localStorage → correct theme persists ✓

---

## 2. Wrong Panel (Diabetes) Shown in ?mode=vision — Root Cause & Fix

### Root Cause
`init()` in `index.html` always called `selectModel(allModels[0].id)` unconditionally after `renderSidebar()`. `allModels[0]` is the first supervised ML model (typically Iris or Diabetes). Even in `?mode=vision` mode — where the sidebar shows only Vision items — the main panel was initialised with a supervised ML model.

### Fix — `services/ml-api/frontend/index.html`

```js
// Before (broken):
renderSidebar();
if (allModels.length > 0) selectModel(allModels[0].id);

// After (fixed):
renderSidebar();
if (APP_MODE === 'vision') {
  selectVision();                        // → Image Classifier panel
} else if (allModels.length > 0) {
  selectModel(allModels[0].id);          // → first ML model (Iris etc.)
}
```

### Result
| Mode | Default panel on load |
|---|---|
| `?mode=vision` | Image Classifier |
| `?mode=ml` | First supervised ML model |
| (no mode) | First supervised ML model |

---

## Commits This Session

### ML-Unified repo

| Hash | Description |
|---|---|
| `bde7a7a` | Fix theme reverting to dark on refresh |
| `018cfa1` | Fix wrong panel shown on load in ?mode=vision |

### ml-portfolio repo

| Hash | Description |
|---|---|
| `e738be3` | Fix theme reverting on refresh in portfolio |

---

## Theme Sync — Full Picture (both directions, both bugs fixed)

```
Portfolio (vercel.app)                    ML Unified (onrender.com)
─────────────────────────────────────────────────────────────────
Launch App clicked
→ appends ?theme=<current> to URL
→ opens ML Unified                →  reads ?theme= from URL
                                  →  applies theme
                                  →  saves to localStorage
                                  →  strips ?theme= from URL ✓
                                  →  refresh → uses localStorage ✓

User toggles theme in ML Unified
Portfolio link clicked
→ onclick sets href with ?theme=  →  (navigates to portfolio)
                                  ←  ThemeToggle reads ?theme=
                                  ←  applies theme
                                  ←  saves to localStorage
                                  ←  strips ?theme= from URL ✓
                                  ←  refresh → uses localStorage ✓
```

---

## Next Up

### Phase 2: Theme palette picker + high contrast + vision ambient themes
- 5 themes: Dark · Light · Ocean · Forest · High Contrast
- Palette picker in navbar (both apps)
- Each vision task gets its own background tint + accent colour:
  - Image Classifier → fuchsia `#e879f9`
  - Image Processing → orange `#fb923c`
  - Object Detection → cyan `#38bdf8`
  - Image Segmentation → purple `#a78bfa`
- Sync palette across domains via URL param (extend `?theme=` to `?theme=ocean`)

### Phase 3: ML Unified + Vision improvements (UI + features)
- Both UI polish and new features (user confirmed)
- Confidence bar charts, side-by-side vision results, batch predict, SHAP, training history

### Phase 4–6: Data drift · MLflow · E2E tests

---

## Standing Rules (unchanged)

- Apply changes to ALL affected repos simultaneously
- Conversation logs stored in `ML-Iris/Conversations/`
- Vercel = portfolio only; Render = ML apps
- `vision_cache/` and `.mcp.json` must never be committed
- Always run `ruff check` + `pytest` before pushing
- Use mock-based tests for inference paths requiring model downloads
- User-facing errors: plain English only
- Keep ml-api and ml-vision requirements.txt fully independent
- All vision endpoint URLs sourced from `VISION_API`, never `API`
- Consider microservices architecture in all new features
- Vision task ambient themes planned for Phase 2
