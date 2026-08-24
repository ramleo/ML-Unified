# Session 2026-08-21/22 — Style Cloak Tool + Adversarial Training Defense (Part 247)

Continuation of the same day as Part 246 (Adversarial Robustness Lab expansion +
Face Cloak), picked up after a `/compact`. Shipped a second privacy-cloaking tool
(Style Cloak, the Glaze/Nightshade counterpart to Face Cloak), then added a
genuinely different-shaped third defense (adversarial training) to the
Adversarial Robustness Lab, then extended that defense with a real photo-upload
path, then fixed stale doc references the new defense introduced.

Tags: `style-cloak`, `mm_style_cloak`, `CLIP`, `clip-vit-base-patch32`, `Glaze`,
`Nightshade`, `cosine-similarity-calibration`, `adversarial-training`,
`mm_robust_training`, `Madry`, `PGD-adversarial-training`, `MNIST`, `TinyCNN`,
`photo-upload-preprocessing`, `digit-classifier`, `user-guide-staleness`,
`HF-Space-deploy`, `Part247`, `continuation-of-Part246`

---

## 1. Resolving an ambiguous "next item" handoff across `/compact`

Before compacting, the user said "we will start next item in pending list for
Adversarial" without specifying which list — the Adversarial Robustness Lab's own
backlog was already fully closed (Part 246), so this could have meant the
broader pending-master-list security cluster instead. An `AskUserQuestion` sent
just before compaction came back garbled (an echoed copy of an earlier assistant
message, not a real answer). After compaction, the user clarified by pointing
back at an earlier web-research use-case list (autonomous-vehicle stickers,
financial fraud evasion, spam filter evasion, facial-recognition bypass,
malware/IDS evasion, Fawkes, Glaze/Nightshade, adversarial training, CAPTCHA
design, watermarking) and said "proceed with Glaze/Nightshade-style artist
protection as the next build" — resolving the ambiguity to a specific, concrete
next feature.

---

## 2. Style Cloak — Glaze/Nightshade-style artist protection

Same real technique family as Face Cloak (adversarial repulsion against an
embedding model) but protecting artwork/images from AI **style-mimicry**
instead of protecting faces from **recognition**, and whole-image instead of
face-crop-only (style is a property of the entire image, no sub-region to
isolate).

**Feasibility work done before writing production code** (per this project's
established pattern):
- Confirmed `transformers` (already a base dependency via `mm_similar.py`'s
  sentence-transformers CLIP usage) supports a fully differentiable CLIP image
  encoder path (`CLIPModel.get_image_features`), gradients flow from pixels to
  embedding.
- Real local test: untargeted repulsion (minimize cosine similarity to the
  original embedding) dropped cosine similarity from 1.0 to -0.36 in under 2
  seconds at epsilon=0.06, 40 steps.
- **Real calibration finding, not guessed**: measured cosine similarity between
  three totally UNRELATED synthetic images in CLIP embedding space — 0.65 to
  0.77. This is much higher than face-embedding space (where different people
  can go negative), because CLIP embeddings share generic visual/scene
  structure even across unrelated content. This directly shaped the protection
  thresholds (`_STRONG_THRESHOLD = 0.5`, `_MODERATE_THRESHOLD = 0.75`) —
  deliberately NOT copied from Face Cloak's face-embedding thresholds.
- Local environment note: `transformers`/`sentence-transformers` were not
  installed in the local dev venv despite being in `requirements-base.txt`;
  installed via `pip install --no-deps` plus manually resolving a
  `huggingface_hub`/`tokenizers` version conflict (`huggingface_hub<1.0,>=0.24.0`,
  `tokenizers>=0.21,<0.22`) to get a working local `transformers==4.48.3` for
  testing — same SSL_CERT_FILE workaround as prior sessions for the CLIP weight
  download.

**Backend** (`services/ml-api/routers/rag/mm_style_cloak.py`, 209 lines):
`_ensure_loaded()` lazy-loads `openai/clip-vit-base-patch32` (MIT license,
~600MB); `_embed()` resizes to 224×224 and L2-normalizes; `_cloak()` runs
40-step epsilon-bounded gradient-ascent-on-cosine-distance (same shape as
`mm_face_cloak.py`'s repulsion loop, but whole-image, no mask); `_protection_label()`
uses the CLIP-specific thresholds above. `CloakRequest{image, epsilon=0.06}` →
`POST /mm-style-cloak/run`. Verified end-to-end locally (cosine -0.3574,
"strong") before deploying.

**Frontend** (`ml-portfolio/src/app/tools/style-cloak/`, new directory):
`page.tsx` (pink accent `#ec4899`, distinct from Face Cloak's purple),
`useStyleCloak.ts`, `StyleCloakRunner.tsx`, `StyleCloakUserGuideModal.tsx`,
`userGuide.ts` — structure mirrors Face Cloak exactly. Added a `capabilities.ts`
card (`Security & Trust` domain, model `CLIP ViT-B/32 (local)`).

Deployed and live-verified: real HTTP call to the HF Space returned 200,
cosine similarity -0.4186, "strong". Commits: `0019547` (backend),
`8fe8e65` (frontend).

---

## 3. Adversarial training — the third defense, a different shape entirely

User picked "Adversarial training defense" (recommended over two new-tool
alternatives — deepfake detection, steganography detection) as the next build,
framed explicitly as extending the Adversarial Robustness Lab rather than a new
standalone tool.

**Key design constraint surfaced immediately**: the existing tool's classifier
is a pretrained 1000-class ImageNet MobileNetV2 — genuinely re-running
adversarial training against that model per-request (or even per-deploy) is
infeasible on a CPU-only Space; real adversarial training needs many epochs
over a real dataset. Decided to scope this down honestly to a **separate small
digit classifier (MNIST)**, trained ONCE offline and shipped as static
checkpoints — not a live training path, and not the same domain as the rest of
the tool (disclosed directly in the module docstring, not hidden).

**Real training run performed this session** (not simulated, not guessed) —
TinyCNN (~110K params), 3 epochs each, same architecture/data, only the
training procedure differs:
```
STANDARD model:       clean accuracy 98.62%  →  robust accuracy  1.09%  (PGD eps=0.2)
ADVERSARIAL-trained:   clean accuracy 96.98%  →  robust accuracy 84.30%  (same attack)
```
The standard model is almost completely fooled; the adversarially-trained model
gives up ~13 points of clean accuracy for a massive, real robustness gain — the
actual, honest trade-off adversarial training makes, demonstrated with real
numbers rather than asserted.

Checkpoints (`mnist_standard.pt`, `mnist_adversarial.pt`, ~427KB each) copied
into `services/ml-api/models/`. Ten real MNIST test-set sample digits (one per
label, chosen once offline) baked into `mm_robust_training_samples.py` as base64
constants (~4KB) — no dataset download at request or deploy time.

**Backend** (`services/ml-api/routers/rag/mm_robust_training.py`, 197 lines
initially): `TinyCNN` class, `_ensure_loaded()`, `_pgd_attack()` (20 steps at
inference vs. 7 during training — a stronger, fairer attack for the demo),
`_run_one_model()` (attacks each model independently, white-box, with its OWN
gradients — the strongest fair attack per model, since the optimal direction
differs between them). `GET /mm-robust-training/samples`,
`POST /mm-robust-training/run`. Verified locally (real attack: standard model
0→9, fooled; adversarially-trained model 0→0, resisted) before deploying.

**Frontend**: new `RobustTrainingDefense.tsx` + `useRobustTrainingDefense.ts`
(kept as separate files rather than extending the already-338-line
`AdversarialRunner.tsx`, to stay under the 400-line ceiling), mounted as a new
section below the existing runner in `page.tsx`. Sample-digit picker (10
thumbnails), epsilon slider, side-by-side "Standard-trained model" /
"Adversarially-trained model" panels with Fooled/Resisted badges. Updated
`userGuide.ts` (new "Adversarial training" section) and `TOOL_SUMMARY` /
`capabilities.ts` description to cover it.

Deployed and live-verified: real HTTP call reproduced the same fooled/resisted
pattern (0→9 vs. 0→0) against the live Space. Commits: `d9359d3` (backend, incl.
checkpoints), `b26e8bf` (frontend).

---

## 4. "how can I verify?" → "how can I check with my own image?"

User asked how to verify the new defense worked — answered with concrete
click-by-click steps and what to expect (red "Fooled" badge on standard,
green "Resisted" on adversarially-trained).

User then asked to test with their own image. Initial `AskUserQuestion` ("add
upload support?") got answered with a clarifying question instead — "is this
only about digits?" — which needed a direct answer before proceeding: yes, this
specific defense section is scoped to MNIST digits (for the compute-feasibility
reason above), but the REST of the tool (main attack section, first two
defenses) already accepts any photo upload today, no changes needed there. A
second `AskUserQuestion` disambiguated which the user actually wanted (the
digit-classifier defense) before building.

### Upload path added to the adversarial-training defense
**Backend**: `_preprocess_upload()` — grayscale, auto-invert (if mean pixel
intensity > 127, assume light-background photo and invert to MNIST's
digit-bright-on-dark convention), crop to the ink's bounding box with 15%
padding, center on a square canvas, resize to 28×28 via PIL bilinear. Real test
with a synthetic "photo of pen-on-paper" image (white background, dark "3"
drawn via PIL/Arial) — preprocessing produced a clean, correctly-centered
28×28 digit, verified visually via the saved preview PNG, and both models
correctly classified it before attack. New `UploadRunRequest{image,
intended_label, epsilon}` → `POST /mm-robust-training/run-upload`, returning
the preprocessed preview image alongside both models' results (same
`_run_one_model` used for both sample and upload paths). Honest module-docstring
caveat: an uploaded photo is real out-of-distribution input for a model trained
only on clean MNIST — the clean prediction itself may occasionally be wrong,
disclosed via the returned preview rather than hidden. File grew to 279 lines
(still under the 400-line ceiling).

**Frontend**: `useRobustTrainingDefense.ts` gained a `mode: "sample"|"upload"`
toggle, upload state (`uploadPreview`, `uploadB64`, `intendedLabel` 0-9
picker), and routes `run()` to the appropriate endpoint. `RobustTrainingDefense.tsx`
gained a tab switcher, file input, digit-label `<select>`, and a "what the
models actually saw" preprocessed-image preview alongside the results.
Updated `userGuide.ts` to document the upload path and its out-of-distribution
caveat.

Deployed and live-verified: real HTTP call with a synthetic photo of a drawn
"5" returned correct clean predictions for both models (5, 5), standard model
fooled under attack (5→3), adversarially-trained model resisted (5→5).
Commits: `88d824d` (backend), `108b2ef` (frontend).

---

## 5. User guide update — real staleness found again

User asked to update the user guide (third time this feature area has
triggered this ask — see Part 246). Full re-read (not just incremental diffing)
surfaced two genuine stale spots, both artifacts of the third-defense addition:
- The tool overview still said "tries two candidate **defenses**" — fixed to
  "two inference-time **defenses**" plus a pointer to the new third section.
- "Notes & limits" still said "all four attacks, and **both** defenses" —
  fixed to "all three defenses."
Also added a missing note about the uploaded-photo 8MB size cap and automatic
preprocessing. Commit `1659af3` (frontend-only doc fix, no backend `.py`
change, so no HF Space upload needed this time).

---

## Pending / backlog state at end of session

- Adversarial Robustness Lab: attack side (FGSM, PGD, patch, black-box, targeted
  variants) and defense side (JPEG recompression, randomized smoothing,
  adversarial training w/ upload) are both now feature-complete relative to
  every item discussed this session and Part 246. No open items specific to
  this tool.
- Broader pending-master-list security/adversarial cluster items not yet built:
  deepfake detection, steganography detection, video-call keystroke inference,
  CAPTCHA-solving research (offered as alternatives to adversarial training this
  session, not chosen).
- Real-world adversarial-ML use-case list (from the earlier web-research turn)
  — remaining unbuilt items: financial fraud evasion, spam filter evasion,
  facial-recognition bypass (attack side), malware/IDS evasion, CAPTCHA design.
  Fawkes (Face Cloak) and Glaze/Nightshade (Style Cloak) are both now done;
  adversarial training is also now done (as a defense, not from that list
  originally, but fulfills the "adversarial training" list item too).
