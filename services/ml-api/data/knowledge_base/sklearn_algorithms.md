<!-- Source: https://scikit-learn.org/stable/modules/tree.html, https://scikit-learn.org/stable/modules/ensemble.html, https://scikit-learn.org/stable/modules/linear_model.html — fetched 2026-07-01 -->

# Scikit-learn Algorithms Reference

## Decision Trees (CART)

### How It Works
Decision trees recursively partition feature space by finding optimal splits θ = (feature j, threshold t). At each node the algorithm evaluates all candidate splits, measures impurity reduction, and selects the best. Recursion continues until a stopping condition is met (max depth, minimum samples, impurity threshold). Scikit-learn implements **CART** (Classification and Regression Trees), producing binary trees.

**Impurity measures:**
- Classification: Gini (default), Entropy
- Regression: squared_error (default), absolute_error, poisson

**Split strategies:**
- `splitter='best'`: Greedy exhaustive search — minimizes impurity exactly
- `splitter='random'`: One random threshold per feature — faster, stochastic; enables learned missing-value routing

**Complexity:** Training O(n_features × n_samples × log n_samples). Inference O(log n_samples).

### Key Parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| `criterion` | `'gini'` / `'squared_error'` | Impurity measure |
| `max_depth` | None | Primary overfitting control; start with 3, then increase |
| `min_samples_split` | 2 | Min samples at node to attempt a split |
| `min_samples_leaf` | 1 | Guarantees minimum leaf size; 5 is a good starting point |
| `min_impurity_decrease` | 0.0 | Split only if impurity drops by at least this |
| `max_features` | None | Features considered per split; reduces overfitting in high-D |
| `ccp_alpha` | 0.0 | Cost-complexity pruning; higher = more aggressive pruning |
| `splitter` | `'best'` | 'random' is faster and supports NaN routing during prediction |

### Missing Values
With `splitter='best'`: evaluates sending NaNs left/right, picks optimal direction. At prediction, follows path learned during training; if feature never had NaN during training, routes to child with most samples.

### Cost-Complexity Pruning
Post-training: `R_α(T) = R(T) + α|T̃|` where |T̃| = number of terminal nodes. Increasing `ccp_alpha` progressively removes weakest links.

### When to Use / Caveats
- Use as interpretable baseline or as base learner within ensembles
- Highly unstable: small data changes produce completely different trees
- Prone to overfitting without depth/leaf controls
- Biased toward high-cardinality or dominant-class features
- Poor at extrapolation (piecewise constant approximation)
- High dimensions with few samples: apply PCA/feature selection first

---

## Ensemble Methods

### Random Forest

**Mechanism:** Bootstrap aggregation (bagging) + feature randomness. Each tree is trained on a bootstrap sample drawn with replacement. At each split, only a random subset of features is evaluated. Prediction = average of all trees (regression) or majority vote (classification). Independent tree errors cancel out, reducing variance.

**Key Parameters:**

| Parameter | Default | Notes |
|-----------|---------|-------|
| `n_estimators` | 100 | More trees = better (diminishing returns); increases runtime linearly |
| `max_features` | `'sqrt'` (clf) / `1.0` (reg) | Primary bias-variance knob; smaller = more regularization |
| `max_depth` | None | Trees are deep by default; control via `min_samples_leaf` |
| `min_samples_leaf` | 1 | Increase to reduce variance |
| `bootstrap` | True | Set False → Extremely Randomized Trees behavior |
| `oob_score` | False | Out-of-bag validation without separate holdout set |
| `n_jobs` | None | Parallelism across cores; -1 uses all |

**Feature importance (`feature_importances_`):** Impurity-based; computed on training data; biased toward high-cardinality features. Use permutation importance for unbiased estimates.

**When to use:** Quick strong baseline; large datasets; balanced classes; low tuning budget.

---

### Extremely Randomized Trees (ExtraTrees)

Same as Random Forest but uses **random split thresholds** instead of optimal ones. Result: slightly more variance reduction, slightly more bias. Faster than RF (no threshold search). `bootstrap=False` by default (uses full dataset).

---

### Gradient Boosted Trees

**Mechanism:** Sequential tree building. Each new tree minimizes residual loss of the current ensemble. Optimizes via gradient descent in function space using Taylor expansion (first + second derivatives) to compute optimal structure scores and leaf values for any differentiable loss.

**Gain for a split:**
`Gain = ½ [G_L²/(H_L+λ) + G_R²/(H_R+λ) − (G_L+G_R)²/(H_L+H_R+λ)] − γ`

If Gain < γ, split is rejected — principled built-in pruning.

#### HistGradientBoosting (recommended for n_samples > 10,000)

- Bins continuous features into ~256 integer bins; reduces split evaluation from O(n) to O(bins)
- Natively handles **missing values** (learned routing) and **categorical features** (no one-hot needed)
- Early stopping enabled by default when n_samples > 10,000
- Supports monotonic and interaction constraints
- Orders of magnitude faster than `GradientBoostingClassifier` on large data

**Categorical handling:** Sorts categories by target variance, evaluates K−1 contiguous partitions → O(K log K) vs O(2^K) for brute-force.

**Key Parameters:**

| Parameter | Default | Notes |
|-----------|---------|-------|
| `max_iter` | 100 | Number of boosting rounds |
| `learning_rate` | 0.1 | Shrinkage; lower = more trees needed, better generalization |
| `max_leaf_nodes` | 31 | Tree size; preferred over `max_depth` for HistGB |
| `max_depth` | None | Alternative tree size control |
| `l2_regularization` | 0.0 | L2 penalty on leaf weights |
| `subsample` | 1.0 | Row sampling fraction per iteration (stochastic boosting) |
| `max_features` | 1.0 | Column sampling per split |
| `max_bins` | 255 | Binning resolution; higher = slower but more accurate splits |
| `categorical_features` | None | Column indices/names for native categorical handling |
| `monotonic_cst` | None | Per-feature monotonicity: -1 (decrease), 0 (free), 1 (increase) |
| `early_stopping` | `'auto'` | Halts when validation score stops improving |

**Loss functions — regression:** squared_error, absolute_error, huber, quantile, gamma, poisson
**Loss functions — classification:** log_loss (default, binary/multiclass), exponential (binary only)

#### GradientBoostingClassifier / Regressor
- More accurate than Hist on small datasets (binning loses precision)
- More flexible loss function options
- Significantly slower for large n_samples

---

### AdaBoost

Fits weak learners (default: decision stumps) on reweighted training data. Misclassified samples get higher weight each round, forcing focus on hard examples. Final prediction is a weighted vote/sum. Implements AdaBoost.SAMME for multiclass. Less used in practice vs GBDT; useful as conceptual baseline and for boosting non-tree estimators.

---

### Random Forest vs Gradient Boosting at a Glance

| Aspect | Random Forest | HistGradientBoosting |
|--------|---------------|----------------------|
| Trees built | In parallel | Sequentially |
| Tree depth | Deep | Shallow |
| Primary mechanism | Variance reduction via averaging | Sequential error correction |
| Missing values | Requires imputation | Native support |
| Categorical features | Requires encoding | Native support |
| Tuning effort | Low | Moderate |
| Best for | Quick baseline, robustness | Max accuracy, large tabular data |

---

## Linear Models

### Logistic Regression

**Purpose:** Classification with probabilistic output.
P(y=1|X) = 1 / (1 + exp(−Xw − w₀))

**Regularization (applied by default):**
- L2 (`penalty='l2'`): Shrinks all weights; robust; default
- L1 (`penalty='l1'`): Sparse weights; performs implicit feature selection
- Elastic-Net (`penalty='elasticnet'`): Mix via `l1_ratio` (saga solver only)

**`C` parameter:** Inverse regularization strength. Higher C = less regularization. Default = 1.0.

**Solvers:**

| Solver | Best for |
|--------|---------|
| `lbfgs` | Default; robust, good general choice |
| `liblinear` | Small datasets; L1 support |
| `saga` | Large datasets; L1 + Elastic-Net support |
| `newton-cholesky` | n_samples >> n_features; high precision |
| `sag` | Large datasets; L2 only |

**Multiclass:** One-vs-Rest (default) or multinomial via `multi_class='multinomial'`.

---

### Ridge Regression

**Purpose:** Linear regression with L2 regularization.
Minimizes: `||Xw − y||₂² + α||w||₂²`

- Shrinks coefficients proportionally toward zero; does NOT produce exact zeros
- Handles multicollinearity extremely well
- `alpha`: regularization strength (≥ 0); default = 1.0
- `RidgeCV`: Efficient LOO cross-validation to select optimal alpha
- `RidgeClassifier`: Converts targets to {-1, 1}; much faster for many-class problems

---

### Lasso

**Purpose:** Linear regression with L1 regularization.
Minimizes: `(1/2n)||Xw − y||₂² + α||w||₁`

- Produces **exact zero coefficients** → automatic feature selection
- Uses coordinate descent with soft-thresholding
- Randomly picks among equally correlated features (instability)
- `LassoCV`: Cross-validation for alpha; preferred for high-D correlated data
- `LassoLarsCV`: LARS-based; faster when n_samples << n_features

---

### Elastic-Net

**Purpose:** Combines L1 and L2.
Minimizes: `(1/2n)||Xw−y||₂² + α·ρ||w||₁ + (α(1−ρ)/2)||w||₂²`

- `l1_ratio` (ρ): 1 = pure Lasso, 0 = pure Ridge
- When features are correlated, Lasso picks one randomly; Elastic-Net keeps all
- Inherits Ridge stability + Lasso sparsity

---

### Regularization Summary

| | Ridge | Lasso | Elastic-Net |
|---|-------|-------|-------------|
| Penalty | L2 | L1 | L1 + L2 |
| Sparsity | No | Yes | Yes |
| Multicollinearity | Excellent | Poor | Good |
| Correlated features | Keeps all (shrunk equally) | Picks one randomly | Keeps all |
| Feature selection | No | Yes | Yes |
