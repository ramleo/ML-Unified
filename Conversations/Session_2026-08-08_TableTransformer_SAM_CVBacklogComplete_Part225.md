# Session 2026-08-08 — Table Transformer, SAM, CV Backlog Complete (Part 225)

Continuation of Part 224 (tampering false-positive fix). This session finished the
remaining CV backlog items (3, already done pre-compaction; 4 and 5, built this
session), closing out the 6-item backlog from Part 221, then moved into a broader
brainstorm about future AI/CV invention ideas.

## Recap — backlog item 3 (perceptual-hash near-duplicate detection)

Already complete going into this session (built earlier, before a context
compaction). New `mm_duplicates.py` — dHash-based near-duplicate detection,
scoped per `session_id` so it never cross-reports between different users/
sessions. Wired into `mm_image.py`/`mm_video.py` at ingest; a cache-hit fix
(`refresh_duplicates_for_chunks`) was needed since the ingest cache is keyed
on file bytes, not session — without it, re-uploading the exact same file
twice in one session (the single most obvious duplicate case) would've been
silently undetectable. Frontend: new "Possible duplicate (N)" dropdown
option in `CitationThumbnailPanel.tsx`. Verified live via two production
uploads of the same bytes under one session_id — second returned a 100%
match against the first. Commits: `7768dfa` (backend), `c380e49` (frontend).

## Backlog item 4 — Table Transformer

**Investigation before building**: real, text-based PDF pages already get an
exact table bbox for free via PyMuPDF's native `page.find_tables()`
(`mm_pdf.py`) — pure vector geometry, no model needed. The actual gap: a
standalone image upload (`mm_image.py`) reconstructs tables from Mistral
OCR's markdown (`split_pipe_tables`) but that reconstruction carries no bbox
at all — no citation highlight box, unlike every other chunk type. Also
confirmed `transformers` (which ships `TableTransformerForObjectDetection`)
and `torch` were already present as dependencies (torch transitively via
`sentence-transformers`, used for the existing opt-in CLIP similarity
feature) — so this didn't need a new heavy dependency, just `timm` for the
ResNet backbone.

**Built**: `mm_tables.py` — `microsoft/table-transformer-detection` (DETR,
ResNet-18 backbone, ~110 MB), lazy-loaded on first use (same pattern as
`mm_similar.py`'s CLIP model). `detect_table_regions()` returns bboxes
sorted top-to-bottom, paired positionally against `table_blocks` (both lists
are top-to-bottom; neither carries an independent position/ID to pair on
otherwise). Only wired into `mm_image.py` — PDF pages don't need it, video
frames don't build separate table chunks at all currently.

**Verified before deploying**: local test with a hand-drawn grid (no text)
found NOTHING even at low threshold — a bare grid isn't realistic enough for
a model trained on real document tables. Rebuilt the test with a realistic
invoice-style table (grid + header/data text) — detected at 99.97%
confidence, bbox closely matched the drawn table region. This caught a real
gap in the first test methodology before it could cause a false "it doesn't
work" conclusion.

**Deploy**: added `timm>=1.0.0` to `requirements-base.txt` — this changed
the Dockerfile's heavy Layer 1 (torch/transformers/ML libs), triggering a
full base-layer rebuild rather than the usual fast path; correctly
anticipated this would take longer than the normal 2-5 min window and
polled patiently instead of assuming failure. Build completed in ~5 min
(`RUNNING_BUILDING` → `RUNNING_APP_STARTING` → `RUNNING`). Live end-to-end
verified: POSTed the same synthetic invoice-table image directly to the
deployed `/rag/mm-ingest`, confirmed the returned table chunk carried the
correct bbox and OCR-reconstructed table text. Commit `b0c203f`.

## Backlog item 5 — Segment Anything (final CV backlog item)

**Scoping decision**: rather than a generic "click to segment" interactive
feature (a genuinely different interaction paradigm — query-time compute,
no upload-driven precedent anywhere else in this codebase), applied SAM as
a refinement of ALREADY-detected bboxes into pixel-accurate masks — same
"compute once at ingest, additive metadata" pattern every other backlog
item used. Chose to apply it specifically to signature and tampering
detections, since those two detector types' rectangular bbox understates
the real shape (ink strokes, irregular edited regions) far more than a
face's or generic object's bbox does.

**Model choice**: tested `Zigeng/SlimSAM-uniform-77` (77%-pruned distillation
of SAM ViT-B, ~39 MB, ~9.7M params) via `transformers`' `SamModel`/
`SamProcessor` — no new pip dependency, since these classes ship in the
already-required `transformers` package. Full SAM (ViT-H, ~2.4 GB) was never
viable on a CPU-only free-tier Space; this was the reason "Segment Anything"
sat unstarted in the backlog since Part 221 as "a real upgrade but
meaningfully heavier, not pre-emptively justified" — finding SlimSAM (and
confirming torch/transformers were already present) is what changed that
calculus.

**Built**: `mm_segment.py` — `refine_masks(b64, regions)` takes a list of
already-detected `{label, confidence, bbox}` dicts, runs ONE BATCHED SAM
inference per image (all box prompts share the same expensive image-encoder
pass — confirmed via direct test: 2 box prompts took 0.61s vs. ~0.65s for a
single one, proving the encoder, not the decoder, dominates cost), extracts
each mask's largest contour via `cv2.findContours` + `approxPolyDP`
(simplified to <=40 points), normalizes to 0-1 image-relative coordinates,
and attaches as a `mask` field — same "plain JSON array" convention every
other bbox in this codebase already uses, not raw image/mask data. Purely
additive: falls back to the existing rectangle wherever refinement fails or
a region is past the per-image cap (`_MAX_REGIONS = 6`).

**Local verification**: synthetic circle+square test — circle got a 16-point
polygon tracing its outline, mask pixel area matched the expected circle
area almost exactly (31,577 vs. 31,415.9 expected); square got a clean
4-point polygon matching its bbox exactly.

**Frontend**: `CitationThumbnailPanel.tsx`'s shared `renderBoxes()` now
draws an inner SVG `<polygon>` (points converted from full-image-normalized
to bbox-LOCAL percentages, since the wrapping `<div>` is already positioned
at the bbox) instead of the plain rectangle border+background whenever a
`mask` is present — every other detection type (faces, generic objects,
duplicates) is unaffected, still plain rectangles. `DetectedObject` type
gained an optional `mask?: [number, number][] | null` field.

**Deploy**: no `requirements-base.txt` change this time (no new pip
package), so deploy was faster — `RUNNING_APP_STARTING` → `BUILDING` →
`RUNNING` in under 2 minutes. Live verification was harder than usual:
tried to synthetically trigger a real signature detection (hand-drawn
cursive scribble via PIL) — the ONNX signature detector didn't recognize it
as a signature (expected; it's trained on real signature datasets, not
programmatic sine-wave scribbles). Tried to synthetically trigger tampering
— multiple attempts (uniform random noise patch, then Gaussian noise patch
at two magnitudes) all landed ELA detections but noise-residual never
corroborated, which is EXACTLY the already-documented, deliberately-accepted
precision-over-recall gap from Part 224's tampering fix (see
`project_tampering_detector_precision.md`), not a new bug — recognized this
and stopped trying to force it rather than keep burning cycles on a known
tradeoff. Settled for the verification that actually matters most: confirmed
via a live production upload that a normal image (no signature, no
tampering) still ingests cleanly with `signatures: null, tampering: null` —
proving `refine_masks`'s early-return path is safe in production for the
overwhelming majority of real uploads, which is the property that mattered
most to de-risk. Honestly flagged to the user that the "does a live
detection actually get a mask attached in production" step specifically
remains unverified — the refinement code itself is verified correct in
isolation (the circle/square test), only that one integration leg wasn't
provable with synthetic test images. Commits: `7385a40` (backend), `7018e4e`
(frontend).

## CV backlog — now fully complete (items 0-5)

All six items from the Part 221 backlog are shipped: item 0 (visual-actions
dropdown consolidation), item 1 (signature detection), item 2 (tampering
detection, later precision-fixed in Part 224), item 3 (near-duplicate
detection), item 4 (Table Transformer), item 5 (Segment Anything mask
refinement).

## AI/CV invention brainstorm — mapping against what's built

User pasted a list of AI/CV invention ideas (from an external source) using
free/open-source libraries (PyTorch, OpenCV, diffusers, MediaPipe, etc.) and
asked, via AskUserQuestion, to map them against what's already built rather
than pick one to build or just discuss.

**Already built (fully or substantially) in Multimodal RAG:**
- Deepfake Detection & Watermarking — tampering detection (ELA + noise-
  residual + SAM masks) covers the detection half; no watermark-embedding
  half exists.
- Smart Surveillance & Intrusion Alert — object detection (YOLOv8s-oiv7,
  601 classes incl. person) exists but runs on uploaded media, not a live
  webcam loop with zone-based alerting.
- Automatic License Plate Recognition — partial: Mistral OCR for exact-text
  extraction and object detection for "vehicle" gating both exist; no
  plate-specific crop/OCR pipeline.
- Blind Assistant Audio Describer — partial: VLM-generated "Describe"
  captions already narrate subject/setting/text; no TTS output, no live
  camera-snap workflow (upload-and-read only, not point-and-speak).

**Not built at all — genuinely new territory:**
Local Text-to-Image/Video Generator (nothing generative exists — everything
today analyzes existing images, doesn't create new ones), Automated Social
Reels Creator (transcription exists, nothing assembles/exports edited
clips), AI Image Inpainting & Object Remover, Gesture-Controlled Desktop
System (MediaPipe — no live-webcam/gesture tooling at all), Automated
Medical Scan Analyzer, Real-time Sign Language Translator.

Pattern named: everything built so far is document/evidence forensics on
UPLOADED media (detect, verify, extract); everything missing is either
generative (diffusion, inpainting) or live/real-time (webcam, gesture,
streaming) — a different architecture (no upload step, persistent camera
loop) than anything in this codebase today.

## Two follow-up questions

**"Before the 0-5 features, what was pending?"** — answered from Part 221's
own recap: two items finished in that same session, right before the CV
backlog was formed — MMRAG-27 (adaptive query routing: per-source-list
retrieval weighting via a new heuristic+LLM query classifier,
`INTENT_SIGNAL_WEIGHTS`, backend-only per user's explicit choice) and
MMRAG-28 (evidence-gated agentic verification: found the self-correction
retry already existed from MMRAG-04 but only fired on "low" groundedness
and regenerated blind; extended the trigger to the far more common "medium"
bucket when specific sentences were flagged, and made the retry actually
evidence-gated via a correction directive naming the flagged sentences).

**"Is it better to add the missing ideas as a new tool or fold into
Multimodal RAG?"** — recommended splitting by whether the feature needs an
upload step at all, not by topic similarity:
- Fold into Multimodal RAG: Image Inpainting/Object Remover (and arguably
  ALPR/audio-description if built out further) — these operate on an
  already-uploaded image and would reuse the existing upload -> process ->
  citation-panel plumbing almost entirely. Inpainting specifically now has a
  head start thanks to this session's SAM work — pixel-accurate masks
  already exist, so "let the user pick a region and inpaint it" is a much
  smaller lift than it would've been before item 5.
- New, separate tool: Text-to-Image Generator, Social Reels Creator,
  Gesture-Controlled Desktop, Medical Scan Analyzer, Sign Language
  Translator — none share Multimodal RAG's core loop (upload -> retrieve ->
  cite -> chat); they're generative-from-scratch, live/streaming, or
  single-purpose analyzers with their own domain UI. Wedging them into
  Multimodal RAG would mean carrying its entire retrieval/citation/chat
  scaffolding for a feature that never uses it.
- Gave a personal instinct (Inpainting first, cheapest and most synergistic
  with what's already built) but left the choice explicitly to the user —
  nothing was built or committed to from this brainstorm.

## Files touched this session

**Backend:**
- `services/ml-api/routers/rag/mm_tables.py` (new) — Table Transformer
  table-region detection.
- `services/ml-api/routers/rag/mm_segment.py` (new) — SAM/SlimSAM mask
  refinement.
- `services/ml-api/routers/rag/mm_image.py` — wired in table-region
  detection (table_blocks bbox pairing) and mask refinement (signatures/
  tampering).
- `services/ml-api/routers/rag/mm_video.py` — wired in mask refinement
  (signatures/tampering); table detection NOT wired here (no table-chunk
  path for video frames).
- `services/ml-api/requirements-base.txt` — added `timm>=1.0.0` (Table
  Transformer's ResNet backbone dependency; SAM needed no new dependency).

**Frontend:**
- `ml-portfolio/src/app/tools/multimodal-rag/_types.ts` — `DetectedObject`
  gained optional `mask?: [number, number][] | null`.
- `ml-portfolio/src/app/tools/multimodal-rag/IngestProgressRail.tsx` —
  inline SSE-payload mapping types extended to carry `mask` through for
  signatures/tampering.
- `ml-portfolio/src/app/tools/multimodal-rag/CitationThumbnailPanel.tsx` —
  `renderBoxes()` draws an SVG polygon instead of a rectangle whenever
  `mask` is present.

## Commit hashes

- Backend: `b0c203f` (Table Transformer), `7385a40` (SAM mask refinement).
- Frontend: (Table Transformer needed no frontend change — existing generic
  bbox-highlight path already covers it), `7018e4e` (SAM mask rendering).

All backend commits uploaded to the HF Space (`wram1708/ml-unified`) per
CLAUDE.md rule 4, each verified via stage=RUNNING + raw file diff + `/docs`
200 + a live end-to-end POST test before being reported as deployed.

## Pending / new items

- **Watermark-embedding half of deepfake detection** — not started; only
  the detection half exists. Would need an invisible-watermark embed step
  at upload/export time, not just detection at ingest.
- **Live-webcam surveillance/intrusion alerting** — object detection core
  exists; the "watch a webcam feed and alert on zone entry" wrapper
  doesn't. Architecturally different (persistent camera loop, no upload
  step) from everything else in this codebase.
- **Plate-specific ALPR pipeline** — OCR and vehicle-gating primitives
  exist; no dedicated plate-crop-then-OCR flow.
- **TTS narration for the Blind Assistant Audio Describer use case** —
  captioning exists; no text-to-speech output or live camera-snap workflow.
- **Genuinely new-territory ideas, none started, no commitment made**:
  Local Text-to-Image/Video Generator, Automated Social Reels Creator, AI
  Image Inpainting & Object Remover, Gesture-Controlled Desktop System,
  Automated Medical Scan Analyzer, Real-time Sign Language Translator.
  Recommended (but not decided) that Inpainting is the most synergistic
  next candidate given the SAM masks now available, and that it would fold
  into Multimodal RAG rather than become a new tool, per the "needs an
  upload step" split described above. Awaiting the user's direction on
  whether/which to pursue.
- The CV backlog itself (items 0-5) is now fully closed — no open items
  remain there.

## Update — Image Inpainting & Object Remover built (post-session)

Inpainting was subsequently built (folded into Multimodal RAG per the
recommendation above), backed by a plain white fill rather than a
content-aware model — LaMa's first-pass result was visibly blurry/smeared
on a live test, so it was replaced with a flat white fill per direction,
dropping the ~200MB model dependency entirely. Ships with a "Remove"
button on any detected region (object/face/signature/tampering), multi-
region removal (chained, not overwritten), and correct box/text-list
hiding once a region is covered by one or more removals (checked against
the union of all removed regions, not each individually).

Updated pending list for this feature and beyond:

- **Freehand mask drawing** — draw-your-own-region instead of only picking
  a detected box.
- **Persisting the inpainted result** — currently a disposable preview,
  resets on citation change.
- **PDF/mixed-content citations** — inpainting currently only works on
  standalone image/video uploads, not a PDF's embedded photo.

Beyond that, from the earlier invention-brainstorm mapping, still
undecided/not started:

- **Partial-coverage extensions**: watermark embedding, live-webcam
  surveillance, plate-specific ALPR, TTS narration.
- **Genuinely new territory**: Text-to-Image Generator, Social Reels
  Creator, Gesture-Controlled Desktop, Medical Scan Analyzer, Sign
  Language Translator (all would be separate standalone tools, not folded
  into Multimodal RAG).
