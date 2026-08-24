# Session 2026-08-08 — Image Inpainting & Object Remover (Part 226)

Continuation of Part 225 (CV backlog complete, invention-brainstorm mapping done, Inpainting
recommended as the next candidate). This session built it.

## What was built

**"proceed with Inpainting"** — explicit authorization to build the recommended next feature.
Entered plan mode given real architectural decisions (model choice, region-selection UX, file
size). Plan approved after trimming stale leftover content from an old plan file (the item-0
dropdown-consolidation plan, already long complete, was still sitting in the plan file from an
earlier session and had to be removed rather than left as confusing dead content).

**Backend — `services/ml-api/routers/rag/mm_inpaint.py`** (new): `POST /rag/mm-inpaint`. Takes a
citation's page/frame image plus a detection's `bbox` (and `mask` if present, e.g. from SAM-refined
signature/tampering detections) and covers that region. Reuses whatever region data already exists
— no new region-selection UI. Registered in `app.py`.

**Model choice — LaMa, then reverted to plain white fill.** First version used LaMa (Large Mask
Inpainting) via `simple-lama-inpainting` (~200MB, CPU-fast, matching the project's "smallest
specialized model" pattern from dHash/Table Transformer/SlimSAM). Verified locally and live via
direct curl (red rectangle removed, blended fill). Live UI test on a real face photo showed the
result was a blurry, smeared patch — poor visual quality. Per explicit user direction, replaced
with a flat **plain white fill** instead. This simplified the endpoint significantly: no model to
load at all, no lazy-load step (unlike every other `mm_*.py` module), and dropped the
`simple-lama-inpainting` dependency from `requirements-base.txt` entirely.

**Frontend — `useInpaint.ts`** (new hook) + **`CitationThumbnailPanel.tsx`** (modified): a "✕"
button in each detection box's corner (image/video-only mode only) calls the endpoint with that
detection's bbox/mask; the citation's displayed image swaps to the result; a "Reset" button next to
the action dropdown restores the original.

## Three real bugs found via live testing, not assumed away

1. **Multi-region removal overwrote instead of stacking.** Each click sent the *original* image, so
   removing a second object undid the first. Fixed: `useInpaint` now chains each new removal onto
   `resultImg ?? imageB64` — the already-edited image if one exists.

2. **Removing a larger region left contained sub-detections' boxes still showing** (e.g. removing
   the whole "Bicycle" box left "Bicycle wheel" boxes pointing at now-blank white space, still
   clickable). Fixed: track every removed bbox (`removedBboxes`), compute per-detection coverage,
   hide any box that's now mostly covered.

3. **A region split across two separate removals never got hidden** (e.g. a "Fish" detection
   overlapping two different "Goldfish" boxes — removing each goldfish individually never covered
   60%+ of the Fish box alone, even though together they fully covered it). Fixed: switched from
   per-box overlap checking to **point-sampled coverage against the union** of all removed boxes
   (8x8 grid, ≥60% covered = hidden). Verified live: removing both goldfish correctly hides the Fish
   box, where the naive per-box check did not.

## A fourth issue found on a deliberate re-check ("check properly")

When asked to verify thoroughly rather than just recite status, re-reading the full file (not just
the diffs) surfaced that the **text lists below the image** (the "Detect objects" list, the
tampering list) were never filtered by the same `isCovered` check the box overlay used — so a
removed detection's box disappeared but it kept showing in the text list underneath. Fixed both
lists. Also found `CitationThumbnailPanel.tsx` had crept up to exactly 400 lines (the project's
hard cap) — split the whole fixed-height results block out into a new `CitationResultsPanel.tsx`
(328 + 102 lines) rather than leave it sitting at the limit.

## Deploy/verification discipline

Every change (3 backend, 4 frontend rounds) was deployed and verified live before being reported
done — HF Space stage=RUNNING, raw file diff against the deployed source, `/docs` 200, then either a
direct curl POST proving real pixel behavior, or a Playwright pass on the live portfolio URL. One
false-negative caught along the way: a Playwright retest right after a push showed the OLD
(pre-fix) behavior — traced to the browser having a stale cached JS bundle rather than the fix
being broken; confirmed by diffing the actual deployed bundle content before/after, then re-tested
fresh and got the correct result. Didn't take the first (wrong) result at face value.

## Commit hashes

- Backend (`ML-Unified`): `fd76af6` (LaMa version), `ac0524e` (reverted to plain white fill).
- Frontend (`ml-portfolio`): `fd0a8d8` (initial build), `a296630` (chaining fix), `956d63c`
  (containment fix), `e88831b` (union-coverage fix), `7b161a2` (text-list filter fix + component
  split).

All backend commits uploaded to the HF Space (`wram1708/ml-unified`) per CLAUDE.md rule 4.

## Other work this session

- Created `images/` folder at the `ML-Unified` project root and moved all 92 top-level `.png` files
  into it (left `.venv` dependency assets and `.playwright-mcp` test-artifact screenshots
  untouched — not project files).
- Appended the current pending-items text verbatim to Part 225's log (it was written before
  Inpainting existed, so didn't yet reflect it).

## Pending / not started

Nothing in progress. All 12 items await explicit direction.

On the Inpainting feature itself:

1. **Freehand mask drawing** — draw-your-own-region instead of only removing a detected box.
2. **Persisting the inpainted result** — currently a disposable preview, resets on citation change.
3. **PDF/mixed-content citations** — inpainting currently only works on standalone image/video
   uploads, not a PDF's embedded photo.

Partial-coverage extensions (something already exists, this would extend it):

4. **Watermark embedding** — deepfake *detection* exists, embedding doesn't.
5. **Live-webcam surveillance/intrusion alerting** — object detection core exists, the live-camera
   wrapper doesn't.
6. **Plate-specific ALPR** — OCR primitives exist, no dedicated plate-crop-then-OCR pipeline.
7. **TTS narration** for the audio-describer use case — captioning exists, no speech output.

Genuinely new territory (each would be a separate standalone tool, not folded into Multimodal RAG):

8. **Text-to-Image Generator**
9. **Social Reels Creator**
10. **Gesture-Controlled Desktop**
11. **Medical Scan Analyzer**
12. **Sign Language Translator**
