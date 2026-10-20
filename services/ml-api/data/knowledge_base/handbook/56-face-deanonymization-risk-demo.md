Chapter 49Face Deanonymization Risk Demo


> See how face re-identification actually works, on photos you supply. Upload a target photo and a small gallery, and the gallery is ranked by how closely each face matches — a real measured similarity, the same mechanism behind Clearview-style search. A 'Protect and re-test' step then cloaks the target and runs the identical search again so you can see whether the match survives. It searches nothing but the photos in your request — no internet, no database.

## At a glance

| | |
|---|---|
| **Also called** | Local · No API Cost |
| **Model or method** | InceptionResnetV1 (local) |
| **What you give it** | Photos |
| **API Calls** | 0 |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/face-deanonymization-demo` |

## Using the tool

### What this tool does
Upload a target photo (the kind of photo someone might post publicly) and a
small gallery (2–10) of other real photos of people. The tool runs a real
face-embedding similarity search — the same mechanism Clearview-style
facial-recognition re-identification systems use — to rank which gallery
photo is most likely the same person as the target, and shows the actual
measured cosine-similarity score for every photo in the gallery.

### Purpose
Face Cloak (a sibling tool in this project) demonstrates a *defense*
against facial-recognition scraping — but it only ever measured a cloaked
photo's similarity to its own original embedding, never showed an actual
re-identification happening. This tool exists to close that gap honestly:
it shows the real attack the defense is meant to counter, using the exact
same face-embedding model, so you can see both the risk and the
countermeasure work against each other on real, measured numbers.

### How to use it
1. Click **Choose target photo** and upload a photo containing one face.
2. Click **Add gallery photos** and upload 1–10 other real photos of
   people (a mix of the same person from a different photo and other
   people works best to see the ranking in action).
3. Click **Run search** — every gallery photo gets a real cosine-similarity
   score against the target's face embedding, and the best match is
   called out.
4. Click **Protect target & re-test** to cloak the target photo (the same
   adversarial-perturbation technique Face Cloak uses) and re-run the exact
   same search, to see whether the match breaks.

### A worked example
This was verified live with two distinct real people's photos: the true
same-person match scored **99% similarity ("Likely same person")**, while
a different person's photo scored **46% ("Uncertain")**. After clicking
"Protect target & re-test," the same-person similarity dropped from 99% to
**-77%**, flipping the verdict all the way to "Likely different person" —
a genuine, measured demonstration that the cloaking countermeasure defeats
the exact re-identification it just showed working.

### Reading the result
Each gallery photo gets a verdict badge:
- **Likely same person** (red, ≥ the same-person threshold)
- **Uncertain** (amber, in between)
- **Likely different person** (green, below the different-person threshold)

The "Best match" banner calls out the single highest-scoring gallery photo
and its similarity percentage. After protection, a second banner shows the
new best match (if any) and how the *original* best-match photo's own
similarity score moved.

### Notes & limits
- **Does not search the internet or any real database.** It only compares
  the photos you upload within this one request — nothing is stored, and
  no external face database is queried. It demonstrates the mechanism, not
  a real-world lookup against any actual person's data.
- Gallery is capped at 10 photos.
- If no face is detected in the target photo (or a gallery photo), that
  photo is reported as having no detectable face rather than a forced
  guess.
- Cloaking (the "Protect" step) only affects the *specific uploaded copy*
  of the target photo in this session — it cannot retroactively protect
  copies of the same photo already posted or scraped elsewhere.

## What problem it solves

Most people's mental model of facial recognition is a police database: a
curated list of known individuals, deliberately assembled. That model makes it
feel distant and bounded.

The reality is closer to a search engine. A face becomes a vector, every vector
goes into an index, and identification is a nearest-neighbour lookup. There is
no list of known individuals — there is a photo, and everything the crawler
ever collected, and a similarity ranking. Scale is the only ingredient that
changes.

This tool makes that mechanism concrete without touching anyone's real data.
You supply a target photo and up to ten gallery photos. It embeds every
detected face with the same model, ranks the gallery by cosine similarity to
the target, and shows the scores. That is the whole of the algorithm behind
Clearview-style re-identification — the difference between this demo and the
real thing is entirely the size of the gallery.

Then it lets you break it. One button cloaks the target using the Face Cloak
tool's existing endpoint and re-runs the identical search, so you can watch a
99% match collapse.

**Scope, stated plainly:** it does not search the internet, any database, or
any stored index. It compares only the photos you upload in that one request,
and nothing is retained.

## How it works, step by step

1. **Upload a target photo and one to ten gallery photos.**
2. **For each photo**, detect the face, take the highest-confidence detection,
   expand the box by 1.6×.
3. **Embed each face** into a 512-dimensional L2-normalised vector.
4. **Compute cosine similarity** between the target's vector and each gallery
   vector.
5. **Rank the gallery** and label each result same, uncertain or different.
6. **Optionally: "Protect and re-test."** The target is sent to Face Cloak's
   endpoint, and the same search is run again against the same gallery.

## The model or algorithm

### One embedding model, imported not duplicated

The face embedding is InceptionResnetV1 on VGGFace2 — described in full in the
Face Cloak chapter, since that tool owns it.

What is worth noting is the structure. This module imports `_ensure_loaded`,
`_face_crop_box`, `_embed`, `_FACE_LABELS` and both similarity thresholds
**directly from `mm_face_cloak`**. It adds no face-embedding code of its own
and shares the single loaded model instance.

That is deliberate and it matters for the demonstration's credibility. If the
attack tool and the defence tool each had their own copy of the embedding
pipeline, any measured difference between them could be an artefact of a
divergence in crop margins or normalisation. Sharing the exact code means the
"protect and re-test" result is a genuine before-and-after on one pipeline,
not a comparison of two implementations. It also means the 112 MB of weights
are loaded once regardless of which tool the visitor opens first.

The same thresholds are reused, mapped to a three-way verdict:

| Cosine similarity | Verdict |
|---|---|
| ≥ 0.5 | **same** |
| 0.3 – 0.5 | **uncertain** |
| 

## Limits

- **No internet search and no database.** Only the photos in the request.
- **Ten gallery photos.** Real systems index billions, and every property that
  makes those systems dangerous — base rates, near-duplicate collisions,
  demographic error skew — needs scale to appear.
- **No accuracy measurement.** The numbers here come from a handful of real
  photos. There is no false-match or false-non-match rate, because measuring
  one requires a labelled multi-identity corpus this project does not have.
- **Known demographic bias.** Published evaluations, including NIST's FRVT,
  have repeatedly found face-recognition error rates that differ substantially
  across demographic groups. Nothing here measures or corrects for that, and
  the demo's small scale conceals it entirely.
- **One face per photo** — the highest-confidence detection.
- **The detector gates everything.** A face the object detector misses is
  simply absent from the search, which is a different failure from a low score.
- **The thresholds are heuristic**, inherited from Face Cloak and not
  calibrated for this model.

## Likely interview questions

**"How does large-scale face search actually work?"**
Every face is converted by a neural network into a fixed-length embedding —
512 dimensions here — trained so that the same person's photos land close
together and different people land apart. Identification is then a
nearest-neighbour query in that space, using an approximate index such as FAISS
or HNSW for speed. There is no per-person model and no enrolment step: adding a
new identity means adding a vector.

**"You got 0.46 between two different people. Is that a problem?"**
On its own, no — it stayed under the same-person threshold, so it did not
produce a false match. As a signal about deployment at scale, yes. It sits in
the uncertain band, and the false-positive rate that matters depends on the
base rate. A threshold that yields a 0.46 for an unrelated pair means that in a
gallery of millions, some unrelated pair will exceed 0.5 by chance. That is why
large-scale identification needs a far stricter threshold than verification
does, and why the same model is sound for unlocking your own phone and unsound
for picking a suspect out of a city.

**"What is the difference between verification and identification?"**
Verification is one-to-one: does this face match this claimed identity? The
base rate is favourable and the failure mode is a locked-out user.
Identification is one-to-many: who is this, out of everyone in the index? Every
extra entry is another chance to exceed the threshold, so the false-positive
rate compounds with gallery size and the failure mode is accusing a stranger.
Vendor accuracy figures are frequently quoted from verification benchmarks and
then applied to identification deployments, which is not a valid transfer.

**"Why import the private helpers from the other module instead of writing your
own?"**
Because the whole value of the tool is the before-and-after comparison, and
that comparison is only meaningful if both sides run the identical pipeline. A
separate implementation could differ in crop margin, resize interpolation or
normalisation, and any of those would show up as a similarity change that had
nothing to do with the cloak. It also shares one loaded model instance instead
of two copies of 112 MB in memory.

**"Isn't building this irresponsible?"**
The mechanism is published, the models are freely downloadable, and the
commercial systems already exist at scale. Nothing here lowers the barrier for
someone intent on building one. What it does is make the mechanism legible to
people who are subject to it, and pair it with a working countermeasure in the
same interface. The constraints are what keep that defensible: user-supplied
photos only, no stored index, no internet lookup, nothing retained.

**"How would you defend against this if you ran a platform?"**
On the platform side: strip metadata, rate-limit and detect bulk scraping,
serve resized images, and treat automated harvesting as an abuse category with
teeth. On the individual side, cloaking of the kind in the paired tool here,
with the caveat that it only protects photos not already collected. And
realistically, the durable answer is legal rather than technical — Illinois's
BIPA and the GDPR's special-category rules for biometric data have changed
commercial behaviour more than any perturbation has.
