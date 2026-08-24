# Conversation — 2026-06-21 — ML-Unified Part 108

## Context
Continuation of Part 107. All work is on ml-portfolio (Next.js frontend) at `/Users/wrks/Downloads/Claude-documentation/Projects/ml-portfolio`.

---

## Session Summary

### Constellation Repulsion — Root Cause & Fix

**Finding:** Homepage uses `ParticleGrid.tsx` (via `ParticleGridClient`), NOT `ConstellationBackground.tsx`. Two completely different components:

| | ParticleGrid (homepage) | ConstellationBackground (tool pages) |
|---|---|---|
| Layout | Fixed grid (38px gap) | Random positions, free-drifting |
| Repulsion | Push away from cursor | Push away (added this session) |
| Spring-back | ✓ dots return to origin | ✗ (was missing — added this session) |
| Color | Purple `rgba(99,102,241,...)` | Cyan `rgba(34,211,238,...)` |

**Fix:** Added origin-based spring-back physics to `ConstellationBackground.tsx`:
- Each dot has `ox`, `oy` (fixed origin)
- Repulsion: `vx += -cos(angle) * force * REPEL_PUSH * 0.08`
- Spring-back: `vx += (ox - x) * SPRING` (SPRING = 0.05)
- Damping: `vx *= 0.80`
- Removed wrap-around (dots spring back instead)

**Commit:** `e2b3875`

---

### AI Suggest — JSON Mode Fix (Partial)

**Root cause analysis:** The error `No JSON found — AI replied: "{ "useCorrelation": true...` means the AI IS returning JSON starting with `{`, but `extractJSON` returns null. Most likely: Gemini truncates the response mid-JSON (no closing `}`), so bracket-depth counter never reaches 0.

**Fixes applied:**
1. Added `jsonMode` param to `callGemini` in `/api/ai-tools/route.ts` → passes `responseMimeType: "application/json"` to Gemini when `jsonMode: true`
2. `useFSAISuggest.ts` now sends `jsonMode: true` in request body
3. Gemini JSON mode forces clean structured output

**Commits:** `e2b3875`, `69714ce`

**Status: Still throwing error** — needs further investigation. Possible remaining causes:
- `jsonMode` param destructuring from `req.json()` has a TS hint (severity: Hint, not error) suggesting TypeScript may not be reading it from the request body correctly
- The Gemini `responseMimeType` may not be supported in all model versions
- Need to add console.log debugging to see what `raw` actually contains

---

### PCA Scree Chart — Cumulative Line Fix

**Bug:** `maxVar` was based on tallest single bar × 1.2 (e.g. 0.263 × 1.2 = 0.316). Cumulative at PC2=49%, PC3=62% exceeded the chart ceiling and clipped off-top. Only PC1 dot (26%) was visible.

**Fix in `FSCharts.tsx`:**
```ts
const totalCumulative = components[components.length - 1]?.cumulativeVariance ?? 0;
const maxVar = Math.min(1, Math.max(
  Math.max(...components.map(c => c.varianceExplained)) * 1.2,
  totalCumulative * 1.05
));
```

**Commit:** `c9a9525`

---

### UMAP 3D — "Right-drag to pan" Fix

**Issue:** On MacBook trackpad, right-click drag doesn't exist. Ctrl+drag is the equivalent.

**Fix:** Changed hint label from "Right-drag to pan" → "Ctrl-drag to pan".

**Commit:** `e2b3875`

---

### FS — Drop Columns Feature

**Added:** Collapsible chip panel above the tab bar in Feature Selection — lists all columns as toggle chips. Click to exclude from selection. Excluded chips show strikethrough + red tint. A count badge on the header shows how many are excluded.

**How it flows:**
- `excludedCols: string[]` state in `page.tsx`
- `FSExcludePanel.tsx` renders the chips (target column dimmed/non-clickable)
- `handleRun` filters: `cols.filter(c => !excludedCols.includes(c.name))` before passing to `runSelection`
- No changes to `fsMain.ts` — it simply receives a shorter `cols` array

**Commit:** `c9a9525`

---

### FS Page Modularization (679 → 395 lines)

New files extracted by subagent:
- `src/components/FSPanels/FSControls.tsx` (148 lines) — grouped tab bar + pipeline indicator + sticky Run/AI row
- `src/components/FSPanels/FSExcludePanel.tsx` (87 lines) — exclude columns chip panel
- `src/components/FSPanels/FSHowItWorks.tsx` (60 lines) — HowItWorks component
- `src/components/FSPanels/FSUploadHero.tsx` (126 lines) — upload hero card
- `src/hooks/useFSAISuggest.ts` (93 lines) — AI Suggest async logic

**Commit:** `c9a9525`

---

### Correlation Heatmap — Annotation Fix

**Bug:** Annotation threshold was `|r| > 0.5` but caption said `|r| > 0.7`. Only Pclass-Fare (r=-0.55) was annotated; all other pairs were ≤ 0.5.

**Fix:** Lowered annotation threshold to `|r| > 0.4` so more pairs show values. Updated caption:
`"Orange = positive r · Blue = negative r · Values shown when |r| > 0.4 · |r| > 0.7 = multicollinearity risk"`

**Commit:** `e2b3875`

---

## Q&A Recorded This Session

### Constellation repulsion explanation
The black empty space around the cursor IS the effect — dots repel away from cursor, leaving a void. As cursor moves, the void follows. Spring-back means dots return to their origin when cursor moves away.

### UMAP 3D — Ctrl-drag to pan
Right-drag doesn't exist on Mac trackpad. Ctrl+trackpad drag = pan (translate camera without rotating). Useful when cluster is off-center after rotation.

### PCA — blue cumulative line
It's the total variance explained as components are added (PC1: 26%, PC1+PC2: 49%, etc.). Bug: only PC1 was visible because Y axis ceiling was too low. Fixed.

### Factor Analysis — WHERE to use in app
- **Kaiser criterion** (keep PCA components with eigenvalue > 1): Add "Auto (Kaiser)" option to PCA tab in Feature Selection — auto-selects component count instead of user typing a number.
- **Factor Analysis**: Different from PCA — models latent variables explaining feature correlations. Could be added as a **3rd Reduction tab** in Feature Selection (alongside PCA and UMAP).
- **NOT yet implemented** — noted as future enhancement.

### Feature Rankings explanation
Each row = one feature. Bars show importance score per method (longer = more important). ✓ = kept, × = dropped. σ² = raw variance of that feature. Top of list = most predictive of target. If multiple methods enabled, compare bars to see agreement.

### Score Comparison explanation
Same features, different angle. Each feature gets a bar per active method side-by-side. All bars long = consistent importance across methods = high confidence. Bars disagree = feature matters to some methods but not others (e.g. non-linear signal that MI catches but Lasso doesn't).

---

## Pending / Known Issues

1. **AI Suggest still throwing error** — `jsonMode` fix was applied but error persists. Needs console.log debugging to see raw API response. Possible: `responseMimeType` not supported on all Gemini model versions, or the TS destructuring issue with `req.json()` is preventing `jsonMode` from being read properly.

2. **"How it works" discoverability** — The collapsible label still says "How it works" without indicating WHICH method it describes. Should say e.g. "How Variance Filter works ▾" so users know it's tab-specific before opening. **Not yet implemented.**

3. **Factor Analysis / Kaiser criterion** — noted as future enhancement, WHERE to add it:
   - Kaiser: "Auto (Kaiser)" option in PCA tab
   - Factor Analysis: new 3rd Reduction tab in FS alongside PCA and UMAP
   **Not yet implemented.**

---

## Commits This Session

| Commit | Description |
|---|---|
| `fa4806d` | fix(fs): robust AI Suggest JSON extraction — bracket-depth parser + toolContext override |
| `c9a9525` | feat: constellation repulsion on all pages, PCA scree fix, UMAP hint, FS drop columns |
| `e2b3875` | fix: constellation spring-back, AI JSON mode, heatmap annotation, UMAP hint |
| `69714ce` | fix(fs): pass jsonMode:true to AI Suggest request |
