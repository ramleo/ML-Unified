Chapter 31PPE Compliance Check


> Upload a site photo and see, per person, whether a hard hat and safety vest are visible. A dedicated PPE detection model is used rather than a general object detector, since general detectors have no safety-vest class at all. Compliance is only ever read from an explicit present or absent signal the model was trained on — never inferred from something simply not being detected — so an unclear photo returns 'unclear' instead of a false pass. Low-resolution images weaken the result noticeably.

## At a glance

| | |
|---|---|
| **Also called** | YOLOv8n PPE |
| **Model or method** | YOLOv8n PPE (ONNX) |
| **What you give it** | Image |
| **API Calls** | 0 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/ppe-compliance-check` |

## Using the tool

### What this tool does
Upload a photo and this detects each person in it, then checks whether a
hard hat and safety vest are visible on them — a real compliance-style
check, using a dedicated PPE-detection model rather than the site's
general object detector (which has no safety-vest class at all).

### Purpose
Checked the code before building anything: the existing 601-class object
detector has a generic "Helmet" class but no vest class of any kind, so a
dedicated model is genuinely required here. Found and hands-on tested
**Hansung-Cho/yolov8-ppe-detection** (MIT-licensed weights, YOLOv8n) —
not trusted from its model card alone: an initial test on a very
low-resolution photo gave a weak, borderline result, investigated and
found to be a resolution problem, not a model problem. Re-tested on 3
higher-resolution real photos and got a real, confident pass (hard hat
0.72-0.88 confidence, safety vest 0.39-0.69), including correctly *not*
claiming "worn" PPE on a photo of gear just lying on the ground.

### How to use it
1. Upload a photo containing one or more people.
2. Click **Check compliance**.
3. Review the annotated image and the per-person hard-hat/vest status.

### A worked example
A studio photo of a worker facing the camera, wearing both a hard hat and
a safety vest clearly, scored: Person 80%, Hardhat 88%, Safety Vest 69% —
all correctly detected. A separate photo of the same gear laid out on the
ground (nobody wearing it) correctly reported both items "unclear" rather
than falsely claiming either compliance or non-compliance, since neither
the "worn" nor "not worn" signal fired confidently on gear that isn't
being worn by anyone.

### Reading the result
- **Annotated image** — each detected person's box, drawn on the real
  photo so you can visually check every claim yourself.
- **Present / Missing / Unclear** — read from whichever explicit signal
  the model actually detected (the model was trained on both "wearing a
  hard hat" and "not wearing a hard hat" as separate classes). "Unclear"
  means neither signal fired confidently — it is NOT the same as
  "missing," and is not assumed to mean either compliance or
  non-compliance.
- **Unattributed items** — PPE items detected in the photo that couldn't
  be matched to a specific person's head/torso region.

### Notes & limits
- **Not a certified safety-compliance system.** This is a real object
  detector applied to a real, disclosed problem, not a validated
  workplace-safety product.
- **Per-person attribution is a spatial heuristic**, not real person
  tracking or pose estimation: each detected hard hat/vest is matched to
  the nearest person's head or torso region by simple box overlap. A
  crowded photo with overlapping people can misattribute an item to the
  wrong person.
- **Detection confidence varies with camera angle and image quality**,
  same as any object detector — an unusual angle can lower confidence
  even for genuinely-worn PPE (seen directly in testing: a top-down
  camera angle scored a real, clearly-worn vest at only 39% confidence).

## What problem it solves

On a construction site, hard hats and high-visibility vests are the difference
between a near miss and an injury. Checking that people are wearing them is a
supervisor walking around and looking — which happens when a supervisor is
walking around and looking.

Automating it from a site camera is a natural fit, and it is also the kind of
problem where a careless implementation is worse than none. A system that
reports "compliant" because it failed to see anything is not a safety system; it
is a false reassurance with a logo on it.

This tool checks a photograph for hard hats and safety vests, attributes each
item to a specific person, and — importantly — **distinguishes "not wearing one"
from "cannot tell"**.

## How it works, step by step

1. **Upload a site photograph.**
2. **Run one detection pass** with a PPE-specific YOLOv8 model.
3. **Decode the raw output** and suppress overlapping boxes.
4. **Attribute items to people** by spatial region — hard hats to heads, vests to
   torsos.
5. **Report per person:** hard hat present, missing, or unclear; vest present,
   missing, or unclear.

## The model or algorithm

### Why an existing detector could not be reused

Nearly every other vision feature in this app reuses the 601-class OIV7
detector. This one could not, and the docstring records that the check was made
rather than assumed: OIV7 has a generic **`Helmet`** class and **no safety-vest
class of any kind**, verified directly against the class list.

So a dedicated model was genuinely necessary — `Hansung-Cho/yolov8-ppe-detection`,
a YOLOv8n fine-tune with **MIT-licensed weights**.

### The positive/negative class design — the important part

The model does not have a `Hardhat` class that either fires or does not. It has
**both** classes explicitly:

```
Hardhat  /  NO-Hardhat
Safety Vest  /  NO-Safety Vest
Mask  /  NO-Mask
```

plus Person, Safety Cone, machinery and vehicle.

This matters more than anything else in the tool. With only a positive class, a
missing hard hat and a **missed detection** produce the same evidence — nothing.
The system cannot tell "this person has no hard hat" from "the model did not see
the hard hat", and reporting non-compliance on the absence of a detection is how
you generate false alarms; reporting compliance on it is how you generate a
dangerous silence.

With an explicit `NO-Hardhat` class, the model states which case it is in. So:

> **Compliance is read from whichever explicit signal fired — never inferred
> from the absence of a positive detection.**

And when neither fires, the answer is **`unclear`**, not a guess.

### The failure that produced that rule

The docstring records it plainly. An initial test on a very low-resolution photo
gave a weak result. Rather than accept it as the model's quality, it was
investigated and found to be a **resolution confound** — re-testing on three
higher-resolution real photographs gave confident results: Hardhat 0.72–0.88,
Safety Vest 0.39–0.69.

And one more check worth noting: the model **correctly avoided claiming "worn"
PPE on a photograph of gear lying on the ground.** Detecting a hard hat and
concluding someone is wearing it is exactly the mistake a naive detect-and-report
pipeline makes, and it is why attribution to a person exists at all.

### Attributing items to people

Detection gives boxes with no relationships. A photo with three workers and two
hard hats needs to know *whose*.

The heuristic is spatial and deliberately simple:

| Item | Region of the person's box | Rule |
|---|---|---|
| Hardhat / NO-Hardhat | top **40%** — the head | item's centre inside that band |
| Safety Vest / NO-Safety Vest | **20% to 100%** — the torso down | same |

Each item is consumed once, so two people cannot both be credited with the same
hard hat, and where several candidates fit, the highest-confidence one wins.

**And it is disclosed as a simplification, not presented as tracking:** there is
no per-person tracking and no pose estimation, so a crowded photograph with
overlapping people can attribute an item to the wrong person. Proper attribution
would use pose keypoints — put the hard hat on the person whose *head keypoint*
it covers — which is considerably more machinery than a bounding-box heuristic.

### Non-maximum suppression

Raw YOLO output contains many overlapping boxes for one object. NMS keeps the
highest-confidence box and discards anything overlapping it by more than the IoU
threshold — **0.45** here. Without it a single hard hat becomes six detections
and the attribution logic gets six candidates for one head.

### The licence and architecture note

This is a good illustration of a recurring problem in this project. The **weights
are MIT**, which is permissive. But running them the normal way — through
`ultralytics.YOLO` — requires the **AGPL-3.0 `ultralytics` package**, which this
project does not otherwise depend on.

The resolution is the same one the OIV7 detector uses: export to ONNX once,
locally, with a dev-only `ultralytics` install that never enters
`requirements*.txt`, and serve the `.onnx` through `onnxruntime`, already a
dependency.

And the export was **verified rather than trusted**: the ONNX output was checked
to match the tested `.pt` output on the same three real photographs before the
file was committed. A conversion step is a place where behaviour silently
changes, and checking it against the thing you already tested is the cheap way to
catch that.

## Why these choices

**Why a three-state output instead of a boolean.** Because the honest states are
three. Present, missing, and unable-to-tell are genuinely different, and
collapsing the third into either of the first two is how a safety tool becomes
untrustworthy — in one direction it cries wolf, in the other it reassures you
about someone it never saw.

**Why hands-on testing before building.** The same discipline recorded elsewhere
in this project after a fire-detection model was rejected on testing. A model
card's numbers are measured on the author's benchmark, not your photographs.

**Why ONNX rather than the ultralytics runtime.** Licence containment, and one
fewer heavy dependency. The pattern — export once locally, ship the artefact,
serve it through a runtime you already have — is reused across the app.

**Why a spatial heuristic rather than pose.** A pose model per person is another
model, more inference time and more failure modes, for a demonstration tool. The
cost is misattribution in crowded frames, which is stated rather than hidden.

## How to read the output

- **`unclear` is not `missing`.** It means neither the positive nor the negative
  class fired for that person, so the photo does not support a verdict. It is
  the most important state in the output.
- **Resolution is the biggest lever.** The recorded failure was a low-resolution
  confound, not a model weakness. A distant or small figure will read `unclear`.
- **Check the attribution in crowded photos.** Overlapping people are exactly the
  case the heuristic can get wrong.
- **Vest confidence runs lower than hard hat** — 0.39–0.69 against 0.72–0.88 in
  the recorded test. Vests vary far more in colour, cut and how much is visible.
- **PPE lying on the ground should not be reported as worn.** It was tested for.
  If you see it happen, the attribution has failed.
- **A person the model did not detect gets no row at all.**

## Limits

- **Two items in practice** — hard hat and vest. The model also has mask classes.
- **No pose estimation and no tracking.** Attribution is a box-region heuristic
  and can misattribute in crowds.
- **Single frame.** No temporal smoothing, so a one-frame miss is a miss.
- **Resolution-sensitive.** Small or distant figures produce `unclear`.
- **Occlusion breaks it** — a worker seen from behind machinery may have no
  visible torso to judge.
- **Not a compliance system.** It reports what one photograph shows. It has no
  record, no identity, no audit trail, and no notion of which PPE this site
  actually requires.
- **The model's training distribution is someone else's site.** Unusual PPE
  colours or styles may not be recognised.

## Likely interview questions

**"Why does the model have NO-Hardhat as a class? Isn't that redundant?"**
It is the most important design decision in the tool. With only a positive class,
"not wearing a hard hat" and "the model missed the hard hat" produce identical
evidence — nothing — and you cannot tell them apart. Reporting non-compliance on
an absent detection generates false alarms; reporting compliance on it generates
a dangerous silence. An explicit negative class means the model states which case
it is in, and when neither fires the answer is `unclear` rather than a guess.

**"How do you know which person a hard hat belongs to?"**
A spatial heuristic: hard hats are matched to the top 40% of a person's box,
vests to the torso band from 20% down, by centre-point containment, with each
item consumed once so two people cannot share one hat. It is a simplification and
I would say so — overlapping people in a crowded frame can be misattributed. The
proper version uses pose keypoints and assigns the hat to whoever's head keypoint
it covers, which is another model and more failure modes than a demonstration
needs.

**"You tested it and got a weak result. Why didn't you reject the model?"**
Because I investigated the weak result instead of accepting it. It turned out to
be a resolution confound — the test photo was very low resolution — not a model
problem. Re-testing on three higher-resolution real photos gave confident
detections, and it also correctly declined to claim PPE was *worn* when the gear
was lying on the ground. Rejecting a model on one bad test is as much a mistake
as adopting one on a good model card.

**"The weights are MIT but the runtime is AGPL. How did you handle that?"**
Exported to ONNX once, locally, with a dev-only `ultralytics` install that never
entered the requirements file, and served the `.onnx` through `onnxruntime` which
was already a dependency. Then verified the ONNX output matched the `.pt` output
on the same three photos before committing the file — a conversion is a place
where behaviour can silently change, and checking it against the thing you
already tested is cheap.

**"Would you deploy this on a real site?"**
Not as a compliance system. It reads one photograph and has no identity, no
record, no audit trail, and no knowledge of what PPE that site requires. As a
supervisor's aid — flagging frames worth a human look — it is useful, provided
`unclear` is surfaced as prominently as `missing`. For anything with consequences
I would add pose-based attribution, temporal smoothing across frames, and a
minimum resolution gate that refuses rather than guesses.
