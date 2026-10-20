Chapter 34Pose VJ Visuals


> Turn on your camera and drive a live generative particle visual with your hand movements. Hand landmarks are tracked in your browser by MediaPipe, so no video frame leaves your device. Switch the microphone on as well and particle size and density react to live volume — raw loudness, not beat or genre detection.

## At a glance

| | |
|---|---|
| **Also called** | Client-Side · No API Cost |
| **Model or method** | MediaPipe HandLandmarker (client-side WASM) |
| **What you give it** | Webcam + optional microphone |
| **Backend Calls** | 0 |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/pose-vj-visuals` |

## Using the tool

### What this tool does
Turn on your camera and **drive a live generative particle visual with your hand
movements**. Hand landmarks are tracked **in your browser** by MediaPipe, so **no video
frame leaves your device**. Switch the microphone on as well and particle **size and
density react to live volume** — raw loudness, not beat or genre detection.

### Purpose
It's a playful, privacy-first demo of real-time, on-device vision: your hand becomes the
controller for a visual, with nothing streamed to a server. A "VJ" (video-jockey) toy that
shows how capable in-browser ML has become.

### How to use it
1. Allow **camera** access; raise a hand into frame.
2. Move your hand — the particles follow your hand's position and gestures.
3. Optionally allow the **microphone** — louder sound makes particles bigger/denser.

### A worked example
Hold your hand up and sweep it across the frame — the particle cloud trails your palm.
Open and close your hand to change the effect. Turn on the mic and talk or play music:
the particles swell with volume and settle in quiet — a hand-and-sound-driven light show,
all computed locally.

### Reading the result
- The visual responds to **where your hand is** and its landmarks (MediaPipe
  HandLandmarker).
- With the mic on, **loudness** (not rhythm) maps to particle size/density.

### Notes & limits
- **Fully client-side** — hand tracking runs as WebAssembly in your browser; **no camera
  or mic data is uploaded** or stored.
- **Needs a camera** and decent light for reliable hand tracking.
- **Volume only** — it reacts to raw loudness, not beat, pitch or genre.

## What problem it solves

Nothing, in the sense the rest of this book means it. There is no dataset, no
score, no verdict, no file to download.

It is here for a different reason. Every other Computer Vision tool in this app
uses a model to *decide* something — is this real, how far away is that, what
object is this. This one uses a model as an **instrument**. Your hands move,
MediaPipe reports where they are sixty times a second, and coloured particles
stream off your fingertips and fade. Turn on the microphone and they swell with
the volume in the room.

It is the demonstration that computer vision does not only classify. And it is
the tool with the cleanest technical claim in the whole app: **zero backend
calls**. No video frame ever leaves your machine.

## How it works, step by step

1. **Turn the camera on.** The browser asks permission; the video element is
   local.
2. **The hand model loads.** MediaPipe's `HandLandmarker` fetches its WASM
   runtime and an ~8 MB model file from Google's CDN on first use — lazily, not
   bundled, so no one who never opens this page pays for the download.
3. **A frame loop starts.** On every `requestAnimationFrame`, the current video
   frame is passed to `detectForVideo`, which returns up to **two hands**, each
   as **21 landmarks** in normalised 0–1 coordinates.
4. **Particles spawn from six of those landmarks** — the wrist and the five
   fingertips. Each keeps its position from the previous frame, so the movement
   between frames gives a velocity.
5. **Particles live their own life.** They inherit some of your hand's velocity
   plus a random kick, drift, slow down, shrink and fade over roughly 40–80
   frames.
6. **Optionally, turn the microphone on.** A separate opt-in. Volume then drives
   how many particles spawn and how large they start.

## The model or algorithm

### MediaPipe HandLandmarker

Google's hand-tracking model, running as WASM plus WebGL in the browser. It
returns 21 points per hand — four joints per finger plus the wrist — in
normalised image coordinates, and it handles up to two hands here.

Landmark detection of this kind is normally a two-stage pipeline: a palm
detector finds hands in the frame, then a landmark model runs on each cropped
hand. In `VIDEO` running mode it also tracks between frames rather than
re-detecting from scratch every time, which is what makes it fast enough to run
at animation frame rate on a laptop.

The important property for this tool is that it is **small and local**. There is
no server round trip, which means no latency budget, no cost per frame, and —
the part that matters most for a webcam tool — **no privacy question to answer.**
The card's "0 backend calls" is a literal claim about the code.

### The particle system

The physics is deliberately simple, and each piece produces a visible effect.

**Velocity is inherited, not invented.** A landmark's velocity is its change in
position since the last frame, damped to 0.4. Particles spawn with half of that
plus a random component. So a slow hand produces a gentle drift and a fast swipe
throws a streak — the visual reads as a response to *you*, rather than as an
animation that happens to be near your hand.

**Spawn count reacts to both inputs:**

```
spawnCount = round((1 + speed × 0.3 + amplitude × 6) × density)
```

The baseline of 1 means a completely still hand still emits, so the visual never
dies while you are in frame. Speed adds a little; amplitude adds a lot — a
weighting of 6 against 0.3, which is what makes the sound the dominant driver
once the microphone is on.

**Drag, not gravity.** Each frame, `vx *= 0.96` and `vy *= 0.96`. Particles
decelerate smoothly to a stop instead of falling, which reads as smoke or light
rather than as physical debris.

**Everything fades together.** With `t = 1 − life/maxLife`, the same value drives
both alpha and radius, so a particle shrinks as it dims and never disappears
abruptly.

**The trail is the trick.** The canvas is never cleared. Instead each frame
paints a translucent dark rectangle over the whole thing:

```js
ctx.fillStyle = "rgba(8, 8, 14, 0.18)";
ctx.fillRect(0, 0, width, height);
```

Every previous frame therefore survives at 82% opacity, then 67%, then 55% —
motion leaves a decaying trail rather than a series of discrete blips. It is the
oldest trick in creative coding and the single line that makes the difference
between this looking alive and looking like scattered dots.

**Stale points are dropped.** Any tracked landmark not seen this frame is
deleted, so a hand leaving and re-entering the frame does not compute a velocity
against its position from ten seconds ago and fire a burst across the screen.
Small detail; without it the tool would misfire every time you took your hand
out of shot.

**The x-axis is mirrored** (`x = (1 − p.x) × width`) so the visual matches a
mirror, which is what a webcam view should do.

### The audio path

Web Audio's `AnalyserNode` with `fftSize = 256`, reading the **time-domain**
waveform rather than the frequency spectrum, and computing RMS:

```
amplitude = min(1, √(mean of ((sample − 128)/128)²) × 4)
```

RMS is the right measure for perceived loudness — it accounts for the whole
waveform rather than the peak, so a single click does not register the same as a
sustained note. The ×4 is a gain factor, because normal room audio through a
laptop microphone produces RMS values well under 0.25 and would otherwise never
reach the top of the range.

**It is loudness, and nothing more.** No beat detection, no onset detection, no
frequency analysis, no genre. The tool and its card both say so. The waveform
data is read but the spectrum is not — a beat detector would need the FFT
magnitudes, an energy history and a threshold above a running average, and none
of that is here.

## Why these choices

**Why the mic is a separate opt-in.** A microphone permission prompt is a bigger
ask than a camera one, and plenty of people will want the visual without it. Two
prompts, each for a thing you actually asked for.

**Why the render loop reads from a ref, not from props.** This is the one piece
of React reasoning worth stating. The animation loop is set up once and runs at
60 fps; hand landmarks and amplitude update at the same rate. Passing them as
dependencies would tear down and rebuild the loop sixty times a second. Instead
the latest values are written into a ref on every render and the loop reads that
ref — so it stays alive and always sees current data. Same pattern, and same
reason, as the pause flag in Pipeline Cinema.

**Why the model loads lazily from a CDN.** 8 MB in the bundle would slow the
whole site for every visitor, and almost none of them will open this page.

**Why hands rather than full-body pose.** Hands are expressive, they are what is
in frame when you are sitting at a laptop, and 21 landmarks per hand gives far
more control than the handful of upper-body points a pose model would resolve at
that distance. *That is my reading of the choice; the code records the model,
not the argument for it.*

**Why 2D canvas rather than WebGL.** At a few thousand particles the difference
does not show, and 2D canvas keeps the code short enough to read.

## How to read the output

There is no output to read, which is the point. But some things are worth
knowing:

- **A still hand still emits.** That is the baseline of 1 in the spawn formula,
  not a stuck loop.
- **Fast movement produces streaks**, because particles inherit your velocity.
- **With the mic on, the visual reacts to loudness only.** It will respond to
  music, clapping, a passing lorry and you talking, and it does not know which
  is which.
- **Two hands maximum.** A third in frame is not tracked.
- **Poor light degrades tracking**, and particles will stutter or stop — that is
  the model losing the hand, not the visual failing.
- **A load error means the CDN could not be reached.** The model is fetched at
  runtime, so this needs a connection the first time.

## Limits

- **Two hands, and hands only.** No body, no face, no objects.
- **Loudness, not music.** No beat, tempo, onset or frequency response.
- **Requires the model download** from Google's CDN on first use — the tool is
  client-side once loaded, not offline-capable from cold.
- **Tracking quality is the ceiling.** Bad light, motion blur, a hand partly out
  of frame, or a busy background all cost landmarks, and the visual follows.
- **No recording or export.** Nothing is saved; it exists while you watch it.
- **One visual style.** Hue and density are adjustable; the particle behaviour
  is not.
- **Fixed at 60 fps via `requestAnimationFrame`** — a slower machine drops
  frames and the motion coarsens.
- **The mic is read but barely used.** One number out of a whole spectrum.

## Likely interview questions

**"What is this for?"**
It is a demonstration that a vision model can be an instrument rather than a
classifier. It also proves a specific engineering claim that matters for the
rest of the app's camera tools: the model runs entirely in the browser, so no
video frame is ever transmitted. That is a much stronger privacy statement than
a policy, because it is a property of where the code runs.

**"Why run the model client-side? What did you give up?"**
Privacy, latency and cost — no frames transmitted, no round trip in a 60 fps
loop, no per-frame server bill. What you give up is model size and control: you
are limited to what will run in WASM in a tab, and to whatever Google ships at
that CDN, with no ability to fine-tune it. For real-time interaction that trade
is obviously right; for a heavy model like the depth estimator in the previous
chapter it is obviously wrong, which is why that one runs server-side.

**"How does the trail effect work?"**
The canvas is never cleared. Each frame paints a translucent dark rectangle over
the whole thing — about 18% opacity — so earlier frames survive, fading
geometrically. It costs one `fillRect` per frame and turns a scatter of dots
into motion with a history.

**"Why is the animation loop reading from a ref?"**
Because it runs at 60 fps and its inputs change at 60 fps. If the landmarks and
amplitude were effect dependencies, the loop would be cancelled and recreated
every frame, which is both wasteful and a source of dropped frames. Writing the
latest values into a ref on each render lets the loop stay alive and still read
current data. The general rule: state for what React should render, refs for
what an imperative loop needs to read.

**"You call it audio-reactive. Is it?"**
It reacts to volume, and I would be careful not to oversell it — the card says
so too. It computes RMS amplitude from the time-domain waveform and uses that to
drive particle count and size. It has no idea where the beat is. Real beat
detection needs the frequency spectrum, an energy history per band, and onset
detection against a running average — the `AnalyserNode` could give me the FFT
for it, and I simply did not build that.

**"Why do you delete tracked points for hands you can no longer see?"**
Because velocity is the difference between this frame's position and the last
one's. If a hand leaves the frame and comes back somewhere else, a stale
previous position produces an enormous fake velocity and fires a burst of
particles across the screen. Dropping unseen landmarks each frame means a
returning hand starts from zero velocity, which is correct.
