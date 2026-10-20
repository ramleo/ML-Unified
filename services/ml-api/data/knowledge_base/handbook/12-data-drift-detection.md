Chapter 8Data Drift Detection


> Check whether live data has drifted away from what your model was trained on. Upload a new production batch and compare it against the training baseline: PSI, KS test and distribution histograms for numeric columns, category frequency shifts for categoricals. A trend sparkline tracks the drift score across successive batches.

## At a glance

| | |
|---|---|
| **Also called** | Monitor Production Data |
| **Model or method** | Statistical tests |
| **What you give it** | Trained model + batch CSV |
| **+ KS Test** | PSI |
| **Where it runs** | On the server |
| **Find it at** | `/tools/drift` |

## Using the tool

### What this tool does
Check whether **live data has drifted** away from what your model was trained on. Upload
a new production batch and compare it against the training baseline: **PSI**, the **KS
test** and distribution histograms for numeric columns, and **category-frequency shifts**
for categoricals. A **trend sparkline** tracks the drift score across successive batches.

### Purpose
A model silently gets worse when the world it sees stops matching the world it was
trained on — more than a bad metric, that is the single most common cause of production
decay. This tool catches that shift early, before it shows up as bad predictions.

### How to use it
1. Provide the **training baseline** data and a **new production batch** (CSV).
2. Run the comparison.
3. Review per-column drift (PSI / KS, histograms, category shifts) and the overall
   **drift score**; upload later batches to extend the **trend sparkline**.

### A worked example
Your model trained on last year's signups. Upload this month's batch: the **age**
histogram has shifted younger (high PSI) and a new **referral source** category appeared
that wasn't in training. The drift score rises — a signal to retrain before accuracy
slips, even though no accuracy metric has dropped yet.

### Reading the result
- **PSI** — Population Stability Index; higher = more shifted (rule of thumb: >0.2 is
  notable, >0.25 significant).
- **KS test** — whether two numeric distributions differ significantly.
- **Category shifts** — new/disappeared categories and changed frequencies.
- **Trend sparkline** — drift over successive batches, so you see it building.

### Notes & limits
- **Drift ≠ worse accuracy by itself** — it's an early warning that inputs changed; pair
  it with real outcome metrics when you have labels.
- **Compare like with like** — the production batch should have the same columns as the
  baseline.
- **Statistical tests only** — no model is trained here; it's a distribution comparison.

## What problem it solves

A model is trained once and used for years. The world it was trained on does not
stay still.

Prices inflate. A marketing campaign brings in a different kind of customer. A
sensor is recalibrated. An upstream team changes a field from "UK" to "GB". None
of these throws an error — the model keeps returning confident predictions, and
they keep getting quietly worse. By the time anyone notices the business metric
sagging, it has been wrong for months.

The trap is that **you usually cannot measure accuracy in production**, because
the true answer arrives late or never. You predicted a customer would churn; you
find out in ninety days. You predicted fraud; you only learn about the fraud you
caught.

So instead of watching the model's accuracy, this tool watches its **input**. If
the data arriving today no longer looks like the data the model was trained on,
the model is being asked questions outside its experience — and that is
detectable immediately, with no labels at all.

## How it works, step by step

1. **Pick a trained model.** Drift is measured against a specific model's
   baseline, so the model has to exist first.
2. **Upload a batch** — a CSV of the rows the model has been seeing. Optionally
   label it (*"Week 3"*, *"After the pricing change"*).
3. **Choose the reference.** By default a batch is compared with the **previous
   batch**, so you see week-on-week movement. Tick *compare to training* and it
   is compared with the model's original baseline instead.
4. **Every field is tested,** numeric and categorical, by the methods below.
5. **A score is produced per field, and one overall.** The overall score is the
   **maximum** across fields, not the average — see *Why these choices*.
6. **The batch is saved as a version.** Uploading the identical file twice is
   detected by SHA-256 hash and does not create a duplicate version.
7. **A trend line** accumulates across successive batches, which is the view
   that actually matters: one number is noise, a rising line is a story.

## The model or algorithm

### Where the baseline comes from — read this first

This is the most important thing to understand about the tool, and the thing an
interviewer would find fastest.

The training data is **not** kept. What the baseline holds is two numbers per
numeric column — a mean and a standard deviation — recovered from inside the
fitted pipeline itself:

- first choice, the `StandardScaler`'s `mean_` and `scale_`, which are exactly
  the training mean and standard deviation;
- failing that, the `SimpleImputer`'s `statistics_` for the mean, with the
  standard deviation estimated from the schema's recorded range as
  `(max − min) / 6` — the assumption that the observed range spans about six
  standard deviations;
- failing that, the schema range's midpoint.

For categorical fields the baseline is `cat_freq`, a genuine record of how often
each category appeared in training, saved when the model was built. If it is
missing, the reference falls back to a **uniform** distribution over the known
options, which is a much weaker assumption and is labelled as such in the output.

**The consequence.** Every numeric test below compares the batch against a
**normal distribution with the training mean and standard deviation** — not
against the training data. If a training feature was skewed, bimodal or
long-tailed, the reference is wrong in a specific way, and the tool will report
drift for a batch that is in fact perfectly typical. *The code does not record
why it was built this way; my reading is that it is the price of not storing the
training set — the model artefact is all there is, and two numbers can be
recovered from it.* It is a real limitation and worth stating plainly rather
than discovering in a review.

### PSI — Population Stability Index

The industry standard for drift, borrowed from credit risk. Cut the feature into
ten bins, compare the share of rows in each bin now against the share then:

```
PSI = Σ (actual% − expected%) × ln(actual% / expected%)
```

Read it as a symmetric distance between two histograms. Each term is positive
whichever way the shift goes — if a bin gains rows both factors are positive, if
it loses them both are negative — so nothing cancels out.

The bins run from `mean − 3σ` to `mean + 3σ` in ten equal steps, batch values are
clipped into that range, and the expected share of each bin comes from the normal
CDF. Empty bins are floored at 1e-6, because `ln(0)` is undefined and one empty
bin would otherwise take the whole score to infinity.

The thresholds are the conventional ones, and being able to quote them is worth
something:

| PSI | Meaning |
|---|---|
| ** 0.25** | significant shift — act |

For categorical fields the same formula runs over category proportions directly,
with no binning needed.

### The KS test

The Kolmogorov–Smirnov statistic is the largest vertical gap between two
cumulative distributions:

```
KS = max | CDF_batch(x) − CDF_reference(x) |
```

0 means identical, 1 means completely separated. Its appeal is that it makes no
assumption about the *shape* of the distributions — it is a genuinely
non-parametric test.

Except here it cannot be, for the reason above: there is no reference sample to
compare against, so the code **draws 2,000 points from a normal distribution**
with the baseline mean and standard deviation (seeded 42) and compares the batch
against those. So the test is really asking *"is this batch normal, with the
training mean and standard deviation?"* — a stricter and different question than
*"does this batch look like training?"*

The p-value uses the asymptotic Kolmogorov formula with the usual small-sample
correction:

```
n_eff  = √(n₁n₂ / (n₁+n₂))
t      = (n_eff + 0.12 + 0.11/n_eff) × KS
p      = 2 · exp(−2t²)
```

A small p-value means a gap this large would be unlikely by chance. The KS test
runs only on uploaded batches with at least 5 values.

### The drift score

Alongside PSI, each numeric field gets a simpler score — how far the batch mean
has moved, in standard deviations, capped at three:

```
drift_score = min(1, |batch_mean − ref_mean| / (3 × ref_std))
```

So 1.0 means the mean has moved three standard deviations or more. Levels are
**low below 0.35, medium to 0.65, high above**.

For categorical fields it is the mean absolute change in category proportions,
with tighter thresholds — **0.15 and 0.30** — because a 15-point swing in a
category's share is already a lot.

**PSI and the drift score answer different questions,** which is why both are
shown. The drift score only sees the *mean*. A distribution that splits into two
groups either side of the old mean has not moved its average at all and scores
near zero — while PSI, which compares the whole shape, will catch it.

### What else is computed

- **Histograms** — 12 bins, the batch's actual shares against the reference's
  expected shares, scaled to a shared maximum so the two overlay honestly.
- **Percentiles** — the batch's 5th, 25th, 50th, 75th and 95th, against the
  reference's equivalents computed from the normal (`z = ±1.6449, ±0.6745, 0`).
- **Null rate** — the share of rows missing this field. Often the first symptom
  of an upstream break, and it needs no statistics at all.
- **A correlation matrix** across the batch's numeric columns, when there are at
  least two with 5+ values. Relationships between features can break even when
  every individual feature looks unchanged.

## Why these choices

**Why the overall score is the maximum, not the mean.** Averaging hides the
thing you are looking for. One badly broken column among forty healthy ones
averages to nothing; the maximum makes it the headline. The cost is that the
overall number tells you the worst case and nothing about how widespread the
problem is, so the per-field table is where the actual reading happens.

**Why compare to the previous batch by default.** Drift is usually gradual, and
each week looks fine against last week while the year looks nothing like
training. Comparing consecutively catches sudden breaks — a deployment, a schema
change — which is the more urgent kind. The *compare to training* switch exists
for the slow kind, and both views are needed.

**Why high-cardinality categoricals are skipped.** Above 20 options a field is
reported with a drift score of zero and a `high_cardinality` flag. With hundreds
of rare categories, per-category proportions in a small batch are mostly
sampling noise, and PSI would report drift constantly. The tool reports the
number of distinct values seen instead. **This is an honest gap, not a
solution** — a user ID or a postcode column simply is not monitored.

**Why versions are hashed.** Uploading the same file twice is easy, and it would
otherwise create a fake data point on the trend line showing zero drift.

**Why nothing needs labels.** That is the entire point. Input drift is
detectable the moment data arrives, months before the ground truth that would
let you measure accuracy directly.

## How to read the output

- **Start with the trend, not today's number.** A single batch has no context. A
  line climbing over five batches is the finding.
- **PSI over 0.25 on a feature the model relies on** is the alarm worth acting
  on. Cross-reference against SHAP or the feature-importance chart — drift in a
  column the model barely uses matters much less than drift in its top feature.
- **Check the null rate first.** It is the cheapest signal and the most likely
  to indicate a broken pipeline rather than a changed world.
- **Read the histogram overlay, not only the score.** It tells you *how* the
  distribution moved — shifted, spread, or split — which points at the cause.
  A clean shift suggests a units or calibration change; a new second peak
  suggests a new population.
- **`baseline: "schema"`** in the response means the pipeline had no usable
  scaler statistics and the reference is the midpoint of the schema range.
  Treat those numbers as very weak.
- **`cat_baseline: "uniform"`** means the training frequencies were missing and
  every category is being assumed equally likely. Almost every real column will
  look drifted against that.
- **Drift is not decay.** It says the input changed. Whether the model got worse
  is a separate question that needs labels. A robust model can ride out real
  drift; a fragile one degrades on very little.

## Limits

- **The reference is a Gaussian, not the training data.** Two numbers per
  column, assumed normal. Skewed or multi-modal features will be misjudged in
  both directions.
- **The KS test compares against synthetic normal samples**, which makes a
  non-parametric test parametric in practice.
- **No target drift and no concept drift.** This watches inputs only. If the
  *relationship* between inputs and outcome changes while the inputs look
  identical — the classic concept drift — nothing here will see it.
- **High-cardinality categoricals are not monitored at all.**
- **No multivariate drift detection.** Every feature is tested alone. Two
  features whose individual distributions are unchanged but whose joint
  relationship has inverted will pass. The correlation matrix is a partial
  answer and is not scored.
- **The overall score is a maximum**, so it says nothing about breadth.
- **Thresholds are fixed** — 0.35/0.65 numeric, 0.15/0.30 categorical, PSI
  0.10/0.25 — and are not tuned to your data or your batch size. A small batch
  will trip them on noise alone.
- **No alerting.** You have to come and look.
- **History and versions are written to local JSON files**, and the hosting this
  runs on has an ephemeral disk — a restart can take the trend line with it.

## Likely interview questions

**"How do you know a model is degrading if you have no labels?"**
You usually cannot measure it directly, so you monitor its inputs as a proxy. If
the incoming distribution has moved away from what the model was trained on, the
model is extrapolating, and that is measurable the day the data arrives. It is
an early warning, not proof of decay — but with a ninety-day label delay it is
the only signal available.

**"What is PSI, and what counts as bad?"**
A symmetric measure of how far a distribution has moved: bin both, and sum
`(actual − expected) × ln(actual / expected)` over the bins. Under 0.1 is stable,
0.1 to 0.25 warrants investigation, above 0.25 is a significant shift. It comes
from credit risk, where those thresholds are conventional.

**"Data drift versus concept drift?"**
Data drift is `P(X)` changing — the inputs look different. Concept drift is
`P(y|X)` changing — the same inputs now imply a different answer, which is what
happened to spending-pattern models in early 2020. Data drift is detectable
without labels; concept drift is not, which is why it is the more dangerous of
the two. This tool detects the first kind only, and I would say so unprompted.

**"PSI says 0.4 on a feature. What do you do?"**
Not retrain first. Find out whether it is real. Check the null rate and the
histogram shape — a clean shift usually means a units or encoding change
upstream, a new second peak usually means a genuinely new population, and a
distribution that suddenly went uniform usually means a broken join. Then check
whether the model actually uses that feature, via SHAP or importance. Retraining
on data that drifted because of a bug just bakes the bug in.

**"Why the maximum across features rather than the average?"**
Because the average hides exactly what you are looking for — one catastrophic
column among forty healthy ones disappears into the mean. The maximum surfaces
it. The trade-off is that the headline number then tells you the worst case and
nothing about how many columns are affected, so the per-field table has to be
read alongside it.

**"What would you add?"**
Three things, in order. Store real training quantiles rather than a mean and
standard deviation, so the reference stops being a Gaussian assumption. Add
prediction drift — the distribution of the model's own outputs — which is nearly
free and catches things input monitoring misses. And add alerting, because a
monitoring tool nobody visits is not monitoring.
