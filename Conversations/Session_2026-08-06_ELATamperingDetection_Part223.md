# Session 2026-08-06 — ELA + Noise-Residual Tampering Detection (Backlog Item 2) — Part 223

Continued from Part 222 (Evidence-height fix, Key facts/PII dropdown additions, signature
detection — backlog item 1). This session: backlog item 2 — tampering detection for
images/video frames, built in two passes (ELA first, then a format-agnostic noise-residual
detector merged in after user pushback on ELA's JPEG-only limitation).

## What was asked and why

User asked "what is ELA tampering detection" — answered with the mechanism (JPEG re-compression
diff), where it'd fit in the project (visual-actions dropdown, ties into the MMRAG-20
reconciliation/document-fraud angle), and the key caveat: **JPEG-only** — PNG/lossless originals
have no compression-decay artifact to exploit. User said "proceed."

## Part 1 — ELA tampering detection (JPEG-only)

### Backend

**`mm_tampering.py`** (new) — pure image processing, no ML model:
- Re-saves the image as JPEG at quality 90, diffs pixel-by-pixel against the original.
- Blockwise (8×8, JPEG's native grid) mean error, threshold at `mean + 2·std`.
- `cv2.connectedComponentsWithStats` → bounding boxes, NMS-free (components are already disjoint),
  capped at 5 detections, confidence normalized via `clip((region_err - mean) / (4·std), 0, 1)`.
- `describe_tampering()` bakes a caveat-carrying sentence into the stored chunk text (same
  groundedness-scoring rationale as `mm_objects.describe_objects`/`mm_signatures.describe_signatures`).

**File-length housekeeping**: `mm_video.py` was already at 389 lines (over CLAUDE.md's 350-line
modularize-first threshold) before this feature touched it. Per rule 3, split it via a Haiku
subagent *before* adding tampering wiring — audio/transcription/chaptering pipeline
(`_extract_audio_wav_to_file`, `_transcribe_long_audio`, `_transcribe_audio`,
`_chunk_segments_with_speakers`, `transcribe_video`, `generate_chapters`, and their constants)
moved to new `mm_video_audio.py` (238 lines), with `mm_video.py` re-exporting `transcribe_video`/
`generate_chapters` so no caller needed to change its import. Result: `mm_video.py` 389→157 lines,
comfortably under the cap even after the tampering wiring was added back in.

**Wired into `mm_image.py`/`mm_video.py`**: same `detect_tampering(b64)` → `describe_tampering()`
→ baked into caption + stored on the chunk pattern as objects/signatures. Threaded through
`ingest.py` (Chroma metadata, reusing `encode_objects`/`decode_objects` — shape-agnostic JSON
codec already built for signatures), `citations.py` (query-time citation response), and
`mm_ingest_payload.py` (ingest-time SSE `notable_chunks`, so it's available on the auto-shown
preview immediately, not just post-answer).

**Real bug caught during local smoke-testing** (not by the user — found before ever deploying):
`stats[i, cv2.CC_STAT_LEFT]` etc. are numpy `int32`, and multiplying/dividing them left numpy
scalar types (`np.float64`) inside the returned bbox list. This would have broken
`json.dumps()` in `ingest.py`'s `encode_objects()` the first time a real detection occurred —
caught via `json.dumps(regions)` in a local smoke test before it ever reached the deployed
backend. Fixed by wrapping the pixel-coordinate arithmetic in `int(...)` before it enters the
returned dict — verified with a re-run producing a clean JSON round-trip.

### Frontend

`_types.ts`, `EvidenceColumn.tsx`, `EvidencePanel.tsx`, `MmRagRunner.tsx`,
`DocumentSummaryPanel.tsx`, `IngestProgressRail.tsx`, `CitationThumbnailPanel.tsx` — `tampering`
field threaded through the exact same sibling-media-chunk-fallback / `jumpToCitation` param-chain
pattern established for `signatures`/`entities`/`piiTypes` across Parts 221–222. New
`TAMPERING_COLOR = "#f87171"` (red, distinct "warning" accent from face/object/signature colors),
new `"Check for tampering (N)"` dropdown option, reuses the existing `renderBoxes()` shared
helper, new result block showing the disclaimer sentence + per-region confidence list.

### Deploy + live verification

Backend commit `29412ef`, frontend commit `bcf51a8`. Uploaded 8 changed `.py` files to the HF
Space, polled `stage` until `RUNNING` (not just non-error), verified raw deployed file content
matched, confirmed `/docs` returned 200 (app actually serving, not just reporting RUNNING).

Live Playwright test: built a synthetic tampered invoice (JPEG-compressed background baked at
quality 40, then a freshly-pasted `$9,999.00` patch pasted over the real `$1,200.00` total,
final save at quality 95) — uploaded through the live portfolio page. Both spliced regions were
correctly detected and localized (89% and 97% confidence), boxes rendered exactly over the actual
edit, result block showed the disclaimer + per-region confidences as designed. Confirmed both via
a direct backend `curl` (to isolate backend-correct vs frontend-stale) and the rendered UI
screenshot.

## Part 2 — user pushback: "any other free alternatives which are good and can work on other file
types other than jpeg?"

User pasted a researched list of forensic tools/techniques (Forensically, JPEGsnoop, ExifTool,
reverse image search). Assessed each on actual buildability, not just conceptual soundness:

- **Forensically** — web-only tool, no API/library; not embeddable.
- **JPEGsnoop** — Windows-only desktop GUI, no CLI/bindings; doesn't run on the Linux HF Space
  regardless of its claimed format list (which is really about extracting embedded JPEG
  thumbnails from RAW/PDF/AVI containers, not analyzing PNG pixels directly).
- **ExifTool** — genuinely usable (real CLI/Python-wrappable, cross-platform) but low value here:
  the pipeline already re-saves every upload through PIL as PNG at ingest, which strips the
  metadata this technique depends on.
- **Reverse image search (Yandex/TinEye)** — real capability but a different privacy posture
  (shipping user images to a third party) than anything else in the tool; flagged as needing
  explicit opt-in, not something to add silently.
- **Noise-residual / clone-detection** — identified as the one genuinely portable, buildable
  technique: format-agnostic (operates on decoded pixels, not a compression artifact), reuses the
  exact blockwise-threshold/connected-components/NMS pattern already built for ELA.

User corrected an initial framing slip ("PNG-capable" — pushed back "its not only about png"):
noise-residual isn't PNG-specific, it's genuinely format-agnostic (WebP, BMP, TIFF, re-saved
JPEGs too) since it never depends on a compression artifact at all — corrected in the next reply.

User then asked three sequential clarifying questions before authorizing build: "what do you
suggest?" (separate dropdown option vs merged into one) → recommended merging, since a user
asking "was this edited" shouldn't have to understand the difference between two forensic
techniques to pick the right menu option, and two independent signals agreeing is stronger
evidence than either alone. "how it will work?" → walked through the 4-step noise-residual
pipeline and the IoU-based merge mechanism. "how will you handle this - 'One tradeoff worth
naming:'?" (the PNG-source-makes-ELA-noisier tradeoff flagged in the recommendation) → designed
the concrete discount mechanism: sniff `source_is_jpeg` from raw upload bytes before the PNG
re-encode, apply a discount multiplier only to ELA-only (non-agreed) detections when the source
wasn't actually JPEG, never discount noise-residual or agreed-upon detections. User said "yes."

## Part 2 build

**`mm_noise_forensics.py`** (new, 91 lines) — `detect_noise_regions(b64)`: grayscale →
`cv2.fastNlMeansDenoising` → absolute residual → blockwise (16×16, coarser than ELA's 8×8 since
noise-variance estimates need more samples per block to be stable) mean energy → outlier blocks
in *either* direction (`|block_energy - mean| > 2·std`) flagged, since a spliced region can be
either suspiciously smoother (denoised/regenerated) or suspiciously grainier (mismatched sensor
source) than its surroundings. Same connected-components → NMS → confidence-normalize →
`{label, confidence, bbox}` output contract as `detect_tampering`, so nothing downstream needs to
know which detector produced a given region.

**`mm_tampering.py`** — added `combine_tampering_detections(ela_regions, noise_regions,
source_is_jpeg)`:
- IoU (`_iou_xywh`, threshold 0.3) match between the two detectors' region lists.
- Overlapping pairs → confidence boosted via `1 - (1-c1)(1-c2)` (two independent ~70% signals
  combine to ~91%, not just averaged), bbox unioned, never discounted regardless of source format.
- ELA-only regions (no noise-residual overlap) → discounted ×0.6 when `source_is_jpeg` is
  `False`, since ELA's "this was previously JPEG-compressed" assumption doesn't hold there —
  still surfaced as a weaker hint, not dropped.
- Noise-residual-only regions → never discounted (format-agnostic by construction).
- `describe_tampering()`'s wording generalized from "elevated JPEG compression error" to
  "signs of possible editing," since the caller no longer knows (or needs to know) which
  detector(s) actually fired.

**Wired into `mm_image.py`**: sniffs `file_bytes.startswith(b"\xff\xd8\xff")` *before* the
PIL-decode-then-PNG-re-encode step (which would otherwise destroy that information), passes the
result through to `combine_tampering_detections`. **`mm_video.py`**: `source_is_jpeg` is
unconditionally `False`, since every extracted video frame is freshly `cv2.imencode(".png", ...)`
— structurally never JPEG-sourced.

### Verification

Local smoke tests on PIL-drawn synthetic images initially showed the noise-residual detector
returning 0 regions in every case — investigated rather than assumed correct, and confirmed it
was a bad-testbed artifact, not a bug: computer-drawn synthetic images have zero real sensor
noise anywhere, so there's nothing for a noise-*mismatch* detector to find. Verified the detector
actually works with a realistic test (Gaussian noise injected across a synthetic base image,
then a perfectly smooth/denoised patch pasted in) — correctly flagged the patch at 92.6%
confidence, bbox matching the pasted region. Confirmed the merge/discount logic behaves as
designed across three cases: JPEG-sourced tampered image (full-confidence ELA hits), PNG-sourced
tampered image (same region, confidence roughly halved by the 0.6 discount), and a clean
untampered PNG (one legitimate ELA false-positive on a high-contrast text/edge region — the
documented, disclosed caveat, not a bug).

Deployed: backend commit `c63ff5f`, uploaded 4 changed files to the HF Space, verified
RUNNING + raw content + `/docs` 200. Live-tested the specific case that previously had zero
coverage — a PNG-only tampered image — via both a direct backend `curl` (0.936 confidence,
correct bbox) and a live Playwright pass on the deployed frontend, confirming the
"Check for tampering (1)" dropdown option appears and the box renders correctly (94% shown in
UI, matches backend within rounding).

**One more real gap caught during this live verification** (not by the user): the frontend's
hardcoded result-block text still read "elevated JPEG compression error, not a certainty" —
accurate for Part 1 (ELA-only) but now misleading, since a detection could equally have come from
the noise-residual detector alone. Fixed to the same detector-agnostic wording the backend's
`describe_tampering()` already uses ("signs of possible editing, not a certainty"). Frontend
commit `0d4c8fe`.

## Files touched this session

**Backend (ML-Unified)**:
- `services/ml-api/routers/rag/mm_tampering.py` (new, then extended with merge logic)
- `services/ml-api/routers/rag/mm_noise_forensics.py` (new)
- `services/ml-api/routers/rag/mm_video_audio.py` (new — split out of mm_video.py)
- `services/ml-api/routers/rag/mm_image.py`, `mm_video.py` (modified twice — ELA wiring, then
  noise-residual + merge wiring)
- `services/ml-api/routers/rag/ingest.py`, `citations.py`, `mm_ingest_payload.py` (modified —
  `tampering` field threaded through Chroma metadata / query-time citations / ingest-time SSE)
- `services/ml-api/routers/rag/mm_ingest.py` (comment-only, from the mm_video.py split)

**Frontend (ml-portfolio)**:
- `src/app/tools/multimodal-rag/_types.ts`, `EvidenceColumn.tsx`, `EvidencePanel.tsx`,
  `MmRagRunner.tsx`, `DocumentSummaryPanel.tsx`, `IngestProgressRail.tsx`,
  `CitationThumbnailPanel.tsx` (modified — `tampering` field threading, dropdown option, box
  render, result block; wording fix in a follow-up commit)

## Commits

- Backend: `29412ef` (ELA tampering, mm_video.py split), `c63ff5f` (noise-residual + merge)
- Frontend: `bcf51a8` (ELA dropdown wiring), `0d4c8fe` (detector-agnostic wording fix)

## Pending / not started

- Backlog items 3–5 (perceptual-hash near-duplicate detection, Table Transformer, Segment
  Anything) — not re-raised this session.
- Genuine/forged signature verification (from Part 222) — still explicitly recommended against,
  no user decision made either way.
- Clone/copy-move detection (block-matching or ORB-keypoint duplicated-region finder) — named as
  the other legitimately buildable forensic technique during the tool-comparison discussion, not
  built or requested.
