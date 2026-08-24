# Session: Test Case Generation — TC-P2 (Parts 16–33)
**Date:** 2026-06-23  
**Context:** Continuation of previous session that ran out of context during Round 2 TC generation.

---

## Session Summary

### Questions Answered

**Q1: Why did context get consumed despite using subagents?**  
Subagents run in isolation, but their *results* return to the main conversation as tool output. In the previous session, all 8 agents returned 85–150 TCs worth of text directly into the main thread. To avoid this, agents should write their own files directly to disk and only return a short confirmation summary.

**Q2: Which TC files were fully written to disk (at session start)?**  
See table below.

**Q3: Will stricter file splits (≤400 lines) save context?**  
No. File size does not affect context. Context is consumed when files are *read*. Splitting one 800-line file into two 400-line files means the agent reads the same total content in two reads. The split only satisfies the CLAUDE.md rule, not context savings.

---

## Work Done This Session

### TC-P2 Generated
- Spawned 1 subagent to read Parts 16–33, generate TCs, and write files directly to disk
- Subagent returned only a short summary (not TC content) → main context stayed clean
- **158 test cases** written across 2 files (split due to 400-line rule):

| File | Parts | TCs | Lines |
|------|-------|-----|-------|
| TC-P2-A.md | 16–24 | 75 | 832 |
| TC-P2-B.md | 25–33 | 83 | 946 |

**Agent stats:** 1 subagent | 92,932 tokens | ~362s (~6 min)

**Notable coverage in TC-P2:**
- 22 Bug-Regression tests: TinyYOLOv3 letterbox, body-stream-read-twice, VISION_API undefined, theme-revert-on-refresh, wrong panel on ?mode=vision load, histogram giant bars, chart capture restore discarding images, PDF tab lock, heatmap bottom row cut-off, favicon 100% error rate
- 5 E2E tests: vision round-trip, EDA full flow, theme sync round-trip, CI/CD pipeline, Segmentation/Detection/Classification in one session
- Backend API tests (pytest) and UI/E2E tests (Playwright)
- Target URLs: `https://ml-unified.onrender.com`, `https://ml-portfolio-rho.vercel.app`

---

## Current State of All TC Files

| File | Parts Covered | TCs | Status |
|------|--------------|-----|--------|
| TC-DOC.md | E2E docs, README | 75 | ✅ Written |
| TC-PEND.md | pending.md, EDA bugs | 47 | ✅ Written |
| TC-REC.md | Parts 113–116 | 24 | ✅ Written |
| TC-HIST.md | Parts 107–112 | 44 | ✅ Written |
| TC-EARLY.md | Early May sessions | 60 | ✅ Written |
| TC-P1.md | Parts 1–15 | 92 | ✅ Written |
| TC-P2-A.md | Parts 16–24 | 75 | ✅ Written |
| TC-P2-B.md | Parts 25–33 | 83 | ✅ Written |
| TC-P4.md | Parts 51–65 | 90 | ✅ Written |
| TC-P3.md | Parts 34–50 | 150 | ❌ Not written |
| TC-P5.md | Parts 66–83 | 105 | ❌ Not written |
| TC-P6.md | Parts 84–96 | 85 | ❌ Not written |
| TC-P7.md | Parts 97–106 | 105 | ❌ Not written |
| testcases.md (index) | All | ~1,030 | ❌ Not updated |

**Written: 9 files, ~590 TCs. Pending: 4 TC files + master index.**

---

## Pending Work (Next Session)

1. TC-P3.md — Parts 34–50 (150 TCs; Agent D previously wrote to wrong path `Testing_Complete_Guide.md` — needs fresh generation)
2. TC-P5.md — Parts 66–83 (105 TCs)
3. TC-P6.md — Parts 84–96 (85 TCs)
4. TC-P7.md — Parts 97–106 (105 TCs)
5. Update `Conversations/testcases.md` master index with all files, TC counts, and agent stats

## Key Lesson for Next Session
Always instruct subagents to **write files directly to disk** and return only a short confirmation. Never let agents return large TC content back to the main thread.
