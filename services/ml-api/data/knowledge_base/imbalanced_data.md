<!-- Source: https://imbalanced-learn.org/stable/user_guide.html — fetched 2026-07-01 -->

# Handling Imbalanced Data (imbalanced-learn)

Standard accuracy is inappropriate for imbalanced datasets. The imbalanced-learn library provides sampling and ensemble strategies to address class imbalance.

---

## Over-Sampling Methods

Over-sampling increases minority class representation either by duplication or synthetic generation.

### RandomOverSampler
**What it does:** Duplicates minority class samples at random until the target ratio is reached.

**Key parameter:** `sampling_strategy` (ratio or dict of target class counts)

**When to use:** Simple baseline; small datasets; fast first attempt.

**Caveats:** No new information introduced — exact duplication significantly increases overfitting risk.

---

### SMOTE (Synthetic Minority Over-sampling Technique)
**What it does:** Generates synthetic samples by linear interpolation between a minority instance and one of its k nearest minority neighbors.

**Key parameters:**
- `k_neighbors` (default 5) — neighborhood size for interpolation
- `sampling_strategy` — target class ratio

**When to use:** Moderate imbalance; continuous feature space where interpolation is meaningful.

**Caveats:**
- May create synthetic samples overlapping with majority class regions
- Performs poorly with high-dimensional or sparse data
- Not safe for categorical features without preprocessing

---

### BorderlineSMOTE
**What it does:** SMOTE variant that focuses synthetic generation on minority samples near the decision boundary (the "danger zone").

**When to use:** Most minority class errors occur near class boundaries.

**Caveats:** Sensitive to noisy boundary samples; can amplify noise in borderline regions.

---

### SVMSMOTE
**What it does:** Uses an SVM decision boundary to identify support vectors and generates synthetic samples around them.

**When to use:** Complex, non-linear boundaries; medium-sized datasets.

**Caveats:** SVM fitting cost is high on large datasets.

---

### ADASYN (Adaptive Synthetic Sampling)
**What it does:** Generates more synthetic samples for minority instances that are harder to classify (surrounded by more majority neighbors), adapting density to local difficulty.

**Key parameter:** `n_neighbors` — neighborhood size for difficulty estimation

**When to use:** Non-uniform minority class difficulty; adaptive oversampling density desired.

**Caveats:** Can amplify noise in very dense majority regions; more sensitive to outliers than SMOTE.

---

## Under-Sampling Methods

Under-sampling reduces the majority class to rebalance the distribution.

### RandomUnderSampler
**What it does:** Randomly removes majority class samples until the target ratio is reached.

**Key parameters:** `sampling_strategy`, `replacement` (with/without replacement)

**When to use:** Large datasets where data loss is acceptable; fast baseline.

**Caveats:** Discards potentially important majority samples; information loss is irreversible.

---

### ClusterCentroids
**What it does:** Prototype generation — replaces majority class samples with K-means cluster centroids, reducing data size while preserving cluster structure.

**When to use:** Large datasets; want to preserve cluster-level majority class structure rather than raw samples.

**Caveats:** Centroids may not correspond to real data points; can distort feature distributions.

---

### TomekLinks
**What it does:** Removes majority class samples that form Tomek links — pairs of samples from opposite classes that are each other's nearest neighbor. Cleans the decision boundary.

**When to use:** Cleaning overlapping boundary regions; preprocessing step before other methods.

**Caveats:** Minimal undersampling on its own; primarily a cleaning technique, not a balancing technique.

---

### Edited Nearest Neighbours (ENN)
**What it does:** Removes majority samples that are misclassified by their k nearest neighbors, cleaning ambiguous majority instances.

**Key parameters:** `n_neighbors`, `kind_sel` ('all' or 'mode')

**When to use:** Cleaning noisy or overlapping majority regions to sharpen the decision boundary.

**Caveats:** Conservative — only removes clearly misclassified majority samples.

---

### Repeated ENN (RENN) and All KNN
**What it does:** Iterative application of ENN (RENN) or progressive k-neighborhood ENN (AllKNN) for more aggressive boundary cleaning.

**When to use:** When single-pass ENN leaves too much overlap.

**Caveats:** Computationally intensive; risk of removing too many majority samples in dense overlap zones.

---

### NearMiss
**What it does:** Heuristic undersampling — selects majority samples based on their distance to minority samples (three variants: NearMiss-1, -2, -3 with different selection strategies).

**When to use:** When the spatial relationship between classes should guide which majority samples to keep.

**Caveats:** Highly sensitive to noise and outliers; variant choice significantly affects results.

---

### Instance Hardness Threshold
**What it does:** Trains a classifier and removes majority samples with high predicted probability of being minority class (instances the classifier would already misclassify).

**When to use:** Dataset-specific cleaning based on actual classifier behavior.

**Caveats:** Requires fitting a classifier; threshold choice matters; adds computational cost.

---

## Combination Methods

Combines over-sampling of minority class with cleaning of the majority class.

### SMOTEENN
**What it does:** Applies SMOTE oversampling, then cleans the resulting dataset using Edited Nearest Neighbours.

**When to use:** Moderate imbalance with class overlap; want both synthetic generation and boundary cleaning.

**Caveats:** Cleaning step may remove some synthetic samples; two-step process requires more tuning.

---

### SMOTETomek
**What it does:** Applies SMOTE oversampling, then removes Tomek links from both classes.

**When to use:** Similar to SMOTEENN; Tomek removal is more conservative (fewer samples removed).

**Caveats:** Less aggressive cleaning than SMOTEENN; may leave more boundary overlap.

---

## Ensemble Methods for Imbalanced Data

These embed resampling inside an ensemble, removing the need for a separate sampling step.

### BalancedBaggingClassifier
**What it does:** Each bootstrap bag is balanced before training using an inner sampler; wraps any base classifier.

**Key parameters:** `estimator`, `sampling_strategy`, `replacement`, `n_estimators`

**When to use:** Moderate to high imbalance; need flexibility to use any base estimator.

**Caveats:** Each bag trains on a balanced but smaller training set; may underuse majority class information.

---

### BalancedRandomForestClassifier
**What it does:** Random forest where each tree trains on a balanced bootstrap sample (random undersampling of majority class per tree).

**Key parameters:** `n_estimators`, `max_features`, `sampling_strategy`

**When to use:** Tree-based modeling preferred; want interpretability (feature importance) with built-in imbalance handling.

**Caveats:** Undersampling per tree discards majority data; can underfit complex majority class structure.

---

### EasyEnsembleClassifier
**What it does:** Trains multiple AdaBoost classifiers, each on a different random undersampled majority class subset; aggregates predictions by averaging.

**Key parameters:** `n_estimators`, `base_estimator` (default: AdaBoostClassifier)

**When to use:** Severe class imbalance; diversity across undersampled subsets is beneficial.

**Caveats:** Multiple full model training runs; computationally expensive.

---

### RUSBoostClassifier
**What it does:** Integrates Random Undersampling (RUS) into each boosting round; undersamples majority class before fitting each weak learner.

**Key parameters:** `n_estimators`, `learning_rate`, `sampling_strategy`

**When to use:** Boosting approach preferred; sequential importance weighting aligns naturally with minority class focus.

**Caveats:** Undersampling at each round progressively reduces effective majority class sample size.

---

## Evaluation for Imbalanced Data

Standard accuracy is inappropriate. Recommended metrics:

| Metric | Why Use It |
|--------|------------|
| Balanced Accuracy | Macro-average recall; immune to class size effects |
| F1 / F-beta | Precision-recall tradeoff; beta > 1 when FN more costly |
| ROC-AUC | Threshold-independent ranking |
| Average Precision (PR-AUC) | Better than ROC-AUC when positives are very rare |
| MCC | Accounts for all four confusion matrix quadrants equally |

---

## Critical Rule: Avoid Data Leakage

Always fit samplers on training data only. Use `imblearn.pipeline.Pipeline` (not sklearn's) to ensure the sampler is applied inside each cross-validation fold, not before splitting.

```python
from imblearn.pipeline import Pipeline
pipe = Pipeline([('smote', SMOTE()), ('clf', RandomForestClassifier())])
cross_val_score(pipe, X, y, cv=StratifiedKFold(5))
```

---

## Method Selection Guide

| Situation | Recommended Approach |
|-----------|---------------------|
| Quick baseline | RandomOverSampler or RandomUnderSampler |
| Continuous features, moderate imbalance | SMOTE or ADASYN |
| Boundary overlap, need cleaning | SMOTEENN or SMOTETomek |
| Large dataset, compute constrained | RandomUnderSampler or BalancedRandomForestClassifier |
| Severe imbalance, need ensemble | EasyEnsembleClassifier or RUSBoostClassifier |
| Tree-based + built-in imbalance handling | BalancedRandomForestClassifier |
| Any base model + imbalance handling | BalancedBaggingClassifier |
