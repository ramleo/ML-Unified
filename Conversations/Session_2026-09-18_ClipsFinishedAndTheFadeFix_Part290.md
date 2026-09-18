# Part 290 — Finishing the clips, and the ones that couldn't be filmed

Continues [Part 289](Session_2026-09-17_ClipsAsIntegrationTests_Part289.md).

2026-09-18. The goal was the tail of the E6 demo-clip backlog, one tool at a
time. Four more clips shipped (PPE, plant-growth, photo-search, crime-scene),
every existing clip got a proper open and close, and three tools were proven
**un-clippable** for concrete reasons — which is its own result. With that, the
honestly-clippable backlog is exhausted; everything left is webcam/WebGL.

The spine of the day: **most of the work was deciding what NOT to film, and
building honest inputs for what could be.**

---

## 0. The fade fix — every clip started and ended abruptly

The user said the recordings "start abruptly and end abruptly." They were
right, and I'd have missed why: the clips DO have a title card and an end card
(they dissolve within the page), but `mux()` in `demo-audio.mjs` muxed with
`-c:v copy` — the **video stream itself was never touched**, so frame one
popped on at full brightness and the last frame stopped dead. No fade from or
to black.

Fix: `mux()` now re-encodes with a video+audio `fade` in (0.6s) / out (0.9s),
pinned to the shorter of picture and sound with `-t`. The card background is
`#0b0e17`, so fading the whole frame to black reads as one continuous open and
close. Re-encoded **all 33 existing clips in place** (local ffmpeg, no
re-recording, no API cost) — and VP9 made them smaller than Playwright's VP8
(depth-parallax 15.4→5.7 MB; the whole folder shrank). `9e9bae1`.

Lesson: a bookend card is not a fade. "Abrupt" meant the *stream*, not the
content — check the first and last actual frames, not just that an intro exists.

## 1. PPE Compliance Check — reject the crowd photo

Real YOLO PPE detection: one worker, hard hat 94%, vest 93%. The lesson was in
sourcing. The first candidate (a free lineup-of-workers photo) detected 8
people with several "vest:missing" labels on people who visibly wore vests —
the crowd-heuristic misattribution the tool honestly warns about, but on screen
it reads as the tool being *wrong*. Cropped to a single clean worker instead
(Pexels, free license). `1599a89`.

## 2. plant-growth — the auto-detect trap, and an honest illustration

Growth-over-time on three synthetic frames of one plant: leaf area
0 → +171% → +412%, measured for real by the HSV green threshold. Two things
mattered:
- **Auto-detect had to be switched OFF in the clip.** With it on, the tool
  crops each frame to the plant's own box and measures fraction-of-crop, which
  barely changes as the plant grows (14–19%) — the exact pitfall the backend
  docstring warns about. Off, it measures against the whole fixed frame and the
  real growth shows. The demo toggles it on-screen and says why.
- The input is a **labelled illustration** (the tool accepts illustrations);
  narration says so. The green-pixel count is genuinely real either way.

Also needed a recorder change: **multi-file upload.** Growth mode's `multiple`
input replaces its list on each pick, so all frames must go in one
`setInputFiles` call. Taught both players (`demo-actions.mjs` + `demoActions.ts`)
to accept `file` as an array. `4b7f4b4`.

## 3. photo-search — CLIP ranks real photos, so use real photos

Five distinct Pexels photos (dog, beach, pizza, bike, mountain), unlabelled,
queried "a dog on grass" → dog **100%**, everything else well behind. CLIP
needs real-world semantics, so this is the one CV clip that genuinely wants
real photos rather than a synthetic input; Pexels free-license is the clean
source. `3bc5d62`.

## 4. crime-scene-reconstruction — a synthetic 3D scene is honest multi-view

Structure-from-motion needs several photos of one **textured, non-flat** scene
(planar scenes degenerate the essential matrix). Built a synthetic textured 3D
scene — three boxes on a checkered floor — and perspective-projected each face
from four camera positions with PIL. That IS genuinely multiple views of one
scene (real parallax, real SIFT texture), so it's honest; narration says
"rendered views." Live OpenCV endpoint: 1602 points, 4 camera poses, no
warnings, WebGL cloud renders under headed Chrome.

The visual lesson: the first take's cloud sat tiny in the viewer because a few
**outlier points** (from repeated box textures causing cross-box feature
mismatches) blew up the auto-fit. Gave every box face a **unique** texture →
outliers gone, extent shrank 4.86→2.8, cloud fills the frame. Measured the
5th–95th-percentile spread to confirm before re-recording rather than eyeballing.
`5226ba2`.

---

## The three that couldn't be filmed, and why

Deciding NOT to film these, with evidence, was as much the work as filming.

- **wildlife-reidentification** — two independent walls. (1) MegaDescriptor is
  trained on wildlife, not domestic cats: two genuinely-different photos of the
  SAME cat (Larry, Tama) scored ~0.35 ("different"); near-identical view scored
  0.998, so it only clears the 0.85 "same" bar for near-duplicates. (2) The
  species it IS strong on (sea turtles / SeaTurtleID) come from datasets whose
  licence forbids reproduction outside scientific papers. Freely-licensed
  species give dishonest results; honest species can't be published.
- **captcha-hardening-lab** — billed (Mistral→paid Gemini vision, twice per
  run), AND the model won. A clear synthetic CAPTCHA read correctly at BOTH
  intensity 80 and 100 (max) — genuinely the tool's own point (VLMs beat classic
  hardening), but a Correct→Correct clip sells the tool as doing nothing.
  Stopped at the ~4 paid calls the user approved.
- **rag-analytics** — not a handbook chapter at all (it's a Multimodal RAG
  sub-page), and clips only launch from a chapter, so a clip has nowhere to go.

All recorded in [[project_demo_clip_audit]].

---

## Commits (all ml-portfolio; no backend changes this session)

| Commit | What |
|---|---|
| `1599a89` | PPE Compliance Check clip (+ Pexels sample) |
| `9e9bae1` | fade every clip in/out; re-encode all 33; recorder `mux()` |
| `4b7f4b4` | plant-growth clip (+ synthetic frames) + multi-file upload in both players |
| `3bc5d62` | photo-search clip (+ 5 Pexels samples) |
| `5226ba2` | crime-scene-reconstruction clip (+ synthetic multi-view scene) |

---

## Lessons

- **A bookend card is not a fade.** The abruptness was in the video stream that
  `mux` copied untouched. Watch the actual first/last frames.
- **The honest move is often to NOT film it.** Three tools were ruled out with
  real evidence (model domain, licence, billing, no chapter) rather than faked
  around. A demo that can't be truthful shouldn't exist.
- **Build the input to the tool's real mechanism, then let it measure.**
  Synthetic plant frames (green pixels), a synthetic textured 3D scene (SIFT +
  parallax), a crafted CAPTCHA — each honest because the tool does real work on
  it. CLIP was the exception that genuinely needed real photos.
- **Measure before re-recording.** The crime-scene cloud's tightness was a
  percentile-spread check, not a guess; the plant auto-detect trap was a live
  endpoint test, not a hunch.
- **Check the cost before the paid tool.** captcha bills per read; verifying
  that up front kept the spend to the approved budget.
