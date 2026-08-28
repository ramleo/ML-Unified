# Session 2026-08-27 (Part 259) — Rotoscope deploy resumed, four new CV tools shipped

Continues directly from Part 258, which ended paused mid-deploy on #46
(SAM3 rotoscope, rescoped to Grounded-SAM) with a real torch version
conflict between `sam2` and `facenet-pytorch`, waiting on the user's
explicit go-ahead to resume.

## 1. #46 resumed and shipped

Applied the proposed fix: installed `facenet-pytorch` with `--no-deps` in
the Dockerfile (same pattern already used for `groundingdino-py`/
`supervision`), letting torch resolve freely to satisfy `sam2`'s
`torch>=2.5.1` floor instead of being pinned down by facenet-pytorch's
stale `torch<2.3.0` ceiling. Deployed successfully — no `BUILD_ERROR`
this time. Verified, not assumed, that this didn't silently break the
two existing facenet-pytorch-dependent tools: live-called Face Cloak
(real photo → correct face detection, cosine similarity −0.769, "strong"
protection) and Face Re-ID Demo (same photo vs. itself → 1.0 "same";
no-face photo → correctly reports no face) against the deployed HF Space.

Verified the actual rotoscope pipeline end-to-end: a synthetic drawn-
square test clip gave Grounding DINO a bad near-whole-frame box (expected
— it's not trained on flat programmatic shapes, not a pipeline bug).
Re-tested with a real photo (a flower, animated into a zoom-video test
clip): Grounding DINO localized it at 80% confidence and SAM2 correctly
tracked/masked just the flower (not the leaves or a second bud) through
all 16 frames — confirmed both locally and live on the deployed site via
Playwright.

**Real limitation found via live testing, not assumed away**: prompting
with "the elephant" on the flower photo (no elephant present) still
returned a confident-looking tracked mask (73% confidence) instead of the
originally-claimed "couldn't find" error — Grounding DINO has no reliable
"nothing matches" signal, it always returns its best guess. The User
Guide had claimed this failure path was reliable, based on an earlier
test against a different image — caught before calling #46 done, and
corrected to honestly disclose that a wrong prompt can silently produce a
wrong-but-plausible-looking result.

Backend `services/ml-api` commits `26e629c`, `26e629c`; frontend
`ml-portfolio` commits `00b5789` (UI), `d429ae3` (overclaim correction).
Pending master list updated marking #46 fully done.

## 2. Two small fixes, on request

- **"Why can't I find #46 in the UI?"** — it's live, just not labeled
  "SAM3" or "rotoscope" anywhere (deliberately, since it's genuinely not
  SAM3) — titled "Text-Prompted Video Object Tracking" with a
  "Grounded-SAM" badge, under Computer Vision.
- **"Why is there no User Guide for Movement Form Comparison?"** — that
  tool predates the "User Guide + ToolsAIChat wired in from the start"
  convention that became standard partway through this project. Added
  both, matching the established pattern (`userGuide.ts`,
  `MovementComparisonUserGuideModal.tsx`, wired into `page.tsx`).
- **Alphabetized tool cards** within each domain section on the homepage
  — a one-line fix in `MLCapabilities.tsx` (`.sort((a, b) =>
  a.title.localeCompare(b.title))` on the per-domain `items` array)
  rather than manually reordering the ~40-entry `capabilities.ts` source
  array. ml-portfolio commit `3d70098`.

## 3. #52 Astrophotography Anomaly Detector — done

Genuinely CPU-friendly, unlike most of the recent CV backlog: pure
classical OpenCV (frame differencing + Hough transform), no neural
network. Researched first and confirmed this is the real, published,
operational technique for meteor/satellite-trail detection (not invented
for this project) — the key discriminator is that a star's slight
frame-to-frame drift leaves a **dipole** (paired +/- streak) in the
signed difference image, while a transient meteor/satellite leaves a
**monopole** (one-sided). Also returns a median-stacked "clean" image
(median, not mean, since it rejects the very transients being detected).

Two real bugs caught during the mandated synthetic-ground-truth
verification pass (no real astrophotography session existed in this
environment, disclosed up front): (1) an initial percentile-based
adaptive threshold broke down on a sparse star field — switched to
Otsu's method; (2) an attempted meteor-vs-satellite classifier (using
position drift between adjacent-pair detections) was tested and found
fundamentally unreliable — a satellite's frame-to-frame shift is almost
entirely *along* its own line direction, geometrically near-identical to
a stationary flash using drift alone. Rather than ship a fragile,
unvalidated classifier, simplified to one honest label ("possible meteor
or satellite trail") for every detection.

Verified against synthetic ground truth (zero false positives on a
50-star drifting field, both an injected meteor and an injected
multi-frame satellite crossing correctly detected, median stack fully
suppressing both transients) before writing any FastAPI/frontend code.
Confirmed real CPU speed: 15 frames at 1600x1200 with 300 stars processed
in 0.06s. Verified live end-to-end on the deployed HF Space and via
Playwright on the live Vercel site. Backend `services/ml-api` commit
`0c91122`; frontend `ml-portfolio` commit `d80a6e7`.

## 4. #49 Wildlife Re-Identification — done, rescoped from DINOv3

Researched before building: **MegaDescriptor** (BVRA/MegaDescriptor-
T-224, from the open-source WildlifeDatasets toolkit) is the first
foundation model built specifically for individual animal
re-identification, published to outperform generic embeddings like CLIP
and DINOv2 on this exact task — picked the purpose-built model over the
originally-brainstormed generic DINOv3 embedding. No new dependency
(`timm` already present, loads via `timm.create_model("hf-hub:BVRA/
MegaDescriptor-T-224", ...)`). Reuses the existing 601-class OIV7 object
detector to crop the animal out of each photo before embedding, mirroring
the already-shipped `mm_face_reid_demo.py`'s target+gallery cosine-
similarity shape almost exactly.

License flagged explicitly: MegaDescriptor is CC-BY-NC-4.0
(non-commercial) — judged a comfortable fit for this non-commercial
educational portfolio, comparable to the AGPL-3.0 tradeoff already
accepted for the YOLO object detector.

Verified with real photos already present on the machine (no genuine
backyard-camera-trap dataset existed, disclosed to the user): two
different goldfish photographed side-by-side in one real photo, cropped
into separate individual-fish photos, scored 0.60 cosine similarity via
the actual detect-crop-embed pipeline (correctly labeled "different");
the same fish crop compared to itself scored 1.00 ("same"). A real
finding along the way: a tiny/upscaled avatar-style cat photo (48px
native) was NOT detected as an animal at all — too little native detail,
confirming detection quality is a real gate on this tool, disclosed
rather than hidden. Same/uncertain/different thresholds explicitly
disclosed as informed by this one real test, not a calibrated
multi-individual benchmark. Verified live end-to-end (HF Space + Vercel,
Playwright). Backend `services/ml-api` commit `ff14bf4`; frontend
`ml-portfolio` commit `5f93a7d`.

## 5. #29 PPE Compliance Check — done

Verified first (not assumed) that the existing 601-class OIV7 detector
has no safety-vest class of any kind — a dedicated model was genuinely
required. Found and hands-on tested `Hansung-Cho/yolov8-ppe-detection`
(MIT-licensed weights, YOLOv8n, real Hardhat/NO-Hardhat/Safety-Vest/
NO-Safety-Vest/Person classes) rather than trusting its model card, same
discipline as the earlier fire-detection rejection: an initial test on a
245x148px real photo gave a weak vest signal (0.06 confidence) —
investigated rather than accepted, and traced to the extreme low
resolution, not the model. Re-tested on 3 higher-resolution real
user-provided photos and got a genuine pass: hardhat 0.72-0.88
confidence, vest 0.39-0.69, and correctly reported "unclear" (not a false
compliance claim) on a photo of the gear laid out on the ground with
nobody wearing it.

Architecture note: the weights are MIT but running them via the
`ultralytics` package would pull in a new AGPL-3.0 runtime dependency
this project doesn't have — avoided by exporting `best.pt` to ONNX once,
locally (dev-only `ultralytics` install, never added to
`requirements*.txt`), verifying the ONNX output matched the tested `.pt`
output on the same 3 photos, then shipping only the `.onnx` file through
the already-present `onnxruntime` — the exact same pattern the existing
OIV7 detector already uses, zero new runtime dependency. New backend
`mm_ppe_compliance.py` reuses `mm_objects.py`'s generic `_nms` helper
directly. Compliance is always read from an explicit present/absent
class the model fired, never inferred from a lack of detection;
per-person item attribution uses a disclosed head/torso spatial-overlap
heuristic (no real tracking).

Verified live end-to-end (HF Space + Vercel, Playwright, real photo).
Backend `services/ml-api` commit `a7305ec`; frontend `ml-portfolio`
commit `34ded0f`.

## 6. #13 rescoped to ASL Fingerspelling Recognition — done

Originally "Sign Language Translator." Discussed with the user: full
sign-language translation needs sequence models over video (ASL has its
own grammar/word order — see the real WLASL/2M-Flores-ASL research
datasets), not something a single-frame hand-pose classifier can
honestly claim. Rescoped, with the user's explicit agreement, to ASL
**fingerspelling** alphabet recognition — real, well-defined, and the
same shape of technique this project has already shipped twice
(gait-pattern-comparison, video-keystroke-inference): live MediaPipe
landmark extraction + classification, entirely client-side, zero
backend.

Built a full real ML pipeline from scratch this session:
- Found a real, ungated, no-Kaggle-auth-needed photo dataset
  (`Marxulia/asl_sign_languages_alphabets_v03` on HF) after confirming
  the obvious Kaggle candidates need auth this project doesn't have
  (same class of blocker as #39's Malimg dataset).
- Verified hand detection actually works using the real shipping library
  (`@mediapipe/tasks-vision`'s `HandLandmarker`, via a Playwright browser
  harness) rather than the local Python `mediapipe` package, which
  crashed on this machine with an unrelated macOS Metal-delegate bug —
  26/26 sample letters correctly detected.
- **Caught a real correctness issue by inspecting the actual images**:
  the dataset's "J" and "Z" photos are static single-frame hand shapes,
  but real ASL J and Z are motion letters, indistinguishable from other
  letters in a static frame — excluded both, matching the standard Sign
  Language MNIST convention (24 static letters shipped, A-Z minus J/Z).
- **Diagnosed a second real anomaly, not just accepted the numbers**: a
  systematic ~50%-vs-80% train/test hand-detection-rate gap traced to
  sketch/line-drawing illustrations mixed into the photo dataset
  (MediaPipe correctly fails to detect a hand in a drawing) — fixed by
  pooling all successfully-detected real photos and re-splitting
  cleanly, rather than silently trusting a broken split.
- Trained a k=1 nearest-neighbor classifier over translation+scale-
  normalized landmarks. Rotation-normalization was tried and found to
  measurably *hurt* accuracy (75.5% → 67.8%), so it was dropped — a
  tested result, not an assumption.
- Measured **79% accuracy on a genuine 314-photo held-out set** (24
  classes, chance ≈4%) — real, disclosed, imperfect-but-useful, not
  assumed from the technique's general reputation.
- Verified the shipped TypeScript classifier reproduces the *exact* same
  248/314 accuracy as the Python training script (ran the real prototype
  JSON through a Node script before writing any UI).
- Known real confusion clusters (U/V/R, M/S/N/A, K/X/P) disclosed
  explicitly in the User Guide as genuine hand-shape ambiguity, not bugs.
- Live-webcam real-world accuracy explicitly flagged as unverified in
  this sandboxed environment (same disclosed gap as `pose-vj-visuals`) —
  confirmed instead that the camera-permission flow and MediaPipe
  WASM/model load correctly, both locally and on the live deployed site.

ml-portfolio commit `2c99aa1`.

## 7. Process note

Immediately after #13 shipped, when asked what CV-backlog items remained,
listed #11 (Social Reels Creator), #12 (Gesture-Controlled Desktop), and
#21 (live-webcam surveillance) as "remaining items" without being clear
that — like #45 (rejected) and #13 (rescoped) — none of these three are
buildable *as literally brainstormed* without the same honest-rescoping
treatment first. Corrected when the user asked why they were presented
that way: #12 is categorically impossible for a hosted web page (browser
sandboxing prevents controlling a user's OS, not just "awkward"); #11 has
a real licensing wall (no royalty-free music source in this project);
#21 is structurally different from every other tool here (persistent
live camera + zone-alert loop, no upload step) and genuinely high effort,
not just a scoping problem.

## Session-end state (original, Part 259)

Six items shipped this session: #46 (deploy resumed and completed, one
real overclaim caught and fixed via live testing), #52, #49, #29, #13
(all net-new, real-technique CV tools, each independently researched and
hands-on verified before building), plus the Movement Form Comparison
User Guide gap-fill and the homepage alphabetical-sort fix. All commit
hashes recorded in `project_pending_master_list.md`. No item was shipped
without either a real measured accuracy number or an explicit disclosed
limitation where perfect accuracy wasn't achievable.

## 7. Cybersecurity feature research (appended later, 2026-08-27/28)

Asked to research and list good cybersecurity features to add, then to go
build one. Researched online first (real technique verification, not
assumed), producing an initial shortlist of six non-duplicate,
CPU-feasible ideas:

1. Malicious Package Scanner (npm/PyPI) — paste a `package.json`/
   `requirements.txt` or a source file; run real static heuristics
   (GuardDog/Semgrep-style: `eval`/`exec`/`subprocess` calls, install-script
   hooks, base64/hex-obfuscated blobs, typosquat Levenshtein-distance
   against top-1000 package names). Pure heuristics, no ML, "signals not
   verdict" — same honest framing as AI Code Detector. Real published
   technique (Datadog's GuardDog).
2. Password Strength + Breach Exposure Checker — zxcvbn-ts strength
   scoring + Have I Been Pwned k-anonymity breach lookup, password never
   leaves the browser except as a 5-char hash prefix.
3. TLS/Security-Headers Scanner — given a domain, live TLS handshake
   (cert chain/expiry/self-signed/weak-cipher check) + HTTP
   security-header audit (CSP, HSTS, X-Frame-Options, etc.),
   Mozilla-Observatory-style. Same "live DNS/network, zero ML" category as
   the Email Auth Checker.
4. Attack-Surface / Exposed-Path Scanner — given a domain, checks common
   misconfig tells: exposed `.git`/`.env`/`.DS_Store`, directory listing,
   outdated CMS version fingerprints, open common ports via banner-safe
   checks. Safe, non-intrusive — no active exploitation.
5. Log-Based Brute-Force / Anomaly Triage — paste an auth/nginx access
   log; detect brute-force clusters, credential-stuffing patterns, and
   impossible-travel-style timing anomalies. Pure stats/heuristics.
6. YARA-Rule File Scanner — run a small curated YARA ruleset against an
   uploaded file (never executes it) to flag known malicious
   patterns/macros — complements the existing entropy-based
   Malware-Image-Triage tool rather than duplicating it.

User picked #2 (Password Strength + Breach Exposure Checker) to build
first — full build/deploy detail already recorded as its own row in
`project_pending_master_list.md` (item #58, ml-portfolio commit
`127abea`). Key points: user explicitly chose the real `zxcvbn-ts`
library over a hand-rolled entropy heuristic (asked via AskUserQuestion);
HIBP's password-range API was confirmed via research to need no API key
and to be purpose-built for direct browser calls — a deliberate,
disclosed deviation from this codebase's only prior precedent
(`qr-phishing-detector` proxies its external reputation checks through
the backend specifically because those need a secret key). A real
JSX whitespace-collapse bug (`password{s} —\nthis password` rendering as
"passwords— this", the same class of bug as ASL Fingerspelling's earlier
`{" "}` fix) was caught via live Playwright verification and fixed before
calling it done.

### Deeper cybersecurity idea dump — user pasted a large external list

The user separately pasted a large cybersecurity-project list from
another AI conversation (Application Security, Endpoint/OS Security,
Identity/Access/Crypto, Cloud/Infrastructure, SOC/Orchestration domains,
plus a "Network IDS / Phishing Classifier / UEBA / SIEM Triage Agent"
comparison table) and asked to go through it. Triaged every item against
this specific project's real constraints — hosted, stateless, CPU-only
HF Space, no persistent local agent, no live cloud credentials, never
executes untrusted files — rather than treating the list at face value.
Full triage below, preserved for future reference (do not re-derive from
scratch next time this list comes up):

**✅ Buildable here, no rescope needed — genuinely new**

| Idea | Why it fits |
|---|---|
| Keystroke Biometric Auth-Risk Demo | Pure client-side JS keydown/keyup timing + KNN/distance scoring. Different from the existing Video-Call Keystroke Inference (that infers keys from *video*; this is literal typing-rhythm biometrics). No overlap. |
| DNS Tunneling / Exfiltration Detector | Paste or live-query DNS records → Shannon entropy + subdomain-length/count heuristics. Zero ML, zero GPU, same category as the Email Auth Checker. |
| SIEM Alert Triage Agent (LLM-judge) | Paste a batch of raw alerts → an LLM judge prioritizes/explains them. Reuses the exact fixed-key Mistral pattern already built for Prompt Injection Playground / AI Code Detector — low incremental effort. |
| Phishing Email Body Classifier | Different angle from what's shipped: existing tools check URLs/headers, not email *text* (urgency language, spoofed display-name tricks, generic greeting). Real NLP technique, CPU-friendly (TF-IDF + classic classifier). Needs a real labeled corpus (Enron + a phishing corpus like Nazario) — same one-time-local-training pattern as ASL Fingerspelling. |
| AI-Powered SAST Scanner | AST parsing + pattern rules for SQLi/XSS/hardcoded secrets in pasted source code. Broader version of the earlier "npm/PyPI scanner" pick from the shortlist above — worth merging into one tool rather than building both separately. |

**🔁 Real technique, but needs a scope change to fit a hosted demo**

| Idea | Problem | Rescope |
|---|---|---|
| Malware PE Header Classifier | Substantially overlaps with the already-shipped Malware-Image-Triage tool's packer-tell check (entry-point-in-last-section). | Extend that tool with deeper PE-header fields rather than shipping a separate one. |
| Crypto/TLS Downgrade Detector | Same technique as the earlier shortlisted "TLS/Security-Headers Scanner." | Fold into that one tool instead of building twice. |
| Supply Chain Dependency Predictor | Needs a trained regression model on GitHub metadata + live GitHub API rate limits. | Ship as a live-heuristic version (stars/last-commit/maintainer-count red flags) like Email Auth Checker's live-DNS pattern, not a trained predictor. |
| Malicious Pull-Request Detector | No git repo exists to scan in a hosted demo. | Rescope to "paste a diff/patch" and heuristically flag suspicious deltas (sensitive file touches, obfuscated additions). |
| IAM Least-Privilege Optimizer | Needs real AWS CloudTrail logs + IAM policy exports most users won't have on hand. | Accept pasted/uploaded policy+log JSON, disclose synthetic-data caveat like Crime Scene Reconstruction did. |
| Honeytoken/Canarytoken Deployer | Real version needs an always-on webhook listener and lives in the user's actual infra — this project has neither. | Scope down to: generate one realistic decoy credential + a single trackable URL, disclose that the real product (Canarytokens.org) does the persistent part. |
| Network IDS (CICIDS2017) | Not really a new tool — this is "run the existing AutoML Pipeline on a labeled network-flow dataset." | Doesn't need new infra; could be a demo dataset added to AutoML, not a standalone project. |
| Automated Incident-Response Playbook | Can't actually isolate a host or disable a user from a hosted demo — must never imply it does. | Advisory-only: paste an incident description, get a suggested playbook (deterministic rules + LLM judge), clearly labeled "suggests, does not execute." |

**❌ Not buildable in this architecture at all — same class as #12 (Gesture-Controlled Desktop)**

| Idea | Why it's a hard no here |
|---|---|
| Ransomware Canary & Entropy Blocker | Requires a persistent OS-level daemon watching the live filesystem — a hosted web page cannot do this, full stop, same sandbox limit as #12. |
| Process Injection Detector | Needs live Windows Sysmon telemetry streaming from the user's own machine in real time — no such data source exists for a web demo. |
| UEBA Engine | Same problem — needs real, ongoing local auth/Sysmon logs from an actual environment, not a one-shot upload. |
| Adaptive Risk-Based Auth Engine | Needs an actual multi-session login history (IP drift, device fingerprint over time) — a stateless portfolio tool has no persistent user accounts to build this risk profile from. |

Recommended build order given to the user from the "buildable now" list:
DNS Tunneling Detector (smallest, self-contained) → SIEM Alert Triage
Agent (highest reuse of existing backend pattern) → Phishing Email Body
Classifier (most novel, needs the one-time local training step).

### Deferred items — grouped together per explicit user request

The user then asked to formally group the **not-buildable** cybersecurity
items above together with **#11/#12/#21** (the CV-backlog items ruled out
earlier this same session, see section 6 above) into one explicit
"Deferred" section in `project_pending_master_list.md`, rather than
leaving them scattered as individually-struck rows — done immediately
after this log entry; see that file's new "Deferred — not buildable in
this hosted architecture" section for the authoritative, up-to-date list.
