# Imbalanced Data in Machine Learning

## What Is Imbalanced Data

Imbalanced data refers to a classification dataset where the number of samples in each class differs substantially. The majority class dominates the dataset while one or more minority classes are underrepresented. This is one of the most common real-world problems in applied machine learning.

### Class Ratio and Severity

The degree of imbalance is typically expressed as a ratio or percentage split between classes:

- **Mild imbalance**: 80/20 or 75/25 split — most standard algorithms can handle this with minor adjustments.
- **Moderate imbalance**: 90/10 or 85/15 — begins to cause meaningful degradation in minority class performance.
- **Severe imbalance**: 95/5 or 99/1 — standard training procedures almost always fail to learn minority class patterns.
- **Extreme imbalance**: 99.9/0.1 — requires specialized techniques and careful metric selection.

A 95/5 split means that for every 95 majority class samples, there are only 5 minority class samples. At this ratio, a naive classifier that predicts the majority class for every sample achieves 95% accuracy — which is high but completely uninformative.

### Common Real-World Examples

- Fraud detection: fraudulent transactions may represent 0.1–1% of all transactions.
- Medical diagnosis: patients with a rare disease may be 1–5% of a screened population.
- Fault detection in manufacturing: defective items may be 0.5–2% of total production.
- Churn prediction: churned users might be 5–15% of the user base.
- Intrusion detection: malicious network packets may be <1% of all traffic.

---

## Why Accuracy Is Misleading for Imbalanced Data

### The Accuracy Paradox

Accuracy is defined as the fraction of correct predictions over all predictions. For a dataset with 950 majority class samples and 50 minority class samples (95/5 split), a model that predicts the majority class for every single input achieves 95% accuracy without learning anything useful.

The core problem is that accuracy treats all errors equally. In most imbalanced settings, misclassifying the minority class (a false negative) carries a much higher cost than misclassifying the majority class (a false positive). A fraud detection system that misses 90% of actual fraud cases but flags nothing is not a good system — even if its accuracy is 99.9%.

### What Accuracy Hides

- **False negative rate**: The proportion of actual positives predicted as negatives. In medical settings, a false negative means a sick patient is told they are healthy.
- **Class-level performance**: A model with 95% accuracy might have 0% recall on the minority class — it has never once correctly identified a minority sample.
- **Distributional shift**: If deployment data has a different class ratio than training data, accuracy changes without reflecting model quality change.

### The Right Framing

For imbalanced problems, always report per-class metrics alongside aggregate ones. Precision, recall, F1-score broken down by class reveal what accuracy conceals.

---

## Oversampling Techniques

Oversampling increases the number of minority class samples to balance the class distribution. This is done either by duplicating existing minority samples (naive oversampling) or by generating new synthetic samples.

### Random Oversampling

The simplest approach: duplicate randomly selected minority class samples until the desired ratio is reached. This is fast and requires no assumptions, but it can lead to overfitting because the model sees the exact same samples repeated many times.

### SMOTE — Synthetic Minority Oversampling Technique

SMOTE generates new synthetic minority samples by interpolating between existing minority class instances and their nearest neighbors in feature space.

**Algorithm:**

1. For each minority class sample x, find its k nearest neighbors among other minority class samples.
2. Randomly select one of these k neighbors, call it x_n.
3. Generate a synthetic point along the line segment between x and x_n: x_synthetic = x + lambda * (x_n - x), where lambda is drawn uniformly from [0, 1].
4. Repeat until the desired class balance is achieved.

**Key parameter — k_neighbors:** The number of nearest neighbors used to generate synthetic samples. Default is typically 5. Smaller k (e.g., 2–3) creates synthetic samples that stay close to existing minority points, reducing the risk of generating samples in majority class regions. Larger k (e.g., 8–10) allows more diversity but increases the chance of overlap with majority class territory. In very small minority classes (fewer than 10 samples), k_neighbors must be set smaller than the minority class size minus one.

**Strengths:**
- Reduces overfitting compared to random oversampling.
- Creates plausible interpolated samples.
- Works well when minority class clusters are compact.

**Weaknesses:**
- Can generate noisy samples if minority class is scattered.
- Does not consider majority class distribution — may generate samples in majority-dominated regions.
- Not suitable for categorical features without modification (use SMOTENC for mixed data).

**Typical usage with imbalanced-learn:**

```python
from imblearn.over_sampling import SMOTE

smote = SMOTE(sampling_strategy='auto', k_neighbors=5, random_state=42)
X_resampled, y_resampled = smote.fit_resample(X_train, y_train)
```

`sampling_strategy='auto'` resamples the minority class to match the majority class count. You can also pass a float (e.g., 0.5 means minority class becomes 50% of majority class size) or a dict specifying exact target counts per class.

### ADASYN — Adaptive Synthetic Sampling

ADASYN is an extension of SMOTE that generates more synthetic samples in regions where the minority class is harder to learn — specifically, where the local neighborhood contains a higher density of majority class samples.

**Algorithm:**

1. Compute the ratio r_i for each minority sample: the fraction of its k nearest neighbors that belong to the majority class.
2. Normalize to get a density distribution d_i = r_i / sum(r_i).
3. Generate more synthetic samples in regions with high r_i (harder to classify) and fewer in regions with low r_i (easier to classify).

**When ADASYN outperforms SMOTE:** When the minority class has a complex, non-uniform distribution and some regions are more decision-boundary-critical than others. ADASYN focuses synthetic generation effort on the hard cases.

**Limitation:** More sensitive to noise than SMOTE. If minority class samples near the majority class boundary are outliers, ADASYN amplifies them.

---

## Undersampling Techniques

Undersampling reduces the majority class to bring the class distribution closer to balance. It is faster than oversampling (smaller dataset) and avoids synthetic data, but discards potentially useful majority class information.

### RandomUnderSampler

Randomly removes majority class samples until the target ratio is reached. Fast and simple. The risk is discarding informative majority class samples.

```python
from imblearn.under_sampling import RandomUnderSampler

rus = RandomUnderSampler(sampling_strategy=0.5, random_state=42)
X_resampled, y_resampled = rus.fit_resample(X_train, y_train)
```

`sampling_strategy=0.5` means the minority class will be 50% of the majority class after resampling (not 50% of the total).

### Tomek Links

A Tomek link is a pair of samples (one from each class) that are each other's nearest neighbor but belong to different classes. These pairs represent ambiguous, borderline examples close to the decision boundary.

Removing the majority class sample from each Tomek link cleans the boundary between classes without drastically reducing the majority class size. This is typically used as a cleaning step rather than a balancing step.

**Effect:** Sharpens the decision boundary. Does not produce a balanced dataset on its own — majority class is only slightly reduced. Often used after SMOTE to clean the synthetic samples that land near the boundary.

### Edited Nearest Neighbors (ENN)

Removes samples whose class differs from the majority class among their k nearest neighbors. More aggressive than Tomek links. Can be used to clean both classes or only the majority class.

### NearMiss

A family of heuristic undersampling methods that select majority class samples based on their distance to minority class samples:

- **NearMiss-1**: Keeps majority samples with the smallest average distance to the k nearest minority samples.
- **NearMiss-2**: Keeps majority samples with the smallest average distance to the k farthest minority samples.
- **NearMiss-3**: For each minority sample, keeps a fixed number of the closest majority samples.

---

## The class_weight Parameter in Sklearn

Many sklearn estimators accept a `class_weight` parameter that adjusts the loss contribution of each sample based on its class. This is the simplest and often most practical approach for handling imbalance.

### class_weight='balanced'

When set to `'balanced'`, sklearn automatically computes weights as:

```
weight_i = n_samples / (n_classes * n_samples_in_class_i)
```

For a 95/5 split with 1000 samples (950 majority, 50 minority, 2 classes):
- Majority class weight: 1000 / (2 * 950) ≈ 0.526
- Minority class weight: 1000 / (2 * 50) = 10.0

This means each minority class sample contributes 10 / 0.526 ≈ 19x more to the loss than a majority class sample. The model is penalized heavily for misclassifying minority samples.

**Estimators that support class_weight:**
- LogisticRegression
- RandomForestClassifier
- DecisionTreeClassifier
- SGDClassifier
- SVC (via class_weight parameter)
- XGBClassifier (via scale_pos_weight for binary classification)

**For XGBoost binary classification:**

```python
scale_pos_weight = n_negative / n_positive  # e.g., 950 / 50 = 19
xgb = XGBClassifier(scale_pos_weight=scale_pos_weight)
```

### Custom Class Weights

You can pass a dictionary with explicit weights:

```python
from sklearn.linear_model import LogisticRegression

model = LogisticRegression(class_weight={0: 1, 1: 10})
```

This gives minority class (label 1) ten times the loss weight of the majority class.

---

## When to Use Each Approach

### Use class_weight When:
- You want the simplest, least invasive adjustment.
- Training time is constrained (no resampling overhead).
- You are using tree-based or linear models with native support.
- The imbalance is mild to moderate (90/10 to 80/20).

### Use SMOTE When:
- The minority class is small but has reasonable structure (not just noise).
- You want to increase minority class diversity without duplicating exact samples.
- The imbalance is severe (95/5 or worse).
- You are using models that do not support class_weight (e.g., some neural network frameworks).

### Use ADASYN When:
- The minority class has non-uniform density and hard-to-classify boundary regions.
- You want adaptive focus on the most discriminative minority regions.
- You are willing to accept more noise in exchange for better boundary coverage.

### Use Undersampling When:
- The majority class dataset is very large and training time is a constraint.
- The majority class contains redundant, easily classifiable samples.
- You are prototyping and want fast iteration.

### Use Tomek Links When:
- As a post-processing cleaning step after SMOTE.
- To sharpen the decision boundary without major data loss.

---

## Combining SMOTE and Undersampling

Using SMOTE alone can produce synthetic minority samples near the boundary that overlap with majority samples, creating noise. A common and effective pipeline combines SMOTE with undersampling:

### SMOTETomek

Applies SMOTE to oversample the minority class, then applies Tomek link removal to clean ambiguous boundary samples from both classes.

```python
from imblearn.combine import SMOTETomek

smt = SMOTETomek(sampling_strategy='auto', random_state=42)
X_resampled, y_resampled = smt.fit_resample(X_train, y_train)
```

### SMOTEENN

Applies SMOTE then Edited Nearest Neighbors (ENN) to remove noisy samples. ENN is more aggressive than Tomek — it removes any sample misclassified by its k nearest neighbors.

```python
from imblearn.combine import SMOTEENN

smote_enn = SMOTEENN(random_state=42)
X_resampled, y_resampled = smote_enn.fit_resample(X_train, y_train)
```

### Recommended Pipeline Order

1. Split data into train/test first.
2. Apply resampling only to the training set — never to validation or test sets.
3. Apply SMOTE or SMOTEENN on the training fold during cross-validation.
4. Evaluate on the original (unmodified) validation set.

Failing to apply resampling inside the cross-validation loop leads to data leakage — synthetic samples generated from the full training set may leak information into validation folds.

---

## Evaluation Metrics for Imbalanced Data

### F1 Score

The harmonic mean of precision and recall:

```
F1 = 2 * (precision * recall) / (precision + recall)
```

Range: 0 to 1. A model must perform well on both precision and recall to achieve a high F1. Preferred over accuracy for imbalanced datasets because it focuses on the minority class performance.

**F-beta score** generalizes F1 with a beta parameter:

```
F_beta = (1 + beta^2) * (precision * recall) / (beta^2 * precision + recall)
```

- beta = 1: Equal weight to precision and recall (F1).
- beta = 2: Recall weighted twice as heavily as precision (use when false negatives are more costly).
- beta = 0.5: Precision weighted twice as heavily (use when false positives are more costly).

### AUC-ROC — Area Under the ROC Curve

The ROC curve plots True Positive Rate (recall) against False Positive Rate at all classification thresholds. AUC-ROC summarizes this as a single number.

- AUC = 1.0: Perfect classifier.
- AUC = 0.5: Random classifier (no better than chance).
- AUC = 0.0: Perfect inverse classifier.

AUC-ROC is threshold-independent, meaning it evaluates the model's ranking ability across all possible decision thresholds. It is less sensitive to class imbalance than accuracy because it measures relative ordering, not absolute counts.

**Limitation for severe imbalance:** At very high imbalance (99/1), AUC-ROC can remain high even when minority class recall is poor, because the False Positive Rate denominator (TN + FP) is large (dominated by majority class).

### AUC-PR — Precision-Recall Curve

Plots precision against recall at all thresholds. For imbalanced datasets, AUC-PR is often more informative than AUC-ROC because it focuses exclusively on the minority class performance.

A model with high AUC-PR correctly identifies minority class samples (high recall) without generating excessive false alarms (high precision).

**Rule of thumb:** Use AUC-PR when the positive (minority) class is what you care about and the class ratio is worse than 90/10.

### G-Mean — Geometric Mean

```
G-Mean = sqrt(sensitivity * specificity)
         = sqrt(TPR * TNR)
```

G-Mean balances performance on both classes. It is maximized only when the model classifies both classes well — a model that classifies majority class perfectly but minority class poorly will have a low G-Mean because TNR is high but TPR approaches zero.

Useful when you want balanced performance across all classes without specifying a threshold preference.

### Matthews Correlation Coefficient (MCC)

MCC produces a high score only if the classifier predicts both classes correctly in proportion. For binary classification:

```
MCC = (TP * TN - FP * FN) / sqrt((TP+FP)(TP+FN)(TN+FP)(TN+FN))
```

Range: -1 to +1. MCC = +1 is a perfect classifier, MCC = 0 is random, MCC = -1 is a perfect inverse classifier.

MCC is considered one of the most reliable single metrics for imbalanced binary classification.

---

## Threshold Tuning

By default, most classifiers use 0.5 as the probability threshold to assign the positive class. For imbalanced data, this default is often suboptimal.

### Why the Default Threshold Fails

A model trained on imbalanced data may output calibrated probabilities where most minority class samples receive probabilities in the range 0.1–0.4 — below the default 0.5 threshold. Lowering the threshold increases recall (more minority class samples captured) at the cost of precision.

### How to Tune the Threshold

1. Generate probability scores on the validation set.
2. Compute precision, recall, and F1 at a range of thresholds (e.g., 0.1 to 0.9 in steps of 0.01).
3. Select the threshold that optimizes the metric relevant to your use case.

```python
from sklearn.metrics import precision_recall_curve

prec, rec, thresholds = precision_recall_curve(y_val, y_prob)
f1_scores = 2 * prec * rec / (prec + rec + 1e-8)
best_threshold = thresholds[f1_scores.argmax()]
```

### Youden's J Statistic

An alternative threshold selection criterion:

```
J = TPR + TNR - 1 = sensitivity + specificity - 1
```

The threshold that maximizes J is the point on the ROC curve farthest from the diagonal. This balances sensitivity and specificity without needing to specify which is more important.

---

## Cost-Sensitive Learning

Cost-sensitive learning explicitly incorporates the misclassification cost into the learning process. Rather than assuming all errors are equally bad, a cost matrix defines the penalty for each type of error.

### Cost Matrix

For binary classification:

|                | Predicted Negative | Predicted Positive |
|----------------|-------------------|-------------------|
| Actual Negative | C(TN) = 0         | C(FP) = cost_fp   |
| Actual Positive | C(FN) = cost_fn   | C(TP) = 0         |

In fraud detection, a false negative (missed fraud) might cost $10,000 while a false positive (flagged legitimate transaction) costs $5 in investigation time. Setting cost_fn/cost_fp = 2000 reflects this.

### Implementation in Sklearn

The `class_weight` parameter approximates cost-sensitive learning when costs are inversely proportional to class frequency. For arbitrary cost matrices, use `sample_weight` in the estimator's `fit()` call:

```python
sample_weights = np.where(y_train == 1, cost_fn, cost_fp)
model.fit(X_train, y_train, sample_weight=sample_weights)
```

---

## SMOTE k_neighbors: Detailed Guidance

The `k_neighbors` parameter in SMOTE controls how many nearest minority class neighbors are considered when generating a synthetic sample.

### Effect of k_neighbors on Synthetic Sample Quality

- **k_neighbors = 1**: Synthetic samples are generated along the line between each minority sample and its single nearest neighbor. Produces dense, localized clusters. Risk of generating nearly identical samples.
- **k_neighbors = 3–5** (default): Balanced diversity. Samples span a small local neighborhood. Most commonly appropriate.
- **k_neighbors = 7–10**: More spread-out synthetic samples. Can fill gaps in sparse minority distributions but risks generating samples in majority class territory.

### Constraint: k_neighbors Must Be Less Than Minority Class Size

If the minority class has only 8 samples, you cannot set k_neighbors = 8 or higher. The constraint is k_neighbors < n_minority_samples. imbalanced-learn will raise an error if this is violated. In practice, for very small minority classes, set k_neighbors = min(5, n_minority - 1).

### Relationship to Noise

High k_neighbors in noisy, scattered minority classes can generate synthetic samples that bridge isolated minority class outliers — creating unrealistic samples in the feature space. In such cases, prefer k_neighbors = 3 or use ADASYN which weights generation away from noisy regions.

---

## Summary of Decision Rules

| Situation | Recommended Approach |
|-----------|---------------------|
| Mild imbalance (80/20), sklearn model | class_weight='balanced' |
| Moderate imbalance (90/10), any model | SMOTE + class_weight |
| Severe imbalance (95/5+), structured data | SMOTETomek or SMOTEENN |
| Very small minority class (<50 samples) | SMOTE with k_neighbors=3, class_weight |
| Noisy minority class | ADASYN or SMOTEENN |
| Large dataset, time-constrained | RandomUnderSampler + class_weight |
| Need clean decision boundary | Add Tomek links cleaning step |
| Evaluation: always | F1, AUC-PR; avoid accuracy alone |
