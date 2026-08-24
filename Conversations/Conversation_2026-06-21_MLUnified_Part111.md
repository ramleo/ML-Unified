# Conversation — 2026-06-21 — ML-Unified Part 111

## Context
Continuation of Part 110. All work is on ml-portfolio (Next.js frontend) at `/Users/wrks/Downloads/Claude-documentation/Projects/ml-portfolio`.

---

## Session Summary

### FE page.tsx Modularization (537L → 394L)

Extracted three hooks to bring feature-engineering/page.tsx under 400 lines:
- `src/hooks/useFELDA.ts` (47L) — LDA state + handleRunLDA
- `src/hooks/useFETransforms.ts` (93L) — applyAllTransforms + LDA merge
- `src/hooks/useFEAISuggest.ts` (91L) — aiSuggest callback + JSON parsing
- `src/hooks/useFEFileLoad.ts` (86L) — handleFile + handleDrop + state reset

**Commits:** `4244d4d`, `65fb85d`

---

### ML Capabilities Cards — Hover Tilt + Glow

Added same hover physics as ProjectCard to CapabilityCard in `MLCapabilities.tsx`:
- Perspective tilt tracking cursor position
- Accent-coloured glow on box-shadow and border
- Shimmer radial gradient following tilt angle
- Smooth spring-back when cursor leaves

**Commit:** `2cd536b`

---

### Chatbot Bubble Blocking Fix

`ToolsAIChat.tsx` outer fixed wrapper: added `pointerEvents: "none"`.
Both the bubble button and chat panel have `pointerEvents: "auto"`.
Elements behind the transparent wrapper area (like dropdowns) are now clickable.

**Commit:** `2cd536b`

---

### LDA Panel Header — Full Row Clickable

`FEPanels/LDAPanel.tsx`: converted `<button>` at right edge to `onClick` on entire header `<div>`.
The chat bubble was covering the ▼ toggle button. Now the whole bar is the click target.

**Commit:** `a674f36`

---

### PCA + FA Projected Scatter

New `FSProjectedScatter` component (63L) — shared SVG scatter with:
- x/y axis lines, labels, class color legend
- Dots colored by target class value

**PCA:** scatter points computed in `computePCA` (fsReduction.ts) from `pcCols` + target col.
Return type updated to include `points: ScatterPoint[]`.

**FA:** factor scores computed in `computeFA` (fsFA.ts): `score_k = Σ_j Z[ri][j] * loadings[j][k]`.
`FAResult` type updated to include `points: ScatterPoint[]`.
`computeFA` signature extended to accept `extra?: { targetCol?, allCols? }`.
`fsMain.ts` updated to pass target info to computeFA.

**`ScatterPoint` type** added to `fsCore.ts`.

**Commit:** `5b1ef60`

---

### Scatter Visual Fixes (dot size, axis labels, legend)

**Problem:** `r={3}` in SVG with `viewBox="0 0 420 200"` displayed at full width → scales 3× → dots appeared ~18px. `fontSize={9}` axis labels appeared ~27px. Legend used squares not circles.

**FSProjectedScatter fixes:**
- Dot radius: `r={3}` → `r={1.5}`
- Axis font: `fontSize={9}` → `fontSize={6}`
- Axis color: brightened to `rgba(255,255,255,0.5)`
- Legend dots: squares → circles (`borderRadius:"50%"`, 8px)
- Legend text: `0.7rem var(--text3)` → `0.75rem var(--text2)`

**FSReductionResultCards fixes (LDA 1D histogram):**
- Dot radius `r={3}` → `r={1.5}`
- Both legend blocks: squares → circles, brighter text

**UMAPScatter:** 2D scatter dot size reduced.

**Commit:** `4847ba4`

---

### LDA Scatter Axis Labels Fix

**Problem:** LDA 2D/3D scatter used UMAPScatter which hardcoded "UMAP-1", "UMAP-2" on axes.

**Fix:** Added `axisPrefix?: string` prop to UMAPScatter (default `"UMAP"`). Axis labels generated dynamically as `` `${axisPrefix}-${i+1}` `` — works for any number of dimensions. LDA passes `axisPrefix="LD"` → shows "LD-1", "LD-2".

**Commit:** `710ea9d`

---

### FS Layout + Font Fixes

**HowItWorks gap:** Added `marginTop: "1.5rem"` wrapper around HowItWorks in page.tsx — separates it visually from sticky "Run Feature Selection" button row.

**ReductionTabs font:** Reduced all enable labels and value displays from `0.84rem` → `0.82rem` (PCA/UMAP/FA/LDA panels).

**Commit:** `b193bdb`

---

### Subagent Permissions — Root Cause Found

Subagents inherit the **ML-Unified** working directory, so they read ML-Unified's `.claude/settings.json`, NOT ml-portfolio's. Updated ML-Unified settings to include `Read`, `Edit`, `Write` alongside existing Bash patterns.

Subagents can now read and edit files. Bash still blocked in subagent context — finishing Bash steps (tsc, commit, push) from main session as workaround.

**Fix:** `ML-Unified/.claude/settings.json` updated with `"Read"`, `"Edit"`, `"Write"`.

---

### Q&A

**"Latent wealth" explanation (FA):** Factor 1 loads on Fare (+0.81) and Pclass (−0.78). Both driven by a hidden third concept — wealth — that FA inferred from their correlation. FA cannot observe "wealth" directly; it discovers that one latent variable causes both features to move together.

**LDA 3D scatter location:** Appears in the results section after clicking "Run Feature Selection". Adaptive: binary target → 1D histogram, 3 classes → 2D, 4+ classes → 3D. Titanic (binary) always shows 1D. Need multi-class dataset (e.g. Iris: 3 classes → 2D).

**Why no 3D for PCA/FA natively:** UMAP's output IS 2D/3D coordinates. PCA/FA output is loadings/variance charts; projected scatter is an additional view (now added).

**Subagent permission flow:** Main session auto-allows because ML-Unified settings.json covers it. Subagents silently fail (not prompt) when denied — not a user-facing prompt. Fixed by adding Read/Edit/Write to ML-Unified settings.

---

## All Commits This Session

| Commit | Description |
|---|---|
| `4244d4d` | refactor(fe): extract LDA state into useFELDA hook |
| `65fb85d` | refactor(fe): further modularize page — applyAllTransforms + aiSuggest + fileLoad hooks |
| `2cd536b` | feat(ui): capability card hover tilt+glow; fix chatbot bubble pointer-events |
| `a674f36` | fix(fe): make entire LDA panel header row clickable to expand/collapse |
| `5b1ef60` | feat(fs): add projected scatter to PCA and FA tabs |
| `b193bdb` | fix(fs): increase gap above HowItWorks; reduce reduction tab label font size |
| `6cd0eb5` | chore: allow Read/Edit/Write in subagent settings (ml-portfolio) |
| `4847ba4` | fix(fs): reduce scatter dot size, fix axis labels and legend circles |
| `710ea9d` | fix(fs): dynamic axis labels for LDA scatter via axisPrefix prop |

---

## Pending Items

1. **Subagent Bash still blocked** — Read/Edit work but Bash (wc -l, tsc, git) is denied in subagent context. Workaround: finish Bash steps from main session. Investigate correct permission format for Bash in subagents.
2. **Kaiser criterion** — "Auto (Kaiser)" toggle in PCA tab: keep components with eigenvalue > 1. Not yet started.
3. **LDA axis label format** — currently "LD-1", "LD-2" (with hyphen). Could be "LD1", "LD2" (no hyphen) — verify with user.
4. **LDA text in FE** — future: custom stopwords, min word frequency, stemming options.
