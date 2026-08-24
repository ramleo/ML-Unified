# Conversation — Part 158
**Date:** 2026-07-05  
**Topics:** Tiered Retrieval · Web Override Toggle · Badge/Source Fixes · Playwright Verification  
**Commits:** `e0b5f56` `1af3955` `79de7e2` `90af1af` `bc28ed1` `59d0626`

---

## Summary

This session implemented tiered retrieval, added a manual web override toggle, then fixed three rounds of badge/source display bugs. All fixes were Playwright-verified. A new memory rule was saved: use Playwright when the same UI issue repeats 2+ times.

---

## Work Done

### 1. Tiered Retrieval (`retrieve.py` — `e0b5f56`)

Added `tiered_hybrid_retrieve` which prioritises uploaded docs before falling back to KB:

- If session has uploaded docs → dense+BM25 retrieve uploaded-only (score filter ≥ 0.15)
- If Tier 1 score passes → return uploaded chunks
- Otherwise → KB retrieval (dense+BM25 over `uploaded=False` chunks) and RRF-merge with Tier 1
- `multi_query_retrieve` uses `tiered_hybrid_retrieve` when `session_id` present, else `hybrid_retrieve`
- Added `"uploaded": bool(meta.get("uploaded", False))` to `dense_retrieve` hit dict so the flag survives the rerank pipeline

Key insight: `rerank.py` calls `dict(chunk)` so any key added to the hit dict is preserved.

### 2. Manual Web Override Toggle

**Backend (`query.py`, `agent.py` — `1af3955`):**
- `force_web: bool = False` added to `QueryRequest` and `AgentRequest`
- CRAG condition: `if (low_confidence and not has_dataset) or req.force_web:`
- When `force_web=True`: `chunks = web_chunks` (replaces KB chunks, not appends)
- Cache bypass: `if req.force_web: cached = None`

**Frontend (`useRagChat.ts`, `ToolsAIChat.tsx` — `79de7e2`):**
- `useState(false)` for `forceWeb`; sent as `force_web: forceWeb || undefined` in both query and agent requests
- Amber globe SVG button in chat header (amber #f59e0b when active)

### 3. Badge/Source Bug Fixes — Three Rounds

**Round 1 (`90af1af`) — two bugs:**
- **"Dataset" badge showed "Knowledge Base"**: `_determine_answer_source` was checking `chunks[0].get("source","").startswith("web:")` but web chunks are appended AFTER KB chunks, so `chunks[0]` was always a KB chunk. Fixed: check `web_fallback_used` flag first; return `"dataset"` when `has_dataset=True` and not web/uploaded.
- **Web override returned cached KB response**: cache key didn't include `force_web`. Fixed: `if req.force_web: cached = None`.

**Round 2 (`bc28ed1`) — web source detection:**
- `force_web` path was still appending (`chunks + web_chunks`). Fixed: `chunks = web_chunks if req.force_web else chunks + web_chunks`.

**Round 3 (`59d0626`) — KB sources under Dataset badge:**
- Sources panel rendered regardless of `answerSource`. Fixed: added `answerSource !== "dataset"` guard in `ChatMessageList.tsx` line 119.
- Playwright verified: uploaded CSV → asked drift question → badge showed "Dataset · HIGH CONFIDENCE" → sources panel hidden.

### 4. Playwright Verification

User explicitly required Playwright verification after repeated failed fixes. Both final fixes confirmed visually:
- Dataset badge: showed correct label, no sources panel
- Web override: amber globe active → sources panel showed web URLs only

### 5. Memory Saved

`feedback_use_playwright.md` — If the same UI issue repeats 2+ times, use Playwright to verify before claiming fixed. Never say "fixed, please test" without verifying yourself first.

### 6. Files Updated

- `Conversations/pending.md` — items #67–72 marked complete with commit references
- `Conversations/testcases.md` — TC-P8 row added (Parts 125–157, 0 TCs, ❌ pending Round 4)

---

## Files Changed

| File | Change | Commit |
|------|--------|--------|
| `services/ml-api/routers/rag/retrieve.py` | tiered_hybrid_retrieve + uploaded metadata in dense/BM25 hits | `e0b5f56` |
| `services/ml-api/routers/rag/query.py` | force_web field, _determine_answer_source fix, cache bypass | `1af3955` `90af1af` `bc28ed1` |
| `services/ml-api/routers/rag/agent.py` | force_web field threaded through _agent_generator | `1af3955` |
| `src/components/useRagChat.ts` | forceWeb state + sent in both request bodies | `79de7e2` |
| `src/components/ToolsAIChat.tsx` | amber globe web override button | `79de7e2` |
| `src/components/ChatMessageList.tsx` | answerSource !== "dataset" guard on sources panel | `59d0626` |
| `memory/feedback_use_playwright.md` | new memory rule | — |
| `Conversations/pending.md` | items #67–72 done | — |
| `Conversations/testcases.md` | TC-P8 row + Round 4 entry | — |

---

## Pending After This Session

| Item | Notes |
|------|-------|
| TC-P8 (Round 4) | Write test cases for Parts 125–157 — tiered retrieval, web override, badge, CRAG, drift context |
| "How I Searched" for dataset-only | When `answer_source="dataset"`, show static note instead of hiding silently |
| `Testing_Complete_Guide.md` | Duplicate of TC-P3.md — can be deleted |

---

## Key Decisions

- `web_fallback_used` flag approach: cleaner than checking source prefix since chunk ordering matters
- Dataset badge hides sources: when answer comes from loaded dataset, KB chunks are supplementary context for the LLM — not citable sources the user needs to see
- Cache bypass on `force_web`: user expects fresh web results, not a cached KB response
