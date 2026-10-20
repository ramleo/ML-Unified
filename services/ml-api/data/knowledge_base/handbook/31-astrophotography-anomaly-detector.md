Chapter 25Astrophotography Anomaly Detector


> Upload 5-30 frames from one fixed-tripod night session and find the meteor and satellite streaks in them. Time-adjacent frames are differenced and a Hough transform picks out the trails; a drifting star leaves a paired positive/negative streak that cancels, while a real transient leaves a one-sided one. You also get a median-stacked clean image with those transients removed. It will not tell you which is a meteor and which is a satellite — that proved unreliable to call from a single session, so every hit is labelled as possibly either. Classical OpenCV throughout; no neural network, no GPU.

## At a glance

| | |
|---|---|
| **Also called** | Frame Differencing + Hough Transform |
| **Model or method** | OpenCV Hough Transform |
| **What you give it** | 5-30 Images |
| **API Calls** | 0 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/astrophotography-anomaly-detector` |

## Using the tool

### What this tool does
Upload 5-30 photos from one fixed-tripod night-sky session, in order, and
this detects meteor and satellite streaks using the real technique
operational meteor/satellite-trail detectors use: differencing
time-adjacent frames, then running a Hough transform on the difference to
find candidate line segments. It also returns a median-stacked "clean"
image of the whole session.

### Purpose
Frame differencing + Hough-transform line detection is the standard
approach in published meteor/satellite-detection systems and real
hobbyist tools (not invented for this project). The key insight that
makes it work: a star drifting slightly between two frames (sky rotation,
no tracking mount) leaves a **dipole** in the difference image — a bright
streak where it moved to, paired with a dark streak where it moved from.
A meteor or satellite trail, present in only one of the two frames,
leaves a **monopole** — one-sided, with no matching opposite-sign
counterpart. This tool filters out dipoles and keeps monopoles as
candidate anomalies.

### How to use it
1. Upload 5-30 photos taken in sequence from a fixed tripod (same
   framing). No image-stacking software needed — just your own JPEGs/PNGs
   in the order they were taken.
2. Click **Detect anomalies**. This is pure classical OpenCV (no neural
   network), so it runs in well under a second even on CPU-only hosting.
3. Review each detected anomaly's cropped preview, drawn on the real
   photo (not the difference image) so you can sanity-check it yourself.
4. Download the median-stacked image for a cleaner view of just the stars.

### A worked example
Verified first against synthetic ground truth (no real astrophotography
session was available to test with — disclosed here rather than glossed
over): a synthetic sequence of 50 drifting "stars" alone produced zero
false-positive detections once the dipole filter was applied. Injecting a
single-frame bright line (simulating a meteor) was correctly detected as
one anomaly; injecting a line that shifted position across three
consecutive frames (simulating a satellite crossing several exposures)
was also correctly detected as a separate anomaly. The median stack of
the star-only sequence fully suppressed both injected transients (down to
the background level) while preserving every star.

### Reading the result
- **Anomaly cards** — each shows the frame range it was found in, its
  length and angle, and a cropped preview with the detected line drawn on
  the original photo.
- **"No anomalies found"** means nothing crossed the detection threshold
  in this session — not a guarantee nothing happened. A faint meteor can
  fall below it.
- **Median stack** — a pixel-wise median across all uploaded frames.
  Meteors and satellites are single-frame outliers at their pixels and
  get rejected by the median; stars, present in every frame, survive.

### Notes & limits
- **No star-based registration.** Real stacking software (DeepSkyStacker,
  Siril) aligns frames by matching star patterns before stacking. This
  tool deliberately skips that and compares/stacks frames exactly as
  uploaded — it works best when the camera didn't move between shots.
- **No meteor-vs-satellite verdict.** This was attempted and rejected
  after testing against synthetic ground truth: a satellite's
  frame-to-frame position shift is almost entirely *along* its own line
  direction (real motion projected onto the sky), which looks
  geometrically near-identical to "the same flash, stationary" using
  position drift alone. Real classification needs proper multi-frame
  trajectory/velocity modeling that this tool doesn't attempt. Every
  detection is labeled "possible meteor or satellite trail," never a
  confident category.
- **A persisting object crossing many consecutive frames may only be
  flagged once** (at its first appearance), not once per frame, since its
  later legs can look dipole-like against its own immediately preceding
  position.
- **Not validated on a real photo session** — only against synthetic
  ground-truth data with known injected anomalies, disclosed above.

## What problem it solves

A night of astrophotography is a few hundred long exposures of the same patch of
sky. Somewhere in them there may be a meteor, or a satellite trail, or an
aircraft. Finding them means opening every frame and looking.

The obvious automation — find bright streaks — does not work, and the reason is
the whole problem. On a fixed tripod with no tracking mount, **every star moves
between frames**, because the Earth is rotating. Each star leaves a short trail.
A detector that flags streaks flags every star in the frame.

So the real question is not *"is there a line here?"* but *"is this line
something that was not there a moment ago?"* This tool answers that with a
physical distinction that is simple, exact, and needs no neural network at all.

## How it works, step by step

1. **Upload a sequence** of frames from one fixed-tripod session, in order.
2. **Difference each adjacent pair** — frame B minus frame A, keeping the sign.
3. **Find candidate lines** in each difference image with a Hough transform.
4. **Deduplicate** the near-identical segments Hough returns for one real line.
5. **Test each line for polarity** — the key step.
6. **Link a streak across consecutive pairs** so one real event is counted once.
7. **Crop and annotate** each surviving anomaly.
8. **Median-stack** the whole sequence into one clean image.

## The model or algorithm

### The dipole/monopole discriminator

This is the idea the tool is built on, and it is worth stating precisely.

Subtract frame A from frame B and **keep the sign** — not the absolute
difference:

**A star that moved** (sky rotation, no tracking) is present in both frames, in
slightly different places. In the signed difference it appears as a **dipole**:
positive where it moved *to*, negative where it moved *from*. Bright and dark,
side by side.

**A meteor or satellite trail** is in one frame and not the other. It has nowhere
to have moved from. In the signed difference it is a **monopole**: one-sided,
positive with no matching negative.

That single distinction separates the thing you want from the thing that fills
the frame, and it is a fact about the physics rather than a learned pattern.

**The absolute difference destroys it.** `|B − A|` makes the dipole's dark half
positive, and the star becomes two bright blobs — indistinguishable from a real
streak. Keeping the sign is the entire trick.

### Measuring the polarity

For each candidate line, the code walks along it and samples a band of pixels on
**both sides**, using the line's perpendicular normal, out to a few pixels either
way. It sums the positive difference values and the negative ones separately.

- A **dipole** has substantial totals on both sides — a moved star.
- A **monopole** has one large total and a near-zero opposite — a real anomaly.

That ratio is the streak's `monopole_strength`, and it is what the detection
threshold is applied to.

### The Hough transform

Hough line detection re-poses the problem: instead of searching the image for
lines, every edge pixel votes in a parameter space of all possible lines
(`rho`, `theta`), and lines that many pixels agree on accumulate peaks. Its
strength is that it finds a line even when it is **broken** — a faint meteor
sampled as a dotted trail still votes coherently — which is exactly the case
here.

Its known weakness is returning several near-identical segments for one real
line, so a deduplication pass merges anything within 15 pixels and 8 degrees.

### Linking across pairs, and why one event produces two detections

A subtle consequence of differencing that is easy to get wrong.

A meteor visible in frame 2 only appears **twice** in the difference sequence:
positive in the (1→2) difference, when it arrives, and negative in the (2→3)
difference, when it disappears. One real event, two detections.

So streaks are forward-linked across consecutive pairs by angle and position —
within 8 degrees and a bounded distance — and merged into a single anomaly. Without
this the tool would double-count every meteor.

### The classification the tool refuses to make

It reports "possible meteor or satellite" and never picks. The reason recorded in
the code is a real negative result, and it is the most interesting thing in the
module:

> *A satellite's frame-to-frame position shift is almost entirely **along its own
> line direction** — real orbital motion projected onto the sky — which is
> geometrically near-indistinguishable from "the same flash, stationary" using
> position drift alone. Tested against synthetic ground truth and found
> unreliable: a moving satellite streak and a stationary flash both produce
> near-zero measured drift.*

The obvious feature — how far did it move — does not separate the two classes,
because movement along a line looks like no movement when all you can measure is
the line's position. Real classification needs multi-frame trajectory and
velocity modelling. The tool says "possible" rather than inventing a confident
label, and the code names that as the same discipline applied elsewhere in the
project.

**"No anomalies found" is also given its honest meaning:** nothing crossed the
threshold, not that nothing happened. A faint meteor falls below it.

### Median stacking

Alongside detection, the sequence is stacked by taking the **median** of each
pixel across all frames.

Median rather than mean, for a specific reason: a mean includes every transient —
a meteor, a satellite, a plane, a cosmic-ray hit — as a faint ghost. The median
takes the middle value at each pixel, so anything appearing in a minority of
frames is discarded entirely while the constant background survives and its
random noise is suppressed. It is the standard robust estimator, and here the
transients it rejects are exactly what the detector is separately looking for.

## Why these choices

**Why classical CV and no neural network.** The discriminating feature is
*physical* — a moved object leaves a signed dipole, a new object does not. That
is exact, needs no training data, and generalises to any sky. A CNN would need a
labelled dataset of meteors that does not exist, and would learn a fuzzy version
of a rule that can be stated in one sentence.

**Why no plate solving.** DeepSkyStacker and Siril register frames against
detected star fields before stacking, which corrects for sky rotation properly.
This tool assumes a static tripod and compares frames as uploaded, which is
disclosed rather than implied. Plate solving is a substantial piece of
astronomy-specific machinery, and without it the dipole signature is actually the
*mechanism* — the very rotation that registration would remove is what makes
stars distinguishable from transients.

**Why report "possible".** Covered above: no ground truth to validate a
classifier, and the obvious geometric feature was tested and failed.

## How to read the output

- **Each anomaly comes with a crop.** Look at it. A satellite trail is long,
  straight and uniform; a meteor usually brightens and fades along its length;
  an aircraft often shows regular gaps from strobes.
- **"Possible meteor or satellite" is the honest label.** It is not hedging — the
  distinction genuinely cannot be made from this data.
- **Nothing found means nothing crossed the threshold.**
- **Check the stack for what the detector missed.** A transient sitting in the
  median-stacked image is bright enough to have survived the median, which is
  unusual and worth looking at.
- **A field full of detections means the tripod moved.** If the camera shifted
  between frames, every star becomes a large dipole and some will read as
  monopoles.
- **Frame order matters.** The sequence is compared as uploaded.

## Limits

- **Static tripod assumed.** No registration, no plate solving. A bumped tripod
  invalidates the run.
- **No meteor-versus-satellite verdict**, for the reason tested and recorded
  above.
- **Faint transients below the threshold are missed silently.**
- **Aircraft, birds, insects and cosmic-ray hits all produce monopoles too.**
  Anything present in one frame and not the next looks the same.
- **Sequences are processed in upload order** with no timestamp checking.
- **A cloud edge drifting through frame** produces large signed differences that
  are not point-like but can still generate Hough lines.
- **Long exposures with heavy star trailing** blur the dipole signature, since a
  star trail is already a line in each frame.
- **Frames are downscaled** before processing, so the finest trails are lost
  before detection runs.

## Likely interview questions

**"Every star moves between frames. How do you avoid flagging all of them?"**
By keeping the *sign* of the difference. A star that moved is in both frames, so
it leaves a dipole — positive where it moved to, negative where it moved from. A
meteor is in one frame only, so it leaves a monopole with no opposite-sign
counterpart. Measuring the positive and negative sums in a band either side of
each candidate line separates them exactly. If you take the absolute difference
instead, the dipole's dark half becomes bright and every star looks like a
streak.

**"Why a Hough transform rather than an edge detector?"**
Because Hough finds lines that are broken. Every edge pixel votes in a parameter
space of possible lines and coherent lines accumulate peaks, so a faint meteor
that appears as a dotted trail still registers as one line. Its cost is returning
several near-identical segments per real line, which is why there is a
deduplication pass at 15 pixels and 8 degrees.

**"Why won't it say whether it's a meteor or a satellite?"**
Because I tested the obvious feature and it failed. A satellite's frame-to-frame
shift is almost entirely *along* its own line — orbital motion projected onto the
sky — which is geometrically near-indistinguishable from a stationary flash when
all you can measure is the line's position. Against synthetic ground truth both
produced near-zero measured drift. Doing it properly needs multi-frame trajectory
and velocity modelling. Labelling it confidently would be overclaiming, so it
says "possible".

**"Why does one meteor produce two detections?"**
Because differencing is pairwise. A meteor in frame 2 appears positive in the
1→2 difference when it arrives and negative in the 2→3 difference when it goes.
One event, two signals. Streaks are forward-linked across consecutive pairs by
angle and position and merged, otherwise every meteor is counted twice.

**"Why median stacking rather than averaging?"**
Because the mean includes every transient as a faint ghost — the meteor you are
trying to isolate ends up smeared into the background image. The median takes the
middle value per pixel, so anything present in a minority of frames is discarded
outright while the constant sky survives and its random noise is suppressed. It
is the robust estimator, and here the outliers it rejects are precisely the
events the detector is looking for.

**"Why no neural network?"**
Because the discriminating feature is physical rather than statistical. "A moved
object leaves a signed dipole, a new object does not" is exact, needs no training
data, and works on any sky. A CNN would need a labelled meteor dataset that does
not really exist and would learn an approximate version of a rule I can state in
one sentence. Reaching for a model when a physical invariant is available is
usually the wrong instinct.
