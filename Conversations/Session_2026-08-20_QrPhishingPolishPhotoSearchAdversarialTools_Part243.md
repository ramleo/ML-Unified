# Session 2026-08-20 — QR Phishing polish, Photo Library Visual Search, Adversarial Examples

Continuation from Part 242. This session closed out the QR Phishing Detector's second
feature round, then shipped two brand-new standalone tools end to end: Photo Library
Visual Search (CLIP-based) and Adversarial Examples (attack + defense demo). Every
feature below was verified live against the real deployed HF Space endpoint (not just
`stage: RUNNING`) and, for frontend changes, against a real running local UI via
Playwright before being reported done.

## 1. QR Phishing Detector — non-URL payload handling

User asked for a web-researched feature list for the QR Phishing Detector. Recommended,
in order: handle non-URL QR payloads (low effort, real functional gap) > scan history >
CSV export > Certificate Transparency check > URLhaus (deprioritized, redundant with
Safe Browsing already shipped). User approved starting with non-URL payloads.

`mm_qr_phishing.py` had grown to 380 lines — over the project's 350-line modularize
threshold — so the Safe Browsing/RDAP/brand-list/root-domain logic was split into a new
`mm_qr_phishing_reputation.py` first (one-way import, no cycle), before adding the
feature.

Added `_detect_payload_type()` — regex-matches WIFI:/BEGIN:VCARD-MECARD:/mailto:/tel:/
(sms|smsto):/geo:/BEGIN:VEVENT prefixes and returns a human label ("Wi-Fi network
credentials", "Contact card", "Email address", etc.), falling back to "Plain text" for
anything unrecognized. A WIFI payload gets an extra medium-risk caution note (scanning
it auto-joins a network).

**Real bug found and fixed while testing**: `mailto:someone@example.com` was being
misparsed as a URL. `urlparse("http://mailto:someone@example.com")` reads "mailto:someone"
as URL userinfo and "example.com" as the host, wrongly triggering the "@" auth-trick
high-risk flag on an ordinary email QR code. Fixed by checking known non-web-scheme
prefixes BEFORE attempting URL parsing, not after — the previous code only checked
non-URL-ness after a failed urlparse, by which point mailto: had already "succeeded" as
a bogus URL.

Verified: 8 real-URL regression cases (typosquat, IP-literal, @-trick, shortener,
suspicious TLD, punycode, clean, bare domain) all scored identically after the fix;
all 7 non-URL payload types + the mailto fix confirmed via direct function calls, then
via the real running local server, then live on the deployed HF Space (WIFI caution and
the mailto fix both re-verified against `https://wram1708-ml-unified.hf.space` directly).

Commits: ML-Unified `75f0683` (payload handling + reputation-module split, HF-uploaded)
→ ml-portfolio `e5550a9` (payload-type UI).

## 2. QR Phishing Detector — scan history (localStorage)

Researched Document Intelligence's existing "Recent documents" pattern via a background
agent before building, to stay consistent rather than inventing a new pattern. Built
`QrScanHistory.tsx` — localStorage key `qr_phishing_history_v1`, last 5 entries, same
load/save/clear shape as `DocHistory.tsx`. Stores the result only (no image preview);
clicking an entry re-displays the saved result via new `restoreFromHistory()` in
`useQrPhishingScan.ts`, without re-running Safe Browsing/RDAP. Pure frontend, no backend
change.

Verified live: scanned a URL, reloaded the page, confirmed the entry persisted and
showed under "Recent scans"; clicked "View again" and confirmed the exact saved result
reappeared; clicked "Clear" and confirmed the panel disappeared.

Commit: ml-portfolio `6e2d115`.

## 3. QR Phishing Detector — CSV export

`QrPhishingCsv.tsx` — identical `csvCell`/`downloadCsv` (Blob + throwaway anchor,
RFC-4180 quote-escaping) pattern as Plant Growth's `PlantGrowthCsv.tsx`. One row per
decoded QR result across the whole current batch. Verified via Playwright's real
download interception (not just a click): confirmed the downloaded file's actual
content, including correct escaping of embedded double quotes in a typosquat reason
string.

Commit: ml-portfolio `b3b265f`. This closed the QR Phishing feature-brainstorm round —
only URLhaus (deprioritized) and Certificate Transparency (see below) were left
deliberately unbuilt.

## 4. Certificate Transparency (crt.sh) check — tried, rejected on reliability

Next pending item was a CT check via crt.sh. Before writing any code, live-tested
crt.sh's JSON API against several real domains and got three DIFFERENT failures
(timeout, 404, 502 Bad Gateway) across identical requests within 30 seconds — not
query-specific, a real service-reliability problem, not a bug on this end. Surfaced this
finding to the user before proceeding rather than assuming it would work; user chose to
skip crt.sh and build scan history instead (see §2). Do not re-attempt without new
evidence of improved reliability.

## 5. New tool: Photo Library Visual Search

Asked to pick from the pending master list; recommended and built (user-approved,
plan-first) **Photo Library Visual Search** — item #50 from the CV brainstorm, reframed
around CLIP (`clip-ViT-B-32`, same model as `mm_similar.py` but its own lazy singleton
to stay decoupled). New backend module `mm_photo_search.py`, new tool at
`/tools/photo-search`.

**Base build**: stateless, one-shot — a single request carries the whole photo batch
AND a text query together, ranked by cosine similarity, no vector DB (not a persistent
corpus, just a batch job). Match percentage badges are min-max normalized WITHIN the
batch/search, not raw cosine score — raw CLIP cosine similarities sit in a narrow
~0.15-0.35 band even for a correct top match, which would read as a "low/broken" score
shown directly. Verified with synthetic red/blue/green squares: correct ranking for
multiple queries, confirmed via direct function calls, the real running server, local
Playwright, and the live deployed HF Space.

**Image-to-image search ("Find similar")**: researched real CLIP-search tools first
(rclip, various CLIP+FAISS demos) — image-to-image search was the most commonly cited
complementary feature to text search. Added `query_image` (base64 reference photo,
mutually exclusive with `query`) and `exclude_filename` (so the reference photo doesn't
appear in its own results — both land in the same embedding space, so ranking logic is
identical regardless of query source). Click "Find similar" on any uploaded photo;
reference photo gets pinned first, outlined, labeled "Reference photo" instead of
scored. Verified live: two similar reddish photos + one blue, clicking "Find similar" on
the first red one correctly excluded itself and ranked the second red photo above blue,
confirmed on the real deployed endpoint.

**Duplicate detection**: `find_duplicates()` — groups near-identical photos by CLIP
cosine similarity, no query needed, reuses the same embeddings. Threshold 0.97, chosen
after research confirmed it sits inside the commonly-cited 0.95-0.99 range for CLIP
dedup — NOT tuned from this tool's own synthetic tests, which turned out to be
misleading: solid-color and random-noise test images are out-of-distribution for CLIP
and compress similarity unnaturally (a recompressed "duplicate" noise image scored
LOWER than an unrelated random-noise image, 0.9555 vs 0.9894). Documented this finding
directly in the code comment rather than silently picking a threshold from bad
synthetic evidence. Verified live: two identical synthetic photos grouped, a third
distinct photo correctly excluded, on the real deployed endpoint.

**Negative/exclude terms**: researched CLIP exclusion-query techniques (published
"average embedding subtraction" method: embed(A) − embed(B)). Implemented as: normalize
both the query and exclude-term embeddings, subtract the exclude direction from the
query direction, re-normalize. Applies after either a text or image query since by that
point it's just a vector. This is a STEER, not a hard filter — documented as such.
Verified with three colored squares: excluding "red color" from "a colorful square"
dropped the red photo from a competitive middle score (0.2484) to dead last, even
negative (−0.0472), confirmed on the real deployed endpoint.

Commits: ML-Unified `3638284` (base) → `ba4954f` (image-to-image) → `ae57143`
(duplicates) → `c18fcd2` (exclude terms), each HF-uploaded and verified live before the
next round started. ml-portfolio `3e33074` (base tool) → `e71335b` (find-similar UI) →
`44e257e` (find-duplicates UI) → `2e08091` (exclude-terms UI).

## 6. Pending master list — two stale rows found and removed

While preparing to recommend the next feature, grepped the actual `src/app/tools/`
directory before trusting the pending table (per the standing lesson from earlier
sessions) and found two stale rows: **#38 Face liveness/anti-spoofing** was already
shipped as `/tools/face-liveness`, and **#47 Depth Anything parallax** was already
shipped as `/tools/depth-parallax`. Removed both rows from the pending table and added a
note explaining why, rather than silently leaving them to be re-offered later.

## 7. New tool: Adversarial Examples (attack + defense demo)

User picked item **#40 Adversarial examples: attack + defense demo** from the pending
list. Before planning, confirmed `torch`/`torchvision` were ALREADY present in the
deployed environment as transitive dependencies of `timm` (already pinned for
`mm_tables.py`) — so nothing new needed adding to requirements, materially de-risking
the plan. Presented a full plan (FGSM/PGD attack, JPEG-recompression defense,
MobileNetV2 classifier) and got explicit go-ahead before writing code.

**Backend** (`mm_adversarial.py`, new): pretrained MobileNetV2 (ImageNet-1000) as the
target classifier — a generic off-the-shelf model, explicitly NOT any model used
elsewhere in this codebase, so the demo is illustrative of a general ML-robustness
property, not an attack on this app's own tools. FGSM (single gradient step) and PGD
(iterative, projected onto the epsilon L∞ ball) attacks, both untargeted — real gradient
access required, unlike this codebase's other CV tools which only need ONNX forward-pass
inference.

**Real, honest finding during testing, changed the whole framing**: initial testing on
synthetic gradient images showed inconsistent defense results; testing on a REAL photo
(matplotlib's bundled `grace_hopper.jpg` test image, found by searching the local
environment for bundled sample photos since none were otherwise available) revealed the
JPEG-recompression defense almost NEVER fully recovered the original correct label
across an entire epsilon/quality sweep (18 combinations tested), even at aggressive
JPEG quality=10. For FGSM specifically at low epsilon, the defended prediction was
IDENTICAL to the raw adversarial one — literally zero effect. Rather than picking
favorable parameters or overselling the defense, rewrote the module docstring and added
a second `disrupted` field (defended prediction differs from the adversarial one, a
weaker "had some effect" signal, decoupled from full `recovered` label match) to report
this honestly. The frontend explicitly frames this as the actual point of the demo, not
a bug — "the defense had no measurable effect" / "disrupted, not recovered" are real,
expected, honestly-labeled outcomes, not error states.

**Frontend**: new tool at `/tools/adversarial-examples` — upload a photo, pick
FGSM/PGD, set epsilon (strength) and JPEG quality via sliders, see a 4-panel comparison
(Original / Adversarial / After JPEG defense / amplified-×8 perturbation visualization)
with color-coded badges (Fooled / Not fooled; Recovered / Disrupted, not recovered / No
effect).

Verified live end-to-end (local function calls → real local server → local Playwright →
live deployed HF Space, including a real request that also exercised the Space's
first-time MobileNetV2 weight download): `bow tie` (51%) → FGSM-fooled to `mortarboard`
→ JPEG-defended lands on `academic gown` (disrupted, not recovered) — identical results
locally and on the real deployed endpoint.

Commits: ML-Unified `23e43e6` (FGSM/PGD + JPEG defense, HF-uploaded, verified live
including confirming the Space actually classifies a real photo correctly, not just
`stage: RUNNING`) → ml-portfolio `1c96725` (tool UI).

## 8. Adversarial Examples — feature research, then Grad-CAM heatmap

User asked for web research on further Adversarial Examples features. Researched
AdVis.js (the reference interactive adversarial-demo tool), IBM's Adversarial
Robustness Toolbox (55+ attacks/30+ defenses across evasion/poisoning/extraction/
inference), and the certified-robustness/randomized-smoothing literature. Recommended,
in priority order: **Grad-CAM saliency heatmap** (reuses gradient access already
built, the headline feature of the reference tool) > targeted attack mode (small code
delta, big demo payoff) > randomized smoothing as a second, more principled defense
(directly answers the honest gap the JPEG-only defense left open) > transferability
test against a second model. Deprioritized adversarial patches and black-box attacks as
higher-effort — user asked whether those were even feasible; confirmed both ARE
buildable later (same MobileNetV2, no new dependency) but cost meaningfully more compute
per request (patches: ~100-300 iterations vs. PGD's ~10; true black-box attacks need
hundreds-to-thousands of query-only forward passes, which would be slow on CPU and
noticeably weaker within a reasonable request timeout — itself an honest finding worth
reporting if built).

User approved building Grad-CAM. Added `_grad_cam()` — hooks MobileNetV2's last conv
block (`model.features`) forward output, backpropagates the predicted class's logit,
weights each activation channel by its global-average-pooled gradient, ReLU, upsamples
to image size — the standard Grad-CAM formulation. Rendered as a JET-colormap overlay
via `cv2.applyColorMap` (opencv-python-headless already a dependency, no new
requirement). Computed for both the original prediction (target = original's own top-1
class) and the adversarial prediction (target = adversarial's own top-1 class), so the
two heatmaps show what actually justified EACH prediction, not the same target twice.

Verified visually before shipping: for the Grace Hopper test photo, the original
"bow tie" heatmap correctly highlighted the neck/tie region; the adversarial
"mortarboard" heatmap showed attention shifted almost entirely to the military cap —
genuinely striking, exactly the kind of concrete "why was it fooled" moment the feature
was meant to produce. Verified live end-to-end (real photo, real local server, local
Playwright screenshot showing the rendered heatmap comparison, then confirmed
non-empty `heatmap` fields on the real deployed HF Space endpoint).

Commits: ML-Unified `c1fe241` (Grad-CAM backend, HF-uploaded, verified live) →
ml-portfolio `5bd8f57` (heatmap comparison UI).

## How to apply going forward

- **A non-URL/non-http scheme (mailto:, tel:, etc.) must be checked BEFORE falling back
  to a fabricated "http://" prefix for scheme-less URL parsing** — `urlparse` will
  happily misread a scheme-like prefix as URL userinfo once "http://" is prepended,
  producing a plausible-looking but wrong host. Any future free-text/payload-type
  feature needs known non-web schemes checked first, not "no false host means it's
  fine."
- **Test a free external API's actual live reliability before writing code against
  it, not just its docs or reputation** — crt.sh looked equivalent to RDAP on paper but
  failed 3/3 live probes differently within a minute; surfacing that BEFORE building
  saved a feature that would have silently no-op'd during outages far more than
  RDAP/Safe Browsing do.
- **Synthetic test images (solid colors, random noise) can be worse than no test at
  all for calibrating a similarity/dedup threshold** — CLIP embeds out-of-distribution
  inputs unnaturally close together regardless of real content; a real, structured photo
  (even one incidentally bundled with an unrelated library, like matplotlib's
  `grace_hopper.jpg`) is a far better proxy, and grounding a threshold in the published
  literature (0.95-0.99 for CLIP dedup) beats guessing from misleading synthetic
  evidence.
- **A "defense" or mitigation feature should report its REAL, measured effectiveness,
  even when that's an honest "mostly doesn't work"** — the JPEG-recompression defense
  for adversarial examples was tested across a real parameter sweep before shipping and
  found to rarely fully recover the correct label; the tool ships that finding directly
  in its copy and adds a softer `disrupted` signal instead of only reporting the strict
  `recovered` outcome, matching this project's established honesty pattern (RDAP,
  region-sharpen classifier corroboration, watermark limits) rather than only shipping
  favorable parameter combinations.
- **Before adding a new heavy dependency (torch/torchvision for gradient-based
  attacks), check whether it's already a transitive dependency of something already
  pinned** — `timm` (for `mm_tables.py`) already required `torchvision`, so the
  Adversarial Examples tool needed zero new requirements-file entries, which was
  confirmed BEFORE planning the feature, not discovered as a surprise mid-build.
- **Grep the actual `src/app/tools/` directory before trusting the pending master
  list's own status text** — two more stale "not started" rows (face liveness, depth
  parallax) were found already-shipped this session; this is now a recurring pattern
  worth checking reflexively before recommending from that table, not just when asked
  "what's pending."
- **When a user asks "can X still be done" about a deprioritized option, answer the
  feasibility question directly and concretely (what it would cost, what dependencies
  it needs) rather than just re-affirming the recommended alternative** — this keeps the
  door open for later without re-litigating the current choice.
