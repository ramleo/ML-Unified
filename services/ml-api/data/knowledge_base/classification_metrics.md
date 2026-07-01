<!-- Source: https://scikit-learn.org/stable/modules/model_evaluation.html — fetched 2026-07-01 -->

# Classification Metrics (scikit-learn)

---

## Accuracy Score

**Measures:** Fraction of predictions that exactly match the true label.

**Formula:** Accuracy = (1/n) x sum(1 if y_pred == y_true else 0)
- Multilabel: subset accuracy — all labels must match per sample.

**Range:** [0, 1]; higher is better.

**When to use:** Balanced datasets; quick baseline; all classes equally important.

**Caveats:**
- Misleading on imbalanced datasets — predicting the majority class always achieves high accuracy
- Does not distinguish between FP and FN error types

---

## Precision

**Measures:** Of all positive predictions made, the fraction that were actually correct.

**Formula:** Precision = TP / (TP + FP)

**Range:** [0, 1]; higher is better; 1.0 = zero false positives.

**When to use:** False positives are costly (spam detection, false alarms, over-diagnosis).

**Caveats:**
- Ignores false negatives entirely
- Can be gamed by rarely predicting positive
- Multiclass: specify `average='macro'/'micro'/'weighted'`

---

## Recall (Sensitivity / True Positive Rate)

**Measures:** Of all actual positives, the fraction the model found.

**Formula:** Recall = TP / (TP + FN)

**Range:** [0, 1]; higher is better; 1.0 = caught all positives.

**When to use:** False negatives are costly (disease detection, fraud, safety systems).

**Caveats:**
- Ignores false positives
- Can be gamed by always predicting positive
- Inverse tradeoff with precision as classification threshold changes
- Multiclass: specify `average` parameter

---

## F1 Score

**Measures:** Harmonic mean of precision and recall. Balanced view when both error types matter equally.

**Formula:** F1 = 2 x (Precision x Recall) / (Precision + Recall)

**Range:** [0, 1]; higher is better; 0 if either precision or recall is 0.

**When to use:** Imbalanced datasets; when both FP and FN carry real cost; general-purpose metric.

**Caveats:**
- Equal weighting of precision and recall may not match actual business costs
- Does not account for true negatives
- Multiclass: specify `average` ('macro', 'micro', 'weighted', 'samples')

```python
f1_score(y_true, y_pred, average='weighted')
```

---

## F-Beta Score

**Measures:** Generalization of F1 where beta controls the relative weight of recall vs. precision.

**Formula:** F_beta = (1 + beta^2) x (Precision x Recall) / (beta^2 x Precision + Recall)
- beta > 1: recall weighted more heavily than precision
- beta < 1: precision weighted more heavily than recall
- beta = 1: equivalent to F1

**When to use:** Asymmetric error costs; beta=2 when catching positives is twice as important as avoiding false alarms.

**Caveats:** Requires choosing beta; no built-in string scorer — use `make_scorer(fbeta_score, beta=2)`.

---

## ROC-AUC Score

**Measures:** Area under the Receiver Operating Characteristic curve. Probability that the model ranks a random positive higher than a random negative.

**Concept:** ROC curve plots True Positive Rate vs. False Positive Rate at every decision threshold. AUC integrates this curve.

**Range:** [0, 1]; 0.5 = random; 1.0 = perfect ranking; higher is better.

**When to use:**
- Binary classification with class imbalance
- Ranking/scoring behavior matters more than specific threshold performance
- Probability calibration evaluation

**Caveats:**
- Summarizes across all thresholds — may mask poor performance at the operating threshold
- Can be optimistic when FP and FN costs differ drastically
- Multiclass: supports `multiclass='ovr'` (one-vs-rest) or `'ovo'` (one-vs-one)

```python
roc_auc_score(y_true, y_scores)  # y_scores from predict_proba
```

---

## Average Precision (PR-AUC)

**Measures:** Area under the precision-recall curve. Weighted mean of precision values at each recall threshold.

**Formula:** AP = sum_n (R_n - R_{n-1}) x P_n

**Range:** [0, 1]; higher is better; baseline equals class prevalence (not 0.5).

**When to use:**
- Highly imbalanced binary classification; positive class is rare
- Information retrieval tasks
- Often more informative than ROC-AUC when positives are scarce

**Caveats:**
- Baseline depends on prevalence, not 0.5 like ROC-AUC
- Requires `predict_proba` or `decision_function`

```python
average_precision_score(y_true, y_scores)
```

---

## Confusion Matrix

**Measures:** Count of TP, TN, FP, FN (binary) or all class pairings (multiclass). Foundation for computing all other classification metrics.

**Structure (binary):** `[[TN, FP], [FN, TP]]`
- Entry (i, j) = samples of true class i predicted as class j

**When to use:** Detailed error analysis; understanding which classes are confused; manual metric computation.

**Caveats:**
- Raw counts depend on dataset size; normalize with `normalize='true'/'pred'/'all'`
- For multiclass with many classes, tables become unwieldy

```python
confusion_matrix(y_true, y_pred, normalize='true')
```

---

## Log Loss (Cross-Entropy Loss)

**Measures:** Penalizes confident wrong probability estimates. Evaluates calibration of predicted probabilities, not just class labels.

**Formula (binary):** LogLoss = -(1/n) x sum(y_i x log(p_i) + (1-y_i) x log(1-p_i))

**Range:** [0, inf); lower is better; 0 = perfect probability predictions.

**When to use:**
- Probability estimates matter (not just class labels)
- Model calibration is important
- Training/evaluation of probabilistic classifiers

**Caveats:**
- Heavily penalizes overconfident wrong predictions (unbounded)
- A single very confident wrong prediction can dominate the score
- Scoring API: `'neg_log_loss'`

```python
log_loss(y_true, y_proba)  # y_proba from predict_proba
```

---

## Matthews Correlation Coefficient (MCC)

**Measures:** Correlation between predicted and true binary labels. Only metric that gives equal importance to all four confusion matrix quadrants.

**Formula:** MCC = (TP x TN - FP x FN) / sqrt((TP+FP)(TP+FN)(TN+FP)(TN+FN))

**Range:** [-1, 1]; +1 = perfect; 0 = random; -1 = inverse (systematically wrong).

**When to use:**
- Severely imbalanced binary classification
- TP, TN, FP, FN all carry equal importance
- Single reliable scalar for imbalanced problems (preferred over F1 in some literature)

**Caveats:**
- Less intuitive to explain than precision/recall
- Multiclass extension exists but interpretation is more complex

```python
matthews_corrcoef(y_true, y_pred)
```

---

## Balanced Accuracy Score

**Measures:** Macro-average of per-class recall. Treats all classes equally regardless of their size.

**Formula:** BalAcc = (1/K) x sum_k [TP_k / (TP_k + FN_k)]
- Binary: (Sensitivity + Specificity) / 2
- `adjusted=True` rescales so that random guessing yields 0

**Range:** [0, 1] (unadjusted); higher is better; random baseline = 0.5 (binary) or 1/K (multiclass).

**When to use:**
- Imbalanced datasets where accuracy is misleading
- All classes should contribute equally to the final score
- Drop-in replacement for accuracy on skewed distributions

**Caveats:**
- Still affected by large within-class variability
- Different from weighted accuracy

---

## Multiclass Averaging Strategies

When extending binary metrics (precision, recall, F1) to multiclass via the `average` parameter:

| Strategy | Description | Use When |
|----------|-------------|----------|
| `'macro'` | Equal weight per class | All classes equally important; highlights minority class performance |
| `'weighted'` | Weight by class support | Class prevalence should matter; resembles accuracy behavior |
| `'micro'` | Aggregate TP/FP/FN globally | Sample-level view; equals accuracy for non-multilabel |
| `'samples'` | Per-sample average | Multilabel classification only |

---

## Metric Selection Guide

| Scenario | Recommended Metric |
|----------|--------------------|
| Balanced classes | Accuracy, F1 (macro) |
| Imbalanced, FP costly | Precision, ROC-AUC |
| Imbalanced, FN costly | Recall, F-beta (beta > 1) |
| Rare positive class | Average Precision (PR-AUC) |
| Probability calibration | Log Loss |
| All error types equal | MCC, Balanced Accuracy |
| General imbalanced binary | MCC or Balanced Accuracy + ROC-AUC |
