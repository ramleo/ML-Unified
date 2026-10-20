Chapter 13Feature Selection


> Cut a dataset down to the columns that actually carry signal. Four methods — variance threshold, correlation filter (drops anything above 0.9), recursive feature elimination with a Random Forest, and SelectKBest on mutual information — prune redundant columns before training, with a configurable top-K cutoff.

## At a glance

| | |
|---|---|
| **Also called** | Keep Only What Matters |
| **Model or method** | RFE · SelectKBest · Variance |
| **What you give it** | Any CSV |
| **Methods** | 4 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/feature-selection` |

## What problem it solves

Feature Engineering makes columns. This tool takes them away.

That sounds like undoing the work, and it is exactly the point. More columns is
not more information. Past a certain width a model has enough freedom to fit
noise, every extra column dilutes the ones that matter, training slows down, and
the model becomes impossible to explain to anyone. Two columns that say the same
thing are worse than one, because the credit for the signal gets split between
them and neither looks important.

Deciding what to cut is normally a morning of correlation matrices and
`SelectKBest` calls. This tool runs twelve selection methods over your CSV,
shows what each one would drop and **why**, and writes out the narrowed file.

Like the preprocessing and feature-engineering tools, it runs entirely in your
browser. Every statistic below — variance, correlation, mutual information,
the Lasso path, the trees — is computed in TypeScript on your own machine.

## How it works, step by step

The twelve methods are not alternatives you pick between. They are a **funnel**,
and they run in a fixed order, each one seeing only the columns that survived
the ones before it. Every method has its own on/off switch and its own
threshold, so you decide how many gates the data passes through.

| # | Gate | What it removes |
|---|---|---|
| 1 | **Variance threshold** | columns whose variance is below your cutoff — a column that barely changes cannot explain a target that does |
| 2 | **Correlation filter** | of any pair correlating above the threshold, the one with the weaker link to the target |
| 3 | **Top-K** | everything outside the K best by association score |
| 4 | **SelectKBest** | as above, but scored by F-regression, ANOVA F, or the association score |
| 5 | **Kendall's τ** | the weakest by rank correlation |
| 6 | **Chi-squared** | the weakest by a contingency-table χ² |
| 7 | **RFE** | eliminated one at a time, weakest first, until K remain |
| 8 | **Lasso** | those the L1 penalty drives to zero |
| 9 | **Ridge** | those with the smallest L2 weights |
| 10 | **Tree importance** | those the trees never split on |
| 11 | **Forward selection** | everything not picked by a greedy forward pass |
| 12 | **Exhaustive search** | everything not in the best-scoring subset |

Then the tool lists every column with the exact reason it was dropped — *"low
variance"*, *"high corr"*, *"RFE r3"*, *"Lasso=0"* — and offers the narrowed CSV.
Alongside the funnel it can also run four **projection** methods: PCA, UMAP,
Factor Analysis and LDA. Those do not select columns, they build new ones; more
on the difference below.

## The model or algorithm

### The association score — and an important honesty note

Almost every gate ranks columns by a single score the interface calls **mutual
information**. Here is what it actually computes:

```
score = −0.5 × log(1 − r²)
```

where `r` is the Pearson correlation with the target.

That formula is real: it is the exact mutual information between two variables
**if you assume they are jointly Gaussian**. It is also the reason the number
behaves the way it does — it goes to zero when `r` is zero and to infinity as
`|r|` approaches one.

But it inherits Pearson's blind spot completely. True mutual information detects
*any* dependence, including a U-shape or a threshold effect. This score detects
**only linear dependence**. A feature that is a perfect parabola of the target
scores zero here, and a genuine mutual-information estimator would score it very
high. *The code does not say why this approximation was chosen; my reading is
that a real MI estimator needs binning or a nearest-neighbour method, both far
slower in a browser and both needing parameters of their own.* Either way, read
the score as "linear association", not as mutual information.

When no target column is chosen, the score falls back to the column's variance.

### The filter methods

**Variance threshold.** Compute each column's variance, drop what falls below
the cutoff. A constant column has variance zero and is pure dead weight. Note
this is scale-dependent — a column measured in millimetres has a thousand times
the variance of the same column in metres — so it is only meaningful on data
that has been standardised, or with a cutoff you have chosen for that column's
units.

**Correlation filter.** For every pair of surviving columns, if `|r|` is at or
above your threshold, one of them goes. The choice of which is the useful part:
the tool keeps whichever has the **stronger association with the target** and
drops the other, rather than dropping arbitrarily or by column order.

**F-regression.** The F statistic for a linear fit, `r²(n−2)/(1−r²)`, which is
what scikit-learn's `f_regression` computes. It is a monotonic function of `r²`,
so it ranks identically to correlation — what it adds is a scale that accounts
for sample size.

**ANOVA F (`f_classif`).** For a categorical target: group the feature's values
by class, then compare the variance *between* the group means with the variance
*within* the groups. A big ratio means the classes separate along this feature.
This is the right test when the target is categorical and the feature is
continuous, and it is genuinely different from correlation.

**Kendall's τ.** A *rank* correlation. Take every pair of rows and ask whether
the feature and the target move the same way; τ is (concordant − discordant)
pairs over the total. Because it only uses order, it catches any monotonic
relationship, not just a straight-line one, and it is unbothered by outliers.
The cost is that it compares every pair, which is O(n²) — the implementation
caps it at the first **500 rows** for that reason.

**Chi-squared.** Cuts the feature into four bins at its quartiles, cross-tabulates
those bins against the target's classes, and sums `(observed − expected)² /
expected` over the table. Large means the feature's distribution changes with
the class. Worth knowing that this differs from scikit-learn's `chi2`, which
requires non-negative features and does not bin — the binning here is what lets
it accept a continuous feature at all, and it costs some resolution.

### The embedded methods

**Lasso.** Linear regression with an L1 penalty on the coefficients. The
distinctive property of L1 is that it drives weak coefficients to **exactly
zero** rather than merely small, so it selects as it fits. The implementation is
coordinate descent with soft thresholding — cycle through the coefficients, and
for each one compute what it would be with the others held fixed, then pull it
toward zero by `alpha` and clip it there if it crosses:

```
w[j] = ρ > α  ?  ρ − α
     : ρ 

## Limits

- **The association score is linear.** A non-linear relationship is invisible to
  it, and to almost every gate that uses it. This is the single most important
  limitation in the tool.
- **Only numeric columns are candidates.** Categorical columns pass through
  untouched — they are never scored and never dropped, so a useless text column
  survives everything.
- **The order is fixed.** Gates apply in the listed sequence, and the result
  depends on it.
- **Everything is fit on the whole file.** As with the other browser tools, if
  you split this narrowed CSV for training afterwards, the selection has already
  seen your test rows. Feature selection performed on all the data before a split
  is a well-known way to produce an optimistic score — the honest version runs
  inside the cross-validation loop.
- **"Trees" are stumps, "RFE" does not refit, "mutual information" is a
  Gaussian approximation.** All three are reasonable fast versions. None is the
  textbook algorithm the name implies.
- **Exhaustive search stops being exhaustive above 15 columns** and quietly
  becomes forward selection.
- **Sampling caps** mean Lasso, Ridge, Kendall and the trees see at most 500 or
  1,000 rows.
- **No stability check.** Selection on a resample can give a different answer,
  and the tool runs once.

## Likely interview questions

**"Why remove features at all? Won't the model just ignore the useless ones?"**
A tree will mostly ignore them, but not for free — every useless column is a
candidate at every split, so it costs training time and adds a chance of a
spurious split, which is worse on small data. A linear or distance-based model
does not ignore them at all. And beyond accuracy there is inference cost, the
number of fields a production system has to collect and validate, and whether a
human can read the explanation.

**"Filter, wrapper, embedded — what's the difference?"**
A filter scores each feature against the target with a statistic and never
trains a model: variance, correlation, ANOVA F, χ². Cheap and model-agnostic. A
wrapper trains a model on subsets and uses its score to choose: RFE, forward
selection, exhaustive search. Expensive and tailored to that model. Embedded
methods select as part of fitting: Lasso's L1 penalty is the classic. This tool
has all three families, which is why the funnel has twelve stages.

**"Why does Lasso zero coefficients when Ridge doesn't?"**
The shape of the penalty. The L1 constraint region is a diamond with corners on
the axes, and the corners are where a coefficient is exactly zero — an ellipse of
constant error is likely to first touch it at a corner. The L2 region is a
circle with no corners, so the optimum lands with all coefficients small but
non-zero. That is why Lasso selects and Ridge only shrinks.

**"Two features correlate at 0.95. Which do you drop?"**
By default the one with the weaker link to the target, which is what this tool
does. But I would check first whether they are actually the same measurement
twice or two different things that happen to move together in this sample —
because if it is the latter, the correlation may not hold in production, and
dropping one loses real information. I would also check which is cheaper or more
reliable to collect.

**"Is feature selection before cross-validation a problem?"**
Yes, and it is the classic mistake. If you select features using the whole
dataset and then cross-validate, the selection has already seen the validation
folds, and the reported score is optimistic — sometimes dramatically so on wide,
short data, where you can get a respectable score selecting from pure noise. The
correct version puts selection inside the fold. This tool operates on a whole
file, so I would treat its output as exploration and, for a model I intended to
deploy, put the same steps in a pipeline.

**"What does PCA cost you?"**
Interpretability, mostly. A principal component is a weighted mix of every
original column, so "component 3 is important" tells a stakeholder nothing.
It also assumes the interesting structure lies along high-variance directions,
which is not always true — a low-variance feature can be the one that separates
your classes, and unsupervised PCA will happily discard it. LDA exists precisely
because of that.
