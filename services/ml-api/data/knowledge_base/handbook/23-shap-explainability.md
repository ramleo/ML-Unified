Chapter 19SHAP Explainability


> See why a model made a particular prediction, not just what it predicted. Every result comes with a SHAP bar chart showing which features pushed it and by how much. Engineered columns are grouped back to the original feature they came from, so you read source influence rather than transform noise.

## At a glance

| | |
|---|---|
| **Also called** | Per-Prediction Feature Impact |
| **Model or method** | SHAP · TreeExplainer |
| **What you give it** | AutoML winner |
| **Chart Per Prediction** | 1 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/shap` |

## Using the tool

### What this tool does
See **why** a model made a particular prediction, not just what it predicted. Every
result comes with a **SHAP bar chart** showing which features pushed the prediction and
by how much. Engineered columns are **grouped back to the original feature** they came
from, so you read source influence rather than transform noise.

### Purpose
A score with no reason is hard to trust or act on. SHAP assigns each feature a signed
contribution to a specific prediction — the standard, math-grounded way to answer "what
drove this result?" — turning a black-box output into something you can explain.

### How to use it
1. Have a trained model + a row to explain (this pairs with the AutoML/prediction flow).
2. Open the **SHAP** view for a prediction.
3. Read the bar chart: bars to one side **pushed the prediction up**, to the other
   **pulled it down**; longer bar = bigger impact.

### A worked example
For a loan-approval prediction, SHAP might show **income (+)** and **clean credit
history (+)** pushing toward approval, while **high existing debt (−)** pulls against
it. If you one-hot-encoded "region," the pieces are grouped back so you see "region"
as one influence, not five noisy fragments.

### Reading the result
- **Direction** — which side of zero a feature's bar sits on (toward / against the
  predicted outcome).
- **Magnitude** — bar length = how much that feature moved this prediction.
- **Grouped features** — engineered/encoded columns are rolled up to their source
  feature so the story is readable.

### Notes & limits
- **Per-prediction, not global.** It explains one result; the same feature can matter
  differently for a different row.
- **Explains the model, not the world.** SHAP shows what the model used — if the model
  learned a spurious pattern, SHAP will faithfully show that too.
- **Tree models** use the exact, fast TreeExplainer.

## What problem it solves

A model says this loan application is a 78% default risk. The next question is
always the same: **why?**

Global feature importance cannot answer it. It tells you that income matters
across the whole dataset; it does not tell you that *this* applicant was pushed
over the line by a short employment history, and that their income was actually
pulling the other way. Those are different questions, and only the second one is
answerable to the person in front of you — or to a regulator.

SHAP gives every single prediction its own breakdown: a starting value, a list
of features, and the exact amount each feature moved the output up or down. The
parts add up to the prediction. That last property is what makes it defensible
rather than merely suggestive.

## How it works, step by step

**1 — Rebuild the row exactly as the model saw it.** The input is reconstructed
the same way `/predict` reconstructs it: missing columns filled from the saved
schema, ID columns blanked, any date field expanded into year / month / day /
day-of-week, values coerced to numbers. If the trained model shipped with a
feature-engineering transformer, that runs too. Getting this wrong is subtle and
fatal — an explanation of a row the model would never have received explains
nothing.

**2 — Split the pipeline.** The saved object is a scikit-learn `Pipeline`. It is
cut into everything-but-the-last-step (the preprocessing) and the last step (the
actual model). The row is pushed through the preprocessing to get the numeric
matrix the model consumes, and the transformed column names are read back out
with `get_feature_names_out()`.

**3 — Pick an explainer.** `TreeExplainer` is tried first. If the model is not a
tree ensemble, `LinearExplainer` is tried. If neither fits, the request fails
with a clear message rather than falling back to something slow and approximate.

**4 — Compute.** SHAP values come back for the single row. There is a second
attempt built in: if the first call raises, the explainer is rebuilt with
`feature_perturbation="interventional"` and a background dataset, which sidesteps
an additivity problem that some Random Forest models hit.

**5 — Untangle the output shape.** Different SHAP versions and different model
types return three different shapes — a list of arrays, one per class; a 3-D
array; or a plain 2-D array. Worse, the 3-D case can be ordered
`(rows, features, classes)` *or* `(classes, rows, features)`. The code
distinguishes them by checking which axis matches the row count, then selects the
slice for the class the model actually predicted. Get this wrong and you present
a confident, correctly-formatted explanation of the wrong class.

**6 — Fold the one-hot columns back up.** The model sees `cat__city_London`;
the user has a field called `city`. Each transformed name is stripped of its
`num__` / `cat__` prefix and matched to an original field either exactly or by
the `field_` prefix, and the values are **summed**. Summing is the right
operation, not averaging — see below.

**7 — Sort and return.** Features are ordered by absolute contribution, so the
biggest movers come first regardless of direction, and returned with the base
value and the predicted class.

## The model or algorithm

**Shapley values** come from cooperative game theory, from Lloyd Shapley in 1953.
The setup: several players cooperate and produce a payout. How much of the payout
does each player deserve?

Shapley's answer is to ask what each player *adds*. Take a coalition of players,
measure what it produces, add one more player, measure again — the difference is
that player's marginal contribution to that coalition. Do it for every possible
coalition, average the results, and you get that player's Shapley value.

Map it onto a prediction. The players are the features. The payout is the model's
output for this row. A "coalition" is a subset of features that the model is
allowed to see, with the rest replaced by their background distribution. A
feature's SHAP value is its average marginal contribution across every possible
subset of the other features.

This allocation is unique. It is the only one satisfying four properties at once:

- **Efficiency** — the contributions sum exactly to the prediction minus the
  base value. This is the additivity that makes the waterfall chart honest.
- **Symmetry** — two features that always contribute identically get identical
  values.
- **Dummy** — a feature that never changes the output gets exactly zero.
- **Additivity** — explanations of an ensemble are the sum of the explanations
  of its members, which is exactly why forests are tractable.

**The cost problem, and why trees are special.** Every subset of *n* features
means 2ⁿ coalitions. Twenty features is a million. Model-agnostic KernelSHAP
handles this by sampling coalitions and fitting a weighted linear model — correct
in expectation, but slow and noisy.

TreeExplainer does not sample. It exploits the structure of a decision tree: a
tree is a set of paths, and each path already encodes exactly which features
were used and in what order. The algorithm pushes all subsets down the tree
simultaneously, tracking the proportion of each subset that flows down each
branch, and computes **exact** Shapley values in time polynomial in the tree
depth and leaf count rather than exponential in the feature count. That is why
this tool is fast enough to explain a prediction while you wait, and why the
answer is exact rather than sampled.

**The base value** is the model's expected output over the background data —
what it would say knowing nothing about this row. The prediction is
`base_value + sum(shap_values)`. For a binary classifier the tree output is a
**log-odds margin, not a probability**, so contributions add up in log-odds
space. A contribution of +0.8 does not mean "+80 percentage points".

**Why sum the one-hot columns.** Shapley values are additive by construction, so
the total credit assigned to the group `city_London`, `city_Paris`,
`city_Tokyo` *is* the credit assigned to `city`. Averaging would divide the real
contribution by the number of categories and make every high-cardinality column
look unimportant.

## Why these choices

**Why SHAP rather than the model's built-in importance.** Impurity importance is
global, unsigned and biased towards high-cardinality columns. It cannot tell you
which direction a feature pushed, and it cannot say anything at all about one
particular prediction. SHAP is per-prediction, signed, and additive.

**Why SHAP rather than LIME.** LIME fits a simple local model around the point
and reports its coefficients. It is faster and model-agnostic, but the
explanation depends on how the neighbourhood was sampled, two runs can disagree,
and the parts do not have to add up to the prediction. SHAP's guarantees are the
reason it survives being questioned. *This comparison is my reading of the
trade-off; the code records the choice, not the argument.*

**Why `check_additivity=False`.** SHAP normally verifies that the contributions
really do sum to the model output, and raises if they do not. That check fails on
some legitimately-loaded pipelines — sparse matrices, externally-trained models —
and the failure is a hard error rather than a warning. Disabling it keeps the
tool working on real uploads. **The cost is real and should be stated plainly:
the one guarantee that would catch a silently wrong explanation has been turned
off.** The interventional-perturbation retry is the partial compensation.

**Why the explainer is imported inside the function rather than at the top of
the file.** The `shap` package is heavy, and importing it at module load would
add several seconds to every cold start on free hosting, including for the
majority of requests that never ask for an explanation.

**Why the two-stage fallback (`TreeExplainer` → `LinearExplainer` → error).**
Both are exact and fast for their model families. The remaining option,
KernelSHAP, is slow enough to time out on a web request and approximate enough to
be misleading — failing with a clear message is more useful than returning a
number nobody should trust.

## How to read the output

- **Start at the base value.** That is the model's default answer before it
  looks at this row.
- **Each bar is a push.** Positive moves the prediction towards the predicted
  class (or upward, for regression); negative pushes away. The length is the
  size of the push.
- **The bars are sorted by size, ignoring sign,** so the two features that
  matter most sit at the top even if they are fighting each other.
- **They add up.** Base value plus every bar equals the model's raw output. If
  you sum them and land somewhere else, something is wrong — and with the
  additivity check disabled, you are the check.
- **Units are the model's output space.** For a binary classifier that is
  log-odds, not percentage points. Compare bars against each other; do not read
  them as probabilities.
- **A large value is not an endorsement.** SHAP describes the model's reasoning.
  If the model learned something silly, SHAP will show you the silly thing
  clearly and confidently. That is the tool working, not failing.

**One honest note about where the real thing lives.** The `/tools/shap` page in
this app trains a model and displays a ranked, colour-coded chart labelled
*SHAP-style Importance* — that chart is the model's **global feature
importance**, not per-prediction Shapley values, and its own label says
"SHAP-style" for that reason. The genuine per-prediction SHAP breakdown described
in this chapter is served by the `/shap/{model_id}` endpoint and appears in the
prediction interface of the ML platform, attached to a specific predicted row.

## Limits

- **Correlated features split the credit.** If height and weight both predict
  the outcome and move together, Shapley values divide the contribution between
  them. Neither looks as important as the pair really is, and dropping one can
  leave the model unchanged. This is a property of the method, not a bug.
- **Tree-path-dependent versus interventional.** The default path-dependent mode
  uses the training-data distribution recorded in the tree's node counts, which
  conditions on the correlations present in the data. The interventional mode
  (used in the fallback) breaks those dependencies and answers a more causal
  question. The two give different numbers for the same row, and this tool may
  use either depending on whether the first attempt succeeded.
- **The additivity check is off** — the failure mode is a plausible-looking
  explanation whose parts do not sum to the prediction.
- **It explains the model, not the world.** SHAP is not causal inference. "Age
  contributed +0.4" means the model used age that way, not that changing the
  person's age would change the outcome.
- **One row at a time.** No global summary plot, no dependence plot, no
  interaction values — all of which SHAP supports and none of which this
  endpoint returns.
- **Tree and linear models only.** No neural networks, no arbitrary pipelines.
- **The background is the training distribution.** Explain a row far outside it
  and the coalitions being averaged over are combinations that never occur in
  reality.

## Likely interview questions

**"Explain SHAP to someone non-technical."**
Several people work on a project together and get a bonus. How much did each
person earn? Look at what the group produces with them and without them, in
every possible combination of colleagues, and average the difference they make.
That average is their fair share. SHAP does exactly that with features instead of
people, and the prediction instead of the bonus.

**"Why is SHAP better than feature importance?"**
Three reasons. It is per-prediction, so it can explain one decision rather than
an average over the dataset. It is signed, so it says which direction a feature
pushed. And it is additive — the parts sum to the prediction, so nothing is
unaccounted for. Impurity importance has none of those and is biased towards
high-cardinality columns as well.

**"Isn't computing Shapley values exponential?"**
For a general model, yes — 2ⁿ coalitions. TreeExplainer avoids it by using the
tree structure: it pushes all subsets down the paths at once and computes exact
values in polynomial time in depth and leaves. That is why the tool restricts
itself to trees and linear models rather than offering the model-agnostic
sampling version.

**"Your SHAP values sum to 3.2 but the model says 96% probability. Explain."**
Different spaces. Tree classifiers output a log-odds margin, and SHAP explains
that margin. Base value plus contributions equals the margin; the probability is
the sigmoid of it. This is the most common misreading of a SHAP chart, and it is
why the bars should be compared with each other rather than read as percentage
points.

**"Two features you know are important show near-zero SHAP. What happened?"**
Most likely they are strongly correlated with each other, so the model uses
whichever it splits on first and the credit is divided — or one is a near-duplicate
and genuinely redundant. Check the correlation matrix, and try dropping one and
retraining. If the score does not move, the model agrees with SHAP.

**"You disabled the additivity check. Isn't that dangerous?"**
Yes, and it was a deliberate trade. The check fails on some valid uploaded
pipelines and takes the whole request down with it. Turning it off keeps the tool
usable at the cost of losing the automatic detection of an inconsistent
explanation. If I were hardening this, I would recompute the sum myself and warn
in the response when it does not match the model's output, rather than leaving
the check simply off.

**"Can I show a customer their SHAP explanation as the reason for a decision?"**
It is a faithful account of *the model's* reasoning, which is usually what
regulation asks for. It is not a causal claim about the customer. And be careful
with the units — a log-odds waterfall is not something to put in front of a
member of the public without translating it first.
