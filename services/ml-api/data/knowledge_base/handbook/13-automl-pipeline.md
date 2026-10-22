Chapter 8AutoML Pipeline


> Upload a CSV and get a trained model without writing any code. Four algorithms — Random Forest, XGBoost, LightGBM and CatBoost — compete on 5-fold cross-validation, and the winner is chosen automatically on F1 for classification or MAE for regression. Optional Optuna tuning and a SHAP explanation then run on whichever model won.

## At a glance

| | |
|---|---|
| **Also called** | 4-Model Competition |
| **Model or method** | RF · XGB · LGB · CatBoost |
| **What you give it** | Any CSV |
| **Models** | 4 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/automl` |

## Using the tool

### What this tool does
Upload a CSV and get a **trained model without writing any code**. Four algorithms —
**Random Forest, XGBoost, LightGBM and CatBoost** — compete on 5-fold cross-validation,
and the winner is chosen automatically (on **F1** for classification, **MAE** for
regression). Optional **Optuna** tuning and a **SHAP** explanation then run on whichever
model won.

### Purpose
Picking an algorithm and tuning it is the slow part of a first model. This runs the
bake-off for you and shows the scoreboard, so you see which model actually fits your
data — and why — instead of guessing.

### How to use it
1. **Upload a CSV** (a header row + the column you want to predict).
2. Choose the **target column**; the tool detects **classification vs regression** from
   it.
3. Run — the four models train and are scored by cross-validation.
4. Review the **leaderboard**, then optionally enable **Optuna tuning** and view the
   **SHAP** explanation of the winner.

### A worked example
Upload a customer-churn CSV with a \`churned\` (yes/no) target. The tool detects
classification, trains all four models, and ranks them by F1 — say LightGBM wins. Turn
on Optuna to squeeze out a better score, then open SHAP to see that "contract length"
and "monthly charges" drove most predictions.

### Reading the result
- **Leaderboard** — each model's cross-validated score; the winner is highlighted.
- **F1 (classification) / MAE (regression)** — the single metric used to pick, so the
  comparison is apples to apples.
- **SHAP** — which features pushed the winner's predictions, and by how much.

### Notes & limits
- **Tabular CSV only** — not images, text or time series.
- **Cross-validation picks the winner**, so the ranking reflects generalisation, not a
  single lucky split.
- **Optuna tuning takes longer** — it's optional; the untuned bake-off is quick.

## What problem it solves

Somebody has a spreadsheet and a question about it. *Which customers will cancel?
What will this house sell for?* Answering that normally means writing code:
load the file, decide whether the question is a classification or a regression
problem, encode the text columns, pick an algorithm, split the data, train,
score, and then wonder whether a different algorithm would have done better.

This tool does all of that from a file upload. You give it a CSV, tell it which
column is the answer, and it hands back a trained model, an honest score, a
ranked list of which columns mattered, and a prediction form you can type into.
The point is not that it beats a careful hand-built model. The point is that it
removes the day of setup work before you can find out whether the data has any
signal in it at all.

## How it works, step by step

**1 — Read the file and guess the question.** The CSV goes to the `/analyze`
endpoint, which reports every column's type, how many distinct values it holds,
and how many are missing. It then guesses the target: *the last column in the
file*. It guesses the task from that column's contents — **classification if the
column is not numeric or has 10 or fewer distinct values, regression
otherwise**. Both guesses are shown as defaults you can change, because both are
crude on purpose: a rule you can see and override is more useful than a clever
one you cannot.

**2 — Build the preprocessing.** Numeric and text columns are separated and
wrapped in a scikit-learn `ColumnTransformer`. Numbers get imputed and scaled;
text gets one-hot encoded. Anything the transformer does not recognise is
dropped (`remainder="drop"`). This whole block becomes step one of a `Pipeline`,
which matters more than it sounds — see *Why these choices*.

**3 — Run the competition.** Every algorithm you ticked is cross-validated on
the same folds, with the same preprocessing, and scored on the same metric. Each
model is fitted five times and scored five times. The full candidate list is
twelve algorithms per task:

| | |
|---|---|
| **Both tasks** | Random Forest, XGBoost, LightGBM, CatBoost, Extra Trees, Decision Tree, KNN, Gradient Boosting |
| **Classification only** | Logistic Regression, SVM, Naive Bayes, AdaBoost |
| **Regression only** | Ridge, Lasso, ElasticNet, SVR |

Five are ticked by default — Random Forest, XGBoost, LightGBM, CatBoost and
Extra Trees. The tool's card on the site says "4-Model Competition", which names
the four the headline is about; the default set is five and the full list is
twelve.

**4 — Pick the winner.** Highest mean cross-validation score for classification;
*lowest* mean absolute error for regression. No tie-breaking rule and no
tolerance band — the top number wins outright.

**5 — Tune, if you asked for it.** Optuna searches the winner's hyperparameters.
This runs *after* the winner is chosen, never before. The Optuna Tuning chapter
covers what happens inside.

**6 — Refit and measure.** The winner is refitted on a fresh 80/20 train/test
split (90/10 for tiny files under ten rows), stratified by class for
classification so both splits keep the same class mix. Every headline number you
see comes from predictions on that held-out 20%, not from the cross-validation.

**7 — Explain.** Feature importances are pulled out of the fitted model, a
learning curve is computed, and a written explanation of why this model won is
generated — by rule first, by a language model if a key is configured.

**8 — Save.** The fitted pipeline, the label encoder, the feature-engineering
transformer and a JSON form schema are written to disk and registered in memory,
which is what makes the prediction form on the results page work. A background
thread copies them to the Hugging Face model repository.

## The model or algorithm

There is no single model here. The mechanism worth understanding is
**k-fold cross-validation**, because it is what makes the comparison fair.

Split the rows into five equal parts. Train on four, score on the fifth. Repeat
five times so every part gets one turn as the scored fold. Average the five
scores. Every row is predicted exactly once, by a model that never saw it during
training — so the average is an estimate of how the algorithm behaves on data it
has not seen, rather than how well it memorised the data it has.

Two details in the implementation matter:

- **The split is stratified for classification** (`StratifiedKFold`), so each
  fold keeps the dataset's class proportions. On a 3%-fraud dataset an unstratified
  fold can easily contain no fraud at all, and the score for that fold is
  meaningless.
- **The folds are identical across algorithms** — same `shuffle=True`, same
  `random_state=42`. If each model got its own random split, some of the score
  difference between them would be split luck rather than model quality.

**Which metric decides.** Class balance is checked first: if the smallest class
is under 20% of the rows, the dataset is treated as imbalanced. That flips two
switches at once — the selection metric becomes **F1-macro** instead of
**F1-weighted**, and every model that supports it gets `class_weight="balanced"`.

F1 is the harmonic mean of precision and recall, so a model cannot score well by
being cautious in one direction. *Weighted* averages the per-class F1 scores in
proportion to how common each class is; *macro* gives every class an equal vote.
On a 97/3 split, weighted F1 is dominated by the majority class and a model that
predicts "not fraud" every time still scores about 0.96. Macro F1 scores that
same model about 0.49, which is the honest answer.

For regression the selection metric is **mean absolute error** — the average
size of the miss, in the units of the target.

**SMOTE.** When the data is imbalanced *and* the smallest class has at least 20
rows in the training split, synthetic minority examples are generated
(`k_neighbors = min(5, minority_count − 1)`). SMOTE picks a minority row, picks
one of its nearest minority neighbours, and creates a new point somewhere on the
line between them. Crucially it sits *inside* an `imblearn` pipeline, so it only
ever runs on the training portion of each fold. Oversampling before the split is
one of the classic ways to produce a beautiful score that means nothing —
copies of the same row end up on both sides of the split.

**Feature importance.** Read straight off the fitted model's
`feature_importances_`, which for tree ensembles is impurity reduction — how
much each split on that column improved the tree's purity, totalled across the
forest. One-hot columns are then summed back to the column they came from
(`city_London`, `city_Paris` → `city`), normalised to percentages, and the top
ten are shown. Without that summing, a text column with fifty categories is
split into fifty individually tiny bars and disappears from the chart.

**Learning curve.** The winner is retrained on 40%, 70% and 100% of the data
with 3-fold cross-validation, and both the training score and the validation
score are plotted. The gap between them is the diagnosis: a wide gap means
overfitting, two low lines together mean underfitting, and the thresholds are
scaled by dataset size (a gap of 0.10 on 150 rows is normal; on 50,000 rows it
is not).

## Why these choices

**Why a `Pipeline` rather than transforming the data first.** This is the single
most important structural decision in the tool. If you impute and scale the
whole file and *then* cross-validate, the scaler has already seen the validation
fold — its mean and standard deviation were computed partly from rows the model
is about to be scored on. The score comes out too high, and you find out in
production. Wrapping preprocessing as step one of the pipeline means
scikit-learn refits it inside every fold, on that fold's training rows only.

**Why gradient boosting dominates the default list.** On tabular data with mixed
types, missing values and non-linear interactions, gradient-boosted trees are
the reliable answer, and XGBoost, LightGBM and CatBoost are three implementations
with genuinely different behaviour — different split-finding, different handling
of categories, different regularisation defaults. Random Forest is in the list
as the stable baseline that rarely wins but rarely embarrasses itself, and Extra
Trees as a cheap, higher-variance-in-splits cousin. *This is my reading of the
selection from the code; the file does not record the reasoning.*

**Why CatBoost specifically.** It handles categorical features with ordered
target statistics rather than one-hot expansion, which is a real advantage on
columns with many categories. Note that in this implementation CatBoost still
receives one-hot-encoded input from the shared `ColumnTransformer`, so it is not
being used at its full strength — the same preprocessing is given to every
competitor to keep the comparison fair, and that fairness costs CatBoost some of
its edge.

**Why the competition is capped at 5,000 rows.** Cross-validating twelve
algorithms five times each on a large file would take longer than anyone will
wait on free hosting. Above 5,000 rows the competition runs on a fixed random
sample (`RandomState(42)`), and only the winner is refitted on the full data.
The trade-off is real: the algorithm that wins on 5,000 rows is not guaranteed to
be the one that would win on 500,000.

**Why `random_state=42` everywhere.** Reproducibility. Run the same file twice
and you get the same winner, the same folds and the same score. The cost is that
you never see how much of the result is seed luck.

## How to read the output

- **The headline score** is on the held-out 20%, not the cross-validation. For
  classification it is F1 (weighted, or macro if the data is imbalanced);
  for regression it is MAE, printed as `±value` in the target's own units.
- **The competition table** shows each algorithm's mean cross-validation score
  and its five individual fold scores. Look at the spread, not just the mean —
  five folds reading 0.81, 0.83, 0.82, 0.80, 0.84 is a stable model; 0.62, 0.91,
  0.55, 0.88, 0.79 is a model whose score is mostly noise, and its "win" is not
  trustworthy.
- **Accuracy is shown but is not what chose the model.** On imbalanced data a
  high accuracy sitting next to a low F1-macro is the expected pattern, not a
  contradiction.
- **ROC-AUC** near 0.5 means the model is guessing; near 1.0 means it separates
  the classes cleanly. It is computed one-vs-rest and macro-averaged for
  multi-class.
- **R² is only displayed when it reaches 0.60.** Below that it is suppressed
  rather than shown as a bad number — worth knowing, because its absence is
  itself information.
- **Feature importance** tells you what the model *used*, which is not the same
  as what *causes* the outcome. A column that is a proxy for the answer will top
  this chart, and that is a warning sign, not a result.
- **The confusion matrix** is where you find out *which* class the model gets
  wrong. A model can hold a respectable F1 while failing completely on the one
  class you actually care about.

## Limits

- **Selection and evaluation share the data.** Twelve models are compared by
  cross-validation, and the winner is then scored on a held-out split — but the
  cross-validation ran on rows that overlap that split. Choosing the maximum of
  twelve noisy scores biases the choice upward. A nested cross-validation would
  measure the whole *procedure* rather than the chosen model; it would also cost
  roughly five times the compute, which is why it is not here.
- **Impurity-based importance is biased** towards high-cardinality and
  continuous columns. Permutation importance or SHAP is the honest version;
  SHAP is available separately in this app.
- **Regression is selected on MAE only.** MAE treats a miss of 100 as ten times
  worse than a miss of 10. If large errors are disproportionately costly, RMSE
  is the right selection metric, and this tool will not choose it for you.
- **Very small classes break the folds.** Fewer than five rows in a class means
  stratified 5-fold cannot give every fold one, and that model's
  cross-validation is skipped with a log line.
- **The competition may run on a sample** — see the 5,000-row cap above.
- **The target guess is positional.** Last column. If your CSV ends with an ID
  column, the default is wrong and the whole run is meaningless. Change it.
- **Any leaked column wins.** Nothing in the tool detects that
  `days_until_cancellation` should not be a feature for predicting cancellation.

## Likely interview questions

**"Why five folds and not ten, or leave-one-out?"**
Five is the standard compromise between the bias of a small training set and the
cost of refitting. Ten folds gives a slightly less biased estimate for roughly
double the compute; leave-one-out is almost unbiased but has high variance and
costs one fit per row. With twelve algorithms in a competition on free hosting,
five is the practical choice.

**"Why does your metric change when the data is imbalanced?"**
Because weighted F1 lets the majority class hide the failure. If 97% of rows are
one class, a model that always predicts that class scores about 0.96 weighted
and about 0.49 macro. Macro gives each class an equal vote, so the model has to
actually get the rare class right. The same 20% check also turns on
`class_weight="balanced"`, which raises the loss penalty for minority-class
mistakes during training.

**"Where could data leak in this pipeline, and how did you stop it?"**
Three places. Preprocessing — solved by putting the `ColumnTransformer` inside
the `Pipeline`, so it refits per fold. Oversampling — solved by putting SMOTE
inside an `imblearn` pipeline, so synthetic rows never reach a validation fold.
Feature engineering — the transformer fits on training data and stores its
learned values (bin edges, transform parameters, quantile bounds) for reuse. What
is *not* solved is a leaked column in the source data; no tool can see that for
you.

**"Your model beat the others by 0.004. Is it better?"**
Almost certainly not. That is inside the fold-to-fold noise. Look at the five
individual fold scores, and if the spread is wider than the gap between the top
two models, treat the result as a tie and pick on cost, interpretability or
inference speed instead. The tool takes the maximum with no tolerance band,
which is a real weakness in its selection rule.

**"You report the test score as the model's performance. Is that honest?"**
It is honest about *that model on that split*. It is mildly optimistic about the
*procedure*, because the maximum of twelve cross-validation scores was used to
pick which model got refitted. Nested cross-validation is the correct fix; it
was not done for compute reasons, and I would say so rather than present the
number as unbiased.

**"Why not just use the best single algorithm every time?"**
Because which one wins genuinely depends on the data. Wide and sparse favours
linear models; many categorical columns favours CatBoost; small and noisy often
favours Random Forest. The competition costs one run and answers the question
for the dataset actually in front of you, instead of importing a prior from
someone else's benchmark.
