Chapter 11Ensemble Methods


> Combine the strongest models instead of betting on one. Voting (VotingClassifier / VotingRegressor) or stacking with a meta-learner on top of the AutoML winners, which typically reduces variance and generalises better than any single model on its own.

## At a glance

| | |
|---|---|
| **Also called** | Combine Top-N Models |
| **Model or method** | Voting · Stacking |
| **What you give it** | AutoML winners |
| **Strategies** | 2 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/ensemble` |

## Using the tool

### What this tool does
Combine the strongest models instead of betting on one. It builds a **Voting**
(VotingClassifier / VotingRegressor) or **Stacking** ensemble with a meta-learner on top
of the AutoML winners — which typically **reduces variance** and generalises better than
any single model on its own.

### Purpose
Different models make different mistakes. Averaging or stacking them cancels out some of
those independent errors, so the ensemble is usually steadier than its best single
member — the standard way competitions and production systems squeeze out the last bit of
reliable performance.

### How to use it
1. Start from the trained models (the AutoML bake-off winners).
2. Pick **Voting** (combine predictions directly) or **Stacking** (train a meta-learner
   on their outputs).
3. Build the ensemble and compare its score against the best single model.

### A worked example
AutoML leaves you with LightGBM, XGBoost and Random Forest at similar scores. A **Voting**
ensemble of all three often edges past the best one, because where XGBoost slips on a row,
the other two outvote it. **Stacking** can do better still by learning *how much* to trust
each model per case.

### Reading the result
- **Voting** — equal (or weighted) say per model; simple and robust.
- **Stacking** — a meta-learner decides how to weight each base model's output; more
  powerful, slightly more prone to overfitting.
- **Compare to the best single model** — the ensemble is worth it only if it actually
  beats that baseline.

### Notes & limits
- **Not always better.** If one model dominates or the models are highly correlated, an
  ensemble adds cost for little gain — check it against the single-model score.
- **Slower to train and predict** than one model (it runs several).
- **Builds on the AutoML winners** — it combines existing strong models rather than
  training from scratch.

## What problem it solves

AutoML picks a winner. But look at the leaderboard it produces and you will
usually see the top three models within a percentage point of each other — and
each one wrong about *different rows*. Betting everything on the model that
happened to score highest throws away the fact that the others knew things it
did not.

An ensemble keeps all of them and combines their answers. The reason it works is
not that averaging is magic; it is that independent errors partly cancel. If
three models each get 10% of rows wrong but disagree about *which* rows, a
majority vote is wrong only where two of the three fail together — which happens
far less often than 10%.

This chapter covers both halves of that idea as they exist in this app, because
they live in two different places, and it is worth being exact about which does
what.

## How it works, step by step

### On the Ensemble Methods page

The page at `/tools/ensemble` runs a **competition and a diversity check**. You
upload a CSV, pick a target, and tick **at least three** algorithms — the form
refuses fewer, because a two-model spread tells you nothing. It then calls the
same `/train` endpoint the AutoML tool uses, with tuning off, and shows:

- the **winner** and its cross-validation score
- the **spread** — how close the top models are to each other, as a percentage
- a **leaderboard** with each algorithm's score and its **stability**, which is
  how consistent that model was across the five folds
- the winner's full test metrics

What this page does **not** do is build the combined model. It tells you whether
combining is worth doing: if the spread is wide, one model is genuinely better
and an ensemble will mostly drag it down toward the others; if the spread is
narrow and the stabilities differ, you have several comparable but differently-
behaved models, which is exactly the situation an ensemble is for.

### Where the combining actually happens

The voting and stacking maths is a **stage in the Pipeline Builder**, served by
`POST /pipeline/ensemble`. You add the Ensemble stage to a pipeline — it unlocks
only after AutoML has run, along with Optuna and SHAP — choose *voting* or
*stacking*, and it returns the ensemble's score alongside each individual
model's, so you can see whether the combination actually beat its parts.

The steps inside that endpoint:

1. Decode the CSV, split off the target, and sample down to 15,000 rows if the
   file is larger.
2. Fit the preprocessing **once**, up front, and reuse the transformed matrix
   for every model. (See *Why these choices* — this is a deliberate deviation.)
3. Score each chosen model on its own with 5-fold **out-of-fold predictions**,
   and record it. A model that throws is logged, scored −999 and excluded rather
   than taking the whole run down.
4. Combine, by voting or by stacking.
5. Return the ensemble score and every individual score.

## The model or algorithm

### Out-of-fold predictions — the idea both methods rest on

Everything here is built on `cross_val_predict`. Split the data into 5 folds;
for each fold, train on the other four and predict this one. Every row ends up
with a prediction from a model that **never saw that row in training**.

This matters more for ensembles than for anything else in the app. If you
trained a model on all the data and then combined its predictions, those
predictions would be partly memory, and any combination built on top of them
would be fitting to memory rather than to skill. Out-of-fold predictions are the
only honest raw material for an ensemble.

### Voting

**For regression** — take each model's out-of-fold prediction and average them:

```
prediction = mean(model₁, model₂, …, modelₙ)
```

**For classification** — the code prefers **soft voting**: collect every model's
predicted class *probabilities*, average them across models, and take the class
with the highest mean probability.

```
ens_preds = argmax( mean over models of predict_proba )
```

If any model cannot produce probabilities, it falls back to **hard voting** —
each model casts one vote for its predicted class, and the most common wins,
implemented as a `bincount().argmax()` per row.

Soft voting is the better default when it is available, and the reason is worth
being able to say: hard voting throws away confidence. Three models predicting
class A at 0.51, 0.52, 0.53 outvote two predicting class B at 0.99 — even though
the two are nearly certain and the three are nearly coin-flips. Soft voting
averages 0.52 against 0.99 and picks B.

### Stacking

Voting weights every model equally. Stacking **learns** the weights.

- **Level 0.** Each base model is trained on 4 folds and predicts the fifth,
  and those out-of-fold predictions are written into a matrix with one column
  per model. That matrix is the new dataset: *n* rows, one feature per base
  model.
- **Level 1.** A second model — the **meta-learner** — is trained on that
  matrix to predict the original target. Here it is `LogisticRegression`
  (`max_iter=500`) for classification and `Ridge` for regression, and it is
  itself scored by 3-fold cross-validation so the reported number is not the
  meta-model grading its own training data.

The meta-learner can learn things a vote cannot: that model B is reliable except
when model C disagrees, or that model A should carry three times the weight of
the others.

**Why the meta-learner is deliberately simple.** A linear model on top of five
strong non-linear models is the standard recipe. The base models have already
done the hard work of extracting structure; the meta-learner's only job is to
decide how much to trust each of them. Something complex at level 1 would start
fitting the noise in the level-0 predictions, and since those predictions are
highly correlated with each other and with the target, it would overfit fast.

### Where the gain comes from

The textbook decomposition is that a model's error breaks into **bias**
(systematically wrong) and **variance** (sensitive to the particular training
sample). Averaging several models trained differently mostly attacks variance —
the individual quirks partly cancel while the shared signal survives.

That leads to the one rule worth remembering: **an ensemble helps in proportion
to how much its members disagree.** Five copies of the same model average to
that model. Five genuinely different learners — a tree ensemble, a boosted
model, a linear model, a distance-based one — have errors that overlap less, and
that is where the gain is. It is also why the page reports the spread and the
per-fold stability rather than only the winner.

## Why these choices

**Why the preprocessing is fitted once, outside the models.** The comment in the
code is explicit: *"manual voting/stacking avoids sklearn VotingClassifier
type-check issues with XGB/LGB."* `VotingClassifier` runs `is_classifier()` on
its estimators, and that check fails for some XGBoost and LightGBM builds — the
same class of problem that forced a manual ROC-AUC path in the Optuna tuner.
Building the vote by hand sidesteps it.

The cost is real and should be stated: fitting the preprocessing on the whole
matrix before cross-validating means the scaler and encoder have seen every
fold. The fold split is honest for the *models*; it is not honest for the
*preprocessing*. On a standard scaler over a decently sized dataset the effect
is small, but it is a genuine deviation from the strict pipeline discipline the
AutoML tool follows, and it exists for a compatibility reason rather than a
statistical one.

**Why a failing model is excluded rather than fatal.** One algorithm that cannot
fit this data should cost one entry on the leaderboard, not the run. It is
scored −999 so it sorts last and is visibly excluded rather than silently
missing.

**Why at least three models.** With two, "the models agree" and "the models
disagree" are the same observation and there is nothing to average that is not
just a midpoint.

**Why 15,000 rows.** Every model is fitted five times for its own score, and
stacking fits each of them five times again to build the meta-features. On free
hosting that is the ceiling that keeps the request from timing out.

## How to read the output

- **Compare the ensemble score against the best individual score.** That single
  comparison is the whole result. Both are returned together for exactly this
  reason. If the ensemble does not beat its best member, do not ship it — you
  have paid *n* times the inference cost for nothing.
- **A narrow spread is the green light.** Top models within a percent of each
  other, with different stability profiles, is the ensemble's best case.
- **A wide spread is a warning.** If one model is clearly ahead, averaging pulls
  it toward the weaker ones. Consider stacking instead, which can learn to
  mostly ignore them, or just ship the winner.
- **Stability is fold-to-fold consistency.** A model scoring 0.81 with high
  stability is more trustworthy than one scoring 0.83 that swings between 0.71
  and 0.94 — and the swinging one may still be a useful ensemble member,
  because it is clearly making different mistakes.
- **A `−999` score** means that model failed to fit and was excluded. Check the
  server log rather than reading it as a bad score.
- **Remember what the score is.** These are cross-validation numbers, not a
  held-out test. The ensemble's number carries the same mild optimism as any
  other cross-validated figure.

## Limits

- **The page and the combining are separate.** `/tools/ensemble` runs the
  competition and reports diversity; the actual voting or stacking runs as a
  Pipeline Builder stage. The card's mention of `VotingClassifier` and
  `VotingRegressor` describes the concept — the implementation is hand-rolled,
  for the compatibility reason above.
- **Preprocessing is fitted outside the folds** in the ensemble endpoint.
- **Voting is unweighted.** Every model counts the same, however bad. A weighted
  vote is the obvious next step and is not implemented; stacking is the escape
  hatch, since the meta-learner effectively learns the weights.
- **One stacking layer only.** No multi-level stacking, and the meta-learner is
  fixed — Logistic Regression or Ridge, not configurable.
- **The models must already be chosen.** Nothing here searches for a
  *diverse* set; it combines whatever you ticked. Two boosted tree models will
  make a poor pair no matter how good each is.
- **Cost.** An ensemble of five models is five models to serve, five to
  monitor, five to keep from drifting. A one-point gain rarely pays for that.
- **Capped at 15,000 rows.**
- **No calibration.** Soft voting averages raw `predict_proba` outputs, and
  different model families are confident in different ways — a tree ensemble's
  0.9 and a logistic regression's 0.9 do not mean the same thing. Calibrating
  each model first would make the average more principled.

## Likely interview questions

**"Why does an ensemble work?"**
Because the members make different mistakes. Error splits into bias and
variance, and averaging several differently-trained models mostly cancels the
variance while the shared signal survives. The condition is diversity — five
copies of one model average to that model, so the whole thing rests on the
members disagreeing.

**"Bagging, boosting, stacking — distinguish them."**
Bagging trains the same kind of model on bootstrap samples in parallel and
averages, attacking variance; Random Forest is bagging with extra feature
randomness. Boosting trains models in sequence, each one fitting what the last
got wrong, attacking bias; XGBoost, LightGBM and CatBoost are all boosting.
Stacking trains *different* model types in parallel and learns a second model to
combine them. Note that this tool ensembles models that are already ensembles —
a vote over Random Forest, XGBoost and CatBoost is bagging and boosting stacked
under a vote.

**"Soft or hard voting?"**
Soft, when every model can give calibrated probabilities, because hard voting
discards confidence — three models at 0.51 outvote two at 0.99, which is the
wrong answer. Hard voting is the fallback when a model only produces labels.
This implementation tries soft first and falls back on exception, which is the
right order.

**"What's the danger with stacking?"**
Leakage at level 0. If the base models predict rows they were trained on, the
meta-features are partly memorised and the meta-learner learns to trust whoever
memorised hardest — a score that collapses in production. The fix is
out-of-fold predictions, which is what `cross_val_predict` gives you here, and
scoring the meta-learner by its own cross-validation on top.

**"Your ensemble scores 0.847 and your best single model 0.844. Ship it?"**
No. That gap is inside the fold-to-fold noise, and you would be paying five
times the inference cost, five deployments and five drift monitors for it. I
would ship the single model. I would only ensemble for a gain that is both
larger than the fold spread and worth the operational weight — and in latency-
sensitive systems, often not even then.

**"How would you improve this implementation?"**
Three things. Put the preprocessing inside the folds, so the ensemble score is
as clean as AutoML's. Add weighted voting, so a weak member cannot drag the
average as hard as a strong one. And calibrate each model's probabilities before
soft voting, because averaging uncalibrated confidences from different model
families is comparing numbers that do not mean the same thing.
