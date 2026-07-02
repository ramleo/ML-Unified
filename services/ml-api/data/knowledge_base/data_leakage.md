# Data Leakage

## What Is Data Leakage

Data leakage occurs when information from outside the training distribution — typically from the target variable or future time periods — is used as a feature during training. The model learns a signal that won't exist at prediction time, producing deceptively good training/CV metrics but poor real-world performance.

Leakage is one of the most common reasons a model performs well in development but fails in production.

---

## Types of Leakage

### 1. Target Leakage

A feature is directly or indirectly derived from the target, but would not be known at prediction time.

**Example**: Predicting loan default. Feature `collection_letter_sent = 1` is added because it correlates strongly with default. But a collection letter is sent *because* the person defaulted — this feature wouldn't exist at the time you're trying to predict default.

**How to detect**: Features with suspiciously high correlation to the target. Features that "shouldn't" be available at prediction time. Test set performance dramatically worse than validation performance after deployment.

### 2. Train-Test Contamination

Preprocessing steps that depend on the full dataset (including test data) are applied before splitting. The test set "leaks" statistics into the training pipeline.

**Common mistakes**:
- Fitting `StandardScaler` on the full dataset before splitting
- Imputing missing values using the mean of the full dataset
- Fitting `SelectKBest` or PCA on the full dataset

**Correct approach**: Fit all preprocessing on training data only. Apply (transform) to validation/test data using training statistics.

```python
# Wrong
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)  # uses full dataset
X_train, X_test = train_test_split(X_scaled)

# Correct
X_train, X_test = train_test_split(X)
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)  # only transform, no fit
```

**Always use sklearn Pipelines** to prevent this — the pipeline fits only on training data within each CV fold.

### 3. Temporal Leakage

For time-series data, using future information to predict the past.

**Examples**:
- Shuffling before splitting (standard train_test_split on time-series)
- Using a 7-day rolling average that includes the current day's value
- Using data from `t+1` to predict `t`

**Correct approach**: Always sort by time, split chronologically. Use `TimeSeriesSplit` for cross-validation. When engineering lag features, ensure lags are strictly in the past.

### 4. Group Leakage

Multiple rows from the same entity (patient, user, session) appear in both train and test. The model memorizes entity-level patterns rather than generalizing.

**Example**: Medical dataset with 10 measurements per patient. Standard split puts some measurements from the same patient in train and test. The model learns patient-specific patterns (blood type, age) that inflate performance.

**Correct approach**: Use `GroupKFold` or `GroupShuffleSplit`, ensuring all rows from an entity are in the same fold.

### 5. Feature Leakage via Aggregation

Aggregated features (e.g., "average purchase amount for this customer") computed over the full dataset include test set rows.

**Correct approach**: Compute aggregations only from training data, or use proper fold-aware feature engineering.

---

## Detection Methods

### Check feature-target correlations
Unusually high correlation (>0.9) between a single feature and the target is suspicious — especially for features that "shouldn't" be that informative.

### Compare validation to production performance
If a model that scores 0.95 AUC in CV drops to 0.65 in production, leakage is the first thing to investigate.

### Permutation importance after deployment
If features that were important in training have near-zero importance on new data, they may have been leaky.

### Remove suspicious features and retrain
If removing a feature causes minimal drop in CV performance but the feature seemed too powerful, it was likely leaky.

---

## Pipelines Prevent Leakage

sklearn `Pipeline` ensures that all fitting (scaler, imputer, encoder, selector) happens only on the training fold within each CV split.

```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.ensemble import GradientBoostingClassifier

pipe = Pipeline([
    ("impute", SimpleImputer(strategy="median")),
    ("scale", StandardScaler()),
    ("model", GradientBoostingClassifier()),
])

# Safe: Pipeline fits imputer+scaler only on each training fold
scores = cross_val_score(pipe, X, y, cv=StratifiedKFold(5))
```

---

## Common Scenarios and Fixes

| Scenario | Leaky approach | Fix |
|----------|---------------|-----|
| Scaling | `fit_transform(X_full)` | Fit only on `X_train` |
| Imputation | Mean of full dataset | Mean of training fold only |
| Encoding | Frequency encoding on full dataset | Pipeline or training-only counts |
| Time series | `train_test_split(shuffle=True)` | Chronological split |
| Multi-row entities | Random split | `GroupKFold` |
| Target encoding | Encode with full `y` | Fold-aware target encoding |

---

## Key Rule

**Any transformation that uses information from the target or from data points outside the current training fold is leakage.** When in doubt, ask: "Would I have access to this feature at the moment I need to make a prediction in production?" If no — it's leakage.
