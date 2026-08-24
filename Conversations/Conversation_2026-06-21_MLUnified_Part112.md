# Conversation — 2026-06-21 — ML-Unified Part 112

## Context
Continuation of Part 111. All work is on ml-portfolio (Next.js frontend) at `/Users/wrks/Downloads/Claude-documentation/Projects/ml-portfolio`.

---

## Session Summary

### Kaiser Criterion for PCA
Added "Auto (Kaiser)" toggle to PCA tab. When enabled, keeps only components with eigenvalue > 1. Slider dims, shows "auto". Internally runs PCA on all p features, filters to λ > 1 (min 1).
**Commits:** `b395866`, `625cf72`

### FA 3D Scatter
FA scatter now uses UMAPScatter with `axisPrefix="F"`. Shows 3D when 3+ factors selected, 2D otherwise.

### LDA Scatter Fixes
- Axis labels: removed hyphen → "LD1", "LD2" (was "LD-1", "LD-2")
- LDA slider now dynamically capped at `nClasses − 1`; note shows "3 classes detected → max 2 discriminants"
- "Capped at N" amber badge in result card when selected > actual components

### 2D/3D Toggle (PCA, FA, LDA)
PCA card extracted to `FSPCACard.tsx`. All three reduction methods (PCA, FA, LDA) now show 2D/3D toggle when 3+ components/factors available. 3D note explains why it's only available with 3+ components.

### LDA Text Preprocessing (FE Tool)
Three new controls added to FE LDA panel:
- Custom stopwords (text input, comma-separated, merged on top of built-in list)
- Min doc frequency (slider 1–10, default 2)
- Stemming toggle (basic Porter-style suffix stripping)

### Stopwords Expanded: 64 → ~320
Expanded `STOPWORDS` set in `feLDA.ts` from 64 words to ~320 (industry-standard coverage). Covers articles, conjunctions, prepositions, pronouns, auxiliaries, numbers as words, time/place words, negation contractions (without apostrophe, since punctuation is stripped pre-tokenization).

### LDA Pipeline Documentation
Added expandable "How Latent Dirichlet Allocation works" collapsible section in FE LDA panel showing full 7-step pipeline. Updated stopword count from ~60 → ~320, replaced "spaCy-equivalent" with "industry-standard coverage" (no legal concerns with mentioning spaCy by name under MIT license, but phrasing was inaccurate since list was written independently).

### ReductionTabs Hints
Added component/factor count explanations to PCA, FA, LDA hint text in ReductionTabs.tsx.

### Component Explanation Text
- **PCA:** "Components = number of principal axes to keep. Start with 2–3 for visualisation. Increase to capture more variance; decrease to compress more aggressively. Auto (Kaiser) picks the optimal count automatically."
- **FA:** "Factors = number of latent variables to extract. Use 2 for a quick overview, 3+ to capture richer structure. Scatter plot shows 2D for 2 factors, 3D for 3+."
- **LDA:** "Components = discriminant axes to compute. Actual output is always capped at nClasses − 1 regardless of slider value."

---

## All Commits This Session

| Commit | Description |
|---|---|
| `b395866` | feat(fs): add Kaiser criterion auto-selection for PCA components |
| `625cf72` | docs(fs): add Kaiser criterion explanation to How PCA Works panel |
| `a5fb0ae` | feat(fs/fe): FA 3D scatter, LDA capped badge, axis no-hyphen, LDA text preprocessing |
| `cbe8902` | feat(fs/fe): 2D/3D toggle, LDA slider cap, PCA 3D scatter, LDA pipeline docs |
| `b0bebb1` | feat(fe): expand LDA stopwords from 64 to ~320 (spaCy-equivalent) |
| `aaab53b` | docs(fe): update LDA pipeline stopword count from ~60 to ~320 |
| `e8acad2` | docs(fe): replace 'spaCy-equivalent' with 'industry-standard coverage' in LDA pipeline |

---

## ⚠️ IMPORTANT — Dataset Size Limits & Complexity (save word for word)

### Dataset size limits by tool

| Tool | File size limit | Row limit | How excess handled |
|---|---|---|---|
| **Data Preprocessing** | None (browser RAM) | No hard cap | All rows processed — large files may freeze browser |
| **AutoML** | None | No hard cap | All rows used; iteration count scales with row count (<500 → 5 iters, <2000 → 12, <10000 → 25, else 50) |
| **Feature Engineering (FE)** | None | No hard cap for transforms | All rows processed for scaling/encoding/imputation |
| **FE — LDA Topic Model** | None | **1000 rows** (hard cap) | `texts.slice(0, 1000)` — rows beyond 1000 silently ignored |
| **Feature Selection (FS) — filters/scoring** | None | No hard cap | All rows used for variance, correlation, MI, Lasso, Ridge, Tree etc. |
| **FS — PCA** | None | No hard cap | All rows used for covariance matrix and projection |
| **FS — UMAP** | None | **400 rows** sampled | Sub-samples 400 rows for graph; remaining rows get kNN out-of-sample extension |
| **FS — FA (Factor Analysis)** | None | **500 rows** sampled | Sub-samples 500 rows for factoring; same kNN extension |
| **FS — LDA (Linear Discriminant)** | None | No hard cap | All rows used |

**Key point:** there is no file size check anywhere — no `file.size` guard. The only limits are row-count caps inside specific algorithms (UMAP, FA, FE-LDA). Everything runs in the browser (no server), so the real ceiling is the user's RAM and JS heap. A 100k-row CSV will parse fine but heavy algorithms (UMAP, exhaustive search) will be slow or freeze.

---

### What we can do about dataset size limits

A few directions, each with different effort/impact:

**1. Show sampling indicators clearly (low effort, high UX value)**
Currently UMAP silently samples 400 rows and does kNN extension. Users don't know this happened. Add visible badges in result cards: *"Scatter computed on 400-row sample · all 5000 rows projected via kNN"*. Same for FA (500 rows) and FE-LDA (1000 rows).

**2. Increase the caps (low effort)**
The current limits are conservative browser-safety defaults:
- UMAP: 400 → could go 600–800 safely (graph is O(n²) so doubling costs 4×)
- FA: 500 → 800–1000 (covariance matrix is O(n·p²), manageable)
- FE-LDA: 1000 → 2000–3000 (Gibbs is O(D·V·K·iter), slowest of the three)

**3. Add a file size / row count warning on upload (low effort)**
If a CSV has >5000 rows, show a yellow notice on the upload card: *"Large dataset — some algorithms will sample rows for performance."* No surprises.

**4. Web Worker offloading (high effort, high impact)**
Move heavy computation (UMAP, FA, LDA Gibbs) off the main thread into a Web Worker. This prevents the UI from freezing on large datasets and allows true async cancellation. The algorithms themselves don't change — just the execution context.

**5. Streaming CSV parse (high effort)**
Currently all tools do `FileReader.readAsText` then parse the whole file at once. For files >50MB this can OOM the tab. A streaming parser (or chunked `readAsSlice`) would handle arbitrarily large files.

**Recommended starting point:** options 1 + 2 + 3 — visible indicators, slightly raised caps, and an upload warning. All three are small changes across a handful of files, and they address the most common user confusion without touching the algorithm architecture.

---

### Per-tool action plan (all tools)

| Tool | Current | Action |
|---|---|---|
| **Data Preprocessing** | No cap | Add warning >5k rows; show processing indicator |
| **AutoML** | No cap | Already scales iterations; just add warning |
| **FE — transforms** | No cap | Add warning >5k rows |
| **FE — LDA** | 1000 cap (silent) | Show "processing first 1000 rows" badge; raise to 2000 |
| **FS — filters/scoring** | No cap | Add warning >5k rows |
| **FS — PCA** | No cap | Add "N rows used" in result card |
| **FS — UMAP** | 400 sampled (silent) | Show "sampled 400 / N rows" in result card; raise to 600 |
| **FS — FA** | 500 sampled (silent) | Show "sampled 500 / N rows" in result card; raise to 800 |
| **FS — LDA** | No cap | Add "N rows used" in result card |

---

### "Sampled 400 / N rows" explained

**"sampled 400 / N rows"** — a small info line in the UMAP result card telling the user that out of their full dataset (say 5000 rows), only 400 were used to build the embedding graph. The remaining 4600 got their coordinates via kNN approximation, not the actual UMAP algorithm. So the user knows the scatter isn't computed on their full data.

**"raise to 600"** — change `const maxRows = 400` in `fsReduction.ts` to `const maxRows = 600`, so UMAP now samples 600 rows instead of 400 before applying kNN extension. More rows → more faithful manifold structure captured → slightly better embedding quality, at the cost of being ~2.25× slower (graph is O(n²), so 600² vs 400²).

Both are independent:
- The indicator is just a UI label — no algorithm change
- Raising the cap is a one-line code change — no UI change

---

### How indicators would show

For datasets under 600 rows:
> `All 350 rows used`

For larger datasets (UMAP):
> `Sampled 600 of 5,000 rows for graph construction · remaining 4,400 projected via kNN`

For FA:
> `Sampled 800 of 5,000 rows for factoring · remaining 4,200 projected via kNN`

For FE-LDA:
> `Processing first 2,000 of 5,000 rows (LDA row limit)`

For uncapped tools (PCA, FS-LDA, filters):
> `All 5,000 rows used`

---

### Hardware config estimation & complexity

**What we CAN detect in-browser:**
- `navigator.hardwareConcurrency` — number of CPU cores (accurate)
- `navigator.deviceMemory` — RAM in GB (Chrome/Edge only; returns rough buckets: 1, 2, 4, 8GB — Firefox/Safari don't expose this)
- A **micro-benchmark on first load** — multiply two 100×100 matrices, time it in ms → gives relative CPU speed (fast M2 vs slow mobile CPU shows 10–20× difference)

**What we CAN compute:**
Since we know `n` (rows), `p` (features), and the exact algorithm complexity:

| Algorithm | Complexity | Memory estimate |
|---|---|---|
| UMAP | O(n²) distance matrix | n² × 8 bytes (600² = 2.9MB) |
| FA | O(n·p²) + O(p³) | p×p matrix |
| PCA | O(n·p·k) | O(n·p) |
| FE-LDA Gibbs | O(D·V·K·iter) | O(D·K + V·K) |
| FS filters | O(n·p) | O(n·p) |

From complexity + benchmark speed → rough time estimate. Display before running:
```
⏱ ~4–7s   💾 ~15MB   complexity O(n²)
based on 2,400 rows · 8 features · your device (~4 cores, ~4GB RAM)
```

**What we CANNOT do reliably:**
- Exact RAM usage (JS GC is opaque)
- Guarantee time accuracy — tab throttling, GC pauses, other tabs all affect it
- CPU clock speed directly (benchmark gives relative, not absolute)

**Honest accuracy:** time estimates would be ±50–100% — useful as a "this will take seconds vs minutes" indicator, not a precise countdown. Memory estimates are more reliable since they're purely mathematical.

Would show on the upload card after a CSV is loaded, updating live as the user changes settings (e.g., moving the UMAP neighbours slider recalculates).

---

### Full complexity table (all tools)

| Tool | Algorithm | Complexity | Memory (n=2000, p=10) | Est. Time (mid-range device) | Notes |
|---|---|---|---|---|---|
| **Preprocessing** | Per-column ops (impute, scale, encode) | O(n·p) | ~1.6MB | <1s | No cap |
| **AutoML** | Simulated training + scoring | O(n·p·iter) | ~3–5MB | 2–10s | iter scales with n |
| **FE — transforms** | Scale / encode / bin per column | O(n·p) | ~1.6MB | <1s | No cap |
| **FE — LDA (Gibbs)** | O(D·V·K·iter) | ~D·K·8 bytes | 5–20s | Capped at 2000 rows |
| **FS — Variance / Corr / MI** | O(n·p) / O(p²) | ~p²·8 bytes | <1s | No cap |
| **FS — Lasso / Ridge** | O(n·p·iter) | ~n·p·8 bytes | 1–5s | No cap |
| **FS — Tree importance** | O(n·p·log n·trees) | ~n·trees·8 bytes | 3–10s | No cap; most expensive filter |
| **FS — RFE** | O(n·p²) | ~n·p·8 bytes | 2–8s | Eliminates one feature per round |
| **FS — Forward / Exhaustive** | O(n·p²) / O(n·C(p,k)) | ~n·p·8 bytes | 3s / up to minutes | Exhaustive auto-falls back at p>15 |
| **FS — PCA** | O(n·p·k) power iter | ~n·p·8 bytes | <1s | No cap; very fast |
| **FS — UMAP** | O(n²) distance + O(n·k) graph | n²·8 bytes (~2.9MB at n=600) | 5–15s | Sampled to 600 rows |
| **FS — FA** | O(n·p²) + O(p³) | ~p²·8 bytes | 2–8s | Sampled to 800 rows |
| **FS — LDA (Linear Disc.)** | O(n·p²) + O(p³) eigen | ~p²·8 bytes | <2s | No cap; p² dominates |

**Key observations:**
- **UMAP** has the worst memory scaling — n² blows up fast (5000² = 200MB, which is why it's capped)
- **Tree importance + Exhaustive** are the slowest unbounded algorithms
- **PCA and FS-LDA** are surprisingly cheap despite looking complex — p is usually small
- Everything runs in the **main JS thread** — any estimate over ~10s risks freezing the browser tab

---

## FE LDA Pipeline — Full 7-Step Process

1. **Build combined stopword set** — built-in ~320 industry-standard English words always applied. User custom stopwords (comma-separated) merged on top. Default list always active even if custom field is empty.
2. **Tokenize** — lowercase, strip non-alphanumeric, split on whitespace, drop tokens < 2 chars, remove stopwords.
3. **Stemming** (optional) — if toggle enabled: strip common suffixes (ing, tion, ness, ment, ies, es, ed, ly, er, s). Words ≤ 4 chars untouched.
4. **Build vocabulary** — count global word frequency, take top 500 most frequent as working vocabulary V.
5. **Min document frequency filter** — remove words appearing in fewer than `minDocFreq` documents (default 2). Drops noise/proper nouns unique to one row.
6. **Collapsed Gibbs Sampling** — iteratively reassign each token to topic k proportional to `(docTopic[d][k] + α) × (wordTopic[w][k] + β) / (topicTotal[k] + V·β)`. α=0.1, β=0.01. Seed=42 (deterministic). Runs for configured iterations.
7. **Output** — topic-document distribution θ[d][k] as columns `lda_topic_0`, `lda_topic_1`,… Top N words per topic shown as coloured chips (φ distribution).

---

## Pending Items

1. **Dataset size indicators + raised caps + upload warnings** — implement across all tools (options 1+2+3 from discussion). Files: `fsReduction.ts` (UMAP 400→600), `fsFA.ts` (FA 500→800), `feLDA.ts` (LDA 1000→2000), result cards in FS, upload components in all tools.
2. **Hardware config estimator** — detect `navigator.hardwareConcurrency`, `navigator.deviceMemory`, run micro-benchmark, compute per-algorithm time/memory estimates from n and p, show on upload card.
3. **Subagent Bash still blocked** — Bash commands (wc -l, tsc, git) denied in subagent context. Workaround: main session handles Bash steps. Root cause unresolved.
