# Session Part 211 — 2026-07-27

## Context
Continued from Part 210 (MMRAG-02/03, live text search). This session shipped
MMRAG-05 (query decomposition), MMRAG-06 (standalone audio ingestion),
MMRAG-07 (visual grounding — bounding boxes on citations), then an
unplanned but substantial MMRAG-07 follow-up: object detection for image/
video citations, expanded to a 601-class vocabulary, with two real bugs
found and fixed in how detected objects reach the LLM's own answers.

## 1. MMRAG-05 — Query decomposition

- New `node_decompose` in `agent_nodes.py`, inserted into the existing
  `/rag/agent` LangGraph loop as `router → decompose → retrieve → grade →
  (rewrite → retrieve)* → generate`. Only runs on the `complex` route (new
  `edge_after_router`) — simple single-fact queries pay no extra LLM call.
- One meta-LLM call splits a compound question into 2-3 standalone
  sub-queries; a single coherent question passes through unchanged. Reused
  `multi_query_retrieve()`'s existing multi-query RRF-merge — no new
  retrieval logic needed.
- Verified: node logic directly with mocked LLM calls, then live — the
  `"decomposing"` SSE step fires correctly in production. Live end-to-end
  split observation was inconclusive twice in a row (shared server Gemini
  key hit `429` both times, same as router/grader on the same requests —
  confirmed via HF Space logs, not guessed) — decompose's graceful
  fallback (single query) worked exactly as designed under that condition.
- Commit: ML-Unified `05dfd81`.

## 2. MMRAG-06 — Standalone audio ingestion

- New `mm_audio.py`: `looks_like_audio()`, `prepare_audio()`,
  `transcribe_audio_upload()` — the last one is the ONLY new orchestration
  logic; it calls `mm_video.py`'s `transcribe_video()` completely
  unmodified, since that function only ever shells out to ffmpeg + Whisper
  on a file path and never touches video frames — it already worked
  identically for a bare audio file.
- `mm_ingest.py` gained an `is_audio` branch (one atomic call, like the
  image branch); `mm_video_store.py`'s existing generic byte-serving
  endpoint reused for audio playback too — no new storage/serving code.
- Verified live end-to-end: generated a real speech clip via macOS `say`,
  ingested it on the deployed Space, then asked a real chat question and
  got a correct, cited answer (0.98 retrieval score) — not just a
  successful upload.
- Two follow-up UI bugs reported by the user, both fixed same session:
  - Progress bar said "Analyzing image…" for every atomic-call upload
    type (image/CSV/audio) — now derives the label from the actual file
    being processed.
  - Added a tooltip on the audio player warning that Whisper transcribes
    speech only — music/instrumental audio may return a hallucinated
    transcript instead of failing outright (verified: Whisper's known
    failure mode on non-speech audio, not a bug in the ingestion code).
- Commits: ML-Unified `876b1a9`; ml-portfolio `dab706b`, `0df6c7b`.

## 3. MMRAG-07 — Visual grounding (bounding boxes on citations)

- Table/figure chunks now carry the exact page-relative bbox they came
  from — `page.find_tables()`'s own bbox for tables, the largest
  qualifying raster image's bbox for figures — computed at chunk-creation
  time in `mm_pdf.py`, not re-searched for later.
- The `chunk_type`/`page`/`bbox` metadata plumbing already existed
  end-to-end (`ingest.py` → `retrieve.py` → `citations.py`) from earlier
  scaffolding, unused until this session. bbox is JSON-encoded before
  reaching Chroma (scalar-only metadata) and decoded in `citations.py`,
  mirroring the existing entities encode/decode pattern.
- Refactored `prepare_pdf()`/`process_page()` to find tables per-page
  directly instead of a separate whole-doc `extract_tables_markdown()`
  pre-pass, so each table's bbox is available right where its chunk is
  built.
- **Real bug caught before deploy**: `tab.bbox` is a plain 4-tuple in this
  PyMuPDF version, not a Rect with `.x0`/`.y0` attributes (the pattern the
  existing Document Intelligence bbox code assumed) — fixed via index
  access, which works for both. Caught by direct local testing against a
  synthetic PDF with a known table + embedded image, verified the computed
  bbox matched the known ground-truth rect exactly (both table and figure).
- **Real bug found live via user screenshot + direct DOM measurement**:
  the overlay box was misaligned once the page thumbnail scrolled. Root
  cause: `position:relative` was on the scrollable outer div
  (`overflow-y:auto` + `max-height`, no explicit `height`) — CSS resolves
  an absolutely-positioned child's percentage `top`/`height` against that
  ancestor's CLIPPED viewport, not the full scrollable content height.
  Measured live: a bbox at `top:50.5%` rendered at 50.5% of the 320px clip
  (161px) instead of 50.5% of the image's true 787px height. Fixed by
  moving `position:relative` to an inner wrapper sized exactly to the
  image; re-verified with the same DOM-measurement technique plus a
  screenshot showing the box correctly wrapping the actual image content.
- Commits: ML-Unified `3c9a10c`; ml-portfolio `c71bacc`, `ce8d14e`.

## 4. MMRAG-07 follow-up — Object detection ("where is the X")

User asked, after seeing the PDF bbox feature working, why a standalone
image citation (bicycle.jpg) had no box. Led to a scoped conversation
about what "visual grounding for a photo" actually requires (object
localization, not page-region math), landing on:

- **Closed-vocabulary detector, precomputed at ingest, matched by keyword
  at query time** — not a per-question vision/LLM call, and not an
  open-vocabulary detector (GroundingDINO/OWL-ViT — 600MB-1.7GB, ruled out
  as disproportionate for v1, same reasoning pattern as the wink-lexicon
  decision in Part 210).
- **ONNX Runtime, not `ultralytics`** — checked real PyPI dependency
  metadata: `ultralytics` pulls torchvision, matplotlib, polars,
  nvidia-ml-py, and its own `opencv-python` (conflicts with the
  `opencv-python-headless` already used for video frame sampling).
  `onnxruntime` was already a project dependency.
- New `mm_objects.py`: letterbox preprocessing + NMS postprocessing,
  verified against the standard ultralytics `bus.jpg` demo image (4 people
  + 1 bus) BEFORE writing any wiring code — detections matched the
  canonical reference exactly, confirmed numerically AND by drawing the
  boxes and visually inspecting them.
- Wired into `mm_image.py` (standalone images) and `mm_video.py` (video
  frames) — `chunk["objects"]` threaded through `ingest.py`/`retrieve.py`/
  `citations.py`/`mm_ingest.py` exactly parallel to the bbox/entities
  encode-decode pattern.
- Frontend: `matchObjectToQuestion()` in `MmRagRunner.tsx` — case-
  insensitive, word-boundary match of the last-asked question against a
  citation's precomputed object labels, longest label first (so "traffic
  light" beats a shorter overlapping word). `CitationThumbnailPanel.tsx`
  draws a distinctly-colored, labeled box for a matched object, taking
  priority over the static table/figure bbox.
- **File-length housekeeping caught mid-session**: `MmRagRunner.tsx`
  crossed 350 lines without a check-first (should have modularized before
  touching it, per project rule). Caught before deploying — extracted the
  entire chat message/input panel into new `ChatPanel.tsx`, bringing both
  files comfortably under 350.
- Verified live: uploaded the real `bus.jpg` fixture, asked "where is the
  bus" (correct green box, 84% confidence) and "where is the person"
  (correctly boxed the highest-confidence person match) via Playwright —
  screenshots + accessibility snapshots, not just API responses.
- **Known, disclosed limitation surfaced honestly**: asking about "the
  person on the left" specifically returned the highest-confidence person
  regardless of position — the matcher resolves class labels, not
  spatial/instance disambiguation. Reported to the user as expected v1
  scope, not a bug.
- Commits: ML-Unified `80f19b1`; ml-portfolio `0056a8f`.

## 5. Expanding vocabulary (Open Images V7) + feeding labels to the LLM

User asked two follow-up questions after testing: (1) why did "where is
the bus" get answered "The bus belongs to EMT Madrid" instead of
describing location, (2) whether ImageNet-1K could expand detectable
classes. Answered both conceptually (ImageNet-1K is classification, no
bbox at all — wrong tool; the text-answer gap was a separate architecture
issue: the bbox overlay is frontend-only, never seen by the LLM), then
user approved proceeding with both fixes.

- **Model swap**: exported `yolov8s-oiv7.pt` (Ultralytics' official Open
  Images V7 weights, 601 classes) to ONNX ONCE locally, in a throwaway
  venv (`ultralytics` never became a runtime dependency), and committed
  the resulting ~44MB `.onnx` file directly into
  `services/ml-api/routers/rag/models/` — a normal git-tracked asset, so
  no download-on-first-use step needed at all (unlike CLIP's ~350MB
  first-use download).
- **Real accuracy finding, not assumed**: tested the smaller/faster
  "nano" OIV7 variant first — raw confidence for the same bus.jpg's bus
  topped out at 0.18 (below threshold, silently found nothing on an
  obviously-present object). The "small" variant scored the same bus at
  0.74. Confirmed via direct confidence-score inspection (not just
  threshold retuning) that this was a genuine model-capacity issue —
  601 classes needs more capacity than COCO's 80. Verified the "s" variant
  visually too (drew boxes: Bus, Man x3, Footwear x4, Jeans, Wheel — all
  correctly placed).
- **LLM context labeling**: extended `citations.py`'s existing
  chunk_type/page labeling to include detected objects.
- **Real bug found via live verification, not assumed fixed**: after
  deploying, asked "where is the bus" again — STILL got "The bus belongs
  to EMT Madrid," despite the label now correctly containing "contains:
  Bus (spans most of the frame)". Root-caused by reconstructing the exact
  system prompt sent for the real live chunk data: the prompt explicitly
  tells the model the `[source, page, type]` bracket is "for your
  reference only... do NOT repeat, quote" — the model applied that
  instruction to the object list too, since it lived in the same
  brackets. Fixed by moving object/position info to ordinary trailing
  text on the chunk (same status as the caption) instead of inside the
  bracket — re-verified live, the answer changed from "The bus is in
  Madrid" to "The bus is in the foreground, spanning most of the frame."
- Added `_spatial_phrase()` — a coarse 3x3-grid description (left/center/
  right, top/bottom, or "spans most of the frame" for a large box)
  computed from each detection's bbox. Verified against bus.jpg's known
  layout before deploying: the bus (≈46% of frame) correctly produced
  "spans most of the frame"; three people at known left/center/right
  positions each got the matching phrase.
- **Real, correctly-behaved limitation found live**: asking "which side is
  the man in the cream coat on" got an honest "the provided information
  doesn't specify" — object detection boxes (generic "Man") and caption
  attributes ("cream coat") are independent, unlinked model outputs with
  no shared identity; the model correctly declined to guess rather than
  hallucinate a match.
- Saved `project_object_detection_grounding.md` memory (at
  `/Users/wrks/.claude/projects/-Users-wrks-Downloads-Claude-documentation-Projects-ML-Unified/memory/project_object_detection_grounding.md`
  — Claude's auto-memory store, not part of this repo) documenting the
  full model-choice/dependency/prompt-placement reasoning for future
  reference, per explicit user request.
- Commits: ML-Unified `a94cb15`, `9b8bc5f`, `bdf102a`.

## Commit summary
| Commit | Repo | What |
|---|---|---|
| `05dfd81` | ML-Unified | MMRAG-05: query decomposition node |
| `876b1a9` | ML-Unified | MMRAG-06 backend: standalone audio ingestion |
| `dab706b` | ml-portfolio | MMRAG-06 frontend: audio upload UI |
| `0df6c7b` | ml-portfolio | fix: progress label + hallucination warning tooltip |
| `3c9a10c` | ML-Unified | MMRAG-07 backend: table/figure bbox |
| `c71bacc` | ml-portfolio | MMRAG-07 frontend: bbox overlay |
| `ce8d14e` | ml-portfolio | fix: bbox overlay scroll-clip misalignment |
| `80f19b1` | ML-Unified | Object detection backend (COCO, ONNX) |
| `0056a8f` | ml-portfolio | Object detection frontend + ChatPanel extraction |
| `a94cb15` | ML-Unified | Swap to Open Images V7 (601 classes); label objects into LLM context |
| `9b8bc5f` | ML-Unified | fix: add spatial phrases to object labels |
| `bdf102a` | ML-Unified | fix: move object info outside citation bracket |

## Pending
- MMRAG-01 through 07 (plus the object-detection follow-up) are done.
  Note: `citations.py`'s object-labeling fix applies uniformly to any
  chunk carrying an `objects` field regardless of `chunk_type`, so video
  frames (which already get `detect_objects()` called on them in
  `mm_video.py`) get the same spatial-phrase LLM-context treatment as
  images automatically — not verified live for video specifically this
  session, worth a quick live check next time a video is uploaded.
  Next candidate: MMRAG-08 ("why was this cited" trace panel) — a natural
  pairing now that citations carry richer grounding data.
- Full backlog reference: `project_mmrag_feature_backlog.md` memory file
  (Claude's auto-memory store, path above).
- Object detection design reference: `project_object_detection_grounding.md`
  (same memory store, path above).
