# Conversation — 2026-06-21 — ML-Unified Part 113

## Context
Continuation of Part 112. All work is on ml-portfolio (Next.js frontend) at `/Users/wrks/Downloads/Claude-documentation/Projects/ml-portfolio`.

---

## Session Summary

### FE LDA Pipeline — Full Process Explained
All 7 steps run automatically on every "Run LDA" click. No manual step triggering. Steps:
1. Build combined stopword set (built-in ~320 + custom)
2. Tokenize (lowercase, strip punctuation, split, drop short tokens, remove stopwords)
3. Stemming (optional, suffix stripping)
4. Build vocabulary (top 500 most frequent)
5. Min document frequency filter (drop words in fewer than minDocFreq docs)
6. Collapsed Gibbs Sampling (iterative topic reassignment)
7. Output (lda_topic_0, lda_topic_1, … columns + top-words chips)

### Stopwords: 64 → ~320
Expanded STOPWORDS set in `feLDA.ts` to ~320 industry-standard English words. Covers articles, conjunctions, prepositions, pronouns, auxiliaries, numbers as words, time/place words, negation contractions (without apostrophe). No legal issue mentioning spaCy (MIT license) but phrasing changed to "industry-standard coverage" since list was independently written.

**Commits:** `b0bebb1`, `aaab53b`, `e8acad2`

---

### API Error: 400 Output blocked by content filtering policy
Comes from the Claude API when CSV data + column descriptions trigger Anthropic's content filter. Filter runs before Claude responds. Most common cause: dataset contains text resembling violence, hate speech, or adult content (even in column names/values). Nothing broken in the tool — data triggers it. Test with a different dataset to confirm.

---

### Dataset Size Limits (full reference — see Part 112 for word-for-word)

| Tool | Row limit | How excess handled |
|---|---|---|
| Data Preprocessing | No hard cap | All rows processed |
| AutoML | No hard cap | Iterations scale with n |
| FE — transforms | No hard cap | All rows |
| FE — LDA | **2000** (raised from 1000) | `texts.slice(0, 2000)` |
| FS — filters/scoring | No hard cap | All rows |
| FS — PCA | No hard cap | All rows |
| FS — UMAP | **600** (raised from 400) | Sub-samples; kNN extension |
| FS — FA | **800** (raised from 500) | Sub-samples; kNN extension |
| FS — LDA | No hard cap | All rows |

No file size check anywhere — ceiling is user's browser RAM. 100k-row CSV parses fine but heavy algorithms (UMAP, exhaustive search) will freeze.

---

### Live Dataset Estimator + Size Warnings

**New files created:**
- `src/lib/hardwareEstimator.ts` — CPU micro-benchmark, hardware detection, per-algorithm time+memory formulas
- `src/components/DatasetEstimator.tsx` — live display component
- `src/components/FEPanels/FEUploadInfo.tsx` — FE tool wrapper (keeps page.tsx under 400L)

**How the estimator works:**

1. **CPU micro-benchmark** — runs once on page load: times 2,000,000 float operations (`Math.sqrt(i + 0.5) * 0.001`), caches result as `opsPerMs`. All subsequent estimates are instant.

2. **Hardware detection:**
   - `navigator.hardwareConcurrency` — CPU cores (accurate, all browsers)
   - `navigator.deviceMemory` — RAM in GB (Chrome/Edge only; rough buckets 1/2/4/8GB; null on Firefox/Safari)

3. **Per-algorithm estimates** — derived from known complexity formulas × opsPerMs:
   - UMAP: O(n²·p) for distance matrix, n capped at 600
   - FA: O(n·p²) + O(p³), n capped at 800
   - PCA: O(n·p·k·iter)
   - FE-LDA Gibbs: O(D·V·K·iter), D capped at 2000
   - FS-LDA: O(n·p²), fast
   - Tree: O(n·p·log(n)·trees), slowest filter
   - Lasso/Ridge: O(n·p·iter)
   - RFE: O(n·p²·rounds)
   - Forward/Exhaustive: O(n·p²) / O(n·C(p,k)), exhaustive falls back at p>15

4. **Accuracy:** ±50–100% — useful for "seconds vs minutes" distinction, not precise countdown. Memory estimates more reliable (purely mathematical).

**Display format (on upload card, updates live with settings):**
```
4 cores · 4GB RAM     ⏱ 4–7s     💾 15MB
                              ▼ per-algorithm
```

Expandable breakdown shows each algorithm with complexity, time range, memory, and sampling note.

**Size warnings:**
- n > 2,000: yellow badge — "Large dataset — some algorithms will be slow. Sampling applied automatically where noted."
- n > 10,000: red badge — "Very large dataset — heavy algorithms may freeze the browser tab. Consider sampling first."

**Live update:** estimator re-derives on every `opts` change (UMAP neighbours slider, toggle algorithms on/off, number of components, etc.) since `opts` is a dependency.

**Sampling indicators in result cards:**
- UMAP: dynamic — "graph on 600 rows · 4,400 projected via kNN" (only shown when n > 600)
- FA: "factoring on 800 rows · N projected via kNN" (only shown when n > 800)
- LDA: "N rows used (all rows)"

**Static notes added:**
- Preprocessing upload: "All rows processed in-browser · large files (>5,000 rows) may be slow"
- AutoML upload: "All rows processed · iteration count auto-scales with dataset size"

---

### Full Algorithm Complexity Table

| Tool | Algorithm | Complexity | Memory (n=2000, p=10) | Est. Time (mid-range) | Notes |
|---|---|---|---|---|---|
| Preprocessing | Per-column ops | O(n·p) | ~1.6MB | <1s | No cap |
| AutoML | RF+XGB+LGB+Cat | O(n·p·iter) | ~3–5MB | 2–10s | iter scales with n |
| FE — transforms | Scale/encode/bin | O(n·p) | ~1.6MB | <1s | No cap |
| FE — LDA (Gibbs) | O(D·V·K·iter) | ~D·K·8 bytes | 5–20s | Cap 2000 rows |
| FS — Variance/Corr/MI | O(n·p) / O(p²) | ~p²·8 bytes | <1s | No cap |
| FS — Lasso/Ridge | O(n·p·iter) | ~n·p·8 bytes | 1–5s | No cap |
| FS — Tree | O(n·p·log n·trees) | ~n·trees·8 bytes | 3–10s | Most expensive filter |
| FS — RFE | O(n·p²·rounds) | ~n·p·8 bytes | 2–8s | One feature eliminated per round |
| FS — Forward/Exhaustive | O(n·p²) / O(n·C(p,k)) | ~n·p·8 bytes | 3s / up to minutes | Auto-fallback at p>15 |
| FS — PCA | O(n·p·k) power iter | ~n·p·8 bytes | <1s | Very fast |
| FS — UMAP | O(n²) distance graph | n²·8 bytes (~2.9MB at 600) | 5–15s | Cap 600 rows |
| FS — FA | O(n·p²) + O(p³) | ~p²·8 bytes | 2–8s | Cap 800 rows |
| FS — LDA (Discriminant) | O(n·p²) + O(p³) | ~p²·8 bytes | <2s | p² dominates |

Key observations:
- UMAP worst memory scaling — n² blows up (5000² = 200MB, reason for cap)
- Tree + Exhaustive slowest unbounded
- PCA + FS-LDA surprisingly cheap — p is usually small
- Everything on main JS thread — estimates >10s risk freezing tab

---

## Commit 139920a — Full Delivery Summary

Commit `139920a` pushed. Everything done:

**New files:**
- `hardwareEstimator.ts` — CPU micro-benchmark, core/RAM detection, per-algorithm time+memory formulas for all 13 algorithms
- `DatasetEstimator.tsx` — live display component: ⏱ time range, 💾 memory, yellow/red size warnings, expandable per-algorithm breakdown
- `FEUploadInfo.tsx` — thin wrapper to keep FE page.tsx under 400L

**Raised caps:**
- UMAP: 400 → 600 rows
- FA: 500 → 800 rows
- FE-LDA: 1000 → 2000 rows

**Live estimator (FS tool):**
- Shows after CSV upload on the upload card
- Updates live as you change any setting (UMAP neighbours, number of components, toggle algorithms on/off, etc.)
- Hardware line: "4 cores · 8GB RAM" (Chrome/Edge); "4 cores" only on Firefox/Safari
- Benchmarks CPU on first load, caches it — all subsequent estimates are instant
- Per-algorithm breakdown expandable, shows sampling notes inline

**Sampling indicators in result cards:**
- UMAP: "graph on 600 rows · 4,400 projected via kNN" (dynamic)
- FA: "factoring on 800 rows · N projected via kNN" (only shown when n > 800)
- LDA: "N rows used (all rows)"

**Static notes:**
- Preprocessing upload: "large files (>5,000 rows) may be slow"
- AutoML upload: "iteration count auto-scales with dataset size"

---

## All Commits This Session

| Commit | Description |
|---|---|
| `b0bebb1` | feat(fe): expand LDA stopwords from 64 to ~320 |
| `aaab53b` | docs(fe): update LDA pipeline stopword count ~60 → ~320 |
| `e8acad2` | docs(fe): replace 'spaCy-equivalent' with 'industry-standard coverage' |
| `139920a` | feat(all): live dataset estimator, size warnings, raised algo caps, sampling indicators |

---

## Architecture Notes

### hardwareEstimator.ts exports
- `runBenchmark(): Promise<number>` — returns opsPerMs, cached after first run
- `getHardware(): { cores, memGB }` — reads navigator APIs
- `estimateFS(n, p, opts, opsPerMs): AlgoEstimate[]` — FS tool, respects enabled opts
- `estimateFELDA(n, vocabCap, k, iter, opsPerMs): AlgoEstimate`
- `estimatePreprocessing(n, p, opsPerMs): AlgoEstimate`
- `estimateAutoML(n, p, opsPerMs): AlgoEstimate`
- `fmtTime(min, max): string` — "~3s", "2–8s", "1min"
- `fmtMem(mb): string` — "<1 MB", "15 MB", "1.2 GB"

### DatasetEstimator.tsx props
```tsx
interface Props {
  n: number;          // row count
  p: number;          // feature count
  tool: "fs" | "fe" | "preprocessing" | "automl";
  fsOpts?: SelectionOpts;   // FS tool — drives per-algo estimates
  ldaEnabled?: boolean;     // FE tool
  ldaTopics?: number;
  ldaIter?: number;
}
```

---

## Pending Items

1. **Playwright automated tests** — upload a CSV, verify configure step shows all 4 toggles, verify DatasetEstimator appears in correct step, verify sampling indicators show in FS result cards after algorithm runs.
2. **AutoML + Preprocessing DatasetEstimator** — row count only available after parse (inside modal state), not at upload step. Static notes added as workaround.
3. **Subagent Bash still blocked** — Read/Edit work but Bash (wc -l, tsc, git) denied in subagent context. Workaround: main session handles Bash steps.
4. **Web Worker offloading** (high effort) — move UMAP/FA/Gibbs off main thread to prevent freezing on large datasets.
5. **Streaming CSV parse** (high effort) — handle files >50MB without OOM.

## Completed This Session (Part 113)

| Commit | Repo | What |
|---|---|---|
| `3719207` | ml-portfolio | fix: ConfigurePanel toggles 2×2 grid + FEUploadInfo moved to configure step |
| `d45d2a6` | ml-portfolio | fix: large-file warning on standalone preprocessing page + AutoML 30s timeout |
| `737bd65` | ml-portfolio | feat: Dockerfile, .env.example, next.config standalone, .gitignore fix |
| `6ba7e89` | ML-Unified | feat: docker-compose.yml — spins up backend + frontend together |
| `11d956f` | ml-portfolio | fix: minHeight:0 on ConfigurePanel — both left and right panels now scroll |

## DatasetEstimator — Pending Changes (agreed, not yet implemented)

Changes to make across `DatasetEstimator.tsx`, `hardwareEstimator.ts`, `AutoMLSteps/Step1Upload.tsx`, `AutoMLModal.tsx`, `PreprocessingPanels/ConfigurePanel.tsx`:

1. Remove `navigator.deviceMemory` RAM display (inaccurate browser API)
2. Add **Recommended RAM** — minimum RAM needed for this dataset + tool (computed from memory estimates)
3. Keep **Estimated time** — already working
4. Keep **Estimated memory consumption** — already working
5. AutoML: move "All rows processed" note — only show after file uploaded, not before
6. AutoML: add DatasetEstimator to config step (currently shows time estimate only)
7. Preprocessing: add DatasetEstimator to configure step

## Platform-Independent Setup

- `docker-compose up` from ML-Unified root starts both services locally — no external platform needed
- Backend runs inside Docker on port 8000; frontend on port 3000; fully self-contained
- `BACKEND_URL` only needed if backend is already deployed elsewhere and you want to point at it:
  - HuggingFace: `BACKEND_URL=https://username-spacename.hf.space docker-compose up`
  - Railway: `BACKEND_URL=https://your-service.railway.app docker-compose up`
  - Render: `BACKEND_URL=https://ml-unified.onrender.com docker-compose up`

| Platform | Where to find URL | Example |
|---|---|---|
| HuggingFace | Space page → top bar | `BACKEND_URL=https://wrks-ml-unified.hf.space docker-compose up` |
| Railway | Project → Service → Settings → Domains | `BACKEND_URL=https://ml-unified.railway.app docker-compose up` |
| Render | Service → top of dashboard | `BACKEND_URL=https://ml-unified.onrender.com docker-compose up` |
- `.env.local` gitignored (local only); `.env.example` committed as template
