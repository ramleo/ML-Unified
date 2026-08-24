# Session 2026-08-09 — PDF Citation Editing + JPEG Ghost Detection (Part 229)

Continuation of Part 228 (AI-fill polish, Gemini model switch, tampering UI fixes). This
session picked up the pending-items list, worked through PDF/mixed-content citation editing
support (item 1) end-to-end including a real bug found and fixed live, then built and shipped
JPEG ghost double-compression detection (item 10) as a new third tampering signal.

## Pending-items list audit

User asked "what next?" then "check documents from Part224.md and tell me pending items" —
initial confusion since Part 224 (`TamperingDetectorFalsePositiveFix`) is a different session
than what the user seemed to expect (only 2-5 pending items there: JPEG ghosts, signature
verification decision, three CV-backlog refs already resolved by Part 225). User then
clarified they meant the fuller Part 228 carryover list (11 items) plus the 2 from Part 224 —
combined into a 13-item list. User then corrected one item: **Cloudflare Workers AI** was
never actually a pending task — it was a researched-and-abandoned lead from the AI-fill
free-alternative search, dropped once paid Gemini worked out. Final 12-item pending list:

1. PDF/mixed-content citation editing (inpainting/add-content)
2. Watermark embedding
3. Live-webcam surveillance
4. Plate-specific ALPR
5. TTS narration
6-10. Five standalone-tool ideas (Text-to-Image Generator, Social Reels Creator,
   Gesture-Controlled Desktop, Medical Scan Analyzer, Sign Language Translator)
11. JPEG ghost double-compression tampering signal
12. Genuine/forged signature verification decision

User: "proceed with 1".

## Item 1 — PDF/mixed-content citation editing

**Root gap found**: the entire Object Remover/AI-fill/add-content toolbar in
`CitationThumbnailPanel.tsx` was gated behind `isImageOrVideoOnly` (standalone image/video
uploads only) even though `useInpaint.ts` and the backend (`/rag/mm-inpaint`, `/rag/mm-ai-fill`)
are fully generic over file type — they just take a page image + bbox in, an edited image out.
PDF page citations could never use draw-region, remove, download, reset, or add-content at all.

**Fix**: introduced a `canEdit` flag (true whenever a valid page image exists — effectively
always, given the render guard above it) and replaced the relevant `isImageOrVideoOnly &&`
gates with it, leaving the separate detection-dropdown-vs-simple-buttons split
(`isImageOrVideoOnly`) untouched since that's a different concern (out of scope for this item).

**File-length modularization**: the edit pushed `CitationThumbnailPanel.tsx` to 402 lines
(over the 400 cap). Extracted the `renderBoxes` closure into a new `DetectionBoxOverlay.tsx`
component (props: list, color, labelFor, allowRemove, canEdit, inpainting, isCovered,
runInpaint), bringing the panel back to ~340 lines.

### The real bug — investigated live, found by reading code, not more guessing

Initial Playwright testing against a real `test_invoice.pdf` showed: draw-region, remove,
download, and reset all worked correctly on a PDF citation (verified via network capture +
direct decode of the backend's returned image — a full, correct invoice). But after using the
"+" add-content control to add text ("$9.00") into a removed region, the citation image
rendered as **solid blank white** in every screenshot — reproducible 100% of the time.

**False leads chased first** (this is where the user's patience ran out — "why are you
guessing?", "bhenchod time waste bandh kar" — both fair calls-out):
- Assumed it was a canvas `toDataURL()` paint/compositing bug. Verified via direct extraction
  and decode of the live DOM `<img>`'s `src` attribute (twice, before/after) that the
  underlying image data was ALWAYS correct — full invoice + added text, decoded cleanly with
  Python/PIL every time. Also reproduced `compositeOntoImage`'s exact logic in an isolated
  HTML page and it rendered correctly there.
- Tried a `key`-based React remount fix (add a `version` counter to `useInpaint`, bump on every
  edit, use `key={editKey-version}` on the `<img>`) reasoning it was a stale in-place `src`
  mutation not repainting. Confirmed via DOM ref change that the remount WAS happening — but
  the screen was STILL blank. This ruled out the remount theory entirely.
- User rejected a further blind `elementsFromPoint` poking attempt outright and told me to stop
  wasting time; correctly called out that repeated live-browser trial-and-error without reading
  the actual layout code was the wrong approach.

**Actual root cause** (found by reading `CitationThumbnailPanel.tsx`'s layout directly, not by
more browser interaction): the add-content editor bar (`AddContentControls.tsx`) was rendered
`absolute left-0 right-0 bottom-0` **inside the full, unclipped tall image wrapper** (1123px
for this invoice), not the 460px-`maxHeight` scrollable viewport around it. Focusing its text
input made the browser auto-scroll the container down to reveal the bar — landing on genuinely
blank whitespace in the lower ~370px of a page whose real printed content only occupies the top
~750px. Not a paint bug or data bug at all — a scroll-position bug. This also explained why the
underlying image data always checked out correct: it was never actually corrupted, just scrolled
out of view.

**Real fix**: anchored the editor panel to the CLICKED region's own bbox (same coordinate the
"+" button itself uses) instead of the bottom of the full tall image — `position: absolute`,
`left`/`top` from `activeBbox`, `transform: translate(-50%, calc(-100% - 8px))` to float just
above the clicked point, `width: 220px` capped to the container. Since the clicked region is by
definition already on screen, this needs no scroll at all, ever. Re-verified live end-to-end:
drew a region, removed it, opened "+", typed "$9.00", clicked Add — the invoice rendered
correctly with the new text visibly composited in, confirmed via real screenshot (not just data
decode) this time.

Also had to first defensively scope the add-content control back to `isImageOrVideoOnly` only
(hiding it for PDFs) once the bug was confirmed real and unsolved, per user pushback about
shipping something broken — then re-enabled it for all citation types (`canEdit`) once the
actual fix landed and was verified.

### Files touched (ml-portfolio repo)

- `CitationThumbnailPanel.tsx` — `canEdit` flag replacing `isImageOrVideoOnly` for the editing
  toolbar; `renderBoxes` extracted to `DetectionBoxOverlay.tsx`; `<img>` given a `key` tied to
  `useInpaint`'s new `version` counter.
- `useInpaint.ts` — new `version` state, bumped on every `persist()`/`reset()`, exposed in the
  hook's return value.
- `AddContentControls.tsx` — editor panel repositioned from `absolute bottom-0` (full tall
  image) to anchored at the clicked region's own bbox.
- `DetectionBoxOverlay.tsx` (new) — extracted shared detected-box+label overlay renderer.

### Commit and deploy

Committed `0bfc2b0` (ml-portfolio repo, frontend-only, no HF Space upload needed), pushed to
`origin main`. Browser closed per explicit instruction after.

## Item 10 — JPEG ghost double-compression tampering detection

User asked "what is the purpose of 10?" first — explained in plain terms: the existing
ELA+noise-residual precision fix (from Part 224) requires both signals to agree before
flagging tampering, which fixed false positives but has a real cost — on an already-recompressed
JPEG, noise-residual's signal gets damped by the compression itself, so a genuinely spliced
region with no noise-residual corroboration gets silently dropped regardless of ELA confidence.
JPEG ghost analysis is a third, independent signal that looks at compression history (which
JPEG quality a block's DCT data actually matches) rather than raw pixel noise, so it isn't
confused by busy real detail the way ELA and (to a lesser extent) noise-residual are.

### Implementation — two iterations, tested before shipping either

**First attempt (failed, caught before shipping)**: naive per-block "which candidate quality
minimizes re-compression error" trivially picks the image's OWN current/last-save quality
almost everywhere (re-quantizing already-quantized DCT coefficients through the same table
loses almost nothing, regardless of a block's true origin) — this swamps any real ghost signal.
Verified via a synthetic true-positive test (a quality-60 patch spliced into a quality-90 base,
whole composite resaved at quality-85): zero detections, confirmed via debug output that
`best_q_idx` was uniformly the current save quality everywhere.

**Working fix**: for each quality level, compute the image-WIDE average diff curve first (the
"global curve", dominated by the majority single-generation content), then subtract it from
each block's own per-quality diff curve before taking the minimum. A block from the same
generation as most of the image stays near zero after this subtraction at every quality; a
block from a different original quality shows a pronounced negative dip, since it fits that
quality distinctly better than the image's typical block does. Verified: the synthetic splice's
true region produced a z-score of ~8.8 against the rest of the image's own population — a
large, clean separation.

**Testing discipline** (explicit purpose was to avoid repeating the three failed heuristic
attempts from Part 224's ELA precision work):
- 3 separate synthetic false-positive tests before wiring anything in: uniform-noise busy JPEG,
  sharp-vs-smooth-quadrant JPEG, mixed-content JPEG — all single-generation, no splice, all
  correctly returned zero detections.
- Synthetic true-positive splice test (quality-60 patch in quality-90 base, resaved at
  quality-85) — correctly localized (detected bbox `[0.325, 0.333, 0.225, 0.233]` vs expected
  `[0.312, 0.312, 0.25, 0.25]`, good overlap), confidence came out modest (0.085, since the
  z-score of the region gets diluted when computed against a population that includes the
  outlier region itself — same self-inclusive-statistics effect the other two detectors also
  have, not a new problem).
- Full three-signal regression test: on the same splice, ELA fired 5 spurious regions (correctly
  dropped, no corroboration), noise-residual found 0 (correctly silent — the exact gap this
  detector exists to fill), ghost alone correctly surfaced the real region. Same busy single-gen
  false-positive image re-tested through the full merged pipeline: 0 regions, confirming no
  regression.

### Merge policy — `combine_tampering_detections` extended to three signals

New `_merge_one()` helper for pairwise IoU-match-and-boost, reused across all combinations.
Policy: ELA-only regions still dropped (unchanged — proven confusable with real fine detail,
no reliable per-block heuristic exists per Part 224's three failed attempts). Noise-residual-
only AND jpeg-ghost-only regions are BOTH now kept solo, since ghost was specifically tested
(3 false-positive scenarios) to confirm it doesn't share ELA's confound before being trusted
this way — this was the whole point of adding it, to recover the recall the noise-residual
requirement was costing on recompressed JPEGs.

### Files touched (ML-Unified repo, backend)

- `mm_jpeg_ghost.py` (new) — `detect_jpeg_ghosts()`, same `{label, confidence, bbox}` contract
  as the other two detectors.
- `mm_tampering.py` — `combine_tampering_detections()` extended to a third optional
  `ghost_regions` param; new `_merge_one()` helper; module + function docstrings updated.
- `mm_image.py`, `mm_video.py` — wired `detect_jpeg_ghosts(b64)` into both ingest call sites.

All files well under the 400-line cap (240/127/185/184 lines respectively).

### Commit, deploy, and live verification

Committed `fe7d325` (ML-Unified repo), pushed to `origin main`. Uploaded all 4 changed `.py`
files to the HF Space (`wram1708/ml-unified`) per CLAUDE.md rule 4. Polled build status through
`RUNNING_BUILDING` → `RUNNING_APP_STARTING` → `RUNNING` (~3 min). Verified the new code was
actually serving via raw file content check (`ghost_regions` param present in the live
`mm_tampering.py`) and `/docs` returning 200. Final verification: POSTed the exact synthetic
splice test image directly to the LIVE production `/rag/mm-ingest` endpoint (not just a local
unit test) — got back the identical detection (confidence 0.085, same bbox) with SAM mask
refinement layered on top, confirming the full deployed pipeline works end-to-end.

## Incidents / feedback this session

- **Sharp user correction on live-testing rigor**: after the first "blank screenshot" showed up,
  I initially treated it as solved based on decoded-data checks alone and told the user it was
  fine (a Playwright screenshot artifact). User pushed back hard ("it didnt work isnt it?"),
  correctly pointing out that DOM data being correct doesn't prove real users see anything
  different from what the screenshots showed. This was the right call — re-investigation found
  a real, reproducible bug (the scroll-to-blank-area issue) that the "it's just my test tooling"
  conclusion had wrongly dismissed. Lesson reinforced: a screenshot-based negative result
  deserves the same "verify, don't assume" treatment as a positive one.
- **User anger at continued live-poking without reading code first**: after the remount fix
  also failed to resolve the blank-screen bug, I kept trying further ad-hoc Playwright/DOM
  introspection calls instead of stepping back to read `CitationThumbnailPanel.tsx`'s actual
  layout. User explicitly rejected a tool call and said to stop wasting time. Correctly
  course-corrected: read the component's JSX/CSS directly, found the actual bug (bottom-anchored
  panel inside an unclipped tall container) within one file read, fixed it, and verified once —
  no further blind trial-and-error needed after that.

## User guide update

After both features shipped, user asked to "update user guide." Audited the two guide files
most affected and found both had gone stale from this session's changes:

- **`objectRemoval.ts`** still said region editing "only works on a standalone image/video
  upload, not a PDF's embedded photo" (now false — item 1's whole point) and listed "Check for
  tampering" as one of the dropdown options whose boxes get a ✕ remove-shortcut (also now false
  — Part 228 removed that shortcut specifically for tampering boxes, since checking for
  tampering is a verification step, not an edit workflow). Rewrote the intro and the relevant
  bullet to reflect current behavior: "Draw region"/Download/Reset now work on any citation
  with a page image (PDF or standalone); the ✕ shortcut remains standalone-image/video-only and
  explicitly excludes tampering boxes. Also added a previously-undocumented bullet for the
  "Download" button (shipped in Part 228, never made it into the guide).
- **`objectDetection.ts`**'s "Check for tampering" bullet only described the original single
  ELA signal. Rewrote it to describe all three now-merged signals (ELA, noise-residual, JPEG
  ghost) in plain terms, kept the existing "not a certainty, verify visually" caveat, and added
  the same tampering-boxes-have-no-✕ note for consistency with the object-removal section.

Both files stayed well under the 400-line cap after edits (70 and 131 lines respectively).
Type-checked clean (`tsc --noEmit`, no userGuide-related errors).

Committed `e37f3c5` (ml-portfolio repo, frontend-only doc changes, no HF Space upload needed),
pushed to `origin main`.

## Commit hashes

- ml-portfolio: `0bfc2b0` (PDF citation editing support + scroll-position bug fix),
  `e37f3c5` (user guide update for both shipped features)
- ML-Unified: `fe7d325` (JPEG ghost detection, three-signal tampering merge)

## Pending list after this session

1. Watermark embedding
2. Live-webcam surveillance
3. Plate-specific ALPR
4. TTS narration
5-9. Five standalone-tool ideas (Text-to-Image Generator, Social Reels Creator,
   Gesture-Controlled Desktop, Medical Scan Analyzer, Sign Language Translator)
10. Genuine/forged signature verification decision (was item 11; item 10/JPEG-ghosts now done)