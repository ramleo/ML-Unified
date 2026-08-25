# Session 2026-08-26 — Three New Security/CV Tools (Part 256)

Continuation session after Part 255. User asked "what next?" against the
consolidated pending list, then approved three sequential tool builds:
**Face Deanonymization Risk Demo**, **Video-Call Keystroke Inference**, and
**Movement Form Comparison** (combining two separate pending-list items).
Each followed the established discipline: research feasibility first,
confirm scope with the user via AskUserQuestion where a real judgment call
existed, plan mode before writing code, build, verify with real data (not
just code review), then ask before commit/push.

---

## 1. Face Deanonymization Risk Demo (pending-list #37)

**Ask**: "#37 (face deanonymization risk demo)".

**Research first**: an Explore-agent pass found `/tools/face-cloak` already
shipped the full *protection* half (InceptionResnetV1/VGGFace2 face
embeddings, gradient-ascent cloaking, epsilon-bounded, masked to the face
region — a simplified untargeted Fawkes) and reported a real measured
cosine-similarity drop. But it only ever compared the cloaked embedding to
the photo's OWN original embedding — it never demonstrated an actual
re-identification. No gallery/database-search code existed anywhere in the
backend.

**Scope decision (AskUserQuestion)**: build a **new standalone tool** that
reuses face-cloak's embedding/cloaking code via a plain Python import,
rather than extending face-cloak's page in place — keeps face-cloak's own
scope unchanged; this is a distinct offense-side demo.

**What it does**: upload a target photo + a 2-10 photo gallery. Backend
embeds every detected face (reusing face-cloak's private `_ensure_loaded`/
`_face_crop_box`/`_embed` helpers and its same/different-person thresholds,
zero duplication, zero changes to `mm_face_cloak.py`), ranks the gallery by
cosine similarity to the target — a real measured match, not simulated. A
"Protect & re-test" button calls the *existing* `/mm-face-cloak/run`
endpoint unmodified, then re-runs the identical search to show the match
break. Explicit UI disclosure: no real internet/database search, only
compares user-supplied photos in the one request.

**Backend**: new router `services/ml-api/routers/rag/mm_face_reid_demo.py`
— `POST /rag/mm-face-reid-demo/search`. Registered in `app.py`.

**Frontend**: new tool `ml-portfolio/src/app/tools/face-deanonymization-demo/`
(`page.tsx`, `FaceReidDemoRunner.tsx`, `useFaceReidDemo.ts`), new
`capabilities.ts` entry (icon `Radar`, accent `#f97316`).

**Verification — real, not just code review**:
- Direct API calls against the deployed HF Space with two real distinct
  people's photos (downloaded stock portraits): same-person (resized) photo
  scored 0.9935 cosine similarity ("same"); a genuinely different person
  scored 0.4577 ("uncertain" — correctly below the same-person threshold).
- Cloaked the target via the existing `/mm-face-cloak/run` endpoint
  (cosine similarity dropped to -0.8751, "strong" protection), re-ran the
  gallery search with the cloaked image: similarity to the real match
  dropped from **0.9935 → -0.7737**, flipping the verdict from "same" to
  "different" — a genuine, measured demonstration that the countermeasure
  defeats the re-identification it just showed.
- Playwright end-to-end on the live Vercel site: uploaded target + 2
  gallery photos, confirmed the UI surfaced the correct best-match photo
  and score, clicked "Protect target & re-test," confirmed the score
  visibly dropped and the verdict flipped on-screen (screenshot captured).

**Commits**: backend `services/ml-api` `3a69923` (+ HF Space upload of
`app.py` and `mm_face_reid_demo.py`), frontend `ml-portfolio` `b8e8eb8`.

---

## 2. Video-Call Keystroke Inference (pending-list #41)

**Ask**: "proceed with #41 (video-call keystroke inference from webcam
motion)".

**Research first**: web search on the real published attacks — Sabra et
al. (video-call keystroke inference from hand/device motion, >90% per-key
accuracy in controlled settings) and the more general USENIX Security '23
paper (Yang et al., "Towards a General Video-based Keystroke Inference
Attack"). The USENIX paper's real pipeline: (1) hand-tracking-based tap
detection + clustering finds candidate keystroke events, (2) an HMM/
language-model decode plus trained 3D-CNNs (self-supervised, trained
per-video) recover actual characters, reaching >90% per-key accuracy.
Stage (2) needs real training compute and risks shipping confidently-wrong
character guesses on an uncalibrated video — the same overclaiming risk
this project has consistently avoided (fire-detection, signature-
verification, the malware-CNN rescope).

**Scope decision (AskUserQuestion)**: build only stage (1) — the real,
measurable, honestly-scoped first half — explicitly disclosing that full
character-level text recovery needs the paper's additional trained-model/
language-model stage, which this doesn't attempt. (The alternative offered
— an HMM/dictionary word-guessing decode — was not chosen.)

**What it does**: entirely **client-side**, zero backend, reusing the
exact `@mediapipe/tasks-vision` `HandLandmarker` pattern already shipped
for Pose VJ Visuals. Steps an uploaded typing video frame-by-frame
*deterministically* (`video.currentTime` + `seeked` event + `detectForVideo`
at a fixed 20 samples/sec — not real-time `requestAnimationFrame`, since
timing precision is the entire signal here). For each of 5 fingertip
landmarks per hand, builds a y-position time series and runs a real
**tap-detection** pass (prominence-based peak detection: a local maximum
in y bracketed by genuine valleys on both sides = a press-release cycle).
Nearby events across fingers within 60ms are merged into one keystroke.
Output: a keystroke-event timeline (time, hand, rough x-position — never a
character), word-boundary segmentation from timing gaps, WPM estimate,
rhythm consistency. Prominent disclosure: recovers WHEN keys were pressed,
never WHAT was typed.

**New code**: `ml-portfolio/src/app/tools/video-keystroke-inference/`
— `keystrokeSignal.ts` (pure signal-processing math), `useVideoKeystrokeExtraction.ts`
(video frame-stepping + MediaPipe), `VideoKeystrokeInferenceRunner.tsx`,
`page.tsx`. New `capabilities.ts` entry (icon `Keyboard`, accent `#38bdf8`).

**Real bug caught and fixed before touching video I/O** (synthetic-data
verification, same discipline as prior sessions): the initial tap-detection
algorithm compared each sample only to its single immediate neighbor to
find a local max. A flat-topped peak plateau (two or more equal-height
samples at the top of a real press-release bump, which smoothing produces)
caused the amplitude check to see a zero-height drop on one side and fail
silently — detection worked on some synthetic taps and completely missed
others depending on exact plateau width. Fixed by switching to a
radius-2 local-max test (tolerates ties, deduped via the existing
refractory period) plus a **directional valley-walk** for amplitude
(`findValley`: walk outward from the peak while y is non-increasing,
stopping at the true reversal point) — a proper prominence calculation
instead of a naive single-neighbor diff. Re-verified against the same
synthetic 6-tap sequence: all 6 correctly detected, word-boundary
segmentation and WPM/rhythm numbers all sane.

**Verification — real, not just code review**:
- Synthetic data: injected known tap timestamps into a fabricated
  fingertip y-series, confirmed `detectTapEvents`/`mergeNearbyEvents`
  recovered them correctly (after the bug fix above), multi-finger merge
  correctly deduped 12 raw detections → 6 real events.
- Sourced a real 9-second stock video (Mixkit, direct mp4, license-free)
  of two hands typing on a laptop keyboard — verified visually via a
  extracted frame before using it.
- Playwright end-to-end on the live Vercel site: uploaded the real video,
  ran "Analyze," got **26 keystroke events detected, ~34 WPM, 4 word
  segments, 24% rhythm consistency** — a plausible, non-garbage result on
  real footage. Console showed only benign MediaPipe XNNPACK/WASM log
  lines (same pattern seen in pose-vj-visuals), clean model teardown.
  Screenshot confirmed a readable timeline with correctly hand-colored dots
  and word-boundary markers.

**Commit**: ml-portfolio `cb6e9f9` (frontend-only, no backend/HF Space
changes needed for this tool).

---

## 3. Movement Form Comparison (pending-list #27 + #48, combined)

**Ask**: user was asked for a recommendation among remaining pending items
("what do you suggest") and picked the assistant's suggestion: "go with
#27/#48 combined — a pose-based movement comparison tool," adding "also
there are few cyber security related pending items" as a note for the next
round (not an instruction to switch immediately).

**Research first**: web search confirmed MediaPipe `PoseLandmarker`
joint-angle extraction is a *validated* real technique, not a heuristic
gamble — published studies find <10% error vs. marker-based motion capture
for hip/knee angles, and joint-angle-change classifiers reach >97% accuracy
distinguishing correct/incorrect exercise form.

**What it does**: entirely **client-side**, zero backend, extending the
same architectural pattern (Pose VJ Visuals, Video-Call Keystroke
Inference) to MediaPipe's `PoseLandmarker` instead of `HandLandmarker".
User uploads two clips (≤30s each): "Your movement" and "Reference
movement" of the same exercise, each assumed trimmed to one full rep
(disclosed assumption, no auto-segmentation attempted). Both are stepped
through frame-by-frame at 10 samples/sec (body motion is slower than
typing, so a coarser rate suffices) with `numPoses: 1`. For each sampled
frame, reads **3D world landmarks** (metric, camera-distance-invariant —
the geometrically correct choice, not normalized 2D image coordinates) and
computes 6 real joint angles via the standard three-point vector-angle
formula: left/right elbow, knee, hip. Each video's own angle-vs-time curve
is resampled onto a shared **0-100% movement-phase axis** (not raw
seconds) — the key piece of real engineering that makes a 4-second clip
directly comparable to an 8-second one of the same movement. Joints are
ranked by RMS deviation, worst first, with the single biggest-gap phase
point called out per joint (e.g. "at 42% through the movement, your knee
angle was 23° less bent than the reference").

**New code**: `ml-portfolio/src/app/tools/movement-form-comparison/` —
`jointAngles.ts` (pure geometry/phase-resampling/deviation math),
`usePoseVideoExtraction.ts` (adapted frame-stepping for `PoseLandmarker`,
model verified reachable via direct HTTP 200 check before use),
`useMovementComparison.ts` (orchestrates both video extractions),
`MovementComparisonRunner.tsx` (dual upload UI, hand-rolled SVG line
charts per joint — no new charting dependency), `page.tsx`. New
`capabilities.ts` entry (icon `Dumbbell`, accent `#22c55e`).

**Verification — real, not just code review**:
- Synthetic geometry checks: `angleAtJoint` returned exactly 90°/180°/0°
  for constructed right-angle/straight-line/folded-back point triples;
  `extractAngleSeries` correctly read ~180°→~90° from a synthetic
  straight-leg→bent-leg frame pair; `resampleToPhase` produced **byte-
  identical** phase-normalized output for two curves with the same shape
  but different durations (2s vs. 4s) — proving the phase-alignment
  actually works, not just runs; `computeDeviation` returned exactly 0 RMS
  for identical curves and correctly identified an injected +20° offset as
  the worst point at the right index.
- Sourced two real stock squat videos (Mixkit, license-free, verified
  visually via extracted frames before use): a front-facing resistance-band
  squat (~6s, trimmed) as "your movement," and a different person's
  side-angle warehouse squat (~8s, trimmed) as "reference movement" —
  deliberately different people, camera angles, and durations to genuinely
  exercise the phase-alignment logic, not a trivial same-video test.
  Rejected other candidates found along the way for being multi-person
  (unclear pose selection) or not the same movement (a lunge).
- Playwright end-to-end on the live Vercel site: uploaded both real clips,
  ran "Compare movements," got 6 distinct, non-flat joint-angle charts
  (all 6 joints: left/right elbow/knee/hip) correctly ranked worst-first by
  RMS deviation, screenshot confirmed visually distinct green (user) vs.
  dashed (reference) curves per joint — not garbage/flat lines. Console
  showed only the same benign MediaPipe log lines seen in the prior two
  tools, clean teardown for both landmarker instances.

**Commit**: ml-portfolio `a288ada` (frontend-only, no backend/HF Space
changes).

---

## Memory updates this session

`project_pending_master_list.md` updated: #37, #41, and #27+#48 (combined)
all marked done with full rationale, real bugs found/fixed, and commit
hashes — matching the existing convention of moving shipped items out of
the open table with a one-line "done" note rather than deleting the row
silently.

## Pending list status after this session

**Newly shipped**: #37 (face deanonymization demo), #41 (video-call
keystroke inference), #27+#48 (movement form comparison).

**Still open, discussed but not started**: #32 (crime scene reconstruction/
SfM), #33 (gait analysis), #45 (Phone-video → 3D Gaussian Splat scanner),
#46 (SAM3 "magic rotoscope") — all higher-effort CV brainstorm items. Pure-
cybersecurity-flavored items from the original brainstorm list are now
largely shipped (deepfake detection, steganography, CAPTCHA hardening,
malware-image triage, face cloak/deanonymization, keystroke inference).
User flagged "a few cybersecurity related pending items" remain — session
ended before re-surveying in detail; next session should re-check
`project_pending_master_list.md` against `capabilities.ts` fresh (per the
list's own standing "always verify before presenting" lesson) before
proposing what's actually left.
