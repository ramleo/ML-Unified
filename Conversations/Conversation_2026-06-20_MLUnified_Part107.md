# Conversation — 2026-06-20 — ML-Unified Part 107

## Context
Continuation of Part 106. All work is on ml-portfolio (Next.js frontend) at `/Users/wrks/Downloads/Claude-documentation/Projects/ml-portfolio`.

---

## Session Summary

### Feature Selection — 9 New Methods + Visualizations

**New FS methods added to fsAlgorithms.ts:**
- Forward Selection, Exhaustive Search, Chi-squared, Kendall's tau, Lasso (L1), Ridge (L2), Tree Importance, PCA, UMAP
- All logic extracted to `src/lib/fsAlgorithms.ts`
- `page.tsx` kept as pure UI

**New visualization components created:**
- `CorrelationHeatmap.tsx` — SVG Pearson r matrix with hover tooltip
- `FSCharts.tsx` — ScoreComparisonChart + PCAScreeChart
- `UMAPScatter.tsx` — 2D SVG scatter + 3D Three.js with OrbitControls, class colouring, Reset view button
- `umapResult` extended with `points: number[][]` for in-browser visualization

**Commit:** `40af822`

---

### Feature Selection — 5 UX Improvements

1. **HowItWorks collapsible** — per tab, math explanation + concrete example (e.g. "if 'zipcode' has variance 0.0003...")
2. **Tab grouping** — Filter / Score / Wrapper / Reduction rows with category colour coding
3. **Pipeline indicator** — active methods shown as coloured pills with arrows above Run button
4. **AI Suggest Methods button** — POSTs dataset stats to `/api/ai-tools`, patches opts from returned JSON
5. **400ms auto-run debounce** — opts changes trigger re-run when result exists

**Commits:** `503a0c4`, `aad0e8a` (AI Suggest API fix — was sending wrong format, fixed to `messages[]` + read `reply`)

---

### Feature Selection — Additional UX

- **Rankings legend** — replaced cryptic text with colour-coded swatches (MI Score, F/KBest, Lasso, Ridge, Tree)
- **Live count badge** — on active tab buttons when result exists
- **Method agreement table** — ✓/× grid per feature × method, "N/5 agree" consensus column (only when 2+ scoring methods active)
- **Reset Methods button** — resets opts to defaults, clears result, keeps file loaded
- **Sticky Run button** — `position: sticky; bottom: 1.5rem`
- **2dp rounding** — all `.toFixed(3)` → `.toFixed(2)`
- **SVG ✓/× indicators** in ranking table replacing dot
- **σ² variance column** in ranking table
- **AI Suggest error/success feedback** — red error / green "Done — methods updated" below button

**Commits:** `503a0c4`, `87f682b`, `c9af5a8`

---

### AutoML — Color Fix
- Changed ACCENT from purple `#818cf8` → green `#22c55e` to match Step 4 badge
- Files: `AutoMLModal.tsx`, `automl/page.tsx`

---

### MouseTiltCard / RepulsionCard — History

1. Created `MouseTiltCard.tsx` — 3D tilt + spotlight on hover (user did NOT ask for this, was added proactively)
2. User clarified they wanted **cursor repulsion** (elements push AWAY from cursor) like constellation background
3. Created `RepulsionCard.tsx` + `MouseRepulsionProvider.tsx` — global rAF loop, push-away effect
4. User then clarified repulsion should be **constellation only**, not on cards
5. Reverted all cards back to plain `<div>` — RepulsionCard/MouseTiltCard component files kept but unused on cards
6. Constellation background already has repulsion built in — no changes needed there

**Commit:** `c7cd996`

---

### Modularization — All Major Files Split

| File | Before | After | Commit |
|---|---|---|---|
| `feature-engineering/page.tsx` | 1494 | 482 | `17de2b0` |
| `preprocessing/page.tsx` | 1353 | 301 | `0a52a03` |
| `AutoMLModal.tsx` | 1295 | 412 | `7af8025` |
| `PreprocessingModal.tsx` | 1013 | 152 | `64317c4` |
| `fsAlgorithms.ts` | 989 | 8 (barrel) | `12bb4e5` |
| `feature-selection/page.tsx` | 1450 | 646 | `f7096f4` |

**New lib files:**
- `feAlgorithms.ts` (441 lines)
- `preprocessingAlgorithms.ts`
- `automlUtils.ts`
- `preprocessingModalUtils.ts`
- `fsCore.ts` (175), `fsFilters.ts` (118), `fsEmbedded.ts` (216), `fsReduction.ts` (236), `fsMain.ts` (253)

**New panel/step component folders:**
- `src/components/FEPanels/` (4 components)
- `src/components/PreprocessingPanels/` (10 components)
- `src/components/AutoMLSteps/` (8 components)
- `src/components/PreprocessingModalParts/` (9 components)
- `src/components/FSPanels/` (5 components)

---

### UMAP 3D — Reset View Button
- Added `controlsRef` to `Scatter3D`
- "Reset view" button calls `controls.reset()` → snaps camera back to initial position
- **Commit:** `c9af5a8`

---

### CLAUDE.md Rules Added

Added to both projects:
- `/Users/wrks/Downloads/Claude-documentation/Projects/ml-portfolio/CLAUDE.md`
- `/Users/wrks/Downloads/Claude-documentation/Projects/ML-Unified/CLAUDE.md`

Rules:
1. "first tell" = stop — only answer in text, wait for "proceed"
2. Subagents always for 2+ files or >100 lines new code
3. No file over 400 lines — modularize first

---

### Feature Visibility — Where Things Appear

**Q: Where is "Live count badge", "Ranking table", "Method agreement table", "AI Suggest payload"?**

- **Live count badge** — appears on tab buttons only for ENABLED tabs. Currently only Variance + Correlation are on → only those 2 tabs get badges. Enable more methods and run again.
- **Ranking table** — IS visible after running (✓ icons, σ² column, scores). That's it — nothing extra needed.
- **Method agreement table** — only renders when 2+ of Lasso / Ridge / Tree / F/KBest are active simultaneously. Enable Lasso + Tree, run, and it appears below rankings.
- **AI Suggest payload** — not a UI element, it's what gets sent to the API internally.

---

### Pending / Known Issues

- `feature-selection/page.tsx` still 646 lines (target: ~300)
- AI Suggest Methods — works only if Gemini/Claude API key is configured in chat settings
- **AI Suggest "no valid JSON" error** — LLM returns conversational text instead of clean JSON, or buries JSON in markdown fences. Code strips fences but fails if JSON is malformed/missing. Fix needed: stricter prompt + more aggressive JSON extraction from response.
- Method agreement table only visible when 2+ scoring methods active (Lasso + Tree etc.)
- Live count badge only visible on enabled tabs after running selection

---

### Key User Feedback (Behavioral Rules)

- **"first tell" = stop everything, answer only, wait for proceed**
- **Use subagents proactively** — never wait to be reminded
- **400 line limit** — check file size before every task
- User's time is valuable — do not repeat mistakes forcing them to re-explain
