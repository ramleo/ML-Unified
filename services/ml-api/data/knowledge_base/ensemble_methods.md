# Ensemble Methods in Machine Learning

Ensemble methods combine multiple base models to produce a single predictive model that achieves better generalization than any individual learner. The central insight is that errors made by different models are often uncorrelated, so aggregating predictions cancels out individual mistakes. This document covers the four major ensemble paradigms: bagging, boosting, stacking, and voting.

---

## Bagging (Bootstrap Aggregating)

Bagging trains multiple base models in parallel, each on a bootstrap sample (sampling with replacement) of the training data. Predictions are aggregated by majority vote (classification) or averaging (regression). Because each model sees a slightly different dataset, the ensemble reduces variance without significantly increasing bias.

### Why Bagging Reduces Variance

High-variance models — typically deep decision trees — overfit individual training sets. When you average many such overfitted models trained on different bootstrap samples, the overfitting patterns cancel out because they are random and uncorrelated. The expected value of the average equals the true signal, while the variance shrinks by a factor proportional to 1/n (where n is the number of estimators), assuming independence.

Formally: Var(average of n models) = sigma^2 / n when models are uncorrelated. In practice, correlation between models reduces this gain, which is why diversity is critical.

### Random Forest

Random Forest extends bagging by also randomizing feature selection at each split. At each node, only a random subset of features is considered as split candidates. This additional randomization further decorrelates the trees, improving the variance reduction.

**Key hyperparameters:**
- `n_estimators`: number of trees; typical range 100–1000. More is generally better up to a point of diminishing returns. Start with 300.
- `max_features`: features considered per split. Default `sqrt(n_features)` for classification, `n_features/3` for regression. Reducing this increases diversity.
- `max_depth`: default is None (fully grown trees). Constraining depth (e.g., 10–20) can improve performance when features are noisy.
- `min_samples_leaf`: minimum samples at a leaf node. Increasing this (e.g., 2–10) smooths the model and prevents overfitting on small datasets.
- `bootstrap`: whether to use bootstrap samples. Setting to False trains each tree on the full dataset, which reduces diversity but can help on very small datasets.

**When to use Random Forest:**
- Tabular data with mixed feature types
- When you want a strong baseline with minimal tuning
- When interpretability via feature importance is needed
- Datasets with thousands to millions of rows
- When training speed matters (parallelizable across trees)

**Feature importance in Random Forest** is computed as the mean decrease in impurity (MDI) across all trees and splits. This can be biased toward high-cardinality features. Permutation importance is a more reliable alternative.

### Extra Trees (Extremely Randomized Trees)

Extra Trees (ExtraTreesClassifier / ExtraTreesRegressor in scikit-learn) pushes randomization further: instead of searching for the best split threshold among the random feature subset, it draws split thresholds randomly and picks the best among those random thresholds.

**Differences from Random Forest:**
- Split thresholds are random, not optimized — this makes training faster and increases diversity
- Uses the full training set (no bootstrap by default) — reduces variance from sampling but increases variance from threshold randomness
- Generally produces slightly higher bias but lower variance than Random Forest on the same dataset

**When Extra Trees outperforms Random Forest:**
- Very high-dimensional data where exhaustive threshold search is expensive
- When you need faster training at the cost of slight accuracy loss
- Datasets with many irrelevant features (the random thresholds act as additional regularization)

**Typical hyperparameters** are similar to Random Forest. A common configuration: `n_estimators=500`, `max_features='sqrt'`, `min_samples_leaf=1`.

---

## Boosting

Boosting trains base models sequentially. Each new model focuses on the errors of the previous ensemble. The result is a strong reduction in bias, at the cost of higher sensitivity to noisy data and longer training time. Boosting is generally the top-performing approach on structured/tabular data.

### How Boosting Reduces Bias

Bias arises when the model family is not expressive enough to capture the true function. Boosting fits a series of weak learners (typically shallow trees, depth 3–8) to the residuals of the current ensemble. Each learner corrects what the previous ones got wrong, progressively fitting a more complex function. The final prediction is a weighted sum of all weak learners.

### XGBoost

XGBoost (eXtreme Gradient Boosting) is a regularized gradient boosting framework. It adds L1 (alpha) and L2 (lambda) regularization to the leaf weights, uses second-order Taylor expansion of the loss for more accurate gradient estimates, and supports sparse data natively.

**Key hyperparameters:**
- `n_estimators`: number of boosting rounds; typically 100–3000. Always pair with early stopping.
- `learning_rate` (eta): shrinks each tree's contribution; typical range 0.01–0.3. Lower values need more trees.
- `max_depth`: tree depth; typical range 3–10. Shallower trees (3–6) are more common to reduce overfitting.
- `subsample`: fraction of training data per tree; typical 0.6–1.0. Adds stochasticity.
- `colsample_bytree`: fraction of features per tree; typical 0.5–1.0.
- `min_child_weight`: minimum sum of instance weights in a child; typical 1–10. Higher values prevent splits on rare samples.
- `gamma`: minimum loss reduction to make a split; typical 0–5. Acts as a pruning threshold.
- `alpha` / `lambda`: L1 / L2 regularization on leaf weights; typical 0–10.

**Early stopping:** Set `early_stopping_rounds=50` with a validation set. Training stops when validation metric does not improve for 50 consecutive rounds. This prevents overfitting and avoids manual tuning of `n_estimators`.

**Recommended starting configuration for a new dataset:**
```
learning_rate=0.05, n_estimators=1000, max_depth=5,
subsample=0.8, colsample_bytree=0.8, early_stopping_rounds=50
```

### LightGBM

LightGBM uses two innovations: Gradient-based One-Side Sampling (GOSS) retains samples with large gradients and randomly samples from those with small gradients, dramatically reducing training data without losing much information. Exclusive Feature Bundling (EFB) bundles mutually exclusive features (rarely nonzero simultaneously) to reduce feature dimensionality.

**Result:** LightGBM is 5–10x faster than XGBoost on large datasets while achieving comparable or better accuracy.

**Key differences from XGBoost:**
- Grows trees leaf-wise (best-first) rather than level-wise. This can achieve better loss reduction but risks overfitting on small datasets. Use `num_leaves` (default 31) to control complexity instead of `max_depth`.
- `num_leaves`: the primary complexity control; typical range 20–300. Keep below 2^max_depth.
- `min_child_samples`: minimum samples in a leaf; increase (e.g., 50–200) on large datasets to prevent overfitting.
- `feature_fraction` / `bagging_fraction`: analogous to XGBoost's colsample and subsample.

**When to prefer LightGBM:**
- Large datasets (>100K rows) where training speed is a bottleneck
- High-cardinality categorical features (LightGBM handles them natively with `categorical_feature`)
- Memory-constrained environments

### CatBoost

CatBoost (Categorical Boosting) addresses target leakage when encoding categoricals during boosting. Standard target encoding within gradient boosting causes leakage because the same sample is used to compute the encoding and to train the model. CatBoost uses ordered target statistics (computing encodings using only samples seen before the current one in a random permutation) to eliminate this leakage.

**Key advantages:**
- Native categorical handling without preprocessing — pass column names directly
- Symmetric (oblivious) trees: the same split is applied at every node of a given depth, which speeds up prediction and acts as regularization
- Strong out-of-the-box performance with less hyperparameter tuning
- GPU training with `task_type='GPU'`

**Key hyperparameters:**
- `iterations`: number of boosting rounds; typical 100–5000
- `learning_rate`: default auto-calculated from iterations; typical 0.01–0.15
- `depth`: tree depth; typical 4–10 (shallower than XGBoost due to symmetric trees)
- `l2_leaf_reg`: L2 regularization; typical 1–10
- `cat_features`: list of categorical column indices or names

**When to prefer CatBoost:**
- Datasets with many categorical features
- When you want to minimize preprocessing effort
- When ordered boosting (leak-free categoricals) is important for data integrity

---

## Stacking (Stacked Generalization)

Stacking uses a meta-learner that takes the predictions of multiple base models (level-0 models) as input features and learns to optimally combine them. Unlike simple averaging, the meta-learner can learn which base models to trust for which regions of the input space.

### Out-of-Fold (OOF) Prediction Mechanics

The critical challenge in stacking is that the meta-learner must be trained on predictions from the base models, but the base models cannot be trained and evaluated on the same data (this would cause severe overfitting in the meta-learner). The solution is out-of-fold predictions.

**OOF procedure:**
1. Split training data into K folds (typically 5 or 10).
2. For each fold k: train each base model on the other K-1 folds, then predict on fold k. This produces one prediction per training sample.
3. After all folds, every training sample has a prediction from a base model that never saw it during training.
4. Stack these OOF predictions as features for training the meta-learner.
5. For the test set: retrain each base model on the full training set, predict on test set. These test predictions become the meta-learner's test features.

This process ensures that the meta-learner is trained on unbiased predictions, preventing leakage from base model training data into meta-learner training.

**Example with 3 base models and 5-fold CV:**
- Training data: 10,000 samples
- OOF matrix: 10,000 x 3 (one column per base model)
- Meta-learner trains on this 10,000 x 3 matrix with original labels
- Test predictions: 3 columns from full-data-trained base models
- Meta-learner predicts on test 3-column matrix

### Meta-Learner Choices

The meta-learner should be a simple, regularized model to avoid overfitting the small OOF feature matrix.

**Classification:**
- `LogisticRegression(C=0.1)`: well-calibrated probabilities, fast, interpretable coefficients reveal which base models the meta-learner trusts
- `Ridge` applied to class probabilities: similar regularization, slightly different behavior
- `GradientBoostingClassifier` with low complexity: captures non-linear combinations, but risks overfitting on small OOF matrices

**Regression:**
- `Ridge(alpha=1.0)`: the standard choice; regularization prevents the meta-learner from over-trusting any single base model
- `Lasso`: performs implicit feature selection — can zero out weak base models entirely
- `ElasticNet`: combines both

**What to avoid as meta-learner:**
- Deep trees or high-complexity models (overfit the OOF matrix)
- Models without regularization (unregularized linear regression)
- The same model type as all base models (no diversity gain)

### When Stacking Beats Voting

Stacking outperforms simple voting when:
- Base models have heterogeneous strengths (e.g., a tree ensemble strong on structured patterns, a linear model strong on linear relationships, a kNN strong on local density)
- Some base models are systematically better on certain data regions (meta-learner can learn to weight them accordingly)
- Base models produce calibrated probability estimates (meta-learner has meaningful signal to learn from)

Stacking loses its advantage when:
- Base models are highly correlated (similar predictions, no complementary information)
- The dataset is very small (OOF predictions are noisy, meta-learner has little signal)
- All base models are similarly accurate (averaging is nearly as good and much simpler)

### Blending vs Stacking

**Blending** is a simpler alternative: hold out a fixed validation set (e.g., 20% of training data), train base models on the remaining 80%, predict on the holdout, train the meta-learner on those holdout predictions.

| Aspect | Blending | Stacking (OOF) |
|---|---|---|
| Data efficiency | Wastes holdout data | Uses all training data |
| Leakage risk | Lower (no CV complexity) | Requires careful implementation |
| OOF quality | Only one holdout split | K-fold, more stable estimates |
| Implementation complexity | Simple | Moderate |
| Typical performance | Slightly worse | Slightly better |

**Rule of thumb:** Use blending when you have abundant data and want simplicity. Use stacking (OOF) when data is limited or you want maximum performance.

---

## Voting

Voting combines base models by aggregating their predictions directly, without a learned meta-layer.

### Hard Voting

Each base model casts a vote for a class label. The final prediction is the class that receives the most votes (majority vote).

**Example:** Three classifiers predict [class A, class A, class B]. Hard vote result: class A (2 vs 1).

**When hard voting is appropriate:**
- Base models are not well-calibrated (probabilities are unreliable)
- Base models are very different in type (some cannot produce probabilities)
- Computational simplicity is required

### Soft Voting

Each base model outputs class probabilities. Probabilities are averaged across models, and the class with the highest average probability wins.

**Example:** Three classifiers predict probabilities for class A as [0.9, 0.7, 0.2]. Average: 0.6. If the threshold is 0.5, class A wins.

**Why soft voting is usually better than hard voting:**
- Hard voting treats a 51% probability model the same as a 99% probability model
- Soft voting weights confident predictions more heavily
- Soft voting can be interpreted as a probability estimate itself (useful for calibration)

**Requirement:** All base models must produce calibrated probabilities. Tree ensembles (Random Forest, GBM) may need Platt scaling or isotonic regression calibration before use in soft voting.

---

## Diversity: The Core Requirement for Ensemble Value

The statistical benefit of combining models depends on their predictions being uncorrelated. If all base models make the same errors, no ensemble method can correct them.

### Sources of Diversity

**Algorithm diversity:** Combine fundamentally different model families — gradient boosting, neural networks, linear models, kNN, support vector machines. Each has different inductive biases and makes different types of errors.

**Data diversity:** Bagging and random subspace methods create diversity by showing different data subsets to each model. This works best when individual models are high-variance.

**Feature diversity:** Use different feature subsets or transformations for different base models. One model might use raw features, another might use PCA components, another might use polynomial features.

**Hyperparameter diversity:** Train multiple instances of the same algorithm with different hyperparameters. For example, stack an XGBoost with depth=4 alongside one with depth=8. They will learn different aspects of the data.

### Measuring Diversity

**Disagreement measure:** The fraction of test samples where two classifiers disagree. Higher is better for ensemble performance (up to a limit where disagreement indicates unreliability).

**Q-statistic:** Measures statistical association between pairs of classifier errors. Lower Q means higher diversity, which predicts better ensemble performance.

**Correlation of predictions:** For regression, compute Pearson correlation between predictions of different base models. Ensembles of models with correlation below 0.7 typically show meaningful gains over individual models.

### Why Combining Similar Models Fails

If you train three Random Forest models on the same data with the same hyperparameters and average their predictions, you get minimal improvement over a single, larger Random Forest. The models are nearly identical — they make the same structural errors on the same samples. Adding more correlated models increases computational cost without improving accuracy. This is why simply bagging an already-bagged model (Random Forest) adds little value.

---

## When Ensemble Wins vs Single Model

### Scenarios Where Ensembles Are Worth the Complexity

- **Competitive accuracy is critical:** In ML competitions (Kaggle), ensembles routinely outperform single models by 0.5–2% on evaluation metrics, often the difference between top-10 and top-100 placements.
- **Prediction uncertainty:** Ensembles naturally produce uncertainty estimates — the variance across models' predictions indicates confidence. Single models require additional techniques (conformal prediction, Monte Carlo dropout) for this.
- **Different models capture different patterns:** When EDA reveals that some data regions follow different dynamics, an ensemble can deploy specialized models for each region via a learned meta-layer.
- **Asymmetric errors matter:** If false positives and false negatives have different costs, ensemble probability calibration can shift decision thresholds more reliably.

### Scenarios Where a Single Model Is Preferable

- **Inference latency constraints:** Ensembles multiply prediction time by the number of base models. A single LightGBM with 1000 trees predicts in ~5ms; a stack of 5 such models takes ~25ms.
- **Interpretability requirements:** SHAP values are well-defined for single models. Attributing a stacked ensemble's prediction to original features requires careful decomposition.
- **Training data is small (<1000 samples):** OOF predictions become noisy and the meta-learner overfits. A single well-regularized model is more stable.
- **Deployment complexity:** Maintaining, versioning, and monitoring 5+ models in production is operationally costly. A single model pipeline is easier to debug and retrain.
- **The single model already achieves near-ceiling performance:** If a well-tuned XGBoost reaches 98% accuracy, an ensemble might push it to 98.3% — rarely worth the added complexity.

### Decision Rule Summary

| Condition | Recommendation |
|---|---|
| Accuracy is the primary objective, data is abundant | Use stacking with diverse base models |
| Low latency required (<10ms per prediction) | Use single optimized model |
| Categorical features dominate | CatBoost or LightGBM single model often competitive |
| Small dataset (<1000 rows) | Single regularized model (Ridge, small RF) |
| Time series data | Caution with standard stacking — use time-series-aware CV |
| Uncertainty estimates needed | Ensemble (variance of predictions) |
| Production simplicity is valued | Single model |

---

## Practical Stacking Implementation Notes

### Number of Base Models

Three to seven base models is the typical sweet spot. Fewer than three provides limited diversity; more than seven rarely improves performance and dramatically increases training time. Prefer heterogeneous algorithms over many instances of the same algorithm.

### Feature Augmentation in Stacking

Beyond passing OOF predictions as meta-features, you can also pass:
- Original features alongside OOF predictions (gives meta-learner access to raw signal)
- OOF predictions from multiple CV runs with different random seeds (reduces variance in OOF estimates)
- Calibrated probabilities rather than raw probabilities (for classification)

### Preventing Target Leakage in Stacking

Always ensure:
- Base model OOF predictions on training data are generated without seeing the target for that fold
- The meta-learner sees only OOF predictions (not training predictions, which would be overfitted)
- Test predictions come from models retrained on the full training set (not from fold-specific models)
- No preprocessing steps (scaling, encoding) are fit on the full training set before the OOF split — they must be fit within each fold

### Multi-Level Stacking

Level-2 stacking (stacking on top of a stack) is theoretically possible but rarely improves results in practice. The OOF predictions become very noisy by the third level, and the meta-meta-learner has almost no signal to learn from. Use at most two levels, and only when you have a large dataset (>50K rows) and compelling reason.

---

## Summary of Ensemble Methods

| Method | Training | Aggregation | Primary Benefit | Main Risk |
|---|---|---|---|---|
| Bagging (Random Forest) | Parallel, bootstrap samples | Averaging / majority vote | Variance reduction | Does not reduce bias |
| Extra Trees | Parallel, full data, random splits | Averaging / majority vote | Faster training, more diversity | Slightly higher bias |
| Boosting (XGBoost/LightGBM/CatBoost) | Sequential, residual fitting | Weighted sum | Bias reduction | Sensitive to noise, overfitting |
| Stacking | Two-stage (base + meta) | Learned meta-model | Combines heterogeneous strengths | Complexity, OOF leakage risk |
| Hard Voting | Independent | Majority class vote | Simplicity | Ignores confidence |
| Soft Voting | Independent | Probability averaging | Confidence-weighted | Requires calibration |
