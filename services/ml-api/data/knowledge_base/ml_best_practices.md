# Machine Learning Best Practices

This document covers the foundational best practices that distinguish reliable, production-ready machine learning systems from experimental code. Adhering to these principles prevents the most common sources of inflated metrics, brittle models, and failed deployments.

---

## Data Splitting Strategy

The fundamental requirement for honest model evaluation is that no data used during training can influence the evaluation metric. Achieving this requires careful partitioning of available data.

### Train / Validation / Test Split

The standard three-way split reserves separate data for three distinct purposes:
- **Train set:** The model learns from this data directly.
- **Validation set:** Used during development to compare models, tune hyperparameters, and make architectural decisions.
- **Test set:** Touched exactly once at the end of the project to report final performance. Never used for any model selection decision.

**Common split ratios:**

| Dataset size | Train / Validation / Test |
|---|---|
| Small (<5K rows) | 60 / 20 / 20 |
| Medium (5K–100K rows) | 70 / 15 / 15 |
| Large (>100K rows) | 80 / 10 / 10 |
| Very large (>1M rows) | 90 / 5 / 5 |

For very large datasets, the absolute number of validation and test samples matters more than the percentage. Having 50,000 samples in each holdout set is sufficient for stable metric estimates regardless of total dataset size.

### Why the Test Set Must Be Treated as Sacred

Every time you use the test set to make a model selection decision, you are implicitly training on it. If you evaluate 20 models on the test set and pick the best one, the reported test accuracy is biased upward by the maximum of 20 random variables — this can easily inflate reported accuracy by 1–5% on small datasets. The validation set is for all iterative decisions. The test set measures generalization.

### Random vs Stratified Splitting

A random split works when:
- The target distribution is roughly uniform across classes
- The dataset is large enough that random sampling produces representative splits

A stratified split preserves the class distribution in each split. Always use stratified splits when:
- **Class imbalance exists:** If the minority class is 5% of the data, a random split might put 0% of the minority class in validation by chance on small datasets. `train_test_split(..., stratify=y)` in scikit-learn handles this.
- **Multi-label classification:** Stratify by a combination of labels or use specialized multi-label stratification libraries.
- **Regression with skewed targets:** Bin the target into quantiles and stratify by bins to ensure each split covers the full value range.

**Concrete example:** A fraud detection dataset with 2% fraud rate and 10,000 samples. A random 80/10/10 split might produce 200 fraud cases in training and only 20 in test — far too few for stable metric estimation. Stratified split guarantees approximately 200/25/25 fraud cases per split, matching the original 2% rate.

---

## Cross-Validation

Cross-validation (CV) provides a more reliable estimate of generalization performance than a single train/validation split, especially when data is limited.

### K-Fold Cross-Validation

The dataset is divided into K equal-sized folds. The model is trained K times, each time using K-1 folds for training and 1 fold for validation. The final performance estimate is the average across all K validation scores.

**Choosing K:**
- `K=5`: Standard choice. Good balance between variance and computational cost.
- `K=10`: Lower variance estimate, higher computational cost. Preferred when dataset is moderately small (<10K rows).
- `K=3`: Use when training is expensive (large datasets, deep learning). Less stable estimates.
- `K=N` (Leave-One-Out): Nearly unbiased but high variance and very expensive. Only appropriate for very small datasets (<100 samples).

**What CV score represents:** The CV score estimates the expected performance on new, unseen data drawn from the same distribution as the training data. It does not guarantee performance if the distribution shifts.

### Stratified K-Fold

Stratified K-Fold applies the same stratification principle to each fold, ensuring each fold has approximately the same class distribution as the full dataset. Always prefer `StratifiedKFold` over plain `KFold` for classification tasks.

**Implementation:** `sklearn.model_selection.StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`

### Time Series Cross-Validation

Standard K-Fold cross-validation is invalid for time series data because it allows future data to appear in the training set of a given fold (temporal leakage). Use TimeSeriesSplit instead.

**TimeSeriesSplit mechanics:**
- Fold 1: Train on weeks 1–4, validate on week 5
- Fold 2: Train on weeks 1–5, validate on week 6
- Fold 3: Train on weeks 1–6, validate on week 7
- Each subsequent fold trains on all previous data

**Walk-forward validation:** A more realistic variant where the training window has a fixed size (e.g., always the last 52 weeks), simulating a rolling production retrain schedule.

**Gap between train and validation:** When predicting h steps ahead, include a gap of h periods between the training end and validation start, preventing the model from seeing near-future data that was used to construct lag features.

### Nested Cross-Validation

When both model selection and performance estimation are needed, use nested CV to avoid optimistic bias:
- **Outer loop:** Provides an unbiased estimate of final model performance.
- **Inner loop:** Selects hyperparameters within each outer training fold.

This is computationally expensive (K_outer x K_inner total training runs) but produces the most honest performance estimate when the dataset is too small to hold out a separate test set.

---

## Data Leakage

Data leakage is the single most common cause of models that appear to work during development but fail in production. It occurs when information from outside the training data's legitimate scope influences the model.

### Target Leakage

Target leakage occurs when a feature is derived from the target variable or is only available after the target is known.

**Examples of target leakage:**
- Predicting loan default using `total_payments_missed` — this is known only after default occurs
- Predicting disease diagnosis using `treatment_type` — treatment is prescribed after diagnosis
- Predicting house sale price using `days_on_market` — houses that sell quickly at low prices affect both feature and target simultaneously

**Detection:** Features with unusually high correlation with the target (Pearson > 0.9) in training data should be investigated. If removing the feature causes a large drop in validation accuracy, it may have been carrying target-like information.

**Prevention:** Map each feature to the timestamp at which it would be available in a real deployment scenario. Only include features available at prediction time.

### Temporal Leakage

Temporal leakage occurs when future information is used to build features for past observations.

**Examples:**
- Using a global mean computed on the full dataset (including future samples) for normalization
- Computing rolling averages over a window that includes future data
- Encoding a categorical variable using statistics computed on the entire dataset

**Prevention:** All aggregations, statistics, and transformations must be computed only on data available at or before the current observation's timestamp. In a rolling window of 7 days, day 7's features must only use data from days 1–6.

### Preprocessing Leakage

Preprocessing leakage occurs when preprocessing steps (scaling, imputation, encoding) are fit on the combined training and test data, allowing test data statistics to influence training.

**Common mistake:**
```python
# WRONG — scaler sees test data statistics
scaler = StandardScaler()
X_all = np.vstack([X_train, X_test])
X_scaled = scaler.fit_transform(X_all)
X_train_scaled = X_scaled[:len(X_train)]
X_test_scaled = X_scaled[len(X_train):]
```

**Correct approach:**
```python
# CORRECT — scaler fit only on training data
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)  # transform only, not fit_transform
```

**Using scikit-learn Pipeline:** The Pipeline object automates this correctly. When you call `pipeline.fit(X_train, y_train)`, all transformers are fit on `X_train`. When you call `pipeline.predict(X_test)`, all transformers use their training-fitted parameters on `X_test`. Never call `fit_transform` manually outside a pipeline when a test set exists.

### Cross-Validation Leakage

Within cross-validation, preprocessing must be fit inside the fold loop, not before it.

**Wrong:** Fit a scaler on all training data, then run CV. The scaler has seen validation data from each fold.

**Right:** Include the scaler inside a `Pipeline` object passed to `cross_val_score`. The pipeline ensures the scaler is fit within each CV fold's training partition only.

---

## Overfitting: Signs and Remedies

Overfitting occurs when a model learns the training data (including its noise) so well that it fails to generalize to new samples.

### Signs of Overfitting

- Training accuracy / metric is substantially better than validation accuracy (gap >5% is often meaningful; gap >10% is severe)
- Validation loss increases while training loss continues to decrease (during neural network training)
- Model performs well on familiar data patterns but poorly on slight variations
- Feature importance shows the model relies heavily on features that should have no causal relationship to the target
- Learning curves show training error decreasing with more complexity, but validation error plateauing or increasing

**Learning curve diagnostic:** Plot training and validation scores as a function of training set size. An overfitting model shows a large gap between the two curves even at maximum training set size. The gap should narrow as more data is added.

### Remedies for Overfitting

**More data:** The most reliable fix. If doubling your dataset eliminates the train/validation gap, overfitting was the cause. Collect more samples or use data augmentation (valid for images, text, and time series; rarely valid for raw tabular data).

**Regularization:**
- L2 (Ridge): penalizes large weights; reduces sensitivity to individual features. Strength controlled by `alpha` (sklearn) or `lambda` (XGBoost). Start with alpha=1.0 and tune via CV.
- L1 (Lasso): penalizes absolute weight magnitude; drives irrelevant feature weights to exactly zero. Useful for implicit feature selection.
- ElasticNet: combines L1 and L2. Good when you have many features with some expected to be completely irrelevant.
- For tree models: reduce `max_depth`, increase `min_samples_leaf`, reduce `n_estimators` (for non-boosting trees), increase `min_child_weight`.

**Dropout (neural networks):** Randomly sets a fraction of activations to zero during each training forward pass. Typical rates: 0.2–0.5 for hidden layers. Forces the network to learn redundant representations and prevents co-adaptation of neurons.

**Early stopping:** Monitor validation loss during training and stop when it begins to increase. Set a patience parameter (e.g., 10–50 epochs or boosting rounds) to tolerate temporary fluctuations. Restore the model weights from the best validation epoch.

**Simpler model:** Reduce hypothesis space. Move from a 10-layer neural network to a 3-layer network, from a depth-10 tree to a depth-4 tree, from 1000-tree forest to 100-tree forest, from polynomial features to linear features. Simpler models have fewer parameters to overfit.

**Feature selection:** Remove irrelevant or redundant features. Each additional feature gives the model more opportunity to find spurious correlations in the training set. Use correlation analysis, mutual information, or embedded methods (LASSO, tree feature importance) to prune features.

**Cross-validation:** Use CV rather than a single train/validation split. CV provides a more stable estimate of whether overfitting is occurring across different data samples.

---

## Underfitting: Signs and Remedies

Underfitting occurs when the model is too simple to capture the true patterns in the data.

### Signs of Underfitting

- Both training and validation accuracy are poor (and approximately equal)
- Model performs similarly on training and test data, but both are far below a reasonable baseline
- Adding more training data does not improve performance
- Learning curve shows both training and validation error are high and plateau early
- Residuals (for regression) show systematic patterns — the model is missing a structural component

### Remedies for Underfitting

**More features:** Engineer features that capture interactions, nonlinearities, or domain knowledge that raw features miss. Polynomial features (x^2, x1*x2), log transforms, binning, and lag features for time series can all expose structure that simple models can learn.

**More complex model:** Move from linear regression to gradient boosting, from a shallow tree to a deeper tree, from 100 trees to 500 trees, from a small neural network to a larger one. Increase `max_depth`, decrease `min_samples_leaf`, reduce regularization strength.

**Less regularization:** If a regularized model underfits, reduce regularization. For Ridge: decrease `alpha`. For trees: decrease `min_child_weight`, increase `max_depth`. For dropout: reduce rate or remove.

**More training:** For neural networks and gradient boosting, train for more epochs or boosting rounds. Underfitting often means the optimization has not converged.

**Different algorithm:** Some data structures require specific algorithms. Linear regression cannot capture interaction effects without explicit feature engineering. If the decision boundary is highly nonlinear, a linear model will underfit regardless of the amount of data.

---

## Always Start with a Baseline Model

The baseline model establishes the minimum acceptable performance level. Any sophisticated model must beat the baseline to justify its complexity.

### What Constitutes a Baseline

**Classification baselines:**
- `DummyClassifier(strategy='most_frequent')`: always predicts the majority class. On a 90/10 split, this achieves 90% accuracy — far above random chance, revealing whether a model truly learns anything.
- `DummyClassifier(strategy='stratified')`: predicts classes randomly according to their prior probability. Useful for balanced accuracy metric.
- Logistic regression with default hyperparameters on raw features.

**Regression baselines:**
- `DummyRegressor(strategy='mean')`: always predicts the training mean. Achieves R^2 = 0 by definition.
- Predicting the previous time step's value (for time series): a "naive" forecast.
- Linear regression on the most correlated single feature.

**Why this matters:** Without a baseline, you cannot know whether your model is doing anything useful. A model achieving 95% accuracy sounds good until you realize a dummy classifier also achieves 95% on the same dataset.

### Baseline Escalation Pattern

1. Dummy baseline (no learning)
2. Logistic / Linear regression (linear learning)
3. Decision tree (nonlinear, interpretable)
4. Random Forest (strong nonlinear baseline)
5. Gradient boosting (XGBoost / LightGBM) — state-of-the-art for tabular data
6. Ensemble / Stacking — final performance squeeze

Each step should show measurable improvement. If a step does not improve over the previous, the complexity it adds is not justified by the data.

---

## Reproducibility

Scientific and production ML requires that results can be reproduced exactly from the same data and code.

### Random Seeds

Set seeds everywhere randomness is present:
- `numpy.random.seed(42)` — affects numpy operations
- `random.seed(42)` — affects Python's built-in random module
- Framework-specific: `torch.manual_seed(42)`, `tf.random.set_seed(42)`
- All scikit-learn estimators that have a `random_state` parameter: pass `random_state=42`
- `train_test_split(..., random_state=42)`
- `KFold(..., shuffle=True, random_state=42)`

**Convention:** `42` is widely used but the specific value does not matter. What matters is that the value is fixed and documented.

### Environment Reproducibility

Record the full dependency list with exact versions (`pip freeze > requirements.txt` or use `poetry.lock`). Model weights, hyperparameters, and training configuration should be logged (use MLflow, Weights & Biases, or simple JSON files). The random seed alone is insufficient if library versions change — NumPy and scikit-learn may change default behavior across versions.

### Data Versioning

Log the dataset hash (SHA-256 of the training CSV, for example) alongside every experiment. If the dataset changes, the hash changes, and you know not to compare experiments across different data versions.

---

## Preprocessing Pipeline: Fit on Train Only

The single most important implementation rule for preventing preprocessing leakage is: all preprocessing transformers must be fit exclusively on training data and applied to all data splits using the fitted parameters.

### What This Means in Practice

**StandardScaler:**
- Fit: compute mean and standard deviation from training data only
- Transform train: subtract training mean, divide by training std
- Transform val/test: subtract the same training mean, divide by the same training std
- The val/test mean and std are never computed or used

**SimpleImputer:**
- Fit: compute median (or mean, or mode) from training data only
- Fill training missing values with training median
- Fill val/test missing values with the same training median
- Val/test missing values are not used to compute the fill value

**OrdinalEncoder / OneHotEncoder:**
- Fit: learn the category vocabulary from training data
- Transform: apply learned vocabulary; handle unknown categories with `handle_unknown='ignore'` or `handle_unknown='use_encoded_value'`
- New categories in test data that weren't in training should be mapped to a special "unknown" category, not recalculate the encoding

**Target Encoding:**
- Particularly dangerous for leakage. Must be computed inside the cross-validation fold loop using only the training partition of each fold. Never compute target statistics on the full training set before splitting.

### Pipeline Construction

A scikit-learn Pipeline ensures correct fit/transform discipline automatically:

```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.ensemble import GradientBoostingClassifier

pipeline = Pipeline([
    ('imputer', SimpleImputer(strategy='median')),
    ('scaler', StandardScaler()),
    ('model', GradientBoostingClassifier(n_estimators=100))
])

# Correct: fit only on training data
pipeline.fit(X_train, y_train)

# Correct: transform uses training-fitted parameters
val_score = pipeline.score(X_val, y_val)
test_score = pipeline.score(X_test, y_test)
```

### Handling Categorical Features in Pipeline

Use `ColumnTransformer` to apply different preprocessing steps to different feature subsets:

```python
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder

preprocessor = ColumnTransformer([
    ('num', Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ]), numeric_features),
    ('cat', Pipeline([
        ('imputer', SimpleImputer(strategy='most_frequent')),
        ('encoder', OneHotEncoder(handle_unknown='ignore', sparse=False))
    ]), categorical_features)
])

full_pipeline = Pipeline([
    ('preprocessor', preprocessor),
    ('model', GradientBoostingClassifier())
])
```

---

## Imbalanced Data Handling

Many real-world classification problems have severe class imbalance (fraud detection: 0.1% positive; disease diagnosis: 1–5% positive). Standard accuracy becomes misleading.

### Evaluation Metrics for Imbalanced Data

- **ROC-AUC:** Measures model's ability to rank positives above negatives. Invariant to class imbalance by construction. But can be misleadingly high if true positives are easy.
- **Precision-Recall AUC:** Better than ROC-AUC when positives are rare. Focuses on how precisely the model retrieves the minority class.
- **F1 score:** Harmonic mean of precision and recall. F1 = 1.0 is perfect; F1 = 0.0 is worst. Use when you care equally about precision and recall.
- **Cohen's Kappa:** Accounts for chance agreement. More interpretable than accuracy for imbalanced datasets.

### Resampling Techniques

**Oversampling (minority class):**
- Random oversampling: duplicate minority class samples. Risk: overfitting to duplicated samples.
- SMOTE (Synthetic Minority Oversampling Technique): generates synthetic minority samples by interpolating between existing ones. Typical usage: oversample minority to 10–50% of majority class size.

**Undersampling (majority class):**
- Random undersampling: discard majority class samples. Risk: losing informative majority samples.
- Tomek links: remove majority samples that are borderline (closest to minority samples). Cleans the decision boundary.

**Class weighting:** Many scikit-learn estimators accept `class_weight='balanced'`, which scales the loss contribution of each sample inversely proportional to class frequency. This is the simplest approach and often sufficient.

**Rule of thumb:** Try `class_weight='balanced'` first. If precision-recall performance is still poor, try SMOTE. Always apply SMOTE only within the training fold, never before splitting, to prevent leakage.

---

## Summary: A Reliable ML Development Checklist

| Step | Action |
|---|---|
| 1. Explore data | Check distributions, missingness, target balance, feature types |
| 2. Baseline model | DummyClassifier or DummyRegressor first |
| 3. Split data | Stratified train/val/test with fixed random_state before any preprocessing |
| 4. Build pipeline | All preprocessing inside Pipeline; fit only on training data |
| 5. Cross-validate | StratifiedKFold (classification) or TimeSeriesSplit (time series) |
| 6. Check for leakage | Audit every feature for temporal and target leakage |
| 7. Escalate model complexity | Linear → tree → ensemble; stop when gains are marginal |
| 8. Tune hyperparameters | On validation set or via inner CV; never on test set |
| 9. Evaluate on test set | Exactly once; report result with confidence interval |
| 10. Log and version | Seed, dependencies, data hash, model artifact, hyperparameters |