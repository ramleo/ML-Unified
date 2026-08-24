# Session 2026-07-21/22 — Multimodal RAG Backlog Round: Query-Aware Boosting, Table Rendering, CSV Upload, Multi-Doc Q&A, Summary View (Part 204)

Continuation after Part 203 (Multimodal RAG's initial build + first live-debugging
marathon). This session picked up mid-conversation after a context compaction,
resumed the interrupted Playwright verification of the Cohere/expansion fix, then
moved into a new backlog round driven by live UI screenshots and a "what should we
add next" brainstorm. User flagged mid-session that weekly context usage was at 86%
with a 19-hour reset — every step after that was run deliberately lean: no
subagents, minimal exploration, direct edits, batched deploys.

---

## 1. Resumed: Cohere/expansion fix verification

Picked up the Playwright check that was interrupted by a context compaction.
Selected Cohere in the live UI (server key, no BYOK), asked a question against the
uploaded standalone image, and confirmed the transparency tag rendered exactly as
designed: **"cohere unavailable (rate limited) — answered via groq"**, tooltip
showing the specific fallback model, clean citation text (no leftover
`[Image: source]` prefix). Closed out Part 203's one remaining open item.

## 2. Two live bugs surfaced by screenshots, both fixed same round

- **Right panel showed only one page at a time**, with no way to browse a
  multi-page document independent of citations. Not a bug — by design (the panel
  always jumped to whichever page the active citation pointed to) — but a real
  gap. Added `PageThumbnailRail.tsx`: a vertical strip of every page, click to
  browse independently of citations. Hidden for single-page/image uploads.
- **A resume's "Career Timeline" graphic wasn't captioned at all.** Root cause,
  found in `mm_pdf.py`'s `_is_visually_dense()`: the check was page-level,
  all-or-nothing — if a page's real text cleared 80 characters, the function
  short-circuited `return False` before ever checking for embedded images, so a
  text-heavy page with an embedded graphic got zero visual captioning. Fixed by
  dropping the text-length short-circuit entirely — any page with
  `get_images()`/`get_drawings()` now gets captioned, regardless of surrounding
  text volume.
- User asked for a better vision model recommendation for reading dense graphics.
  Real bottleneck wasn't model choice — it was the caption prompt itself (2-4
  sentence summary, 500-char cap) structurally unable to hold 6 job entries ×
  2 dates each. Recommended (and built) reusing `mistral-ocr-latest` (already
  proven in Document Intelligence) as a **second pass alongside the caption** —
  exact OCR'd text appended to the caption, not replacing it. Verified live:
  asked "give me dates in career timeline," got every role's exact start/end
  date correctly, still tagged "Answered via gemini" (server default, not a
  fallback — confirmed no `primary_provider` was set, so nothing was silently
  swapped).

Commits: ML-Unified `0fcf9ca` (page-image fix), `3db512c` (OCR pass);
portfolio `5779498` (page browser), `12a6b50`+`d1cb9a3` (guide updates).

## 3. Feature brainstorm → picked one → built it: RRF modality-weighting

Asked what other real improvements fit current 2026 multimodal RAG best
practices; web-searched, filtered out enterprise-governance noise (SSO, audit
logs — not relevant to a portfolio demo), kept two candidates: caption-vs-OCR
consistency checking, and RRF modality-weighting. Recommended the latter — a
concrete, already-witnessed failure mode (a short table/figure/image chunk
losing the RRF fusion race to a longer, weaker-but-verbose prose match) vs. a
speculative one (no hallucinated caption had actually been observed yet).

Built: `reciprocal_rank_fusion()` gained an optional `type_boost` param
(default `None` — zero behavior change for the plain-text RAG tool), threaded
through `hybrid_retrieve`/`tiered_hybrid_retrieve`/`multi_query_retrieve`.
`query.py` applied a flat 1.2x boost to table/figure/image chunks, but only in
`restrict_to_uploads` mode (Multimodal RAG) — never for the general-KB tool.

**Refined same session**, at user's follow-up ("start with query-aware
boosting, go one by one"): a flat boost over-promotes a figure caption even on
a purely textual question. Added `_detect_type_boost()` — a small keyword
heuristic (table/row/column..., chart/graph/figure/diagram/plot/trend/visual...,
image/photo/picture...) that only boosts the specific chunk_type(s) a question
actually seems to be asking about, at 1.3x. `query.py` crossed the 400-line cap
building this — split its semantic-cache helpers into a new `cache.py` module
(pure extraction, no behavior change) to stay under it.

Commits: ML-Unified `5cd79d6` (flat boost + cache.py split), `820b798`
(query-aware refinement).

## 4. Backlog build-out, one item at a time as requested

User asked for "useful features apart from RRF weighting," then worked through
them one by one:

- **Table-native rendering** (`1c053dc`, portfolio): table citations were
  showing raw pipe-markdown (`| a | b |`) as plain truncated text. No
  `remark-gfm` dependency existed for proper markdown table parsing — rather
  than add one mid-session, wrote a small inline parser (`parsePipeTable`) for
  the exact, fully-known format `extract_tables_markdown()` already produces.
  `RagSourceCard.tsx` now renders an actual `<table>` when `chunkType==="table"`.
- **CSV upload** (`0227572`, ML-Unified): scoped to CSV only, not CSV+XLSX as
  first discussed — `openpyxl` isn't a current dependency, and adding one
  plus verifying it installs cleanly on the HF Space would have cost real
  context/time under the budget constraint. `build_csv_chunks()` in
  `mm_ingest.py` reuses the existing `table` chunk_type end-to-end (500-row
  cap, 50 rows/chunk) — same retrieval/citation path as a PDF's embedded
  tables, zero new infrastructure.
- **Multi-document Q&A** (`92744f8`, portfolio only — **zero backend changes**):
  turned out smaller than scoped. The backend's `tiered_hybrid_retrieve` tier-1
  filter was already `{uploaded: True, session_id: X}` — scoped to the whole
  session, not a single source — so multiple simultaneous uploads were already
  jointly retrievable; the only reason it behaved as single-document was
  `IngestProgressRail.tsx` explicitly calling `DELETE /rag/uploads/{source}` on
  the previous upload before every new one. Removed that call, turned
  `MmRagRunner`'s single `ingested` object into a `documents` list with a
  per-document remove button, and made the citation/preview panel resolve
  against whichever document a citation actually belongs to (not just "the"
  document).
- **Per-document summary view** ("dashboard," per user's earlier phrasing) —
  offered two interpretations (per-doc structure summary vs. cross-session
  usage analytics) via `AskUserQuestion`; recommended the former (reuses
  already-extracted data, no new tracking/storage needed). Backend: added
  `notable_chunks` (all non-text chunks — tables/figures/images) to the
  `mm-ingest` done event (`4602a74`). Frontend: a "▸ summary" toggle next to
  each document chip expands to list every extracted table/figure/image via
  the same `RagSourceCard` component (reusing the table-native rendering from
  earlier), with a new `hideConfidence` prop since there's no query relevance
  score in this context (`ef6ecdf`).

Each item deployed and verified individually per the batch-deploy convention:
commit → push → HF Space upload → poll for `RUNNING` → confirm `lastModified`
matches the fresh commit (not just a cached `RUNNING` from before the upload,
learned from an earlier session) → health check.

## 5. Two follow-up questions from live screenshots

- **User re-tested and asked "where is dashboard?"** after seeing the expanded
  summary panel working correctly — clarified that the panel they were already
  looking at (per-document, "▸ summary" toggle) *is* the feature; "dashboard"
  was only the word used during the brainstorm, never a literal UI label. Also
  proactively flagged a real quality issue visible in their own screenshot:
  Resume page 3 was captioned as a "figure" whose own caption said *"this is a
  text-based document, not a visual"* — a side effect of the earlier
  visually-dense fix now captioning pages with even a tiny decorative
  image/drawing (an icon, a divider). Offered to tighten the check; not yet
  built, pending user decision.
- **"What about invoice, doesn't it have a table?"** — explained a real
  architectural gap: `find_tables()` only runs on actual PDF pages via
  PyMuPDF; a standalone image upload (the invoice was a PNG) always goes
  through the single holistic image-caption path (`build_image_chunk`),
  never table-detection. Also flagged that the OCR pass added earlier this
  session only runs on PDF figure pages (`mm_pdf.py`), not standalone images —
  so a standalone invoice's numbers rely on the general caption alone, not
  OCR-backed exact text. Offered a fix (route standalone images through the
  PDF pipeline, or add table detection to the image path directly) — not yet
  built, pending user decision.

## 6. Backlog captured in project memory

At user's request, saved the full running backlog to
`project_realworld_usecases.md` (auto-memory): 11 proposed-but-unbuilt
features (video support, export/download structured data, follow-up source
drill-down, confidence-aware OCR-vs-caption checking, redaction/PII awareness,
answer-length control, manual chunk-type retrieval filter, shareable session
URL, table→chart on demand, ingestion diffing for re-uploads, and a
usage/analytics dashboard as the explicitly-not-built alternative to the
per-document summary view that was built instead) — plus a compact record of
everything actually shipped this session, so a future session with no memory
of this conversation can still pick up the thread accurately.

## 7. Key lessons reinforced

- **A user's "let's see" is real signal, not idle chatter** — when told to
  proceed with an item "now, let's see," building and deploying immediately
  (rather than batching further) let a real gap surface fast (the resume's
  page-3 false-positive figure caption, the invoice's missing table
  extraction) — direct, current live-testing catches things a plan never would.
- **A feature that already half-exists in the backend can make a "big"
  request small.** Multi-document Q&A was scoped as a meaningful architecture
  change; it turned out the retrieval layer already supported it, and the
  entire feature came down to *removing* one deletion call plus frontend
  state reshaping — worth actually reading the current retrieval filter
  before assuming a feature needs new backend plumbing.
- **Context-budget awareness changes real engineering choices, not just
  pace.** Explicitly scoped CSV-only (not CSV+XLSX) specifically to avoid a
  new-dependency install/verify cycle under time pressure — a smaller, honest
  feature now over a bigger one that risks not finishing cleanly.
- **A component's own screenshot is often the fastest bug report.** Both
  follow-up issues this session (page-3 mislabeled figure, invoice's missing
  table) were caught by the user just looking at what the tool had already
  produced, not through deliberate testing — worth continuing to invite "what
  do you see" rather than only reacting to explicit bug reports.
