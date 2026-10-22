Chapter 39Wildlife Re-Identification


> Upload a new sighting and a gallery of past ones and see which individual animal it most likely matches. The animal is cropped out of each photo, then compared using MegaDescriptor, a foundation model built specifically for individual animal re-identification rather than a general-purpose vision embedding. Treat it as a ranking aid, not an identification system — the same/uncertain/different bands are not calibrated against a benchmark. MegaDescriptor is CC-BY-NC-4.0, so non-commercial use only.

## At a glance

| | |
|---|---|
| **Also called** | MegaDescriptor |
| **Model or method** | MegaDescriptor-T-224 |
| **What you give it** | Target + Gallery Photos |
| **API Calls** | 0 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/wildlife-reidentification` |

## Using the tool

### What this tool does
Upload a new sighting photo and a small gallery of past sighting photos
of the same species, and this crops the animal out of each photo, embeds
each crop with a foundation model built specifically for individual
animal re-identification, and ranks the gallery by similarity to the new
sighting — the kind of "is this the same individual returning" question a
backyard camera trap raises.

### Purpose
Originally scoped around a generic vision embedding (DINOv3), but
researched before building anything: **MegaDescriptor**
(BVRA/MegaDescriptor-T-224, from the open-source WildlifeDatasets
toolkit) is the first foundation model built specifically for individual
animal re-identification, and is published to outperform generic
embeddings like CLIP and DINOv2 on this exact task. Using the
purpose-built model instead of a plausible-sounding generic one is the
point — the same discipline as this project's other tools that pick the
real, right technique over a substitute.

### How to use it
1. Upload a **new sighting photo** of an animal.
2. Upload 1-10 **past sighting photos** of the same species — the
   candidates you want to compare the new sighting against.
3. Click **Compare sightings**. The animal is detected and cropped
   automatically in every photo before comparison.
4. Review the ranked results — each past sighting gets a similarity score
   and a qualitative same/uncertain/different label.

### A worked example
Verified with two real photos before this was considered working, since
no genuine backyard-camera-trap dataset was available in this
environment (disclosed here rather than glossed over): comparing the
same photo of two goldfish swimming together, cropped into two separate
individual fish, scored **0.60 similarity, correctly labeled
"different"** — the two fish are visibly similar (same species,
side-by-side) but the model still told them apart. Comparing one fish
crop to itself scored **1.00, correctly labeled "same."**

### Reading the result
- **Each gallery card** — the detected animal label, a cosine similarity
  percentage, and a same/uncertain/different label.
- **Best match** — the single highest-similarity past sighting, called
  out separately.
- **"No animal detected"** means the object detector couldn't find an
  animal in that photo clearly enough (very low resolution or an unusual
  crop can cause this) — not that nothing is there.

### Notes & limits
- **Not a validated identification system.** The same/uncertain/different
  thresholds are informed by one real test (above), not a calibrated
  threshold from a proper multi-individual validation set — none exists
  in this environment. Treat results as "does this look like the same
  individual," never proof.
- **No pose-normalization or multi-crop averaging.** Real wildlife re-ID
  research pipelines use these techniques to improve reliability; this
  tool runs a single crop through a single forward pass per photo.
- **License**: MegaDescriptor is CC-BY-NC-4.0 (non-commercial) — a fit
  for this educational, non-commercial portfolio.
- **Detection quality gates everything.** If the underlying object
  detector can't find the animal in a photo (too small, too low-res, an
  unusual angle), no comparison is possible for that photo.

## What problem it solves

A camera trap fires four hundred times over a month. Standard species
classification tells you: fox, fox, badger, fox, fox. Useful, and it does not
answer the question ecologists actually ask.

**Is that the same fox?**

That distinction is everything downstream. Population estimates depend on
counting *individuals*, not sightings. Territory and range depend on recognising
the same animal at two locations. Survival rates depend on knowing whether an
animal seen in March is the one seen in September. A hundred sightings of one
fox and a hundred sightings of a hundred foxes produce identical species counts
and completely different ecology.

The traditional answer is physical tagging — collars, ear tags, microchips —
which means capturing the animal. This tool asks whether a photograph is enough.

## How it works, step by step

1. **Upload two photographs** of an animal.
2. **Find the animal** in each, using the 601-class detector already in the app,
   filtered to a set of animal labels.
3. **Crop with 1.4× expansion** around the box — not a tight crop.
4. **Embed each crop** with MegaDescriptor into a vector.
5. **Compare with cosine similarity.**
6. **Return a verdict** — same, uncertain, or different — with the number.

## The model or algorithm

### MegaDescriptor, and why not a general embedding

The tool was originally scoped around DINOv3 — a strong general-purpose vision
embedding. The research done before writing code found something better suited:
**MegaDescriptor** (`BVRA/MegaDescriptor-T-224`), from the WildlifeDatasets
toolkit. It is the first foundation model built specifically for **individual
animal re-identification**, and it is published as outperforming generic
embeddings including CLIP and DINOv2 on exactly this task.

The distinction that makes it the right model is worth being precise about,
because it is the conceptual core of the chapter.

A general embedding is trained so that **similar images** land near each other.
For animals that means it learns *species* — every fox near every other fox,
because foxes look alike. That is the correct behaviour for its objective and
exactly wrong here, since it makes two different foxes score as a match.

A re-identification embedding is trained on the opposite objective: **the same
individual, across different photographs, must land closer together than two
different individuals of the same species.** It has to learn what distinguishes
one fox from another — coat pattern, scars, ear notches, facial markings — while
ignoring pose, lighting and background.

**Same-species discrimination is a harder problem than species classification**,
and it needs a model trained for it.

It loads through `timm`, already a project dependency, so no new package was
needed.

### The verification that was actually done

The docstring records real measured numbers rather than a claim that the
technique is sound:

| Comparison | Cosine similarity |
|---|---|
| the same cat at two different resolutions | **0.992** |
| two different goldfish, side by side in one photo | **0.656** |
| cat versus goldfish | **0.090** |

Those three numbers are doing real work. The first shows resolution invariance.
The second is the one that matters most — two individuals *of the same species*
separating clearly, which is precisely what a general embedding would fail. The
third confirms the scale is behaving sensibly at the far end.

That is the difference between "MegaDescriptor is a re-ID model" and "this
pipeline produces discriminative signal on this hardware".

### The thresholds, and their honest status

```
≥ 0.85   likely the same individual
0.75 – 0.85   uncertain
< 0.75   likely different
```

The code is explicit that these are **informed by one real test, not calibrated
against a multi-individual validation set** — because none was available in this
environment.

The **uncertain band is the important part of that design.** With thresholds you
cannot validate, a two-way verdict forces a guess on every borderline case. A
three-way output lets the system decline, and declining is the correct answer
when the evidence is between the two anchors you actually measured. It is the
same reasoning as the Face Liveness chapter's uncertain band, arrived at from the
same cause: a threshold you cannot calibrate should not be made to carry a binary
decision.

### Why the crop is expanded by 1.4×

A tight bounding box is the wrong input, and the code says so: **re-ID embeddings
expect body context, not a tight crop.**

What identifies an individual is often the *pattern across the body* — the
distribution of markings, the proportions, the shape of the whole animal. A tight
crop can clip the tail, the ear tips, the flank, and those are exactly the
regions that differ between individuals of one species. The same reasoning
appears in the Face Liveness chapter for a different reason, and the shared rule
is: **match the crop geometry the model was trained on, and prefer context over
tightness when the signal is distributed.**

### Detect first, then embed

Embedding a whole photograph would mix the animal with grass, sky and a fence
post, and two photographs of the same fox in different places would differ
mostly in background. Detecting and cropping first means the embedding describes
the animal.

This is the same **crop-then-remeasure** pattern the app uses for person → face,
vehicle → number plate, and plant → foliage. A general detector locates the
region; a specialised model works inside it.

The animal label set is drawn from the detector's existing OIV7 classes — Animal,
Mammal, Bird, Cat, Dog, Fox, Deer, Badger-adjacent carnivores, down to Goldfish
and Butterfly — so nothing new was trained.

## Why these choices

**Why re-ID rather than fine-tuning a classifier per animal.** A classifier needs
a class per individual and retraining every time a new animal appears — hopeless
for wildlife, where the population is unknown and changing. An embedding needs no
retraining: a new individual is a new vector, and identification is a nearest-
neighbour lookup.

**The licence trade, stated plainly.** MegaDescriptor is **CC-BY-NC-4.0** —
non-commercial. That is a fit for a non-commercial educational portfolio and
would not be for a product. The code names it as comparable to the AGPL-3.0
trade-off already accepted for the YOLO detector. Checking and recording the
licence before adopting is the same habit that split Depth-Anything's Small
checkpoint from its non-commercial siblings.

**What is deliberately not done.** Real re-ID pipelines use pose normalisation
and multi-crop averaging; this uses a single crop and a single embedding. The
docstring says so, along with the plainest statement of scope in the tool:
*"Does this look like the same individual," not proof.*

## How to read the output

- **Read the similarity number, not only the verdict.** 0.86 and 0.84 are the
  same evidence with different labels.
- **"Uncertain" is a real answer.** It means the score fell between the two
  anchors that were actually measured.
- **Same species is the meaningful test.** Two different animals of *different*
  species scoring low proves nothing — the goldfish-versus-cat number is 0.09.
  The comparison that tells you the tool is working is two individuals of the
  same species.
- **Photograph the same aspect.** Two photographs of one animal from opposite
  sides may show entirely different markings.
- **A poor crop invalidates the comparison.** If the detector found the wrong
  thing, or clipped the animal, the embedding describes something else.
- **No animal detected means no comparison**, not "different".

## Limits

- **Not a validated identification system.** Published wildlife re-ID benchmarks
  report real error rates even with MegaDescriptor, and this skips the pose
  normalisation and multi-crop averaging those pipelines use.
- **Thresholds come from one test.** No multi-individual validation set was
  available.
- **No camera-trap dataset was available** to test against, which is the actual
  deployment condition.
- **Two images at a time.** No population database, no clustering, no
  "which of these forty sightings are the same animal".
- **Species with little individual variation** — many birds, most fish — are
  intrinsically much harder than a spotted or scarred mammal.
- **Pose, lighting and occlusion all degrade it**, and nothing here normalises
  for them.
- **CC-BY-NC-4.0.** Non-commercial use only.
- **Detection is the first failure point.** An animal the OIV7 detector does not
  recognise never reaches the embedding.

## Likely interview questions

**"Why not use CLIP or DINOv2?"**
Because they are trained so that *similar images* land near each other, and for
animals that means they learn species — every fox near every other fox. That is
correct for their objective and exactly wrong here, since it makes two different
foxes score as a match. A re-ID model is trained on the opposite objective: the
same individual across photographs must be closer than two individuals of the
same species, so it has to learn coat pattern, scars and markings while ignoring
pose and background. MegaDescriptor is published as beating both on this task.

**"How do you know it works?"**
Measured numbers rather than a claim about the technique. The same cat at two
resolutions scored 0.992; two different goldfish side by side in one photo scored
0.656; cat against goldfish scored 0.090. The middle number is the one that
matters — two individuals of the same species separating cleanly is exactly what
a general embedding would fail, and it is the evidence the pipeline produces real
discriminative signal on this hardware.

**"Your thresholds aren't calibrated. What did you do about it?"**
Added an uncertain band and disclosed the status. With thresholds informed by one
test rather than a validation set, a two-way verdict forces a guess on every
borderline case. A three-way output lets the system decline, and declining is the
right answer when the score sits between the anchors I actually measured. To
calibrate them properly I would need a labelled multi-individual dataset — ideally
real camera-trap footage — which was not available.

**"Why expand the crop instead of using the tight box?"**
Because what identifies an individual is often distributed across the whole body
— the pattern of markings, the proportions, the shape — and a tight box clips
exactly the regions that differ between individuals of one species. Re-ID
embeddings are trained on crops with body context, so a tight crop is also the
wrong input distribution. Prefer context over tightness when the signal is
distributed.

**"How would you scale this to a real camera-trap survey?"**
Embed every detection once and store the vectors, then cluster them rather than
comparing pairs — that turns "are these two the same" into "how many individuals
are in these four hundred sightings", which is the actual ecological question.
Add pose normalisation and multi-crop averaging per sighting to cut the variance,
and calibrate the thresholds against a labelled subset from the same cameras,
because the right threshold depends on the species and the camera placement.
