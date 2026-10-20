Chapter 61Style Cloak


> Add a barely-visible perturbation across an image so its CLIP embedding drifts away from where a model would naturally place it — a simplified take on the Glaze and Nightshade approach to countering AI style-mimicry. You get the actual measured similarity drop, calibrated against an unrelated-image baseline, plus the honest caveat: it protects the copy you cloak, not images already scraped elsewhere.

## At a glance

| | |
|---|---|
| **Also called** | Local · No API Cost |
| **Model or method** | CLIP ViT-B/32 (local) |
| **What you give it** | Image |
| **API Calls** | 0 |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/style-cloak` |

## Using the tool

### What this tool does
Upload an image — artwork, a photo, anything you've made — and this tool
adds an **adversarial perturbation** across the whole image, invisible
to your eye, specifically designed to push that image's representation
in a CLIP vision model's "embedding space" far away from where it
naturally sits. If that cloaked image is later scraped and used to
train or fine-tune an AI style-mimicry model, the model learns a
DISTORTED representation of it instead of the real one. This is the
same real idea behind **Glaze** and **Nightshade** (Shan et al. 2023,
University of Chicago) — built to protect artists' work from
unauthorized AI style-mimicry — and the same technique Face Cloak
applies to face-recognition embeddings instead of style embeddings.

### How to use it
1. Click **Choose image** and upload the image you want to protect.
2. Adjust **strength (epsilon)** — how large the perturbation is allowed
   to be. Higher values disrupt the embedding more but are more likely
   to become visible as texture, especially at the high end.
3. Click **Cloak this image** to see the original and cloaked image side
   by side, plus how much the embedding actually moved.

### Reading the result
- **Cosine similarity**: how similar the cloaked image's embedding is to
  the original, on a -1 to 1 scale. 1.0 = identical (uncloaked). Real
  testing found two totally UNRELATED images typically measure around
  0.65-0.77 in CLIP embedding space (much higher than you might expect —
  CLIP embeddings share generic visual structure even for unrelated
  content), so that range is the honest baseline for "reads as a
  different image" here, not 0.0.
- **Protection level** (Strong / Moderate / Weak): a plain-language read
  on the cosine similarity number, calibrated against that real
  unrelated-image baseline above — not copied from Face Cloak's
  thresholds, since CLIP's embedding space behaves differently from a
  face-recognition model's. "Strong" means the embedding dropped below
  where two unrelated images typically sit; "Weak" means it barely
  moved — try a higher epsilon.
- Real testing on a real image: epsilon=0.06 dropped cosine similarity
  from 1.0 (identical) to -0.36 in about 1-2 seconds — well below the
  unrelated-image baseline, a large, measured disruption.

### What this is (and isn't) — read this honestly
- This is a **simplified, untargeted** version of the real
  Glaze/Nightshade technique. The actual papers push an image toward a
  DIFFERENT, chosen style's feature-space region (Glaze) or specifically
  poison a concept-to-rendering association (Nightshade) — both stronger
  and more durable than pure repulsion. This tool instead pushes the
  embedding AWAY from its own original position, since it doesn't ship a
  bundled style-target dataset to aim at. Still a real, measured
  disruption — just not the papers' full method.
- This protects the SPECIFIC image you cloak, going forward. It does
  nothing for copies of this image that are already online or already
  scraped into an existing training dataset.
- The real Glaze/Nightshade research is an ongoing arms race — style-
  mimicry models can be retrained to be more robust against known
  cloaking methods, so this isn't a permanent, one-time fix.
- No real style-mimicry pipeline is run here (no actual fine-tuning or
  style-transfer training to test against) — the cosine-similarity drop
  is a real, directly measured signal against the CLIP encoder used
  here, but not a guarantee against every possible style-mimicry system,
  which may use a different encoder entirely.
- The embedding model used (CLIP ViT-B/32, OpenAI) is a generic,
  off-the-shelf, MIT-licensed model, not tied to any specific real-world
  mimicry system.

### Notes & limits
- No API cost — the CLIP model and the cloaking optimization both run
  locally on the backend, no external calls.
- The whole image is perturbed, unlike Face Cloak's face-only crop —
  style is a property of the entire image, so there's no sub-region to
  isolate.
- Nothing is stored: your image and the cloaked result only exist for
  this one run.

## What problem it solves

An illustrator with a recognisable style posts their portfolio online. Someone
scrapes it, fine-tunes an image model on a few dozen pieces, and can now
generate unlimited work in that style on demand. The artist's name becomes a
prompt keyword. Nothing was copied in the sense copyright law understands —
what was taken is the *style*, which copyright does not protect.

**Style cloaking** is the countermeasure, from the Glaze and Nightshade work by
Shan et al. (SAND Lab, University of Chicago, 2023). Style-mimicry pipelines do
not learn from pixels directly; they learn from an image encoder's
representation of the image. If you perturb the picture so that its
*embedding* moves somewhere else while the picture still looks the same to a
person, a model trained on the cloaked version learns a distorted account of
the style.

This is the artist-facing sibling of Face Cloak in this book. Both take the
adversarial perturbation from the Adversarial Robustness Lab and aim it at
protecting somebody rather than breaking a classifier. The difference is which
embedding space is targeted: face identity there, visual style here.

Upload an image, get back a version that looks the same and embeds somewhere
else, with the measured similarity between the two.

## How it works, step by step

1. **Upload an image.** No face detection, no region selection — the whole
   image is the subject.
2. **Compute its CLIP image embedding** — 512 dimensions, L2-normalised — and
   freeze it as the reference.
3. **Run 40 gradient-ascent steps** that *minimise* cosine similarity to that
   reference, ε-bounded per pixel across the entire image.
4. **Measure cosine similarity** between the original and cloaked embeddings.
5. **Return the cloaked image**, the similarity, and a protection level
   calibrated against a real baseline.

## The model or algorithm

### Why CLIP

**`openai/clip-vit-base-patch32`** via `transformers`, MIT licensed, about
600 MB, producing a 512-dimensional L2-normalised embedding.

Two reasons. Style-transfer and fine-tuning pipelines commonly use CLIP or a
CLIP-adjacent encoder to represent an image's visual character — it is the
closest thing to a standard for "what does this picture look like" as opposed
to "what objects are in it". And this project already depends on
`transformers` with a CLIP model elsewhere, so nothing new enters the
dependency tree.

### The attack loop

Structurally identical to Face Cloak's, with two differences that matter.

```
orig_embed = embed(x)                      # computed once, held fixed
α = ε / 8

repeat 40 times:
    s = cos_sim( embed(x_adv), orig_embed )
    g = ∇ₓ s
    x_adv ← x_adv − α · sign(g)             # DESCEND — reduce similarity
    x_adv ← clip(x_adv, x − ε, x + ε)
    x_adv ← clamp(x_adv, 0, 1)
```

**No mask.** Face Cloak confines its perturbation to the expanded face crop,
because a face photograph has one small region the target model cares about.
An artwork has no such region — style is a property of brushwork, palette,
composition and edge quality distributed across the whole picture. There is no
sub-region to isolate, so the perturbation covers everything.

**The objective is cosine similarity directly, minimised**, rather than
squared L2 distance maximised. On the unit sphere these are equivalent up to a
monotone transform, so the choice is presentational: the quantity being
optimised is the same one reported in the result, which makes the loop's
progress directly interpretable.

Everything else carries over — a frozen reference computed once, a step size of
ε/8 with 40 steps to give the optimiser headroom inside the ball, the ε-ball
projection, and the clamp to a valid image.

### The thresholds, and why they are not Face Cloak's

This is the part of the tool most worth understanding, and it came from
measurement rather than from copying.

Before choosing thresholds, the CLIP cosine similarity was measured **between
two completely unrelated images** — different shapes, different colours,
different composition. The result: **0.65 to 0.77**.

That is startlingly high next to face-embedding space, where two different
people land around 0.3 to 0.5. The reason is what each space is trained to do.
A face embedding is trained specifically to separate identities, so unrelated
inputs are pushed apart aggressively. CLIP is trained to align images with text
descriptions across an enormous, general distribution — so all natural images
share a large amount of generic visual and scene structure, and even unrelated
ones sit fairly close together. **A high CLIP similarity between two images
does not mean they look alike.**

Copying Face Cloak's thresholds would therefore have been badly wrong: a
cloaked image sitting at 0.6 would have been labelled "weakly protected", when
0.6 is already *below* the floor for two random unrelated images.

Calibrated against the measured baseline instead:

| Similarity | Label |
|---|---|
| below 0.5 | **strong** |
| 0.5 – 0.75 | **moderate** |
| above 0.75 | **weak** |

The "weak" boundary sits at the top of the unrelated-image range: above 0.75,
the cloaked image is still more similar to its original than two random images
are to each other, so essentially nothing has been achieved.

**Measured on a real cloaking run:** ε = 0.06, 40 steps, one to two seconds,
and cosine similarity dropped from 1.0 to **−0.36**. Well below the
unrelated-image baseline — the cloaked image now reads to CLIP as *more*
different from its own original than two random unrelated pictures typically
are from each other.

The general lesson is worth stating outside this tool: **an embedding
similarity number is meaningless without knowing that space's baseline.** The
only way to know it is to measure the similarity of things you know to be
unrelated, in that space, with that model.

## Why these choices

**Why repulsion instead of targeting a decoy style?** The same honest
simplification as Face Cloak, disclosed rather than glossed. Glaze is
**targeted** — it pushes toward a different, chosen art style's region of
feature space, so a model trained on the cloaked work learns a coherent but
wrong style. Nightshade goes further, poisoning the association between a
concept and its rendering, so the damage propagates beyond the individual
image. Both are more sophisticated and more durable than plain repulsion, and
both need a bundled dataset of style targets to draw from. This tool ships no
such dataset, so it uses the simpler variant: measurably effective, weaker than
the published technique.

**Why a higher default ε than Face Cloak?** 0.06 here against 0.05 there, with
a ceiling of 0.12 against 0.1. Two reasons pull the same way. The perturbation
must survive whatever the image goes through before it is scraped, and it is
spread across the whole picture rather than concentrated on a face — so more
budget is needed for equivalent effect. And artwork hides perturbation better
than skin does: texture, brushwork and varied colour give the noise somewhere
to sit, whereas a smooth cheek shows it immediately.

**Why L2-normalise the embedding after the model?** So that cosine similarity
is the dot product and the reported number is directly comparable to the
measured unrelated-image baseline. Comparing an unnormalised similarity to a
normalised baseline would be a category error.

**Why lazy-load?** 600 MB of weights, and most sessions never open this tool.

## How to read the output

**Read the number against the baseline, not against 1.0.** Two unrelated images
sit at 0.65–0.77 in this space. That is the reference point. A cloaked image at
0.6 has moved past "as different as a random other picture"; at 0.85 it has
barely moved at all despite the drop from 1.0 looking substantial.

**Compare the images side by side at full size.** The perturbation is spread
over the whole picture, so it is more visible in smooth areas — a flat sky, a
plain background — than in detailed ones. If it is obtrusive, lower ε and
accept a weaker cloak.

**"Strong" means strong against CLIP.** A style-mimicry pipeline built on a
different encoder is not what was measured, and nothing here demonstrates
transfer.

## Limits

The first three are in the module's own docstring, because they frame the tool
honestly.

- **It protects this image going forward, and nothing else.** Copies already
  scraped and trained on are untouched.
- **It is an ongoing arms race.** The Glaze research is explicitly framed that
  way — mimicry models can be trained to be robust against cloaking methods
  once those methods are public. This is not a permanent fix.
- **No style-mimicry benchmark is run.** There is no fine-tuning or
  style-transfer pipeline here to test against. The similarity drop is a real,
  measured signal **against the CLIP encoder itself**, not a guarantee against a
  system that may use a different encoder entirely.
- **Repulsion, not targeting** — weaker than Glaze, and it does nothing of what
  Nightshade does.
- **Whole-image perturbation is more visible** than a face-only one, especially
  in flat regions.
- **Re-encoding may weaken it.** Any platform that recompresses uploads is
  doing something like the JPEG defence from the Adversarial Robustness Lab.
- **Resizing may weaken it too.** The embedding is computed at CLIP's input
  resolution, so a perturbation optimised at the source resolution is resampled
  by any pipeline that scales the image differently.
- **One encoder, one measurement.** No transfer to other CLIP variants or to
  non-CLIP encoders has been tested.

## Likely interview questions

**"Why does style cloaking need a different threshold from face cloaking, when
both use cosine similarity on normalised embeddings?"**
Because the spaces have completely different baselines. A face encoder is
trained specifically to separate identities, so two different people land
around 0.3–0.5. CLIP is trained to align images with text over a general
distribution, so all natural images share substantial generic structure and two
unrelated pictures measure 0.65–0.77. Reusing the face thresholds would call a
well-cloaked image "weak" when it was already further away than a random
unrelated image. The measurement of the unrelated baseline had to come first.

**"How do you know 0.65–0.77 is the right baseline?"**
It was measured, not assumed — CLIP embeddings of images deliberately chosen to
share nothing in shape, colour or composition. That is the general procedure I
would use for any embedding space before quoting a threshold in it: establish
what "unrelated" scores, in that space, with that model, and only then decide
what a meaningful separation is.

**"Why perturb the whole image here but only the face crop in the other tool?"**
Because of where the target model's signal lives. Face recognition reads one
localised region, so confining the perturbation there spends the budget where
it counts and leaves the rest of the photo untouched. Style is distributed —
brushwork, palette, edge quality, composition — with no sub-region that carries
it. There is nothing to mask to.

**"Why is Glaze's targeted approach better than repulsion?"**
Repulsion pushes the embedding somewhere far away, which may be an implausible
region of the space that a retrained model can learn to recognise as
"cloaked" — the perturbation becomes its own detectable signature. Targeting
lands it in a region occupied by a real, different art style, which is
plausible and cannot be flagged as anomalous without also flagging genuine
work in that style. Nightshade goes further again by poisoning concept-to-image
associations, so the effect is not confined to the cloaked image.

**"Does this actually stop anyone training on the artwork?"**
Not by itself, and it would be wrong to claim so. What is measured is that the
CLIP embedding moves a long way — a real result against that encoder. Whether a
particular fine-tuning pipeline is degraded depends on its encoder, its
preprocessing, how many cloaked versus uncloaked images it has, and whether it
was trained to resist known cloaking. None of that is tested here, and saying
otherwise would encourage artists to post work they would otherwise hold back —
which is the failure mode where a protection tool leaves people worse off.

**"What would make this a real defence?"**
Targeted rather than repulsive cloaking against a decoy style; validation
against an actual fine-tuning run to show measured style degradation rather
than an embedding-distance proxy; robustness testing against recompression,
resizing and denoising, since those are what a scraper's pipeline does anyway;
and transfer testing across several encoders, because an attacker will not use
the one you optimised against. Beyond the technical, the durable answers are
non-technical — licence terms, robots and opt-out signals with actual
enforcement, and legal frameworks that recognise style-mimicry as a harm.
