Chapter 63Video-Call Keystroke Inference


> Upload a short clip of someone typing and recover when the keys were pressed from hand motion alone. Frame-by-frame hand tracking feeds a tap detector on fingertip movement, producing a timeline of keystrokes, which hand, and likely word boundaries from the gaps — the same side channel behind published research on video keystroke inference. It stops at timing and does not attempt to recover what was typed: that needs per-target trained models this doesn't have. Runs in your browser; no video leaves your device.

## At a glance

| | |
|---|---|
| **Also called** | Client-Side Only |
| **Model or method** | MediaPipe HandLandmarker (local) |
| **What you give it** | Video |
| **API Calls** | 0 |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/video-keystroke-inference` |

## Using the tool

### What this tool does
Upload a short video (60 seconds max) of hands typing — your own recorded
webcam clip or video-call footage. The tool tracks fingertip motion
frame-by-frame using MediaPipe hand tracking, and detects real
keystroke-shaped press-release events purely from that motion's timing.
This is the same hand-tracking signal that published side-channel attacks
(USENIX Security '23, video-based keystroke inference) key off. Runs
entirely in your browser — **no video is ever uploaded anywhere**.

### Purpose
Video calls routinely show a participant's hands, and it's a real,
published finding that hand motion during typing leaks timing information
even when no audio or keylogger is involved. This tool demonstrates that
side channel honestly and at the scope that's actually reproducible without
per-target training data: **when** keys were pressed, not **which**
characters were typed. The full published attack adds a trained
language-model decoding stage (needing per-target training data) to go from
timing to actual text — that stage is deliberately not included here, and
is disclosed prominently rather than silently implied.

### How to use it
1. Click **Choose video** and upload a clip (up to 60 seconds) showing
   hands typing, ideally with both hands clearly visible over a keyboard.
2. Click **Analyze** — the tool steps through the video frame-by-frame
   (not real-time playback) for precise, jitter-free timestamps, tracking
   each hand's fingertips.
3. Review the detected keystroke-event timeline, estimated typing speed,
   and likely word boundaries.

### A worked example
A real downloaded stock video of two hands typing on a laptop, verified
live during development, produced **26 keystroke events** correctly
alternating between hands, a plausible **~34 WPM** estimate, and **4 word
segments** inferred from timing gaps between bursts of taps — with no
audio and no keylogger involved, purely from watching hand motion.

### Reading the result
- **Timeline** — each dot is one detected press-release event, colored by
  which hand (blue = left, amber = right); vertical lines mark where a
  longer pause plausibly indicates a space between words.
- **Keystroke events detected** — the total count of press-release motions
  found.
- **WPM** — a timing-based typing-speed estimate (not validated against
  ground-truth text, since no text is recovered).
- **Word segments** — clusters of taps separated by pauses long enough to
  plausibly be word boundaries.
- **Rhythm consistency** — how uniform the inter-keystroke timing is.

If no motion matching a press-release pattern is found, the tool says so
rather than fabricating events — try a clip with hands more clearly visible
over the keyboard.

### Notes & limits
- **Does NOT recover which characters were typed** — only WHEN keys were
  pressed. No text, words, or characters are ever shown, by design.
- Real character-level attacks require a trained language-model decoding
  stage with per-target training data this demo doesn't have — extending
  to that is a deliberate non-goal, not a missing feature.
- Best results need both hands clearly visible and reasonably well-lit;
  occluded or fast-panning footage will under-detect events.
- 60-second clip cap, entirely client-side (MediaPipe WASM) — nothing is
  sent to any server.

## What problem it solves

On a video call, people watch the other person's face. They rarely think about
what else is in frame — and on a laptop, what is in frame is very often the
hands.

In 2023 a USENIX Security paper by Yang et al. demonstrated that this is a real
side channel: from webcam video of someone typing, an attacker can recover what
they typed. Not by reading the keyboard, which is usually not visible at all,
but by watching the **hands** and inferring which keys the finger motion is
consistent with. The published pipeline reports over 90% per-key accuracy.

That is a genuinely uncomfortable result. It means a screen-shared meeting, a
recorded call, or a video posted publicly can leak a password typed while the
camera was on.

This tool builds the **first stage** of that attack and stops there, on purpose.
Upload a video of someone typing, and it recovers a real keystroke timeline —
when each press happened, which hand made it, where the word boundaries fall,
and how fast the typing was. It does not recover characters, and the interface
says so prominently.

## How it works, step by step

1. **Upload a video** of hands typing. Everything runs in the browser; no
   backend, nothing uploaded anywhere.
2. **Step through the video frame by frame** at 20 samples per second, seeking
   to each timestamp rather than playing.
3. **Track both hands** with MediaPipe's HandLandmarker, recording the position
   of all five fingertips per hand.
4. **Detect taps** in each fingertip's vertical motion.
5. **Merge near-simultaneous detections** across fingers into single
   keystrokes.
6. **Segment into words** from the gaps between keystrokes.
7. **Report the timeline** with WPM and a rhythm-consistency figure.

## The model or algorithm

### Tracking

MediaPipe's HandLandmarker gives 21 landmarks per hand with a left/right
handedness label, configured for two hands. Only the five fingertip landmarks
— thumb, index, middle, ring, pinky — are kept, producing up to ten independent
time series of `(t, x, y)` with coordinates normalised to the frame.

Sampling is at 20 Hz. That is chosen against the physics rather than the
video's frame rate: a key press-and-release cycle takes roughly 100–150 ms, so
20 samples per second puts two to three samples inside each press. Fewer would
miss presses entirely; many more would multiply the cost without resolving
anything new.

The video is **seeked** to each timestamp and awaited, not played. Playback
would tie analysis speed to real time and would drop frames under load. Seeking
is slower per frame but deterministic, and determinism matters for a
measurement.

### Detecting a tap

This is the real work, and it was written and verified before any video code
existed.

A keypress is a **downward finger motion followed by a return**. In normalised
image coordinates the origin is top-left, so *down* is *increasing y*. A press
therefore appears as a **local maximum in y, bracketed by lower values on both
sides.**

The bracketing is the whole point. A hand drifting toward the camera, or
settling into position, produces monotonically increasing y with no return — no
bracketing valley, correctly ignored. Only the press-and-release shape counts,
which is the same signal the published attacks key off.

Four mechanisms make that robust:

**A 3-sample moving average** first. Enough to knock down per-frame landmark
jitter, short enough not to smear out a genuine single-frame press dip.

**A local-maximum radius of 2 samples** on each side, rather than comparing
against the immediate neighbours only. A real peak sampled at 20 Hz can be flat
across two or three samples.

**A valley walk** for amplitude. This replaced the original implementation and
is the bug worth recording. The first version measured amplitude by comparing
the peak against its single immediate neighbours — which returns **zero** for
any peak whose top is flat across more than one sample, because the neighbour
has the same value. Flat-topped peaks are common at this sampling rate, so real
presses were silently scoring zero amplitude and being discarded.

The fix walks outward from the peak in each direction while y is
non-increasing, and returns the lowest value reached before the signal turns
back upward — the true flanking valley:

```
amplitude = min( peak.y − leftValley,  peak.y − rightValley )
```

Taking the `min` of the two sides means a press is only counted if it is
bracketed on *both* sides. A single downward step at the end of a series does
not qualify.

Amplitude below 0.012 in normalised units is treated as tracking noise, not a
press.

**A refractory period** of 80 ms per finger. No finger presses two keys 80 ms
apart, so anything closer is the same event detected twice — which also cleanly
resolves ties across a flat peak top.

### From taps to keystrokes

Ten fingers are tracked independently, but a hand presses one key at a time.
When several fingers dip together — as they do, because pressing with the index
finger moves the whole hand — that is one physical event. Detections within
60 ms of each other are collapsed, keeping the earliest of the cluster.

### Word segmentation

No character identity is involved. The only signal is timing.

```
median_gap = median of all inter-keystroke intervals
boundary   = any gap > 2.2 × median_gap
```

Using the typist's **own median** rather than a fixed threshold is what makes
this work across different people and speeds — a fast typist's word boundary
may be shorter than a slow typist's ordinary keystroke interval. The 2.2
multiplier is a judgement, not a fitted value.

### The two summary numbers

**Words per minute** uses the standard typing convention that five keystrokes
constitute one word, regardless of actual word lengths.

**Rhythm consistency** is `1 − (stddev / mean)` of the intervals, clamped to
[0,1] — the complement of the coefficient of variation. 1 means a metronomic
rhythm, 0 means erratic. It is a shape descriptor of the timeline, not a
biometric claim; the Keystroke Biometric Auth-Risk tool elsewhere in this book
is where timing is actually used for identification, and it needs per-key dwell
and flight from real key events rather than inferred taps.

## Why these choices

**Why stop at the timeline instead of recovering characters?** Because the
character-recovery stage of the published attack is not reproducible here, and
faking it would be worse than omitting it.

Yang et al.'s pipeline needs a self-supervised CNN trained on the target's own
setup, plus an HMM with a language model to resolve the many-keys-per-finger
ambiguity. Both stages require per-target training data — video of *that*
person at *that* camera angle on *that* keyboard. Without it there is no
mapping from finger position to key, and any character output would be
fabrication dressed as inference.

The scope was confirmed explicitly before building rather than discovered
partway through, and the interface states the boundary rather than implying a
capability the tool does not have.

**Why frame-by-frame rather than real time?** Determinism, and honesty about
the threat model. A real attacker works from a recording, offline, with as much
compute as they like. Real-time processing would be a harder engineering
problem that makes the attack look *less* practical than it is.

**Why fully client-side?** The input is video of someone typing, quite possibly
a password. Uploading that to a server to demonstrate a privacy risk would be
absurd. It also means the tool works with no backend and no API cost.

**Why track all five fingertips rather than just the index?** Because touch
typists use all of them, and it is not known in advance which finger presses a
given key. Tracking all ten and merging afterwards is more robust than guessing
— and the merge step is what makes the redundancy harmless.

### Verified on real video

Tested on a downloaded stock video of two hands typing on a laptop: **26
keystroke events**, correctly alternating between hands, **about 34 WPM**, and
**4 word segments**. Plausible on every axis, with a clean MediaPipe teardown
and no console errors.

The signal-processing layer was verified separately and first, against
synthetic data with injected taps at known timestamps — which is how the
flat-peak amplitude bug was found, before any video was involved.

## How to read the output

**The timeline is the result.** Each entry is a detected press with its
timestamp and which hand made it. Alternating hands across a sequence is a
strong sign the detection is tracking real typing rather than noise.

**Word segments are approximate.** A long pause to think looks identical to a
space. Someone typing a long word without pause produces one segment covering
several words.

**WPM is derived from the keystroke count**, so it inherits every miss and
every false positive. Treat it as an estimate of typing rate, not a measurement.

**What is absent is the point.** There is no text output. If you wanted to know
*what* was typed, the honest answer is that this stage cannot tell you, and the
stage that could needs training data specific to the person you are watching.

## Limits

- **No character recovery.** By design, and the reason is a missing trained
  model, not a missing feature.
- **Both hands must be visible.** A hand off-frame contributes nothing, and its
  keystrokes are simply absent.
- **Camera angle matters enormously.** The detector reads vertical motion in
  image coordinates, so a near-side-on view flattens the press signal into
  almost nothing.
- **Fast typing exceeds the sampling rate.** Above roughly 10 keystrokes per
  second, presses fall inside the 80 ms refractory window and merge.
- **The thresholds are judgement calls** — 0.012 amplitude, 60 ms merge, 80 ms
  refractory, 2.2× median for boundaries — tuned on synthetic data and one real
  video, not fitted on a labelled corpus.
- **No accuracy figure.** Measuring one needs video with a ground-truth
  keystroke log recorded alongside, which this project does not have.
- **Modifier keys, held keys, backspaces and mouse movement** are all
  indistinguishable from ordinary presses or missed entirely.

## Likely interview questions

**"How can you detect a keypress from video without seeing the keyboard?"**
You are not detecting the key, you are detecting the finger. A press is a
characteristic vertical motion — down, then back up — which in image
coordinates is a local maximum in y bracketed by lower values on both sides.
That shape distinguishes a real press from a hand drifting or settling, which
has no return. The keyboard never needs to be visible; the hand is the sensor.

**"You had a bug in the peak detection. What was it?"**
Amplitude was measured against the peak's immediate neighbours. At 20 Hz a real
press often produces a flat top spanning two or three samples, so the immediate
neighbour has the same value and the computed amplitude is zero — real presses
were being thrown away as noise. The fix walks outward from the peak while the
signal is non-increasing and takes the lowest value before it turns back up,
which finds the true flanking valley regardless of how wide the plateau is. It
was caught on synthetic data with known injected taps, before any video code
existed.

**"Why take the minimum of the two valley depths rather than the average?"**
Because it enforces the bracketing requirement. Averaging lets a deep valley on
one side compensate for no valley at all on the other, which is exactly the
monotonic-drift case the detector needs to reject. Taking the minimum means the
press must be bracketed on both sides to count.

**"Why segment words by the typist's own median gap rather than a fixed
threshold?"**
Because typing speeds differ by a large factor between people. A fixed
threshold of, say, 300 ms would treat every gap as a word boundary for a slow
typist and none for a fast one. Normalising against the person's own median
makes the rule scale-free, and the same trick shows up in other tools in this
book — it is the general fix whenever a threshold has to work across subjects
with very different baselines.

**"What would it take to actually recover the text?"**
A model mapping fingertip position to key, which is where the difficulty lives:
each finger covers several keys, so position alone is ambiguous. The published
attack resolves it with a self-supervised CNN trained on the target's own
setup, then an HMM with a language model over the sequence to pick the most
probable text consistent with the ambiguous per-key distributions. The language
model does a lot of the work — it turns a noisy per-key guess into readable
text. All of it needs per-target training data, which is why this tool stops at
the timeline.

**"What is the practical defence?"**
Keep hands out of frame — a higher camera angle, or an external keyboard placed
below the visible area. Do not type passwords while a camera is live, and use a
password manager so you rarely need to. On the platform side, a
hands-detected-in-frame warning during screen sharing is entirely feasible, and
so is blurring the lower portion of the frame by default. The attack needs a
clear view of a press-and-release from a favourable angle, and every one of
those is removable.

**"Was building this responsible?"**
The full attack is published and peer-reviewed; the capability exists whether or
not this exists. What is here is the stage that demonstrates the risk without
supplying a capability — a keystroke timeline is not somebody's password. The
character-recovery stage was deliberately not built, and the reason is stated in
the interface rather than left as an implied "coming soon".
