# Conversation Part 153 — Drift: Smooth Curves, Radar Chart, AI Explain Fixes, Model Names
**Date:** 2026-07-04  
**Topics:** Smooth density curves on histograms, radar fingerprint chart, AI explain markdown rendering, Groq/Gemini/Cohere model fixes, chart sizing, cards scroll layout, drift improvement ideas

---

## Session Work

### 1. Smooth Density Curves on Histograms + Radar Chart

User pointed out that distribution overlay (smooth density curve) and radar/spider chart were never implemented despite being requested.

**`DriftCharts.tsx`** (new file, extracted from DriftFeatureCard):
- SVG-based histogram with grouped bars (training dim, batch solid) + catmull-rom smooth density curve overlay
- Dashed line = reference curve, solid line = batch curve
- Y-axis grid lines, x-axis labels, hover tooltips via `<title>`

**`DriftRadarChart.tsx`** (new file):
- Spider chart of all features — each spoke = one feature, radius = drift score
- Concentric grid rings at 25/50/75/100%
- Polygon fill + dots colored by drift level (red/amber/green)
- High-drift labels in red, low-drift in gray
- Inserted between DriftRankingChart and DriftAIExplain

**`DriftFeatureCard.tsx`** — removed inline `NumericHistogram` and `CategoricalBars` (imported from DriftCharts instead). File dropped from 378 → 265 lines.

**Commits:** `8541464` (ml-portfolio)

---

### 2. AI Explain Panel — Provider + Model Fixes

#### Errors encountered:
- **Cohere 404**: model `command-r-plus` deprecated in Cohere v2 API
- **Groq 401**: Invalid API Key
- **Gemini**: was using `gemini-2.0-flash`, codebase uses `gemini-2.5-flash`

#### Root cause of model name mistakes:
Used training-data memory instead of reading codebase. Correct source: `toolsAiProviders.ts`, `route.ts`, `useAutoMLExplain.ts`.

#### Fixes applied to `_explain.py`:
- Cohere: `command-r-plus` → `command-a-03-2025` (matches `toolsAiProviders.ts`)
- Gemini: `gemini-2.0-flash` → `gemini-2.5-flash` (matches codebase default)
- Groq: `llama-3.3-70b-versatile` — already correct

#### Added Gemini 2.5 + 3.5 as separate buttons (user request):
- `_PROVIDER_MODELS` expanded with `gemini-2.5-flash` and `gemini-3.5-flash` keys
- Family detection: `family = "gemini" if provider.startswith("gemini") else provider`
- Frontend: 4 provider buttons — Groq · Gemini 2.5 · Gemini 3.5 · Cohere
- Default changed to Cohere

**Commits:** `af5f9f0`, `01524f4`, `b85d0db`, `6b8f2f6`, `c97896f`, `b8df9b2` (various fixes)

#### Groq 401 resolution:
- Not a code issue — base_url is correctly set to `https://api.groq.com/openai/v1`
- Google AI's diagnosis ("sending Groq key to OpenAI servers") was wrong
- Root cause: GROQ_API_KEY in HF Space was stale/wrong key
- User deleted and re-added `AIRaML` key (gsk_...XCK0) → Groq now working

#### Cohere key:
- Was missing from HF Space secrets entirely
- User added it → Cohere now working

---

### 3. Markdown Rendering for AI Output

AI output was showing raw markdown (`###`, `**bold**`, `---`) as plain text.

**Fix in `DriftAIExplain.tsx`:**
- Added `import ReactMarkdown from "react-markdown"` (already in package.json)
- Replaced `whiteSpace: "pre-wrap"` div with `<ReactMarkdown>` with styled components for h1/h2/h3, p, strong, hr, ul, ol, li, code

**Commit:** `00b8545`

---

### 4. Chart Size + Cards Layout Fixes

**Histogram too large:**
- `DriftCharts.tsx`: VH reduced 140 → 100, added `maxHeight: 160px` on SVG

**Cards not multiple of 3 → horizontal scroll:**
- `MLCapabilities.tsx`: changed condition from `isOdd || isSmall` to `capabilities.length % 3 !== 0`

**Commit:** `00b8545`

---

### 5. TypeScript Fixes

- `TS2345`: `p.id` string not assignable to `ProviderId` — fixed with `p.id as ProviderId` cast
- `ProviderId` type moved above `PROVIDERS` array declaration
- **Commit:** `b8df9b2`, `c97896f`

---

### 6. L6 vs L12 Embedding Question

User noticed health endpoint shows `all-MiniLM-L6-v2`. Clarification:
- **Embedding model** (vectorizes docs/queries): `all-MiniLM-L6-v2` — unchanged, correct
- **Reranker** (re-scores retrieved candidates): upgraded to `cross-encoder/ms-marco-MiniLM-L-12-v2` in commit `ef3dd31`
- These are two different components; health endpoint reports embedding model only

---

### 7. Drift Improvement Ideas (Text Only — Not Implemented)

User asked for visual enrichment ideas. Recommendations (in priority order):

1. **CDF overlay** — Plot empirical CDFs of ref vs batch on same chart. KS stat = max gap between CDFs. Makes KS test self-explanatory. Industry standard in Evidently AI, NannyML, WhyLogs.
2. **Drift heatmap over time** — Matrix (features × batches), color = drift level. Shows which features consistently drift vs spike.
3. **Percentile shift table** — P5/P25/P50/P75/P95 ref vs batch. More robust than mean/std for skewed data.
4. **Correlation change heatmap** — Feature-to-feature correlation for training vs batch. Catches structural drift invisible in per-feature views.
5. **PSI bin waterfall** — Which value ranges drive the PSI score.

**Layout improvement:** Feature cards in 2-column grid on wide screens; Ranking + Radar side by side.

---

## All Commits This Session

| Hash | Repo | Description |
|------|------|-------------|
| `8541464` | ml-portfolio | feat(drift): smooth density curves + radar fingerprint chart |
| `af5f9f0` | ML-Unified | fix(drift): cohere model command-r-plus → command-r-plus-08-2024 |
| `01524f4` | ML-Unified | fix(drift): cohere model → command-a-03-2025 |
| `b85d0db` | ML-Unified | feat(drift): gemini-2.5-flash + gemini-3.5-flash; family routing |
| `6b8f2f6` | ml-portfolio | feat(drift): Gemini 2.5 + 3.5 buttons; default Gemini 2.5 |
| `c97896f` | ml-portfolio | fix(drift): ProviderId type ordering; default cohere |
| `b8df9b2` | ml-portfolio | fix(drift): cast p.id as ProviderId (TS2345) |
| `00b8545` | ml-portfolio | feat(drift): markdown render; smaller histogram; cards scroll |

HF Space uploads done for `_explain.py` after each backend commit.

---

## Files Changed

| File | Status |
|------|--------|
| `src/app/tools/drift/DriftCharts.tsx` | new |
| `src/app/tools/drift/DriftRadarChart.tsx` | new |
| `src/app/tools/drift/DriftFeatureCard.tsx` | modified (265 lines) |
| `src/app/tools/drift/DriftRunner.tsx` | modified |
| `src/app/tools/drift/DriftAIExplain.tsx` | modified |
| `src/components/MLCapabilities.tsx` | modified |
| `services/ml-api/routers/drift/_explain.py` | modified |

---

## Pending Drift Improvements (Not Yet Built)

~~- CDF overlay per feature card~~ ✓ done
~~- Drift heatmap over time (multi-batch)~~ ✓ done
~~- Percentile shift table (P5–P95)~~ ✓ done
~~- Correlation change heatmap~~ ✓ done
~~- PSI bin waterfall~~ ✓ done
- 2-column feature card grid on wide screens (deferred)

---

---

# Session Continuation — 2026-07-04 (Part 154)
**Topics:** Build all 5 drift visualizations, layout fixes, equal-height grid boxes

---

## 1. All 5 Drift Visualizations Built

User confirmed "build in that order 1,2,3,4,5" referring to the improvement ideas from Part 153.

### Backend changes (`ML-Unified`)

**`_state.py`** — Added `label` field to history snapshot features so the heatmap can show human-readable feature names instead of raw names.

**`_compute.py`** — Two additions to `_process_numeric`:
```python
# Percentiles
if len(vals) >= 5:
    feat["recent_pct"] = [round(float(np.percentile(vals, p)), 4) for p in [5,25,50,75,95]]
    _z = [-1.6449, -0.6745, 0.0, 0.6745, 1.6449]
    feat["ref_pct"] = [round(ref_mean + z * ref_std, 4) for z in _z]
```
And in `compute_drift`:
```python
# Re-extract vals per numeric feature → compute Pearson correlation matrix
_corr_vals: dict[str, tuple] = {}
# ... collect in loop ...
if len(_corr_vals) >= 2:
    result["correlation"] = _build_correlation(_corr_vals)
```
`_build_correlation` uses `np.corrcoef` on all numeric features simultaneously.

**`__init__.py`** — `/drift/{model_id}/history` GET endpoint was already present.

### Frontend new files (`ml-portfolio`)

**`DriftCharts.tsx`** — Added `CDFChart` export:
- Computes empirical CDF from histogram bins (cumulative sum of `ref_h` / `actual_h`)
- Dashed = ref CDF, solid = batch CDF
- KS stat label shown in header
- Subtitle: "Cumulative probability. Max vertical gap = KS statistic."

**`DriftExtraCharts.tsx`** (new, 116 lines):
- `PercentileTable` — shows P5/P25/P50/P75/P95 ref vs batch, delta column, yellow highlights >15% relative shift
- `PSIWaterfall` — density difference per bin (batch_p − ref_p). Orange bars = batch excess, blue bars = batch deficit. Total PSI annotated in header.

**`DriftHeatmap.tsx`** (new, 153 lines):
- Fetches `/drift/{modelId}/history` on mount
- Renders only when ≥2 batches in history
- SVG grid: features (Y) × batches (X), Overall row at top
- Color: green (<35%) → yellow (35–65%) → red (>65%)
- Column labels rotated -35°, batch labels truncated
- Legend + description: "features × batches matrix — shows which features drift consistently vs spike once"

**`DriftCorrelation.tsx`** (new, 123 lines):
- Receives `correlation: { features: string[], matrix: number[][] }` from result
- SVG grid: red = positive Pearson r, blue = negative, diagonal = ACCENT background
- Column labels rotated -40°, label truncation at 11 chars
- Cell font-weight 700 when |r| > 0.5
- Description: "Pearson r between all numeric features. Strong off-diagonal = structural drift invisible in per-feature views."

### Frontend modified files

**`driftTypes.ts`**:
```typescript
// Added to FeatureDrift:
recent_pct?: number[];  // [P5, P25, P50, P75, P95]
ref_pct?: number[];

// Added new type:
export type CorrelationData = { features: string[]; matrix: number[][] };

// Added to DriftResult:
correlation?: CorrelationData;
```

**`DriftFeatureCard.tsx`** — Added section inside expanded numeric card:
```tsx
{/* CDF · PSI Waterfall · Percentile Table */}
{f.type === "numeric" && f.histogram && f.histogram.length > 0 && !highNull && (
  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
    <CDFChart bins={f.histogram} ksLabel={f.ks_stat} />
    <PSIWaterfall bins={f.histogram} psi={f.psi} />
    {f.ref_pct && f.recent_pct && (
      <div style={{ gridColumn: "1 / -1" }}>
        <PercentileTable f={f} />
      </div>
    )}
  </div>
)}
```

**`DriftRunner.tsx`** — Results section restructured:
```tsx
<DriftOverview result={result} />
<div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: "1.25rem" }}>
  <DriftRankingChart features={result.features} />
  <DriftRadarChart features={result.features} />
</div>
{result.correlation ? (
  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
    <DriftHeatmap modelId={modelId} />
    <DriftCorrelation correlation={result.correlation} />
  </div>
) : <DriftHeatmap modelId={modelId} />}
<DriftAIExplain result={result} modelId={modelId} />
```

---

## 2. Issues Found After Screenshot Review

User sent screenshot showing:
1. **Too much horizontal space** — page was constrained to `maxWidth: 960`
2. **CDF/PSI/Percentile not visible** — hidden behind a 3-step toggle (expand card → see toggle → click toggle)
3. **Boxes different sizes** — `alignItems: "start"` on grids prevents equal height

### Fixes applied

**Visibility fix** — Removed the `showExtra` toggle entirely. CDF, PSI Waterfall, and Percentile Table now visible by default whenever a numeric feature card is expanded.

**Width fix** — `page.tsx`: `maxWidth: 960 → 1280` for both header and content container. Drift is a data-dense dashboard; 960 was too narrow.

**Equal height fix** — Removed `alignItems: "start"` from both grid containers in `DriftRunner.tsx`. CSS Grid default (`stretch`) makes both cells in each row match the tallest item's height.

---

## All Commits This Session (Part 154)

| Hash | Repo | Description |
|------|------|-------------|
| `372b30d` | ML-Unified | feat(drift): percentile shift, correlation matrix, snapshot labels |
| `ba9b934` | ml-portfolio | feat(drift): CDF overlay, heatmap, percentile table, correlation, PSI waterfall |
| `909fd5c` | ml-portfolio | fix(drift): show CDF/PSI/percentiles by default; 2-col layout; descriptions |
| `ae515e7` | ml-portfolio | fix(drift): expand page maxWidth 960 → 1280 for dashboard-density layout |
| `2a0dd2a` | ml-portfolio | fix(drift): equal-height grid cells — remove alignItems:start |

HF Space uploads done for `_compute.py` and `_state.py` after backend commit.

---

## Files Changed (Part 154)

| File | Status | Lines |
|------|--------|-------|
| `services/ml-api/routers/drift/_compute.py` | modified | 210 |
| `services/ml-api/routers/drift/_state.py` | modified | 106 |
| `src/app/tools/drift/driftTypes.ts` | modified | — |
| `src/app/tools/drift/DriftCharts.tsx` | modified | 251 |
| `src/app/tools/drift/DriftExtraCharts.tsx` | new | 116 |
| `src/app/tools/drift/DriftHeatmap.tsx` | new | 153 |
| `src/app/tools/drift/DriftCorrelation.tsx` | new | 123 |
| `src/app/tools/drift/DriftFeatureCard.tsx` | modified | 293 |
| `src/app/tools/drift/DriftRunner.tsx` | modified | 153 |
| `src/app/tools/drift/page.tsx` | modified | — |

---

---

# Session Continuation — 2026-07-04 (Part 155)
**Topics:** RAG chat AI errors, dynamic drift context, cache bugs, scroll issues, cross-provider key contamination, Groq system prompt missing

---

## 1. Provider Error Strings Leaking into Cache and Query Expansion

**Root cause chain discovered:**
- `stream_cohere` and `stream_gemini` yielded error strings (`[Cohere error 429]`, `[Gemini error 400]`) as normal tokens
- These got stored as `{role: "assistant"}` messages in chat history
- Next request sent them as history → Gemini received two consecutive `model` turns → **Gemini 400 Bad Request**
- Same error strings leaked into `expand_query` as "query variants" (visible in "QUERY VARIANTS SEARCHED" UI section)
- Semantic cache stored the error string as a valid response → same question returned cached error

**Fixes applied:**

`llm.py` — `stream_cohere` and `stream_gemini`: changed `yield f"[Provider error NNN]"` → `raise` so exceptions propagate cleanly. `complete()` catches them and returns `""`. `expand_query` gets `""` → returns `[query]` only.

`query.py` — Added `generation_failed` flag: if any yielded token matches error pattern (`startswith("[")` and `"error" in token`), set flag and skip caching. Error surfaces via `{"type": "error"}` SSE, not as a token.

`useRagChat.ts` — `sanitizeHistory()`: strips `Error:`/`No response.` assistant messages and deduplicates consecutive same-role turns before sending history. Prevents Gemini 400.

`useRagChat.ts` — Added `hadError` flag: suppresses "No response." when error message already shown (prevented double message).

`ChatMessageList.tsx` — Added `overscrollBehavior: "contain"` to message container (prevents page scroll on chat wheel).

---

## 2. Cross-Provider API Key Contamination → Groq 401

**Root cause:** The API KEY field in settings is shared across all providers. User had entered Cohere key → switched to Groq → Cohere key sent as `user_key` to Groq endpoint → 401.

**Fix:** `useRagChat.ts` — `setUserKey("")` called when provider changes.

**Regression introduced:** `setUserKey("")` also fired on initial mount when localStorage provider was read, wiping saved API keys for ALL users on every page load → broke chat AI in all other tools.

**Fix for regression (pending commit):** Added `mountedRef` — `setUserKey("")` only runs after first mount:
```ts
const mountedRef = useRef(false);
useEffect(() => {
  // load from localStorage
  mountedRef.current = true;
}, []);
useEffect(() => {
  if (!mountedRef.current) return;
  localStorage.setItem(LS_PROVIDER, provider);
  setUserKey("");
}, [provider]);
```

---

## 3. Dynamic Drift Context in AI Chat

**Problem:** `ToolsAIChat` on drift page received only a hardcoded static string — LLM had no knowledge of the actual uploaded CSV or drift results.

**Fix:**
- `DriftRunner.tsx`: added `onResult?: (r: DriftResult | null) => void` prop; called on upload success and on clear
- `page.tsx`: added `driftResult` state, `buildDriftContext()` function that formats actual feature data:
  ```
  Batch: test.csv | Rows: 5000 | Overall drift: 87.0% (high)
  Total features: 8 | High drift: 3 | Medium: 2 | Low: 3
  HIGH drift features: Annual Income (numeric, drift=87.0%, PSI=0.842, KS=0.421); ...
  ```
- Missing `FeatureDrift` import caused Vercel build failure (TypeScript error) → fixed in separate commit `78ad509`

---

## 4. Semantic Cache Bugs

**Bug 1 — Stale error entries replayed:** Cache stored error strings before `generation_failed` fix. Even after fix, old entries persisted in memory. Fix: guard in cache hit path discards entries where `full_text` matches error pattern.

**Bug 2 — Provider cross-contamination:** Cache key was query embedding only — Groq's cached response served to Gemini for same query. Fix (pending commit): `_cache_lookup` and `_cache_store` now include `provider` in key; entries only match same-provider lookups.

---

## 5. Groq System Prompt Not Passed

**Root cause:** `stream_groq_openai` only received `messages` (history + user query). `system_prompt` (containing tool context + retrieved chunks) was built but never passed for Groq/OpenAI — only Claude, Gemini, Cohere received it.

**Fix (pending commit):**
```python
if provider in ("groq", "openai"):
    full_messages = [{"role": "system", "content": system_prompt}] + messages if system_prompt else messages
    token_iter = stream_groq_openai(provider, model, key, full_messages)
```

---

## 6. In-Memory RAG Index Lost on HF Space Restart

**Explanation given:** RAG uses ChromaDB in-process (in-memory). Every HF Space restart (triggered by each `api.upload_file()` call) clears the index. User-ingested documents are lost; only 13 pre-seeded ML docs remain. Fix requires persisting ChromaDB to `/data/` directory — deferred task.

---

## All Commits This Session (Part 155)

| Hash | Repo | Description |
|------|------|-------------|
| `597a135` | ML-Unified | fix(rag): skip caching provider error tokens; surface provider/model in error message |
| `37c4e01` | ml-portfolio | fix(chat): contain scroll in message list — prevent page scroll on chat wheel |
| `2de18a4` | ML-Unified | fix(rag): raise on HTTP errors in stream_cohere/stream_gemini instead of yielding error strings |
| `0146ae3` | ml-portfolio | fix(chat): sanitize history before send — remove error turns, enforce alternating roles |
| `1793a28` | ml-portfolio | fix(chat): clear userKey on provider switch — prevents cross-provider key contamination |
| `51d3a9f` | ml-portfolio | fix(drift/chat): dynamic drift context; scroll containment; no-double-error message |
| `78ad509` | ml-portfolio | fix(drift): add missing FeatureDrift import — fixes Vercel build failure |
| `2bbec1f` | ML-Unified | fix(rag): discard stale error entries from semantic cache on hit |

HF Space uploads done for `query.py` and `llm.py`.

**Pending (not yet committed — blocked by session):**
- `mountedRef` fix in `useRagChat.ts` (setUserKey regression)
- Groq system prompt fix in `query.py`
- Provider-aware cache key in `query.py`

---

## Files Changed (Part 155)

| File | Repo | Change |
|------|------|--------|
| `services/ml-api/routers/rag/llm.py` | ML-Unified | raise instead of yield on HTTP errors |
| `services/ml-api/routers/rag/query.py` | ML-Unified | generation_failed flag; stale cache guard; Groq system prompt (pending); provider cache key (pending) |
| `src/components/useRagChat.ts` | ml-portfolio | sanitizeHistory; hadError; mountedRef fix (pending) |
| `src/components/ChatMessageList.tsx` | ml-portfolio | overscrollBehavior: contain |
| `src/components/ToolsAIChatSettings.tsx` | ml-portfolio | overscrollBehavior: contain |
| `src/app/tools/drift/DriftRunner.tsx` | ml-portfolio | onResult callback prop |
| `src/app/tools/drift/page.tsx` | ml-portfolio | buildDriftContext(); FeatureDrift import fix |
