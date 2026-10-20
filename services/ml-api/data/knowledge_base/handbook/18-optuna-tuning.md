Chapter 14Optuna Tuning


> Squeeze more out of the model AutoML picked. A TPE sampler runs up to 30 trials searching for better hyperparameters. It runs after model selection rather than before, so tuning can never inflate the score that won the competition in the first place.

## At a glance

| | |
|---|---|
| **Also called** | Post-Winner Hyperparameter Search |
| **Model or method** | TPE Sampler · 5-fold CV |
| **What you give it** | AutoML winner |
| **Max Trials** | 30 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/optuna` |

## Using the tool

### What this tool does
Squeeze more out of the model AutoML picked. A **TPE sampler** runs up to **30 trials**
searching for better hyperparameters, scored by **5-fold cross-validation**. It runs
**after** model selection, not before — so tuning can never inflate the score that won
the competition in the first place.

### Purpose
Every model has dials (tree depth, learning rate, regularisation) that change its
accuracy. Trying combinations by hand is slow and biased; Optuna searches them
intelligently — each trial informed by the last — to find a stronger setting than the
defaults.

### How to use it
1. Start from the **AutoML winner** (tuning runs on whichever model won).
2. Launch **Optuna tuning** — it runs up to 30 cross-validated trials.
3. Compare the **tuned score** to the untuned winner and keep it if it's better.

### A worked example
AutoML picks LightGBM at F1 0.82. Optuna runs 30 trials varying \`num_leaves\`,
\`learning_rate\` and \`min_child_samples\`, each scored by 5-fold CV, and lands on a
setting at F1 0.85. Because it ran after selection, that 0.85 is an honest improvement,
not a number that was tuned *to* win.

### Reading the result
- **Best trial** — the hyperparameters that scored highest on cross-validation.
- **Tuned vs untuned** — the gain over the default winner; small or zero gains are
  normal and still honest.
- **TPE sampler** — focuses trials on promising regions instead of random guessing.

### Notes & limits
- **Runs after model selection on purpose** — tuning before choosing would let a model
  "win" just because it was tuned, which this avoids.
- **Up to 30 trials** — more would cost more time for diminishing returns on a demo.
- **Cross-validated** — the reported gain reflects generalisation, not one lucky split.

## What problem it solves

Every model has knobs that are not learned from the data. How many trees. How
deep. How fast to learn. Nobody hands you those; the library ships defaults, and
the defaults are a compromise chosen to be inoffensive across every dataset in
the world rather than good on yours.

Turning the knobs by hand means guessing, retraining, comparing, guessing again.
Grid search automates the guessing but scales terribly — five knobs with five
values each is 3,125 full training runs. Random search is better than its
reputation but still learns nothing from the trials it has already run.

This tool runs a search that **learns as it goes**: each trial's result informs
where the next trial looks. It runs on the model AutoML already picked, and it
runs *after* that pick — which is a deliberate ordering, and the most defensible
thing about the design.

## How it works, step by step

**1 — Get a winner first.** The tool uploads your CSV, runs the AutoML
competition, and finds the best algorithm. Tuning starts from there.

**2 — Set up a study.** An Optuna *study* is the search; a *trial* is one
candidate configuration and its score. The direction is always **maximize** —
error metrics like MAE and RMSE are fed in as their negated scikit-learn scorers,
so "higher is better" holds uniformly and the search logic never needs a special
case.

**3 — Suggest a configuration.** The sampler proposes values for every knob in
the winning algorithm's search space.

**4 — Score it.** A fresh pipeline is built — same `ColumnTransformer`
preprocessing, the candidate estimator on the end — and cross-validated on the
same folds. The mean fold score is the trial's value.

**5 — Repeat.** Ten to two hundred times, chosen with a slider. (The tool's card
says "30 Max Trials", which is the cap in the AutoML wizard's tuning step; the
standalone Optuna tool goes to 200.) Progress streams back trial by trial, so
you watch the best score improve live.

**6 — Report.** The best parameters, the best score, the full trial history, and
a **parameter importance** breakdown showing which knobs actually mattered.

**7 — Refit.** A new estimator is constructed with the winning parameters and
trained on the training split, and every headline metric is measured on the
held-out test set as usual.

## The model or algorithm

**TPE — Tree-structured Parzen Estimator** — is the default sampler, and it is
worth being able to explain properly, because "Bayesian optimisation" as an
answer stops one question short.

Standard Bayesian optimisation models `p(score | parameters)` — fit a surrogate,
usually a Gaussian process, and pick the point where it predicts well. TPE turns
the problem around and models `p(parameters | score)` instead.

Here is the mechanism. After some trials, sort them by score and split at a
quantile — the good ones and the rest. Now fit two probability densities over
the parameter space:

- **l(x)** — the density of parameter values among the *good* trials.
- **g(x)** — the density among the *rest*.

Both are Parzen estimators: kernel density estimates, a small bump placed on
each observed value and summed. Then, to choose the next configuration, sample
many candidates and pick the one maximising the ratio **l(x) / g(x)** — the point
most likely under the good distribution and least likely under the bad one.

Why this is a good idea in practice: fitting two densities is cheap and scales
linearly in the number of trials, where a Gaussian process is cubic. It handles
categorical and integer parameters natively, which Gaussian processes do not. And
the "tree-structured" part means it handles *conditional* parameters — a knob
that only exists when another knob has a particular value — which matters for
real hyperparameter spaces.

The configuration used here is `TPESampler(seed=42, multivariate=True,
n_startup_trials=10)`:

- **`n_startup_trials=10`** — the first ten trials are random. With fewer than
  ten observations the two densities are noise, and the search would commit to a
  region on almost no evidence.
- **`multivariate=True`** — model the parameters *jointly* rather than one at a
  time. The default independent TPE treats learning rate and tree count as
  separate one-dimensional problems, which misses the fact that a good learning
  rate depends on how many trees you are going to build. Joint modelling is
  slower per trial and better at finding correlated optima.
- **`seed=42`** — the search is reproducible.

**The alternative sampler: QMC (Sobol).** Quasi-Monte Carlo does not learn at
all. It lays down a low-discrepancy sequence — points that cover the space far
more evenly than uniform random, which clumps and leaves gaps. Sobol is useful
for two things: a genuinely unbiased survey of the whole space, and
parallelism, since no point depends on any other's result. It is offered as the
second option for exactly that reason.

**The search spaces.** Each algorithm gets a space written for it:

| Algorithm | Knobs searched |
|---|---|
| **Random Forest** | `n_estimators` 50–300, `max_depth` ∈ {None, 5, 10, 15, 20}, `min_samples_split` 2–10, `min_samples_leaf` 1–4, `max_features` ∈ {sqrt, log2} |
| **XGBoost** | `n_estimators` 50–500, `max_depth` 3–12, `learning_rate` 0.005–0.3 (log), `subsample` 0.5–1.0, `colsample_bytree` 0.5–1.0, `min_child_weight` 1–10, `gamma` 0–5, `reg_alpha` 0–5, `reg_lambda` 0.1–5 |
| **LightGBM** | `n_estimators` 50–500, `num_leaves` 20–200, `learning_rate` 0.005–0.3 (log), `subsample` 0.5–1.0, `colsample_bytree` 0.5–1.0, `min_child_samples` 5–100, `reg_alpha` 0–5, `reg_lambda` 0–5 |
| **CatBoost** | `iterations` 50–400, `learning_rate` 0.01–0.3 (log), `depth` 4–10, `l2_leaf_reg` 1–10 |

**Learning rate is sampled logarithmically** (`log=True`). This is not a detail.
On a linear scale between 0.005 and 0.3, roughly 98% of the range sits above
0.05 — the search would almost never try a small learning rate. On a log scale,
0.005–0.05 and 0.05–0.3 get comparable attention, which matches how the parameter
actually behaves: the difference between 0.01 and 0.02 matters as much as the
difference between 0.1 and 0.2.

**Parameter importance.** After the study finishes, `optuna.importance` reports
how much of the variation in scores each parameter explains — fANOVA by default,
which fits a random forest over the trial history and decomposes the variance.
This is often the most useful output in the whole run: it tells you which three
knobs to keep and which five to stop searching next time.

## Why these choices

**Why tuning runs after selection, not before.** This is the design decision the
tool is built around. If every candidate algorithm were tuned before the
competition, the winner's score would include the benefit of that tuning — and
since tuning searches for the best cross-validation score, that best score is
optimistically biased by construction. Selecting on it means picking whichever
algorithm was luckiest under search, not whichever is best. Running tuning
afterwards keeps the competition scores comparable and untouched.

The cost of the ordering is honest too: an algorithm that is mediocre at defaults
but excellent when tuned will never get the chance. Random Forest is fairly
robust to its defaults; XGBoost and LightGBM are much more sensitive, so this
ordering quietly disadvantages them. *That is my reading of the trade-off, not a
comment recorded in the code.*

**Why the score is cross-validated rather than measured on a validation split.**
A single split is noisy, and tuning against a noisy signal fits the noise. Five
folds cost five times the compute per trial and give a target worth optimising.

**Why `maximize` with negated error metrics.** One direction means one code path.
Optuna's own convention.

**Why ROC-AUC has its own code path.** scikit-learn 1.4's `roc_auc` scorer uses
`is_classifier()` type detection, which fails for CatBoost and some XGBoost
estimators — the scorer refuses a model that is perfectly capable of producing
probabilities. The workaround calls `cross_val_predict(method="predict_proba")`
and computes the AUC directly. There is a second guard alongside it: if the
minority class has fewer rows than there are folds, some fold will contain a
single class and AUC is undefined, so the fold count is reduced to
`max(2, minority_count)` and a line is logged.

**Why a failing trial is pruned rather than fatal.** A single bad parameter
combination that crashes the fit should cost one trial, not the run. Exceptions
and NaN scores raise `TrialPruned`, the **first** error message is captured, and
if *every* trial fails the run ends with a `RuntimeError` quoting that first
cause and suggesting a different metric. That is the difference between "all 30
trials failed" and a message you can act on.

**A note on the pruner.** The study is created with
`MedianPruner(n_startup_trials=5, n_warmup_steps=0)`. Optuna's pruners work by
having the objective report intermediate values and call `should_prune()` — this
objective does neither; it runs a full `cross_val_score` and returns one number.
So in practice **the pruner never fires**, and every trial runs to completion.
It is harmless, but it is not doing what its presence suggests.

**The secondary metric is tracked, not optimised.** If you select one, each trial
also computes it on a cheap 2-fold split and stores it as a trial attribute, so
you can see the trade-off — did the RMSE gains cost you R²? — without letting it
influence the search. The 2-fold split keeps the cost down; it also makes the
secondary number noisier than the primary one, which is the right priority.

## How to read the output

- **The trial history chart** is the real diagnostic. A curve that improves fast
  and then flattens means the search converged and more trials will not help. A
  curve still climbing at the last trial means stop reading and raise the
  budget. A flat line from trial one means the defaults were already at a local
  optimum, or the metric cannot distinguish these configurations.
- **The best score is a cross-validation score,** not a held-out one. It is the
  best of N attempts to maximise it, so it is optimistically biased. The number
  to quote is the test-set metric measured afterwards.
- **Parameter importance is the transferable finding.** If `learning_rate`
  explains 60% of the variance and `reg_alpha` explains 2%, you have learned
  something about the problem that outlives this run.
- **Compare tuned against untuned before believing in the tuning.** A gain of
  half a percent on a cross-validation score with a two-percent fold spread is
  not a gain.
- **Best parameters at the edge of a range** — `max_depth` landing on 12 when 12
  is the maximum — means the range was too narrow and the true optimum is
  outside it.

## Limits

- **Optimistic by construction.** The best of N cross-validation scores is a
  maximum over noise. The more trials, the more the bias. The held-out test score
  is the number that survives scrutiny.
- **Tuning and selection share the folds.** The same cross-validation splits
  choose the algorithm and then tune it, so the tuned score inherits the
  selection's optimism as well as its own.
- **The winning algorithm is fixed.** Tuning cannot discover that a different
  algorithm would have been better once tuned.
- **Only four algorithms have search spaces** — Random Forest, XGBoost, LightGBM
  and CatBoost. Anything else falls through to CatBoost's space in the estimator
  builder, which is not meaningful for, say, a Ridge regression.
- **The pruner is inert**, as described above, so a hopeless configuration
  consumes a full five-fold cross-validation like any other.
- **No time budget.** The control is trial count, not wall-clock, so 200 trials
  on a large dataset can take a very long time with no way to stop it gracefully.
- **One seed.** Reproducible, but you never see how much of the result is the
  seed.
- **The ranges are hand-written and fixed.** They cannot adapt to dataset size,
  and a dataset whose optimum lies outside them will never reach it.

## Likely interview questions

**"How does TPE work? Don't just say Bayesian optimisation."**
It splits the trials into good and bad at a quantile, fits a kernel density over
the parameter values in each group — l(x) for good, g(x) for bad — and picks the
candidate that maximises l(x)/g(x). So it models the parameters given the score,
not the score given the parameters. That makes it cheap, linear in trials rather
than cubic, and naturally able to handle categorical and conditional parameters.

**"Why not grid search?"**
It scales exponentially and it wastes almost all of its budget. Bergstra and
Bengio's result is the one to cite: in most hyperparameter spaces only a few
dimensions matter, and a grid tests the same few values of the important
dimension over and over while varying the unimportant ones. Random search covers
the important dimension better for the same budget, and TPE beats random by
concentrating where the good results already are.

**"Your tuned model scores 0.91 in cross-validation and 0.86 on test. Why the
gap?"**
Because 0.91 is the maximum of many attempts to maximise that exact number, so
it captures the fold noise as well as the signal. 0.86 is a single honest
measurement on data that took no part in either the selection or the tuning.
The gap is the size of the optimism, and it is expected — a *large* gap suggests
too many trials for the dataset's size, or a leak.

**"Why tune after model selection instead of tuning everything?"**
Fairness of the comparison. Tuning inflates a cross-validation score; if only the
tuned candidates are compared, you select on how much the search inflated them.
The honest alternative is to tune every candidate with the same budget and then
compare — which costs N times as much compute. The trade-off I made is that the
competition stays comparable and algorithms sensitive to their defaults are
slightly disadvantaged.

**"What is `multivariate=True` doing?"**
Modelling the parameters jointly instead of independently. Independent TPE
treats learning rate and number of trees as separate problems, and misses that
the best learning rate depends on how many trees will be built. Joint modelling
captures that interaction, at a higher per-trial cost.

**"How would you know when to stop?"**
Look at the best-so-far curve. If it has been flat for a third of the budget,
stop. Better still, use Optuna's built-in early stopping via a callback, or set a
wall-clock timeout — neither of which this tool currently exposes, which is a
fair criticism of it.

**"You have a pruner configured. What does it prune?"**
Nothing, in this implementation — and I would rather say that than imply
otherwise. `MedianPruner` needs the objective to report intermediate values and
check `should_prune()`; this objective runs one `cross_val_score` and returns a
single number, so there is nothing to prune against. Making it real would mean
scoring fold by fold and reporting after each, which would let a clearly bad
configuration be abandoned after two folds instead of five.
