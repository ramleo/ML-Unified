# Session Part 209 — 2026-07-26

## Context
Continued from Part 208 (MMRAG-01 blur detection shipped, two real bugs
fixed). This session built MMRAG-04 (answer groundedness scoring), then
fixed two more real bugs the user caught by actually using the feature —
one of which turned out to require actual new functionality, not just a fix.

## 1. MMRAG-04 — Answer groundedness scoring

User asked what to build next; recommended MMRAG-04 (groundedness) over
MMRAG-02 (cross-doc contradiction detector) since it's self-contained and
directly signals eval-first thinking. User also asked to apply SOLID
principles wherever relevant.

- New file: `services/ml-api/routers/rag/groundedness.py` —
  `score_groundedness(answer, chunks, embed_fn) -> dict`. Splits the answer
  into sentences, embeds each with the already-loaded MiniLM/Jina embedder
  (no new model, no extra LLM call), finds each sentence's best cosine-sim
  match against the retrieved chunks. Flags sentences with no good match as
  "ungrounded." Pure function, dependency-injected embed_fn — SRP + DIP so
  `query.py` depends only on the (answer, chunks, embed_fn) -> dict contract,
  not the scoring internals.
- Thresholds calibrated against REAL all-MiniLM-L6-v2 embeddings, not
  guessed: grounded/paraphrased sentences scored 0.44-0.94 max similarity;
  fabricated/unrelated sentences scored 0.10-0.36. Threshold set at 0.40.
- Wired into `query.py`'s done event (both cached and live paths) and
  `cache.py`'s `cache_store`/`cache_lookup`.
- Frontend: extracted a shared `GroundednessBadge.tsx` component (High/
  Medium/Low badge + "possibly unsupported" sentence list) — used by BOTH
  `ChatMessageList.tsx` (the generic floating chat) and `MmRagRunner.tsx`
  (Multimodal RAG's own bespoke chat panel, which does NOT use
  ChatMessageList — a gap a Playwright verification agent caught: the badge
  initially only reached the floating widget, not the actual document Q&A
  UI users see on the tool page).
- Commits: ML-Unified `4f23916` (backend), ml-portfolio `7923df1` (badge in
  ChatMessageList), ml-portfolio `b5da070` (fix: wire into MmRagRunner via
  shared GroundednessBadge component).
- Verified live end-to-end via Playwright: uploaded a real invoice PDF,
  asked a grounded question, badge showed "high (61%)" correctly matching
  an answer that quoted the invoice number/total directly from the source.

## 2. Real bugs caught by the user actually using the feature

**Bug A — answer-length toggle appeared broken.** User screenshotted three
answers (Concise/Normal/Detailed toggles) that were all identical text.
Investigated live via direct curl tests against the deployed Space:
confirmed the backend DOES vary answer length correctly for a fresh
question in restrict_to_uploads mode (191 chars concise vs 430 chars
detailed, cache_hit false both times). Initial conclusion: the toggle only
applied to the NEXT question, not retroactively to an already-displayed
answer — user firmly rejected this as an explanation ("this was the reason
I wanted you to fix it yesterday") and wanted the ALREADY-DISPLAYED answer
to regenerate in place when the toggle is clicked.

**Real fix:** refactored `useRagChat.ts`'s `send()` into a shared
`runQuery(queryText, historyBase, lengthOverride)` core, then added
`regenerateLastAnswer(newLength)` which finds the last user message,
strips any trailing assistant answer, and re-runs `runQuery` at the new
length — replacing the last answer in place rather than requiring a new
question. Wired into `MmRagRunner.tsx`'s Concise/Normal/Detailed buttons
(previously called `chat.setAnswerLength` directly; now call
`chat.regenerateLastAnswer`). Commit: ml-portfolio `fab4438`.

Verified live via Playwright: asked "what is in my resume?" (got a long
detailed answer), clicked "concise" with NO re-ask — the same answer
bubble was replaced instantly with a shorter version, question preserved
above it. Zero console errors.

**Bug B (found in passing, real, separate) — semantic cache ignored
answer_length.** While investigating Bug A, proved via live curl that the
cache served byte-identical 969-char answers for "concise" and "detailed"
on the same question (both cache_hit: true) for non-restrict_to_uploads
queries. Root cause: `cache.py`'s `ctx_hash()` only hashed
`tool_context + session_id`, never `answer_length`. Fixed by folding
`answer_length` into the hash. Commit: ML-Unified `dc154b5` (bundled with
Bug C below).

**Bug C — "Soft Skills" section silently dropped, not extracted or
captioned.** User's resume has a circular donut infographic listing 6 soft
skills (Change Agent, Collaborator, Communicator, Innovator, Planner,
Thinker) as labels baked into a raster image, not real PDF text. Asked
"tell me about soft skills" → model said the doc doesn't list any, despite
the labels being clearly visible in the page screenshot the user provided.

Investigated directly against the real PDF (PyMuPDF): confirmed
`get_text()` returns nothing for those labels (they're image pixels, not
text), and computed the donut's image bounding-box area at ~2.96% of the
page — below `mm_pdf.py`'s `_is_visually_dense()` threshold of 5%
(`_MIN_VISUAL_AREA_RATIO`), meaning the page was never even sent to the
vision-caption pipeline. Confirmed decorative bullet-icons on the same page
measure only ~0.06% — so 2.96% is a real, meaningful graphic being wrongly
filtered as noise. Lowered the threshold to 2% (wide margin above the
0.06% decorative icons, below the 2.96% real graphic). Commit: ML-Unified
`dc154b5`.

Verified live: re-ingested the real resume via curl — chunk_summary went
from `{"figure": 0}` to `{"figure": 1}`; asking "tell me about soft skills"
now correctly returns all 6 skills. Re-verified in the actual deployed UI
via Playwright: ingest badge showed "3 text · 1 figure chunks", and the
chat correctly listed all 6 soft skills in both a targeted question and a
general "what is in my resume?" summary.

## Commit summary
| Commit | Repo | What |
|---|---|---|
| `4f23916` | ML-Unified | MMRAG-04 backend: groundedness.py + wiring through query.py/cache.py |
| `7923df1` | ml-portfolio | MMRAG-04 frontend: groundedness badge in ChatMessageList's "How I searched" panel |
| `b5da070` | ml-portfolio | Fix: extracted shared GroundednessBadge.tsx, wired into MmRagRunner (the actual doc Q&A UI) |
| `dc154b5` | ML-Unified | Fix: lowered visual-density threshold (soft skills) + cache ctx_hash now includes answer_length |
| `fab4438` | ml-portfolio | Fix: regenerateLastAnswer — toggle regenerates last answer in place instead of requiring a re-ask |

## Pending
- MMRAG-04 is fully done, deployed, and verified, along with three
  unplanned bug fixes surfaced by real usage.
- Next unstarted Tier-1 backlog items: MMRAG-02 (cross-document
  contradiction detector), MMRAG-03 (domain-specific NER).
- Full backlog reference: `project_mmrag_feature_backlog.md` memory file /
  `Conversations/..._Part207.md`.
