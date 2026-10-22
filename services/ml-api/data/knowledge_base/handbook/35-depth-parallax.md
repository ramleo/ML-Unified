Chapter 28Depth Parallax


> Upload one photo and get a per-pixel depth map, then watch it become a parallax diorama — near objects shift more than far ones as you move your pointer. The model runs on this project's own server rather than any third-party AI provider — your photo is sent there to build the depth map, processed in memory and not stored.

## At a glance

| | |
|---|---|
| **Also called** | One Photo, Instant 3D |
| **Model or method** | Depth-Anything-V2-Small (ONNX) |
| **What you give it** | Single photo |
| **Model Size** | 37MB |
| **Where it runs** | On the server |
| **Find it at** | `/tools/depth-parallax` |

## Using the tool

### What this tool does
Upload one photo and get a **per-pixel depth map** — how near or far each pixel is —
then watch it become a **parallax diorama**: near objects shift more than far ones as
you move your pointer. The depth model runs on this project's own server (not a
third-party AI provider); your photo is sent there to build the depth map, processed in
memory, and **not stored**. The visual effects then render in your browser with WebGL.

### Purpose
Monocular depth estimation — guessing 3D structure from a single flat photo — is one of
the more striking things a vision model can do. This tool makes it tangible: it turns
the raw depth map into several effects you can actually see and move.

### How to use it
1. **Upload a photo** (one with clear near and far elements — a person in front of a
   background — shows the effect best).
2. Wait for the **depth map** to be built on the server.
3. Pick a **mode** and move your pointer over the image:
   - **Parallax** — near things shift more than far things as you move.
   - **Depth map** — the raw near→far map itself.
   - **Bokeh** — far regions blurred, near kept sharp (depth-of-field).
   - **AR occlusion** — a placed object sits correctly in front of/behind scene depth.
   - **3D relief** — the image pushed into a depth-shaded surface.

### A worked example
Upload a portrait with a background a few metres back. In **Parallax**, moving the
pointer makes the subject glide against the background like a diorama. Switch to
**Bokeh** and the background softens while the face stays sharp — the classic
portrait-mode look, produced from the single photo's depth.

### Reading the result
- Brighter/closer vs darker/farther in the **depth map** shows what the model inferred.
- Clean subject/background separation = a good depth estimate; fuzzy edges or haloing
  around the subject = the model was unsure there.

### Notes & limits
- **Single-image depth is an estimate, not a measurement.** Thin objects, reflections,
  glass and flat textureless walls are the usual trouble spots.
- **Effects run in your browser (WebGL).** Only the depth map is computed on the
  server; the parallax/bokeh/relief rendering is client-side.
- **Privacy.** Your photo is used only to build the depth map, processed in memory, and
  not retained.

## What problem it solves

A photograph is flat. It records where light landed on a sensor and throws away
how far each thing was.

Recovering that distance from **one** picture is a genuinely hard problem,
because it is ambiguous: a small object close up and a large object far away
project to exactly the same pixels. Two eyes solve it by comparing views. One
camera cannot, and has to *infer* depth from everything else in the image —
occlusion, perspective, texture getting finer with distance, familiar object
sizes, shading, haze.

This tool does that inference and then does something with the answer. Upload
one photo, get a per-pixel depth map, and then use it five ways: a parallax
diorama that shifts as you move the pointer, the raw depth map, a portrait-mode
background blur, an AR occlusion demo, and a draggable 3D relief.

## How it works, step by step

1. **Upload one photo.**
2. **The server estimates depth.** The image is capped at 1,024 px on the long
   side, resized so its short side is about 518 px in multiples of 14,
   normalised with ImageNet statistics, and pushed through the model.
3. **The output is normalised per image** to 0–255 and written back out as a
   greyscale PNG at the original photo's size. Brighter means nearer.
4. **The browser takes over.** From here everything is WebGL on your own
   machine, with the photo as one texture and the depth map as another.

Five views, all driven by that one depth map:

| View | What it does |
|---|---|
| **Parallax** | shifts each pixel by an amount proportional to its depth, following your pointer |
| **Depth map** | the raw greyscale output |
| **Bokeh** | pick a point to keep sharp; everything blurs by how far its depth is from that point |
| **AR occlusion** | places an object *into* the scene so nearer things correctly hide it |
| **3D relief** | builds real geometry from the depth map and lets you move a camera around it |

## The model or algorithm

### Depth-Anything-V2-Small

37 MB, quantised ONNX, built on a DINOv2 backbone. From
`onnx-community/depth-anything-v2-small-ONNX`.

**Two things about it are worth being precise on.**

**It is relative depth, not metric.** The model makes no claim about real-world
units. It gives correct *ordering* within a single image — this is nearer than
that — and nothing more. There is no scale to recover, which is why the output
is normalised per image with no attempt to preserve a value across photos. For
driving a parallax effect that is exactly enough and nothing is lost. For
measuring a room it would be useless.

**The licence was checked at the checkpoint level.** The docstring records that
the upstream `DepthAnything/Depth-Anything-V2` repository licenses the **Small**
checkpoint as Apache-2.0, while Base, Large and Giant are CC-BY-NC-4.0. Only
Small is used. That distinction is inside one repository, under one model
family — exactly the kind of thing a licence badge does not tell you.

It was also verified by hand before adoption: real inference on a real photo of
a car, confirming the map cleanly separated foreground from background with a
smooth gradient rather than noise.

### Why 518 and multiples of 14

DINOv2 is a vision transformer, and a transformer cuts its input into fixed
patches — 14×14 pixels here. An input whose dimensions are not multiples of 14
does not tile cleanly. So the resize targets a short side of about 518, then
rounds both dimensions to the nearest multiple of 14. Those numbers are copied
from the model's own `preprocessor_config.json` rather than guessed, which is
the same discipline as the liveness chapter's crop: **preprocessing must match
training, exactly.**

The 1,024 px cap on the input is a compute decision — a 37 MB model on CPU
against a full-resolution phone photo is slow, and the extra pixels do not
improve a depth map that will be resized back down anyway.

### The parallax shader

This is the most interesting piece of the tool, and it is nine lines:

```glsl
float depth = texture2D(uDepth, vUv).r;      // 0..1, higher = nearer
vec2 shift = depth * uMaxShift * vec2(uPointer.x * 2.0,
                                      uPointer.y * 2.0 * 0.6);
gl_FragColor = texture2D(uImage, clamp(vUv - shift, 0.0, 1.0));
```

Read it backwards and the trick is clear: for each output pixel, look up its
depth, then sample the source image from a position **offset by that depth**.
Near pixels (depth near 1) pull from far away; distant pixels (depth near 0)
barely move. That difference in movement *is* parallax — the thing your eyes use
to judge distance when you move your head.

Two constants encode judgement:

- `MAX_SHIFT_UV = 0.045` — the maximum displacement is 4.5% of the image. Small
  on purpose: pushing it further reveals that there is nothing behind the
  foreground to show, and the illusion breaks into smearing.
- The vertical shift is scaled by **0.6**. Horizontal head movement is what
  produces parallax in real life; damping the vertical axis keeps the effect
  feeling like looking round something rather than like the picture wobbling.

**The bug this design fixes.** The depth map used to compute displacement is
blurred by 3 px first, and the comment explains why. A real object edge — a bike
frame against the sky — is a genuine hard depth jump. But the shader is
sampling a *displacement field*, and at a hard edge two neighbouring screen
pixels pull from very different source positions, which shows up as streaky
tearing right along the edge as soon as the shift is non-zero. Blurring the
depth copy softens the field without touching the displayed image. It is a good
illustration of a general point: a discontinuity that is correct in the data can
still be wrong in the thing you compute from it.

### Bokeh

A 9-tap blur whose radius is driven by how far a pixel's depth is from the depth
you clicked:

```
blur ∝ |depth(pixel) − depth(focus point)|
```

That is the same idea as a real lens: a physical aperture has one plane in
focus, and everything in front of or behind it lands on the sensor as a disc
rather than a point. The code is honest that it is an approximation — a fixed
nine-tap box-ish blur, not a true circle of confusion — but the *shape* of the
effect is right, and unlike a real lens you can move the focal plane after the
photo was taken.

### 3D relief

The other four views are screen-space tricks. This one builds actual geometry: a
mesh where each vertex's height comes from the depth map, textured with the
photo, viewed through a real camera matrix. Dragging moves the camera sideways
rather than rotating the picture, so near things move more than far things for
the correct reason rather than by simulation.

Two details in the mesh builder matter. The depth grid is **smoothed** over a
5-cell radius, for the same reason the parallax depth is blurred — a spike in
the height field is a spike in the geometry. And the outer 14 cells are
**feathered**, so the mesh does not end in a hard cliff at the image border.

The camera range is deliberately limited, and the reason given is the honest
one: **a single photo only ever saw its camera-facing surface.** Move far
enough round and you are looking at the back of a shape that has no back.

## Why these choices

**Why run the model server-side and everything else in the browser.** The 37 MB
model would be a slow download and a slow CPU inference in a tab. But once the
depth map exists it is just a texture, and every effect built on it is a shader
running at 60 frames a second on the viewer's GPU. One request, then no
round-trips. The card discloses the split plainly: the photo goes to this
project's own server, not a third-party AI provider, is processed in memory and
not stored.

**Why five views instead of one.** A depth map on its own is a grey picture that
means nothing to most people. Parallax makes it *felt*, bokeh makes it
*familiar* — everyone has used portrait mode — occlusion makes it *useful*, and
the relief makes it *literal*. Together they answer "what is depth estimation
for?" better than any one of them.

**Why the effect is deliberately understated.** The single most common way this
kind of demo fails is being pushed too far. `MAX_SHIFT_UV = 0.045` and the
limited relief camera range are both the same decision: stay inside what one
photograph can actually support.

## How to read the output

- **Brighter is nearer.** The absolute values mean nothing across photos.
- **Look at the edges in the depth map.** Clean silhouettes mean the model
  understood the scene; a foreground object bleeding into the background is
  where every downstream effect will look wrong.
- **Parallax works best on a photo with real depth separation** — a subject with
  distinct background. A flat wall or a landscape at infinity produces almost no
  shift, correctly.
- **Streaking at the edge of the frame is expected.** Shifting reveals pixels
  that the photograph does not contain, and the shader clamps to the edge rather
  than inventing them.
- **In bokeh, click the thing you want sharp.** The focal plane is where you
  clicked, in depth, not in position — so anything at the same distance stays
  sharp too, exactly like a real lens.
- **In the relief, small camera movements read best.** Push it and the missing
  back faces show.

## Limits

- **Relative depth, not metric.** No distances, no measurements, nothing
  comparable between photos.
- **A single photo has no hidden surfaces.** Parallax, occlusion and relief are
  all limited by there being nothing behind the foreground. This is the hard
  ceiling on all of it.
- **Monocular depth is inference, not measurement.** It fails in the ways human
  intuition fails: reflections, glass, mirrors, a poster of a landscape on a
  wall, unfamiliar object scales.
- **Input capped at 1,024 px**, so fine detail in a large photo is lost before
  the model sees it.
- **The depth map is blurred and smoothed before use**, so genuinely thin
  structures — railings, hair, wires — soften.
- **Bokeh is a nine-tap approximation**, not a lens simulation. No bokeh shape,
  no highlight blooming.
- **WebGL is required** for four of the five views, and the tool detects and
  reports failure rather than showing a blank canvas.
- **CPU inference on free hosting**, so the first request after the server has
  been asleep is slow.

## Likely interview questions

**"How can a single image give you depth at all? Isn't it ambiguous?"**
Fundamentally, yes — a small near object and a large far one project identically,
so there is no geometric solution. Monocular depth models get around it by
learning priors from enormous amounts of data: occlusion order, perspective
convergence, texture gradients, typical object sizes, shading, haze. It is the
same set of cues a person uses looking at a photograph with one eye closed. That
is also why the output is relative rather than metric — the cues fix ordering,
not scale.

**"What's the difference between relative and metric depth, and why does it
matter?"**
Relative depth gives correct ordering within one image; metric gives actual
distances. For a parallax effect, ordering is all you need, so relative is
sufficient and the model is honest about not claiming more. For robotics,
measurement or reconstruction you need metric depth, which requires either a
calibrated camera, stereo, a known-size reference in frame, or a depth sensor.

**"Explain your parallax shader."**
For each output pixel, read its depth from the depth texture, multiply by the
pointer offset and a maximum shift, and sample the source image from the offset
position instead of the original one. Near pixels move more than far ones, which
is exactly parallax. The one non-obvious part is that the depth map used for the
displacement is blurred by three pixels — at a hard depth edge, adjacent screen
pixels would otherwise pull from wildly different source positions and produce
visible tearing along every silhouette.

**"Why blur the depth map if the edges are correct?"**
Because it is not being displayed, it is being used as a *displacement field*.
A discontinuity that is correct as data becomes a discontinuity in where
neighbouring pixels sample from, and that reads as tearing. The displayed image
is untouched; only the copy driving the maths is softened. It is a good example
of a value being right for one purpose and wrong for another.

**"Why did you use the Small checkpoint?"**
Partly size — 37 MB runs on CPU on free hosting where Large would not. But
mainly licensing: in that repository the Small checkpoint is Apache-2.0 while
Base, Large and Giant are CC-BY-NC-4.0, so the larger ones cannot be used in
anything commercial. That distinction lives inside one repo under one model
family, so I checked the LICENSE directly rather than trusting the badge — the
same habit that caught a weights-versus-code licence mismatch elsewhere in this
project.
