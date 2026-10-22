Chapter 30Gait Pattern Comparison


> Upload two side-view walking videos and compare how the two people move. Body pose is tracked per frame, individual stride cycles are found from knee-angle peaks, and each video's strides are averaged into one walking signature before the two are compared. This is not identification: a monocular, uncalibrated view can show that two clips walk similarly, never that they are the same person. Runs entirely in the browser; no video leaves your device.

## At a glance

| | |
|---|---|
| **Also called** | Client-Side · No API Cost |
| **Model or method** | MediaPipe PoseLandmarker (local) |
| **What you give it** | 2 Videos |
| **API Calls** | 0 |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/gait-pattern-comparison` |

## Using the tool

### What this tool does
Upload two side-view videos of someone walking. This tracks body pose
frame-by-frame with MediaPipe (the same technique behind this site's
[Movement Form Comparison](/tools/movement-form-comparison) tool), detects
each video's repeating stride cycles from knee-angle peaks, averages the
joint-angle curve across all detected cycles into one "gait signature" per
video, then compares the two signatures.

### Purpose
Real gait-recognition research exists (e.g. the CASIA-B benchmark line of
work) and typically uses silhouette-based Gait Energy Images or deep
embeddings under controlled camera conditions — and even then has real,
non-trivial error rates. This tool demonstrates the underlying *mechanism*
— pose tracking, cyclic stride segmentation, phase-aligned curve comparison
— using the much coarser, honestly-scoped technique of monocular 2D/3D pose
joint angles from an ordinary phone video, not a validated biometric system.

### How to use it
1. Record or find two videos of someone walking from the side, ideally
   showing at least 3-4 full strides, ≤30 seconds each.
2. Upload one to **Video A** and one to **Video B**.
3. Click **Compare gait patterns**.
4. Review each video's detected stride count and cadence, then the overall
   similarity label and per-joint curve comparison.

### A worked example
Upload the same person walking in two different clips (e.g. two takes of
the same walk) as Video A and B — the tool should detect a similar cadence
and stride count in both, and the per-joint curves should track closely,
producing a **"Similar gait pattern"** label. Now try Video B as a clearly
different walking style (much faster or slower pace, or a different
person) — the cadence and curves diverge, and the label shifts to **"Some
differences"** or **"Substantially different"**. If a clip isn't actually
continuous walking (e.g. someone standing still), the tool correctly
reports "not enough consistent strides detected" instead of guessing.

### Reading the result
- **Strides detected / cadence** — shown per video as soon as pose tracking
  finishes, even before comparing; a real measured stride count and
  steps-per-minute estimate.
- **Overall label** — "Similar gait pattern," "Some differences," or
  "Substantially different," based on the average RMS angle difference
  across joints. These thresholds are a reasonable-looking heuristic
  against typical gait knee/ankle angle ranges, **not calibrated against
  any labeled human gait dataset**.
- **Per-joint charts** — each joint's averaged stride-cycle curve for both
  videos overlaid on a shared 0-100% stride-phase axis, plus the RMS
  difference between them.

### Notes & limits
- **Not a validated biometric identification technique.** Camera angle,
  clothing, walking speed, carried objects, and fatigue all measurably
  affect gait appearance — this tool cannot control for any of them.
  Treat a result as "do these two clips show a similar walking pattern,"
  never as proof of identity.
- **No camera calibration.** Distances and speeds are not measured in
  real-world units — only joint *angles*, which are camera-distance-
  invariant when using MediaPipe's 3D world landmarks.
- **Needs a clear side-view of continuous walking.** A frontal view, a
  partially-visible body, or fewer than 2 full strides will correctly fail
  to produce a signature rather than guessing from insufficient data.
- **Assumes one person per video.** Multiple people in frame will confuse
  pose tracking.

## What problem it solves

How someone walks is remarkably individual — and remarkably consistent for that
person over time. Physiotherapists use that: a patient's walk before an injury
and after six weeks of rehabilitation is the measurement that says whether the
rehabilitation worked. Sports scientists use it to spot an asymmetry that will
become an injury. Neurologists use it because gait changes early in several
conditions.

The obstacle is that "does this walk look different?" is a judgement made by eye,
by someone experienced, from a video. It is subjective, hard to communicate, and
impossible to compare across months except by watching two clips one after the
other.

This tool turns two videos of someone walking into two **numerical gait
signatures** and reports where and by how much they differ — per joint, in
degrees.

It runs entirely in your browser. No video is uploaded.

## How it works, step by step

1. **Upload two clips** of walking, ideally from the side.
2. **Extract pose** from every frame — body landmarks, in the browser.
3. **Compute four joint angles per frame:** left and right knee, left and right
   ankle.
4. **Smooth** each angle series with a three-point moving average.
5. **Find the strides** by detecting peaks in the knee angle.
6. **Resample each stride to 50 points** so strides of different durations
   become comparable.
7. **Average the strides** into one representative curve per joint — the
   signature.
8. **Compare the two signatures** with root-mean-square difference per joint.

## The model or algorithm

### The gait cycle, and why it is the right unit

Walking is periodic. One **gait cycle** runs from one event on a leg to the next
occurrence of the same event — heel strike to heel strike. Everything about the
walk repeats inside that cycle, so a cycle is the natural unit: comparing raw
time series would mostly measure that one clip is longer than the other.

**Knee angle is the channel used to find cycle boundaries**, and the reason is
in the code's own comment: the knee reaches near-full extension once per stride,
so consecutive peaks bracket exactly one cycle. It is the cleanest periodic
signal a pose estimator produces from a walk.

### Peak detection by prominence, not by height

A naive peak detector finds every local maximum, and a jittery pose stream has
hundreds. Two filters make it robust:

**Prominence ≥ 8°.** A peak's prominence is how far it rises above the higher of
the two valleys either side of it. Height alone is the wrong test — a small
wobble on top of a high plateau is a tall local maximum and not a real peak.
Prominence asks "how far would you have to descend before you could climb to
somewhere higher", which is the question that separates a stride from a tremor.

**Minimum cycle 0.4 seconds.** Faster than any real walking stride, so it acts
purely as a guard against jitter double-counting one peak as two.

### Phase normalisation — the key idea

Two people walk at different speeds; the same person walks at different speeds on
different days. A stride lasting 1.1 seconds and one lasting 0.9 cannot be
compared sample by sample.

So each detected cycle is **resampled to a fixed 50 points**, converting the
x-axis from *time* to **percentage of the gait cycle**. 0 is the start of the
stride, 49 is the end, whatever the duration. This is the standard convention in
clinical gait analysis, and after it every stride is directly comparable to every
other.

Then the strides are **averaged across cycles**, which is the second important
step: one stride contains a person's walk plus that stride's noise. Averaging
several keeps what is consistent and cancels what is not — the same variance
argument as the multi-frame averaging in the Face Liveness chapter.

**At least 2 cycles are required.** With fewer, the tool refuses to produce a
signature and says why, rather than returning an average of one thing.

### Picking the reference leg

Cycle boundaries are taken from **whichever knee produced more detected cycles**.
The comment gives the practical reason: one leg's tracking is often cleaner than
the other depending on which side faces the camera. The far leg is partly
occluded by the near one for much of the stride, so its landmarks are noisier.
Choosing the better channel is a small thing that avoids a whole class of
failures.

### Comparison — RMS difference in degrees

For each joint, the two averaged curves are compared point by point:

```
RMS = √( mean over the 50 phase points of (a[i] − b[i])² )
```

**Root mean square rather than mean absolute difference** because squaring
penalises large deviations disproportionately — a curve that matches well for
most of the stride and diverges badly at toe-off is a meaningful difference, and
RMS surfaces it where a mean would dilute it.

The output is **in degrees**, which is the property that makes it usable: "the
left knee differs by 14° RMS through the stride" is a sentence a
physiotherapist can act on, unlike a similarity score between 0 and 1.

### The thresholds, and their honest status

```
similar                    < 10°
some differences      10 – 20°
substantially different  > 20°
```

The code's comment is unusually direct about these:

> *"Thresholds are a reasonable-looking heuristic against typical gait
> knee/ankle angle ranges (~0–70° through a stride), NOT calibrated against any
> labeled human gait dataset — disclosed in the UI."*

That is the right way to ship a threshold you have not validated: pick it from a
defensible reference — 10° against a 70° range is roughly 14% of the signal — and
say clearly that it is a heuristic, in the interface, not only in a comment.

### Cadence

Mean cycle duration converted to steps per minute — `60 / mean_cycle_duration`.
A simple, comparable number that captures walking speed independently of the
shape of the curves, and it is often the first thing that changes.

## Why these choices

**Why joint angles rather than landmark positions.** An angle is invariant to
where the person is in frame, how far from the camera they are, and how tall they
are. Raw landmark coordinates change with all three, so any comparison based on
them would measure the filming, not the walk. The angle at the knee is the same
number whether the person is close or far, left or right of frame.

**Why the browser.** Video of a person walking is personal, and medical or
rehabilitation footage more so. Client-side processing means it is never
transmitted — a stronger guarantee than a privacy policy, because it is a
property of where the code runs.

**Why only knees and ankles.** They carry the clearest periodic signal in a
side-view walk. Hips are informative and much noisier from a single camera; arms
vary with what someone is carrying.

**Why refuse below two cycles** rather than return something. A signature
averaged over one stride is that stride, noise included, presented as if it were
a stable pattern. Refusing with an explanation of what to film is more useful
than a confident wrong number.

## How to read the output

- **Read the per-joint numbers, not just the overall label.** An overall 12°
  that is 4° in three joints and 30° in the left knee is a specific finding; the
  average hides it.
- **A left-right asymmetry within one clip is often the interesting result** —
  compare the left knee curve against the right in the same video, not only
  across videos.
- **Filming consistency is the biggest confound.** Same camera position, same
  angle, same distance, ideally the same clothing. A change in filming produces a
  difference the tool cannot distinguish from a change in the walk.
- **Cadence changes alone** can explain curve differences: a faster walk has
  genuinely different joint kinematics.
- **A refusal is information.** "Not enough consistent strides" usually means
  the clip was too short, not side-on, or the walk was not continuous.
- **The thresholds are a heuristic.** Treat 9° and 11° as the same finding.

## Limits

- **The thresholds are uncalibrated.** Stated in the code and in the interface.
- **Single camera, single plane.** A side view captures flexion and extension.
  Rotation and side-to-side movement are largely invisible.
- **Pose estimation is the noise floor.** Loose clothing, poor light, and the
  far leg being occluded all degrade the landmarks before any analysis runs.
- **Four joints only.**
- **Two clips at a time.** No history, no trend across a rehabilitation
  programme.
- **Filming differences are indistinguishable from gait differences.**
- **Not a diagnostic tool.** It measures the difference between two videos. It
  has no model of pathology, no norms, and no population reference.
- **Needs continuous walking** — at least two or three clean strides.

## Likely interview questions

**"Why compare angles instead of landmark positions?"**
Because angles are invariant to the things that vary between two recordings —
distance from the camera, position in frame, the subject's height. Landmark
coordinates change with all of those, so a comparison built on them would mostly
measure the filming. The angle at the knee is the same number whether the person
is two metres away or five.

**"Two clips are different lengths and different walking speeds. How do you
compare them?"**
Phase normalisation. Detect the gait cycles, then resample each one to a fixed 50
points so the x-axis becomes percentage of the stride rather than time. After
that a 1.1-second stride and a 0.9-second stride are directly comparable point
by point. It is the standard convention in clinical gait analysis, and it is the
step that makes the whole comparison possible.

**"How do you detect a stride reliably from a noisy pose stream?"**
Peaks in the knee angle, filtered two ways. Prominence of at least 8°, because
height alone counts every wobble on a plateau as a peak while prominence asks how
far you would have to descend before climbing higher — which is the question that
separates a stride from jitter. And a minimum cycle of 0.4 seconds, faster than
any real stride, purely to stop one peak being counted twice.

**"Why RMS rather than mean absolute difference?"**
Because squaring penalises large deviations disproportionately. A pair of curves
that match well through most of the stride and diverge sharply at toe-off is a
real, clinically meaningful difference, and RMS surfaces it where a mean would
average it away. It also keeps the output in degrees, which is what makes the
number actionable.

**"Your thresholds aren't validated. Isn't that a problem?"**
It is a limitation, and the right response is to disclose it rather than hide it
— which the code and the interface both do. They are picked against a defensible
reference: knee and ankle angles span roughly 0–70° through a stride, so 10° is
about 14% of the signal. To validate them properly I would need a labelled gait
dataset with clinical ground truth, and without one I would rather ship a stated
heuristic than an implied certainty.

**"Why run it in the browser?"**
Because gait video is personal, and rehabilitation footage especially so. Nothing
is uploaded, which is a guarantee about where the code runs rather than a promise
about what a server does with the data. It also costs nothing to serve, and pose
estimation is fast enough client-side that there is no accuracy sacrifice to
justify sending it anywhere.
