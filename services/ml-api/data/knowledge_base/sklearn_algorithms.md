# Scikit-Learn Algorithms: Comprehensive Technical Guide

This guide covers the core supervised learning algorithms available in scikit-learn. Each section provides the mathematical intuition, key hyperparameters with typical ranges, strengths and weaknesses, and concrete guidance on when to use or avoid each method. All algorithms follow the standard scikit-learn API: `fit(X, y)`, `predict(X)`, `score(X, y)`.

---

## Random Forest

Random Forest is an ensemble learning method that builds many decision trees independently (bagging) and combines their predictions by majority vote (classification) or averaging (regression). It is one of the most reliable general-purpose algorithms in machine learning and often serves as a strong baseline.

### Bagging: The Foundation

Bagging (Bootstrap Aggregating) trains each tree on a bootstrap sample of the training data — a random sample with replacement of the same size as the original dataset. On average, each bootstrap sample contains about 63.2% of the original rows (some appear multiple times; roughly 36.8% are never selected). The unselected rows form the out-of-bag (OOB) sample.

Bagging reduces variance without significantly increasing bias. Individual trees are high-variance, low-bias learners. Averaging many such trees reduces variance while preserving the low bias.

### Key Hyperparameters

#### n_estimators

Number of trees in the forest.

- Default: 100.
- More trees always reduce variance (up to a point of diminishing returns).
- Practical minimum: 100 trees for stable estimates.
- Typical production range: 200 to 500.
- Beyond 500: marginal improvement; compute cost may not be justified.
- Use `n_jobs=-1` to parallelize tree building across all CPU cores.

#### max_features

Number of features to consider at each split. This is the primary mechanism for decorrelating trees in the forest.

- Default for classification: `'sqrt'` (square root of total features).
- Default for regression: `1.0` (all features, i.e., no subsampling).
- Common values: `'sqrt'`, `'log2'`, or a float between 0.1 and 1.0.
- Lower values produce more diverse trees (higher bias per tree, lower variance overall).
- Rule of thumb for regression: try `max_features=0.33` as a starting point.
- For datasets with many irrelevant features, lower `max_features` helps important features get selected more often.

#### max_depth

Maximum depth of each tree.

- Default: `None` (trees grow until all leaves are pure or contain fewer than `min_samples_split` samples).
- Unlimited depth works well for Random Forest because bagging controls variance.
- Limiting depth (e.g., 10-20) reduces training time and memory on large datasets.

#### min_samples_split

Minimum number of samples required to split a node.

- Default: 2.
- Increasing to 5-20 acts as regularization; prevents splits on very small node groups.

#### min_samples_leaf

Minimum number of samples required at each leaf node.

- Default: 1.
- Values of 5-10 smooth predictions on noisy datasets.

#### max_samples (bootstrap fraction)

The fraction of samples to draw for each tree's bootstrap sample.

- Default: `None` (draw a full bootstrap sample of size n).
- Can be set to a float (e.g., 0.8) to draw smaller bags — reduces training time.

### Out-of-Bag Score

Because each tree is trained on a bootstrap sample, approximately 37% of the data is never seen by each tree. These OOB samples can serve as a validation set. Setting `oob_score=True` computes an unbiased estimate of generalization error without a separate validation split.

```python
from sklearn.ensemble import RandomForestClassifier

rf = RandomForestClassifier(n_estimators=300, max_features='sqrt',
                             oob_score=True, n_jobs=-1, random_state=42)
rf.fit(X_train, y_train)
print(rf.oob_score_)   # unbiased accuracy estimate
```

OOB score is particularly useful when training data is scarce.

### Feature Importance in Random Forest

Random Forest provides `feature_importances_` as mean decrease in impurity (MDI) across all trees. This metric is fast but biased toward high-cardinality features and correlated features. For more reliable importance, use permutation importance (`sklearn.inspection.permutation_importance`) or SHAP values.

### When to Use Random Forest

- Good default algorithm for tabular classification and regression tasks.
- When data has mixed feature types (numerical and ordinal).
- When interpretability is needed at the aggregate level (feature importance).
- When training data is moderate in size (1k-500k rows).
- When you want a reliable baseline with minimal hyperparameter tuning.

### When Random Forest Struggles

- Very high-dimensional sparse data (text): gradient boosting or linear models often better.
- Very large datasets (>1M rows): training time can be prohibitive; LightGBM/CatBoost preferable.
- Extrapolation beyond training range: all tree-based methods fail at extrapolation.

---

## Extra Trees (Extremely Randomized Trees)

Extra Trees (ExtraTreesClassifier / ExtraTreesRegressor) is a variant of Random Forest that introduces additional randomization in the split-finding step.

### How Extra Trees Differs from Random Forest

In Random Forest, the best split among a random subset of `max_features` features is selected (using the optimal threshold for each candidate feature). In Extra Trees, both the features and the split thresholds are drawn at random — the algorithm selects the best split among these randomly generated candidates.

This extra randomization:
- Reduces variance further (trees are more diverse).
- Increases bias slightly (splits are suboptimal).
- Is significantly faster to train because no threshold optimization is performed.

### Key Hyperparameters

Same as Random Forest. The critical difference is in the splitting strategy, not the architecture.

- `n_estimators`: same guidance as Random Forest (200-500).
- `max_features`: can be set higher than Random Forest (e.g., `'sqrt'` or `0.5`) since random splits already decorrelate trees.

### When to Use Extra Trees

- When training time is a bottleneck and a small accuracy trade-off is acceptable.
- When Random Forest overfits and additional regularization is needed.
- As a fast alternative to Random Forest for large datasets.

In practice, Extra Trees and Random Forest perform similarly, with Extra Trees typically 2-5x faster to train.

---

## Logistic Regression

Logistic Regression is a linear model for binary and multiclass classification. Despite the name, it is a classification algorithm. It models the log-odds of the target class as a linear combination of features.

### Mathematical Foundation

For binary classification:

```
P(y=1 | x) = sigmoid(w^T x + b) = 1 / (1 + exp(-(w^T x + b)))
```

The model is trained by minimizing the cross-entropy loss (log loss) with optional regularization.

### C Parameter (Inverse Regularization Strength)

`C` is the inverse of regularization strength: `C = 1 / lambda`.

- Smaller C: stronger regularization, simpler model, more bias.
- Larger C: weaker regularization, more complex model, more variance.
- Default: 1.0.
- Typical range: 0.001 to 100 (search log-uniformly: 0.001, 0.01, 0.1, 1, 10, 100).
- When features are not scaled, regularization is biased toward high-magnitude features — always scale before Logistic Regression.

### Solver Choice

The `solver` parameter determines the optimization algorithm.

| Solver | Penalty | Best For |
|---|---|---|
| `lbfgs` | L2, none | Default; works well for small-to-medium datasets |
| `saga` | L1, L2, ElasticNet, none | Large datasets, sparse solutions needed |
| `liblinear` | L1, L2 | Small datasets; one-vs-rest only |
| `newton-cg` | L2, none | Medium datasets, fast convergence |
| `sag` | L2, none | Large datasets, faster than lbfgs on large n |

For most use cases, `lbfgs` (default) is appropriate. Use `saga` when you need L1 regularization (sparse feature selection) or ElasticNet.

### Multi-Class Strategies

- `multi_class='ovr'` (one-vs-rest): trains one binary classifier per class.
- `multi_class='multinomial'`: softmax regression; minimizes true multinomial log-loss. Generally better for more than 2 classes.
- `multi_class='auto'` (default): chooses multinomial when solver supports it.

### Regularization Types

- `penalty='l2'` (default): shrinks all coefficients toward zero; keeps all features.
- `penalty='l1'`: forces many coefficients to exactly zero; performs feature selection.
- `penalty='elasticnet'`: combination of L1 and L2; controlled by `l1_ratio` (0=L2, 1=L1).

### When to Use Logistic Regression

- Linear separability assumption holds (or approximately holds).
- High-dimensional text classification (with L1 regularization for sparsity).
- Probability calibration is important: logistic regression outputs well-calibrated probabilities.
- As a baseline to understand the linear component of a problem.
- When interpretability of coefficients is required.
- Fast inference and small model size are requirements.

### When Logistic Regression Fails

- Non-linear decision boundaries without feature engineering.
- Mixed numerical/categorical data with complex interactions.
- When features are highly correlated (collinearity inflates coefficient variance).

---

## Ridge Regression

Ridge Regression (L2 regularized linear regression) minimizes the residual sum of squares plus a penalty on the squared magnitude of coefficients:

```
minimize: ||y - Xw||^2 + alpha * ||w||^2
```

### Alpha Parameter

`alpha` is the regularization strength (analogous to `1/C` in Logistic Regression).

- Default: 1.0.
- Typical range: 0.01 to 1000 (search log-uniformly).
- alpha=0: ordinary least squares (no regularization).
- Higher alpha: stronger shrinkage; coefficients pulled toward zero.

### When Ridge Beats OLS

- When features are highly correlated (multicollinearity): OLS has high variance; Ridge stabilizes it.
- When n (samples) < p (features): OLS is undefined; Ridge provides a unique solution.
- When you want to retain all features but reduce their influence.

### RidgeCV

`RidgeCV` performs Ridge regression with built-in cross-validation to select the best `alpha` from a list. Much faster than a full `GridSearchCV` loop because it leverages the closed-form solution.

```python
from sklearn.linear_model import RidgeCV
import numpy as np

model = RidgeCV(alphas=np.logspace(-3, 4, 50), cv=5)
model.fit(X_train, y_train)
print(model.alpha_)    # selected alpha
```

---

## Lasso Regression

Lasso Regression (L1 regularized linear regression) minimizes:

```
minimize: ||y - Xw||^2 + alpha * ||w||_1
```

The L1 penalty promotes sparsity: many coefficients become exactly zero, effectively performing automatic feature selection.

### Alpha in Lasso

Same interpretation as Ridge. Typical range: 0.0001 to 10.

### Ridge vs. Lasso: When to Use Which

| Criterion | Ridge | Lasso |
|---|---|---|
| Feature selection | No | Yes |
| Multicollinearity | Handles well (distributes weight) | Picks one; zeros others |
| Sparse solution needed | No | Yes |
| Many irrelevant features | Retains with small weight | Eliminates |
| Correlated features | Preferred | Unstable (arbitrary which is kept) |

### ElasticNet

ElasticNet combines L1 and L2 penalties. Useful when there are many correlated features and sparse solutions are desired. Controlled by `l1_ratio` (0=Ridge, 1=Lasso).

---

## Support Vector Machines (SVM)

SVMs find the hyperplane that maximizes the margin between classes. For non-linearly separable data, the kernel trick implicitly maps features to a higher-dimensional space where linear separation is possible.

### C Parameter

`C` controls the trade-off between maximizing the margin and minimizing classification errors on the training set.

- Small C: wide margin, more misclassifications allowed (soft margin), high bias.
- Large C: narrow margin, fewer training errors (hard margin), high variance.
- Default: 1.0.
- Typical range: 0.01 to 1000 (log-uniform search).

### Kernel Choice

#### Linear Kernel (kernel='linear')

No implicit feature map. Equivalent to a linear classifier. Fast and interpretable. Works well when:
- Data is linearly separable.
- Number of features is large relative to samples (text, genomics).
- p >> n scenarios.

#### RBF Kernel (Radial Basis Function, kernel='rbf')

```
K(x, z) = exp(-gamma * ||x - z||^2)
```

Maps data to infinite-dimensional space. Default kernel. Works well when the decision boundary is non-linear and features are on comparable scales. Most common choice for non-linear problems.

#### Polynomial Kernel (kernel='poly')

```
K(x, z) = (gamma * x^T z + coef0)^degree
```

Useful for problems where feature interactions of a specific degree are meaningful. Less common in practice; degree 2 or 3 is typical.

### Gamma Parameter (RBF, Polynomial, Sigmoid kernels)

Controls the influence radius of each training example.

- High gamma: small influence radius; model fits training data closely (high variance, can overfit).
- Low gamma: large influence radius; smoother decision boundary (high bias, may underfit).
- Default: `'scale'` = 1 / (n_features * X.var()).
- Alternative default: `'auto'` = 1 / n_features.
- Typical range (manual): 1e-4 to 10.

### Feature Scaling Is Mandatory

SVM is not scale-invariant. Features must be standardized (zero mean, unit variance) or min-max scaled before SVM training. Failing to scale causes the kernel distance computation to be dominated by high-magnitude features.

```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

pipe = Pipeline([
    ('scaler', StandardScaler()),
    ('svm', SVC(C=1.0, kernel='rbf', gamma='scale', probability=True))
])
```

### When to Use SVM

- Small-to-medium datasets (up to ~10,000 samples): SVMs scale as O(n^2) to O(n^3) with standard solvers.
- High-dimensional feature spaces (text classification with linear kernel).
- When a clear margin of separation exists in the data.
- When you need a theoretically grounded classifier with solid generalization bounds.

### When to Avoid SVM

- Large datasets (>50,000 rows): training time becomes prohibitive.
- Probabilistic outputs needed: SVM does not natively output calibrated probabilities (use `probability=True` but it adds cost via Platt scaling).
- Interpretability required: SVM decision boundaries are opaque.

---

## Decision Trees

Decision Trees partition the feature space by recursively splitting on the feature and threshold that best separates the target classes or reduces regression error. They are fully interpretable and require no feature scaling.

### Gini Impurity vs. Entropy (criterion)

Both measure node impurity; both produce similar trees in practice.

**Gini Impurity:**
```
Gini = 1 - sum(p_i^2)
```
- Computationally faster (no logarithm).
- Tends to isolate the most frequent class in one branch.
- Default for classification.

**Entropy (Information Gain):**
```
Entropy = -sum(p_i * log2(p_i))
```
- Slightly more expensive to compute.
- Penalizes impurity more evenly.
- May produce slightly better-balanced trees.

In most practical cases, the choice between Gini and Entropy makes negligible difference. Use `criterion='gini'` (default) unless you have a specific reason to prefer entropy.

For regression, use `criterion='squared_error'` (default) or `'absolute_error'` for robustness to outliers.

### max_depth

Most important hyperparameter for controlling tree complexity and overfitting.

- Default: `None` (fully grown tree; high overfitting risk).
- Typical range: 3 to 15.
- Shallow trees (3-5): interpretable, high bias, good for explanations.
- Deeper trees (10-15): capture complex patterns but overfit without pruning.
- Rule: start shallow and increase while monitoring validation performance.

### min_samples_split and min_samples_leaf

Pre-pruning parameters that stop splitting early.

- `min_samples_split`: minimum samples to split a node. Default: 2. Increase to 10-50 to regularize.
- `min_samples_leaf`: minimum samples in any leaf. Default: 1. Setting to 5-20 creates smoother predictions.

### max_leaf_nodes

Limits the total number of leaf nodes in the tree. An alternative to `max_depth` for controlling tree size.

### Pruning with ccp_alpha

Post-pruning using Cost-Complexity Pruning. After training a full tree, `ccp_alpha` removes branches that do not sufficiently reduce impurity relative to their complexity cost.

```python
from sklearn.tree import DecisionTreeClassifier

path = DecisionTreeClassifier().cost_complexity_pruning_path(X_train, y_train)
ccp_alphas = path.ccp_alphas

# Cross-validate to find best alpha
best_tree = DecisionTreeClassifier(ccp_alpha=0.01)
best_tree.fit(X_train, y_train)
```

### When to Use Decision Trees

- Interpretability is a hard requirement (single tree, shallow depth).
- Baseline model for a classification or regression problem.
- As a building block for ensemble methods (Random Forest, Gradient Boosting).
- Mixed feature types; no scaling required.

### When Decision Trees Fail

- Standalone deep trees generalize poorly (high variance).
- Linear relationships between features and target: linear models are more efficient.
- Extrapolation: tree predictions are piecewise constant; they cannot extrapolate beyond training range.

---

## K-Nearest Neighbors (KNN)

KNN is a non-parametric, lazy learning algorithm. It stores all training examples and makes predictions by finding the K closest training examples to a new query point, then aggregating their labels.

### How KNN Works

**Classification:** The query point is assigned the class that appears most frequently among its K nearest neighbors (majority vote).

**Regression:** The query point is assigned the average target value of its K nearest neighbors.

No explicit training step exists; all computation happens at prediction time. This makes training instantaneous but inference slow for large datasets.

### Choosing K

`n_neighbors` is the most critical hyperparameter.

- K=1: each prediction is determined by a single neighbor; high variance, zero training error.
- K=n: every prediction is the majority class (classification) or mean target (regression); maximum bias.
- Typical range: 3 to 30.
- Odd K for binary classification: avoids tie-breaking.
- Rule of thumb: start with K = sqrt(n_train) as an initial estimate.
- Tune via cross-validation; plot validation accuracy vs. K.

### Distance Metrics

`metric` parameter controls how distance between points is measured.

- `'minkowski'` with `p=2` (default): Euclidean distance.
- `'minkowski'` with `p=1`: Manhattan distance (L1). More robust to outliers and high dimensions.
- `'cosine'`: useful for text/document similarity (requires dense vectors).
- Custom metrics: any callable that satisfies distance metric axioms.

### weights Parameter

- `'uniform'` (default): all K neighbors vote equally.
- `'distance'`: closer neighbors receive higher weight (1/distance). Better when nearby points are more relevant than distant ones.

### Feature Scaling Is Mandatory

KNN uses distance; unscaled features dominate the distance calculation. Always apply `StandardScaler` or `MinMaxScaler` before KNN.

### Curse of Dimensionality

In high-dimensional spaces, all points become approximately equidistant. KNN degrades badly when the number of features exceeds ~20-50 (depending on data density). Dimensionality reduction (PCA) before KNN is often necessary.

### KNN Algorithm Options

`algorithm` parameter:
- `'auto'`: selects best algorithm based on data.
- `'ball_tree'`: efficient for moderate dimensions with specific metrics.
- `'kd_tree'`: efficient for low dimensions (<20 features).
- `'brute'`: exact nearest neighbor search; necessary for custom metrics or high dimensions.

`leaf_size` affects tree construction speed; default 30 is typically fine.

### When to Use KNN

- Small-to-medium datasets with well-defined local structure.
- Multi-label classification (KNN handles it naturally).
- Recommendation systems (similarity-based retrieval).
- When the decision boundary is highly irregular and non-parametric.
- As a quick baseline when domain knowledge suggests local similarity matters.

### When to Avoid KNN

- Large datasets: inference time is O(n * p) per query; impractical at scale.
- High-dimensional features: curse of dimensionality.
- When fast inference is required in production.
- Imbalanced classes: majority class dominates votes unless using `weights='distance'` and class-weighting.

---

## Algorithm Selection Decision Rules

### By Dataset Size

| n (rows) | Recommended Algorithms |
|---|---|
| <1,000 | Logistic Regression, SVM (RBF), Decision Tree, KNN |
| 1,000-10,000 | Random Forest, Logistic Regression, SVM, Gradient Boosting |
| 10,000-100,000 | Random Forest, Gradient Boosting (XGBoost/LightGBM/CatBoost) |
| >100,000 | Gradient Boosting, Logistic Regression (with SGD), Linear SVM |

### By Feature Type

| Feature Composition | Recommended |
|---|---|
| All numerical, low-dimensional | Any algorithm; try Linear + Tree + Ensemble |
| High-cardinality categoricals | CatBoost, then Random Forest |
| Text (bag-of-words, TF-IDF) | Logistic Regression (L1/L2), Linear SVM, Naive Bayes |
| Mix of numerical + categorical | Random Forest, CatBoost, Gradient Boosting |
| High-dimensional (p >> n) | Ridge, Lasso, ElasticNet, Linear SVM |

### By Interpretability Requirement

| Requirement | Algorithm |
|---|---|
| Full interpretability (rules) | Decision Tree (shallow, max_depth 3-5) |
| Coefficient interpretability | Logistic Regression, Ridge, Lasso |
| Feature importance only | Random Forest, Extra Trees, Gradient Boosting |
| Black box acceptable | SVM (RBF), Deep Ensembles, KNN |

### By Training vs. Inference Trade-off

| Priority | Algorithm |
|---|---|
| Fast training, slower inference | KNN, Logistic Regression |
| Slow training, fast inference | SVM, Random Forest, Gradient Boosting |
| Both fast | Logistic Regression, Ridge Regression |

---

## Preprocessing Requirements by Algorithm

| Algorithm | Scaling Required | Missing Values | Categoricals |
|---|---|---|---|
| Logistic Regression | Yes | Impute first | Encode (OHE or ordinal) |
| Ridge / Lasso | Yes | Impute first | Encode |
| SVM | Yes (mandatory) | Impute first | Encode |
| Decision Tree | No | Can handle NaN with splitter tricks | Encode (ordinal) |
| Random Forest | No | Impute first | Encode (ordinal) |
| Extra Trees | No | Impute first | Encode (ordinal) |
| KNN | Yes (mandatory) | Impute first | Encode |
| Gradient Boosting (sklearn) | No | Some support | Encode (ordinal) |

---

## Cross-Validation Best Practices

All sklearn estimators work with `cross_val_score` and `GridSearchCV`.

```python
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.ensemble import RandomForestClassifier

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
scores = cross_val_score(
    RandomForestClassifier(n_estimators=200, n_jobs=-1),
    X, y, cv=cv, scoring='roc_auc', n_jobs=-1
)
print(f"ROC-AUC: {scores.mean():.4f} +/- {scores.std():.4f}")
```

Use `StratifiedKFold` for classification to preserve class proportions across folds. Use `KFold` for regression. For time-series data, use `TimeSeriesSplit` to prevent future data leakage.

---

## Hyperparameter Search Strategy

### Grid Search

Exhaustively evaluates all combinations. Practical only for 1-3 hyperparameters.

```python
from sklearn.model_selection import GridSearchCV

param_grid = {'n_estimators': [100, 300], 'max_features': ['sqrt', 0.3]}
gs = GridSearchCV(RandomForestClassifier(), param_grid, cv=5, scoring='roc_auc', n_jobs=-1)
gs.fit(X_train, y_train)
print(gs.best_params_)
```

### Randomized Search

Samples a fixed number of parameter combinations from distributions. More efficient than grid search for many parameters.

```python
from sklearn.model_selection import RandomizedSearchCV
from scipy.stats import loguniform, randint

param_dist = {
    'n_estimators': randint(100, 500),
    'max_features': loguniform(0.1, 1.0),
    'max_depth': [None, 5, 10, 15]
}
rs = RandomizedSearchCV(RandomForestClassifier(), param_dist, n_iter=50,
                        cv=5, scoring='roc_auc', n_jobs=-1, random_state=42)
rs.fit(X_train, y_train)
```

For 4+ hyperparameters, prefer RandomizedSearchCV with n_iter=50-100 over GridSearchCV.