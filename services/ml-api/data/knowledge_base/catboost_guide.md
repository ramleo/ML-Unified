# CatBoost: Comprehensive Technical Guide

CatBoost (Categorical Boosting) is a gradient boosting library developed by Yandex, released in 2017. It is specifically engineered to handle categorical features natively without manual preprocessing and introduces ordered boosting to eliminate prediction shift — a subtle form of target leakage that affects other gradient boosting methods. CatBoost consistently ranks among the top performers on tabular datasets that contain a mix of numerical and categorical columns.

---

## Gradient Boosting Fundamentals

Gradient boosting builds an ensemble of decision trees sequentially. Each tree is trained to predict the negative gradient of the loss function with respect to the current model's predictions. The final prediction is the sum of all tree outputs, scaled by the learning rate. The core challenge is that each tree is trained on the same dataset it partially helped label — this creates target leakage when statistics derived from the target variable are used as features during training.

### Why Classic Gradient Boosting Has Prediction Shift

In standard gradient boosting (and in XGBoost/LightGBM), when computing target-encoding statistics for a categorical feature, the statistic for observation `i` is computed using all observations including `i` itself. During training, the model sees a biased estimate of the category's mean target — one that includes the true label of the current observation. During inference, this bias disappears. The model is therefore trained on a distribution that differs from what it encounters at inference time. This gap is called prediction shift.

---

## Ordered Boosting: CatBoost's Core Innovation

CatBoost addresses prediction shift through ordered boosting. Rather than training all trees on the same residuals from the full dataset, CatBoost maintains a random permutation of the training data and computes the residual for observation `i` using only a model trained on observations `1` through `i-1` in that permutation.

### How Ordered Boosting Works Step by Step

1. A random permutation of training examples is drawn at the start.
2. The model is split into two copies: one for building trees (the "learning" model) and one for providing predictions at inference time.
3. For observation `i`, its gradient/residual is computed using the model trained on `{1, 2, ..., i-1}`.
4. The leaf value for that observation uses a separate subset to prevent overfitting.
5. Multiple random permutations are used across iterations to reduce variance.

This ensures no observation ever contributes to its own gradient calculation, eliminating prediction shift entirely.

### Ordered vs. Plain Boosting Mode

CatBoost supports two modes: `ordered` (default for small-to-medium datasets) and `plain` (resembles standard gradient boosting). On large datasets (>100k rows), `ordered` mode can be slow because it maintains multiple model copies. In that case, setting `boosting_type='Plain'` significantly reduces training time with a small accuracy trade-off.

---

## Native Categorical Feature Handling

### Target Statistics (TS)

The standard approach for encoding categorical features in gradient boosting is to compute the mean target value for each category and use that number as a numerical feature. The problem is target leakage: if category A has three observations with labels `[0, 1, 1]`, the encoding for the first observation with label `0` incorporates its own label in the mean.

CatBoost solves this using Ordered Target Statistics. For observation `i` in the permutation, the target statistic for its category `c` is:

```
TS(i, c) = (sum of targets for category c in positions 1..i-1) + prior_sum
           / (count of category c in positions 1..i-1 + prior_count)
```

The `prior_sum` and `prior_count` serve as a smoothing term (similar to additive smoothing in Bayesian estimation). This ensures the statistic for observation `i` never uses its own label.

### Ordered Target Statistics vs. Standard Mean Encoding

Standard mean encoding without cross-validation causes overfitting, especially on low-frequency categories. CatBoost's ordered TS:
- Never leaks the target for the current observation.
- Applies Bayesian smoothing automatically to handle rare categories.
- Is computed on-the-fly per permutation, so it changes across iterations.

### Specifying Categorical Features

CatBoost requires you to declare which columns are categorical using the `cat_features` parameter. It accepts column indices (integer list) or column names (when using Pool with a DataFrame). CatBoost internally converts string categories to integer codes using a hash and then applies ordered TS.

```python
from catboost import CatBoostClassifier, Pool

train_pool = Pool(X_train, y_train, cat_features=['city', 'product_type'])
model = CatBoostClassifier(iterations=500, depth=6, learning_rate=0.05)
model.fit(train_pool)
```

If `cat_features` is not specified, CatBoost treats all columns as numerical. Passing categorical columns without declaring them causes a training error if they contain strings.

### Combination Features

CatBoost can automatically create combinations of categorical features (interactions). It greedily selects combinations that provide the largest gradient gain. The maximum number of combinations is controlled by `max_ctr_complexity` (default 4). Higher values explore more interactions but increase training time.

---

## Key Hyperparameters

### iterations (alias: num_boost_round, n_estimators)

Number of trees to build. More trees improve performance but increase training time and risk overfitting without regularization. Typical range: 100 to 5000. When the overfitting detector is active, training halts early and the optimal number of trees is stored in `best_iteration_`.

- Low (100-300): quick experiments, small datasets.
- Medium (500-1000): standard production settings.
- High (2000-5000): large datasets with low learning rate.

### depth (alias: max_depth)

Maximum depth of each tree. CatBoost uses symmetric (oblivious) trees where all nodes at the same depth use the same split condition. This is different from XGBoost/LightGBM which use asymmetric trees. Symmetric trees are faster to evaluate and less prone to overfitting.

- Default: 6.
- Typical range: 4 to 10.
- Shallow trees (4-6): high bias, low variance, faster training, better generalization on noisy data.
- Deep trees (8-10): can capture complex patterns but require more regularization.

Symmetric trees mean that depth 8 has 256 leaf nodes — the same structure is replicated across the full width of the tree.

### learning_rate (alias: eta)

Step size for each tree's contribution. Smaller values require more trees but usually produce better generalization.

- Default: auto-determined based on `iterations` and dataset size (typically 0.03-0.1).
- Typical range: 0.01 to 0.3.
- Rule of thumb: halving the learning rate should approximately double `iterations` for equivalent performance.
- For final models, use learning_rate=0.01-0.03 with early stopping.

### l2_leaf_reg (alias: reg_lambda)

L2 regularization applied to leaf values. Higher values increase regularization, shrink leaf values toward zero, and reduce overfitting.

- Default: 3.0.
- Typical range: 1 to 10.
- On small datasets or noisy targets, values of 5-10 help significantly.

### border_count (alias: max_bin)

Number of splits to evaluate for each numerical feature when building histograms. Higher values give finer granularity but increase memory and training time.

- Default: 128 (CPU), 32 (GPU).
- Typical range: 32 to 254.
- Rarely needs tuning beyond the default unless you have continuous features with very fine-grained decision boundaries.

### cat_features

List of column indices or names that CatBoost should treat as categorical. Critical for correct ordered TS computation. Do not one-hot encode or label-encode these columns before passing them to CatBoost — let CatBoost handle them natively.

### bagging_temperature

Controls the randomness of Bayesian bootstrap (the default bootstrap mode in CatBoost). A value of 1.0 gives standard Bayesian bootstrap; 0.0 makes all weights equal (no bagging). Higher values increase diversity among trees.

- Default: 1.0.
- Typical range: 0.0 to 1.0.

### rsm (random subspace method, alias: colsample_bylevel)

Fraction of features to use at each split (column subsampling). Reduces correlation between trees and speeds up training.

- Default: 1.0 (use all features).
- Typical range: 0.5 to 1.0.

### random_strength

Amount of randomness applied to scoring of splits. Adds noise to split scores during the first few iterations to encourage exploration.

- Default: 1.0.
- Higher values: more exploration, useful to escape local optima on small datasets.

---

## Overfitting Detector

CatBoost has a built-in overfitting detector that monitors a validation metric and stops training when it stops improving. This is equivalent to early stopping in XGBoost but is integrated directly into CatBoost's fit API.

### Usage

```python
model = CatBoostClassifier(
    iterations=2000,
    learning_rate=0.03,
    od_type='Iter',        # or 'IncToDec'
    od_wait=50,            # stop if no improvement for 50 rounds
    eval_metric='AUC'
)
model.fit(
    X_train, y_train,
    eval_set=(X_val, y_val),
    verbose=100
)
print(model.best_iteration_)
```

### od_type Options

- `Iter`: stops if the metric does not improve for `od_wait` consecutive iterations.
- `IncToDec`: stops when the metric begins consistently declining relative to a smoothed moving average.

### Why This Matters

The overfitting detector lets you set `iterations` high (e.g., 3000) and `learning_rate` low (e.g., 0.01) without worrying about exact stopping point. CatBoost will find the optimal checkpoint and store it in `best_iteration_`. This is the recommended workflow for production models.

---

## Why CatBoost Wins on Tabular Data with Categoricals

### No Preprocessing Pipeline Required

XGBoost and LightGBM cannot natively handle string categories — you must one-hot encode or target-encode them manually. One-hot encoding creates high-dimensional sparse matrices for high-cardinality categoricals (e.g., ZIP codes, product IDs), which wastes memory and degrades split quality. CatBoost's ordered TS handles cardinalities of 10,000+ without memory explosion.

### Symmetric Trees for Fast Inference

CatBoost's symmetric (oblivious) tree structure evaluates all examples with the same sequence of comparisons. This allows vectorized batch scoring, making inference significantly faster than XGBoost or LightGBM on CPU. On GPU, symmetric trees map naturally to parallel evaluation.

### Better Calibrated Probabilities

Empirical benchmarks on UCI datasets show CatBoost produces better calibrated probability estimates than XGBoost/LightGBM on datasets with high-cardinality categoricals. This is due to the Bayesian smoothing in ordered TS, which prevents the model from being overconfident about rare categories.

### Ordered Boosting Reduces Overfitting on Small Datasets

On datasets under 10,000 rows, prediction shift causes measurable overfitting in XGBoost/LightGBM. CatBoost's ordered boosting reduces this gap, often matching or beating tree-based competitors on small tabular datasets.

---

## Comparison to XGBoost and LightGBM

### XGBoost

- Tree growth: level-wise (BFS). All nodes at the same depth are expanded before moving deeper.
- Categorical support: none natively. Requires manual encoding.
- Regularization: L1 (alpha) and L2 (lambda) on leaf weights plus tree complexity penalty (gamma).
- Approximate splits: uses histograms or exact greedy. Global or local sketch.
- GPU support: yes.
- Strengths: mature, stable, excellent documentation, widest ecosystem support.
- Weakness: slow on high-cardinality categoricals, no ordered boosting.

### LightGBM

- Tree growth: leaf-wise (best-first). Expands the leaf with the highest loss reduction regardless of depth.
- Categorical support: yes, via Fisher's optimal binning — groups categories by sorted target rate. Faster than one-hot but not equivalent to CatBoost's ordered TS.
- Regularization: min_child_samples, min_child_weight, num_leaves.
- Key advantages: very fast training, low memory (GOSS + EFB), excellent for large datasets.
- Weakness: leaf-wise growth can overfit on small datasets; categorical handling less principled than CatBoost.

### CatBoost

- Tree growth: level-wise with symmetric structure.
- Categorical support: ordered TS, native, no manual encoding.
- Regularization: l2_leaf_reg, bagging_temperature, random_strength.
- Key advantage: no target leakage on categoricals, best out-of-box performance on mixed datasets.
- Weakness: slower training than LightGBM on purely numerical data; ordered mode slow on very large datasets.

### When to Choose Each

| Scenario | Recommended |
|---|---|
| High-cardinality categoricals | CatBoost |
| Very large datasets (>1M rows), numerical only | LightGBM |
| Need widest ecosystem/tooling support | XGBoost |
| Small datasets (<10k rows) with categoricals | CatBoost |
| Fast prototyping, large scale | LightGBM |
| Unknown, mixed dataset | CatBoost or LightGBM (benchmark both) |

---

## GPU Training Support

CatBoost has first-class GPU support and is often faster on GPU than LightGBM for datasets with categorical features.

### Enabling GPU

```python
model = CatBoostClassifier(
    iterations=1000,
    task_type='GPU',
    devices='0'           # GPU device index
)
```

### GPU-Specific Behavior

- `border_count` default drops to 32 on GPU (vs 128 on CPU). Increase to 128 if precision is critical.
- Ordered boosting on GPU uses approximations; for maximum accuracy use `boosting_type='Plain'` with GPU.
- Training speed improvements of 10-50x over CPU are typical on large datasets.
- Multi-GPU: specify `devices='0:1:2'` or `devices='0-3'`.

---

## Feature Importance and Interpretability

CatBoost provides multiple types of feature importance:

### PredictionValuesChange (default)

Measures how much the model's predictions change when a feature is removed. Computed on training data. Fast to compute.

### LossFunctionChange

Measures the loss function change when a feature is removed. More accurate than PredictionValuesChange. Requires a validation set.

### SHAP Values

CatBoost integrates with the SHAP library. Symmetric tree structure allows exact SHAP computation in O(TLD) time, where T is trees, L is leaves per tree, and D is depth.

```python
shap_values = model.get_feature_importance(train_pool, type='ShapValues')
```

---

## Practical Configuration for Common Use Cases

### Quick Benchmark (small dataset, <10k rows)

```python
CatBoostClassifier(iterations=500, depth=6, learning_rate=0.05,
                   l2_leaf_reg=3, od_type='Iter', od_wait=30,
                   cat_features=cat_cols, verbose=0)
```

### Production Model (medium dataset, 10k-500k rows)

```python
CatBoostClassifier(iterations=3000, depth=7, learning_rate=0.02,
                   l2_leaf_reg=5, bagging_temperature=0.8,
                   rsm=0.8, od_type='Iter', od_wait=100,
                   cat_features=cat_cols, task_type='CPU', verbose=200)
```

### Large Dataset (>500k rows)

```python
CatBoostClassifier(iterations=2000, depth=8, learning_rate=0.05,
                   boosting_type='Plain', l2_leaf_reg=3,
                   cat_features=cat_cols, task_type='GPU', verbose=100)
```

---

## CatBoost Pool Object

CatBoost's `Pool` class encapsulates the dataset along with metadata (categorical feature indices, weights, group IDs for ranking). Using Pool avoids redundant re-encoding on each fit call and is required for some advanced features.

```python
from catboost import Pool

train_pool = Pool(
    data=X_train,
    label=y_train,
    cat_features=['city', 'product_id'],
    weight=sample_weights          # optional per-sample weights
)
```

Passing a Pool to `model.fit()` is more efficient than passing raw arrays when using categorical features, especially for repeated cross-validation runs.

---

## Cross-Validation with CatBoost

```python
from catboost import cv, Pool

params = {
    'iterations': 500,
    'depth': 6,
    'learning_rate': 0.05,
    'loss_function': 'Logloss',
    'eval_metric': 'AUC'
}
cv_results = cv(params=params, pool=train_pool, fold_count=5, shuffle=True,
                partition_random_seed=42, plot=False, verbose=False)
print(cv_results['test-AUC-mean'].max())
```

The built-in `cv` function handles early stopping per fold and reports mean and standard deviation of metrics across folds.

---

## Common Pitfalls

### Forgetting cat_features

If categorical columns contain strings and `cat_features` is not set, CatBoost raises a type error. If they have been integer-encoded already, CatBoost treats them as numerical — which may work but loses the benefit of ordered TS. Always declare `cat_features` explicitly.

### Using One-Hot Before CatBoost

One-hot encoding categorical features before passing them to CatBoost defeats the purpose. CatBoost's internal handling is almost always superior to manual one-hot encoding for cardinality > 5.

### Not Setting od_wait High Enough

With `od_wait=20` and `learning_rate=0.01`, the detector may stop too early. When using a very small learning rate, set `od_wait=100-200` to allow the model sufficient time to demonstrate improvement.

### Ignoring verbose

By default, CatBoost prints training logs every iteration. For long training runs, set `verbose=100` or `verbose=False` in production pipelines.