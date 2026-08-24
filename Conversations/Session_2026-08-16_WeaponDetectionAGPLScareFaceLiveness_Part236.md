# Session 2026-08-16 (cont'd) — Weapon detection, AGPL licensing scare, CV brainstorm research, Face Liveness Detector

Continuation of the same day as Part 235, resuming directly from "proceed with Weapon detection, but
where will you add it?" Covers finishing the CV-brainstorm backlog (weapon detection, video doorbell,
crowd density, restricted-zone plate enforcement, fire/smoke — the last one researched and correctly
NOT built), a real licensing scare when Ultralytics' own GitHub statements revealed their YOLO models
claim AGPL-3.0 even for just exported weights, a full research cycle hunting for a clean replacement
(none found — D-FINE hands-on tested and rejected for missing weapon classes), two rounds of web
research into CV+cybersecurity and general "mind-blowing" home-buildable CV ideas, and building a new
standalone Face Liveness Detector tool end-to-end — including catching and fixing a real reliability
bug the user found by actually testing it live.

## Part 1 — Weapon detection

Checked the code first, per the standing verify-before-building lesson: the 601-class object detector
already had `Weapon`, `Knife`, `Handgun`, `Rifle`, `Sword`, `Bomb`, `Missile` as literal OIV7 classes —
same "already returns it, just needs surfacing" pattern as plate detection. Built as a pure client-side
filter (`WEAPON_LABELS` set in `CitationThumbnailPanel.tsx`) + new "Detect weapons" dropdown option,
zero backend changes, deliberately excluding `Kitchen knife` (an ordinary culinary object, would
false-alarm on kitchen photos). User then asked "will it detect bomb?" — `Bomb`/`Missile` were missing
from the initial label set despite existing in the detector; added them in a same-day follow-up commit.
Also updated `objectDetection.ts` user guide with an accuracy caveat (general-purpose detector, not
trained specifically for weapons/explosives).

## Part 2 — Video doorbell (person vs. package)

Checked first again: `Person` already matched literally in `EvidenceColumn.tsx`'s question-matching
logic, and `Box` already existed as a detected class — the only real gap was no synonym mapping for
"package"/"parcel"/"delivery" phrasing pointing at `Box`. Fixed with a 4-line addition to
`HIERARCHY_SYNONYMS`, closing the "video doorbell" use case almost for free, same pattern as weapons.

**User live-tested it and reported it didn't work** — screenshots showed the object detector's
dropdown had no "Detect objects" option at all for a `package-at-door.jpeg` upload (0 detections), and
a second `person-at-door.jpeg` test showed the person detected fine but the carried boxes not detected
at all. Debugged with real evidence rather than guessing: ran the detector directly against the actual
uploaded files and found both were tiny Getty-watermarked stock-preview thumbnails (148px tall, 6-7KB)
— genuinely too little pixel data for the 601-class detector, `Box` scored only 0.232 (below the 0.35
threshold). A user-provided larger `package-at-door2.png` (1024x683, real resolution) still didn't
detect `Box` — scored 0.26, still under threshold but real, correctly-positioned signal. Traced this
to a genuine model weakness on stacked-cardboard-shipping-box scenes specifically (the "Box" class
likely trained mostly on gift/product boxes).

## Part 3 — Per-class confidence threshold + file-length cleanup

Fixed the Box detection gap with a **per-class threshold override** (`_CLASS_THRESH_OVERRIDES = {"Box":
0.22}` in `mm_objects.py`) rather than lowering the global 0.35 threshold — keeps higher-stakes classes
(Weapon/Handgun/etc) at the stricter bar while catching the real Box signal. Verified against all three
test images before deploying (both `package-at-door.jpeg` and `package-at-door2.png` now correctly
detect Box; `person-at-door.jpeg`'s carried boxes still don't — confirmed via direct raw-score check
that this one is genuinely near-zero signal, not a threshold issue, since the boxes are occluded/held
awkwardly and cropping around the person didn't help either).

This addition pushed `mm_objects.py` to 390 lines, over the project's 350-line modularize-first
threshold — split the 601-class `OIV7_CLASSES` list (74 lines, pure data) into a new `oiv7_classes.py`,
dropping the file to 316 lines. Also fixed a **real stale-citation bug** the user found: removing a
document from "Session sources" didn't clear its citations already shown in the Evidence panel from an
earlier chat turn, even though the backend chunk was already deleted — added
`removeSourceFromEvidence()` to `useRagChat.ts`, wired into `MmRagRunner.tsx`'s `removeDocument`.

## Part 4 — Crowd density counter

Checked first, again: `detect_objects()` caps its returned box list at `_MAX_DETECTIONS` (8) across
every class combined, for citation box-drawing UI — meaning a naive `objects.filter(Person).length`
would silently undercount any real crowd. This turned the row's "Low effort" label into real work, not
a quick filter. Fixed by changing `detect_objects()`'s return type to `(objects, person_count)` —
`person_count` captured BEFORE the slice, a real uncapped count — threaded through `mm_image.py`/
`mm_video.py` (callers), `ingest.py` (storage, plain scalar), `citations.py` (query-time API), and
`mm_ingest_payload.py` (post-upload SSE preview). Frontend: `personCount` threaded through the full
citation data path (`MmRagRunner.tsx`, `EvidenceColumn.tsx`, `EvidencePanel.tsx`,
`DocumentSummaryPanel.tsx`, `_types.ts`, `IngestProgressRail.tsx`) into a new "Crowd density (N)"
dropdown option showing the real headcount as text, not boxes. Verified live against the deployed HF
Space via a direct `/rag/mm-ingest` call — `person_count: 1` confirmed.

## Part 5 — Restricted-zone plate enforcement

Zero backend changes needed — built entirely from existing pieces. Reused `FreehandDrawLayer` (already
powering "Draw region"/"Sharpen region…") for zone-drawing, keeping only its bbox output. Extended
`DetectionBoxOverlay`'s `color` prop to accept a per-detection color function (not just one flat
color), so a plate renders red when its center falls inside the drawn zone, blue otherwise, plus a
violation summary line. Found and fixed a real mutual-exclusion gap along the way: `SharpenOverlay`'s
own draw layer had no awareness of the new zone-drawing mode, so both could have mounted and captured
pointer events simultaneously — threaded a proper `onExitZoneMode` callback through `SharpenControls.tsx`
rather than just papering over it with an extra render guard. Live-verified via Playwright against a
real plate photo: drew a zone away from the plate → "No plates inside the restricted zone"; redrew
directly over the plate's actual screen position (read from the DOM) → "1 of 1 plate inside the
restricted zone" with the box turning red, screenshot-confirmed.

## Part 6 — Fire/smoke detection: researched and correctly NOT built

Checked first: no `Fire`, `Flame`, `Smoke`, or generic `Gas`-leak class exists anywhere in the 601-class
vocabulary — only `Fire hydrant`/`Fireplace` (objects, not the phenomena) and `Gas stove` (an
appliance). This couldn't be built as a client-side filter like weapons/plates/crowd. User chose "find
a good non-Ultralytics-trained model" — researched candidates, found one real option:
`prithivMLmods/Fire-Detection-Engine-ONNX` (Apache-2.0, ONNX-ready, ViT classifier, claimed 97.98%
accuracy). **Hands-on tested it before integrating anything** — downloaded the real ONNX file, ran it
against real test photos AND synthetic solid-color images (a saturated orange square, a solid gray
square, a solid blue-sky square). Result: near-uniform ~25-40% across all three classes on every input,
including the "obviously fire-colored" orange square (only 40.1%) and the "obviously normal" blue
square (only 38.4%) — not a preprocessing bug, the model genuinely doesn't generalize past its narrow,
undocumented 2,424-sample training set. **Rejected**, same evidence-based pattern as the earlier
signature-verification and D-FINE rejections. `project_pending_master_list.md` updated with the
specific numbers so this doesn't get re-attempted without new evidence.

## Part 7 — Ultralytics/AGPL licensing scare

User asked what "risk" meant regarding the existing object detector, then "dig into this properly."
Deep research into Ultralytics' actual license terms found a direct, on-point GitHub exchange
(issue #22458): Ultralytics' founder stated in writing that **weights produced by training with their
YOLO code are treated as derivative works under AGPL-3.0, and exporting to ONNX or avoiding their
runtime doesn't change that** — directly contradicting the "we only use the ONNX export, never their
code at runtime" reasoning this whole codebase's object detector was built on. Confirmed
`yolov8s-oiv7.onnx` is an official Ultralytics-distributed pretrained model, not a third-party
fine-tune. Real caveat surfaced by the research: whether ML model *weights* are actually a legally
"derivative work" of training *code* under copyright law is genuinely unsettled — no court ruling
found — so this is Ultralytics' stated interpretation, not settled fact, and Ultralytics has an
acknowledged track record (per a different thread) of overstating what AGPL requires in their own
marketing.

Spent two more research rounds hunting for a clean non-Ultralytics replacement covering the same class
set (Weapon/Handgun/Knife/Rifle/Sword/Bomb/Missile/Vehicle-plate/Face/Box/vehicles): YOLOX (weights-
license ambiguity, unresolved GitHub issue), RT-DETR/RF-DETR (Apache-2.0 but COCO-80 only, missing
every weapon/plate/face class), YOLO-World (actually GPL-3.0 despite marketing claims), Grounding DINO
(Apache-2.0, open-vocabulary, but confirmed ~5sec/image on CPU — too slow), D-FINE (**hands-on
verified**: cloned the repo, exported a real ONNX file, benchmarked real CPU latency (65.9ms on this
machine), and checked Objects365's actual 365-class list against requirements — confirmed Bomb,
Missile, Handgun, Rifle, Sword, License Plate, and Face are ALL missing; "Weapon" collapses to one
undifferentiated "Gun" class). User also found and asked about a self-researched list (LibreYOLO,
RF-DETR, Detectron2/MMDetection+LVIS, SAM 3) — fact-checked each: LibreYOLO is real but its own docs
admit weights aren't covered by its MIT license; RF-DETR confirmed clean but COCO-80 only; LVIS (1203
classes) is the closest partial fit (has gun/pistol/rifle/sword/knife/license_plate) but confirmed via
direct class-list check to be missing bomb/missile/handgun entirely; SAM 3 is real but wrong category
(segmentation, not detection) and its license explicitly bans weapons-related use.

**No clean replacement exists.** User's final decision: **accept the low practical risk for now** — a
free, non-commercial demo with no evidence of Ultralytics enforcing against projects like this, keep
the current (working, accurate, full-coverage) detector as-is, revisit only if the project's scope
changes. This was documented as a settled decision, not left open.

## Part 8 — CV brainstorm research (two rounds, tables)

User asked for "mind-blowing" home-buildable CV project ideas (researched: phone-video → 3D Gaussian
Splat scanning, SAM3 "magic rotoscope," Depth Anything parallax toys, home biomechanics coaching,
wildlife re-identification via DINOv3 embeddings, personal photo search, pose-driven generative
visuals, backyard astrophotography anomaly detection, plant growth quantification) then a second round
specifically at the CV+cybersecurity intersection, explicitly severity-ranked (deepfake fraud detection
and face-recognition deanonymization/liveness ranked High — real, large-scale financial/privacy harm
already happening; malware-as-image classification Medium-High; adversarial examples, video-call
keystroke inference, steganography detection, QR phishing Medium; CAPTCHA research Low-Medium, mostly
academic). Both lists presented as tables per explicit request, then merged and added to
`project_pending_master_list.md` as rows 36-53 (18 new items) at the user's request, with the security
list explicitly kept in severity order and the general list marked severity N/A rather than forcing an
inapplicable ranking onto "scan your room in 3D."

## Part 9 — Face Liveness Detector (built, then fixed a real reliability bug)

User picked "impressive results" as the narrowing criterion for the 29-item list, then explicitly asked
to pick one — chose **Face liveness/anti-spoofing detection** specifically for its self-verifiability
(matches the same standing project preference that picked Text-to-Image over Medical Scan Analyzer
earlier): you can test it yourself immediately with a photo of your own face. Scoped first via
research: public liveness-detection datasets are mostly research-gated (CelebA-Spoof is the one
directly downloadable, non-commercial license); found one real, permissively-licensed pretrained
option, `MiniFASNetV2-SE` (600KB ONNX) from `minivision-ai/Silent-Face-Anti-Spoofing` via its ONNX
port `facenox/face-antispoof-onnx`. **Verified the license directly** (cloned both repos, read the
actual LICENSE files) rather than trusting badges — genuinely clean Apache-2.0 on both code AND
weights, no Ultralytics-style gap. Research also surfaced a real, honest caveat up front: academic
literature is blunt that liveness detectors generalize badly cross-dataset (~45-48% error rate, near
coin-flip, when tested on a spoof-attack type the model wasn't trained on).

Built as a new standalone tool at `/tools/face-liveness` — first webcam-capture feature in this
codebase (`useWebcam.ts`, from scratch, no prior `getUserMedia` precedent anywhere), with an upload
fallback. Backend `mm_liveness.py` reuses the existing OIV7 face detector for the crop, runs the
anti-spoof model, returns a real/spoof verdict. Live-verified end-to-end via Playwright before
deploying (real face → "Looks live" 99.4%; no-face photo → correctly reports no face, no guessing) —
then deployed and reverified against the live HF Space directly.

**User then tested it live with their own actual webcam and reported a genuinely live face scored
"spoofed."** Debugged with real evidence rather than accepting the known-limitation caveat as an
excuse: tested JPEG recompression alone (didn't reproduce it), then systematically tested resolution/
brightness/contrast/mirroring differences between a clean stock photo and realistic webcam conditions.
Reproduced it: downscaling + dimming + lowering contrast on the SAME photo that scored 99.4% "real"
dropped it to 52.4% and flipped the verdict — a near coin-flip, not a confident wrong answer. Tried
CLAHE (adaptive histogram equalization) as a preprocessing fix — it flipped the verdict back to "real"
but only at 50.7%, confirming the real problem isn't fixable with preprocessing: the model's actual
signal collapses under exactly the lighting/contrast a webcam produces, matching the cross-dataset
caveat that was already disclosed before building.

**Real fix, not a workaround:** changed the backend to return a raw signed `real_score` (0-1) instead
of a pre-decided bool+confidence split, so results from multiple frames can be properly averaged.
Frontend now captures 4 frames (~1s apart) and averages the score; a result within 15 points of 50/50
now shows an honest "Uncertain — try better lighting" state instead of a falsely confident verdict
either way, matching how the existing tampering detector already avoids overclaiming with Low/Medium/
High tiers rather than a binary. Reproduced the exact reported failure with a synthetic degraded image
and confirmed the fix: same image that previously flipped to false "Looks spoofed" at 52% now correctly
shows "Uncertain, 48% real-leaning" — screenshot-confirmed, then deployed and reverified live against
the HF Space (`real_score: 0.994` on the known-good test photo, new response shape confirmed live).

## Commit hashes (chronological, this session)

**ML-Unified (backend):**
1. `9d76cc8` — per-class Box confidence threshold + `oiv7_classes.py` split
2. `ff47d62` — real uncapped `person_count` for crowd density
3. `6906792` — `mm_liveness.py` face liveness endpoint (new)
4. `48c25b3` — `mm_liveness.py` raw `real_score` fix (multi-frame averaging support)

**ml-portfolio (frontend):**
1. `6cd862d` — weapon detection base feature
2. `1da97ac` — weapon detection Bomb/Missile addition
3. `fa68ef3` — weapon detection user-guide cleanup
4. `e35f576` — package/parcel/delivery → Box synonym mapping (video doorbell)
5. `0f9adb9` — stale-citation-after-source-removal fix
6. `cfb578a` — crowd density counter UI
7. `5d32f2c` — restricted-zone plate enforcement
8. `bf8ad8c` — Face Liveness Detector new standalone tool
9. `3871676` — face liveness multi-frame averaging + "uncertain" state fix

## Memory changes this session

- `project_pending_master_list.md` updated repeatedly: weapon detection, video doorbell, crowd
  density, and restricted-zone plate enforcement all moved from the pending table into the "already
  done" section with commit hashes and real findings. Fire/smoke detection marked **Blocked** (not
  removed) with the specific rejection evidence, so it isn't silently re-attempted later. Added rows
  36-53 (18 new items) from the two rounds of CV brainstorm/cybersecurity research, severity-ranked
  where applicable. Face Liveness Detector was picked and built directly, not added to the table first.
- The Ultralytics/AGPL licensing risk and the "accept for now" decision were discussed at length but
  are NOT yet written into a dedicated memory file — worth doing in a future session so this doesn't
  get re-litigated from scratch (the full reasoning and evidence trail lives in this session's
  transcript and this log).

## Pending / not yet resolved

Rows 27, 29, 31-53 of `project_pending_master_list.md` remain untouched: Sports form tracker, PPE
compliance check, Source camera ID (PRNU), Crime scene reconstruction (SfM), Gait analysis, plus all 18
items from this session's CV brainstorm/cybersecurity research (deepfake fraud detection, face-
recognition deanonymization demo, adversarial examples attack+defense, video-call keystroke inference,
steganography detection, malicious QR/phishing detection, CAPTCHA research, 3D Gaussian Splat scanner,
SAM3 rotoscope, Depth Anything parallax toy, home biomechanics coach, wildlife re-identification,
personal photo search, pose-driven generative visuals, backyard astrophotography, plant growth
quantification). No build decision made on any of these. The Ultralytics/AGPL exposure across the
existing detector is a settled "accept for now" decision, not open, but should get its own memory file
for continuity across future sessions.
