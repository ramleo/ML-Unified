Chapter 12Feature Engineering


> Build new features out of your columns without writing code. Per-column transforms (log1p, sqrt, z-score, min-max, percentile rank, winsorising, outlier and missing flags) plus binning, polynomial and interaction terms, ratios, lags and rolling windows, date extraction and cyclical sin/cos encoding. It all runs in your browser, and the CSV it writes uses whole-file statistics — the transformer that ships inside a trained pipeline is the one that fits on training data only.

## At a glance

| | |
|---|---|
| **Also called** | No-Code Transforms |
| **Model or method** | scikit-learn · pandas |
| **What you give it** | Any CSV |
| **Transforms** | 10+ |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/feature-engineering` |

## What problem it solves

Models learn from the columns you give them. They do not invent new ones.

A gradient-boosted tree can find that high income and low debt together mean
low risk, because it can split on both. It cannot easily learn `debt / income`,
because that ratio is a smooth surface and a tree approximates it with a
staircase of axis-aligned splits — dozens of them, fitted from data, when one
column would have said it exactly. A linear model cannot learn it at all.

Feature engineering is the work of writing that column yourself. It is
consistently the highest-leverage thing you can do to a tabular model, and it is
normally pandas code: a dozen lines per idea, re-run every time the data
changes, and easy to get subtly wrong in a way that inflates your score.

This tool turns it into a form. Pick columns, tick transforms, see the new
columns appear with their names and values, download the widened CSV or send it
to AutoML.

## How it works, step by step

**1 — Profile the columns.** Same analysis as the preprocessing tool: type,
distinct count, missing count, skew for numeric columns, and the top values for
text ones. A column is numeric if fewer than 5% of its non-empty values fail to
parse as a number.

**2 — Choose transforms.** Per-column transforms are picked from a grid; the
cross-column features (interactions, ratios, lags) get their own panels. There
is also an optional AI suggestion step that asks a language model to propose a
transform list per column from a fixed vocabulary — its output is a suggestion
you tick or ignore, not something applied for you.

**3 — Apply, in fourteen passes.** The engine walks a fixed sequence of feature
families. Every new column is **appended**; nothing is overwritten and no
original column is removed. So the output is always at least as wide as the
input, and the original data survives intact.

**4 — Review and export.** The new column names are listed, the widened table is
previewed, and the result is downloadable or handed to AutoML.

## The model or algorithm

There is no model. There is a catalogue of transforms, and the interesting part
is *why each one exists*.

### Per-column numeric transforms

| Transform | What it computes | Why you would want it |
|---|---|---|
| `log1p` | `log(1 + x)` | Compresses a long right tail. Defined at zero, where plain log is not. |
| `sqrt` | `√x` | The same idea, gentler. |
| `zscore` | `(x − mean) / std` | Zero mean, unit variance. |
| `minmax` | `(x − min) / (max − min)` | Rescales to [0, 1]. |
| `percentile` | fraction of values ≤ x | Rank as a number. Immune to outliers and to the shape of the distribution entirely. |
| `outlier_flag` | 1 if \|z\| > 3 | Lets the model treat "this is extreme" as its own fact. |
| `missing_flag` | 1 if the cell was empty | See below — often the most valuable column in the list. |
| `winsor` | clipped to the 1st and 99th percentile | Keeps the row, removes the extremity. |
| `above_mean` | 1 if x > column mean | A crude split, occasionally exactly the signal. |
| `bin_equal` | 5 equal-width bins, 0–4 | Turns a number into a category by value range. |
| `bin_quantile` | 5 equal-count bins, 0–4 | Turns a number into a category by rank, so every bin is equally populated. |

**Why `missing_flag` deserves attention.** Missingness is frequently
informative. A blank `income` on a loan application may mean the applicant
declined to state it, which correlates with the outcome. Impute the gap and that
signal disappears — the model sees a median income and cannot tell it apart from
a real one. Adding the flag *before* imputing keeps both the plausible value and
the fact that it was invented.

**Equal-width versus quantile bins.** Equal-width divides the range into five
equal spans, so a skewed column can put 95% of its rows in bin 0. Quantile bins
divide the *rows* into five equal groups, so every bin is populated but the bin
widths vary. Quantile is usually the better default; equal-width is better when
the absolute value ranges mean something externally.

### Cross-column features

**Interaction terms (`A × B`).** The product of two columns. Trees can
approximate an interaction by splitting on one column inside a branch of the
other, but that costs depth and data. Linear models cannot represent it at all
without being handed the product. If domain knowledge says two things matter
*together* — price and quantity, dose and weight — the product is the column
that says so.

**Polynomial cross-terms.** Given a set of columns, generate every pairwise
product. The brute-force version of the above: use it when you suspect
interactions but do not know which.

**Squares (`A²`).** Lets a linear model bend. A straight line through a curved
relationship underfits everywhere; adding `x²` lets it fit a parabola.

**Ratios (`A / B`), and ratio-with-difference pairs.** Ratios normalise away a
scale that is not the thing you care about: debt-to-income, price per square
metre, clicks per impression. The paired variant emits both `A / B` and `A − B`,
because they encode different questions — *how many times bigger* versus *how
much bigger* — and which one carries the signal is usually an empirical
question. Division guards against a zero denominator (the plain ratio returns
empty; the paired version adds 1e-8).

**Frequency encoding.** A category replaced by how often it occurs. One column
instead of *n*, and rare categories often behave differently from common ones in
ways that are directly useful.

**Row-wise aggregates.** Mean, sum, min, max or standard deviation across a set
of columns *within each row*. Useful when several columns are readings of the
same underlying thing — twelve monthly balances, say — and their level or their
volatility is what matters.

### Time features

**Date extraction.** A timestamp is useless to a tree as a timestamp. Split into
year, month, day, day-of-week, hour and quarter and each part becomes something
splittable — weekday versus weekend, month-end effects, the night shift.

**Cyclical encoding — the one that is genuinely clever.** Hour 23 and hour 0 are
one hour apart. As numbers they are 23 apart, and every model you feed them to
believes the 23. So instead of the number, emit two columns:

```
sin(2π · value / period)
cos(2π · value / period)
```

That places the value on a circle. Hour 23 and hour 0 land next to each other;
December and January land next to each other. Two columns are needed because one
alone is ambiguous — sine has the same value at two points on the circle, and
the cosine resolves which. The period is yours to set: 24 for hours, 12 for
months, 7 for days of the week.

**Lag and difference features.** Given a column to sort by, `x_lag3` is the
value three rows earlier in sorted order, and `x_diff3` is the change since
then. This is how a tabular model is taught about time at all: without a lag
column, each row is an independent observation and yesterday does not exist.

**Rolling window aggregates.** Mean, min, max or standard deviation over the
last *n* rows in sorted order — the local level, or the local volatility. Both
lag and rolling features are computed by ranking the rows on the sort column,
walking the sorted order, and writing the results back to the original row
positions, so the row order of your file is never disturbed.

## Why these choices

**Why appending rather than replacing.** Every transform adds a column and
leaves the original. That means transforms never chain — `log1p` and `zscore`
ticked together give you `x_log1p` and `x_zscore`, both computed from the raw
`x`, not a z-scored log. It also means nothing is ever lost, the output is
inspectable against the input, and a tree model can choose whichever
representation splits best. The cost is width.

**Why the transforms are simple and readable.** Every column's formula is one
line you can check by hand, and the name says what it is (`fare_log1p`,
`age_x_income`, `hour_sin`). Feature engineering fails quietly when nobody can
say what a column contains six months later.

**Why sin/cos rather than one-hot for cyclical values.** One-hot on twelve
months costs twelve columns, learns each month independently, and still does not
know that December is next to January. The sin/cos pair costs two columns and
encodes the adjacency directly. *This is my reading of the trade-off; the code
records the choice, not the argument.*

### Two implementations, and which one is leak-safe

This matters, and the tool's card compresses it into a single sentence that is
worth unpacking.

There are **two** feature-engineering code paths in this application:

**The browser path** (this tool's export). Every statistic — mean, standard
deviation, min, max, quantile, category frequency — is computed **over the whole
file**, because the whole file is what the tool has. If you take the widened CSV
and split it into train and test afterwards, the z-score in the training rows was
computed partly from the test rows.

**The pipeline path** (`FeatureEngineeringTransformer` in the backend). This is a
proper scikit-learn transformer with `fit` and `transform` separated. At `fit`
time it stores what it learned — bin edges from `qcut`/`cut`, the fitted
Yeo-Johnson `PowerTransformer` per column, IQR bounds for outlier flags, the
sorted value array for rank transforms, the minimum date for days-since — and at
`transform` time it *reuses those stored values* rather than recomputing them.
Placed inside the pipeline, it refits on each training fold and applies the
training fold's numbers to the validation fold.

So: **the "fit on training data only" guarantee belongs to the pipeline path.**
The browser export is for exploration and for producing a file to look at. If
the engineered features are going into a model whose score you intend to
believe, they need to be built inside the pipeline.

## How to read the output

- **The new-column list is the deliverable.** Read the names. If you cannot say
  what `age_x_fare_div_pclass` means, it will not survive review.
- **Columns before / after.** Ticking six transforms across ten columns is sixty
  new columns. Polynomial cross-terms on eight columns is twenty-eight more.
  Width grows faster than people expect.
- **Check for near-duplicates.** `zscore` and `minmax` of the same column are
  perfectly correlated — they are the same information twice. Only one belongs
  in the model.
- **Empty values in a new column are meaningful.** A lag column is empty for the
  first *n* rows; a rolling column for the first *n − 1*; a ratio is empty
  wherever the denominator was zero.
- **Test the features, do not admire them.** Run AutoML before and after. If the
  score does not move, the features are not carrying signal, however clever they
  look.

## Limits

- **Whole-file statistics in the browser path** — the leakage point above.
- **No feature selection.** Nothing here removes a useless column. Sixty new
  features means sixty, including the correlated and the constant. The Feature
  Selection tool is the other half of this job.
- **Transforms do not chain.** All per-column transforms read the raw column.
- **Interaction and polynomial terms are pairwise only** — no three-way products.
- **Lag and rolling features assume a single series.** There is no group-by, so
  running them on a file containing several customers will happily lag across the
  boundary from one customer into the next and produce nonsense.
- **Date parsing uses the browser's `Date`.** Ambiguous and non-ISO formats
  parse differently in different browsers, and an unparseable value becomes
  empty rather than an error.
- **Cyclical encoding needs the right period,** and there is no check that the
  column's values actually span it.
- **Everything is in memory** — the file-size ceiling is the browser's.
- **The AI suggestion step is a suggestion.** It has seen the column names and
  profile, not the target, so it cannot know what is predictive.

## Likely interview questions

**"Give me a concrete example of a feature that beat the model."**
Debt-to-income. Both columns are already there, and a tree can approximate the
ratio with a staircase of axis-aligned splits — but it needs depth and rows to do
it, and it will still generalise worse than the single column that states the
ratio exactly. One line of feature engineering buys what several levels of tree
depth were spending capacity on.

**"Why sin and cos for an hour of the day? Why two columns?"**
Because the raw number puts hour 23 and hour 0 twenty-three apart when they are
one apart. Mapping to a circle fixes the distance. Two columns because a single
sine is ambiguous — the same value occurs at two points on the circle — and the
cosine disambiguates. It costs two columns instead of twenty-four for one-hot,
and unlike one-hot it actually encodes adjacency.

**"When does feature engineering not help?"**
When the model can already represent the relationship. Deep gradient-boosted
trees on a large dataset will find most monotonic interactions on their own, and
adding hand-made versions mostly adds correlated columns and variance. It helps
most with linear models, with small datasets where the model cannot afford to
learn the structure from data, and wherever domain knowledge encodes something
the data alone does not contain.

**"You have 60 new features and 500 rows. What is the problem?"**
The curse of dimensionality: with more features than the data can support, the
model has enough freedom to fit noise, and every added column dilutes the signal
in the ones that matter. I would follow this with feature selection, or a model
with strong regularisation, and I would compare against the un-engineered
baseline honestly rather than assuming more columns is better.

**"How do you keep feature engineering from leaking?"**
Fit it on training data only, and apply the stored parameters everywhere else —
which in scikit-learn means writing it as a transformer with `fit` and
`transform` separated and putting it inside the pipeline, so it refits per fold.
That is what the backend transformer in this app does; it stores its bin edges,
Yeo-Johnson lambdas, IQR bounds and rank arrays at fit time. The browser export
in this tool computes over the whole file, which is fine for exploration and not
fine for a model you intend to trust — and I would rather state that distinction
than let the two be confused.

**"Should you engineer features before or after imputation?"**
Add the missing-flag before, because imputation destroys the information it
records. Do value-based transforms after, because they need a value to transform.
That ordering is a real decision and the pipeline has to encode it explicitly —
it will not fall out of the tooling by itself.
