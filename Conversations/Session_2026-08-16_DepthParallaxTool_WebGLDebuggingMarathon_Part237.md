# Session 2026-08-16 (cont'd) — Depth Parallax tool built, then a long real-bug-fixing marathon

Continuation of the same day as Part 236. Opens with data-persistence follow-up questions on the
just-shipped Face Liveness tool, then picks the next pending-list item (Depth Parallax, chosen from a
shortlist filtered for "impressive results"), builds it as a new five-mode standalone tool, and spends
most of the session finding and fixing a long chain of *real* bugs the user caught by actually using
the deployed feature — several of which traced back to genuine mistakes in this session's own work,
not pre-existing issues.

## Part 0 — Face Liveness data-persistence Q&A

Quick factual follow-up before starting new work: confirmed `mm_liveness.py` never writes captured
webcam frames to disk or a database (decodes in-memory, runs inference, returns a result dict) — so
there's nothing to retrieve later, and no future logging/caching change could retroactively recover
data from a request that already completed before that change shipped. Answered in plain text, no
code changes.

## Part 1 — Picking Depth Parallax from the pending list

Read `project_pending_master_list.md` per standing practice. Narrowed the CV-brainstorm backlog to
four "high visual impact + real feasibility" candidates (Depth Anything parallax, SAM3 rotoscope,
malware-as-image classification, adversarial attack/defense demo) and let the user pick — they chose
**Depth Anything parallax/3D toy**.

**Verified feasibility before committing**, per the project's standing "verify before building"
discipline: researched Depth-Anything-V2-Small's license (Apache-2.0 for the Small checkpoint
specifically — Base/Large/Giant are CC-BY-NC-4.0, not used), downloaded the real ONNX-community
quantized export (37MB), and ran it against a real photo (`car.jpeg`) locally before writing any
backend code — confirmed the depth map cleanly separated the car from the background with a real
gradient, not noise.

## Part 2 — Backend + base tool build

Built `services/ml-api/routers/rag/mm_depth.py` (`POST /rag/mm-depth`), mirroring the existing
`mm_liveness.py` pattern: lazy ONNX singleton, resize-to-multiple-of-14 preprocessing per the model's
own `preprocessor_config.json`, returns a base64 grayscale PNG depth map resized back to the original
photo's dimensions. Verified end-to-end locally (direct Python call) before wiring up the frontend.

Frontend: new `/tools/depth-parallax` page, `DepthParallaxRunner.tsx`, and an initial `ParallaxCanvas.tsx`
implementing pointer-driven parallax as a **discrete 40-column grid-tile** displacement (each tile
shifted by its own sampled depth × pointer offset). Verified live via Playwright on a car photo — looked
fine at the time. Committed and HF-uploaded the backend (`mm_depth.py` + model files), pushed the
frontend. First deploy of the day for this tool.

**User's first live screenshot exposed a real bug**: uploading a bicycle photo (thin spokes right next
to a very different-depth background) showed jagged black tearing — neighboring tiles with a big depth
delta shifted apart and exposed gaps. Root-caused correctly (tile granularity vs. a continuous depth
field) but the first fix attempt (draw an unshifted base layer first, then depth-sorted tiles on top)
only *reduced* the tearing, it didn't eliminate the underlying problem — flagged for a deeper rewrite.

## Part 3 — Real per-pixel WebGL shader rewrite + layout fix

Rewrote `ParallaxCanvas.tsx` from scratch as a true per-pixel WebGL fragment shader (continuous UV
displacement sampled from the depth texture every fragment) — no tile boundaries exist to tear at,
the correct fix rather than another tuning pass on the tile approach. Along the way, extracted shared
WebGL boilerplate (shader compile, texture upload, fullscreen quad) into `webglUtils.ts` since three
more modes were about to reuse it.

**Also fixed a layout complaint the user had raised before but I hadn't retained**: the page had been
scaffolded by copying `face-liveness/page.tsx`'s narrow `max-w-3xl` container — itself an outlier
against every other tool page (`max-w-6xl`/`max-w-7xl`/`max-w-[1600px]`). Widened to `max-w-6xl` and
grew the canvas display size. Saved a standing feedback memory (`feedback_dont_cramp_layout.md`) so
this pattern doesn't get copied forward again.

Added two new modes reusing the same one backend call, zero extra server cost:
- **Bokeh** (`BokehCanvas.tsx`) — simulated depth-of-field, a fixed 9-tap blur kernel scaled by
  distance from a click-to-set focus depth.
- **AR occlusion** (`ArOcclusionCanvas.tsx`) — click to place a marker, slider sets its assigned
  depth; per-pixel occlusion test against the real depth map hides the marker behind nearer real
  content instead of always floating on top like a naive sticker overlay.

## Part 4 — A real local-tooling illusion (not a code bug)

While verifying the rewrite via Playwright screenshots, the rendered bicycle appeared visibly rotated
~30-40° even at pointer-rest, where the shader is a pure identity passthrough — mathematically
incapable of introducing rotation. Spent a long debugging pass (`readPixels` sampling, ASCII-art pixel
dumps, a hard dev-server restart, then a completely isolated from-scratch WebGL test with zero app
code) before concluding this was a genuine quirk of the local machine's headless-Chromium software
WebGL rasterizer — the isolated minimal test (trivial fullscreen-quad passthrough shader) reproduced
the exact same rotation on both JPEG and PNG input. The user's own real-browser screenshot of the same
feature showed correct orientation. Saved as `feedback_local_webgl_screenshot_unreliable.md` — local
screenshots of WebGL canvases on this machine can't be trusted for pixel-level visual judgment;
`readPixels`/DOM checks are the reliable substitute, but fine visual polish still needs the user's own
eyes.

## Part 5 — 3D relief mode (first version) + the *real* upside-down bug

Added a fifth mode, `Relief3DCanvas.tsx`: real displaced-mesh geometry (`reliefMesh.ts` builds a
subdivided plane, `mat4.ts` supplies minimal in-house perspective/rotation matrix helpers — no new
dependency), draggable within a small rotation range, framed as the honest ceiling of monocular
depth (a relief, not a walk-around 3D model). Verified via `readPixels`/GL-error checks rather than
local screenshots, per the lesson above.

**User's real screenshots then surfaced several genuine, distinct bugs in one batch:**
- **Every WebGL view was upside down.** Root cause: `texImage2D` uploads an image's rows top-first
  into a texture space where v=0 is conventionally the *bottom* — needed
  `gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true)`. One-line fix in the shared `makeTexture()`, verified
  with a real signal (brightness `readPixels` comparison: canvas-bottom now matches the source
  photo's actual road brightness, canvas-top matches its sky/trees), not a screenshot.
- **Display size was capped at the source photo's native pixel width** (`Math.min(displayWidth,
  width)`), so small source photos rendered tiny regardless of the wide layout. Removed the cap.
- **3D relief showed ugly stretched spikes** at depth discontinuities (bike silhouette vs.
  background) — a classic displaced-mesh artifact. First fix (discard any mesh quad whose corners
  disagreed too much after light smoothing) assumed depth is mostly flat with a few clean edges; real
  photos aren't — bike spokes alternate near/far every few pixels, so it punched holes all over the
  mesh, not just at the silhouette. **User: "3d is uglier, fix it, don't waste my time."** Corrected:
  removed discarding entirely, replaced with much heavier smoothing (radius 5, up from 1) of the
  geometry only — the color texture on top stays sharp regardless, the mesh underneath only needs
  broad shape.

Also, per direct user questions, clarified in plain text (no build) what Bokeh and AR occlusion
concretely demonstrate, tied to what's actually on screen, and answered a design question about
adding real-world height-field "2.5D" rotation (foreshadowing the relief mode) and Histogram of
Oriented Gradients use cases — both in the abstract and, later, concretely inside this project
(edge-aware smoothing for the relief mesh, not yet built).

## Part 6 — Second bug-report round: AR marker mislocation, relief tearing on hover, unclear captions

- **Parallax edge streaking**: hovering caused visible tearing right along hard depth edges (car/bike
  frame against background) — sampling a *displacement field* at a hard edge means neighboring screen
  pixels pull from very different source UVs. Fixed by blurring only the copy of the depth map used
  to compute displacement (`blurredCanvas()` in `webglUtils.ts`), never the color image itself.
- **AR occlusion marker mispositioned**: user reported clicking placed the marker "somewhere else."
  Real bug — the DOM click handler measured Y the normal way (0=top), but the shader's UV space has Y
  flipped (0=bottom) from the fullscreen quad's own convention. A click near the top placed the marker
  near the bottom. Fixed by flipping the click's Y before storing it; verified with an actual off-center
  click test (pink pixel confirmed appearing exactly where clicked, both top and bottom).
- **AR occlusion "what's the pink thing"**: added the ability to upload a custom image as the marker
  instead of the flat pink dot (second texture unit, same occlusion shader logic).
- **3D relief texture also upside down**, a *different* instance of the flip issue: the mesh's UV
  coordinates were built from the depth sampler's own top-down convention, but the color texture is
  now flip-uploaded — so the mesh's "top" vertex sampled the photo's bottom row. Fixed by flipping
  only the texture-sampling UV (`1 - v`), not the geometry's own vertex position.
- Rewrote the Bokeh/AR-occlusion in-UI captions to explain the concrete real-world thing each
  demonstrates (portrait-mode blur; AR objects hiding behind nearer real content) rather than
  restating the button label, after the user said the purpose still wasn't clear from the first
  round of captions.

## Part 7 — Live verification discipline, enforced by the user

User explicitly pushed back on being told things were "verified" via my own local test harness:
**"start all over again and also verify if the feature is working fine or not," "ask me to proceed or
not when using playwright."** From this point on, every individual Playwright action (navigate,
click, upload, evaluate) was proposed and explicitly approved one at a time, and verification moved
to testing the actual **live deployed Vercel site**, not localhost — using a real user-supplied photo
(`campbell-3ZUsNJhi_Ik-unsplash.jpg`, a Porsche with strong sky/road brightness contrast, chosen as a
much better test case than the bicycle's fine spoke detail).

Verified on the live site with concrete numeric evidence, not assertions:
- Parallax: orientation correct (screen-top brightness 238.9 ≈ source sky 239; screen-bottom 65.1 ≈
  source road 65), and sample pixels measurably change with pointer position.
- AR occlusion: clicking top vs. bottom moved the marker to the correct location both ways, old
  location cleared back to normal photo color.
- Bokeh: local sharpness variance at the license plate went 344 (blurred, focused on distant sky) →
  7019 (sharp, focused on the plate) — a 20x swing, real depth-based blur.
- 3D relief: orientation correct, drag response confirmed.

## Part 8 — 3D relief still didn't feel like real 3D — root-caused and fixed properly

**User: "its not 3d, 3d doesn't look like that, it is as if i am just moving the full image left to
right, nothing 3d about it."** Rather than re-asserting it was real, checked the actual math: measured
on the live photo that the background moved 154px while the near foreground moved only 42px —
*backwards* from real depth, and confirmed analytically why: under object *rotation*, a point's screen
motion is dominated by its own x/y position relative to the rotation center, not its depth, when the
photo's spatial extent (±1.85 units) dwarfs its depth range (0.6 units) — true regardless of camera
distance or FOV tuning, since the ratio of depth-motion to position-motion under rotation is
independent of rotation angle.

**Real fix**: replaced object rotation with camera-shift parallax — drag moves the *camera* sideways
while the object stays still. Under perspective projection this makes near points move more than far
points automatically (1/distance falloff), the same principle behind real motion parallax and the same
one the 2D Parallax tab already used successfully, just now through a real camera on real 3D geometry.
First pass at this (`DEPTH_SCALE 0.6→0.9`, `CAMERA_DISTANCE 2.4→1.8`, wider FOV, aiming for a bigger
near/far differential) reintroduced a *worse* bug: the frustum-fit math used the far/base plane's
distance to check framing margin instead of the near plane's (the more restrictive case, since near
content occupies more of the frustum) — **the car was clipping at rest, and any drag pushed it fully
out of frame.** User: "the image moved horizontally and it went out of frame."

Corrected by re-deriving `CAMERA_DISTANCE`/`DEPTH_SCALE`/`FOV_RAD` together against the *near*-plane
margin specifically, and computing the camera shift limit dynamically from that real margin (scaled to
the photo's own aspect ratio) instead of a fixed guessed constant — so this class of bug can't recur
for a different photo shape. Verified properly this time: sampled real content well inside the frame
(not at the edge, where an intentional letterbox safety margin is expected and was mistaken for a bug
on the first check) at both drag extremes — confirmed it stays real photo color, never the canvas
clear color, in both directions. Re-verified the near/far differential is still correctly signed (car
52px vs. background 44px) after the corrected tuning.

## Commits

**ML-Unified**: `c164777` (backend `mm_depth.py` + Depth-Anything-V2-Small model files).

**ml-portfolio**: `1afb894` (base tool, tile-grid parallax), `0e6b6ad` (tearing patch, later
superseded), `054f1cf` (real per-pixel shader rewrite + wide layout + Bokeh + AR occlusion),
`401843e` (3D relief, first version), `0cfe1d0` (flip fix + display-size fix + relief-spike fix +
clearer captions), `54c2595` (Parallax edge-streak fix + relief-hole fix + custom AR marker),
`5ecea27` (relief texture-UV flip + AR marker click Y-axis fix + peek animation), `ff7434b` (3D relief
switched from rotation to camera-shift, corrected frustum framing).

## How to apply

- Don't re-litigate per-pixel-shader-vs-tile-grid for Parallax, or rotation-vs-camera-shift for 3D
  relief — both are settled, evidence-backed decisions in this file.
- `UNPACK_FLIP_Y_WEBGL` must be set on every texture upload in this tool (`makeTexture()` already
  handles it) — and remember any *new* UV-generating code (like the relief mesh) needs its own
  matching flip, since the fix isn't automatically inherited by hand-built UV coordinates.
- Don't trust local screenshots of WebGL canvases on this machine for pixel-level judgment — see
  [[feedback_local_webgl_screenshot_unreliable]]. Use `readPixels`/GL-error/DOM checks, and ask the
  user to confirm anything visually subtle.
- When tuning a 3D camera/frustum, always check framing margin against the *nearest* rendered plane,
  not the nominal/base camera distance — the near plane is the restrictive case.
- The user now expects each individual Playwright tool call proposed and approved one at a time
  during live verification — see [[feedback_local_webgl_screenshot_unreliable]] and this session's
  Part 7 for why that expectation was set.
