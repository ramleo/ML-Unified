<!-- Source: https://scikit-learn.org/stable/modules/ensemble.html — fetched 2026-07-01 -->

# Ensemble Methods (scikit-learn)

Ensemble methods combine predictions from multiple base estimators to improve generalizability and robustness. They reduce variance and/or bias by leveraging model diversity.

---

## Gradient Boosting

Builds an additive model sequentially; each new weak learner corrects errors of previous ones using gradient descent in functional space.

### Variants
- **HistGradientBoostingClassifier/Regressor** — histogram-based binning; orders of magnitude faster for n_samples > 10k; native categorical + missing value support
- **GradientBoostingClassifier/Regressor** — traditional implementation; better for small datasets

### Key Parameters
| Parameter | Description |
|-----------|-------------|
| `n_estimators` / `max_iter` | Number of boosting rounds |
| `learning_rate` | Shrinkage per step (recommended <= 0.1) |
| `max_depth` / `max_leaf_nodes` | Tree size control |
| `subsample` | Stochastic boosting sample fraction |
| `max_features` | Feature subsampling per split |
| `loss` | 'squared_error', 'absolute_error', 'huber', 'quantile' (regression); 'log_loss' (classification) |

### HistGBT-only Features
- `categorical_features` — native categorical support (no manual encoding needed)
- `monotonic_cst` — monotonic constraints per feature
- `interaction_cst` — restrict feature interactions
- Early stopping enabled by default when n_samples > 10k (`n_iter_no_change`, `validation_fraction`, `tol`)
- Built-in missing value handling (treated as a separate category)

### When to Use
- Default choice for tabular/structured data
- HistGBT for large datasets (>10k samples); GradientBoosting for small datasets

### Caveats
- HistGBT binning reduces split precision on very small datasets
- Monotonic constraints unsupported for categorical features or multiclass
- Computationally expensive vs. single models

---

## Random Forests & Extra Trees

Parallel ensemble using bootstrap aggregating (bagging) with random feature subsets. Trees are independent and trained simultaneously.

### Variants
- **RandomForestClassifier/Regressor** — best split within random feature subset
- **ExtraTreesClassifier/Regressor** — random thresholds at each split (lower variance, slightly more bias)
- **RandomTreesEmbedding** — unsupervised transformation via leaf indices

### Key Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_estimators` | 100 | Number of trees (more = better, diminishing returns) |
| `max_features` | 'sqrt' (clf) / 1.0 (reg) | Features per split |
| `max_depth` | None | Full tree development |
| `min_samples_split` | 2 | Min samples to split a node |
| `bootstrap` | True (RF) / False (ET) | Bootstrap sampling |
| `oob_score` | False | Out-of-bag error estimate |
| `n_jobs` | None | Parallelization (-1 = all cores) |

### When to Use
- High-variance problem is the main concern
- Quick, robust baseline for tabular data
- When interpretability via feature importance is needed

### Caveats
- Memory intensive with many deep trees; model size O(M x N x log N)
- Impurity-based `feature_importances_` biased toward high-cardinality features — use `permutation_importance` for reliable results
- HistGBT often outperforms on large datasets

---

## Bagging Meta-estimator

Trains multiple instances of any base estimator on random subsets; aggregates predictions to reduce variance.

### Variants by Sampling Strategy
| Variant | bootstrap | bootstrap_features |
|---------|-----------|-------------------|
| Bagging | True | False |
| Pasting | False | False |
| Random Subspaces | True/False | True |
| Random Patches | True | True |

### Key Parameters
- `estimator` — any base learner (KNN, SVM, decision tree, etc.)
- `n_estimators`, `max_samples`, `max_features` — subset sizes
- `oob_score` — out-of-bag evaluation

```python
BaggingClassifier(KNeighborsClassifier(), max_samples=0.5, max_features=0.5)
```

### When to Use
- Base estimator is complex and high-variance (e.g., deep trees, SVM)
- Need to wrap any arbitrary estimator (not just trees)

---

## AdaBoost

Sequential boosting: trains weak learners on reweighted data, giving higher weight to misclassified samples. Combines weak learners via weighted vote.

### Variants
- **AdaBoostClassifier** — AdaBoost.SAMME (multiclass)
- **AdaBoostRegressor** — AdaBoost.R2

### Key Parameters
- `n_estimators` — number of weak learners
- `estimator` — base learner (default: decision stump, depth=1)
- `learning_rate` — contribution scaling (default 1.0; reduce if overfitting)

### When to Use
- Weak learners as base estimators
- Iterative, bias-reduction focus

### Caveats
- Susceptible to noisy data and outliers (exponential loss amplifies them)
- Less robust than gradient boosting
- Base learner must perform better than random chance

---

## Voting Classifier/Regressor

Combines conceptually different estimators via majority vote or averaged probabilities. No interaction between estimators during training.

### Modes
- **Hard voting** — majority class label vote; ties resolved by ascending class order
- **Soft voting** — argmax of weighted average predicted probabilities (more powerful when calibrated)
- **VotingRegressor** — arithmetic average of predictions

### Key Parameters
- `estimators` — list of (name, estimator) tuples
- `voting` — 'hard' or 'soft'
- `weights` — per-estimator weights (applied to probabilities in soft voting)

```python
VotingClassifier(estimators=[('lr', clf1), ('rf', clf2)], voting='soft', weights=[2, 1])
```

### When to Use
- Diverse, equally-performing model types already available
- Quick combination without redesigning training pipeline

### Caveats
- Soft voting requires `predict_proba` from all estimators
- No learning interaction between models

---

## Stacking (Stacked Generalization)

Base estimators trained in parallel; their cross-validated predictions feed a meta-learner. Most expressive ensemble strategy.

### Process
1. Base estimators fit on full training data
2. Meta-learner trained on cross-validated outputs of base estimators
3. At inference: base estimator predictions → meta-learner → final output

### Key Parameters
- `estimators` — base layer (name, estimator) list
- `final_estimator` — meta-learner
- `stack_method` — output extraction: 'predict_proba', 'decision_function', 'predict', or 'auto'
- `cv` — cross-validation strategy for meta-learner training

```python
StackingRegressor(estimators=[('ridge', RidgeCV()), ('lasso', LassoCV())],
                  final_estimator=GradientBoostingRegressor())
```

### When to Use
- Diverse base models each predict well independently
- Maximum accuracy is the goal; compute cost is acceptable

### Caveats
- Computationally expensive (CV during training)
- Binary classification: first `predict_proba` column dropped (perfect collinearity)
- Multi-layer stacking adds complexity rapidly

---

## Comparison Summary

| Method | Training | Best For |
|--------|----------|----------|
| HistGradientBoosting | Sequential | Large tabular datasets (>10k) |
| GradientBoosting | Sequential | Small tabular datasets |
| Random Forest | Parallel | Fast baseline, interpretability |
| Extra Trees | Parallel | High randomness, faster training |
| Bagging | Parallel | Wrapping any complex estimator |
| AdaBoost | Sequential | Weak learner stacking |
| Voting | Parallel | Diverse model fusion |
| Stacking | Parallel + Sequential | Maximum accuracy, diverse models |

---

## Cross-Cutting Concepts

### Feature Importance
- `feature_importances_` on tree ensembles = mean impurity decrease (fast but biased toward high-cardinality features)
- `permutation_importance` = model-agnostic, more reliable, computed post-fit

### Out-of-Bag (OOB) Estimation
- Available when bootstrap sampling is used (`oob_score=True`)
- Useful for quick model selection; slightly pessimistic vs. cross-validation

### Warm Start
- `warm_start=True` on forest/boosting methods adds estimators to an existing fit
- Enables incremental training without retraining from scratch
