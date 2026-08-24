# Session 2026-08-16 (cont'd) — Watermark, narration, ALPR, signature-verification decision

Continuation of the same day as Part 234, but a distinct session picking up the consolidated
pending-items list (`project_pending_master_list.md`) one item at a time: watermark embedding, TTS
narration, PDF-citation-editing (found already done), plate detection (ALPR), a feasibility-researched
no-build decision on signature verification, a stale-pending-item correction, and a CV-brainstorm
review from a shared Google AI Mode link. Five separate times this session, a pending-list row turned
out to already be resolved by earlier work that was never removed from the table — this became its
own tracked lesson (see Memory changes below).

## Part 1 — Watermark embedding (invisible DCT/QIM)

Picked "watermark embedding" off the pending list — paired with the existing tampering detector
(`mm_tampering.py`/`mm_noise_forensics.py`/`mm_jpeg_ghost.py`) as the "embedding" half of that
backlog item, per how it was originally framed. Designed and built from scratch (no existing
watermark code): a fixed 216-bit payload (1-byte length + 24-byte label + 16-bit checksum) embedded
via 8x8-block DCT quantization-index-modulation (QIM) on the image's Y (luma) channel, redundantly
repeated across blocks and recovered by majority vote. Pure local image processing — zero API cost,
zero budget gating, unlike every other image-gen feature in this codebase.

New `services/ml-api/routers/rag/mm_watermark.py` (214 lines): `embed_watermark()`/`verify_watermark()`
plus `POST /rag/mm-watermark/embed` and `/verify`. Registered in `app.py`. Frontend: new
`useWatermark.ts` hook + `WatermarkControls.tsx` component, wired into `CitationThumbnailPanel.tsx`'s
toolbar ("Embed watermark" downloads a watermarked copy of whatever's on screen; "Verify watermark"
checks any image and shows a result badge).

Verified locally before any deploy: round-trip embed→verify recovers the exact label at 100%
confidence, survives a JPEG resave down to quality 50, correctly rejects unwatermarked images and
images too small to hold the payload. Committed (`7d7d497` backend, `71eb0a5` frontend), HF Space
uploaded, then verified fully live end-to-end via Playwright: uploaded a test image, confirmed "No
watermark detected" on the original, clicked "Embed watermark," confirmed the DOWNLOADED file
actually decodes the label, re-uploaded that same downloaded file through the live UI and got
`✓ "MLU-VERIFIED" (100%)` on screen — not just a code-review claim, an actual round trip through the
real deployed app.

## Part 2 — TTS narration ("Read aloud")

"TTS narration (Blind Assistant Audio Describer)" turned out to be pure aspiration — researched first
and confirmed zero existing code or dedicated UI anywhere in either repo for "blind assistant" or
"audio describer." What actually shipped: a "Read aloud" button on the existing caption text in
Multimodal RAG's citation panel (visible after selecting "Describe (caption + OCR)"), using
browser-native `window.speechSynthesis` — zero backend cost, zero API key, no new dependency. New
`useNarration.ts` hook, wired into `CitationResultsPanel.tsx` (not `CitationThumbnailPanel.tsx`,
which was already near its 400-line cap). Committed `8b3efcc`, pushed, verified live via Playwright
(button appears, toggles Read aloud ↔ Stop reading correctly).

**Real user-reported bug round:** after live use, the voice was "not clear" — all three of robotic/
low-quality, too fast, and cutting out mid-read. Root-caused each: Chrome resolves `getVoices()` to
`[]` until the async voice list loads (so `speak()` got stuck with the single bundled low-fidelity
fallback voice), default rate 1.0 reads as rushed on longer captions, and Chrome has a long-standing
bug where it silently auto-pauses an active `speechSynthesis` session ~15s in and never resumes on
its own. Fixed with a voice-quality scoring heuristic (prefers voices named natural/neural/premium/
enhanced, "Google," or non-local-service), rate 0.95, and splitting text into per-sentence utterances
chained via `onend` plus a periodic `resume()` nudge every 10s while active. Committed `b09e4c6`. User
confirmed live after the fix: "it sounds good."

## Part 3 — User guide sync + first stale-pending-item correction

Asked to update the Multimodal RAG user guide and check it was current. Added the two missing
sections (watermark embed/verify in `objectRemoval.ts`, explicitly distinguished from the pre-existing
"Traceable watermark" shared-link screen-tag feature which is a different, unrelated thing with the
same word in its name; read-aloud in `citations.ts`). Committed `ee4b3e4`.

Then asked to do "PDF/mixed-content citation editing" next — researched first (per the standing
project norm of grepping code before starting) and found it was **already shipped**, commit `0bfc2b0`
from 2026-08-09, well before later session logs (Parts 227-231) kept re-listing it as pending without
re-checking. Corrected `project_pending_master_list.md` immediately rather than building a duplicate.
This was the first of what became five stale-pending-item discoveries this session — see Memory
changes below for the standing lesson this became.

## Part 4 — Plate detection (ALPR)

Verified genuinely unbuilt first (unlike the PDF-citation item). Researched the actual codebase state:
the 601-class object detector (`mm_objects.py`) already outputs "Vehicle registration plate" as one of
its classes with zero filtering, and the corroborated region-sharpen+OCR flow (`mm_deblur.py`'s
`_sharpen_region`) was literally built around a real plate-hallucination incident already documented
in that module's own docstring. So the actual gap was thin: surface plates as their own dropdown
option (mirroring the existing signatures pattern) and a one-click "Read plate" button reusing the
existing corroborated sharpen call with the plate's own bbox — no new backend endpoint needed at all.

Built: `DetectionBoxOverlay.tsx` gained an optional `onReadAction` prop (a second per-box button,
distinct from the existing ✕ remove-region shortcut); `CitationThumbnailPanel.tsx` gained a `plates`
list (client-side filter of the same `objects` array signatures/faces already use) and a "Detect
plates (N)" dropdown option. Along the way, `CitationThumbnailPanel.tsx` hit 398/400 lines — extracted
its entire header button row into a new `CitationToolbar.tsx` component (317 lines afterward), a
purely presentational split with no behavior change, verified via a live regression pass (Draw
region, Embed/Verify watermark all still worked correctly through the new prop wiring). Committed
`e8cde2c`.

**Live testing with 3 real user-provided plate photos** (`Number-Plate-Detection1/2/3.png`) surfaced
two real bugs:
1. **Markdown-table leak.** The BMW photo (plate "LX17 PYD") detected and read correctly — both
   independent corroboration reads agreed on `LXI7 PYD` (a shared 1/I OCR misread, not a corroboration
   failure) — but the confirmation message leaked raw markdown table syntax:
   `"Confirmed by two independent AI reads: \"| LXI7 PYD | | --- |\" — still verify against original"`.
   Root cause: Mistral OCR wraps short bordered snippets (a plate) in pipe-table markdown even though
   it isn't real tabular data; `mm_image.py`/`mm_video.py` already handle this class of artifact via
   `clean_ocr_text`, but `_sharpen_region`'s own `_ocr_text` never applied it. Fixed with a new
   `_strip_markdown_table()` flattener layered on top of `clean_ocr_text`. Committed `5b2fd6e`, HF
   Space uploaded, re-verified live — clean output confirmed.
2. **Detection recall gap.** The grayscale Mini Cooper photo (plate "HR 26 BR 9044," plainly legible
   to a human) scored "Car" at 91% confidence but the detector missed the plate entirely — too small a
   fraction of the full 640x640 detector input, worsened by matplotlib axis/title chrome eating into
   the frame. User asked "what can we do about this" — presented three options (crop-and-redetect
   vehicle boxes / lower the plate class's confidence threshold globally / accept as a known
   limitation), recommended the first since it fixes the actual cause rather than papering over it and
   follows an existing template. User approved. Generalized the existing person→face crop-and-redetect
   fallback in `mm_objects.py` (`_detect_faces_in_person_crops`) to vehicle→plate
   (`_detect_plates_in_vehicle_crops`): crop each confidently-detected vehicle box, re-run plate-only
   detection on that higher-resolution crop. Verified locally on the exact failing photo (now detects
   at 48%, correctly positioned box) with no regression on the other two test photos. Committed
   `44afd50`, HF Space uploaded, re-verified live: "Detect plates (1)" now appears where it didn't
   before, box sits precisely over the real plate. "Read plate" itself then hit a live Gemini `429 Too
   Many Requests` — pulled the actual HF Space run logs for direct evidence rather than guessing,
   confirmed this was an upstream rate limit from cumulative sharpen calls across the session, entirely
   unrelated to the detection fix, and stopped retrying per the project's two-failure/no-blind-retry
   norm on billed APIs.

Also generalized the guide (`objectDetection.ts`) alongside the initial build, documenting the
one-click "Read plate" action and why it reuses the corroboration flow rather than trusting one AI
guess.

## Part 5 — Signature verification: researched, decided not to build

Picked up the last "decision, not a build" item from the pending list (open since a much earlier
session referred to as "Part 229"). Researched feasibility first via a background agent rather than
guessing: a candidate model exists — `Mels22/Signature-Detection-Verification`, the SAME author/repo/
license (Apache-2.0, ungated) as the signature DETECTOR already in use, ships a Siamese
`verifier_siamese.pt` head, plausible ONNX export path (plain CNN, no exotic ops). Cleared every
feasibility bar (public, ungated, permissive license, exportable) but failed on reliability: the model
card's "100% accuracy" is over only 15 epochs on the author's own small dataset (classic overfitting
signal), and the number that actually matters — end-to-end detect-then-verify pipeline accuracy — is
the author's own reported **0.5743**, barely better than chance. Presented this honestly, recommended
not building since a genuine/forged verdict wrong nearly half the time on something like a contract
would actively mislead a user who trusts it. User agreed: don't build. Documented the decision (and
the reasoning, so it isn't accidentally revisited) in `project_pending_master_list.md`, same treatment
as the earlier Medical Scan Analyzer no-build decision.

## Part 6 — Region-sharpen TEXT/GRAPHIC misclassification: also already fixed

Picked this up next expecting to build something — checked the actual code first (per the now-standing
lesson) and found commit `e34a71a` ("LANCZOS resize + dual-corroborated region classification," part
of an earlier session referred to as "Part 231") had already fixed exactly this. `_sharpen_region`
now runs the TEXT/GRAPHIC classify call on BOTH independently-sharpened crops concurrently and only
treats a region as GRAPHIC if both agree, rather than trusting one call — meaningfully cutting the
original single-call ~1/3 misclassification rate the pending-list row was still describing. Presented
this to the user with the option to harden further (a third tie-breaking call) or just close it out;
user chose to close it out. This was the fifth stale-pending-item discovery this session.

## Part 7 — CV/security brainstorm from a shared link

User shared a Google AI Mode conversation link (`share.google/aimode/...`) covering a broad
brainstorm of CV project ideas across several rounds: general beginner/intermediate/advanced projects,
a "sports form tracker" recommendation, an inventory/checkout-assistant idea, a perimeter-intrusion
tripwire system, a comprehensive security-use-case list (residential/commercial/traffic/industrial/
defense), and a forensics-specific list (image forgery, video surveillance analysis, biometrics, crime
scene reconstruction, source camera identification).

Fetched via Playwright (WebFetch's own redirect handling didn't resolve the share link correctly;
`browser_navigate` followed it to the real Google AI Mode conversation page, and
`page.evaluate(() => document.body.innerText)` pulled the full ~16.8k-character conversation text in
three chunked reads). Cross-referenced every idea against what ML-Unified already has, and first pass
was too aggressive about filtering to only 3 options — user pushed back ("are these the only ones or
are there good usecases... related to images and videos?"), so did a full honest re-pass covering
everything mentioned, organized into: already-built (OCR, ALPR, forgery detection, object/face
detection — don't re-offer), upload/video-friendly new ideas worth considering (weapon detection —
may already work via existing object classes; sports form tracker on an UPLOADED video, not
live-only, corrected from the first pass; crowd density counter; PPE compliance check; fire/smoke
detection; source camera identification/PRNU; crime scene reconstruction via photogrammetry; gait
analysis; restricted-zone plate enforcement; video-doorbell person-vs-package), poor-fit items needing
a live camera feed (loitering, tailgating, tripwires, drone detection — same architectural mismatch
already flagged for the existing live-webcam-surveillance pending item), and out-of-scope items
(iris/fingerprint biometrics, under-vehicle inspection, thermal/night-vision, facial-recognition
access control). No build decision made yet — this was a scoping/options pass, not an implementation
round.

## Commit hashes (chronological, this session)

**ML-Unified (backend):**
1. `7d7d497` — invisible watermark embed/verify (`mm_watermark.py`)
2. `5b2fd6e` — strip markdown-table leak from region-sharpen OCR reads
3. `44afd50` — crop-and-redetect vehicle boxes to catch small plates

**ml-portfolio (frontend):**
1. `71eb0a5` — watermark embed/verify UI
2. `8b3efcc` — read-aloud narration (initial)
3. `b09e4c6` — narration voice-quality/rate/Chrome-pause-bug fix
4. `ee4b3e4` — user guide: watermark + narration sections
5. `e8cde2c` — plate detection UI + toolbar extraction (`CitationToolbar.tsx`)

## Memory changes this session

- New `feedback_verify_pending_before_building.md` — created after the 3rd stale-pending-item hit
  (PDF-citation editing, text/image-paste, and the watermark/narration audit), later updated to 5
  after the ALPR-scope undersell and the TEXT/GRAPHIC-misclassification staleness. Standing rule: grep
  the actual code and check `git log` before starting ANY item pulled from the pending master list,
  even when the row's own description sounds confident and specific.
- `project_pending_master_list.md` updated repeatedly: watermark embedding, TTS narration,
  PDF-citation editing (correction), text/image-paste (correction), plate-specific ALPR, signature
  verification (no-build decision documented), and region-sharpen misclassification (correction) all
  moved out of the pending table into the "already done" section with commit hashes and what was
  actually found in each case.

## Pending / not yet resolved

Remaining items, unchanged in status from before this session: Social Reels Creator,
Gesture-Controlled Desktop, Sign Language Translator (all high-effort standalone CV tools), live-webcam
surveillance/intrusion alerting (high effort, architecturally different — no upload step), MMRAG
backlog (MMRAG-07/16/17/18/19/21/22, explicitly parked), LLM Fine-tuning Pipeline (needs GPU), Time
Series Forecasting. New candidates surfaced this session from the CV brainstorm (Part 7 above), no
build decision made on any of them yet — weapon detection specifically flagged as possibly already
working with zero new code, same pattern as plate detection turned out to be, worth checking before
building anything.
