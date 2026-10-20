Chapter 32Photo Library Visual Search


> Upload a batch of photos and describe what you are looking for in plain language — 'the red backpack', 'a dog on a beach' — and every photo is ranked by how well it matches. CLIP puts the images and your words in the same embedding space, so nothing needs tagging or captioning first. Nothing is stored between searches.

## At a glance

| | |
|---|---|
| **Also called** | CLIP · No API Cost |
| **Model or method** | clip-ViT-B-32 (local) |
| **What you give it** | Batch of photos + text query |
| **API Calls** | 0 |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/photo-search` |

## Using the tool

### What this tool does
Upload a batch of photos, then describe in plain language what you're
looking for — "the red backpack", "a dog on a beach", "a whiteboard with
diagrams" — and every photo gets ranked by how well it matches your
description. No tagging or captioning step first: this uses CLIP, a model
trained to understand images and text in the same "space," so it can
compare a sentence directly against a photo's visual content.

### How to use it
1. Click **Add photo(s)** and select as many images as you want to search
   through (you can add more photos in multiple batches — they all stay in
   the pool together).
2. Type what you're looking for into the search box and click **Search**
   (or press Enter).
3. Photos re-sort with the best match first, each showing a match
   percentage badge.

### Search by an example photo instead
Instead of typing a description, you can click **Find similar** on any
photo you've already uploaded to search using that photo itself as the
query — useful when you know roughly what you want but it's easier to show
than describe. The reference photo gets outlined and labeled instead of
scored, and won't appear in its own results.

### Excluding a concept
The optional **excluding** field steers results away from a concept —
"beach sunset" excluding "people" pushes photos with people further down,
even if they'd otherwise match well. This works by subtracting the excluded
concept's direction from the search direction in CLIP's embedding space —
it's a steer, not a hard filter, so a photo that strongly matches both the
main description and the excluded concept can still rank low rather than
being removed outright.

### Reading the match percentage
The percentage is **relative to this batch and this search only** — it
shows how much better a photo matches your description compared to the
others in the same search, not an absolute confidence score. A 100% match
means "the best fit among the photos you uploaded," not "certainly this."
Searching the same photos with a different description can reorder and
re-score everything.

### Find duplicates
Click **Find duplicates** to check the whole batch for near-identical
photos (burst shots, accidental re-uploads) — no query needed, it reuses
the same CLIP embeddings. Matched photos get grouped together and outlined
in a shared color. This is a heuristic, not exact-file matching: it can
occasionally group photos that are genuinely just very visually similar
(not literal duplicates), especially for near-blank or low-detail images.

### What this is (and isn't)
CLIP compares overall visual meaning, not exact objects or text in the
image — it's very good at broad scenes, colors, and concepts, but a very
specific or unusual description (an exact brand logo, a precise count of
objects) may not rank as cleanly. Nothing is stored between searches:
photos and results only exist in your browser tab for that session.

### Notes & limits
- No API cost — CLIP runs locally on the backend, no external calls.
- Every search re-embeds the whole photo batch, so a very large batch
  (dozens of photos) will take a little longer per search than a small one.
- This is search over a batch you upload in-session, not a persistent
  photo library — nothing is saved after you leave the page.

## What problem it solves

You have four hundred photos and you are looking for the one with the red
backpack in it.

Every conventional search is useless here. Filenames are `IMG_4821.jpg`. There
are no tags, because nobody tags their own photos. Sorting by date only helps if
you remember when. So you scroll, and you look at four hundred pictures.

The reason this is hard is that the search term is *text* and the thing being
searched is *pixels*, and those live in completely different representations.
There is nothing in a JPEG that the string "red backpack" can be matched
against.

This tool bridges that gap. Type a description, or point at a photo you already
have, and it ranks the batch by how well each image matches — with no captions,
no tags and no training on your library.

## How it works, step by step

1. **Upload a batch** — up to 40 photos, 8 MB each.
2. **Embed every photo** with CLIP, in one batched call.
3. **Embed the query.** Either your text, or a reference photo.
4. **Optionally subtract an exclusion** — "beach photos, not people".
5. **Normalise everything and take the dot product**, which gives cosine
   similarity between the query vector and each image vector.
6. **Sort best-first** and return the ranking.

The same embeddings also power duplicate detection, with no extra model and no
query.

## The model or algorithm

### CLIP — one space for pictures and words

`clip-ViT-B-32`, and the idea behind it is the whole chapter.

CLIP was trained on hundreds of millions of image-and-caption pairs from the
internet, with two encoders — one for images, one for text — and one objective:
**put a picture and its true caption close together in a shared vector space,
and push mismatched pairs apart.** That is contrastive learning; for a batch of
N pairs, the correct pairing has to score higher than all N−1 wrong ones.

The consequence is what makes this tool possible. After training, an image of a
red backpack and the sentence "a red backpack" land near each other **in the
same 512-dimensional space**, even though they came through entirely different
encoders. Which means comparing text to an image is just a dot product.

Before CLIP, the way to do this was to run a classifier over a fixed vocabulary
and search the labels — which limits you to the classes someone chose in advance.
CLIP has no label set. "A red backpack", "someone laughing", "a photo taken at
golden hour" all work, because they are all just sentences to encode.

### Cosine similarity, and why everything is normalised

Similarity is the cosine of the angle between two vectors:

```
similarity = (a · b) / (|a| × |b|)
```

Normalising both to unit length first reduces that to a plain dot product, which
is why the code divides by the norms and then does one matrix multiply:

```python
img_norms = image_embeds / norm(image_embeds, axis=1, keepdims=True)
scores    = img_norms @ query_norm
```

**Angle rather than distance** is the right measure here because the *direction*
of an embedding carries the meaning while its magnitude is largely an artefact —
of image contrast, of sentence length. Two vectors pointing the same way are
about the same thing whatever their length.

The matrix multiply also means all 40 comparisons happen in one operation
instead of a Python loop.

### Text or image, same machinery

A reference photo is encoded by the image encoder instead of the text encoder,
and after that **the ranking code is identical** — by that point it is just a
vector. That is the shared-space property paying off: "find more like this one"
and "find a red backpack" are the same operation with a different first step.

One necessary detail: when the reference photo is itself in the batch,
`exclude_filename` removes it from its own results, so the trivial 100%
self-match does not take the top slot.

### The exclusion — steering, not filtering

`exclude_query` lets you say "beach photos, but not people". The implementation
is CLIP vector arithmetic — normalise both, subtract the exclusion direction
from the query direction, then re-normalise:

```
query = unit(query) − unit(exclude)
```

This works because directions in CLIP space are semantic, so subtracting one
concept's direction genuinely moves the query away from it.

**The comment in the code is careful to say what this is not**, and the
distinction is the interesting part: it **steers** rather than filters. A photo
that matches both concepts strongly — "a red car" excluding "vehicles" — can rank
low, because the subtraction weakens the *whole* query direction, not just the
excluded part. When the two concepts overlap heavily, you have subtracted much
of what you were asking for.

A hard filter would need a second pass with a threshold on the exclusion score.
Vector arithmetic is one extra encode and no extra pass, and it behaves well
when the concepts are genuinely separate — which is the common case.

### Duplicates come free

Duplicate detection needs no new model and no query: *"does this batch contain
near-identical photos"* is just *"are any two embeddings almost the same
vector"*. The default threshold is **0.97**, inside the range normally used for
near-duplicate detection with this model.

This is worth noticing as a design pattern. The embeddings were computed for
search; duplicate detection is a second question asked of the same numbers.

**And it is near-duplicate, not exact-duplicate.** A file hash finds byte
identical copies and nothing else. Embedding similarity finds the same photo
resized, re-compressed, lightly cropped or colour-adjusted — which is what "I
have this twice" usually means in a real library.

### Stateless by design

There is no database and no index. One request carries the photos *and* the
query, and nothing survives it. The docstring is explicit that this is not a
searchable corpus that outlives a request — it is a batch job.

That is a real limitation for a photo library, where you would want to embed
once and query many times. It is the right call for a stateless demo on
ephemeral hosting, where anything written to disk disappears on restart anyway.

## Why these choices

**Why CLIP rather than captioning each photo and searching the text.** Captioning
means a vision-model call per photo — slow, and expensive at 40 photos — and the
caption is a lossy summary: whatever it did not mention is unsearchable. CLIP
embeds the whole image once, and the query meets it directly.

**Why the module owns its own model instance** even though the same CLIP model is
loaded elsewhere in the app. The docstring says it: to keep the two features
decoupled. The cost is memory; the benefit is that changing one feature's model
cannot break the other.

**Why 40 photos and 8 MB.** One request, CPU inference, free hosting.

**Why one batched encode** rather than per-photo calls. Batching is where nearly
all the throughput is on CPU inference.

## How to read the output

- **Scores are relative, not absolute.** Cosine similarity for CLIP typically
  lands in a narrow band — 0.2 to 0.35 is a normal range for a good text match,
  not a bad score. **Read the ranking, not the number.**
- **The gap between first and second tells you more than either.** A clear
  leader means a confident match; forty photos within 0.01 means the query
  matched nothing in particular.
- **Descriptive queries beat single words.** "A red backpack on a wooden floor"
  gives CLIP more to align against than "backpack".
- **Image queries are usually stronger than text** for "more like this", because
  the reference contains far more detail than a sentence.
- **An exclusion that removed everything** means the two concepts overlapped —
  the subtraction took the query with it.
- **`skipped`** counts photos dropped as invalid or oversized.

## Limits

- **40 photos per request, 8 MB each.**
- **Stateless.** Re-uploading and re-embedding on every query; no index.
- **CLIP's known weaknesses are yours.** It is poor at counting ("three cats"),
  at reading text in images, at fine spatial relations ("the cup *left of* the
  laptop"), and at distinguishing fine-grained categories it saw little of.
- **Its training data is the internet**, with the biases that implies.
- **Exclusion steers, it does not filter.**
- **Scores are not calibrated.** There is no threshold above which a match is
  "correct".
- **No face recognition, no location, no date filtering** — this is visual
  similarity only.
- **Duplicate detection at 0.97 is a judgement call**; a genuinely similar pair
  of different photos can cross it.

## Likely interview questions

**"How can you search images with text at all?"**
CLIP trains an image encoder and a text encoder together, contrastively, so that
a picture and its true caption end up close in one shared vector space while
mismatched pairs are pushed apart. After training, "a red backpack" and a photo
of one land near each other despite coming through different encoders — so the
search is a dot product between a text vector and a set of image vectors. Before
CLIP you would classify into a fixed label set and search the labels, which
limits you to categories chosen in advance.

**"Why cosine similarity rather than Euclidean distance?"**
Because direction carries the meaning and magnitude is mostly an artefact — of
image contrast, of sentence length. Two vectors pointing the same way are about
the same thing regardless of length, and cosine ignores length by construction.
Normalising both to unit vectors also turns the whole thing into one matrix
multiply, so all 40 comparisons happen in a single operation.

**"Your scores are all around 0.3. Is that bad?"**
No — that is a normal range for CLIP text-image similarity, and the absolute
value is not meaningful. What matters is the ranking and the gap: a clear leader
means a confident match, while forty photos within 0.01 of each other means the
query matched nothing in particular. I would not put a fixed threshold on it.

**"How does the exclusion work, and when does it fail?"**
Vector arithmetic: normalise the query and the exclusion, subtract the exclusion
direction, re-normalise. It fails when the two concepts overlap heavily — "a red
car" excluding "vehicles" subtracts most of what you asked for, because the
subtraction weakens the whole query direction rather than just the excluded part.
It steers rather than filters, and I would describe it that way to a user rather
than implying it is a hard exclusion.

**"You get duplicate detection for free. Explain."**
Search already embeds every photo. "Are two photos near-duplicates" is "are two
embeddings nearly the same vector", so it is a second question asked of numbers
already computed — no extra model, no query. And it is better than a file hash
for the actual problem: a hash finds byte-identical copies only, while embedding
similarity catches the same photo resized, re-compressed or lightly cropped,
which is what having something twice usually looks like.

**"How would you make this work over 100,000 photos?"**
Split embedding from querying. Embed once at upload time and store the vectors
in a vector database — FAISS, or pgvector — then a query embeds one string and
does an approximate nearest-neighbour search instead of a full scan. The current
design re-embeds the whole batch per request, which is correct for a stateless
demo of at most 40 photos and completely wrong at scale.
