Chapter 30Movement Form Comparison


> Upload a clip of your own movement and a reference clip of the same exercise, and see where your form differs. Body pose is tracked in both, six joint angles (elbows, knees, hips) are computed from 3D landmarks, and the two clips are stretched onto a shared 0-100% movement-phase axis so a 4-second rep compares directly against a 6-second one. Joints are ranked by how far apart they drift, with the single worst moment called out for each. Assumes one person and one full rep per clip — a training aid, not a clinical assessment. Runs entirely in the browser; no video leaves your device.

## At a glance

| | |
|---|---|
| **Also called** | Client-Side · No API Cost |
| **Model or method** | MediaPipe PoseLandmarker (local) |
| **What you give it** | 2 Videos |
| **API Calls** | 0 |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/movement-form-comparison` |

## Using the tool

### What this tool does
Upload your video of an exercise and a reference video of the same
exercise, and this tracks body pose in both with MediaPipe, computes 6
real joint angles (left/right elbow, knee, hip), and compares them on a
shared 0-100% movement-phase axis so a 4-second clip is directly
comparable to an 8-second one.

### Purpose
MediaPipe joint-angle extraction is a validated technique — published
studies report under 10% error versus marker-based motion capture for
hip/knee angles, and joint-angle classifiers reach over 97% accuracy
distinguishing correct from incorrect form. This is a real measurement
pipeline, not a heuristic gamble: 3D world-landmark coordinates (metric,
camera-distance-invariant) feed a standard 3-point vector-angle formula
at each joint, and each video's own angle-vs-time curve is resampled onto
its own 0-100% phase axis before comparison — the key piece of real
engineering that makes clips of different length and speed comparable.

### How to use it
1. Trim both videos to one full rep, start to finish (≤30s each).
2. Upload **Your movement** and a **Reference movement** of the same
   exercise — ideally a correct-form example.
3. Click **Compare movements**. Pose tracking and angle extraction run
   entirely in your browser; no video is uploaded anywhere.
4. Review the joint charts, ranked worst-deviation-first.

### A worked example
Verified against two real downloaded stock squat videos — different
people, different camera angles, different clip durations — before this
was considered working: the pipeline produced 6 distinct, non-garbage
joint-angle charts correctly ranked by deviation, with no manual
alignment needed despite the clips' different lengths.

### Reading the result
- **Each joint chart** — your angle curve (solid) versus the reference
  (dashed), both plotted on the shared 0-100% movement-phase axis, plus
  the RMS (root-mean-square) angle deviation across the whole rep.
- **"Biggest gap at N% through the movement"** — the single phase point
  where your angle differed most from the reference, in degrees, so you
  know exactly where in the rep to focus rather than just an aggregate
  score.
- **Joints are ranked worst-first** so the most useful comparison is
  always at the top.

### Notes & limits
- **One person, one full rep.** No rep counting or auto-segmentation is
  attempted — upload a clip that's already trimmed to exactly one
  repetition of the movement.
- **A training-form aid, not a clinical or professional-coaching
  assessment.** This surfaces where your joint angles differ from a
  reference, not a diagnosis of injury risk or technique correctness.
- **Reference quality matters.** The comparison is only as good as the
  reference video's own form — this doesn't independently verify the
  reference is "correct."
- **Pose-tracking accuracy depends on video quality.** Poor lighting,
  baggy clothing, or an unusual camera angle can degrade MediaPipe's
  landmark detection, which propagates into the angle measurements.

## What problem it solves

You are doing a squat. Are your knees tracking correctly? Is your hip hinge deep
enough? Is one elbow flaring on the press?

Form feedback normally requires a coach standing next to you, or a video you
watch back and cannot really judge — because the errors that matter are ten or
fifteen degrees, and nobody sees ten degrees by eye in a moving body.

This tool compares your movement against a reference clip, joint by joint, and
tells you **which joint deviates most and at what point in the movement**. Not
"your form is 82% correct" — a specific joint and a specific moment.

Like the gait tool, it runs entirely in your browser. No video leaves the
machine.

## How it works, step by step

1. **Upload two clips** — yours and a reference performance of the same movement.
2. **Extract pose** from every frame of each, in the browser.
3. **Compute six joint angles per frame:** both elbows, both knees, both hips.
4. **Resample each series to 50 points**, so the two clips align by phase rather
   than by time.
5. **Compare point by point**, per joint, with RMS difference in degrees.
6. **Rank the joints worst-first**, and record where in the movement each was
   worst.

## The model or algorithm

### The six angles, and how an angle is computed

Each is the angle at a middle joint, formed by the two segments meeting there:

| Angle | Landmark triple | Anatomically |
|---|---|---|
| Elbow (L/R) | shoulder → elbow → wrist | arm bend |
| Knee (L/R) | hip → knee → ankle | leg bend |
| Hip (L/R) | shoulder → hip → knee | trunk-to-thigh angle |

Computed as the angle between two vectors from the middle point:

```
cos θ = (v₁ · v₂) / (|v₁| |v₂|)
```

with the cosine clamped to [−1, 1] before the arccos, because floating-point
error can push a dot product a hair outside the valid range and `acos` returns
`NaN` for it. A small guard that prevents a whole series turning into nothing.

### 3D world landmarks, not 2D image coordinates

This is the choice the code singles out, and it is the right one to be able to
defend.

MediaPipe returns two things: **normalised 2D image coordinates** (where the
joint appears in the frame) and **3D world landmarks** (an estimated metric
position relative to the hips).

Computing an angle from 2D image coordinates measures the angle **as projected
onto the camera plane** — which changes when the person rotates, moves closer, or
the camera is at a different height. An elbow at a genuine 90° reads as
something else entirely when the arm points toward the lens.

3D world landmarks are camera-distance-invariant and metric, so the angle
computed from them is the actual joint angle. The comment calls it *"the
geometrically correct choice for joint-angle math"*, and it matches the published
MediaPipe approach.

**This is the difference between measuring the movement and measuring the
filming.**

### Phase normalisation

The same mechanism as the Gait chapter, for the same reason. Two people perform
the same movement at different speeds; the same person varies rep to rep. Time is
not a comparable axis.

Each series is resampled to a fixed **50 points**, so the x-axis becomes
*percentage of the movement* — 0 is the start, 49 is the end. After that,
point-for-point comparison is meaningful regardless of tempo.

### RMS, and the worst-phase index

For each joint:

```
RMS = √( mean over the 50 points of (user[i] − reference[i])² )
```

But the RMS alone would say only *how much* you differ. The comparison also
records:

- **`worstPhaseIndex`** — which of the 50 points had the largest single
  deviation
- **`worstDiff`** — how large it was

That converts "your right knee is 14° off" into **"your right knee is 22° off at
about 60% through the movement"** — which is the bottom of a squat, and is
actionable in a way an average is not.

### Ranking worst-first

The joints come back **sorted by RMS descending**, so the first thing you see is
the joint that most needs attention.

That sounds cosmetic and is not. Six joints presented in anatomical order require
the reader to scan and compare. Sorted by deviation, the answer to "what should I
fix?" is the first row. A tool that surfaces the most important finding first is
doing part of the interpretation for you.

## Why these choices

**Why angles rather than positions.** An angle is invariant to where you are in
frame, how far from the camera, and how tall you are. Landmark positions vary
with all three, and a comparison built on them would report differences that are
entirely about the recording. Same argument as the Gait chapter.

**Why six joints.** Elbows, knees and hips cover the major compound movements —
squats, presses, hinges, lunges — with the joints whose angles a pose estimator
resolves reliably. Wrists and ankles are noisier and matter less for form in most
lifts; spine angle needs landmarks a single camera does not give confidently.

**Why left and right separately.** Because asymmetry is one of the most useful
findings available. A comparison that averaged the sides would hide the thing you
most want to know.

**Why the browser.** Video of yourself exercising is personal, and the whole
computation is cheap enough client-side that there is nothing to gain by sending
it anywhere.

## How to read the output

- **Start at the top of the list.** It is sorted by deviation, so the first joint
  is the one to work on.
- **Use the worst-phase index, not just the RMS.** "22° off at 60% through" tells
  you *when* it goes wrong, which is what makes it fixable. 60% of a squat is the
  bottom; 20% of a press is the initial drive.
- **Compare left against right in your own clip** — a large left-right gap is a
  finding on its own and does not need the reference.
- **Film both clips the same way.** Same angle, same distance, same framing. This
  is the biggest confound.
- **The reference has to be the same movement.** Comparing your squat to
  someone's deadlift produces numbers that mean nothing.
- **Small differences are not errors.** Body proportions differ, and two people
  with different limb lengths performing an identical-quality squat will not
  produce identical angle curves.

## Limits

- **No thresholds and no verdict.** It reports degrees; it does not say what
  counts as bad form. Unlike the Gait tool it does not even offer a heuristic
  band — the reader interprets.
- **A reference clip is required**, and the result is only as good as it is.
- **Six joints.** No spine, no shoulder rotation, no ankle dorsiflexion, no foot
  position — several of which matter a great deal for form.
- **Single camera.** Movement toward or away from the lens is the least
  reliably estimated, and 3D world landmarks are an *estimate* of depth, not a
  measurement.
- **Body proportion differences** appear as deviation, and nothing normalises for
  them.
- **Whole-clip phase normalisation.** A clip containing three reps is normalised
  as one 0–100% movement, so the clips need to contain comparable content —
  ideally one rep each.
- **Pose quality is the floor.** Loose clothing, poor light, occlusion by
  equipment.
- **Not coaching.** It measures the difference between two videos. It has no
  model of correct form, no injury awareness, and no idea what you are trying to
  do.

## Likely interview questions

**"Why use 3D world landmarks instead of the 2D image coordinates?"**
Because an angle computed from 2D coordinates is the angle *projected onto the
camera plane*, which changes when the person rotates or moves relative to the
lens. An elbow genuinely at 90° reads as something else when the arm points
toward the camera. World landmarks are metric and camera-distance-invariant, so
the angle you compute is the actual joint angle. It is the difference between
measuring the movement and measuring the filming.

**"How do you compare two clips at different speeds?"**
Phase normalisation. Resample each joint's angle series to a fixed 50 points so
the axis becomes percentage of the movement rather than time. A two-second rep
and a three-second rep then line up point for point. It is the same technique as
clinical gait analysis and it is what makes the comparison possible at all.

**"Why report the worst phase index and not just the average deviation?"**
Because the average is not actionable. "Your right knee is 14° off" gives you
nothing to change. "Your right knee is 22° off at 60% through the movement"
points at the bottom of the squat, which is a specific thing to work on. The
average tells you there is a problem; the phase index tells you where it is.

**"Why sort the joints by deviation?"**
So the answer to "what should I fix?" is the first row. Six joints in anatomical
order make the reader do the comparison themselves; sorted worst-first, the tool
has done part of the interpretation. It is a small decision that changes whether
the output is usable at a glance.

**"Why no verdict — no 'good form' or 'bad form'?"**
Because I have no calibrated basis for one. Correct form depends on the movement,
the person's proportions, their mobility and their goal, and I have no labelled
dataset that maps a degree deviation to a form judgement. The Gait tool at least
offers a heuristic band and says clearly it is uncalibrated; here I would rather
report degrees and a location and let the reader — or their coach — interpret,
than attach a confident label to a number I cannot justify.

**"What's the biggest source of error?"**
Filming inconsistency, by a distance. Different camera angle or distance between
the two clips produces deviation the tool cannot distinguish from a difference in
movement. After that, body proportion differences between you and the reference —
two people performing an identically good squat with different limb lengths will
not produce identical curves, and nothing here normalises for that.
