<!-- Source: https://developers.google.com/machine-learning/guides/rules-of-ml, https://developers.google.com/machine-learning/crash-course/overfitting/dividing-datasets, https://developers.google.com/machine-learning/crash-course/real-world-guidelines — fetched 2026-07-01 -->

# Machine Learning Best Practices

Core engineering principles for reliable, production-ready ML systems drawn from Google's Rules of Machine Learning and Google ML Crash Course.

---

## Data Splitting Strategy

### Three-Part Split (Standard)

Always divide data into three disjoint subsets:

| Split | Typical Size | Purpose |
|-------|-------------|---------|
| Training | ~70% | Model learns parameters |
| Validation | ~15% | Hyperparameter tuning and model selection during development |
| Test | ~15% | Single final evaluation after all decisions are made |

- Shuffle data before splitting to remove ordering bias.
- Never use test-set results to guide model changes — each time validation or test results inform a model tweak, those sets become less reliable as unbiased estimators.
- Refresh validation/test sets periodically when the dataset evolves.

### Requirements for Valid Test and Validation Sets

- Large enough for statistically significant conclusions.
- Representative of both the training distribution and real-world deployment conditions.
- Zero examples duplicated in the training set.
- Free from any temporal or structural leakage between splits.

### Cross-Validation

Use k-fold stratified cross-validation when data is scarce. It is more rigorous than a single holdout split and produces more stable performance estimates. Stratify by class label to preserve class proportions in each fold.

---

## Avoiding Data Leakage

Data leakage causes models to appear much stronger in evaluation than they are in production. Common sources:

- **Target leakage**: Features that contain information about the label that would not be available at prediction time (e.g., a "diagnosis confirmed" flag included as a feature when predicting diagnosis).
- **Train/test contamination**: Preprocessing steps (scaling, imputation, encoding) fitted on the full dataset before splitting. Always fit transformers on training data only, then apply to validation/test.
- **Temporal leakage**: Using future data to predict past events. When data has a time dimension, the split must respect chronological order — never shuffle before splitting a time series.
- **Indirect leakage**: Features indirectly correlated with the label through a confounder (e.g., hospital specialization predicting diagnosis category because certain hospitals only treat certain diseases).
- **Dynamic table leakage** (production): Features joined from tables that change over time create skew — what the model saw at training time differs from what is available at serving time. Snapshot or log serving-time feature values to close this gap.

**Rule**: audit every feature to confirm it would be available at the exact moment of prediction in production, with no knowledge of events after the prediction timestamp.

---

## Overfitting: Detection and Prevention

### Detection

- Track training loss vs. validation loss across epochs/iterations. Divergence (training loss continues falling while validation loss plateaus or rises) is the primary signal.
- Monitor metric delta between training data, holdout data, next-day data, and live predictions (training-serving skew). Large gaps signal engineering errors or overfitting to stale signals.
- Use learning curves: plot performance vs. training set size. High variance (large gap between train and val curves) indicates overfitting; high bias (both curves plateaued at poor performance) indicates underfitting.

### Prevention

- **Regularization**: L2 (weight decay) or L1 (sparsity) penalties on model parameters. Apply stronger regularization to features that cover few examples (rare features overfit easily).
- **Early stopping**: Halt training when validation metric stops improving.
- **Dropout / data augmentation**: For neural networks.
- **Simpler models first** (Google Rule #4, #14): Start with interpretable linear/logistic models. They are easier to debug, less prone to overfitting, and set a calibrated baseline. Add complexity only when simpler models demonstrably underfit.
- **Hold out positional features**: In ranking models, do not cross position with content features — position artificially inflates interaction rates and causes position-dependent overfitting.
- **Importance-weight sampled data** instead of dropping it: Arbitrary data removal introduces bias; use sampling weights (weight = 1/sampling_rate) to preserve calibration.

---

## Cross-Validation

- **k-fold CV**: Split training data into k folds; train k models each using k-1 folds, evaluate on the held-out fold. Average performance across folds.
- **Stratified k-fold**: Maintain class proportions in every fold. Required for imbalanced datasets.
- **Time-series CV (walk-forward)**: For temporal data, each fold trains on past data and validates on the immediately following window. Never allow future data into the training window.
- After cross-validation selects a configuration, retrain on the full training set and evaluate once on the test set.

---

## Training-Serving Skew

Production models fail silently when serving conditions differ from training conditions.

- **Schema skew**: Training and serving data arrive in different formats or with different feature ranges. Apply identical schema validation and data contracts to both pipelines.
- **Feature skew**: Feature engineering code diverges between offline training and online serving. **Reuse the same code** (Rule #32) — never maintain separate implementations.
- **Log serving-time features** (Rule #29): Save actual feature values used during prediction and pipe them back to training logs. This is the only way to guarantee training and serving use identical data.
- **Test on post-cutoff data** (Rule #33): Always evaluate the final model on data with timestamps after the training cutoff. Performance should degrade gracefully, not collapse — a collapse signals temporal leakage.

### Measuring Skew (Rule #37)

Track these gaps in sequence:

1. Training data vs. holdout data
2. Holdout data vs. next-day data
3. Next-day data vs. live predictions

Large gaps at any level indicate engineering errors or time-sensitive features that have become stale.

---

## Data Drift and Monitoring

- **Define a data schema**: Set expected ranges, allowed categorical values, and distribution bounds for every feature. Alert when incoming data violates schema.
- **Silent failures** (Rule #10): Degraded data quality (stale tables, reduced feature coverage, changed upstream sources) may not cause obvious errors but will slowly erode model performance. Instrument feature coverage and distribution statistics.
- **Slice-level monitoring**: Monitor metrics separately across important data subsets (region, user cohort, product category). Aggregate metrics can mask degraded performance on critical slices.
- **Model freshness** (Rule #8): Determine how quickly performance degrades on stale models (day-old, week-old). Set retraining schedules and staleness alerts accordingly.
- **Live quality signals**: When serving data lacks ground-truth labels, use human raters, user feedback signals, or gradual rollout (validate on a query subset before full deployment) to catch quality regressions.

---

## Reproducibility

- **Seed all random number generators** at the start of every experiment (data shuffling, train/test split, model initialization, dropout). Record the seed with results.
- **Version datasets**: Tag the exact dataset snapshot used for each experiment. Re-running on a refreshed dataset invalidates comparisons.
- **Deterministic splits via hashing** (production): Use invariant hash keys (e.g., query + log date, not current timestamp) to assign examples to train/eval splits. This prevents data leakage across time periods and ensures consistent distribution across experimental runs.
- **Pin dependency versions**: Record library versions (scikit-learn, XGBoost, etc.) alongside model artifacts. Different versions can produce different results for the same code.
- **Infrastructure tests** (Rule #5): Validate data ingestion and feature pipelines independently from ML logic. Confirm that the model score in training environment matches the score in serving environment on the same example.

---

## Production Readiness Checklist

- [ ] Data schema validated for training and serving inputs
- [ ] No leakage between train/validation/test splits confirmed
- [ ] Serving-time features logged and matched to training features
- [ ] Performance gate (AUC or metric threshold) checked before export (Rule #9)
- [ ] Training-serving skew measured and within acceptable bounds
- [ ] RNG seeds recorded; results are reproducible from seed + dataset snapshot
- [ ] Monitoring in place for feature distribution drift and slice-level performance
- [ ] Model freshness threshold defined and staleness alert configured
- [ ] Gradual rollout plan defined; rollback procedure documented
