# Session 2026-08-23 — Search-Bug Follow-up, FFT/Steganography
# Investigation, Plant-Growth Phase-Correlation Alignment (Part 252)

Direct continuation of Part 251, same conversation. Three real fixes to the
homepage search-bar bug (the first two "fixes" from Part 251 turned out
incomplete under real user testing), a rigorous FFT-technique investigation
that correctly rejected two failed approaches before landing on a working
one, and a complete second feature (plant-growth GIF alignment) — both
verified live end-to-end, not just unit-tested, with real deploys to
Vercel/HF Space throughout.

Tags: `ml-portfolio`, `ML-Unified`, `homepage-search-bug`, `sticky-search-bar`,
`fft-artifact-detection-rejected`, `chi-square-steganalysis`,
`phase-correlation-alignment`, `plant-growth-tool`, `hf-space-deploy`,
`process-accountability`, `Part252`, `continuation-of-Part251`

---

## 1. Homepage search-bar bug — two more real bugs found after the "fixed" claim

Part 251 ended believing the search-bar scroll bug was fixed. The user
reported "issue persists" with a screenshot. Rather than re-asserting the
fix, re-tested live with Playwright at multiple viewport sizes — genuinely
could not reproduce at first. User then gave the exact repro: "scrolled
down till Computer Vision tool, then typed 'pi'". Reproducing that exact
scenario surfaced a real second bug: the existing fix targeted the sticky
search bar's own position, but when the matching results are in a domain
ABOVE the user's current scroll position (not just below), the fix's
`scrollIntoView` call on a `position: sticky` element didn't reliably
correct it. Fixed by retargeting the plain (non-sticky) section container
+ switching to `behavior: "instant"` (a "smooth" scroll was racing against
fast typing across keystrokes).

User asked to see the fix live, step by step, with permission before each
Playwright action — did so, using a **real mouse-wheel scroll** (not a
programmatic jump) to match the user's actual input method. This found
a **third** bug: the fix's two position-based heuristics ("is the bar's
top negative", "is the section's bottom above 80px") were both proxies for
"are results visible" — neither actually checked the real result content,
so a result 90%+ scrolled off-screen still passed both heuristics. Fixed by
checking the actual `.cap-grid`/`.cap-no-results` elements' real visible
height directly (requiring ≥120px genuinely visible, not just any overlap).

A **fourth** bug surfaced immediately after: the fix's effect also fired on
initial page load/refresh (query="" on mount, section legitimately below
the fold), incorrectly reading that as "results scrolled out of view" and
force-auto-scrolling the page down on every fresh load. Fixed by skipping
the effect's first run via an `isFirstRun` ref.

All four fixes verified live on production (`ml-portfolio-rho.vercel.app`)
via Playwright, not just localhost. Commits: `09db8de`, `33f11b8`,
`b63623a` (search-bar), all on `ml-portfolio`.

**Explicit accountability exchange**: user directly asked "what did you do
exactly while testing, give me steps, match it with steps i gave you to
reproduce the issue" — answered with a literal side-by-side comparison,
naming every place my test methodology (programmatic scroll, different
window sizes, simulated keystrokes) diverged from the user's actual manual
repro, rather than asserting equivalence.

## 2. Pending-list review — Computer Vision / Security & Trust

User asked for the pending backlog filtered to CV/Security. Before
presenting it, cross-checked the stale `project_pending_master_list`
memory against the live `capabilities.ts` and found two more stale rows
(seventh+ time this has happened in this project, per that memory's own
running count): **Photo Library Visual Search** (#50) and **Adversarial
Robustness Lab** (#40) were both already fully shipped, contradicting the
memory's "pending" listing. Corrected the memory before answering.

## 3. Fourier-transform research — three genuine techniques found, six ruled out for this codebase

User asked (after a `/loop`-style tangent about FFT applications in
cybersecurity/CV/NLP) to research real techniques and match them against
what's actually buildable here. Delivered a table separating "real fit"
(STFT steganography detection, phase-correlation image alignment) from
"needs infrastructure this project doesn't have" (network IDS — no traffic
source; MFCC — no audio tool) from "no integration point" (FNet needs a
self-trained transformer; frequency-domain data augmentation needs a
training loop, and every CV tool here is inference-only on pretrained
ONNX models).

## 4. FFT periodic-artifact detection for AI-splice detection — built, tested, REJECTED

User pushed back hard on an initial "we can't do X" framing ("your job is
to find ways to implement techniques, find work around, find solutions")
and asked to plan out an FFT-based detector aimed at AI-generated/AI-
inpainted image splices — a genuine gap none of the existing three
tampering detectors (ELA, noise-residual, JPEG-ghost) are built to catch,
since all three read compression/noise statistics that a re-noised AI
patch can evade.

Built `mm_fft_artifacts.py`: block-wise 2D FFT, radial power spectrum,
compared each block's spectral falloff slope against its local
neighborhood (same trick the three existing detectors use). Verified
against the SAME real bike photo already used to validate ELA's
fine-detail confound, plus a synthetic GAN-like splice (downsample +
nearest-neighbor upsample, reproducing real upsampling periodicity without
needing an actual GAN model).

**Result: genuine, decisive rejection.** The synthetic splice's slope
deviation never became the image's own top-scoring region, even at extreme
severity (scale 4→32). A second, richer attempt (comparing the FULL radial
profile shape via a distance metric instead of collapsing to one slope)
also failed — the untouched, never-touched original photo scored a
**higher** anomaly (4.93 std) than the actual synthetic splice (4.60 std).
Per a bar set explicitly before the second attempt ("if this doesn't
cleanly separate the splice, I stop, no more tuning"), stopped there,
deleted the unwired/uncommitted module, and recorded the negative finding
in `project_tampering_detector_precision` memory — matching the project's
existing "signature verification: decided NOT to build" precedent.

## 5. Chi-square LSB steganography detection — built, tested, SHIPPED

Same FFT-based idea was tried once more, this time aimed specifically at
steganography (a near-Nyquist frequency-energy ratio) — worked cleanly on
one PNG test image, then **failed completely** on 3 real native-JPEG
photos (grace_hopper/china/flower from local ML libraries): JPEG's own
compression dumps 2-3 orders of magnitude of variable energy into exactly
the band this measured, swamping the LSB signal entirely.

Corrected course to the actual textbook-correct technique for this
specific problem: the classical **Westfeld-Pfitzmann chi-square attack**
(spatial-domain histogram value-pair analysis, not frequency-domain at
all) — chosen specifically because it doesn't share the JPEG-noise
confound. Built `mm_steganography.py`, validated against the same 4 real
test photos with a real LSB payload embedded directly into the decoded
pixel array at multiple embedding rates (100%/50%/20%): clean baseline
consistently 8.9-18.0, 100%-rate embed consistently 0.5-1.3, clean
separation, no false positives, honestly disclosed reduced sensitivity
below ~20-30% rate (matches the technique's known published behavior, not
a flaw in this implementation).

**Two real integration bugs found only by testing the full pipeline, not
the isolated module**:
- A same-shape bug to my own earlier per-channel design mistake: taking
  the MIN chi-square across R/G/B channels produced a live false positive
  (china.jpg's R channel alone read 35% "detected" with zero embedding).
  Fixed by AVERAGING across channels instead — validated this was also
  the only approach that actually preserved signal when LSB was embedded
  into RGB directly then needed detecting (a pure luminance-conversion
  approach, tried in between, destroyed the signal to 0% entirely, since
  PIL's weighted grayscale formula scrambles the clean bit-level structure
  averaging preserves).
- `mm_ingest_payload.py` had its own explicit SSE-response field list —
  computed correctly upstream but silently dropped before reaching the
  frontend. A parallel bug one layer further up, in the frontend's
  `IngestProgressRail.tsx`, which has its OWN separate snake_case→camelCase
  field-mapping list for the same payload. Both fixed; this class of bug
  (a new backend field needs updating in at least 3 separate explicit
  field lists across the stack, not just the function that computes it)
  is now a named, reusable lesson.

Surfaced as a new "Possible hidden data (N%)" dropdown option in
multimodal-rag's citation panel (same whole-image, no-bbox pattern as the
existing "Crowd density" feature) — verified live via Playwright on BOTH
localhost and production (`ml-portfolio-rho.vercel.app` talking to the
real deployed HF Space), for both a genuine stego image (option appears,
100% confidence) and a clean image (option correctly absent, no false
positive).

**Wording/UX follow-up round** — user asked three direct questions after
seeing the shipped feature: "what is the pattern, how will a layman know?",
"can you show the user where the pattern is?", "will a layman understand
how to use this?" Answered honestly rather than just re-patching text:
(1) rewrote the vague "colors show a pattern" into a concrete plain-English
explanation of the actual pixel-value-pair mechanism; (2) **directly said
no** — this technique has no "where," the whole payload is spread evenly
across every pixel, and drawing a fake box would be dishonest, unlike
tampering/objects, which do have a location; instead built a new, real
"Show what the computer sees" on-demand visualization (new
`/rag/mm-steganography/visualize` endpoint, renders the red channel's
LSB plane as black/white) with an explicit "this is NOT the hidden message
or its location" caption — then verified that caption's honesty is
literally true by confirming both the stego and clean image's bit-planes
render as ~50/50 static, indistinguishable from each other; (3) confirmed
the feature was previously purely informational with nothing to do, same
gap named directly, addressed by the same visualization addition.

Backend commits `4c371d0`, `7f5f8b7`, `eba6a20`; frontend commits `abe3336`,
`e6881d0`, `8d61135` — all deployed to the live HF Space and Vercel, each
verified with a real API call against the actual production URL after the
rebuild finished (not just trusting the "RUNNING" status stage).

## 6. Plant Growth: phase-correlation frame alignment for GIF export — SHIPPED

Second "ready candidate" from the FFT research table. Initial framing
("one function call, `cv2.phaseCorrelate`") was corrected after actually
checking the integration point: the GIF exporter (`PlantGrowthGif.tsx`) is
deliberately, explicitly client-side-only (its own docstring says so) —
sending photos to a backend just for alignment would violate that design.
Resolved by computing alignment as a byproduct of the measurement call
that ALREADY has the photos server-side, rather than adding a new
round-trip.

Built `mm_plant_growth_align.py`: validated the sign convention and
accuracy numerically FIRST (recovered known synthetic shifts within ~1px,
including a realistic edge-clipped-not-wraparound translation test) before
wiring into `mm_plant_growth.py`'s `_run_growth_mode()` as an additive
`frame_alignment` field, confirmed the other caller (group-reid) safely
ignores the new field. Threaded through the frontend
(`usePlantGrowthRunner.ts`, `PlantGrowthRunner.tsx`,
`PlantGrowthGif.tsx`) with graceful fallback to the old centered-draw
behavior when alignment isn't available (GIF export works pre-measurement,
unchanged).

Verified live end-to-end with a synthetic plant photo (green leaf-blobs on
a soil background, not a repurposed bicycle photo — user directly asked
"why are you checking a bicycle image in the plant growth tool?", a fair
catch, since the bike photo had been reused all session purely out of
convenience and wasn't representative of the tool's real content): measured
a real ~29/-14px simulated camera shake, exported the actual GIF file, then
independently re-measured the shift between the two real exported frames —
residual dropped to ~1.2px, confirming the correction is genuinely applied
in the output file, not just computed and silently discarded. Backend
commit `d9ce4c1`, frontend commit `7775ced`, both deployed and verified
live against the real production HF Space URL.

---

## Where this stands

- Homepage search-bar bug: four real bugs found and fixed across this and
  the previous session; all four verified live on production.
- Steganography detection: shipped, deployed, verified live — chi-square
  LSB attack + on-demand bit-plane visualization.
- FFT periodic-artifact AI-splice detection: rejected, documented, not
  shipped — a closed line of investigation, not an open one.
- Plant-growth GIF camera-shake correction: shipped, deployed, verified
  live.
- Known, named, NOT yet acted on: `CitationThumbnailPanel.tsx` is at 391
  lines (past the project's 350-line "modularize soon" marker, under the
  hard 400-line cap) — flagged to the user, deferred pending their call,
  same treatment as `app.py`'s own deferred-refactor precedent.

## How to apply going forward

1. **A new backend response field needs updating in every explicit field
   list along its path, not just the function that computes it.** This
   session hit this exact bug shape twice in one feature (`mm_ingest_
   payload.py`'s SSE field list, then `IngestProgressRail.tsx`'s separate
   snake_case→camelCase mapping) — grep for the sibling field name (e.g.
   `"tampering"`) across the whole call path before considering a new
   field "wired in," not just adding it where it's computed.
2. **When a "layman-facing" wording complaint comes in, check whether the
   real fix is copy or missing functionality before just rewording.** The
   steganography caveat text needed BOTH a plain-language rewrite AND a
   genuinely new capability (the bit-plane visualization) — rewording
   alone would have left the "can you show me" and "how do I use this"
   gaps unaddressed.
3. **The bar set before a second tuning attempt should actually be
   honored.** The FFT-artifact rejection explicitly named a stopping
   condition before starting the second (profile-shape) attempt, and
   stopped there the moment it wasn't met — this discipline is what made
   the eventual switch to chi-square (a genuinely different, correct
   technique) happen instead of an indefinite tuning loop.
4. **Test images should represent the tool's actual domain**, not
   whichever real photo happens to be lying around from a previous
   feature's testing — caught directly by the user mid-session; a
   synthetic-but-representative image (leaf-blobs for plant growth) is
   better than a convenient-but-irrelevant one (a bicycle) even when the
   underlying algorithm being tested (pixel-shift correlation) doesn't
   technically care about image content.
5. **A live HF Space deploy verification means a real API call against the
   production URL after the rebuild finishes** — checking `stage ==
   "RUNNING"` alone was insufficient in earlier sessions; this session's
   pattern (poll stage, then immediately fire a real request and check its
   actual returned content) was applied consistently across all three
   backend deploys this session and should stay the default.
