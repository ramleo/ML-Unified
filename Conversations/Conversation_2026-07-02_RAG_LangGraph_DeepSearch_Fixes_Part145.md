# Conversation Part 145 — LangGraph Deep Search UI Fixes
**Date:** 2026-07-02  
**Branch:** main  
**Topics:** SSE source events missing, graph diagram redesign, closure bug, LangGraph stream_mode fix

---

## Context (Continued from Part 144)

All Phase 3 RAG work was complete. This session focused on two bugs reported after deploying the LangGraph Deep Search feature:
1. Sources not appearing in the chat panel when using Deep Search
2. Agent graph diagram looking too plain (vertical dot list)

---

## SSE Line Buffering Fix

### Problem
The SSE parser in `ToolsAIChat.tsx` used:
```js
const lines = decoder.decode(value).split("\n").filter(Boolean);
```
If a `reader.read()` call returned a partial SSE event (JSON split across two reads), `JSON.parse` would fail silently and the event was dropped. This caused `source` events and early `agent_step` events (routing, retrieving) to be lost.

### Fix — `src/components/ToolsAIChat.tsx` (commit `4daf1ee`)
Added `sseBuffer` to accumulate incomplete lines across reads:
```js
let sseBuffer = "";
// inside while loop:
sseBuffer += decoder.decode(value);
const parts = sseBuffer.split("\n");
sseBuffer = parts.pop() ?? "";
const lines = parts.filter(Boolean);
```
Net: +3 lines (397 → 400 total).

---

## Agent Graph Diagram — Collapsible (commit `4daf1ee`)

Added collapse toggle to `AgentGraphDiagram.tsx`:
- `const [isOpen, setIsOpen] = useState(true)` — default open
- Chevron SVG button in header rotates 90° when collapsed
- Node list and footer note gated on `{isOpen && (...)}` 

---

## LangGraph stream_mode Fix

### Problem
`requirements.txt` specifies `langgraph>=0.2.0`. On HF Space, pip installed `0.4.x`. In langgraph 0.4+, the default `stream()` mode changed. Without explicit `stream_mode`, the event format didn't match what the code expected (`{node_name: delta}`), causing an exception → `final_state` reset to initial (chunks=[]) → no source events emitted.

### Fix — `services/ml-api/routers/rag/agent.py` (commit `6d4faf2`)
```python
# Before:
for event in _compiled.stream(initial):
# After:
for event in _compiled.stream(initial, stream_mode="updates"):
```
Explicitly pins "updates" mode which guarantees `{node_name: state_delta}` format in all langgraph versions.

Uploaded `agent.py` to HF Space after commit.

---

## Agent Graph Diagram — SVG DAG Redesign (commit `49a534e`)

### Problem
The original diagram was a vertical dot list — didn't look like a graph. User requested proper LangGraph-style visualization.

### New Design — `src/components/AgentGraphDiagram.tsx` (169 lines)

Full SVG DAG:
- **Nodes**: Rounded rectangle (`rx=6`) with label + desc text inside
- **Down arrows**: Vertical lines with polygon arrowheads between each consecutive node
- **Loop arrow**: Dashed curved bezier path from right edge of Rewriter → right edge of Retriever, with left-pointing arrowhead. Shows `N×` badge when loops > 0
- **Status colors**:
  - Idle: dim fill + dim border
  - Active: accent fill + accent border + pulsing glow rect (`nodePulse` CSS animation)
  - Done: accent border + checkmark circle in top-right corner
- **Collapse toggle**: chevron SVG in header, preserved from previous version

Layout constants: `NW=178, NH=38, NX=20, STRIDE=58`. SVG viewBox `0 0 240 280`. All widths scale via `width="100%"`.

---

## Root Cause Analysis — Remaining Issues (not yet fixed)

### Sources Still Not Appearing After stream_mode Fix

Two reasons identified:

**1. DDG blocked from HF Space**  
`web_search_fallback` calls DuckDuckGo. HF Space likely blocks/rate-limits outbound scraping → returns `[]` → no web source events emitted.

**2. Reranker floor drops all off-topic chunks**  
For a Kafka query (not in ML KB), cross-encoder scores all KB chunks below `ABS_FLOOR = 0.01`. `rerank()` returns `[]`. `node_grade` sees empty chunks → `grade = "websearch"`. When DDG also fails, final `chunks = []` → no source events.

**Fix needed**: Always emit KB chunks even when grade=websearch; add "outside KB" visual note.

### Query Router Not Highlighted — Closure Bug

`setAgentDoneSteps(s => [...s, prevStep!])` captures `prevStep` **by reference**. When routing + retrieving + grading all arrive in one `read()` call, React batches all three `setAgentDoneSteps` calls. By the time React runs the batched updaters, `prevStep` has already advanced to `"grading"` — so all three updaters add `"grading"` instead of `"routing"`/`"retrieving"`.

**Fix needed**:
```js
const snap = prevStep;
setAgentDoneSteps(s => [...s, snap]);
```

### User Requests for Next Session
1. Fix sources (KB chunks always emitted + outside-KB note)
2. Fix closure bug for node highlighting
3. Animated flowing arrows (CSS `stroke-dashoffset` animation)
4. DAG improvements: START/END nodes, branch labels, active connector coloring, simple-path shortcut arrow

---

## Commits This Session (Part 145 — earlier)

| Hash | Repo | Description |
|------|------|-------------|
| `4daf1ee` | ml-portfolio | fix: SSE line buffering + collapsible agent graph |
| `49a534e` | ml-portfolio | feat: SVG DAG graph with arrows + loop edge |
| `6d4faf2` | ML-Unified | fix: pin stream_mode=updates on LangGraph |

---

## Continuation — Part 145 (same session, post-compaction)

### Issues Reported (via screenshot)

1. **Sources showing wrong file**: Kafka query surfaced `feature_selection.md` with "Low" badge — irrelevant KB chunk leaked through after `abs_floor=0.0` change.
2. **Arrow before Generator not animated**: Grader→Rewriter arrow was orange/animated but Rewriter→Generator was dim, even when Generator completed.

---

### Fixes Applied

#### Fix 1 — Closure bug + animated arrows (`67f6be5`, ml-portfolio)

- `ToolsAIChat.tsx`: Captured `prevStep` as `const snap` before `setAgentDoneSteps` updater — fixes React batching bug where all steps resolved to last value.
- `AgentGraphDiagram.tsx`: Added `@keyframes flowArrow` CSS; arrows turn accent-colored + march when source node is active/done.

#### Fix 2 — Sources pipeline (`88a722b`, ML-Unified)

- `rerank.py`: Added `abs_floor` param; agent path passes `0.0` so off-topic queries return KB chunks for grading instead of `[]`.
- `agent_nodes.py`: Passes `abs_floor=0.0` to `rerank()`.
- `agent.py`: When web fallback fails, falls back to `kb_chunks`; emits `low_confidence=true` in done event.

#### Fix 3 — Wrong source displayed (`d432336` ml-portfolio, `dda0d6e` ML-Unified)

**Root cause 1 (sources):** `abs_floor=0.0` let `feature_selection.md` (score ~0.001) through. Fixed in `agent.py`: when web fallback fails, filter `kb_chunks` to those scoring `>= 0.01` before surfacing as sources. Off-topic queries now show no sources + `low_confidence=true` banner.

**Root cause 2 (arrow):** Arrow coloring used **source** node status (`statusOf(NODES[i].id)`). A flow bypassing Rewriter (grade=websearch → generate) left Rewriter "idle", so Rewriter→Generator arrow stayed dim even after Generator completed. Fixed by using **destination** node status (`statusOf(NODES[i+1].id)`) — arrow into a node glows when that node is reached regardless of path taken.

---

### Design Discussion — Source Categories

User asked: "why no source shown? from where is Kafka info fetched?"

**Answer**: LLM answers from pre-training knowledge when KB has no relevant articles. RAG sources only show what was retrieved from the KB or web — not the LLM's parametric knowledge.

User then asked about categorizing sources. Agreed categories:

| Category | Detection | Example |
|----------|-----------|---------|
| **KB** | `source` has no prefix | `feature_selection.md` |
| **Web** | `source.startsWith("web:")` | `web:duckduckgo.com/...` |
| **User Upload** | needs `source: "user:<file>"` tag on ingest | `user:my_guide.pdf` |
| **Model** | no sources at all | placeholder in UI |

Implementation plan (not yet built):
- Frontend: parse `source` prefix → colored pill badge (KB / Web / User)
- Backend: tag user-uploaded chunks with `user:` prefix in `/rag/ingest`
- Simplest MVP: just KB vs Web (2 badges) since user uploads aren't widely used yet

---

### All Commits (Part 145 continuation)

| Hash | Repo | Description |
|------|------|-------------|
| `67f6be5` | ml-portfolio | fix: closure bug + animated flowing arrows in agent graph |
| `88a722b` | ML-Unified | fix(rag): always surface KB sources in agent; fix reranker floor |
| `d432336` | ml-portfolio | fix(dag): color arrows by destination node, not source |
| `dda0d6e` | ML-Unified | fix(rag): filter low-score KB chunks when web fallback fails |

---

## Continuation — Part 145 (second post-compaction session)

### Source Category Badges

#### Implementation (`a3b0753`, ml-portfolio)

Added KB / Web / User / Model category badges to `RagSourceCard.tsx`.

Detection logic:
- `source === ""` → **Model** (grey)
- `source.startsWith("web:")` → **Web** (green)
- `source.startsWith("user:")` → **User** (purple)
- anything else → **KB** (blue)

`displayName()` strips the prefix before rendering the filename. `CategoryBadge` component renders a colored pill. Sits left of the filename in the card header row.

---

### Bug: Kafka/Weather Showing KB Sources + No Model/Web Badge

#### User report
- Asking "what is kafka" → 6 KB sources shown (optuna_tuning, catboost_guide, etc.) all with Low badge
- Asking "what is today's weather" → ml_best_practices.md shown with Low badge
- No Web badge ever appearing, no Model badge ever appearing

#### Root cause analysis (two separate bugs)

**Bug 1 — Score filter only ran inside the websearch branch:**

```python
if not kb_chunks or final_state.get("grade") == "websearch":
    ...try web...
    if not web_used:
        chunks = [c for c in kb_chunks if score >= 0.01]  # ← only ran here
```

For off-topic queries where grader said `"good"` (not "websearch"), this block was skipped entirely. `chunks = kb_chunks` passed all low-score irrelevant chunks straight to the source emitter.

**Bug 2 — Grader says "good" for off-topic queries:**

`abs_floor=0.0` always returns KB chunks (even scoring 0.001). Grader LLM sees them and inconsistently rates them as "good" — it doesn't reliably say "websearch" for topics like Kafka or weather.

**Bug 3 — No Model badge when chunks empty:**

When `chunks = []` after filtering, the for-loop emits zero source events. Zero events = zero cards = no badge at all. Frontend has no way to render Model without a card.

**Bug 4 — DDG was already replaced but Tavily not yet uploaded:**

DDG HTML scraping is blocked from HF Space datacenter IPs. The Instant Answer API (`api.duckduckgo.com`) works only for encyclopedic topics, not conversational queries.

#### Why DDG is blocked on HF Space

HF Space containers share datacenter IP pools. DDG (and all search engines) block datacenter IPs because scrapers/bots run from the same ranges. DDG HTML endpoint also checks for browser-like TLS fingerprints that `httpx` doesn't produce.

---

### Fixes Applied

#### Fix 1 — Replace DDG with Tavily (`63aef77`, ML-Unified)

`crag.py` rewritten:
- Primary: **Tavily API** (`TAVILY_API_KEY` env var on HF Space) — purpose-built for LLM/RAG, works from any server, 1000 free searches/month
- Fallback: DDG Instant Answer (no key, encyclopedic topics only, no HTML scraping)
- `requirements.txt`: added `tavily-python>=0.5.0`

#### Fix 2 — Universal score filter (`63aef77`, ML-Unified)

Moved the `score >= 0.01` filter outside the `if` block so it always runs when web wasn't used:

```python
# Before: only ran inside "if not kb_chunks or grade == 'websearch'"
# After:
if not web_used:
    chunks = [c for c in chunks if float(c.get("score", 0)) >= 0.01]
```

#### Fix 3 — User: prefix on uploaded chunks (`63aef77`, ML-Unified)

`ingest.py` `/ingest` endpoint now tags user-uploaded chunks with `user:` prefix:

```python
tagged_source = f"user:{fname}"
chunks = chunk_document(text, source=tagged_source)
```

Duplicate check and response also use `tagged_source`. Frontend `CategoryBadge` already detects `user:` prefix → shows User badge.

#### Fix 4 — Second-chance web fallback + Model badge (`21c5c27`, ML-Unified)

`agent.py` two additions:

```python
# After score filter, if chunks empty and web wasn't tried yet → try now
if not chunks and not web_fallback_tried:
    web_fallback_tried = True
    try:
        web_chunks = web_search_fallback(...)
        if web_chunks:
            chunks = web_chunks
            web_used = True
    except Exception as exc:
        ...

# After emit loop, if still no sources → emit Model placeholder
if not seen_sources:
    yield _sse({"type": "source", "doc": {
        "source": "", "text": "Response from model training knowledge.", "score": 0, "display_score": 0,
    }})
```

This covers the case where grader says "good" but all chunks score below 0.01 — web is tried as a second chance, then Model badge shown if web also fails.

#### Fix 5 — Tavily health check in `/rag/health` (`21c5c27`, ML-Unified)

`query.py` health endpoint now tests Tavily key on each call and returns:
```json
{ "tavily": "ok" | "not_set" | "error: <message>" }
```

---

### Badge Behavior After All Fixes

| Query | Expected badge |
|-------|---------------|
| "explain XGBoost" | **KB** (high-score chunks) |
| "what is kafka" | **Web** (Tavily works) or **Model** (Tavily empty) |
| "what is today's weather" | **Web** or **Model** |
| User-uploaded file query | **User** |
| Any LLM-only answer | **Model** |

User confirmed: working after upload.

---

### Agentic Architecture Review

Full flow paths after all fixes:

- **Path 1 (on-topic, grade=good):** high-score KB chunks pass filter → KB badge ✓
- **Path 2 (off-topic, grade=websearch):** web fallback triggered → Tavily → Web badge ✓; Tavily fails → Model badge ✓
- **Path 3 (off-topic, grade=good — grader wrong):** all chunks filtered → second-chance web → Web badge ✓; web fails → Model badge ✓
- **Path 4 (simple route):** grader skipped entirely → chunks filtered by score → KB or Model badge ✓

Remaining known limitation: grader LLM sometimes says "good" for off-topic queries (Kafka, weather) because it hallucinates relevance between ML concepts and adjacent tech topics. Second-chance web fallback covers this case.

---

### What's Next in RAG

**Phase 2 remaining (not started):**
- Jina v3 embeddings (replaces MiniLM-22MB, meaningfully better retrieval)
- Semantic caching (50–80% LLM cost reduction on repeated/similar queries)
- RAGAS evaluation (measure faithfulness/relevancy baseline)
- Multi-tenant upload isolation (user A's uploads shouldn't surface for user B)

**Phase 4 (not started):**
- Dataset Schema RAG (embed CSV column names/stats → retrieve relevant guides after training)
- RAPTOR hierarchical indexing (for long docs >10k tokens)
- Algorithm Recommendation RAG

Priority order: semantic caching → RAGAS → Jina v3 → Dataset Schema RAG

---

### All Commits (second post-compaction session)

| Hash | Repo | Description |
|------|------|-------------|
| `a3b0753` | ml-portfolio | feat(rag): KB/Web/User/Model category badges in source cards |
| `63aef77` | ML-Unified | fix(rag): Tavily web search, universal score filter, user: prefix on uploads |
| `21c5c27` | ML-Unified | fix(rag): second-chance web fallback + Model badge + Tavily health check |
