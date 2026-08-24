# Conversation — 2026-06-21 — ML-Unified Part 109

## Context
Continuation of Part 108. All work is on ml-portfolio (Next.js frontend) at `/Users/wrks/Downloads/Claude-documentation/Projects/ml-portfolio`.

---

## Session Summary

### AI Suggest — Final Fix (truncation root cause resolved)

**Root cause:** Gemini was truncating the JSON response mid-way because `maxOutputTokens` was hardcoded to 800. The response `{"useVariance":true,"varianceThreshold":0.01,"useCorrelation":true,"` ended mid-key — no closing `}` — so both `JSON.parse` and bracket-depth extractor failed.

**Fixes applied:**
1. `src/app/api/ai-tools/route.ts` — added `maxTokens` param to `callGemini` signature and POST handler destructuring; wired through both primary and retry calls
2. `src/hooks/useFSAISuggest.ts` — sends `maxTokens: 2048` in request; tightened prompt to say "only include fields you are enabling, skip everything else, keep compact"
3. Also fixed wrong field names in prompt: `kBestK` → `selectKBestK`, `rfeK` → `rfeTargetK`

**Commit:** `aa6454d`

---

### Badge Count Fix

**Problem:** Every tab showed "7" (total feature count) even on disabled tabs — `result.keptCount` was rendered for ALL tabs whenever result existed.

**Fix:** `src/components/FSPanels/FSControls.tsx` — added `tab.enabled &&` condition so badge only appears on enabled tabs.

**Commit:** `aa6454d`

---

### Factor Analysis (FA) — New Reduction Tab

**Algorithm:** Principal axis factoring with communality iteration
- Standardise features (z-score)
- Build Pearson correlation matrix R
- Iterate up to 25 rounds: replace diagonal with h²_i, extract top-k eigenvectors via power iteration + deflation, update communalities
- Converge when max change < 0.001
- Cap at 500 rows for performance

**New files:**
- `src/lib/fsFA.ts` (135 lines)
- Adds to `SelectionOpts`: `useFA: boolean`, `faFactors: number` (default 3)
- Adds to `SelectionResult`: `faResult?: FAResult` (loadings, communalities, variance, featureNames)

**UI:** Loadings table — orange bold = |loading| > 0.5, dim = weak. Variance % bar per factor. Download CSV button.

**HowItWorks:** Explains communalities, principal axis factoring, Titanic example (Factor 1 → Fare +0.81, Pclass −0.78 = latent "wealth"). Caveat: assumes linear relationships.

**Commit:** `aa6454d`

---

### Linear Discriminant Analysis (LDA) — New Reduction Tab

**Algorithm:** Supervised dimensionality reduction
- Requires categorical target — returns null if numeric/empty
- Compute class means, global mean
- Between-class scatter S_B = Σ_c n_c × (μ_c − μ)(μ_c − μ)^T
- Within-class scatter S_W = Σ_c Σ_{x in c} (x − μ_c)(x − μ_c)^T
- Regularisation: S_W += 0.0001 × I (prevents singular matrix)
- Solve S_W⁻¹ S_B via Gaussian elimination → eigenvectors = linear discriminants
- Cap: max components = nClasses − 1

**New files:**
- `src/lib/fsLDA.ts` (174 lines)
- Adds to `SelectionOpts`: `useLDA: boolean`, `ldaComponents: number` (default 2)
- Adds to `SelectionResult`: `ldaResult?: LDAResult` (points, variance, featureWeights, featureNames, targetValues)

**UI — adaptive scatter based on nClasses:**
- Binary (2 classes) → 1D histogram: dots on horizontal LD1 axis, deterministic vertical jitter `(i * 2654435761) % 1000 / 1000`, coloured by class
- 3 classes → 2D SVG scatter (reuses UMAPScatter Scatter2D)
- 4+ classes → 3D Three.js scatter (reuses UMAPScatter Scatter3D with OrbitControls + Reset view)

**Warning chip:** "⚠ LDA requires a categorical target column" shown when target is empty or numeric.

**Constraint note added in UI + HowItWorks:**
"Max usable components = nClasses − 1: binary classification gives 1 component (1D projection), 3 classes gives max 2D scatter, 4+ classes allows 3D."

**Commits:** `aa6454d`, `c9b2398`

---

### S_B / S_W Explanation (Q&A)

**S_B (Between-class scatter):** How far apart class centres are from global mean. Large S_B = classes well-separated.

**S_W (Within-class scatter):** How spread points are within each class around their own class mean. Small S_W = tight clusters within classes.

**LDA maximises S_B / S_W** — finds projection where classes are far apart AND internally tight. Solves eigenvectors of S_W⁻¹ · S_B.

---

### Latent Dirichlet Allocation (LDA topic model) — NOT added

**Decision:** Skipped for FS tool — it's a text/topic model for bag-of-words data, not tabular numeric features.

**Where it belongs:** Feature Engineering tool, as a "Text" category transform:
1. Tokenize text column → word list per row
2. Remove stopwords, lowercase
3. Build vocabulary → integer document-term matrix
4. Run LDA → K topic probability columns per row
5. Output: `topic_0, topic_1, ...` numeric columns replace the text column

**Status:** Not yet implemented. Noted as future FE enhancement when text data support is added.

---

### Constellation Background — Spring-back Physics

**Finding:** Homepage uses `ParticleGrid.tsx` (grid layout, spring-back). Tool pages use `ConstellationBackground.tsx` (random drift, no spring-back).

**Fix:** Added origin-based spring-back to ConstellationBackground:
- Each dot gets fixed `ox`, `oy` origin
- Repulsion: `vx += -cos(angle) * force * REPEL_PUSH * 0.08`
- Spring-back: `vx += (ox - x) * 0.05`
- Damping: `vx *= 0.80`

**Commit:** `e2b3875`

---

### Other Fixes This Session

| Fix | File | Commit |
|---|---|---|
| PCA scree cumulative line clipping | `FSCharts.tsx` | `c9a9525` |
| UMAP hint "Ctrl-drag to pan" (Mac) | `UMAPScatter.tsx` | `e2b3875` |
| Heatmap annotation threshold → \|r\| > 0.4, caption updated | `CorrelationHeatmap.tsx` | `e2b3875` |
| HowItWorks label → "How Variance Filter works" per tab | `FSHowItWorks.tsx` | `3df3781` |
| FS Drop columns chip panel | `FSExcludePanel.tsx` | `c9a9525` |
| FS page modularized 679 → 380 lines | `page.tsx` + new hooks | `c9a9525`, `aa6454d` |
| AI Suggest: jsonMode:true + maxTokens:2048 + correct field names | `useFSAISuggest.ts` | `3df3781`, `aa6454d` |

---

## All Commits This Session

| Commit | Description |
|---|---|
| `fa4806d` | fix(fs): robust AI Suggest JSON extraction |
| `c9a9525` | feat: constellation repulsion, PCA scree fix, UMAP hint, FS drop columns |
| `e2b3875` | fix: constellation spring-back, AI JSON mode, heatmap annotation |
| `69714ce` | fix(fs): pass jsonMode:true to AI Suggest |
| `3df3781` | fix(fs): correct AI Suggest field names; HowItWorks shows method name |
| `aa6454d` | feat(fs): FA + LDA; AI Suggest token fix; badge fix |
| `c9b2398` | feat(fs): LDA 3D scatter + 1D histogram fallback + constraint note |

---

## Pending / Future Items

1. **Latent Dirichlet Allocation** — add to Feature Engineering as text→numeric transform (tokenize → BoW → LDA → topic columns). Not yet started.
2. **Kaiser criterion** — add "Auto (Kaiser)" toggle to PCA tab (keep components with eigenvalue > 1). Not yet started.
3. **AI Suggest** — monitor if `maxTokens: 2048` + tighter prompt resolves truncation fully. If still failing, add console.log to API route to inspect raw response.
