<!-- Source: https://scikit-learn.org/stable/modules/feature_selection.html — fetched 2026-07-01 -->

# Feature Selection (sklearn.feature_selection)

## What It Does

`sklearn.feature_selection` provides methods to select a subset of original features that contribute meaningfully to model performance. Feature selection reduces noise, training time, memory, and overfitting risk, and improves interpretability. It is distinct from feature extraction (PCA, etc.) — it retains original columns rather than creating new representations.

---

## Filter Methods (Univariate, Model-Independent)

Fast and scalable. Score each feature independently; cannot detect interactions.

### VarianceThreshold
Removes features with variance below a threshold. Default removes zero-variance (constant) features.

```python
sel = VarianceThreshold(threshold=0.16)  # for boolean: p*(1-p), e.g. 0.8*(1-0.8)
```

Use as a first-pass cleaning step before any other method.

### SelectKBest / SelectPercentile
Select the top k features or top p% by statistical score.

```python
X_new = SelectKBest(f_classif, k=20).fit_transform(X, y)
X_new = SelectPercentile(mutual_info_classif, percentile=20).fit_transform(X, y)
```

**Scoring functions:**

| Function | Problem Type | Captures | Notes |
|---|---|---|---|
| `f_classif` | Classification | Linear relationship | Fast; assumes normality |
| `f_regression` | Regression | Linear relationship | Fast |
| `chi2` | Classification | Any | Non-negative features only (counts/frequencies) |
| `mutual_info_classif` | Classification | Any (incl. non-linear) | Slower; needs more samples; set `random_state` |
| `mutual_info_regression` | Regression | Any (incl. non-linear) | Same caveats |
| `r_regression` | Regression | Linear (Pearson r) | Fast |

Do not use regression scoring functions with a classification target.

### GenericUnivariateSelect
Allows configurable strategy (k, percentile, fpr, fdr, fwe) for hyperparameter search across selection modes.

**Statistical filter variants:** `SelectFpr` (false positive rate), `SelectFdr` (false discovery rate), `SelectFwe` (family-wise error) — for p-value-based cutoffs.

---

## Wrapper Methods (Model-Dependent)

Train a model to evaluate feature subsets. Slower but accounts for interactions and model-specific behavior.

### RFE (Recursive Feature Elimination)
Fits the estimator, ranks features by `coef_` or `feature_importances_`, removes the least important, repeats.

- `n_features_to_select` — target number of features to keep.
- `step` — number (or fraction) of features to remove per iteration. `step=1` is exhaustive; `step=0.1` removes 10% per round.
- `estimator` must expose `coef_` or `feature_importances_`.

### RFECV
Cross-validated RFE that automatically finds the optimal number of features.

- `cv=5` — number of folds.
- `scoring='roc_auc'` — metric to optimize.
- `rfecv.n_features_` — optimal feature count at CV peak.

**Limitation:** Slow for large feature sets (p > 500). Results depend on the estimator — use the same model class you will train on.

### SequentialFeatureSelector (SFS)
Greedy forward or backward selection — adds/removes one feature at a time based on cross-validated score.

- `direction='forward'` — start empty, add best feature each step.
- `direction='backward'` — start full, remove worst feature each step.
- `n_features_to_select` — target count.

**When to use:** Estimator does not expose `coef_` or `feature_importances_`. Forward selection for selecting few features; backward for selecting many.

**Caveat:** Slower than RFE or SelectFromModel; requires fitting n_features * cv models per step.

---

## Embedded Methods (Selection During Training)

### SelectFromModel
Meta-transformer that uses a model's `coef_` or `feature_importances_` to threshold features.

```python
clf = ExtraTreesClassifier(n_estimators=50).fit(X, y)
model = SelectFromModel(clf, prefit=True, threshold="mean")
X_new = model.transform(X)
```

- `threshold` — `"mean"`, `"median"`, `"0.1*mean"`, or a numeric value.
- `max_features` — cap on number of features selected.

**L1-based selection:** Use `Lasso`, `LogisticRegression(penalty='l1')`, or `LinearSVC(penalty='l1')`. Smaller C or higher alpha = more sparsity = fewer features.

**Tree-based selection:** Use impurity-based `feature_importances_` from RandomForest, ExtraTrees, or gradient boosting.

**Caveat:** Impurity-based importances are biased toward high-cardinality features. Use permutation importance or SHAP values for less biased estimates.

---

## Sparse Data Support

`chi2`, `mutual_info_regression`, and `mutual_info_classif` handle sparse matrices without densification — important for text or high-dimensional one-hot encoded inputs.

---

## Feature Selection in Pipelines

Always wrap selection in a Pipeline to prevent data leakage — the selector must be fit only on training folds:

```python
pipe = Pipeline([
    ('selector', SelectKBest(mutual_info_classif, k=20)),
    ('clf', RandomForestClassifier())
])
scores = cross_val_score(pipe, X, y, cv=5, scoring='roc_auc')
```

Fitting selection outside the CV loop can inflate CV metrics by 0.05–0.15 AUC through selection overfitting.

---

## When to Use Each Method

| Situation | Method |
|---|---|
| First pass — remove constants and near-constants | `VarianceThreshold` |
| Fast baseline ranking, linear relationships | `SelectKBest(f_classif)` or `SelectKBest(f_regression)` |
| Non-linear or non-monotonic relationships | `SelectKBest(mutual_info_classif)` |
| Count/frequency features, classification | `SelectKBest(chi2)` |
| Model-based, estimator has coef_/importances_ | `SelectFromModel` |
| Want auto-selected feature count | `RFECV` |
| Estimator has no coef_/importances_ | `SequentialFeatureSelector` |
| Multi-objective or correlated features | SHAP-based selection (external) |

---

## Caveats

- **Unsupervised selection:** `SelectPercentile` and `SelectKBest` support unsupervised mode with an appropriate `score_func`.
- **L1 instability:** Among correlated features, L1 arbitrarily selects one. ElasticNet is more stable for group selection.
- **Hyperparameter tuning for selection:** Combine with cross-validation; treat `k`, `threshold`, or `n_features_to_select` as a hyperparameter to tune.
- **Impurity importance bias:** High-cardinality features appear more important due to more possible split points. Prefer permutation importance or SHAP for final selection decisions.
- **Model mismatch:** Filter methods optimal for linear models may not be optimal for tree-based models — match the selection strategy to the model family.
