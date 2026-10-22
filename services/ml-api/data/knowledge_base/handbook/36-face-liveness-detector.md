Chapter 29Face Liveness Detector


> Show your face to the camera, or upload a photo, and see whether it reads as a genuinely present face or a spoof — a printed photo or a screen replay. The same category of check that gates face-unlock and identity verification. The model runs on this project's own server rather than any third-party AI provider — your photo is sent there for the check, processed in memory and not stored.

## At a glance

| | |
|---|---|
| **Also called** | Real vs. Spoofed |
| **Model or method** | MiniFASNetV2-SE (ONNX) |
| **What you give it** | Webcam or photo |
| **Model Size** | 600KB |
| **Where it runs** | On the server |
| **Find it at** | `/tools/face-liveness` |

## Using the tool

### What this tool does
Show your face to the camera, or upload a photo, and see whether it reads as a
**genuinely present face** or a **spoof** — a printed photo or a screen replay. This
is the same category of check that gates face-unlock and identity verification. The
model runs on this project's own server (not a third-party AI provider); your image is
sent there for the check, processed in memory, and **not stored**.

### Purpose
"Is there a real, live person in front of the camera?" is the first question any
biometric system must answer, because a face match alone can be fooled by a photo of
the person. This tool demonstrates that liveness check — and is honest about how hard
it is in a browser under uncontrolled lighting.

### How to use it
1. Allow **camera** access and position your face in frame, or **upload a photo**.
2. Capture — the tool checks the image and, for the webcam, averages several frames
   for a steadier read.
3. Read the verdict: **Real**, **Spoof**, or **Uncertain**.

### A worked example
Point the webcam at your own face in good, even light → it reads **Real**. Now hold up
a photo of a face on your phone screen to the camera → it should read **Spoof** (screen
replay). In poor or uneven lighting, a genuine face can come back **Uncertain** — that
is the tool refusing to guess, not a failure.

### Reading the result
- **Real** — the signals are consistent with a live, present face.
- **Spoof** — patterns consistent with a printed photo or a screen (moiré, flatness,
  reflections).
- **Uncertain** — not enough confidence either way; try better, even lighting and a
  face that fills the frame.

### Notes & limits
- **Lighting-sensitive by design.** Anti-spoofing is genuinely finicky under bad
  lighting; the honest **Uncertain** state exists so the tool doesn't over-claim.
- **Small, fast model.** It runs a compact on-server model (MiniFASNetV2-SE, ONNX,
  ~600KB) — a demonstration, not a production identity gate.
- **Privacy.** Your image is sent to this project's server only for the check,
  processed in memory, and not retained.

## What problem it solves

Face recognition answers *"who is this?"*. It does not answer *"is there
actually a person here?"* — and a recogniser will happily identify a printed
photograph of you, or your face played back on a phone screen, as you.

That gap is called a **presentation attack**, and closing it is what liveness
detection does. It is the check sitting behind face-unlock on a phone and behind
the selfie step in identity verification: before asking whose face this is, ask
whether it is a face being presented live or a picture of one.

This tool runs that check. Show your face to the camera or upload a photo, and
it reports whether the image reads as a live face or a spoof.

## How it works, step by step

1. **Capture.** The browser takes **four frames, 250 ms apart** — roughly a
   second of video — or you upload a single photo.
2. **Find the face.** Each frame goes to the server, which runs the object
   detector already used elsewhere in the app and keeps the highest-confidence
   `Human face` box. If there is no face, it stops and says so rather than
   guessing.
3. **Crop, generously.** The box is expanded by **1.5×** around its centre and
   made square, with reflection padding where the expansion runs off the edge of
   the image.
4. **Letterbox to 128×128.** Resize preserving aspect ratio — Lanczos when
   scaling up, area averaging when scaling down — then pad to a square, again by
   reflection. Scale to [0, 1] and transpose to channels-first.
5. **Classify.** One ONNX forward pass returns two numbers, a *real* logit and a
   *spoof* logit.
6. **Score.** `sigmoid(real − spoof)` gives one number from 0 to 1. **No verdict
   is decided here.**
7. **Average, then decide.** The browser averages the four frames' scores and
   only then commits: above 0.65 *"Looks live"*, below 0.35 *"Looks spoofed"*,
   and in between **"Uncertain"**.

## The model or algorithm

### The classifier

**MiniFASNetV2-SE** — 600 KB, quantised ONNX, 128×128 RGB in, a binary
real/spoof classifier out. It comes from `minivision-ai/Silent-Face-Anti-
Spoofing` (Apache-2.0, 2020) by way of the community ONNX port
`facenox/face-antispoof-onnx` (Apache-2.0, 2025).

"Silent" is the key word. There are two families of liveness detection:

- **Active** — the system tells you to blink, turn your head, follow a dot.
  Reliable, and it makes every login a small performance.
- **Passive, or "silent"** — a single still image is enough, with no
  cooperation asked for. Much better to use, and much harder to do.

This is the passive kind. With one still frame there is no motion to analyse, so
the model has to work from what a re-presentation does to the *texture* of an
image: the moiré pattern of a screen's pixel grid, the flatness of a print, the
specular reflection off glass or paper, the loss of fine skin detail through one
extra capture cycle. Those artefacts are what a small CNN can learn — and it is
why the model needs so little resolution to work at all.

**The licence was checked, not assumed.** The docstring records that the LICENSE
file in both repositories was read directly before adopting the model, because
the weights and the code can be licensed differently — as the project learned
elsewhere, where permissively-licensed detector code shipped weights carrying a
separate AGPL claim. Here the weights ship under the same Apache-2.0 as the code
in both repos.

### Why the crop is expanded and reflection-padded

Both are copied deliberately from the ONNX port's own preprocessing, and both
matter more than they look.

The **1.5× expansion** exists because a tight face box throws away exactly the
evidence the model was trained on. The give-away of a spoof is often just
outside the face — the edge of a phone held in a hand, the border of a sheet of
paper, the background out of focus in a way a real scene would not be. A tight
crop cuts the frame out of the picture of the frame.

**Reflection padding** rather than black or grey fill is the standard choice for
a texture model. A hard black border is itself a strong, artificial edge, and a
CNN looking for texture artefacts will happily key on it. Mirroring the
neighbouring pixels produces a continuation with the same statistics as the
image, so the padding contributes nothing the model can mistake for signal.

The important general principle: **preprocessing must match what the model was
trained on, exactly.** A different crop ratio or a different padding mode is not
a minor deviation — it shifts the input distribution and quietly degrades a model
that still looks like it is working.

### Why the server returns a score and not a verdict

This is the design decision that carries the tool, and it came from a real
observation recorded in the code: **a live webcam face scored "spoofed" at 52%
under dim, low-contrast lighting** — a near coin flip, on the correct answer's
wrong side.

The model's confidence collapses toward 0.5 under exactly the conditions a
laptop webcam produces. So the endpoint deliberately does not return
`{real: false, confidence: 0.52}`. It returns the raw signed score, and lets the
caller decide with more information than one frame provides.

The client then does two things with it:

- **Averages four frames.** Independent noise partly cancels; a single frame
  that lands on the wrong side of 0.5 gets outvoted by three that do not. It is
  the same variance argument as the Ensemble chapter, applied to one model over
  time instead of several models at once.
- **Refuses to decide in the middle.** With `UNCERTAIN_MARGIN = 0.15`, anything
  between 0.35 and 0.65 is reported as **Uncertain**. Not a failure state — the
  honest answer when the evidence is a coin flip.

`real_score` is `None` when no face was confidently detected. The tool never
guesses on an image with nothing to check.

### Reusing the detector

Locating the face reuses `detect_objects` — the same OIV7 detector that powers
"Detect faces" elsewhere in the app, filtered to the `Human face` class. No
second face-detection model was added: one download, one warm session, one thing
to keep licensed and updated.

## Why these choices

**Why four frames at 250 ms.** One second is short enough not to feel like a
wait and long enough for the webcam's auto-exposure to settle and for the
subject to move slightly. Four averages away a good deal of frame noise; more
would make the tool feel slow for diminishing returns.

**Why an uncertain band at all.** Because a binary verdict from a model whose
score is 0.52 is a lie told confidently. In a security context, "I don't know" is
a usable answer — it routes to a second factor. A wrong "real" does not.

**Why 600 KB.** It runs on CPU, on free hosting, with no GPU and no cold-start
download worth mentioning. A large model would be more accurate on paper and
unusable here.

**Why the image is sent to the server rather than checked in the browser.** The
detector and the ONNX runtime live server-side. The tool discloses this plainly
on the card: the photo is sent to this project's own server, not a third-party
AI provider, processed in memory and not stored.

## How to read the output

- **The percentage is "real-leaning", averaged over four frames.** It is not a
  probability that you are a real person; it is where the model's signed score
  landed.
- **"Uncertain" is the expected answer in bad light.** Move to a window, or use
  a brighter room, and try again. It is not a failure of the check.
- **A verdict on an uploaded photo is weaker than one from the camera**, because
  the four frames are then four copies of the same image and averaging cancels
  nothing.
- **A printed photo and a screen replay are different attacks** and this model
  is much more comfortable with one than the other. A phone-screen replay
  behaves very differently to these models than a flat print.
- **No face found means no verdict**, not "spoof".

## Limits

The module's own docstring is unusually direct about this, and it should be
repeated rather than softened.

- **Cross-dataset generalisation in this field is genuinely poor.** The academic
  literature is consistent: a naive CNN trained on one spoof dataset and tested
  on another scores close to a coin flip — around 45–48% error. Even
  sophisticated cross-domain methods only reach roughly 20–30% error, still far
  worse than same-dataset performance.
- **The quoted 98.2% accuracy and 0.9984 AUC are CelebA-Spoof numbers** — the
  dataset the model was trained and tested on. They have not been independently
  verified here beyond confirming the pipeline works end to end and that a real
  face crop scores clearly real with a strong logit margin. **Do not quote them
  as this tool's accuracy.**
- **It has never been tested against this codebase's own camera, lighting and
  spoof conditions.** Expect it to work in controlled conditions and be
  genuinely unreliable at the edges.
- **Low light collapses the score toward 0.5** — the observed failure, and the
  reason the uncertain band exists.
- **Only the largest face is checked.** One face per image.
- **Four frames over one second is not motion analysis.** A video replay that is
  static for a second is not distinguished by temporal reasoning; each frame is
  judged alone.
- **No defence against a 3D mask, a deepfake video feed, or an injected camera
  stream.** This detects re-presentation artefacts, not synthesis.
- **This is a demonstration, not a security control.** For anything that
  matters, passive liveness is one signal among several — device attestation,
  active challenges, document checks.

## Likely interview questions

**"What is a presentation attack and why doesn't face recognition stop it?"**
Holding up a photo, a phone screen, or a mask in front of the camera. Recognition
answers "whose face is this?" — and a photo of me is still, correctly, my face.
Liveness answers the prior question, "is a real face being presented?", and it
has to be a separate check because the recogniser is doing its job correctly
when it is fooled.

**"Passive or active liveness — which would you build?"**
Both, layered. Passive is far better to use, because nothing is asked of the
person, and it is the harder problem — a single still frame gives you texture
artefacts and nothing else. Active is much more robust but adds friction to
every login. In practice: passive first, and escalate to an active challenge
when the passive score lands in the uncertain band, which is exactly what the
uncertain band in this tool would route to.

**"Your model reports 98% accuracy. Would you deploy it on that?"**
No, and this is the part I would raise unprompted. That number is on CelebA-
Spoof, the dataset it was trained on. Liveness detection is notorious for poor
cross-dataset generalisation — a model trained on one attack dataset and tested
on another can score close to chance, and even good cross-domain methods land
around 20–30% error. Before deploying I would need numbers on *my* cameras, *my*
lighting and *my* attack types, and I would expect them to be much worse.

**"Why does your API return a score instead of a verdict?"**
Because during testing a genuinely live face scored 52% "spoof" in poor light —
the model's confidence collapses toward 0.5 under exactly the conditions a
webcam produces. A single frame near 0.5 is not enough to commit to. Returning
the raw signed score lets the client average several frames and apply its own
threshold, and it lets the interface say "uncertain" rather than pick a side of
a coin flip. Deciding at the wrong layer would have thrown that information away.

**"Why expand the crop by 1.5× instead of using the face box?"**
Two reasons. The model was trained on crops shaped that way, so anything else
shifts the input distribution. And the evidence of a spoof is often outside the
face — the edge of a phone, the border of a sheet of paper, the way the
background is lit. A tight crop removes the picture of the picture, which is the
most reliable tell there is.
