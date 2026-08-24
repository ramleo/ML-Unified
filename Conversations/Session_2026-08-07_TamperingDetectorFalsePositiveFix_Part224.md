# Session 2026-08-07 — Tampering Detector False-Positive Fix (Part 224)

Continuation of Part 223 (ELA + noise-residual tampering detection build). This session was
entirely about a live-caught false-positive bug in that feature, and the multi-round debugging
that led to the actual fix.

## The bug report

User uploaded a real, unedited bicycle photo (blurred bokeh background, sharp foreground) and
the "Check for tampering (5)" dropdown showed 5 regions at 72-95% confidence, all sitting on the
bike's spokes and frame edges. Two complaints:
1. "it says tempering, i thought the image was original one without tempering" — false positive.
2. Labels overlapping each other on screen.

## Round 1 — noise-residual local-neighborhood fix (turned out insufficient alone)

Initial hypothesis: `detect_noise_regions()` (`mm_noise_forensics.py`) compares each 16x16 block
against the WHOLE image's mean/std noise level. A real photo's depth-of-field blur (sharp
foreground vs. blurred background) creates large, gradual variation that looks like "outliers"
globally even though nothing was edited.

Fix: compare each block against a box-blurred LOCAL average instead of the global mean (high-pass
filter on the block-energy map). Raised `_OUTLIER_STD` 2.0 -> 3.0 -> 3.5, added `_MIN_CONFIDENCE`
floor.

Verified via synthetic tests: gradual blur-gradient false positives dropped from many to 2-3
(residual boundary-effect noise); a synthetic sharp-foreground/high-texture-background photo
(closer to real bokeh) returned 0 false positives; a genuine spliced flat patch still detected at
full confidence.

Also fixed the label-overlap complaint in `CitationThumbnailPanel.tsx`: shortened tampering box
labels from "Tampering (NN%)" to just "NN%" (the panel/dropdown already say "tampering"), and
widened the label-collision check to catch boxes close horizontally, not just diagonally.

Deployed (backend commit `c09aed2`, frontend commit `b568e1b`), verified live via HF Space
stage=RUNNING + raw file content check + `/docs` 200.

## User re-tested — same exact 5 detections, same confidences

User uploaded again (cache cleared) — IDENTICAL confidences (74/72/89/74/95) came back. This was
the key diagnostic signal: byte-identical output across "different" uploads meant either (a)
backend was skipping recompute for a cached/duplicate source, or (b) the detections were actually
coming from a DIFFERENT, unpatched code path.

Checked `mm_ingest.py`: multimodal ingest sources always get a UUID suffix
(`f"user:{filename}:{_uuid.uuid4().hex[:8]}"`), ruling out dedup/caching.

Direct backend test with a synthetic bike-spoke-like image confirmed: **ELA (`mm_tampering.py`'s
`detect_tampering()`) was firing on the spokes, not noise-residual** (which correctly returned 0
after the Round 1 fix). ELA had never been touched by the Round 1 fix — it has the identical
underlying flaw via a different mechanism: JPEG quantization/compression error concentrates at
real high-frequency content (spokes, thin edges) the same way tampering-induced error does.

## Round 2 — three failed heuristic fixes for ELA (all tested and rejected)

**Attempt A — local-neighborhood normalization for ELA** (mirroring the noise-residual fix):
did NOT suppress the spoke false positive (49 detections on the synthetic spoke-JPEG test,
actually worse) though it did preserve genuine-tamper detection.

**Attempt B — Sobel edge-density guard** (skip blocks whose original-image edge magnitude was
unusually high, reasoning real fine detail has high edge density but tampering doesn't): fixed
the spoke false positive (0 detections) but broke real detection — tested against a genuine
spliced NOISY patch (not a flat patch, which was a flawed earlier test since flat patches have
near-zero JPEG error either way) and the edge guard suppressed it entirely (empty result) where
the pre-guard code correctly found it at 100% confidence, near-exact bbox match. Root cause: a
genuinely spliced/noisy patch is ALSO high-edge-density by nature (the whole point of a splice is
it doesn't match its surroundings), so edge density can't discriminate the two cases.

Also tested this same edge-guard on noise-residual's already-shipped code with a noisy (not flat)
spliced patch — it happened to NOT regress there (still found it at 100% confidence). Inconsistent
behavior across the two detectors confirmed the heuristic is not a reliable discriminator, just
sometimes-lucky.

**Attempt C — connected-component solidity/shape filter** (reject thin elongated regions —
spokes are line-like/low-fill-ratio, real edits are blob-like/high-fill-ratio): tested with
`_MIN_SOLIDITY = 0.55` — did NOT fix the spoke false positive (13 detections still passed) AND
wiped out the genuine-tamper test case entirely (0 detections, down from 1 real hit). Worse on
both axes.

## Round 2 resolution — require cross-detector agreement, drop solo ELA hits

Conclusion after three failed attempts: no cheap per-block heuristic reliably separates "busy real
photo" from "tampered region" for ELA alone — this is a known-hard problem in image forensics
(why real tools use PRNU sensor fingerprinting or trained models, not simple heuristics).

Final fix in `combine_tampering_detections()` (`mm_tampering.py`): a solo ELA hit — no
noise-residual agreement on roughly the same region (IoU >= 0.3) — is now **dropped entirely**,
not discounted at any confidence. Only two cases surface a detection:
1. ELA + noise-residual agree (IoU >= 0.3) — confidence-boosted, merged bbox.
2. Noise-residual alone — kept at full strength, since it's the only signal on non-JPEG uploads
   and has its own (tested, working) local-neighborhood + edge-density guard against this same
   fine-detail confound.

Removed the now-dead `_ELA_NONJPEG_DISCOUNT` constant and `source_is_jpeg` parameter from
`combine_tampering_detections()` (unused once solo ELA hits are dropped regardless of source
format) — updated call sites in `mm_image.py` (also removed the now-unused `source_is_jpeg`
sniffing computation) and `mm_video.py`.

Verified against the user's ACTUAL bicycle.jpeg file (found via `find` on the local filesystem,
not just a synthetic approximation):
- Local direct-function test: ELA still fires 5 false regions (72-95% confidence, unchanged
  behavior — the underlying flaw is real and reproducible), noise-residual finds 0, merge policy
  correctly drops all 5 -> final result 0.
- Live end-to-end test: POSTed the real bicycle.jpeg to the deployed HF Space's
  `/rag/mm-ingest` endpoint directly (`curl -X POST ... -F "file=@bicycle.jpeg"`), parsed the SSE
  response's `notable_chunks`, confirmed `"tampering": null` in the actual production response —
  not just a local unit test claim.

Deployed (backend commit `1f63935`), verified live via HF Space stage=RUNNING + raw file content
check (`grep` for the new `combine_tampering_detections` signature with no `source_is_jpeg` param)
+ `/docs` 200.

## Known accepted tradeoff — discussed explicitly with user

The "require agreement" policy is precision-favoring, not free: it will now MISS some genuinely
subtle edits, especially on already-compressed JPEGs where noise-residual is itself less sensitive
(JPEG compression already damps the fine noise texture noise-residual looks for). Confirmed via a
synthetic test: a real spliced noisy patch on a heavily JPEG-recompressed image was caught by ELA
alone (1 region) but noise-residual found nothing to corroborate, so the current policy drops it.

Presented two options for improving recall later if desired:
1. Let very-high-confidence solo ELA hits through with an explicit "unconfirmed, single-signal"
   label instead of full removal — flagged as low-value since the bicycle false positives were
   themselves in the 72-95% range, right where a "very high confidence" cutoff would need to sit.
2. Build a genuinely different third signal: JPEG "double-compression"/quantization analysis
   ("JPEG ghosts") — examines DCT coefficient statistics in the frequency domain to find a region
   compressed at a different quality/generation than the rest of the photo. Less confusable with
   real fine detail than ELA/noise-residual since it doesn't read raw pixel busy-ness. This is the
   standard professional forensic technique for exactly this gap.

**User's decision**: declined to build option 2 now ("no"), but explicitly asked to remember it
for future optimization ("but keep it in mind, we may optimize this in future"). Saved as a
project memory (`project_tampering_detector_precision.md`) documenting the current tradeoff, why
the three heuristic attempts failed (with enough detail to avoid re-trying the same dead ends),
and the JPEG-ghost analysis as the recommended next lever, including the same testing discipline
(synthetic false-positive + synthetic true-positive test) that caught the previous two failures
before they shipped.

## Files touched this session

**Backend:**
- `services/ml-api/routers/rag/mm_noise_forensics.py` — local-neighborhood normalization
  (`_LOCAL_SMOOTH`, `local_avg`/`local_dev`), raised `_OUTLIER_STD` to 3.5, `_MIN_CONFIDENCE`
  floor, Sobel edge-density guard (`_EDGE_GUARD_STD`) — this detector's guard DID test clean and
  stayed shipped, unlike ELA's.
- `services/ml-api/routers/rag/mm_tampering.py` — local-neighborhood normalization added then
  kept (harmless); edge-density guard added then REVERTED (broke true positives); merge policy
  changed to drop solo ELA hits entirely; removed `_ELA_NONJPEG_DISCOUNT` and `source_is_jpeg`
  param.
- `services/ml-api/routers/rag/mm_image.py` — removed now-unused `source_is_jpeg` raw-byte
  sniffing; updated `combine_tampering_detections()` call site.
- `services/ml-api/routers/rag/mm_video.py` — updated `combine_tampering_detections()` call site.

**Frontend:**
- `ml-portfolio/src/app/tools/multimodal-rag/CitationThumbnailPanel.tsx` — shortened tampering
  box labels to just percentage; widened label-collision/stacking check to catch horizontal
  crowding.

## Commit hashes

- Backend: `c09aed2` (noise-residual local-neighborhood fix), `48fd71b` (noise-residual
  edge-density guard, kept), `1f63935` (drop solo ELA hits — final fix).
- Frontend: `b568e1b` (shortened labels, wider stacking check).

All backend commits uploaded to the HF Space (`wram1708/ml-unified`) per CLAUDE.md rule 4, each
verified via stage=RUNNING + raw file diff + `/docs` 200 before being reported as deployed.

## Pending / deferred

- JPEG "double-compression"/quantization ("JPEG ghosts") analysis as a third tampering signal —
  explicitly deferred by the user for future optimization, not rejected. See
  `project_tampering_detector_precision.md` for the recommended approach and required testing
  discipline before it's built.
- All other backlog items (3-5: perceptual-hash duplicate detection, Table Transformer, Segment
  Anything) and the genuine/forged signature verification decision — untouched, not re-raised
  this session.
