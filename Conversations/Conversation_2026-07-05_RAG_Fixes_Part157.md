# Conversation — 2026-07-05 · RAG Fixes & Tiered Retrieval · Part 157

## Session Summary

Continuation from Part 156. Fixed 0-candidate retrieval, Jina error, settings scroll, and built tiered answer source + confidence badge system.

---

## Issues Fixed

### 1. chunks_indexed: 0 (commit `32425a8`)

**Problem:** `app.py` defaulted `DATA_DIR` to `/data` (absolute, HF Space persistent disk). KB `.md` files live at `data/knowledge_base/` (repo-relative). On HF Space, `/data/knowledge_base/` never existed.

**Fix:** Changed default `DATA_DIR` from `"/data"` to `"data"` (relative) in both `app.py` and `routers/rag/__init__.py`.

**Also:** Uploaded all 17 KB markdown files to HF Space at `data/knowledge_base/`.

**Result:** `chunks_indexed: 47` confirmed.

---

### 2. Jina `RustBindingsAPI` error (commit `32425a8`)

**Problem:** `'RustBindingsAPI' object has no attribute 'bindings'` — tokenizers version incompatibility on HF Space CPU environment.

**Fix:** Pinned `tokenizers>=0.20,<0.21` in `requirements.txt`.

**Result:** `jina_error: null` confirmed.

---

### 3. Settings scroll — `preventDefault` missing (commit `4d49595`)

**Problem:** Previous fix used `e.stopPropagation()` which stops JS event bubbling but NOT the browser's native scroll behavior. `e.preventDefault()` is required.

**Fix:** `ToolsAIChatSettings.tsx` handler changed to `{ e.preventDefault(); e.stopPropagation(); }`.

**Playwright result:** `eventDefaultPrevented: true, docGotEvent: false, verdict: "FIXED"`.

---

### 4. Tiered Answer Source + Confidence Badge (commits `6568a37`, `f865aa0`)

**Problem:** All responses labeled generically. CRAG web fallback was firing even when a dataset was loaded, causing Investopedia results to override actual CSV stats.

**Fix:**
- `query.py`: Added `has_dataset = bool(req.tool_context.strip())`
- CRAG condition changed to `if low_confidence and not has_dataset:`
- Added `_determine_answer_source()` — tags as `dataset/uploaded_doc/knowledge_base/web`
- Added `_determine_confidence()` — score-based (high ≥0.5, medium ≥0.15, low <0.15)
- Both emitted in `done` SSE event and stored in semantic cache
- `useRagChat.ts`: Added `answerSource`, `confidence` state, parsed from done event
- `ChatMessageList.tsx`: Confidence badge rendered below each assistant response

**Badge examples:** `Dataset · HIGH CONFIDENCE` (green), `Knowledge Base · medium confidence` (amber), `Web · low confidence` (red)

---

### 5. Drift page thin context (commit `5420029`)

**Problem:** `buildDriftContext()` included drift scores but not per-column stats. LLM couldn't answer "what is income range?" even though `FeatureDrift` had `recent_mean`, `recent_std`, `recent_pct`.

**Fix:** Updated `featLine()` to include `batch_mean`, `batch_std`, `batch_range=[P5,P95]`, `ref_mean`, `ref_std` for every feature.

---

### 6. Confidence bump when dataset + KB combined (commit `3ba9c7c`)

**Problem:** When dataset was loaded AND KB chunks were retrieved, confidence showed Low (KB rerank scores naturally low against dataset-specific questions). But LLM had both sources — shouldn't be Low.

**Fix:** `_determine_confidence()` accepts `has_dataset` param. When true, thresholds lowered by one tier (≥0.3→high, ≥0.05→medium, else medium — never low when dataset present).

---

### 7. "How I Searched" missing in Deep Search (commit `3ba9c7c`)

**Problem:** Deep Search routes to `/rag/agent`. Agent's done event didn't emit `expanded_queries`, `candidates_retrieved`, `answer_source`, or `confidence` — so "How I Searched" section never rendered and no confidence badge showed.

**Fix:** Added all four fields to `agent.py` done event. Rewritten query surfaced as `expanded_queries` when it differs from original.

---

## Root Cause Analysis: "0 candidates" in How I Searched

When `chunks_indexed: 0`, retrieval returns nothing. CRAG fires (web fallback). Sources shown are web chunks but `candidates_retrieved = 0`. This was the symptom of the KB not being indexed — now resolved with 47 chunks indexed.

---

## Design Decisions

### Why not call LLM for confidence grading?
Extra LLM call adds latency + cost. Score-based heuristic (top rerank score) is deterministic and fast. Honest for web too — a good web result scores high → Medium or High confidence, not hardcoded Low.

### Why suppress CRAG when dataset loaded?
`tool_context` already gives the LLM exact column stats (mean, std, range). Web search overrides this with generic info. Dataset questions should be answered from actual data, not Investopedia.

### Answer source tiers
Priority design (retrieval not yet tiered, only labeling is tiered):
1. **Dataset** — tool_context (exact CSV stats)
2. **Uploaded doc** — user's ingested documents (`uploaded=True` metadata)
3. **Knowledge Base** — pre-seeded ML theory docs
4. **Web** — CRAG fallback, only when no dataset

---

## Commits

| Hash | Description |
|------|-------------|
| `32425a8` | fix(rag): use relative DATA_DIR default + tokenizers pin |
| `4d49595` | fix(settings): preventDefault on wheel |
| `6568a37` | feat(chat-ai): tiered answer source + confidence badge (frontend) |
| `f865aa0` | feat(rag): tiered source + confidence in done event; CRAG suppressed on dataset |
| `5420029` | fix(drift): per-column stats in tool_context |
| `3ba9c7c` | fix(rag): confidence bump dataset+KB; How I Searched in Deep Search |

---

## Q&A — Why Sources and "How I Searched" Don't Show for Dataset Answers

**Q:** Why is sources section and "How I Searched" missing when answer_source = "dataset"?

**A:** Both absent for the same reason — the answer came entirely from `tool_context` (dataset stats), not KB retrieval.

- **Sources missing:** Sources block only renders when `sources.length > 0`. When `answer_source = "dataset"`, retrieval returned zero KB chunks — nothing to cite. LLM read income range directly from system prompt (batch_range, ref_mean etc. added in drift context fix). Nothing to show.
- **"How I Searched" missing:** Renders only when `expandedQueries.length > 0 || candidatesRetrieved != null`. Since retrieval returned nothing, both are empty/null → `hasInsights = false` → section hidden.

**This is correct behavior.** Example confirmed working: "what is income range?" → answered with ₹1,038.95 min, ₹1,04,131.10 max, reference mean ₹2,50,000, high 87% drift — accurate from dataset context alone.

**Potential improvement:** When `answer_source = "dataset"`, still render "How I Searched" with a static note: "Answered from loaded dataset context — no KB retrieval needed." Not yet implemented.

---

## Pending

- **Tiered retrieval** — retrieval still uses one mixed pool (uploaded docs + KB compete equally). Need to query uploaded docs first, fall through to KB if insufficient. Most invasive change — deferred.
- **"How I Searched" for dataset-only answers** — optionally show even when no retrieval happened.

## Conversations Log Location
`/Users/wrks/Downloads/Claude-documentation/Projects/ML-Unified/Conversations/`
