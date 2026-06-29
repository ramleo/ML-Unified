# Classification Metrics in Machine Learning

## Overview

Evaluating a classification model requires more than a single number. Different metrics capture different aspects of performance — some measure overall correctness, others focus on specific types of errors, and others provide threshold-independent views of discriminative ability. The appropriate choice depends on the class distribution, the cost of each error type, and the business problem being solved.

---

## Accuracy

### Definition

Accuracy is the fraction of predictions that are correct:

```
Accuracy = (TP + TN) / (TP + TN + FP + FN)
```

where TP = true positives, TN = true negatives, FP = false positives, FN = false negatives.

### When Accuracy Is Misleading

Accuracy is a reliable metric only when the class distribution is roughly balanced and the cost of all error types is equal. Both conditions frequently fail in practice.

**The accuracy paradox:** On a dataset with 95% majority class samples and 5% minority class samples, a model that always predicts the majority class achieves 95% accuracy. Yet it has 0% recall on the minority class — it has never once correctly identified a positive case. This is especially dangerous in:

- Fraud detection: missing fraud is costly.
- Medical screening: missing a disease is life-threatening.
- Anomaly detection: missing an anomaly defeats the entire purpose.

**When accuracy is acceptable:**

- Binary or multi-class datasets with near-equal class distribution.
- When all error types have identical cost.
- As a secondary metric alongside class-specific metrics.

---

## Confusion Matrix

### Structure

For binary classification, the confusion matrix is a 2x2 table:

```
                 Predicted Negative    Predicted Positive
Actual Negative       TN                    FP
Actual Positive       FN                    TP
```

- **True Positive (TP)**: Model predicts positive; actual is positive. Correct.
- **True Negative (TN)**: Model predicts negative; actual is negative. Correct.
- **False Positive (FP)**: Model predicts positive; actual is negative. Type I error.
- **False Negative (FN)**: Model predicts negative; actual is positive. Type II error.

### Reading the Confusion Matrix

All other classification metrics are derived from these four values. The confusion matrix is the ground truth from which precision, recall, F1, and many other metrics can be computed by hand.

A good model has high TP and TN counts, and low FP and FN counts. The relative importance of FP vs. FN depends entirely on the application domain.

### Multi-Class Confusion Matrix

For k classes, the confusion matrix is k x k. Entry (i, j) is the number of samples with actual class i predicted as class j. The diagonal contains correct predictions; off-diagonal entries are misclassifications.

---

## Precision

### Definition

Precision (also called Positive Predictive Value) measures: of all samples predicted as positive, what fraction are actually positive?

```
Precision = TP / (TP + FP)
```

Range: 0 to 1. Higher is better.

### Interpretation

Precision answers the question: "When the model raises an alarm, how often is it correct?" A precision of 0.85 means that 85% of positive predictions are genuine positives, and 15% are false alarms.

### When Precision Matters More

Precision is the priority when false positives are costly:

- **Spam detection**: Flagging a legitimate email as spam (FP) annoys the user and may cause missed important communication. Precision must be high.
- **Legal discovery**: Flagging an innocent document for manual review wastes reviewer time. High precision reduces unnecessary work.
- **Recommendation systems**: Recommending an irrelevant item (FP) degrades user experience.

### Precision-Recall Tradeoff

Increasing the classification threshold generally increases precision but decreases recall. A model that only fires on very high-confidence cases will have high precision but will miss many actual positives (low recall). This tradeoff is fundamental and cannot be eliminated — it can only be managed by choosing the appropriate operating point.

---

## Recall (Sensitivity)

### Definition

Recall (also called Sensitivity or True Positive Rate) measures: of all actual positive samples, what fraction did the model correctly identify?

```
Recall = TP / (TP + FN)
```

Range: 0 to 1. Higher is better.

### Interpretation

Recall answers: "Of all the genuine positives that exist, how many did the model find?" A recall of 0.90 means the model correctly identified 90% of actual positives, and missed 10% (false negatives).

### Specificity

Specificity is the true negative rate — the recall for the negative class:

```
Specificity = TN / (TN + FP)
```

High specificity means the model correctly identifies most negatives (few false positives). Sensitivity and specificity are the two standard clinical metrics for diagnostic tests.

### When Recall Matters More

Recall is the priority when false negatives are costly:

- **Medical diagnosis (cancer screening)**: Missing a patient with cancer (FN) has severe consequences. Recall must be maximized even at the cost of more false alarms.
- **Security intrusion detection**: Missing an actual intrusion (FN) is far worse than investigating a false alarm.
- **Child safety content detection**: Missing flagged content is unacceptable; over-flagging is a manageable inconvenience.

### The Fundamental Tradeoff

Any improvement in recall (lowering the threshold, flagging more samples as positive) tends to reduce precision (more FPs). There is no way to simultaneously maximize both unless the model is perfect. The right balance is a domain decision, not a modeling decision.

---

## F1 Score

### Definition

F1 is the harmonic mean of precision and recall:

```
F1 = 2 * (Precision * Recall) / (Precision + Recall)
   = 2*TP / (2*TP + FP + FN)
```

Range: 0 to 1. Higher is better.

### Why Harmonic Mean

The harmonic mean penalizes extreme imbalance between precision and recall more severely than the arithmetic mean. A model with precision = 1.0 and recall = 0.01 has an arithmetic mean of 0.505, implying reasonable performance. Its F1 score is only 0.02 — correctly reflecting that the model is useless.

### Interpretation

F1 = 0.85 means the model achieves a balance of 85% between precision and recall. It is the standard single-number summary for binary classification on imbalanced datasets.

### Limitation

F1 treats precision and recall as equally important. If one is more important than the other for your application, F-beta score is more appropriate.

---

## F-Beta Score

### Definition

F-beta generalizes F1 by introducing a parameter beta that controls the relative weight of recall vs. precision:

```
F_beta = (1 + beta^2) * (Precision * Recall) / (beta^2 * Precision + Recall)
```

### Beta Values and Their Meaning

- **beta = 1**: F1 score. Precision and recall are equally weighted.
- **beta = 2**: Recall is weighted twice as heavily as precision. Use when false negatives are more costly than false positives (medical diagnosis, fraud detection).
- **beta = 0.5**: Precision is weighted twice as heavily as recall. Use when false positives are more costly (spam filtering, legal review).

### Choosing Beta

The choice of beta should be driven by the cost ratio of FN to FP. If missing a positive case costs twice as much as a false alarm, use beta = 2. If a false alarm costs twice as much as a missed detection, use beta = 0.5.

---

## AUC-ROC — Area Under the ROC Curve

### The ROC Curve

The Receiver Operating Characteristic (ROC) curve plots the True Positive Rate (recall / sensitivity) on the y-axis against the False Positive Rate (1 - specificity) on the x-axis as the classification threshold varies from 0 to 1.

```
True Positive Rate (TPR) = TP / (TP + FN)    # same as recall
False Positive Rate (FPR) = FP / (FP + TN)   # 1 - specificity
```

At threshold = 0: all samples predicted positive → TPR = 1, FPR = 1.
At threshold = 1: all samples predicted negative → TPR = 0, FPR = 0.
The curve traces the path between these extremes.

### AUC — Area Under the Curve

AUC-ROC is the area under the ROC curve, computed by integrating over all thresholds.

- **AUC = 1.0**: Perfect classifier — achieves TPR = 1 with FPR = 0.
- **AUC = 0.5**: Random classifier — the ROC curve lies on the diagonal.
- **AUC < 0.5**: Systematically worse than random (inverting predictions would give AUC = 1 - original_AUC).

### Probabilistic Interpretation

AUC-ROC equals the probability that the model assigns a higher score to a randomly chosen positive sample than to a randomly chosen negative sample. This makes it a measure of ranking quality, independent of any specific threshold.

### Threshold Independence

AUC-ROC does not depend on the choice of classification threshold. It evaluates the model's ability to rank positives above negatives across all possible thresholds. This is useful for comparing models before committing to a decision threshold.

### Limitation for Severely Imbalanced Data

With extreme class imbalance (e.g., 99/1), AUC-ROC can be misleadingly high. A model with poor minority class recall may still have a high AUC-ROC because the FPR denominator (TN + FP) is dominated by the large number of true negatives. Even a model that catches only 30% of positives may achieve AUC = 0.92 on a 99/1 dataset.

---

## AUC-PR — Precision-Recall Curve

### The Precision-Recall Curve

The PR curve plots Precision on the y-axis against Recall on the x-axis as the classification threshold varies. Unlike ROC, which involves TN (and is thus affected by majority class size), the PR curve uses only TP, FP, and FN — quantities directly related to the minority (positive) class.

### Why AUC-PR Is Better for Imbalanced Data

True negatives do not appear in any PR curve metric. This means AUC-PR is not inflated by having many correctly classified majority class samples. A model must genuinely identify positives (high recall) without too many false alarms (high precision) to achieve a high AUC-PR.

A random classifier on a dataset with p% positive samples achieves AUC-PR = p (the baseline). On a 5% positive class dataset, random achieves AUC-PR = 0.05 — making it easy to see how much better a real model is.

### Interpreting AUC-PR

- AUC-PR = 1.0: Perfect precision and recall at all thresholds.
- AUC-PR = class prevalence rate (e.g., 0.05 for 5% minority): No better than random.
- The shape of the curve matters: a curve that is high and flat indicates robust performance across a range of thresholds; a curve that drops sharply indicates the model only performs well in a narrow threshold range.

### Decision Rule

Use AUC-PR instead of (or in addition to) AUC-ROC when:
- The positive class is the rare class and the metric of interest.
- Class imbalance is moderate to severe (worse than 90/10).
- The cost of false positives and false negatives differ substantially.

---

## Log Loss (Cross-Entropy Loss)

### Definition

Log loss (binary cross-entropy) measures the quality of probability estimates, penalizing confident wrong predictions heavily:

```
Log Loss = -(1/n) * sum(y_i * log(p_i) + (1 - y_i) * log(1 - p_i))
```

where y_i is the true label (0 or 1) and p_i is the predicted probability of the positive class.

### Properties

- **Range**: 0 to infinity. Perfect predictions give log loss = 0; completely wrong confident predictions give log loss → infinity.
- **Sensitive to calibration**: Predicting 0.9 when the true class is 1 gives lower loss than predicting 0.6. This rewards well-calibrated probability estimates.
- **Punishes overconfidence**: A prediction of 0.999 for a sample that turns out to be class 0 incurs a very large penalty. This prevents models from being recklessly confident.

### When to Use Log Loss

- When the predicted probabilities will be used downstream (e.g., as inputs to a decision system, expected value calculation, or ensembling).
- When probability calibration matters as much as ranking.
- As the training objective for logistic regression, neural networks, and gradient boosting classifiers.
- In competitions where probability predictions are scored (Kaggle uses log loss for probabilistic tasks).

---

## Matthews Correlation Coefficient (MCC)

### Definition

MCC is a correlation coefficient between observed and predicted binary classifications:

```
MCC = (TP * TN - FP * FN) / sqrt((TP+FP)(TP+FN)(TN+FP)(TN+FN))
```

Range: -1 to +1.

- **MCC = +1**: Perfect prediction.
- **MCC = 0**: No better than random.
- **MCC = -1**: Perfect inverse prediction (all positives predicted as negative, all negatives as positive).

### Why MCC Is Preferred for Imbalanced Data

MCC uses all four values of the confusion matrix (TP, TN, FP, FN) in a balanced way. It produces a high score only when the classifier performs well on both classes — it cannot be inflated by a majority-class-biased model.

Consider a 95/5 dataset where the model predicts majority class for everything:
- Accuracy = 0.95 (misleadingly high)
- F1 (minority class) = 0.0 (correctly low)
- MCC = 0.0 (correctly reflects no predictive value)

For comparison, if a model has TP=40, TN=900, FP=50, FN=10 on a 50/950 dataset:
```
MCC = (40*900 - 50*10) / sqrt((90)(50)(950)(910))
    = (36000 - 500) / sqrt(3,871,575,000)
    ≈ 35500 / 62221
    ≈ 0.571
```

MCC of 0.571 reflects a genuinely useful model that still has room for improvement.

### MCC vs. F1 Score

F1 ignores TN entirely — it only looks at TP, FP, and FN. MCC includes TN, giving it a more complete picture of binary classification performance. In most imbalanced scenarios, reporting both F1 and MCC is best practice.

---

## Multi-Class Averaging Strategies

When extending binary metrics (precision, recall, F1) to multi-class problems, there are three standard averaging strategies.

### Macro Averaging

Compute the metric independently for each class, then take the unweighted average:

```
F1_macro = (F1_class_0 + F1_class_1 + ... + F1_class_k) / k
```

**Effect**: Each class contributes equally to the average, regardless of how many samples it contains. A rare class with poor F1 will pull down the macro average significantly. This is the appropriate choice when all classes are equally important, including rare ones.

**Use when**: Every class matters equally; rare class performance must not be hidden by aggregation.

### Micro Averaging

Aggregate TP, FP, and FN across all classes, then compute the metric once from the totals:

```
Precision_micro = sum(TP_i) / sum(TP_i + FP_i)
Recall_micro    = sum(TP_i) / sum(TP_i + FN_i)
F1_micro        = harmonic mean of Precision_micro and Recall_micro
```

**Effect**: Larger classes dominate the metric because they contribute more TPs, FPs, and FNs. Micro-F1 equals accuracy when each sample belongs to exactly one class.

**Use when**: You care about overall system performance and larger classes are more important (e.g., a common class failing would have more impact).

### Weighted Averaging

Compute the metric per class, then take a weighted average where weights are proportional to the number of true samples in each class (support):

```
F1_weighted = sum(F1_i * n_i) / sum(n_i)
```

**Effect**: Combines macro and micro — rare classes contribute less but are not entirely ignored. Useful for imbalanced multi-class settings.

**Use when**: You want a single number that accounts for class frequency but does not completely ignore rare classes.

### Choosing the Right Average

| Situation | Recommended Average |
|-----------|---------------------|
| Balanced classes, all equally important | Macro |
| Imbalanced, overall system performance | Weighted or Micro |
| Imbalanced, rare class performance matters | Macro |
| Reporting alongside class-specific metrics | All three, for transparency |

---

## When to Optimize Precision vs. Recall

The choice between prioritizing precision or recall is a business and domain decision, not a modeling decision. Here are canonical examples:

### Optimize Recall When:

**Medical diagnosis (cancer screening)**
- A false negative means telling a sick patient they are healthy — the consequences can be fatal.
- The cost of a missed case (FN) far exceeds the cost of additional follow-up tests for a false positive (FP).
- Target: very high recall (0.95+), accept lower precision (0.3–0.6).

**Security threat detection**
- A missed intrusion (FN) can lead to data breach or system compromise.
- False alarms (FP) are handled by security analysts — costly but manageable.
- Target: recall > 0.90, precision can be lower.

**Child safety content moderation**
- Missing a piece of harmful content is unacceptable.
- Over-flagging for manual review is operationally burdensome but preferable.

### Optimize Precision When:

**Spam detection**
- Sending a legitimate email to spam (FP) is more disruptive than letting one spam through (FN).
- Users tolerate occasional spam but not missing important emails.
- Target: precision > 0.95, recall can be 0.7–0.8.

**Legal document review**
- Each flagged document requires expensive human review.
- Missing a few relevant documents is acceptable; wasting reviewer time on irrelevant ones is not.
- Target: precision > 0.85.

**Recommendation systems**
- Recommending an irrelevant item (FP) degrades trust.
- Missing a relevant item (FN) is invisible to the user.
- Target: precision-focused.

### Balanced Precision and Recall:

When costs of FP and FN are roughly equal, F1 score (beta=1) is appropriate. This is common in:
- General text classification
- Image classification
- Multi-class NLP tasks

---

## Putting It Together: Metric Selection Framework

### Step 1: Assess Class Balance

- Balanced (less than 70/30 split): accuracy, F1.
- Moderately imbalanced (70/30 to 90/10): weighted F1, AUC-ROC.
- Severely imbalanced (>90/10): AUC-PR, MCC, F1 on minority class.

### Step 2: Identify Error Costs

- FN >> FP cost: maximize recall, use F-beta with beta=2.
- FP >> FN cost: maximize precision, use F-beta with beta=0.5.
- Equal costs: F1, AUC-ROC.

### Step 3: Threshold or Ranking Task?

- If you need a final yes/no decision at a fixed threshold: F1, precision, recall, MCC at that threshold.
- If you are evaluating the model's ranking ability across all thresholds: AUC-ROC, AUC-PR.
- If probability quality matters: log loss.

### Step 4: Multi-Class Considerations

- All classes matter equally: macro F1.
- Larger classes drive business outcomes: micro or weighted F1.
- Report confusion matrix for full transparency.

---

## Summary Table

| Metric | Formula | Range | Best For |
|--------|---------|-------|----------|
| Accuracy | (TP+TN)/N | 0–1 | Balanced classes, equal error costs |
| Precision | TP/(TP+FP) | 0–1 | Minimizing false alarms |
| Recall | TP/(TP+FN) | 0–1 | Minimizing missed positives |
| F1 | 2PR/(P+R) | 0–1 | Balanced precision/recall |
| F-beta | (1+b²)PR/(b²P+R) | 0–1 | Asymmetric error costs |
| AUC-ROC | integral of ROC | 0–1 | Threshold-independent ranking |
| AUC-PR | integral of PR curve | 0–1 | Imbalanced, positive class focus |
| Log Loss | -mean(log p) | 0–inf | Probability calibration |
| MCC | correlation of CM | -1 to +1 | Imbalanced, balanced view |