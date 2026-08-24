# Session 2026-08-21 — Adversarial Robustness Lab Expansion + Face Cloak Tool (Part 246)

Continuation of the same day as Part 245 (homepage/Capabilities redesign), but a
distinct session: fixed a card-height regression, then took the freshly-renamed
Adversarial Robustness Lab through its entire research backlog (targeted attacks →
randomized smoothing → transferability → adversarial patch → black-box attack),
then researched and shipped a brand-new standalone privacy tool, Face Cloak
(Fawkes-style adversarial face-embedding disruption).

Tags: `adversarial-robustness-lab`, `mm_adversarial`, `mm_adversarial_models`,
`mm_adversarial_attacks`, `mm_adversarial_defenses`, `targeted-attack`,
`randomized-smoothing`, `transferability`, `adversarial-patch`, `black-box-attack`,
`SimBA`, `face-cloak`, `mm_face_cloak`, `Fawkes`, `facenet-pytorch`,
`InceptionResnetV1`, `file-split`, `ProjectCard`, `live-verification`,
`HF-Space-deploy`, `Part246`, `continuation-of-Part245`

---

## 1. Live ML Apps card-height fix

User reported the three homepage project cards (ML Unified Platform / EDA
Explorer / ML Vision Platform) rendered at different heights. Root cause: a
prior session's fix for a different dead-space bug had set the grid to
`alignItems: "start"`, which let each card size to its own description length
instead of matching row height. Fixed by:
- `ProjectsSection.tsx`: grid back to `alignItems: "stretch"`.
- `ProjectCard.tsx`: description clamped to 3 lines (`-webkit-line-clamp`) with a
  "See more"/"See less" toggle button, so the clamp — not incidental content
  length — is what makes heights equal.

Verified live: all three cards render at 461px height; toggle expands/collapses
per-card without affecting siblings. Commit `4a94404` (ml-portfolio).

---

## 2. Picked next pending item + tool rename

User asked to pick a pending item from the Adversarial Examples tool's own
research backlog (recorded in Part 243) and separately asked why the tool was
named "Adversarial Examples" — asked for a rename keeping "Adversarial",
replacing "Examples" with something more accurate to its actual attack+defense
scope.

Recommended and built **targeted attack mode** (small code delta, reuses
existing gradient machinery, big demo payoff) as the next feature, and renamed
the tool to **"Adversarial Robustness Lab"** — including the URL slug
(`/tools/adversarial-examples` → `/tools/adversarial-robustness-lab`), confirmed
via `AskUserQuestion` rather than assumed.

### Targeted FGSM/PGD attack
- Backend (`mm_adversarial.py`): `_fgsm`/`_pgd` gained a `targeted: bool` param —
  untargeted ascends the loss w.r.t. the true label (push away); targeted
  descends the loss w.r.t. a caller-chosen target label (push toward it), same
  gradient, opposite sign. New `GET /mm-adversarial/categories` endpoint for the
  frontend's label picker. Pre-check: if the model already predicts the target
  label, reject with a clear 400 rather than trivially "succeeding".
- Real verification: targeted PGD at eps=0.08 reliably forced "golden retriever"
  from a real photo's "bow tie" original, both locally and on the deployed Space.
- Frontend: target-label `<input list>` + `<datalist>` over the 1000 ImageNet
  classes (lazy-fetched on focus), "Target achieved"/"Target not reached" badge.

Two commits initially needed on the frontend side — a `git mv`-only rename
commit (`b7f9bb7`) accidentally captured zero content changes because `git add`
only staged the pure rename; the actual edits inside those files had to be
committed separately (`59efe26`). Backend: `4b3e82f`.

---

## 3. Randomized smoothing (second defense)

User picked randomized smoothing next. Implemented `_randomized_smooth()`:
classifies `_SMOOTH_SAMPLES=25` independently Gaussian-noised copies of the
adversarial image and majority-votes, reporting `vote_confidence` (fraction of
samples agreeing) as an honest instability signal separate from the point
prediction.

Real sigma sweep on a real PGD-attacked photo (before picking a default):
- sigma=0.15: barely disrupted anything (96% vote stayed on the attacker's
  chosen wrong label).
- sigma=0.35+: started destroying real image content, landing on unrelated
  labels.
- sigma=0.25 (shipped default): sometimes recovered the correct label but with
  visibly LOW vote_confidence (~0.3-0.4) — an honest instability, not hidden
  behind a single point prediction.

Frontend: new "After randomized smoothing" panel with a vote-agreement bar,
independent recovered/disrupted/no-effect badge alongside the JPEG defense
panel. Commits: backend `be6175e`, frontend `8df4726`.

---

## 4. Transferability check + first file split (400-line rule)

Added `check_transfer` opt-in: classifies the SAME adversarial image with
ResNet18 (a different architecture, zero gradient access during the attack) and
reports whether ResNet18's own prediction also changed. Verified directly (not
assumed) that `ResNet18_Weights` and `MobileNet_V2_Weights` share an identical
ImageNet category ordering before reusing one `_categories` list for both.

Real finding from a method/epsilon sweep: FGSM's single-step perturbation did
NOT transfer to ResNet18 at ANY tested epsilon (0.02-0.08); PGD's multi-step
perturbation DID transfer at every epsilon tested — a single-image finding,
reported as observed, not generalized into a rule.

`mm_adversarial.py` crossed 488 lines while building this. Split into
`mm_adversarial.py` (router/orchestration) + `mm_adversarial_models.py` (model
loading, `_predict`, Grad-CAM, image helpers) — done directly rather than via
subagent, given the real risk of a subagent mishandling Python's
`from x import mutable_global` reassignment pitfall (documented explicitly in
the new file's docstring: callers must access `models._model`/`models._categories`
through the module, never via direct import, since those globals are
REASSIGNED not mutated in place). Re-verified with the same local test harness
plus a live Playwright run after the split. Commits: backend `06bb00a`,
frontend `bc50fdd`.

---

## 5. Adversarial patch (third attack)

Optimizes a single square, unconstrained (no epsilon ball) patch region into a
directly VISIBLE "sticker" attack — the single-image/single-placement version,
not Brown et al. 2017's universal cross-image/position patch (would need
expectation-over-transformation training this demo can't afford per-request).

Feasibility-tested before committing to the design: untargeted patches fooled
the classifier almost instantly (1-2 gradient steps — a patch this size is
already disruptive before optimization even helps). Targeted patches showed a
sharp size/success relationship: 10% patch failed to converge at all within
300 steps; 25% patch succeeded in 28-38 steps. Shipped default 20% patch,
150-step budget, early-stops the moment the goal is met (`patch_steps` in the
response is a real measure of work done, not always the full budget).

Frontend: patch-size slider replaces the epsilon slider when this method is
selected; perturbation preview switches to unamplified "The patch region"
(amplify=1.0, since the patch is already directly visible — amplifying further
would just clip to solid color). Commits: backend `d02e304`, frontend `1b52f3a`.

---

## 6. Black-box query-only attack (fourth attack) + second file split

Closed out the last item on the original research list: a fundamentally
different threat model — zero gradient access, only forward-pass queries
returning a softmax score, via a simplified SimBA (Guo et al. 2019). Each query
nudges one never-repeated (pixel, channel) coordinate by ±epsilon, keeping the
change only if it moved the target score the right direction.

Real, load-bearing finding (this is *why* the attack was worth building, per
the user's earlier question about what "weaker within a request timeout"
actually meant): untargeted converged in 348 queries (~5.5s). Targeted did NOT
converge at all even at the maximum 3000-query budget (~46s), and pushing to
6000 queries with a larger step (~94s, already past a reasonable request
budget) still failed. This genuine negative result is baked directly into the
shipped copy — "Target not reached" for a targeted black-box run is framed as
the demonstrated point of the attack, not a bug.

`mm_adversarial_models.py` crossed 416 lines adding `_black_box_attack`. Second
split: `mm_adversarial_models.py` (model/predict/Grad-CAM/image helpers) +
`mm_adversarial_attacks.py` (all four attacks) + `mm_adversarial_defenses.py`
(both defenses) — four files total now, all under 300 lines each. Re-verified
locally then live via Playwright (real photo, real local server) and a real
production HTTP call against the deployed Space. Commits: backend `72e2a50`,
frontend `53b6b5e`.

This closed the entire prioritized research list from Part 243 — untargeted +
targeted attacks across four distinct threat models, two defenses, and
cross-model transferability, each with real-tested honest findings in the
copy rather than favorable-case cherry-picking.

---

## 7. User guide maintenance pass (twice)

Twice asked to "update user guide" as features landed — each time a genuine
re-read of `userGuide.ts` surfaced real staleness the incremental edits had
missed:
- First pass: intro paragraph and the "how to use it" results list still
  described only the original untargeted-attack + JPEG-defense version, never
  updated when targeted attacks/transferability shipped.
- Second pass: "Notes & limits" still said "both attacks" from before the patch
  and black-box attacks existed (now four).

Also caught a real bug while writing prose for the patch section: an unescaped
backtick used for markdown code-formatting inside the guide's own JS template
literal would have broken the build — `npx tsc` caught it before commit, not
in production. Commits: `59efe26`/`8df4726`/`bc50fdd`/`1b52f3a`/`53b6b5e`
(incremental) + `d9f6098` (dedicated fix pass).

---

## 8. Live user testing of the real tool

User actually used the deployed tool directly (uploaded a real car photo,
typed "golden retriever" as a target, ran FGSM then PGD) and asked live
questions about the results shown on screen — walked through: why does
"target not reached" happen at low epsilon/weak method (FGSM, low strength,
semantically distant target), what to click next, and confirmed a successful
PGD-at-higher-epsilon run ("Target achieved") was a genuine success — both for
the demo's own purpose (proving the vulnerability) and as the "bad news" the
tool exists to communicate (classifiers can't be blindly trusted). No code
changes this section — pure explanation grounded in the user's own live
screenshots, not hypothetical results.

---

## 9. Web research: adversarial ML use cases → Face Cloak feasibility

User asked for real-world adversarial ML use cases. Two web searches:
attack-side incidents (autonomous-vehicle sign-spoofing, financial-fraud
evasion, spam-filter evasion) and defense-side "adversarial used for good"
(Fawkes personal-photo privacy cloaking, Glaze/Nightshade artist protection,
adversarial training, CAPTCHA design, watermarking). Recommended Fawkes-style
photo cloaking as the next build — closest fit to this site's existing
Security & Trust domain, complementary to (not duplicating) the attack-demo
framing of Adversarial Robustness Lab.

**Feasibility research (via subagent) before writing any code**: confirmed
this codebase has face DETECTION (YOLOv8s-oiv7, AGPL-derived) and face
LIVENESS classification (MiniFASNetV2, Apache-2.0) but no face-EMBEDDING/
recognition model, which Fawkes actually needs. Compared candidates
(`facenet-pytorch` InceptionResnetV1 MIT/~100MB, MobileFaceNet no clean
package, EdgeFace license-unclear, InsightFace weights non-commercial-only).
Picked `facenet-pytorch`'s InceptionResnetV1 — cleanest license fit given this
project's prior AGPL-YOLO friction, small enough for the free-tier HF Space.

---

## 10. Face Cloak tool — built, verified, shipped

New standalone tool at `/tools/face-cloak`. `pip install facenet-pytorch
--no-deps` locally (its own pinned Pillow version failed to build against the
dev machine's very new Python 3.14; the actual deployed Space runs Python 3.11
per its Dockerfile, where the normal pinned install should work cleanly — this
was confirmed correct by the real deploy, not just assumed).

**Backend** (`mm_face_cloak.py`, new, 227 lines): reuses `mm_objects.py`'s
existing face detector to locate the face (same reuse pattern as
`mm_liveness.py`), then runs gradient-ascent repulsion — maximize L2 distance
between the perturbed face-crop's embedding and the photo's own original
embedding (fixed reference), masked to only the face-crop region so the rest
of the photo is untouched, epsilon-bounded per pixel.

**Deliberately simplified vs. the real Fawkes paper**, disclosed directly in
the module docstring and user guide rather than hidden: this is UNTARGETED
(push away from own embedding) since no bundled decoy-identity dataset exists
to target toward, unlike the paper's TARGETED feature-collision approach
(which the original authors' own follow-up work found gives stronger, more
durable protection).

Real local test: 40 steps, epsilon=0.05, ~1 second, dropped cosine similarity
between original and cloaked face embeddings from 1.0 (identical) to -0.58
(near-opposite direction) — reported via a `protection_level`
(strong/moderate/weak) heuristic using published face-verification similarity
ranges (>~0.5-0.7 same-person, <~0.3 different-person), explicitly disclosed
as a heuristic, not a certified per-system threshold.

**Frontend**: new tool page (accent `#8b5cf6`, unused elsewhere on the site),
`FaceCloakRunner`/`useFaceCloak`/`userGuide.ts`/`FaceCloakUserGuideModal.tsx`
following the same structural pattern as Adversarial Robustness Lab. Result
panel shows original vs. cloaked image side by side, the real cosine-
similarity number and protection-level badge, and explicit copy that this
protects only the newly-cloaked photo (not copies already scraped elsewhere)
and can weaken against recognition models retrained after a cloaking method
becomes public — matching this project's established honesty pattern.

New Security & Trust capabilities card added.

**Deploy verification hit a real wrinkle worth recording**: after the HF Space
rebuild (needed since `facenet-pytorch` is a brand-new dependency — confirmed
`RUNNING` via the stage API), two local `curl --max-time` verification
attempts returned "Unterminated string" JSON-decode errors — looked like two
consecutive failures, which per this project's standing rule should trigger a
stop-and-investigate rather than a third blind retry. Checked the Space's own
run logs directly (`/api/spaces/{id}/logs/run`) instead of guessing: found
every one of the three `/rag/mm-face-cloak/run` requests had actually returned
`200 OK` server-side, weights downloaded once (107MB in ~1s from HF's own
CDN). The truncation was a CLIENT-side `curl --max-time` artifact from this
local machine's connection struggling with the large base64-image response
payload, not a backend problem. A fourth attempt with a longer timeout and
`curl -o` (avoiding a piped python parse mid-transfer) completed cleanly:
`cosine_similarity: -0.7824`, `protection_level: strong`, 647,540-byte cloaked
image — full confirmation. Commits: backend `456b6f3`, frontend `64ffc5a`.

---

## Where this stands

**Adversarial Robustness Lab**: the entire Part-243 research backlog is now
closed — untargeted + targeted attacks across four threat models (FGSM, PGD,
visible patch, black-box query-only), two defenses (JPEG recompression,
randomized smoothing), and cross-model transferability. Nothing pending from
the original brainstorm. Any further work here (adversarial patches were
already built; the "higher-effort" items flagged back in Part 243 — true
label-only black-box beyond this session's score-based SimBA, or a universal/
cross-image patch) would be a genuinely new ask, not a backlog item.

**Face Cloak**: v1 shipped and verified live in production. Known,
not-yet-built extensions (none currently requested, listed here only because
the user explicitly asked pending items be recorded this session):
- **Targeted (real Fawkes) mode** — push toward a real decoy identity's
  embedding instead of pure repulsion; would need a small bundled/embedded
  reference face set to pick decoys from, not yet sourced or licensed.
- **Multi-face support** — currently only the single highest-confidence
  detected face is cloaked; a group photo's other faces are left untouched.
- **No real re-identification benchmark** — the cosine-similarity drop is a
  real, direct measurement, but no same-person/different-person photo-pair
  dataset exists in this codebase to validate the heuristic
  strong/moderate/weak thresholds against actual match/no-match outcomes.
- **Epsilon/steps only tuned against one real test photo** (Grace Hopper) —
  not swept across a range of face angles/lighting/expressions.

---

## How to apply going forward

- **A real, load-bearing negative result is worth shipping directly in the
  UI copy, not softening** — the black-box attack's targeted-mode failure at
  max query budget, and the small-patch targeted failure, are both the actual
  point of those features, framed that way in the shipped copy rather than
  hidden as an edge case.
- **Feasibility-test the actual algorithm on a real photo before designing
  the full feature** — the patch attack's steps-vs-size relationship and the
  black-box attack's targeted-vs-untargeted query-cost gap were both
  discovered via quick standalone Python tests BEFORE writing the production
  module, which is what let the shipped defaults (20% patch, 1500-query
  default budget) be evidence-based instead of guessed.
- **A subagent isn't automatically the right tool for a risky refactor** —
  both file splits this session were done directly rather than delegated,
  specifically because of a real, easy-to-miss Python footgun (mutable-global
  reassignment across a `from x import y` boundary) where a subagent
  re-deriving context from scratch was judged more likely to introduce a bug
  than to safely execute the mechanical split.
- **Two consecutive client-side failures should trigger a check of direct
  server evidence (logs), not a third blind retry** — the "two truncated
  responses" here looked like a backend problem but were a local curl timeout
  artifact; the Space's own run logs (`200 OK` on every request) were the
  actual ground truth, found in under a minute instead of guessing further.
- **Re-reading a living doc (`userGuide.ts`) after a batch of incremental
  edits reliably finds real staleness** — both "update user guide" requests
  this session found genuine gaps (a rename-era leftover, a feature-count
  leftover) that individual per-feature edits had missed; worth treating as a
  standing check, not a one-time task.
