Chapter 9Data Preprocessing


> Clean a messy CSV before you train on it. Deduplicate rows, fill missing values with 8 numeric strategies (mean, median, KNN, MICE, forward or backward fill, a constant, or drop the row) or 5 categorical ones, strip outliers with the 1.5 × IQR rule, and correct skew with a log transform. It all runs in your browser. Download the cleaned file, or send it straight through to AutoML.

## At a glance

| | |
|---|---|
| **Also called** | Clean Before You Train |
| **Model or method** | SimpleImputer · KNN · MICE |
| **What you give it** | Any CSV |
| **Steps** | 4 |
| **Where it runs** | In your browser — the file never leaves your machine |
| **Find it at** | `/tools/preprocessing` |

## Using the tool

### What this tool does
Clean a messy CSV before you train on it. **Deduplicate** rows, **fill missing values**
with 8 numeric strategies (mean, median, KNN, MICE, forward or backward fill, a constant,
or drop the row) or 5 categorical ones, **strip outliers** with the 1.5 × IQR rule, and
**correct skew** with a log transform. It all runs in your browser — download the cleaned
file, or send it straight through to AutoML.

### Purpose
Real data arrives dirty: duplicates, blanks, extreme values, lopsided distributions.
Models trained on that learn the mess. Cleaning first is the unglamorous step that most
decides whether a model is any good — this makes it a few clicks.

### How to use it
1. **Upload a CSV.**
2. Apply fixes in order: **deduplicate** → **impute** missing values (pick a strategy per
   column type) → **outliers** (1.5 × IQR) → **skew** (log) as needed.
3. Preview the cleaned data, then **download** it or **send to AutoML**.

### A worked example
A CSV has duplicate rows, blank \`income\` cells, and a few extreme \`age\` values. Dedup
removes the repeats; impute \`income\` with **KNN** (uses similar rows) instead of a flat
mean; the **1.5 × IQR** rule flags the impossible ages; a **log** transform tames the
skewed \`income\`. The cleaned file is ready to train on.

### Reading the result
- **Imputation strategy matters:** mean/median are quick; **KNN/MICE** estimate a missing
  value from related columns and are usually more faithful.
- **1.5 × IQR** marks points far outside the middle 50% of a column as outliers.
- **Log transform** pulls in a long right tail so a skewed column behaves better.

### Notes & limits
- **Clean, then split** for a strict benchmark — imputing on the whole file before
  splitting can leak test information into training.
- **Dropping rows loses data** — prefer imputing unless a row is mostly empty.
- **Tabular CSV only**, runs in your browser.

## What problem it solves

Real spreadsheets are messy. Blank cells, duplicated rows, a column where 3% of
the values are typed as `N/A` and 2% as `unknown`, an income column where one
row reads 40,000,000, a category column stored as text when the model needs
numbers. Every one of those either crashes training or quietly degrades it.

Cleaning that up is the least interesting and most repeated work in machine
learning. This tool does it through a form: look at the file, choose what to do
about each problem, see the before-and-after, and download the cleaned CSV or
send it straight to AutoML.

The thing worth knowing before anything else: **it all runs in your browser.**
The CSV is parsed, analysed, imputed, filtered, encoded and re-serialised in
TypeScript on your own machine. Nothing is uploaded. That is a privacy property
you can demonstrate by opening the network tab, and it is also the tool's main
constraint — everything is bounded by your browser's memory.

## How it works, step by step

**Analysis first.** The file is parsed with a hand-written CSV reader that
handles quoted fields and escaped quotes. Each column is profiled: type,
distinct values, missing count, and for numeric columns the mean, standard
deviation, min, max and skew. A column counts as numeric when **at least 95% of
its non-empty values parse as a number** — a threshold, not a dtype, so a mostly-
numeric column with a few stray `"n/a"` entries is still treated as numeric.

**A quality score** is computed and shown as a single number out of 100:

- start at 100
- subtract `2.5 ×` the percentage of missing cells, capped at 45
- subtract up to 35 in proportion to how many numeric columns are badly skewed
  (|skew| ≥ 1)
- subtract up to 20 in proportion to how many columns have any missing values

It is a rule of thumb for drawing the eye to the worst files, not a statistic.

**Recommendations.** Alongside the score, the tool inspects the profile and
suggests fixes you can apply with one click: drop a column where ≥97% of values
are unique (an ID with no signal); switch to KNN imputation when a numeric
column is more than 15% missing; use frequency or target encoding instead of
one-hot when a text column has more than 30 categories; enable the skew fix;
enable standardisation.

**Then the pipeline runs, in a fixed order.** The order is not cosmetic —
several steps change what the later ones see.

1. **Drop** the columns you unticked.
2. **Deduplicate** — exact whole-row duplicates only, first occurrence kept.
3. **Classify** each remaining column as numeric or categorical by the 95% rule.
   The target column is excluded from every transform that follows.
4. **Impute numeric** missing values.
5. **Impute categorical** missing values.
6. **Remove outliers**, by IQR.
7. **Fix skew**, by log1p.
8. **Encode** the categorical columns.
9. **Standardise** to z-scores.

Then the result is re-profiled so you can see the before-and-after per column,
and offered as a download or handed to AutoML.

## The model or algorithm

There are three pieces of real machinery here. The rest is bookkeeping.

### Imputation

Eight strategies for numbers — mean, median, KNN, MICE, forward fill, backward
fill, constant zero, drop the row — and five for text: most frequent, forward
fill, backward fill, constant `"Unknown"`, drop the row.

Mean and median are one line each. The two that are worth explaining:

**KNN imputation.** To fill a gap in column *c* of row *r*, find the rows that
*do* have a value in *c*, measure how similar each is to row *r*, take the five
most similar, and average their values of *c*.

Similarity is mean squared difference across the other numeric columns, counting
only columns where both rows have a value:

```
distance(r, t) = Σ (r[j] − t[j])² / (number of columns j where both are present)
```

Dividing by the count is what lets rows with different missing patterns be
compared at all — otherwise a row missing four columns would look artificially
close to everything.

**One honest caveat: the columns are not scaled before the distance is
computed.** A salary column in the tens of thousands and an age column in the
tens contribute to the same sum, so salary dominates the distance almost
completely and the "nearest neighbours" are effectively nearest-in-salary. If
your columns have wildly different scales, KNN imputation here is weaker than it
looks.

**MICE.** *Multiple Imputation by Chained Equations*, and the implementation
does the chained-equations part faithfully:

1. Fill every gap with its column mean, so there is a complete matrix to work
   with.
2. For each column with gaps in turn: throw away the current fills for that
   column, fit an ordinary least-squares regression predicting it from all the
   other columns using the rows that were never missing, and predict the gaps.
3. Repeat the whole sweep five times, so each column's estimate improves as the
   others improve around it.

The regression is solved directly: the normal equations are formed and
solved by Gaussian elimination with partial pivoting, with a guard that skips a
pivot smaller than 1e-12 rather than dividing by it. No library, about forty
lines.

**A precise caveat about the name.** The *multiple* in MICE means drawing each
imputed value from a distribution and producing several complete datasets, so
that the uncertainty of the imputation can be propagated into the final
analysis. This implementation takes the regression's point prediction with no
random draw, and produces one dataset. That makes it **iterative regression
imputation** — the same as scikit-learn's `IterativeImputer` with its default
settings, which has the same caveat attached to it. It is deterministic and
reproducible, and it understates uncertainty.

### Outlier removal — the IQR rule

Sort the column. Take the value a quarter of the way up (Q1) and the value three
quarters of the way up (Q3). The gap between them, `IQR = Q3 − Q1`, is where the
middle half of the data lives. Anything below `Q1 − 1.5 × IQR` or above
`Q3 + 1.5 × IQR` is dropped.

Quartiles are used rather than mean and standard deviation because they are
*robust*: one absurd value barely moves a quartile, while it moves the mean and
inflates the standard deviation enough to hide itself. The 1.5 multiplier is
Tukey's convention — on normally distributed data it flags roughly 0.7% of
points.

**Two behaviours to know.** Rows are removed, not values — one wild figure in
one column takes the whole row with it. And the columns are processed one after
another on the progressively shrinking dataset, so the quartiles for the third
column are computed after the first two have already removed rows. Reordering
the columns in your file can therefore change the result.

### Encoding

- **One-hot** — one new 0/1 column per distinct value, sorted alphabetically.
  No information invented, no false ordering, but *n* categories become *n*
  columns.
- **Ordinal** — each category replaced by its alphabetical index. Compact, and
  it tells a linear model that `Chicago (1)` sits between `Boston (0)` and
  `Denver (2)`, which is false. Fine for trees, dangerous elsewhere.
- **Frequency** — each category replaced by how often it occurs, as a fraction.
  One column regardless of cardinality, and often genuinely predictive since
  rare categories tend to behave differently from common ones.
- **Target** — each category replaced by the mean of the target for that
  category, with the overall mean as fallback. Powerful, and the most dangerous
  option in the tool. See *Limits*.

**Standardisation** is the usual z-score, `(x − mean) / std`, applied to every
non-target column that parses as numeric — which after one-hot encoding
includes the 0/1 dummy columns.

**Skew correction** applies `log1p(x)` — that is `log(1 + x)`, which is defined
at zero where plain `log` is not — but only to columns whose skew exceeds 1 *and*
whose minimum is at least 0. Yeo-Johnson, a stronger transform that also
handles negative values, exists in this app — in the pipeline builder's clean
stage and in the backend feature-engineering transformer — but not in this
browser-side tool.

## Why these choices

**Why the browser.** No upload means no privacy question to answer, no file-size
limit on the server, no cost per request, and it works while the backend is
asleep. The cost is that it is bounded by browser memory and single-threaded, and
that it is a second implementation of logic that also exists in Python — two
implementations can drift.

**Why the fixed step order.** Impute before removing outliers, so the outlier
rule sees complete columns. Remove outliers before fixing skew, so a single
extreme value does not dictate the skew statistic. Encode before standardising,
so the numeric columns are all present when the means are computed. Each of
those is defensible; the order is also not configurable, which is a limitation.

**Why 1.5 × IQR and skew > 1.** Both are the textbook conventions. |skew| > 1
is the usual "substantially skewed" line, and 1.5 IQR is Tukey's. Using
conventions means the numbers are explainable to someone who already knows them.

**Why presets.** *Quick Clean* — deduplicate and mean-impute, change nothing
else — gets a file loadable without altering its distributions. *ML Ready* —
KNN imputation, outlier removal, skew fix, one-hot, z-score — is the aggressive
option for tree-free models. Most people want one of those two, and the third
option, *Custom*, exists for everyone else.

## How to read the output

- **Rows before / after.** A large drop means outlier removal or a `drop`
  imputation strategy took more than you expected. Losing 30% of your data to
  clean it is rarely the right trade.
- **Columns before / after, and "OHE columns added".** One-hot on a column with
  200 categories adds 200 columns. If the after-count jumped, check which column
  caused it and switch that one to frequency encoding.
- **Missing count after** should be zero unless you chose `none`.
- **The per-column comparison** shows each distribution before and after. This
  is where you confirm the skew fix actually made a column symmetric rather than
  merely different.
- **The quality score after** is only useful as a direction of travel; it is a
  hand-made formula, not a measurement.

## Limits

- **Statistics are computed over the whole file, and there is no train/test
  split.** Every mean, median, quartile, category frequency and target mean uses
  all the rows. If you split this cleaned file afterwards, the training-side
  statistics already contain information from your test rows. **For target
  encoding this is not a subtlety, it is direct leakage of the label into a
  feature** — with no smoothing and no out-of-fold scheme, a category that
  appears once gets that row's own target value written into its feature. That
  will look wonderful in cross-validation and fail in production. For a model
  you intend to deploy, do the cleaning inside a pipeline that refits per fold —
  which is exactly what the AutoML tool does.
- **Duplicate detection is exact-match only.** Two rows differing by a trailing
  space are two rows.
- **Outlier removal is per column and sequential**, so it depends on column
  order, and it deletes whole rows.
- **KNN imputation ignores column scale** — see above.
- **MICE here is deterministic point imputation**, not multiple imputation.
- **The 95% numeric rule can misclassify** a column, and a postcode or a
  numeric-looking ID will be treated as a number and imputed with a mean.
- **Standardisation is applied to one-hot dummies too**, which is harmless for
  trees, changes the interpretation of coefficients in linear models, and is
  wrong if you were relying on the dummies staying 0/1.
- **The quality score is not calibrated against anything.**
- **Browser memory is the file-size ceiling**, and there is no streaming or
  chunking in the transform path.

## Likely interview questions

**"When would you use median instead of mean to impute?"**
Whenever the column is skewed or has outliers. The mean is dragged towards the
extreme values, so imputing with it pushes every filled cell in the direction of
the tail. The median is unaffected by how extreme the extremes are. My rule:
symmetric column, mean; skewed column, median; and if the missingness is heavy
and the other columns are informative, a model-based imputer instead of either.

**"Why is target encoding dangerous?"**
Because the feature is built from the label. If you compute a category's mean
target using all the rows and then train on those rows, the model can partly read
the answer out of the feature — and for a category with one row, it reads it
exactly. The fixes are out-of-fold encoding (compute each fold's values from the
other folds only) and smoothing towards the global mean in proportion to how
rare the category is. This tool implements neither, so I would only use its
target encoding for exploration, not for a model I intended to trust.

**"Should you remove outliers?"**
Usually not by default. An outlier is either a data error, a rare but real event,
or the actual thing you are trying to predict — and the IQR rule cannot tell
those apart. In fraud detection the outliers *are* the positive class. I would
investigate first, and prefer capping (winsorising) to deleting, because deleting
throws away every other column in that row as well.

**"Does standardisation matter for a random forest?"**
No. A tree splits on `x
