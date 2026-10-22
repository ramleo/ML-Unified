Chapter 25ASL Fingerspelling Recognition


> Hold up one hand fingerspelling an ASL letter and it is recognised live from your webcam. MediaPipe hand landmarks feed a k-NN classifier, entirely client-side. This covers individual letters only, not signed words or ASL grammar — those need sequence models over video and are a genuinely different problem. J and Z are excluded because both require motion a single frame cannot capture, following the same convention as the Sign Language MNIST benchmark.

## At a glance

| | |
|---|---|
| **Also called** | Client-Side · No API Cost |
| **Model or method** | MediaPipe HandLandmarker + k-NN (local) |
| **What you give it** | Live Webcam |
| **API Calls** | 0 |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/asl-fingerspelling-recognition` |

## Using the tool

### What this tool does
Hold up one hand fingerspelling a letter of the American Sign Language
alphabet, and this recognizes it live from your webcam — MediaPipe hand
landmarks feed a k-nearest-neighbor classifier trained on real photos,
entirely in your browser.

### Purpose
This was originally brainstormed as a general "sign language translator."
Real ASL translation is a fundamentally different, much harder problem —
ASL is its own language with its own grammar and word order, recognized
from whole-word or sentence video sequences (the real research datasets
for this, WLASL and 2M-Flores-ASL, are built around exactly that). A
single-frame hand-pose classifier can't honestly do that. This tool is
rescoped to the real, well-defined sub-problem it can actually do:
recognizing individual finger-spelled letters — how ASL signers spell out
names, places, or words that don't have a dedicated sign.

### How to use it
1. Click **Start camera** and allow camera access.
2. Hold up one hand, facing the camera, forming one of the 24
   supported letters (see the reference chart below the camera view).
3. Hold the shape steady for a moment — a letter only appears once the
   same prediction holds for several consecutive frames, to avoid
   flickering between guesses.

### A worked example — real, measured accuracy, not assumed
Trained and evaluated on real photos from a public dataset, not
synthetic data: extracted MediaPipe hand landmarks from a real
photo dataset, held out ~15% of the successfully-detected photos as a
genuine test set never included in the shipped classifier, and measured
**79% accuracy** (248/314 held-out photos) across 24 letter classes
(random chance would be about 4%). Rotation-normalizing the hand's
orientation was tried and found to make accuracy WORSE (67.8% vs. 75.5%
at the time), so it was dropped — a real result, not a guess, and a good
example of why every technique choice here was tested, not assumed.

### Reading the result
- **A letter appears** once the same prediction has held steady for
  several consecutive frames.
- **"Hold the shape steady…"** means a hand is detected but the
  prediction hasn't stabilized yet.
- **"Show one hand to the camera"** means no hand is currently detected.

### Notes & limits
- **Fingerspelling only, not sign-language translation.** This
  recognizes individual letters, never whole signed words, phrases, or
  ASL grammar.
- **J and Z are excluded.** Both require a traced motion in real ASL
  (a hooked path for J, a traced Z shape) that a single static frame
  cannot capture — datasets built for static-letter recognition (e.g.
  Sign Language MNIST) exclude them for the same reason.
- **Known mix-ups, from the real confusion data measured during
  evaluation**: U/V/R (similar raised-finger configurations), M/S/N/A
  (similar closed-fist variants), K/X/P. These are genuine, disclosed
  limitations of the underlying hand shapes being visually close, not
  bugs to "fix."
- **Trained on plain-background studio photos.** Live webcam accuracy in
  a cluttered or dim environment has not been verified end-to-end in
  this environment (this project's test browser doesn't deliver real
  webcam frame data) — an open follow-up, not something claimed as
  tested. Landmark-based classification (not raw-pixel) is inherently
  more robust to background changes than a pixel-based model would be,
  but this hasn't been confirmed on a real camera yet.
- **Runs entirely in your browser.** No video frame is ever sent to a
  server.

## What problem it solves

American Sign Language has a manual alphabet — a hand shape per letter — used for
spelling names, technical terms and anything without an established sign.
Recognising those shapes from a camera is the entry point to sign-language
interfaces, and it is a genuinely hard vision problem: the hand is small,
self-occluding, and moves.

This tool recognises fingerspelled letters from your webcam, in your browser,
with no server call and no neural network of its own.

It is also the tool in this book with the most honest headline number attached
to it, and that is the most interesting thing about it.

## How it works, step by step

1. **Track the hand** with MediaPipe, which returns 21 landmarks in 3D.
2. **Normalise them** — translate to the wrist, scale by hand size.
3. **Compare against 1,845 stored prototype vectors**, each labelled with a
   letter.
4. **Take the single nearest one** and report its letter with the distance.

That is the whole classifier. No training at runtime, no model file beyond the
hand tracker, no server.

## The model or algorithm

### Normalisation — and the one that was deliberately not applied

The raw landmarks depend on where the hand is in frame and how far from the
camera. Two things fix that:

**Translate to the wrist.** Every landmark becomes relative to landmark 0, so
position in the frame stops mattering.

**Scale by hand size.** Divide by the wrist-to-middle-finger-knuckle distance —
landmark 0 to landmark 9. That is a rigid part of the hand, so it is a stable
ruler regardless of which letter is being formed. A hand near the camera and the
same hand across the room now produce the same vector.

The result is 21 points × 3 coordinates = a 63-dimensional vector.

**Rotation was tested and rejected.** This is the finding worth remembering:

> Rotation-normalising **hurt** held-out accuracy — **75.5% down to 67.8%**.

The reason, recorded in the code, is that **hand orientation itself carries real
signal for some letters** rather than being noise to remove. In ASL, some letters
differ largely by orientation; normalise it away and you have deleted the feature
that separates them.

The general lesson is a good one: invariance is not free. Every invariance you
build in throws away information, and it is only an improvement if the
information was noise. That has to be *measured*, not assumed — and the obvious
normalisation was the wrong call here.

### k-nearest neighbour, with k = 1

The classifier stores 1,845 example vectors and classifies by finding the closest
one in Euclidean distance. No training, no weights, no loss function — the data
*is* the model.

**k = 1 was chosen by testing**, not by default:

| k | Held-out accuracy |
|---|---|
| **1** | **75.5%** |
| 3 | 70.7% |
| 5, 7, 9, 15 | declining further |

That is the opposite of the usual expectation — larger k normally smooths noise
and helps. The code explains why it does not here: with little data per class and
many visually close letters, a vote across more neighbours pulls in examples from
confusable classes. If the two nearest neighbours of an `M` are an `M` and an
`N`, k=3 can outvote the correct answer. A single closest match generalises
better when the classes are crowded together.

### The measured accuracy

```
248 / 314 = 79.0%   on genuine unseen photos
24 classes, chance = 4.2%
```

Several things about that number are worth pointing at.

**It is measured on a held-out set**, on photographs never included in the
shipped prototypes. That is the only kind of accuracy figure worth quoting, and
it is the difference between this and a model card.

**Chance is quoted alongside it.** 79% against a 4.2% baseline is the honest
framing; 79% on its own could mean anything.

**24 classes, not 26.** J and Z are excluded because they involve *motion* — they
are not static hand shapes at all, so a single-frame classifier cannot represent
them.

**It is not 100%, and the tool says so.** Fingerspelling recognition from a
single frame with a nearest-neighbour classifier over ~77 examples per class is
exactly a 79% problem. The number is in the code as a constant, exported, and
disclosed in the interface.

### Why this is a reasonable approach and not a shortcut

k-NN over normalised landmarks looks primitive next to a trained network, and for
this problem it is well matched:

- **The hard part is already done.** MediaPipe's hand tracker is the heavy model,
  and it has already turned pixels into a clean, low-dimensional geometric
  description. Classifying 63 numbers is a much easier problem than classifying
  an image.
- **No training infrastructure.** Adding a letter means adding examples.
- **Fully interpretable.** A misclassification is a specific nearest neighbour
  you can look at.
- **It runs in a browser**, instantly, with the prototypes shipped as JSON.

## Why these choices

**Why landmarks rather than pixels.** A CNN on hand images has to learn to ignore
skin tone, sleeve colour, lighting and background before it can start on shape.
Landmarks are already invariant to all of that. Using a strong upstream model to
produce a clean representation, then a simple classifier on top, is a good
general pattern — and it is why the whole thing fits in a browser.

**Why the browser.** Webcam video of a person, and a tool whose users may rely on
sign language, is exactly the case where "nothing is uploaded" is worth more than
a privacy policy.

**Why prototypes in JSON rather than a trained model.** The whole classifier is
data, so it version-controls as data, and the accuracy number can be recomputed
by re-running the held-out set against it.

## How to read the output

- **79% means roughly one letter in five is wrong.** Expect to correct it.
- **The distance is the confidence.** A large distance to the nearest prototype
  means nothing in the set looked like your hand — a hold that is not quite any
  letter, or a tracking failure.
- **Confusions are systematic, not random.** Visually close letters — the closed-
  fist family especially — swap for each other. Knowing which cluster a letter
  is in tells you what its likely error is.
- **J and Z are absent** because they are movements, not shapes.
- **Hold the shape still and let the tracking settle.** Motion blur degrades the
  landmarks before the classifier sees them.
- **Match the prototypes' viewpoint.** They were collected from a particular
  camera angle, and a very different one is out of distribution.

## Limits

- **79% on held-out data.** Stated, measured, and not rounded up.
- **24 letters.** No J, no Z, no numbers, no words.
- **Static shapes only.** Real fingerspelling flows between letters; this reads
  one frame at a time with no transition model.
- **No sequence modelling and no language model.** A spelling correction pass
  over the letter stream would fix a lot of the 21%, and there is none.
- **k-NN scales linearly.** 1,845 comparisons per frame is fine; ten times that
  would not be.
- **The prototype set is small** — around 77 examples per class — and reflects the
  hands, lighting and camera angle it was collected from.
- **One hand.**
- **Tracking quality is the floor.** Bad light or a partly out-of-frame hand
  produces bad landmarks and the classifier faithfully classifies them.

## Likely interview questions

**"Why k-NN and not a neural network?"**
Because the hard part is already solved upstream. MediaPipe has turned the image
into 21 clean 3D landmarks, so the remaining problem is classifying a
63-dimensional geometric vector, not an image — and for that, with a small
dataset, nearest-neighbour is competitive and needs no training infrastructure.
It also runs in a browser instantly and every mistake is inspectable: you can
look at the specific prototype that won. A network would likely beat 79%, and it
would need training, a model file and a much less transparent failure mode.

**"You normalised for position and scale but not rotation. Why?"**
Because I tested it and it made things worse — held-out accuracy dropped from
75.5% to 67.8%. Hand orientation carries real signal for some ASL letters rather
than being noise, so normalising it away deletes the feature that separates them.
The general point is that every invariance throws information away, and whether
that is an improvement depends on whether the information was noise. It has to be
measured.

**"Why is k=1 better than k=3?"**
It is the opposite of the usual expectation, and it is a consequence of the data.
With few examples per class and many visually close letters, a vote across more
neighbours pulls in examples from confusable classes — if the two nearest
neighbours of an M are an M and an N, k=3 can outvote the right answer. Measured:
75.5% at k=1, 70.7% at k=3, declining further above that.

**"Your accuracy is 79%. Is that good?"**
Against a 4.2% chance baseline on 24 classes, it is real signal — and I would
quote both numbers together, because 79% alone is meaningless without the
baseline. It is not production quality for a communication tool, and the interface
says so. The biggest available improvement is not a better classifier: it is
sequence modelling and a language model over the letter stream, since most errors
are systematic confusions between visually close letters that a dictionary would
resolve.

**"How would you get it to 95%?"**
More data first — the prototype set is around 77 examples per class from one
camera angle and one set of hands, so broadening that is the highest-value move.
Then temporal smoothing, since a letter held for half a second gives fifteen
frames to vote across rather than one. Then a language model over the output,
which fixes exactly the confusable-cluster errors that dominate the remaining
21%. A bigger classifier is further down that list than people expect.
