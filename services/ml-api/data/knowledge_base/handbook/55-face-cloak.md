Chapter 48Face Cloak


> Add a barely-visible perturbation to a photo so face-recognition models place it somewhere other than your real face. A simplified take on Fawkes, the privacy technique built to counter unauthorised facial-recognition scraping. You get the actual measured drop in embedding similarity, and an honest caveat: this protects the copy you cloak, not photos of you already scraped elsewhere.

## At a glance

| | |
|---|---|
| **Also called** | Local · No API Cost |
| **Model or method** | InceptionResnetV1 (local) |
| **What you give it** | Photo |
| **API Calls** | 0 |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/face-cloak` |

## Using the tool

### What this tool does
Upload a personal photo and this tool adds an **adversarial perturbation**
to the face region — invisible to your eye — specifically designed to push
that face's representation in a face-recognition model's "embedding space"
far away from where it naturally sits. If that cloaked photo is later
scraped and used to train or match against a facial-recognition system
(the kind companies like Clearview AI build from public photos without
consent), the system learns or matches a DISTORTED representation of your
face instead of the real one. This is the same real technique behind
**Fawkes** (Shan et al. 2020, University of Chicago) and the same idea
Glaze/Nightshade use to protect artists' work from AI style-mimicry.

### How to use it
1. Click **Choose photo** and upload a personal photo with a visible face.
2. Adjust **strength (epsilon)** — how large the perturbation is allowed
   to be. Higher values disrupt the face embedding more but are more
   likely to become visible as texture, especially at the high end.
3. Click **Cloak this photo** to see the original and cloaked photo side
   by side, plus how much the face's embedding actually moved.

### Reading the result
- **Cosine similarity**: how similar the cloaked face's embedding is to
  the original, on a -1 to 1 scale. 1.0 = identical (uncloaked). Real
  face-verification systems generally treat similarity above ~0.5-0.7 as
  "same person" and below ~0.3 as "different person" for this class of
  model — a common heuristic range, not a certified per-system threshold.
- **Protection level** (Strong / Moderate / Weak): a plain-language read
  on the cosine similarity number above, using those same heuristic
  cutoffs. "Strong" means the embedding moved into different-person
  territory; "Weak" means it barely moved at all — try a higher epsilon.
- Real testing on a real photo: epsilon=0.05 dropped cosine similarity
  from 1.0 (identical) to -0.58 (near-opposite direction) in under 2
  seconds — a large, measured disruption, not a marginal one.

### What this is (and isn't) — read this honestly
- This is a **simplified, untargeted** version of the real Fawkes
  technique. The actual paper pushes the face toward a REAL, chosen decoy
  identity's embedding (a stronger, more durable form of protection); this
  tool instead pushes the embedding AWAY from its own original position,
  since it doesn't ship a bundled dataset of decoy faces to target. Still
  a real, measured disruption — just not the paper's full method.
- This protects the SPECIFIC photo you cloak, going forward. It does
  nothing for copies of this photo that are already online or already
  scraped into an existing dataset.
- Published follow-up research on the real Fawkes technique found its
  protection can weaken against face-recognition models that get
  RETRAINED after a cloaking method becomes publicly known — this is an
  ongoing arms race between cloaking techniques and recognition systems,
  not a permanent, one-time fix.
- No real re-identification benchmark is run here (no bundled dataset of
  real same-person/different-person photo pairs) — the cosine-similarity
  drop is a real, directly measured signal, but not a guarantee against
  every possible face-recognition system that might exist.
- The embedding model used (InceptionResnetV1, trained on VGGFace2) is a
  generic, off-the-shelf, MIT-licensed model — not tied to any specific
  real-world recognition system, and not any model used elsewhere on this
  site.

### Notes & limits
- No API cost — face detection, the embedding model, and the cloaking
  optimization all run locally on the backend, no external calls.
- Only works on a photo with a face the detector can find; a very small,
  angled, or obscured face may not be detected at all.
- Only the face region (with a margin) is perturbed — the rest of the
  photo is left completely untouched.
- Nothing is stored: your photo and the cloaked result only exist for
  this one run.

## What problem it solves

Facial recognition at scale does not work by storing photographs. It works by
converting each face into a **vector** — a list of numbers positioned so that
two photographs of the same person land close together and two different people
land far apart. Identification is then a nearest-neighbour lookup in that space.

Companies like Clearview AI built their databases by scraping public photos
from the open web. Nobody consented, nobody was notified, and once a photo is
scraped the vector derived from it exists independently of the photo.

**Face cloaking** is the countermeasure, from Shan et al.'s Fawkes (SAND Lab,
University of Chicago, 2020). The insight is that the same adversarial
perturbation that fools an image classifier can be aimed at an embedding model
instead. Add a small, near-invisible change to the face region of a photo and
the vector it produces lands somewhere else entirely — so a recognition system
that scrapes the cloaked photo learns or matches the wrong point in the space.
The photo still looks like you. The vector does not.

This tool implements that. Upload a photo, and it returns a visually similar
version whose face embedding has been pushed far from where it started, with
the measured cosine similarity between the two so you can see how far.

It is the defensive counterpart to this book's Adversarial Robustness Lab —
the same mathematics, aimed at protecting someone rather than breaking a model.

## How it works, step by step

1. **Upload a photo.** Capped at 8 MB and scanned by the shared file gate.
2. **Locate the face** using the 601-class object detector already in this
   project, taking the highest-confidence `Human face` box.
3. **Expand the box by 1.6×** so the crop includes context, which is what the
   embedding model expects.
4. **Compute the original embedding** — one 512-dimensional L2-normalised
   vector — and freeze it as the reference.
5. **Run 40 gradient-ascent steps** that maximise the distance from that
   reference, ε-bounded per pixel and masked to the face region only.
6. **Measure cosine similarity** between the original and cloaked embeddings.
7. **Return the cloaked photo**, the similarity, and a protection level.

## The model or algorithm

### The embedding model, and why this one

**InceptionResnetV1** from `facenet-pytorch`, pretrained on VGGFace2. About
112 MB, producing a 512-dimensional L2-normalised embedding.

The licence was the deciding factor. After this project's earlier friction over
an AGPL-licensed detector, the MIT licence here was **confirmed by reading the
LICENSE file directly** rather than trusting a badge on a page. That habit is
worth keeping: licence metadata on model hubs is frequently wrong, and the
consequences land on whoever ships the code.

Face detection reuses the existing OIV7 detector rather than adding a dedicated
face model — the same pattern the liveness tool uses. One fewer model to
download, one fewer dependency to license.

### The attack loop

Structurally this is PGD, the iterative attack from the Adversarial Robustness
Lab, with three modifications.

```
orig_embed = embed(x)                      # computed once, held fixed
α = ε / 8

repeat 40 times:
    d    = ‖ embed(x_adv) − orig_embed ‖²   # squared L2 distance
    g    = ∇ₓ d                             # gradient w.r.t. the pixels
    x_adv ← x_adv + α · sign(g)             # ASCEND — increase the distance
    x_adv ← clip(x_adv, x − ε, x + ε)       # stay inside the ε-ball
    x_adv ← clamp(x_adv, 0, 1)              # stay a valid image
    x_adv ← x·(1−mask) + x_adv·mask         # face region only
```

**The objective is embedding distance, not classification loss.** There is no
label and no classifier — the loss is simply how far the current vector has
moved from where it started, and the gradient says which pixels move it fastest.

**The reference is frozen before the loop.** If the target were recomputed each
step the optimisation would chase its own tail; fixing it once means every step
pushes away from the true starting point.

**The mask is reapplied at the end of every step.** The projection and clamp
operate on the whole tensor, so without the final line the perturbation would
leak outside the face box. Reapplying the mask each iteration — rather than
once at the end — keeps the gradient in subsequent steps honest about what it
is actually allowed to change.

Step size is ε/8 with 40 steps, so the loop has five times the budget it needs
to reach the ball's edge in any direction. That headroom is what lets it find a
good point inside the ball rather than just a corner.

### Measuring the result

Cosine similarity between the original and cloaked embeddings, which for
L2-normalised vectors is just their dot product, ranging from +1 (identical
direction) through 0 (orthogonal) to −1 (opposite).

| Similarity | Label |
|---|---|
| below 0.3 | **strong** |
| 0.3 – 0.5 | **moderate** |
| above 0.5 | **weak** |

Those cut-offs come from the published face-verification convention that above
roughly 0.5–0.7 reads as "same person" and below roughly 0.3 reads as
"different person" for this class of model. They are a **common heuristic
range, not a certified per-model threshold**, and the response says so.

**Measured on a real photo:** 40 steps at ε = 0.05 took about one second and
dropped cosine similarity from 1.0 to **−0.58**. Not merely far away —
pointing in nearly the opposite direction.

## Why these choices

**Why repulsion instead of targeting a decoy?** This is the honest simplification
against the real paper, and it is disclosed rather than glossed.

Fawkes is **targeted**: it pushes the embedding toward a specific real decoy
identity, creating a feature-space collision with someone who actually exists.
The authors' own follow-up work found that gives stronger and more durable
protection than pure repulsion, because it lands the vector in a region the
model considers plausible — a legitimate part of face space, occupied by a real
person — rather than in some empty region that a retrained model might learn to
recognise as "cloaked".

Doing that requires a bundled dataset of real identities to select a decoy
from. This tool ships no such dataset, so it uses the simpler repulsion
variant: still effective, measurably so, but weaker than the published method.

**Why 1.6× crop expansion?** Face embedding models are trained on crops that
include forehead, chin and some background. A pixel-tight box is out of
distribution and produces a worse embedding — which would make the cloaking
look more effective than it is, since you would be measuring the distance from
a bad starting point.

**Why perturb only the face?** Two reasons. It is where the signal is, so the
budget is spent efficiently. And it keeps the rest of the photo pixel-identical,
so the visible change is confined to the region where a small perturbation is
least noticeable against skin texture.

**Why does the box need pixel coordinates rather than an actual crop?** Because
the gradient has to flow back to the original full-resolution tensor. The crop
is taken by slicing a differentiable tensor and resizing with bilinear
interpolation, so `autograd` can trace the whole path from the 512-dimensional
embedding back to the individual pixels of the source image. Cropping to a new
image object would sever that path.

**Why load the model lazily?** Most sessions never open this tool, and 112 MB
of weights should not be downloaded on the chance that someone might.

## How to read the output

**Cosine similarity is the number that matters.** It answers: how far did the
face embedding move? Near 1.0 means the cloak failed. Near 0 means the vector
is orthogonal to where it started. Negative means it points the other way.

**Compare the two images.** At ε = 0.05 the change is usually visible as faint
texture on close inspection and invisible at normal viewing size. If you can
see it clearly, ε is too high for the purpose.

**A "strong" label means strong against this model, today.** It is a measured
disruption of one specific embedding model, not a guarantee against any system
you have not tested.

The Face Deanonymization Demo elsewhere in this book completes the
demonstration: it runs an actual similarity search, cloaks the target, and
re-runs the same search. Measured live, the same-person similarity fell from
0.99 to −0.77 and the verdict flipped from "same" to "different" — the
countermeasure defeating the identification it had just performed.

## Limits

Four of these are in the module's own docstring, because they are the honest
frame for the whole tool.

- **It protects this photo going forward, and nothing else.** Copies already
  scraped and trained on are unaffected. If your face is already in a database,
  cloaking a new photo does not remove it.
- **It is an arms race, not a fix.** Published follow-up research on Fawkes
  found protection degrades against recognition models retrained *after* the
  cloaking method becomes public. Defenders publish, attackers adapt.
- **No re-identification benchmark is run.** There is no bundled dataset of the
  same and different people, so no true false-match or false-non-match rate is
  measured. The similarity drop is real and measured; it is not a certified
  guarantee.
- **It is measured against one embedding model.** Transfer to a different
  architecture is plausible but untested here, and the transfer results in the
  Adversarial Robustness Lab suggest it is far from automatic.
- **Repulsion, not targeting** — weaker than the published technique.
- **One face per photo.** The highest-confidence detection is cloaked; others
  are left alone.
- **Re-encoding may weaken it.** Any platform that recompresses uploads is
  performing something close to the JPEG defence from the Adversarial
  Robustness Lab, which partially destroys perturbations.
- **The thresholds are heuristic**, not calibrated for this model.

## Likely interview questions

**"How is cloaking different from blurring a face?"**
Blurring destroys the image for humans as well as machines — you can no longer
share the photo as a photo. Cloaking leaves it looking normal to people and
changes only the vector a recognition model computes. The trade is that
blurring is unconditional and cloaking is model-dependent and reversible in
principle by an adaptive attacker.

**"Walk me through the optimisation."**
Compute the face embedding once and freeze it. Then iteratively compute the
squared L2 distance between the current perturbed embedding and that frozen
reference, take the gradient with respect to the input pixels, and step in the
direction of its sign to *increase* the distance. After each step, project back
into the ε-ball around the original, clamp to valid pixel values, and reapply
the face mask. It is PGD with an embedding-distance objective instead of a
classification loss, and ascending instead of descending.

**"Why cosine similarity rather than Euclidean distance?"**
The embeddings are L2-normalised, so they all lie on the unit sphere and only
direction carries information — Euclidean distance and cosine similarity are
then monotonically related and measure the same thing. Cosine is the convention
in the face-verification literature, which means the published same/different
thresholds are directly usable rather than needing conversion.

**"Your similarity went negative. What does that mean?"**
The cloaked embedding points in roughly the opposite direction from the
original on the unit sphere. For a verification system that thresholds
similarity, that is comprehensively past "different person" — but it is worth
being clear that negative similarity is not inherently better than zero. What
matters is being on the wrong side of the decision threshold; the extra
distance is spare margin, not proportionally more protection.

**"Is this legal, and is it ethical?"**
It is a defensive privacy tool applied to your own photographs, in the same
category as a VPN or ad blocker. The technique was developed by academic
researchers explicitly to counter non-consensual scraping, and published. The
uncomfortable symmetry is that the same mathematics powers the attack demo
elsewhere in this book — an adversarial perturbation is neutral, and what
distinguishes the two tools is whose model is being disrupted and whether the
person in the photo agreed to be in the database.

**"Why is targeted cloaking stronger than repulsion?"**
Because of where each one lands the vector. Repulsion pushes to somewhere far
away, which may be an empty region of face space that a retrained model can
learn to identify as "this is a cloaked photo" — the perturbation becomes its
own signature. Targeting lands the vector on a real identity's position, a
legitimately occupied region that cannot be flagged as anomalous without also
flagging that real person. The cost is needing a dataset of real identities to
draw the decoy from, which is why this tool does not do it.

**"If it degrades once the method is public, is it worth deploying?"**
It is worth deploying with correct expectations. It raises the cost and
imposes a retraining burden on the scraper, which has value, and it protects
against systems that exist now. What it must not be sold as is permanent
protection, because that would encourage people to share photos they would
otherwise withhold — which is the failure mode where a privacy tool makes
things worse than doing nothing.
