# Session Part 210 — 2026-07-26

## Context
Continued from Part 209 (MMRAG-04 groundedness shipped). This session built
MMRAG-02 (contradiction detector) and MMRAG-03 (entity extraction +
entity-based retrieval filtering), then — prompted by a user question about
"important words as chips" — built a new live search/highlight feature over
document text, which surfaced two real bugs during a careful multi-turn
debugging exchange with the user. Closed with a conceptual Q&A on agentic RAG.

## 1. MMRAG-02 — Cross-document contradiction detector

- New `services/ml-api/routers/rag/contradictions.py`: two-stage, cost-bounded
  pipeline. (1) embedding-similarity pass narrows a session's cross-document
  chunk pairs to same-topic candidates (similarity 0.45–0.93 band — too low is
  unrelated topics, too high is near-duplicate text). (2) only that small
  candidate set (capped at 6 pairs) gets one fast LLM judge call each, using a
  fixed server-key-only provider (`groq`/`llama-3.1-8b-instant`) — same
  rate-limit-safety reasoning as `expand.py`'s query expansion.
- `POST /rag/contradictions {session_id}` → `{checked_pairs, sources,
  contradictions: [{similarity, explanation, chunk_a, chunk_b}]}`.
- Frontend: `ContradictionsPanel.tsx` — "Check documents for contradictions"
  button, shown once 2+ docs are in a session.
- Verified live: uploaded two synthetic PDFs (same project, conflicting
  deadlines — March 15 vs April 30, matching budget figures) via curl and
  Playwright; correctly flagged the deadline conflict, correctly did NOT flag
  the matching budget as a contradiction.
- Commits: ML-Unified `d2e966b`, ml-portfolio `277d2c3`.

## 2. MMRAG-03 — Domain-specific entity extraction + retrieval filtering

- New `services/ml-api/routers/rag/entities.py`: regex-based extraction of
  money/date/percent per chunk (same cost profile as `pii.py`'s PII
  detection — no LLM call). Person/org NER explicitly out of scope — regex
  heuristics for those produce too many false positives on headers/titles.
- Wired into `index_chunks()` (ingest.py), both retrieval paths
  (retrieve.py), and `build_source_doc()` (citations.py) — citations now
  carry structured `{type, value}` entities.
- Frontend: entity chips on `RagSourceCard.tsx` citation cards.
- **Follow-up (same session, user-initiated)**: extended entities from
  display-only to genuine retrieval filtering. Added `entity_type_filter`
  parameter threaded through `dense_retrieve`/`bm25_retrieve`/
  `hybrid_retrieve`/`tiered_hybrid_retrieve`/`multi_query_retrieve` (mirrors
  `chunk_type_filter`'s existing hard-filter pattern). Chroma filtering uses
  scalar `has_money`/`has_date`/`has_percent` boolean flags per chunk
  (`entity_type_flags()` in entities.py) since Chroma metadata must be
  scalar, not a JSON list. Caught and fixed a real bug via direct Chroma
  testing: a single-type `entity_type_filter` wrapped in `$or` failed
  validation (`$or` requires 2+ clauses) — fixed by skipping the `$or`
  wrapper for a single type, same pattern `chunk_type_filter` already uses.
- `mm-ingest`'s SSE done event gained `entity_types: string[]` (which types
  exist anywhere in the doc) so the frontend knows which filter chips to
  show — computed once, not folded into the existing `chunk_summary` dict
  (kept separate to avoid touching that dict's existing 4-processor
  aggregation surface).
- Frontend: `DocumentChipsRow.tsx`'s existing "Only search" row extended
  with Money/Date/Percent chips alongside Text/Table/Figure/etc — user chose
  "same row" over "separate row" when asked directly.
- **Housekeeping**: `mm_ingest.py` crossed 400 lines during this work —
  extracted ingestion-diffing (revision detection) into new
  `mm_revision.py`, per CLAUDE.md's file-length rule.
- Verified live via curl (`entity_type_filter=["percent"]` correctly
  returned 0 chunks for a doc with no percent; `["date"]` correctly returned
  the date-containing chunk) and Playwright (chips render only for entity
  types actually present; selecting "Date" still retrieves correctly).
- Commits: ML-Unified `c740bb2`, `06964b0`; ml-portfolio `d8f4c4c`, `338d948`.

## 3. Live search/highlight over document text (unplanned, user-driven)

Grew out of a user question ("can it find important words and add as a
chip?") that, through several rounds of clarification, converged on: a live
search-as-you-type box over a document's extracted text (matching the
existing video-transcript search UX), not auto-extracted keyword chips.

- **Backend**: `mm-ingest`'s done event gained `text_segments: [{page,
  text}]` — a document's plain-text chunks in reading order. Excluded for
  video (its audio transcript is ALSO chunk_type "text" but already has a
  richer, timestamped `transcript_segments` view — this would've just
  duplicated it).
- **Frontend refactor**: extracted the video-transcript search box (input +
  match counter + ↑/↓ nav + highlighting) into a new shared
  `SearchableTextPanel.tsx` component (SRP/DRY) and reused it for a new
  "Extracted text" search panel in `DocumentSummaryPanel.tsx` for non-video
  docs. Net line-count REDUCTION in DocumentSummaryPanel despite gaining a
  feature, since search logic was no longer duplicated.
- **Matching-algorithm debugging arc** (user explicitly asked "how do
  search algorithms work" then "which is well-suited for a large document,"
  driving genuine research before implementing):
  - Started with word-boundary PREFIX match ("child" matches "children").
  - User asked for real-time-as-you-type + irregular-plural coverage
    (man/men, mouse/mice). Installed `stemmer` npm package (Porter/Snowball,
    2KB, zero deps) — but **verified directly before committing to it** that
    `stemmer("child")` ≠ `stemmer("children")` (different stems) — a
    stemmer alone would have been a REGRESSION vs. the existing prefix
    match, since stemmers only strip regular suffix patterns, not irregular
    forms. Caught this via direct testing, not assumption.
  - Checked a full dictionary-based lemmatizer (`wink-lemmatizer`) as the
    "correct" alternative — real cost check via `npm view`: its own code is
    36KB but its `wink-lexicon` dependency (actual word-form dictionary) is
    **12.5MB unpacked**. `natural` (bigger NLP lib) is 13.7MB and pulls in
    server-only deps (mongoose/redis/pg) — unusable client-side. Ruled both
    out as disproportionate for a search box over one document.
  - **Landed on a hybrid**: prefix match → Porter stemmer → small
    hand-maintained list of ~12 common English irregular plurals
    (child/children, man/men, mouse/mice, etc.), isolated behind one
    function (`wordsMatch()` in new `wordMatch.ts`) specifically so a future
    upgrade to a real lemmatizer is a localized change, not a rewrite.
  - Saved a memory (`project_search_matching_hybrid.md`) documenting the
    full reasoning/cost tradeoff per the user's explicit request ("note it
    somewhere so it can be helpful in future"), plus an equally detailed
    doc-comment directly in `wordMatch.ts`.
  - Verified live via Playwright: "man" correctly highlights both "men" and
    "man" (not "women"); "mouse" correctly highlights both "mice" and
    "mouse."

### Two real bugs the user caught by actually using the feature

**Bug A — barely-visible highlight.** The `<mark>` style used a 33%-opacity
background tint, nearly invisible against the panel's dark background.
Fixed: solid accent-color background + bold dark text. Verified via
screenshot.

**Bug B — whole paragraph appeared "highlighted."** User noticed (and
pushed back twice, correctly refusing my first two wrong explanations)
that typing "machine" made page 1's ENTIRE paragraph look tinted while page
2 showed only the matched word. Root-caused via direct Playwright
reproduction with the exact same resume file and query: there were TWO
separate highlighting mechanisms — the correct per-word `<mark>`, AND a
separate whole-item background tint applied to whichever item was the
"currently selected" search match (`isCurrentMatch`). That mechanism made
sense for the ORIGINAL video-transcript use case (each item = one short
subtitle line, so tinting "the current line" is subtle) but broke down for
a document use case where each item is an entire page of text — tinting
"the whole current item" lit up a full paragraph. Fixed by removing the
`isCurrentMatch` background entirely (↑/↓ navigation and auto-scroll are
driven by state, not this background, so nothing about navigation broke);
kept the separate `highlightedKey` background (citation/chapter jump-to)
untouched. Verified live via Playwright + screenshot on both pages.

**Debugging note**: an earlier exchange in this same investigation
involved the user asking "why does 'd' highlight all these unrelated
words" — direct testing (`stemmer()`/`startsWith()` against every listed
word) proved NONE of them matched "d," but ALL of them started with "c" —
concluded the actual typed query was "c," misread as "d" in the screenshot
due to the text cursor. Confirmed by exact reproduction with the same file
and query, word-for-word, before accepting the theory.

## Commit summary
| Commit | Repo | What |
|---|---|---|
| `d2e966b` | ML-Unified | MMRAG-02 backend: contradictions.py |
| `277d2c3` | ml-portfolio | MMRAG-02 frontend: ContradictionsPanel |
| `c740bb2` | ML-Unified | MMRAG-03 backend: entities.py, wired into ingest/retrieve/citations |
| `d8f4c4c` | ml-portfolio | MMRAG-03 frontend: entity chips on RagSourceCard |
| `06964b0` | ML-Unified | entity_type_filter retrieval filtering + mm_ingest.py modularization (mm_revision.py) |
| `338d948` | ml-portfolio | Money/Date/Percent filter chips in DocumentChipsRow |
| `4e65c8a` | ML-Unified | text_segments in mm-ingest done event |
| `1968dc8` | ml-portfolio | SearchableTextPanel.tsx (shared live search component) |
| `4e0eea7` | ml-portfolio | wordMatch.ts hybrid prefix+stemmer+irregular-plural matching |
| `d6c14fc` | ml-portfolio | fix: highlight visibility (solid bg vs faint tint) |
| `60c0729` | ml-portfolio | fix: remove whole-item background tint for current search match |

## Addendum — MMRAG-05: query decomposition (same day, follow-up)

- New `node_decompose` in `agent_nodes.py`, inserted into the existing
  `/rag/agent` LangGraph loop as `router → decompose → retrieve → grade →
  (rewrite → retrieve)* → generate`. Only runs on the `complex` route (a new
  `edge_after_router`), so simple single-fact queries pay no extra LLM call.
- One meta-LLM call splits a compound question ("what's the deadline in doc
  A and the budget in doc B") into 2-3 standalone sub-queries; a single
  coherent question passes through unchanged. Reused
  `multi_query_retrieve()`'s existing multi-query RRF-merge (already used
  elsewhere for phrasing variants) for the actual multi-query retrieval — no
  new retrieval logic needed.
- `AgentState` gained `sub_queries: list`; SSE stream gained a
  `"decomposing"` step and surfaces `sub_queries` (only when an actual split
  happened, i.e. length > 1) in both the `agent_step` and final `done`
  events, for UI transparency.
- Verified: `node_decompose`/`node_retrieve` logic directly with mocked LLM
  calls (compound query → 2 sub-queries; simple query → passthrough;
  sub-queries correctly threaded into `multi_query_retrieve`) before
  touching the deployed Space.
- Deployed: committed `05dfd81`, pushed, uploaded `agent.py`/`agent_nodes.py`
  to the HF Space, confirmed `RUNNING` and actually serving the new code —
  live SSE stream shows the `"decomposing"` step firing correctly.
- **Known gap**: didn't get a clean live observation of an actual 2-way
  split producing populated `sub_queries` in the SSE output — both live test
  attempts hit the shared server Gemini key's `429 Too Many Requests` (same
  rate limit that also hit `router`/`grader` on the same requests), so
  `decompose` fell back to its default (single query) exactly as designed.
  This is the existing free-tier shared-key rate-limit behavior, not a bug
  in the new node — confirmed via HF Space run logs, not guessed. Stopped
  retrying after two identical rate-limited attempts rather than burn more
  of the same quota for no new information.
- Commits: ML-Unified `05dfd81`.

## Pending
- MMRAG-01 through 05 are done. Next candidates: MMRAG-06 (standalone audio
  ingestion — low-medium effort, Whisper pipeline already exists), MMRAG-07
  (visual grounding/bounding boxes on citations), MMRAG-08 ("why was this
  cited" trace panel).
- Full backlog reference: `project_mmrag_feature_backlog.md` memory file.
