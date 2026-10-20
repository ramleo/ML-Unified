Chapter 44CAPTCHA Hardening Lab


> Upload a CAPTCHA-style image and watch a vision-language model try to read it — modern VLMs handle plain text CAPTCHAs far more easily than classic OCR ever did. One intensity slider then stacks three model-agnostic hardening techniques (pixel noise, an occlusion wave, contrast reduction) and the model tries again, side by side. Nothing gradient-based is used, because the solver here is a black box — the same constraint a real CAPTCHA vendor faces. It only ever reads an image you upload; it never contacts a live CAPTCHA on a real site.

## At a glance

| | |
|---|---|
| **Also called** | VLM Read Attempt · Before/After |
| **Model or method** | Mistral/Gemini vision cascade |
| **What you give it** | Photo |
| **VLM Read Attempts** | 2 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/captcha-hardening-lab` |

## Using the tool

### What this tool does
Upload a CAPTCHA-style image you already have, and a vision-language model
(VLM) attempts to read it. Then a hardening slider stacks three classic,
model-agnostic perturbations — pixel noise, an occlusion wave, and reduced
contrast/color — onto that same image, and the VLM tries to read the
hardened version too. This never contacts or solves a live CAPTCHA on a
real website — it only reads an image you upload.

### Purpose
CAPTCHAs exist to tell humans and bots apart. As VLMs get better at reading
distorted text, it's worth knowing empirically how much visual degradation
it actually takes to defeat a model-based solver, since that number
directly informs how CAPTCHAs should be designed. The real research
question this tool demonstrates is **"how much hardening does it take
before the model's answer breaks?"** — not "can we defeat this one model
outright." Because the VLM is a black-box hosted API with no gradient
access, this deliberately uses classic non-gradient perturbations rather
than adversarial-example techniques like FGSM/PGD (those are used instead
in the separate Adversarial Robustness Lab tool, against a local
white-box model).

### How to use it
1. Click **Choose CAPTCHA image** and upload a distorted-text CAPTCHA image.
2. (Optional) Type what the CAPTCHA actually says into **"What it actually
   says"** — this lets the tool mark each attempt Correct/Wrong instead of
   just showing the raw text the model returned.
3. Drag the **Hardening intensity** slider (0–100) to choose how strongly
   the three perturbations are applied.
4. Click **Test hardening** — the model reads both the original and the
   hardened image, and both results appear side by side.

### A worked example
Upload a 5-character CAPTCHA reading "X7K9P" and type that into the ground-
truth field. At intensity 0–20, the model typically still reads it
correctly (marked **Correct**, green). Raise intensity toward 60–100 and
re-run — mistakes appear (marked **Wrong**, red), or the model's answer
becomes visibly garbled. Note: this project's own live testing found a
large-clear-font synthetic CAPTCHA that the VLM still read correctly even
at maximum (100) intensity — a genuine finding, not tuned away, and exactly
the kind of result this tool is built to surface honestly.

### Reading the result
Each side (Original / Hardened) shows the model's answer text and, if you
supplied ground truth, a **Correct** or **Wrong** badge. There's no single
"defeated" verdict — you're meant to slide the intensity and watch where
(if anywhere) the answer breaks for the specific CAPTCHA and model in front
of you.

### Notes & limits
- Only tests one specific hosted VLM, not every possible CAPTCHA-solving
  model or technique — a different model may have a different breaking
  point on the same image.
- Perturbation strength is capped and deliberately non-adversarial (no
  gradient access to the model) — this is closer to real-world image
  degradation (compression, printing, screen glare) than a crafted
  adversarial attack.
- Never submits to, or interacts with, a live CAPTCHA challenge on any
  real website — upload-only, one image per request.

## What problem it solves

A CAPTCHA is a test that is supposed to be easy for a person and hard for a
machine. Text CAPTCHAs worked for years because optical character recognition
was brittle: distort the glyphs, overlap them, add a wavy line, and OCR fell
apart while people read straight through it.

Vision-language models have removed that gap. A model that can describe a
photograph in a paragraph can also read six wobbly characters, and it does so
without any of OCR's dependence on clean segmentation. The classic text CAPTCHA
is, for practical purposes, over — which is why the large providers moved years
ago to behavioural signals and risk scoring rather than a puzzle.

This lab lets you see that for yourself, and then ask the follow-up question:
**how much distortion does it take before the model stops being able to read
it, and is any human still able to at that point?**

You upload a CAPTCHA image. A vision-language model reads it. One slider adds
increasing amounts of classic distortion. The same model reads the hardened
version. Both answers appear side by side, and if you tell the tool what the
image actually says, each attempt gets a correct/incorrect mark.

Scope, stated the same way as everywhere else in this book: it operates only on
an image you upload. There is no scraping, no automation against a live
reCAPTCHA or hCaptcha challenge, and no bulk solving. One image in, one
read-attempt out.

## How it works, step by step

1. **Upload a CAPTCHA image.**
2. **The reader model attempts the original**, returning the characters it
   sees.
3. **Three perturbations are applied** at an intensity you set from 0 to 100.
4. **The same model attempts the hardened image.**
5. **Both answers are returned** with the hardened image itself, so you can
   look at what the model was given.
6. **Optionally supply the ground truth**, and each attempt is marked correct
   or incorrect by a whitespace-insensitive, case-insensitive comparison.

## The model or algorithm

### The reader

The reader is a hosted vision-language model, reached through the same
provider-cascade helper the document tools in this book use. That choice
matters for the design of everything else.

### Why the hardening is deliberately not gradient-based

The Adversarial Robustness Lab elsewhere in this book attacks a local
torchvision classifier using FGSM and PGD — real gradients through weights the
tool has in memory. None of that is available here. The reader is behind
somebody else's API: no weights, no gradients, and the provider may change the
model under you without notice.

That constraint is not a limitation of the demo. It **is the real situation**.
A CAPTCHA vendor does not know, and cannot control, which solver will be
pointed at their challenge — a person, a commercial solving service, an OCR
pipeline, or whichever multimodal model shipped last week. A perturbation
tailored to one specific model's gradients would be worthless against the next
one.

So real CAPTCHA hardening has always used **model-agnostic** distortions:
noise, occlusion, warping, colour and contrast manipulation. This tool
reproduces exactly that, under one scalar intensity.

### The three perturbations

All three scale from a single `t = intensity / 100`, applied in a deliberate
order.

**1. Contrast and colour reduction, first.** Contrast is scaled by `1 − 0.5t`
and saturation by `1 − 0.4t`. At full intensity, contrast is halved and colour
is heavily muted. This goes first because it is a whole-image tone shift, and
applying it after the other steps would attenuate them too. It mirrors what
real CAPTCHA backgrounds do — muddying the text into the background instead of
attacking the glyphs directly.

**2. A sinusoidal occlusion wave.** Two sine curves are drawn across the middle
of the image, half a period out of phase with each other, one dark and one
light:

```
y(x) = h/2 + amplitude · sin( 4π · x/w  +  phase )
amplitude = 2 + 10t
thickness = 1 + 3t
```

The dark-and-light pair is the point. A single dark line is easy to remove —
threshold it out. Two lines of opposite polarity mean that whichever background
the text sits on, one of them contrasts against it, so no single thresholding
step clears both.

**3. Gaussian pixel noise, last.** Independent noise with `σ = 45t` per
channel, added on top and clipped to the valid range. It goes last so that the
noise sits over the drawn lines too, rather than being smoothed by later
operations.

### Parsing the reader's reply

One implementation detail caused a real bug and is worth recording.

The prompt asks for `{"text": "..."}` rather than a bare string, because the
first provider in the cascade **forces `response_format=json_object`
regardless of prompt wording**. Asking for plain text gets JSON back anyway.
The first live test looked like a failure: the model clearly read the CAPTCHA
correctly both times, yet the ground-truth comparison marked both attempts
wrong — because the answer being compared was a JSON blob, not the characters.

The fix was to request a defined shape and parse it with the same helper the
rest of the codebase uses, with a fallback to the raw string if the expected
key is missing. String-matching a response that may or may not be raw text
depending on which provider answered is not a workable contract.

The correctness comparison itself is intentionally forgiving in one direction
only — it lowercases and strips all whitespace, so `Ab 3 xY` matches `ab3xy`,
but it does not do fuzzy or edit-distance matching. A near miss is a miss.

## Why these choices

**Why one slider instead of separate controls per perturbation?** Because the
question the tool exists to answer is "how much hardening", not "which
hardening". A single monotonic axis makes the comparison legible and makes
repeated runs comparable.

**Why show the hardened image back to the user?** So the human half of the test
can be evaluated at the same time. A CAPTCHA that the model cannot read and a
person cannot read either has not been hardened, it has been broken. Seeing the
image is the only way to judge that, and it is the whole reason the tool
returns it.

**Why no score, only two answers?** With one image there is no statistical
claim to make. Two raw answers plus an optional correctness mark is exactly as
much as one sample supports.

### The finding, reported as it happened

During live verification, the reader **read a synthetic test CAPTCHA correctly
even at maximum hardening intensity.** Large clear characters, and 100 on the
slider did not stop it.

That is not a favourable result for the tool, and it was kept rather than
tuned away — partly because the tool's framing already asks the right question
("how much hardening does it take", not "does this one attempt succeed"), and
partly because it is the honest headline. A modern vision-language model reads
through classic CAPTCHA distortion at intensities well past where a person
starts struggling. The perturbations that used to defeat OCR were exploiting
segmentation, and these models do not segment.

## How to read the output

Read the two answers, then look at the hardened image.

- **Both correct** — hardening at this intensity did nothing to the machine.
  Check whether the image is still comfortable for you to read; if it is, the
  test has no discriminating power at all here.
- **Original correct, hardened wrong** — you have found an intensity that
  degrades the model. Now the real question: can you still read it? If not,
  the distortion is failing both parties equally.
- **Both wrong** — either the image is genuinely hard, or the reader is a poor
  fit for this style of CAPTCHA. One sample cannot distinguish those.

The result applies to this image, at this intensity, with this reader, on this
run. Noise is random, so repeating the same request will not give the identical
answer.

## Limits

- **One image, one attempt per side.** This is a demonstration, not a
  benchmark. Nothing here supports a statement about CAPTCHAs in general.
- **The reader is a hosted model** and can change without notice, so results
  are not reproducible across time in the way a pinned local model would be.
- **No human baseline is measured.** The tool shows you the hardened image and
  leaves the human-readability judgement to you, which is subjective and
  uncontrolled.
- **Text CAPTCHAs only.** Image-grid challenges, puzzle-slider challenges and
  behavioural risk scoring are entirely outside the scope.
- **The perturbations are the classic set**, not the state of the art in
  adversarial typography, and are applied at a fixed structure — the wave is
  always horizontal and centred, so an attacker who knew that could target it.
- **The noise is random per run.** Identical requests give different images and
  can give different answers.

## Likely interview questions

**"Why can a vision-language model read a CAPTCHA that defeated OCR?"**
Classic OCR is a pipeline: binarise, segment into characters, classify each
one. Every CAPTCHA distortion targeted the segmentation stage — overlap the
glyphs and the pipeline cannot cut them apart, so everything downstream fails.
A vision-language model has no segmentation stage. It processes the whole image
into patch embeddings and produces text, so the attack surface that CAPTCHAs
were designed against no longer exists in the solver.

**"Why not use FGSM here, like the adversarial lab does?"**
No gradient access. The reader is a hosted API — I can send an image and read a
string, nothing more. Even if I could attack it, a perturbation optimised
against one model's gradients would not survive the provider swapping models,
and a real CAPTCHA has to hold up against every solver simultaneously. Model-
agnostic distortion is the only thing that generalises, which is why real
CAPTCHA hardening has always looked like this.

**"Your tool shows the model reading through maximum hardening. Doesn't that
mean the tool failed?"**
It means the technique failed, which is the finding. The tool's job is to
measure how much hardening it takes; the answer on that image was "more than
this slider goes". Reporting that is more useful than picking an image and an
intensity where the demo looks impressive. It is also the correct conclusion
about text CAPTCHAs generally, and it lines up with the industry having moved
away from them.

**"So how should a real service stop bots today?"**
Not with a puzzle. The direction the major providers took is risk scoring from
behaviour and context — mouse and touch dynamics, timing, device and network
reputation, account history — with a challenge shown only to sessions that
already look suspicious. Beyond that: rate limiting, proof-of-work to make bulk
requests cost something, and cryptographic attestation like Privacy Pass, which
proves "a real user was verified once" without re-testing every time. The
useful reframing is that you are not trying to prove humanity, you are trying
to make automated abuse expensive per unit.

**"Why draw two occlusion lines instead of one?"**
Polarity. A single dark line over dark text is nearly invisible, and a single
dark line over light text is trivially removed with a threshold. Drawing a dark
line and a light line half a period apart means whatever the local background
is, one of them contrasts against it, so no single global thresholding step
clears both.

**"Is building this ethical?"**
The line I would draw is between a tool that studies a defence and a tool that
defeats one at scale. This takes one uploaded image, reads it once, and shows
what happens under distortion — no live-site automation, no batch solving, no
integration with any real challenge. That is the same posture as the rest of
the security tools in this book, and the finding it produces is useful to
defenders: text CAPTCHAs no longer work, and here is the evidence.
