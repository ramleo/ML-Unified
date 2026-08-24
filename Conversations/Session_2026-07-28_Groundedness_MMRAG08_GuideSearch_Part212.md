# Session Part 212 — 2026-07-28

## Context
Continued from Part 211 (MMRAG-05/06/07, object detection). This session
started from a user-reported anomaly (a correct "where is the bicycle"
answer scored Low groundedness) and grew into: a real groundedness-scoring
bug fix, a frontend bbox-label clipping fix, an OIV7 hierarchy matching gap
fix, all of MMRAG-08 ("why was this cited" trace panel), and a full search
feature added to the User Guide modal (block-level jump, real keyword
highlighting, keyboard navigation) — with two real bugs found and fixed in
that search feature along the way.

## 1. Groundedness scoring — two separate real bugs, same feature line

- **Bug 1 — object-detection text not baked into the scored chunk.** The
  user asked "where is the car" and got the correct answer ("the car spans
  most of the frame") but a Low (32%) groundedness badge. Root cause:
  `citations.py`'s `build_system_prompt()` injected the spatial phrase into
  a LOCAL `chunk_block` string used only for the LLM prompt — `groundedness.py`
  and `likely_used_indices()` both independently re-read `chunk["text"]`
  (the raw stored chunk), which never contained that phrase. Fixed by
  moving `describe_objects()`/`_spatial_phrase()` into `mm_objects.py` and
  calling it at INGEST time in `mm_image.py`/`mm_video.py`, baking the
  sentence directly into the chunk's stored `text` — so the LLM prompt,
  groundedness scoring, and citation-overlap scoring all read the same
  fact. Removed the now-redundant query-time injection in `citations.py`.
  Requires re-uploading old images/videos to backfill.
  Commit: ML-Unified `640d555`.
- **Bug 2 — chunk-level (not sentence-level) embedding diluted short facts.**
  Even after fix 1, a car photo's citation still scored borderline (Medium
  40%, flagged "possibly unsupported") while a bicycle photo's identical
  fix scored cleanly (Medium 54%). Root-caused directly from
  `groundedness.py`: `chunk_embs = embed_fn(chunk_texts)` embedded each
  chunk's ENTIRE text as ONE vector — the car chunk's long appearance
  description ("teal-colored SUV... reads 'DATSUN'") diluted its one short
  spatial fact under the averaging; the bicycle chunk's text was mostly
  spatial content already (7 detected objects, most naming a side), so it
  diluted far less. Fixed by splitting each chunk into sentences too (same
  granularity as the answer side already had), so a short answer can match
  its one relevant source sentence directly instead of an entire diluted
  paragraph.
  Commit: ML-Unified `615b3e5`.
- **Verified live, both fixes, real data**: bicycle citation went from Low
  (32%) pre-fix to High (61.4%) post-fix; a real video (`Original_recording5.mp4`,
  user-provided) scored High (80.7%) then High (85%) through the actual
  deployed UI, with the bounding box correctly rendered alongside.

## 2. Frontend bug — bounding-box confidence label clipped at top of frame

- User screenshot showed a video frame's confidence label ("13%") cut off
  at the top of the citation thumbnail. Root cause in
  `CitationThumbnailPanel.tsx`: the label was positioned `top: -22` (22px
  ABOVE its bounding box) — when the detected object's box started near
  the top of the frame (common for a subject filling most of a close-up
  shot), the label floated above the image itself and got clipped by the
  container.
- Fixed by moving the label INSIDE the box's top-left corner instead of
  floating above it — can never go off-frame regardless of box position.
  Commit: ml-portfolio `294b80c`.

## 3. Frontend bug — generic terms didn't match their OIV7 subclass

- User asked "locate the person" and got no box, even though "Man" was
  detected at 73% confidence on that exact frame. Root cause: Open Images
  V7 is hierarchical — the detector reports the specific subclass ("Man"),
  never the generic parent ("Person"); `matchObjectToQuestion()` in
  `MmRagRunner.tsx` only did a literal label match.
- Fixed with a small synonym map (`HIERARCHY_SYNONYMS`): person/people →
  man/woman/boy/girl, vehicle → car/truck/van/bus/bicycle/motorcycle/
  train/airplane/boat/limousine/taxi. Only covers the generic terms
  someone would plausibly type, not the full 601-class taxonomy.
  Commit: ml-portfolio `26cd796`.

## 4. MMRAG-08 — "Why was this cited?" retrieval trace panel

- **The core problem**: the retrieval pipeline (dense → BM25 → RRF fusion →
  cross-encoder rerank) reused a single `"score"` dict key at every stage,
  each stage overwriting the last — no way to tell whether a chunk won on
  semantic similarity, keyword match, both, or neither.
- **Backend fix** (`retrieve.py`, `rerank.py`, `citations.py`):
  `reciprocal_rank_fusion()` gained an optional `labels: list[str] | None`
  param — passing `["dense", "bm25"]` at the BASE fusion level records each
  merged doc's per-signal `{score, rank}` into a `retrieval_trace` dict,
  plus `hybrid_score` (the RRF value, stashed before rerank overwrites
  `"score"`) and `type_boost`. OUTER fusion passes (merging query-variant
  results, or tier1+tier2) are called WITHOUT labels, so `dict(doc_store[key])`
  copies the existing trace through untouched — only that pass's own
  `"score"` gets replaced. `rerank.py` does the same trick with
  `entry.setdefault("hybrid_score", ...)` before setting `rerank_score`.
  `citations.py`'s `build_source_doc()` surfaces all of this in the SSE
  payload.
  Commit: ML-Unified `f8bae4b`.
- **Frontend** (`RagSourceCard.tsx`, `ChatPanel.tsx`, new `RagTableView.tsx`):
  a "Why was this cited?" link under each citation reveals the breakdown
  in plain language (e.g. "Semantic (meaning) match: 0.554 similarity,
  ranked #1..."). `RagSourceCard.tsx` was already at 366 lines (over the
  project's 350-line modularize-first threshold) — extracted its
  self-contained table/CSV/chart view into `RagTableView.tsx` first,
  bringing the card to 277 lines before adding the ~30-line trace section.
  Commit: ml-portfolio `8b0324c`.
- **Verified live**: real numbers rendered (dense 0.554 rank #1, BM25 5.75
  rank #1, hybrid 0.0328, final relevance 96%) on a real bicycle citation,
  coexisting correctly with the MMRAG-07 bounding box on the same card.
- **User confusion resolved**: the same bicycle citation's trace numbers
  looked different after a second document (car.jpeg) was uploaded and a
  new question asked. Clarified (in guide + directly to user): the panel
  never re-runs anything on click — it's a frozen snapshot of that specific
  answer's retrieval run; scores/ranks are relative to whatever was in the
  candidate pool at that moment, so they legitimately differ across
  questions, not because anything about the cited document changed.
  Guide commit: ml-portfolio `ef90922`.

## 5. User Guide — search box added, then two real bugs fixed in it

- **Feature**: a search box in the `MmRagUserGuideModal`, since the guide
  had grown long enough that finding a topic meant manual scrolling.
  Splits the guide markdown into block-level scroll/search targets on
  blank-line boundaries, further splitting any list block into individual
  bullets (keeping wrapped continuation lines attached) so search jumps to
  the SPECIFIC bullet, not the top of a whole multi-bullet section (e.g.
  "Reading citations"). ↑/↓ buttons step through matches with a live
  `N/total` counter.
  Commit: ml-portfolio `c3a082b`.
- **Bug found immediately**: searching "bounding box" (or any multi-word
  phrase) showed 0 matches. Root cause: reused `wordMatch.ts`'s
  `textMatches()`, which is built for the transcript search box's
  single-word prefix+stemmer matching (one typed word vs one document
  word) — no single word ever "starts with" a two-word string. Fixed with
  a plain case-insensitive substring matcher (`guideMatches`) instead,
  local to this component — a full-guide search needs ordinary phrase
  matching, not single-word tolerance.
  Commit: ml-portfolio `6ec34c6`.
- **User-requested improvement**: matches only tinted the whole block's
  background, not the actual matched words — hard to spot in a long
  paragraph. Added `rehype-raw` (small, standard react-markdown companion,
  confirmed via `npm audit` to introduce no new vulnerabilities beyond
  Next.js's own pre-existing ones) so a literal `<mark>` wrapped around
  each raw-text match renders instead of being escaped as plain text.
  Matches on the RAW markdown string (not the syntax-stripped version used
  for locating blocks) so offsets line up; a match straddling actual
  markdown syntax (e.g. inside `**bold**`) still locates/scrolls to its
  block but won't get the inline `<mark>` — accepted gap, documented in
  code comments.
  Commit: ml-portfolio `8d1fa5c`.
- **User-requested addition**: keyboard navigation (Enter/↓ = next match,
  Shift+Enter/↑ = previous) instead of only mouse-clicking the ↑/↓
  buttons. While touching this logic, fixed a latent bug in the
  PRE-EXISTING buttons too: JS's `%` doesn't wrap negative numbers back
  into range (`(-1) % 3 === -1`, not `2`), so repeatedly clicking ↑ at the
  first match would silently break the cursor (`matchIndices[-1]` is
  `undefined`, stopping the scroll-to-match effect). Fixed with a
  normalizing double-modulo (`((c % n) + n) % n`), applied consistently to
  both the display counter and the actual scroll target.
  Commit: ml-portfolio `3cb307b`.
- All four steps verified live via Playwright against the deployed site
  (not just code-read) — including one case where a deploy's dashboard
  said "Ready" but the actual edge-served JS bundle was still stale for
  several minutes after, confirmed by directly grepping the live chunk
  content for a marker string before/after re-testing, rather than trusting
  the dashboard status alone.

## Commit summary

| Repo | Commit | What |
|---|---|---|
| ML-Unified | `640d555` | Bake object-detection text into stored chunk (groundedness bug 1) |
| ML-Unified | `615b3e5` | Sentence-level chunk embedding for groundedness (bug 2) |
| ML-Unified | `f8bae4b` | MMRAG-08 backend — retrieval trace propagation |
| ml-portfolio | `7be08c7` | User guide — object detection / bounding box section |
| ml-portfolio | `294b80c` | Fix bbox confidence label clipping at top of frame |
| ml-portfolio | `26cd796` | Generic-term → OIV7 subclass matching (person/vehicle) |
| ml-portfolio | `44d3d18` | User guide — document both frontend fixes above |
| ml-portfolio | `ef90922` | User guide — clarify trace panel is a frozen per-question snapshot |
| ml-portfolio | `8b0324c` | MMRAG-08 frontend — trace panel + RagTableView extraction |
| ml-portfolio | `c3a082b` | User guide search box (block-level jump/highlight) |
| ml-portfolio | `6ec34c6` | Fix: guide search didn't match multi-word phrases |
| ml-portfolio | `8d1fa5c` | Fix: highlight the actual matched keyword (rehype-raw) |
| ml-portfolio | `3cb307b` | Keyboard nav for guide search + negative-modulo cursor bug |

## Pending / next candidates
- MMRAG-09 (temporal moment retrieval for video), MMRAG-11 (FFT scene-cut
  detection), MMRAG-12 (multilingual Q&A), MMRAG-14 (chart data extraction)
  remain unbuilt Tier-3 backlog items — see `project_mmrag_feature_backlog.md`
  in Claude's memory store for the full prioritized list.
- No other open threads from this session; both groundedness bugs, both
  frontend bugs, and the full MMRAG-08 + guide-search feature set were all
  verified live before being reported done.
