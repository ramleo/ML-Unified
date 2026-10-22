Chapter 17Pipeline Builder


> Run the whole pipeline as one sequence instead of tool by tool. A visual canvas chains all seven stages together — preprocessing, feature engineering, feature selection, AutoML, Optuna tuning, SHAP explanation and ensembling — so a labelled CSV goes in one end and a trained, explained model comes out the other.

## At a glance

| | |
|---|---|
| **Also called** | End-to-End ML Canvas |
| **Model or method** | Full Pipeline |
| **What you give it** | Any labeled CSV |
| **Stages** | 7 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/pipeline-builder` |

## Using the tool

### What this tool does
Run the whole ML pipeline as **one sequence** instead of tool by tool. A visual canvas
chains all seven stages together — **preprocessing → feature engineering → feature
selection → AutoML → Optuna tuning → SHAP explanation → ensembling** — so a labelled CSV
goes in one end and a **trained, explained model** comes out the other.

### Purpose
Each stage exists as its own tool, but real modelling runs them in order and hands one
stage's output to the next. This stitches them into a single flow so you see the end-to-end
path — and get the final model — without manually carrying a CSV between seven tools.

### How to use it
1. **Upload a labelled CSV** and pick the **target** column.
2. The canvas shows the **seven stages** in order; run the pipeline.
3. Each stage hands its output to the next: clean → engineer → select → train → tune →
   explain → ensemble.
4. Read the final model's score and its **SHAP** explanation at the end.

### A worked example
Feed a churn CSV in: preprocessing fills blanks and drops duplicates, feature engineering
adds a tenure×charges interaction, selection prunes to the top features, AutoML picks
LightGBM, Optuna tunes it, SHAP explains it, and ensembling combines the top models — one
run, from raw file to an explained, tuned ensemble.

### Reading the result
- Follow the **canvas** left to right — each node is a stage, and its output feeds the
  next.
- The end carries the **winning/ensembled model**, its score, and the **SHAP** feature
  story.

### Notes & limits
- **Tabular CSV only** (classification or regression), the same scope as the individual
  stage tools.
- **It's the stages combined**, so the same caveats apply (e.g. fit transforms on
  training data for a strict benchmark).
- **Longer than one tool** — it runs seven steps, including optional Optuna trials.

## What problem it solves

Every other tool in this part of the book does one job. Clean the file. Build
features. Cut the useless columns. Train and compare. Tune. Explain.

Used one at a time, each hands you a CSV that you then feed into the next, and
three things go wrong. You lose track of what you did — three files later, was
the outlier removal on or off? You cannot compare — was the score better because
of the feature engineering, or because you changed the imputation at the same
time? And you cannot repeat it — the sequence exists only as a memory and a
folder of downloads.

The Pipeline Builder makes the sequence itself the object. Seven stages on one
canvas, each configured, each showing what it did, running as one chain. A
labelled CSV goes in and a trained, explained model comes out, and the recipe is
visible the whole way.

## How it works, step by step

### The seven stages

They run in this order, and the order is the argument of the whole tool:

| # | Stage | Produces | Consumed by |
|---|---|---|---|
| 1 | **Preprocessing** | a cleaned CSV | everything after |
| 2 | **Feature Engineering** | new columns | everything after |
| 3 | **Feature Selection** | a narrowed column set | AutoML |
| 4 | **AutoML** | a winning algorithm and a leaderboard | Optuna, SHAP, Ensemble |
| 5 | **Optuna** | tuned hyperparameters | Ensemble |
| 6 | **SHAP** | per-feature contributions | display |
| 7 | **Ensemble** | a voting or stacking score | display |

Stages 5, 6 and 7 are **locked until AutoML has run**, because each needs a
winning model to work on. The canvas greys them out rather than letting you
click into a dead end.

Data passes between stages as base64 CSV strings held in a shared pipeline
state — `csvB64` for the raw upload, then `preprocessedCsvB64`, `feCsvB64`,
`fsCsvB64` as each stage rewrites it. Because they are strings rather than file
handles, the whole pipeline survives being written to browser storage and
reopened.

### Three ways to run it

- **Guided** — one stage at a time. Configure, run, look at the result, then
  move on. This is the mode for learning what each stage does to your data.
- **Express** — configure all seven up front, then run the chain in one go, with
  the canvas animating each stage as it executes. This is the mode for the
  fifth time you run it.
- **A/B Compare** — define **two** complete pipelines and run both on the same
  file. This is the mode that answers the question the other tools cannot.

### Code export

At the end, the tool writes out the equivalent **scikit-learn Python** — the
imports for the winning algorithm, the preprocessing, the feature work and the
model with its tuned parameters. The canvas is a way to arrive at a pipeline;
the export is how it leaves and becomes real code someone can review, put in a
repository, and run in production.

## The model or algorithm

There is no new algorithm here. The stages are covered in their own chapters.
What is worth explaining is **what the pipeline object is and why it matters**,
and how the A/B comparison works.

### The pipeline as the unit

In scikit-learn a `Pipeline` is a list of steps where every step but the last is
a transformer with `fit` and `transform`, and the last is an estimator. Calling
`fit` on the pipeline fits each step on the output of the one before.

The reason this is a *concept* and not just a convenience: a pipeline can be
cross-validated as a single object. When you write

```python
cross_val_score(pipeline, X, y, cv=5)
```

scikit-learn refits **every step** inside each fold — the imputer, the scaler,
the encoder, the model — on that fold's training rows only. Do the same steps by
hand before splitting and the imputer's mean, the scaler's standard deviation
and the encoder's categories have all been computed using rows the model is
about to be scored on. The score comes out too high, and you discover it in
production.

That is why the tool is built around a chain rather than a sequence of file
downloads. The chain corresponds to something scikit-learn can hold as one
object; the downloads do not.

**Where this implementation does and does not honour that.** The AutoML stage
builds a real `Pipeline([("pre", preprocessor), ("est", estimator)])` and
cross-validates it, so the preprocessing is refit per fold — correct. But the
Preprocessing, Feature Engineering and Feature Selection stages run **before**
that, over the whole file, and hand the next stage a rewritten CSV. Their
statistics have therefore seen every row. The chain is honest from AutoML
onward, and not before it. *That is my reading of the design from the code, not
a stated intent.*

### Inside the AutoML stage

Sample to 15,000 rows if larger, then for each chosen algorithm build a fresh
pipeline and cross-validate it — `f1_weighted` for classification,
`neg_mean_absolute_error` for regression, with the sign flipped back so higher
is better on the leaderboard. Sort, take the winner, refit on everything,
register it in memory under a `pb_` id so the later stages can find it.

A failing algorithm is scored **−999** and stays on the leaderboard with its
error attached, rather than vanishing or taking the request down.

### The A/B comparison

Both pipelines run over the same decoded dataframe, in sequence:

```
decode → preprocess → feature engineering → feature selection → AutoML
```

Each returns a score and a wall-clock time in milliseconds, and the higher score
wins with the absolute difference reported.

The value here is that **only one thing needs to change between A and B**. Same
file, same target, same folds, same seed. Turn Yeo-Johnson on in B and nothing
else, and the difference in score is attributable to that decision in a way it
never is when you compare two things you ran on different days with different
settings.

One honest detail in the comparison code: if *every* model in a leg fails, the
top of the leaderboard is a −999 entry, and the function logs
*"every model failed — returned 'winner' is not a real comparison outcome"*
rather than pretending. Worth knowing the winner field can be meaningless in
that case.

## Why these choices

**Why this stage order.** Each stage depends on the last being done. Feature
engineering on un-imputed columns propagates the gaps into every derived column.
Feature selection before the features exist cannot see them. Tuning before you
know which algorithm won tunes the wrong one — and worse, tuning every candidate
before the competition inflates the score that decides the competition, which is
covered in the Optuna chapter. SHAP and ensembling both need a fitted model.

**Why three modes rather than one.** They are three different questions.
*Guided* answers "what does this stage do?", *Express* answers "give me the
model", *A/B* answers "was that change worth it?". A single mode would serve one
of those well and the other two badly.

**Why the CSV moves as base64 rather than a file handle.** A `File` object
cannot be serialised, so a refresh would lose the pipeline. Strings can be
written to browser storage, which is what lets the canvas survive a reload —
at the cost of roughly a third more memory than the raw bytes.

**Why code export exists at all.** A visual builder that only produces a model
inside itself is a demo. One that produces the code is a starting point someone
can review in a pull request. It is also the honest admission that a canvas is
for exploring, and production belongs in a repository.

**Why the later stages are locked rather than hidden.** A greyed-out stage tells
you it exists and what it needs. A hidden one teaches nothing.

## How to read the output

- **The stage cards are the record.** Each shows what it changed — rows before
  and after, columns added, features dropped, the winner and its score. Read
  them as a sequence and you have the story of what happened to your data.
- **Watch the row and column counts across stages.** Preprocessing dropping
  40% of the rows or feature engineering tripling the columns is usually not
  what you intended, and it is only visible in the chain view.
- **In A/B, read the difference against the fold spread.** A gap of 0.003
  between two pipelines is not a result. The comparison is only meaningful when
  the difference is bigger than the noise between folds — which the AutoML
  chapter's advice on fold scores applies to directly.
- **A/B also reports time.** A pipeline that scores 0.002 better and takes four
  times as long has lost.
- **A `−999` on a leaderboard** is a failure, not a score. The error is attached.
- **Read the exported code before you trust the pipeline.** It is the clearest
  statement of what the canvas actually built, and the place a mistake in your
  configuration becomes obvious.

## Limits

- **Only AutoML onward is leak-safe.** The first three stages compute their
  statistics over the whole file. For a model you intend to deploy, the
  cleaning, feature building and selection all belong inside the cross-validation
  loop, and here they are not.
- **The stage order is fixed.** You cannot select features before engineering
  them, or clean twice.
- **15,000 rows** is the AutoML stage's ceiling; larger files are sampled.
- **A/B is two, not many.** No grid over pipeline configurations.
- **A/B compares a single cross-validated score.** Two runs on the same seed and
  the same folds — better than comparing across days, but still one measurement
  each, with no repeats and no confidence interval.
- **No branching.** The canvas is a chain, not a graph; you cannot fork a
  dataset down two paths and rejoin them.
- **The exported code covers four algorithms** — Random Forest, XGBoost,
  LightGBM and CatBoost — and falls back to Random Forest for anything else, so
  an exported pipeline whose winner was, say, Ridge will not be the model you
  actually ran.
- **No scheduling and no persistence of the run.** This builds a pipeline; it
  does not operate one.

## Likely interview questions

**"What is a scikit-learn Pipeline and why does it matter?"**
A list of transformers ending in an estimator, treated as one object. It matters
because `fit` is applied step by step *within* whatever data it is given, so
cross-validating a pipeline refits the preprocessing inside each fold. Doing the
same transformations by hand before splitting lets the imputer and scaler see
the validation rows, and the score comes out optimistically high. The pipeline
is the mechanism that makes the split honest.

**"Walk me through your pipeline order and defend it."**
Clean, engineer, select, train, tune, explain, ensemble. Cleaning first because
every later step assumes complete columns. Engineering before selection because
you cannot select a feature that does not exist yet. Selection before training so
the competition is not diluted by noise columns. Tuning after training, never
before, because tuning inflates a cross-validation score and selecting on an
inflated score picks whichever model the search flattered most. Explanation and
ensembling last because both need fitted models.

**"How do you know a change to your pipeline actually helped?"**
Change one thing, hold everything else fixed — same data, same folds, same seed
— and compare. That is what the A/B mode enforces. And then check the difference
against the fold-to-fold variance: if the models swing by two points across
folds, a half-point difference between pipelines is noise, and I would call it a
tie rather than a win.

**"Where does this design leak, if anywhere?"**
The first three stages. They transform the whole file and pass the result on, so
their statistics — imputation means, scaler parameters, selection scores — have
seen every row including whatever ends up in the validation folds. From AutoML
onward it is correct, because that stage builds a real pipeline and
cross-validates it. If I were fixing it, I would make the first three stages
emit *configuration* rather than a rewritten CSV, and have AutoML assemble them
into the pipeline it fits — which is exactly what the code export already
produces on paper.

**"Why export code rather than a saved model file?"**
Because a pickled model is opaque and version-fragile, and nobody can review it.
Code can be read in a pull request, kept in version control, adapted, and run
where the model actually has to live. The canvas is for deciding what the
pipeline should be; the export is how that decision leaves the tool.
