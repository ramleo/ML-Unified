Chapter 41Adversarial Robustness Lab


> Upload a photo and break an image classifier on purpose. Craft subtle FGSM or PGD perturbations, a visible adversarial patch, or a black-box attack with no gradient access, untargeted or aimed at a specific label. Then try two inference-time defences, check whether the attack transfers to a second model, and see adversarial training compared against a standard model on the run you just performed. It reports honestly whether a defence actually recovered the right label, and whether a targeted black-box attack converged at all within the query budget — often it doesn't.

## At a glance

| | |
|---|---|
| **Also called** | Local · No API Cost |
| **Model or method** | MobileNetV2 + FGSM/PGD/Patch/Black-box (local) |
| **What you give it** | Photo |
| **API Calls** | 0 |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/adversarial-robustness-lab` |

## Using the tool

### What this tool does
Upload a photo and this tool crafts an **adversarial attack** — a tiny,
mostly-invisible change to the pixels (FGSM/PGD), a visible "sticker"
patch region (Adversarial patch), or a query-only attack that never sees
the model's gradients at all (Black-box) — specifically designed to fool a
pretrained image classifier (MobileNetV2, trained on ImageNet) into
predicting the wrong thing, often with HIGH confidence in that wrong
answer. The attack can be **untargeted** (any wrong label counts) or
**targeted** (forces one exact chosen label). Then it tries two
inference-time **defenses** (JPEG recompression, randomized smoothing)
and shows honestly whether either one actually recovered the correct
prediction, plus an optional **transferability check** against a second,
different model. A separate third section further down demonstrates
**adversarial training** — a fundamentally different kind of defense —
on a small digit classifier.

### How to use it
1. Click **Choose photo** and upload any image.
2. Pick an attack method:
   - **FGSM** (single-step) — fast, one gradient step, tiny perturbation
     over the whole image.
   - **PGD** (iterative, stronger) — several smaller steps, generally more
     effective at fooling the classifier, especially at low strength.
   - **Adversarial patch** — optimizes one square region (unconstrained,
     no epsilon limit) into a directly VISIBLE sticker-style attack,
     instead of a subtle whole-image perturbation.
   - **Black-box** — the ONLY attack here with zero access to the model's
     gradients, only its predictions — the realistic threat model against
     someone else's deployed API. Genuinely much slower and, for a
     targeted goal, often doesn't converge at all (see its own section
     below).
3. For FGSM/PGD/black-box, adjust **strength (epsilon)** (labeled
   "per-query step" for black-box) — how large the perturbation is allowed
   to be. For the patch attack, adjust **patch size** instead — what
   fraction of the image the square patch covers. For black-box, also
   adjust **query budget** — how many model queries it's allowed before
   giving up.
4. Adjust the **defense's JPEG quality** — lower quality is a more
   aggressive (but more visually lossy) defense attempt.
5. Optionally type a **target label** (autocompletes over the 1000
   ImageNet classes) to try a **targeted** attack — forcing that EXACT
   wrong label, not just any wrong one. This is strictly harder than an
   untargeted attack; leave it blank for untargeted.
6. Optionally check **Check transferability (ResNet18)** to also classify
   the SAME adversarial image with a second, different model architecture
   — see whether the attack fools a model it was never crafted against.
7. Click **Run attack + defense** to see the results side by side:
   Original, Adversarial, After JPEG defense, and After randomized
   smoothing — each with its own predicted label and confidence — plus a
   transferability panel (if checked) and Grad-CAM heatmaps below.

### Reading the result — read this honestly, not optimistically
- **Fooled / Not fooled** on the adversarial image: whether the attack
  changed the top prediction at all. In testing during development, this
  was true almost every time, even at fairly small epsilon.
- **Recovered** on the defended image: the STRICT outcome — the defended
  prediction exactly matches the original correct label. This is the
  ideal case, but real testing found it does NOT happen reliably —
  sometimes not at all across a whole sweep of settings for a given photo.
- **Disrupted, not recovered**: the defense changed the SPECIFIC wrong
  answer the attack converged to, landing on a different wrong label
  instead of the correct one. This shows the defense had some real effect
  without actually fixing anything — a genuine, common outcome.
- **No effect**: the defended image's prediction is identical to the raw
  adversarial one — the JPEG pass didn't disrupt the perturbation at all
  for that combination of attack/strength/quality.
- **Target achieved / Target not reached** (only shown for a targeted
  attack): whether the adversarial prediction landed on your EXACT chosen
  label, not just any wrong one. Not reaching it usually means the epsilon
  budget was too small for that specific target — try increasing it.

### Randomized smoothing (the second defense)
This defense classifies many independently noised copies of the
adversarial image and takes a majority vote, instead of trusting one
deterministic prediction. The **vote agreement %** shown is the real
signal to watch: a HIGH vote agreement (whatever the label) means the
model was consistently confident across the noise; a LOW one (near 30-40%)
means the vote barely won — an honest sign of instability, not a reliable
recovery, even in cases where the winning label happens to be correct.
Real testing found this defense behaves similarly to JPEG recompression:
sometimes disrupts the attack, rarely reliably recovers the exact original
label. See mm_adversarial.py's module docstring for the actual sigma
sweep behind this framing.

### Transferability (does it fool a DIFFERENT model too?)
This attack is crafted using gradients from MobileNetV2 only — it has zero
access to ResNet18's weights or gradients. If you check "Check
transferability", the SAME adversarial image is also classified by
ResNet18, and "Transferred" means ResNet18's own prediction changed too —
a real security implication: an attacker who can only query a DIFFERENT
model than the one deployed may still succeed. Real testing found this
varies a lot: FGSM's single-step perturbation didn't transfer at all in
one real-photo test (ResNet18 stayed correct across every tested epsilon),
while PGD's multi-step perturbation transferred at every epsilon tested on
the same photo — a single-image finding, not a general rule, reported as
observed. See mm_adversarial.py's module docstring for the actual sweep.

### Adversarial patch (the third attack)
Unlike FGSM/PGD, this attack doesn't stay imperceptible — it optimizes one
square, unconstrained patch region into whatever pixel values best fool
the model, then places it in the center of the photo. This is the single-
image, single-placement version: the patch is optimized for THIS exact
photo, not a universal sticker proven to work on any photo from any angle
(that would need training across many images/positions/rotations, far more
compute than a live demo can do per-request). Real testing found a sharp
asymmetry between goals: **untargeted** patches fool the classifier almost
instantly — often in 1-2 optimization steps, since a patch that large is
already a big, blunt perturbation even before real optimization. **Targeted**
patches (forcing one exact label) are genuinely much harder: a small (10%)
patch failed to reach the target at all within the step budget in real
testing, while a larger (25%) patch reached it in under 40 steps — bigger
patch, easier and faster attack. The optimization step count shown after
a run is a real measure of how much work THIS run actually needed (it
stops the moment the goal is met, not always the full budget).

### Black-box attack (the fourth attack — the realistic threat model)
FGSM, PGD, and the patch attack all need REAL gradient access — this tool
has the actual model loaded locally, so it can compute "which direction
would most fool this classifier" directly via backpropagation. A real
attacker targeting someone else's deployed model usually can't do that —
they can only send an input and see the prediction come back, like
querying a live API. This attack simulates exactly that: no gradients, only
repeated queries that each return a confidence score, using a simplified
version of a published technique (SimBA). Each query nudges ONE pixel
value up or down and keeps the change only if it helped, so — unlike
FGSM/PGD's single-shot epsilon-bounded perturbation — this attack can take
hundreds to thousands of queries to get anywhere. Real testing found this
tradeoff is real, not theoretical: an **untargeted** attack converged in
~350 queries (a few seconds), but a **targeted** attack did NOT converge
at all even at the maximum 3000-query budget in real testing — a genuine,
expected limitation of query-only attacks within a request-sized budget,
not a bug. If you see "did not reach the target" for a targeted black-box
run, that IS the point of this attack — it's demonstrating a real
security/cost tradeoff, not failing to work.

### Adversarial training (the third defense — a different kind entirely)
JPEG recompression and randomized smoothing are both **inference-time**
defenses — tricks applied to an image AFTER a model was already trained
normally. Adversarial training is fundamentally different: it changes HOW
the model is trained in the first place, by training directly on
adversarially-attacked examples instead of only clean ones (Madry et al.
2018). Because real adversarial training needs many epochs over a real
dataset — infeasible to redo live against the 1000-class ImageNet
classifier used above — this section demonstrates it on a much smaller,
separate pair of digit classifiers (MNIST), trained ONCE offline and
shipped as static checkpoints, not retrained per request.
Pick a sample digit (or switch to **Upload your own** and photograph a
digit you've written on plain paper — it's preprocessed server-side:
grayscale, auto-invert, cropped to the ink, centered, resized to 28x28,
and you'll see exactly what the models received), choose an attack
strength, and click **Attack both models** — the SAME white-box PGD
attack (each model attacked with its own gradients) runs against a
standard-trained model and an adversarially-trained model side by side.
A real photo is out-of-distribution input for a model trained only on
clean MNIST, so even the CLEAN (unattacked) prediction may occasionally
be wrong — that's shown honestly, not hidden, since it's a real limit of
the preprocessing, not a bug. Real, measured numbers across
the full MNIST test set: the standard model goes from 98.6% clean
accuracy to just 1.1% robust accuracy under this attack — essentially
always fooled; the adversarially-trained model goes from 97.0% clean
accuracy to 84.3% robust accuracy under the identical attack — a real,
large, measured robustness gain, at the honest cost of a small drop in
clean accuracy. This is the real trade-off adversarial training makes,
demonstrated with actual numbers, not asserted.

### Where was the model looking? (Grad-CAM)
Below the three images, a second row shows a **Grad-CAM heatmap** for the
original and adversarial predictions — warmer colors mark the regions that
most drove that specific prediction. This is the actual "why" behind the
label change: the photo barely changed to your eye, but the model's
attention can shift to a completely different region to justify its new,
wrong answer. Comparing the two heatmaps side by side is often more
convincing than the label change alone.

### Why the defenses don't reliably work — this is the point of the demo
Both JPEG recompression and randomized smoothing are real, published
mitigation techniques against this attack family, but the real
adversarial-ML literature has always shown they're inconsistent, not a
guaranteed fix — and testing this exact demo against a real photo
confirmed that directly for both: across a sweep of epsilon/quality/sigma
combinations, the correct label was almost never fully and reliably
recovered. Simple input-side defenses are cheap and sometimes helpful, but
they are not a substitute for a genuinely robust, adversarially-trained
model — showing that honestly is more useful than pretending either toy
defense always works.

### What this is (and isn't)
This is an educational demo of a real ML robustness property, using a
generic off-the-shelf classifier (not any model used elsewhere on this
site) — it says nothing about the reliability of this site's other tools.
Nothing is stored: your photo and the results only exist for this one run.

### Notes & limits
- No API cost — the classifier, all four attacks, and all three defenses
  (including the two small digit-classifier checkpoints) run locally on
  the backend, no external calls.
- A targeted attack is strictly harder than an untargeted one — it may not
  reach your chosen label within the epsilon range this demo allows.
- PGD takes a few seconds longer than FGSM since it runs several gradient
  steps instead of one.
- Randomized smoothing runs 25 extra forward passes per request (one per
  noised copy), so results take slightly longer than the attack alone.
- The transferability check is OFF by default since it triggers a one-time
  ~45MB ResNet18 weight download on first use, adding to the wait.
- A targeted adversarial patch can take up to 150 optimization steps and
  may still fail to reach the target (a real, honest outcome, not a bug)
  — a smaller patch is more likely to fail; try a larger one first.
- The black-box attack's query budget caps at 3000 — a targeted run at the
  max budget can take up to roughly a minute or more; a real, expected
  cost of not having gradient access, not a slow implementation.
- An uploaded digit photo is capped at 8MB and preprocessed automatically
  (see the Adversarial training section above) — no manual cropping or
  thresholding needed on your end.

## What problem it solves

A neural network that classifies photographs with 90% accuracy can be made to
misclassify almost any one of them by changing the pixels in a way a person
cannot see. This is not a rare corner case or a bug in one model. It is a
property of high-dimensional decision boundaries that has survived a decade of
attempts to fix it.

That matters directly for the rest of this book. Several tools here — the
liveness check, the tampering detector, the object detectors — rest on a
classifier's output. If a classifier can be steered by an engineered
perturbation, then any decision built on top of it inherits that weakness. This
lab exists to make the failure visible, and then to show, honestly, how far the
available defences actually get you.

It runs four attacks and three defences against a real pretrained model, and
reports what happens rather than what should happen. Several of the results
recorded here are negative.

## How it works, step by step

1. **Upload a photo.** It is resized to 224×224 and classified by MobileNetV2,
   pretrained on ImageNet's 1,000 categories.
2. **Choose an attack** — FGSM, PGD, an adversarial patch, or the query-only
   black-box attack — and a strength, ε.
3. **Choose untargeted or targeted.** Untargeted means "make it wrong".
   Targeted means "make it say *this specific label*".
4. **The attack runs** and produces a modified image.
5. **Both images are classified**, and **Grad-CAM heatmaps** show where the
   model was looking before and after.
6. **Optionally check transferability** — does the same modified image also
   fool ResNet18, a model the attack never touched?
7. **Run a defence** — JPEG recompression or randomised smoothing — on the
   attacked image and see whether the correct label comes back.
8. **Separately, the adversarial-training panel** compares two small digit
   classifiers, one trained normally and one trained on attacks.

## The model or algorithm

### Why the model is off-the-shelf

The target is torchvision's **MobileNetV2**, ImageNet-pretrained, roughly 14 MB.
It is deliberately not any model used elsewhere in this project — the point is a
general property of neural classifiers, not an attack on this application. It
also has to be a real PyTorch model rather than the ONNX exports used by the
other vision tools here, because three of the four attacks need **gradients**,
and ONNX runtime only does forward passes.

### Attack 1 — FGSM, the one-step attack

The **Fast Gradient Sign Method** (Goodfellow et al., 2014) is the foundational
attack and is one line of mathematics:

```
x_adv = x + ε · sign( ∇ₓ  L(model(x), y_true) )
```

Training computes the gradient of the loss with respect to the *weights* and
steps them downhill. FGSM computes the gradient with respect to the **pixels**
and steps them uphill — the same machinery, aimed the other way. Taking only
the `sign` means every pixel moves by exactly ε, which spends the entire budget
in the L∞ sense while keeping any single pixel's change imperceptible.

Targeted FGSM is the same expression with the sign flipped and the target label
substituted: descend the loss towards the label you want instead of ascending
away from the one that is correct.

### Attack 2 — PGD, the iterative attack

**Projected Gradient Descent** (Madry et al., 2018) is FGSM done properly:
several small steps instead of one large one, with a projection back inside the
allowed region after each step.

```
for each of 10 steps:
    x_adv ← x_adv + α · sign(∇ₓ L)          with α = ε/4
    x_adv ← clip(x_adv, x − ε, x + ε)       project onto the ε-ball
    x_adv ← clamp(x_adv, 0, 1)              stay a valid image
```

The projection is what makes it correct rather than merely iterative. Without
it the perturbation grows without bound and stops being imperceptible; with it,
the attack explores the ε-ball's interior instead of only its corner. PGD is
generally regarded as the strongest first-order attack and is the standard
against which defences are measured.

Two clamps, not one: the ε-ball keeps the perturbation small, and the [0,1]
clamp keeps the result a displayable image. An adversarial example with a pixel
value of 1.3 is not an image.

### Attack 3 — the adversarial patch

A different family entirely. Instead of a tiny change everywhere, this
optimises a **single visible square** — a sticker — with no ε constraint at all
inside that square. The rest of the image is untouched. This is the attack
family that can, in principle, be printed and stuck on a physical object.

A mask selects a centred square covering a chosen fraction of the image; the
patch pixels are then optimised by the same sign-of-gradient step used by PGD,
free to take any value in [0,1]. The loop **early-stops the moment the goal is
met**, so the reported step count is a real measure of how much optimisation
that particular run needed rather than a fixed budget.

Testing found a sharp asymmetry worth stating plainly:

| Goal | Result |
|---|---|
| Untargeted | fools the classifier almost immediately — often within 1–2 steps, sometimes because a patch of this size is already a large blunt perturbation before optimisation contributes anything |
| Targeted, 10% patch | failed to reach the chosen label at all within the step budget |
| Targeted, 25% patch | reached it in under 40 steps |

This is the single-image, single-position version. Brown et al.'s original
**universal** patch is trained across many images, positions, scales and
rotations using expectation-over-transformation so that it works anywhere on
any photo — a substantially larger job, and the tool does not claim to do it.

### Attack 4 — the black-box attack, with no gradients at all

The first three attacks assume you can differentiate through the model, which
means having the weights. The realistic threat model usually does not: you have
an HTTP endpoint that returns scores.

This implements a simplified **SimBA** (Guo et al., 2019). Visit random,
never-repeated `(channel, row, column)` coordinates. At each one, try nudging
that single value by +ε, then by −ε, and keep whichever direction moves the
target class's softmax score the right way. If neither helps, leave it and move
on.

Because each coordinate is touched at most once, the maximum per-pixel change
is bounded by ε automatically — the algorithm gets its ε-ball for free, with no
projection step.

The measured results are the reason this attack is in the tool:

| Goal | Queries | Wall time | Outcome |
|---|---|---|---|
| Untargeted | 348 | ~5.5 s | succeeded |
| Targeted | 3,000 | ~46 s | **failed** |
| Targeted, larger step | 6,000 | ~94 s | **still failed** |

Query-only attacks are dramatically more expensive than white-box ones, and a
request-sized query budget is often simply not enough for a targeted goal. That
is a genuine property of the threat model, reported as observed rather than
tuned away.

One caveat is stated in the code: this assumes **score-based** access, meaning
the API returns a probability. Many hosted classifiers do. A true label-only
black box, where you see nothing but the top-1 string, is harder still and
needs far more queries.

### Grad-CAM — showing *why*, not just *what*

A changed label alone is unconvincing; it looks like a number moved. Grad-CAM
takes the last convolutional block's activations, weights each channel by its
gradient towards the predicted class's logit, and produces a heatmap of the
regions that actually drove *that specific prediction*.

Computed for both the original and the attacked image and shown side by side,
it makes the attack legible: the model's attention shifts off the object and
onto background texture that now carries the engineered signal.

### Defence 1 — JPEG recompression

Encode the attacked image as lossy JPEG and decode it back. JPEG's quantisation
discards high-frequency detail, and an adversarial perturbation is largely
high-frequency, so some of the attack is destroyed while the image content
survives.

Two outcomes are reported separately, and the distinction is the honest part:

- **`recovered`** — the defended prediction exactly matches the original
  correct label. The strict, ideal outcome.
- **`disrupted`** — the defended prediction merely differs from the
  attacker's chosen wrong label. Weaker, but evidence the defence did
  something.

Testing across several ε and quality combinations found it more often achieves
*disruption* than *recovery*, works better against PGD than against
single-step FGSM, and struggles when the model's original confidence was
unremarkable to begin with. That matches the mixed findings in the
adversarial-ML literature on input-preprocessing defences, and it is reported
rather than filtered down to the favourable settings.

### Defence 2 — randomised smoothing

Instead of one prediction, classify 25 independently Gaussian-noised copies of
the image and take a majority vote. The intuition: the perturbation is a small,
precisely-aimed direction in pixel space, and large random noise knocks most
samples off that direction, so the vote drifts back towards the image's true
neighbourhood.

The sigma sweep run during development is the most useful thing in this
section:

| σ | Effect on a strong PGD attack (ε = 0.08) |
|---|---|
| 0.15 | barely disrupted anything — 96% of votes stayed on the attacker's label |
| **0.25** | *sometimes* recovered the correct label, but with vote confidence around 0.3–0.4 — a bare plurality that changed between runs on identical input |
| 0.35+ | started destroying real image content, landing on labels unrelated to either the original or the attack |

The shipped default is 0.25, and its instability is surfaced directly as
`vote_confidence` rather than hidden behind a single point prediction. Too
little noise and the attack survives; too much and you have destroyed the
image. The usable window is narrow and depends on the attack strength you did
not know in advance.

This is the **empirical** vote only. Cohen et al.'s certified-radius guarantee
needs thousands of samples plus a concentration bound, and the tool explicitly
does not claim it.

### Defence 3 — adversarial training

The other two defences are tricks bolted onto a finished model. Adversarial
training (Madry et al., 2018) changes how the model is built: generate attacks
during training and train on them, so the decision boundary is pushed away from
the directions attacks actually use.

This cannot be demonstrated on MobileNetV2 — real adversarial training needs
many epochs over a labelled dataset, which is not happening per-request on a
CPU-only host. So the panel uses two small CNNs (about 110K parameters each)
trained once offline on MNIST and shipped as static checkpoints of roughly
427 KB. Same architecture, same data, same three epochs; the only difference is
the training procedure.

| | Clean accuracy | Accuracy under PGD |
|---|---|---|
| Standard training | **98.62%** | **1.09%** |
| Adversarial training | 96.98% | **84.30%** |

That table is the whole argument. The standard model is essentially destroyed
by an attack it never saw. The adversarially-trained model gives up about 1.6
points of clean accuracy and keeps 84% under the same attack.

Both models are attacked **independently and white-box**, each using its own
gradients, because the optimal perturbation differs per model and sharing one
would be an unfair, weaker test of the defended model.

## Why these choices

**Why show FGSM when PGD is strictly better?** Because the comparison is the
lesson. FGSM is one step and PGD is ten, and the difference shows up everywhere
— in success rate, in how much of the ε budget is actually used, and most
strikingly in transferability.

**The transferability finding.** With `check_transfer` enabled, the same
attacked image is handed to ResNet18, a different architecture that the attack
never had gradient access to. Across ε from 0.02 to 0.08 on a real photo:
FGSM's perturbation **did not transfer at any tested ε** — ResNet18 kept its
correct prediction every time, even though FGSM fooled MobileNetV2 every time.
PGD's perturbation **transferred at every tested ε**. It moved ResNet18's
prediction, though never to the same wrong label MobileNetV2 landed on.

This is a single-image, single-model-pair observation, and it is reported that
way rather than as a general law. But the direction is intuitive: a one-step
attack finds a perturbation specific to one model's local gradient, while an
iterative attack pushes further into a region where several models are wrong
together.

**Why is targeted always the harder mode?** Untargeted needs the prediction to
land anywhere in 999 wrong classes. Targeted needs it in one specific class.
Same ε budget, vastly smaller target — which is why targeted mode fails within
budget for the patch at 10% and for the black-box attack entirely.

**Why present three defences that all partially fail?** Because that is the
state of the field, and a lab that showed only a defence that works would be
teaching the wrong thing. The two input-preprocessing defences are cheap and
unreliable. Adversarial training genuinely works and costs clean accuracy,
training time, and generality. There is no free option, and the honest ordering
is: adversarial training if you can afford it, input preprocessing as
defence-in-depth, and never a claim of robustness without measuring it under
attack.

## How to read the output

Compare the two labels first, then the two Grad-CAM heatmaps. If the label
changed but the attention map is unchanged, the model was near a boundary
already; if the attention moved off the object, the attack redirected it.

For the patch attack, read the step count — it is a real measure of difficulty
for that image, since the loop early-stops on success.

For the black-box attack, read the query count. That number is the attack's
real-world cost against a rate-limited API, and it is the reason gradient
access matters so much.

For randomised smoothing, read `vote_confidence`, not the label. A correct
label at 0.35 vote confidence is a coin flip that happened to land well, and
re-running on the identical input can give a different answer.

For the defences generally, `disrupted` without `recovered` means the defence
broke the attack without restoring the truth. That is a real outcome and
usually the common one.

## Limits

- **One model, one dataset per demo.** The main lab is MobileNetV2 on ImageNet
  photos; the adversarial-training panel is a tiny CNN on MNIST digits. MNIST
  robustness results notoriously do not generalise upward.
- **The adversarially-trained model was only tested against PGD** at the ε
  range offered here. Robustness against attacks it was not trained on — a
  different ε, a transferred attack, a black-box attack — can be much weaker.
- **The patch is not universal.** It is optimised for one image at one
  position, and physical printing, angle and lighting are not modelled.
- **The black-box attack assumes score access.** Label-only is harder.
- **Randomised smoothing here is empirical**, with no certified radius.
- **Uploaded photos of handwritten digits are out-of-distribution** for the
  MNIST models. Preprocessing mirrors MNIST conventions — greyscale, auto-invert,
  crop to ink, centre, resize to 28×28 — but a photographed digit can be
  misclassified before any attack, which is why the preprocessed image and the
  clean prediction are both shown.
- **Every number quoted in this chapter came from a specific run** on a
  specific image. They demonstrate behaviour; they are not benchmarks.

## Likely interview questions

**"Explain FGSM in one sentence."**
Take the gradient of the loss with respect to the input pixels rather than the
weights, step every pixel by ε in the direction of that gradient's sign, and
you have moved the image across the decision boundary while changing each pixel
by an amount too small to see.

**"Why does PGD beat FGSM?"**
FGSM takes one linear step, which assumes the loss surface is locally linear
over the whole ε-ball — it usually is not. PGD takes several smaller steps and
projects back onto the ball after each, so it follows the curvature and finds a
better point inside the same budget. Empirically it also produces perturbations
that transfer to other models, which the single step does not.

**"What is the difference between a targeted and an untargeted attack, and why
does it matter operationally?"**
Untargeted only requires the model to be wrong; targeted requires a specific
wrong answer. Targeted is much harder for the same budget, which is why some
attacks in this lab succeed untargeted and fail targeted outright. It matters
operationally because most real harms are targeted — making a stop sign read as
a speed limit, or making malware classify as benign — so untargeted success
rates overstate the attacker's real capability.

**"Your defence recovered the correct label. Is the model safe now?"**
No, for two reasons. First, the defence was measured against the attack it was
shown; an attacker who knows the defence is present can attack the composed
system — differentiate through the JPEG approximation, or optimise against the
noise distribution. That is **adaptive attack** evaluation, and the field's
history is a long list of defences that looked strong until someone ran one.
Second, in this lab the recovery is unstable: the smoothing vote sits near 0.35
and flips between runs on identical input.

**"What does adversarial training cost?"**
Clean accuracy, training compute, and generality. Here, 1.6 points of clean
accuracy for 83 points of robust accuracy against the trained-for attack — a
good trade at this scale. Training cost is the real bill: each batch needs a
full PGD attack generated against the current weights, so an epoch costs
roughly the number of attack steps times a normal epoch. And the robustness is
specific to the attack type and ε range it was trained on.

**"How would you attack a model you have no access to?"**
Either transfer or query. Transfer: train or obtain a substitute model on
similar data, attack it with something iterative like PGD, and hope the
perturbation carries — this lab's transfer result shows PGD carrying where FGSM
did not. Query: a score-based method like SimBA, which needed 348 queries for
an untargeted success here and failed targeted at 6,000. That query count is
also the defence — rate limiting, returning coarse or top-1-only scores, and
detecting the near-duplicate query patterns these attacks produce all raise the
cost sharply.

**"Why do adversarial examples exist at all?"**
The framing I find most useful is Ilyas et al.'s: they are not bugs but
**non-robust features**. Models learn genuinely predictive patterns that happen
to be imperceptible to humans and brittle under small perturbation. The model
is not malfunctioning — it is using signal that is real in the training
distribution and trivially manipulable. That also explains transferability:
different models trained on the same data learn overlapping non-robust
features, so a perturbation that exploits one often exploits another.

**"Where does this matter in a product?"**
Anywhere a classifier's output triggers a consequence without a human in the
loop — content moderation, fraud scoring, biometric liveness, automated
inspection. The engineering response is not to expect a robust model. It is to
assume the classifier can be steered and to design the surrounding system
accordingly: rate limits and query-pattern monitoring to make black-box attacks
expensive, multiple independent signals so no single model is decisive,
human review for consequential outcomes, and measuring accuracy under attack
rather than only on the clean test set.
