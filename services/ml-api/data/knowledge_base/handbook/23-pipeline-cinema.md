Chapter 18Pipeline Cinema


> Watch the seven ML stages play out as an animation rather than reading about them. Illustrated characters carry data through each step of the pipeline in turn. Nothing to upload — it is a walkthrough of how the stages fit together.

## At a glance

| | |
|---|---|
| **Also called** | Animated ML Showcase |
| **Model or method** | Visual Demo |
| **What you give it** | No upload needed |
| **Stages** | 4 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/pipeline-cinema` |

## Using the tool

### What this tool does
Watch the **seven ML stages play out as an animation** rather than reading about them.
Illustrated characters carry data through each step of the pipeline in turn —
preprocessing, feature engineering, feature selection, AutoML, Optuna tuning, SHAP
explanation and ensembling. **Nothing to upload** — it's a visual walkthrough of how the
stages fit together.

### Purpose
The pipeline is easier to *get* when you can see data move through it. This is the
explain-it-visually companion to Pipeline Builder: same seven stages, but as a narrated
animation for understanding the flow, not for processing your own data.

### How to use it
1. Open the tool — it starts the animation; there's nothing to configure.
2. Watch each stage hand its data to the next, in order.
3. When you want to run the real thing on your own CSV, go to **Pipeline Builder** (or the
   individual stage tools).

### A worked example
Press play: a character brings in a messy dataset, another scrubs it clean
(preprocessing), the next crafts new columns (feature engineering), the pile is trimmed
(selection), models race (AutoML), the winner is fine-tuned (Optuna), its reasons are
shown (SHAP), and finally several models team up (ensembling) — the whole journey in one
animated pass.

### Reading the result
- Each scene = **one stage**; the order is the real pipeline order.
- It's **conceptual** — the point is the sequence and hand-offs, not real numbers.

### Notes & limits
- **No data in, no model out** — it's a demonstration, not a processing tool.
- For real work on your data, use **Pipeline Builder** (end-to-end) or the per-stage
  tools.

## What problem it solves

Everything else in this part of the book asks you to already know why it exists.
Preprocessing assumes you know why missing values are a problem. AutoML assumes
you know what cross-validation is for. The Pipeline Builder shows seven stages
and expects you to recognise them.

Pipeline Cinema is for the person who does not — a stakeholder, an interviewer
asking what your app does, a student, or you on the first day. It plays the
pipeline as an animation. Illustrated characters carry an orb of data left to
right across a stage, a narrator explains what is happening in ordinary
sentences, and each stage takes its turn.

It is the one tool in the app whose product is understanding rather than output.

## How it works, step by step

**Without a file** it runs as a scripted walkthrough. Four chapters, four
characters, four scenes. Each stage announces itself with a chapter card, the
data orb travels to that stage's position on the track, the narrator delivers
its lines, and the stage marks itself done. You can pause it, stop it, and
click any completed stage to go back and look at it again.

**With a file** it becomes something else entirely: a real run, narrated. Upload
a CSV, pick a target, and the same four scenes play — but now each one **calls
the real backend**, on your data, and the narration is generated from what came
back:

| Stage | Endpoint | What the narrator then says |
|---|---|---|
| Preprocess | `/pipeline-builder/preprocess` | *"Loading your dataset — 891 rows, 12 columns detected."* … *"Imputing missing values: Age (177), Cabin (687)."* … *"Removed 3 duplicate rows."* … *"Fixed skewness in: Fare using log1p."* |
| Feature Eng | `/pipeline-builder/feature-eng` | how many feature columns it started with, and how many new ones it created |
| Feature Select | `/pipeline-builder/feature-select` | how many features were evaluated, which low-signal ones were dropped, how many were kept |
| AutoML | `/pipeline-builder/automl` | how many models were trained on how many rows, each one's score, and the winner |

The output CSV of each stage becomes the input of the next, exactly as in the
Pipeline Builder, so what you are watching is a genuine run with the animation
wrapped around it.

Each scene runs on a timer — roughly 8.4, 8.0, 7.2 and 10 seconds — long enough
to read the narration, and the AutoML scene gets the longest because it has the
most to say.

## The model or algorithm

There is no model of its own. Every number in the narration comes from the
Pipeline Builder's endpoints, described in that chapter. What is worth
explaining here is **the construction**, because building a narrated animation
over a real, slow, failure-prone backend is where the actual engineering is.

### Two clocks that have to agree

There is an animation clock — chapter card in, orb travels, narrator lines
appear, scene holds — and there is a network clock, which is however long the
backend takes. They have nothing to do with each other, and the code has to
reconcile them.

The pattern used is: fire the request, hold the scene for a fixed duration, and
whenever the response lands, swap the narration lines in. If the call is fast,
the scene still plays for its full length so you can read it; if the call is
slow, the animation covers the wait instead of showing a spinner. The animation
is the loading state.

### Pausing something asynchronous

A pause button is easy when everything is on a timer and hard when the code is
`await`-ing. The implementation keeps a paused flag in a ref and wraps every
wait in a `waitPauseable(ms)` helper, so the sequence checks the flag as it goes
rather than sleeping through it. A ref rather than state, because the running
loop needs the value at the moment it checks it, and a state variable captured
in a closure would still hold whatever it was when the loop started. A stopped
flag works the same way, checked at each step so the sequence can unwind
cleanly instead of being killed mid-scene.

### Degrading rather than breaking

Each stage's call is wrapped so that a failure sets a visible error and the
scene still plays with its scripted lines. On free hosting the backend sleeps
and the first request can take thirty seconds or fail outright — a walkthrough
that dies at stage one because a server was cold would be worse than useless.

### Reading the columns without a CSV parser

Between stages the tool shows which columns exist now, so you can watch feature
engineering widen the table and feature selection narrow it. It gets those by
base64-decoding the CSV it just received and splitting the **first line only**.
It never parses the body — it only needs the header, and parsing megabytes of
rows to read one line would be the slowest thing in the tool.

## Why these choices

**Why four stages and not seven.** The four shown are the ones that visibly
transform the *data* — clean it, widen it, narrow it, learn from it. Optuna,
SHAP and ensembling operate on the *model* after the fact, and there is no
visual story of an orb moving through them. *That is my reading of the split
from the code; the file records the list, not the reasoning.* Note the card's
description says "seven ML stages" — the tool animates **four**, and its own
`stat` field correctly says 4.

**Why the file is optional, and why it changes the tool.** The card says
"nothing to upload", and that is true — it plays without one. But the upload bar
exists, and with a file the tool stops being a cartoon and becomes a narrated
run of your own data. Both modes are real; the second is the more interesting
one and is easy to miss.

**Why narration rather than labels.** *"Imputing missing values: Age (177),
Cabin (687)"* teaches what imputation is by showing it happening to columns you
recognise. A label reading "Imputation" teaches nothing to the person who needed
this tool.

**Why the scenes are fixed-length rather than paced by the network.** Because
the point is comprehension, and a scene that flashes past in 200 milliseconds
because the cache was warm is not comprehensible. The timing serves the reader,
not the machine.

## How to read the output

- **Watch the column count between stages.** Feature engineering adding twenty
  columns and feature selection removing thirty is the clearest picture of what
  those two stages are for that the app produces anywhere.
- **The narration is real when you have uploaded a file.** The row counts, the
  imputed columns, the dropped features and the model scores are your data, not
  a script. Without a file, the lines are illustrative.
- **The AutoML scene reports 3-fold cross-validation**, not the 5 used elsewhere
  — the Pipeline Builder's AutoML stage takes a fold count, and the cinema asks
  for a faster one so the scene does not outlast its welcome.
- **A visible error means the backend failed** and the scene fell back to
  scripted lines. The numbers on screen after that are not yours.
- **Click a finished stage to revisit it.** The run does not have to be restarted
  to look again.

## Limits

- **Four stages only.** No Optuna, SHAP or ensembling.
- **The configuration is fixed.** Every stage runs with default settings; you
  cannot choose an imputation strategy or an algorithm. The Pipeline Builder is
  where choices live.
- **It is slow on purpose** — around 34 seconds of scene time plus network. That
  is the right trade for a first-time explanation and the wrong one for anything
  you do repeatedly.
- **Only the CSV header is read** for the column display, so the columns shown
  are names, not a preview of values.
- **The card's description says seven stages.** It animates four.
- **No export.** The run happens, and nothing is saved from it — the trained
  model lives only in the backend's memory under its own id.
- **It teaches this app's pipeline**, which is one reasonable pipeline, not the
  only one.

## Likely interview questions

**"Why build an animated explainer at all? Isn't that decoration?"**
Because the audience for it cannot use the other tools yet. Every other tool
assumes the reader already knows why the stage exists. This one is aimed at the
person deciding whether the pipeline is worth their attention — a stakeholder, an
interviewer, someone new — and for them a narrated run on real data communicates
in thirty seconds what a documentation page does not.

**"How do you animate over an API that takes an unpredictable time?"**
Two independent clocks. The animation runs on fixed scene durations so it stays
readable; the request is fired at the start of the scene and its result is
swapped into the narration whenever it lands. If the call is quick, the scene
still plays out fully; if it is slow, the animation *is* the loading state. And
every call is wrapped so a failure degrades to scripted lines with a visible
error rather than stopping the sequence.

**"Why is the pause flag a ref and not state?"**
Because the running loop reads it at the moment it checks, and a state value
captured in a closure would be whatever it was when the loop started — clicking
pause would have no effect until the next render, which never comes for an
already-running async sequence. A ref is always current. The same applies to the
stop flag.

**"What would you improve?"**
Let the viewer choose the stage configuration and re-run, so it becomes a
teaching tool rather than a fixed demonstration. Show a small before-and-after
sample of actual rows, not just the column names, since seeing a blank cell get
filled is more convincing than being told it was. And add the three missing
stages, even if their scene is a diagram rather than a journey.
