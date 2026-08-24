# Conversation — 2026-06-21 — ML-Unified Part 110

## Context
Continuation of Part 109. All work is on ml-portfolio (Next.js frontend) at `/Users/wrks/Downloads/Claude-documentation/Projects/ml-portfolio`.

---

## Session Summary

### AI Suggest — Truncation Fix (maxTokens)

- `src/app/api/ai-tools/route.ts` — added `maxTokens` param to `callGemini` signature + POST handler destructuring; wired through both primary and retry callGemini calls
- `src/hooks/useFSAISuggest.ts` — sends `maxTokens: 2048`; prompt tightened to "only include fields you are enabling, skip everything else"
- Also fixed wrong field names in previous session: `kBestK` → `selectKBestK`, `rfeK` → `rfeTargetK`
- **Commit:** `aa6454d`

---

### Badge Count Fix

- `src/components/FSPanels/FSControls.tsx` — added `tab.enabled &&` so badge only shows on enabled tabs (was showing total `keptCount` on ALL tabs including disabled ones)
- **Commit:** `aa6454d`

---

### Factor Analysis (FA) + LDA (Linear Discriminant) — Added to FS

**New files:** `src/lib/fsFA.ts` (135L), `src/lib/fsLDA.ts` (174L), `src/components/FSPanels/FSReductionResultCards.tsx` (309L), `src/hooks/useFSDownloads.ts` (53L)

**FA:** Principal axis factoring, 25-round communality iteration, converges at Δ<0.001. Loadings table coloured by strength. Caveat: assumes linear relationships.

**LDA:** Supervised, S_W regularised (+0.0001×I). Adaptive scatter display:
- Binary (2 classes) → 1D histogram with deterministic jitter
- 3 classes → 2D SVG scatter (reuses UMAPScatter)
- 4+ classes → 3D Three.js scatter (reuses UMAPScatter Scatter3D)
- Warning chip if target is numeric/empty

**Constraint note added:** "Max components = nClasses − 1. Binary → 1D. 3 classes → 2D. 4+ → 3D."

**HowItWorks:** FA and LDA descriptions with concrete Titanic examples.

**Commits:** `aa6454d`, `c9b2398`

---

### S_B / S_W Explained (Q&A)

- **S_B** (Between-class scatter): how far apart class centres are from global mean. Large = classes well-separated.
- **S_W** (Within-class scatter): how spread points are within each class. Small = tight clusters.
- LDA maximises S_B/S_W — finds projection where classes are far apart AND tight internally. Solves eigenvectors of S_W⁻¹·S_B.

---

### Latent Dirichlet Allocation — Added to Feature Engineering

**Algorithm:** Collapsed Gibbs Sampling
1. Tokenize (lowercase, strip punctuation, split whitespace)
2. Remove ~60 stopwords
3. Build vocabulary (cap 500 most frequent words)
4. Random topic init via deterministic LCG
5. Gibbs iterations: sample new topic ∝ `(doc_topic+α) × (word_topic+β) / (topic_total+V×β)`, α=0.1, β=0.01
6. Compute θ (doc-topic) → output columns; φ (topic-word) → top words per topic
7. Cap at 1000 rows

**New files:**
- `src/lib/feLDA.ts` (163L)
- `src/components/FEPanels/LDAPanel.tsx` (192L)

**Modified:**
- `src/app/tools/feature-engineering/page.tsx` — 537L (WAS 481L — NOW OVER 400 LINE LIMIT)

**UI:** Column selector (string/categorical only), nTopics (2–20, default 5), nIter (10–200, default 50), top-word chips per topic in per-topic colours.

**Output:** `lda_topic_0`, `lda_topic_1`, ... columns appended to dataset.

**Commit:** `d3baa07`

---

### Permission Allowlist Added

Created `/Users/wrks/Downloads/Claude-documentation/Projects/ML-Unified/.claude/settings.json` with:
```json
{
  "permissions": {
    "allow": [
      "Bash(curl -s *)",
      "Bash(.venv/bin/ruff check *)",
      "Bash(/Users/wrks/Library/Python/3.9/bin/ruff check *)",
      "Bash(/Users/wrks/Downloads/Claude-documentation/Projects/ml-portfolio/node_modules/.bin/tsc --noEmit)",
      "Bash(npx tsc --noEmit)",
      "Bash(npx tsc --noEmit *)"
    ]
  }
}
```

Subagents were being denied Read/Bash tools — this fixes it for future sessions.

---

### Save vs Compact Explanation (Q&A)

- **Without saving before /compact:** compaction summary is lossy, lives only in-session. If session ends, detailed work is gone.
- **Save first, then /compact:** save file is permanent on disk with exact commit hashes. Future sessions can Read it for full fidelity.
- **Rule:** Always save before /compact.

---

## All Commits This Session

| Commit | Description |
|---|---|
| `aa6454d` | feat(fs): FA + LDA; AI Suggest maxTokens; badge fix |
| `c9b2398` | feat(fs): LDA 3D scatter + 1D histogram + constraint note |
| `d3baa07` | feat(fe): Latent Dirichlet Allocation text-to-topics transform |

---

## Pending Items

1. **feature-engineering/page.tsx is 537 lines** — over 400-line limit. Must modularize next session (extract LDA state + handler into hook, extract configure section panels).
2. **AI Suggest** — monitor if maxTokens:2048 + tighter prompt fully resolves truncation. May still need console.log debugging if error persists.
3. **Kaiser criterion** — "Auto (Kaiser)" toggle in PCA tab (keep components with eigenvalue > 1). Not yet started.
4. **LDA text in FE** — future: add preprocessing options (custom stopwords, min word frequency, stemming).
