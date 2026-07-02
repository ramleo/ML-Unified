# Cross-Validation

## Why Cross-Validation

A single train/test split gives a noisy estimate of generalization performance — it depends heavily on which samples end up in each set. Cross-validation averages performance over multiple splits, reducing variance in the estimate without requiring more data.

## K-Fold Cross-Validation

Split data into K equal folds. Train on K-1 folds, evaluate on the held-out fold. Repeat K times, rotating which fold is held out. Final score = mean across K folds.

```
K=5 example (100 samples):
Fold 1: train on [21–100], eval on [1–20]
Fold 2: train on [1–20, 41–100], eval on [21–40]
...
```

**Choosing K:**
- K=5 or K=10 are standard. K=10 gives lower bias but higher compute.
- K=N (Leave-One-Out) is unbiased but extremely slow on large datasets and has high variance.
- K=3 is acceptable when data is very large (>100k rows) and compute is the bottleneck.

## Stratified K-Fold

For classification, ensures each fold has the same class distribution as the full dataset. Critical for imbalanced data — plain K-fold can accidentally put all minority samples in one fold.

Always use `StratifiedKFold` for classification tasks. `KFold` for regression.

## Repeated K-Fold

Run K-fold CV multiple times with different random seeds, average results. Reduces variance further. Useful when you need a very reliable estimate and have enough compute.

```python
from sklearn.model_selection import RepeatedStratifiedKFold
cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=42)
```

## Time-Series Cross-Validation

Standard K-fold shuffles data — this leaks future information into training when data has temporal order. Use time-based splits instead.

**TimeSeriesSplit**: Train on past, evaluate on future. Each successive fold expands the training window.

```
Split 1: train [t1–t100],  eval [t101–t120]
Split 2: train [t1–t120],  eval [t121–t140]
Split 3: train [t1–t140],  eval [t141–t160]
```

Never shuffle time-series data before splitting. Never use future data as features without explicit lag engineering.

## Group K-Fold

When samples are not independent (e.g., multiple rows from the same patient, user, or experiment), standard K-fold can leak group-level information. `GroupKFold` ensures all rows from a group are in the same fold.

```python
from sklearn.model_selection import GroupKFold
cv = GroupKFold(n_splits=5)
for train_idx, val_idx in cv.split(X, y, groups=patient_ids):
    ...
```

## Nested Cross-Validation

Used when you need both hyperparameter tuning and an unbiased performance estimate.

- **Outer loop**: Estimates generalization performance (K-fold)
- **Inner loop**: Selects hyperparameters (K-fold on the training portion)

Without nesting, tuning on the validation set and reporting its score gives an optimistic (biased) estimate.

```python
# Outer CV gives the final score
outer_cv = StratifiedKFold(n_splits=5)
# Inner CV selects hyperparameters
inner_cv = StratifiedKFold(n_splits=3)
clf = GridSearchCV(estimator=model, param_grid=params, cv=inner_cv)
scores = cross_val_score(clf, X, y, cv=outer_cv)
```

## Common Mistakes

**Using the test set for model selection**: If you tune hyperparameters based on test set performance, the test set is no longer a valid estimate of generalization. Reserve the test set for final evaluation only.

**Not stratifying imbalanced data**: With 5% minority class and K=5, one fold might have 0 minority samples. Always stratify.

**Shuffling time-series**: Leads to data leakage. Future values appear in training set. Model appears to perform well but fails on real future data.

**Reporting mean without std**: CV score should be reported as `mean ± std` across folds. High std means the estimate is unreliable.

## Variance in CV Scores

High fold-to-fold variance indicates:
- Dataset is small (each fold is small → noisy estimate)
- Class imbalance (use stratified)
- Data has structure (groups, time) that needs a matching CV strategy

## CV vs Hold-Out

| | Hold-Out | K-Fold CV |
|---|---|---|
| Data efficiency | Low (train on 80%) | High (all data used for training across folds) |
| Variance of estimate | High | Low |
| Compute | Fast | K× slower |
| When to use | Very large datasets, deep learning | Tabular ML, model selection |

## Practical Recommendations

- Default to `StratifiedKFold(n_splits=5)` for classification
- Use `TimeSeriesSplit` for any temporal data
- Use `GroupKFold` when rows are not independent
- Report `mean ± std` of CV scores, not just mean
- Use nested CV when comparing algorithms — not just tuning one
