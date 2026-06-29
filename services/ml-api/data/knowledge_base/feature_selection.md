# Feature Selection

Feature selection is the process of identifying and retaining only those features in a dataset that contribute meaningfully to a model's predictive performance. It is distinct from feature extraction (which creates new representations, e.g., PCA) — selection chooses a subset of the original columns without transforming them.

---

## Why Feature Selection Matters

### The Curse of Dimensionality

As the number of features grows, the volume of the feature space grows exponentially. For a fixed training set size, data becomes increasingly sparse in high-dimensional space. Distance-based models (KNN, SVMs with RBF kernel) degrade rapidly because "nearest neighbors" in 500 dimensions are not meaningfully closer than any other point.

A rule of thumb: you need roughly 10–20 training samples per feature for a linear model to generalize. A dataset with 200 rows and 150 features is almost certainly underdetermined.

### Noise Reduction

Irrelevant features add noise to every learning algorithm. In a random forest, irrelevant features dilute the split-selection pool and increase variance. In linear models, they can absorb regularization budget that should be spent on true signals. Removing noise improves both accuracy and generalization.

### Training Speed and Memory

Feature count directly determines model size, memory footprint, and training time. Halving the feature count roughly halves the memory for tabular models and often reduces training time super-linearly (e.g., matrix operations scale as O(n * p) or O(p^2)).

### Interpretability

A model built on 8 carefully selected features is far easier to explain to a stakeholder than one built on 200. Feature selection is often a prerequisite for deploying models in regulated industries (finance, healthcare).

### Avoiding Overfitting

Spurious correlations between irrelevant features and the target exist by chance, especially in small datasets. Removing these features prevents the model from fitting noise.

---

## Filter Methods

Filter methods score each feature independently of the model, using statistical tests or information-theoretic measures. They are fast, scalable, and immune to overfitting within the selection step itself. Their main limitation is that they cannot detect interactions between features.

### Variance Threshold

The simplest filter: remove features whose variance falls below a threshold. A feature with near-zero variance carries no information.

```python
from sklearn.feature_selection import VarianceThreshold
sel = VarianceThreshold(threshold=0.01)
X_reduced = sel.fit_transform(X)
```

**Typical threshold:** 0.01 for normalized data, or compute feature-wise variance and inspect the distribution — there is often a natural gap between truly invariant and informative columns.

**Use case:** First-pass cleaning step before any other selection method. Removes constant and quasi-constant columns (e.g., a flag that is 1 for 99.9% of rows).

### Correlation Filter

Remove features that are highly correlated with each other (multicollinearity) because they carry redundant information and destabilize linear model coefficients.

**Pearson correlation** measures linear association; suitable for numeric features and linear models.

```python
corr_matrix = X.corr().abs()
upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
to_drop = [col for col in upper.columns if any(upper[col] > 0.90)]
X_reduced = X.drop(columns=to_drop)
```

**Decision rule:** Correlation > 0.85–0.95 typically signals redundancy. The exact threshold depends on domain tolerance. When two features have correlation > 0.90, keep the one with higher individual correlation to the target.

**Spearman rank correlation** is appropriate for non-linear monotonic relationships and ordinal data. Use it when features are not normally distributed.

### ANOVA F-Test (for Classification)

Tests whether the mean of a numeric feature differs significantly across class labels. A high F-score indicates the feature discriminates between classes.

```python
from sklearn.feature_selection import f_classif, SelectKBest
sel = SelectKBest(score_func=f_classif, k=20)
X_reduced = sel.fit_transform(X, y)
```

**Assumptions:**
- The feature should be (approximately) normally distributed within each class.
- Classes should have similar variance (homoscedasticity). If not, the test is unreliable.
- Only captures linear relationships between features and the class label.

**For regression:** Use `f_regression`, which computes the F-statistic for linear relationship between each feature and the continuous target.

### Mutual Information

Mutual information (MI) measures how much knowing a feature reduces uncertainty about the target. Unlike F-tests, MI captures non-linear relationships.

```python
from sklearn.feature_selection import mutual_info_classif, mutual_info_regression
# For classification
scores = mutual_info_classif(X, y, discrete_features='auto', random_state=42)
# For regression
scores = mutual_info_regression(X, y, random_state=42)
```

MI = 0 means the feature and target are statistically independent. Higher values indicate stronger association.

**Advantages over F-test:**
- Detects non-monotonic relationships (e.g., a quadratic effect).
- Works with any target type with appropriate variant.
- No distributional assumptions.

**Limitations:**
- Computationally more expensive than correlation for very large datasets.
- Estimating MI from samples is noisy; results can vary across runs (set `random_state` for reproducibility).
- Does not account for interactions between features.

**Practical use:** Rank features by MI score. Retain features above a score threshold (typically MI > 0.01–0.05) or retain the top-k by MI. Combine with variance threshold as a pre-filter.

---

## Wrapper Methods

Wrapper methods evaluate feature subsets by actually training a model and measuring performance. They are computationally expensive but account for feature interactions and the specific model being used.

### Recursive Feature Elimination (RFE)

RFE fits the model on all features, ranks features by importance or coefficient magnitude, removes the least important feature(s), and repeats until the desired number remains.

```python
from sklearn.feature_selection import RFE
from sklearn.linear_model import LogisticRegression

estimator = LogisticRegression(max_iter=1000)
rfe = RFE(estimator=estimator, n_features_to_select=15, step=1)
rfe.fit(X_train, y_train)
X_reduced = rfe.transform(X_train)
# rfe.ranking_ gives rank (1 = selected)
# rfe.support_ is a boolean mask
```

**`step` parameter:** Number of features to remove per iteration. `step=1` is exhaustive but slow. `step=0.1` removes 10% of remaining features per step — faster but coarser.

**RFECV:** Cross-validated RFE that automatically selects the optimal number of features.

```python
from sklearn.feature_selection import RFECV
rfecv = RFECV(estimator=estimator, cv=5, scoring='roc_auc', step=1)
rfecv.fit(X_train, y_train)
optimal_n = rfecv.n_features_  # number of features at CV peak
```

**Limitations:**
- Slow for large feature sets (p > 500) and complex models.
- Results depend on the estimator — RFE with LogisticRegression selects different features than RFE with RandomForest. Use the same model class you will train on.

---

## Embedded Methods

Embedded methods perform feature selection as part of the model training itself. They are faster than wrapper methods while being more context-aware than filter methods.

### L1 Regularization (Lasso)

L1 regularization adds a penalty proportional to the absolute value of model coefficients. This penalty drives many coefficients exactly to zero, effectively eliminating features.

```python
from sklearn.linear_model import LassoCV, LogisticRegressionCV
# Regression
lasso = LassoCV(cv=5, max_iter=10000).fit(X_train, y_train)
selected = np.where(lasso.coef_ != 0)[0]

# Classification
lrc = LogisticRegressionCV(Cs=10, penalty='l1', solver='liblinear', cv=5)
lrc.fit(X_train, y_train)
selected = np.where(lrc.coef_[0] != 0)[0]
```

**The alpha parameter (Lasso) / C parameter (LogisticRegression):** Controls sparsity.
- Lasso: higher alpha = more regularization = fewer features. LassoCV finds the optimal alpha via cross-validation.
- LogisticRegression: lower C = more regularization. `Cs=10` tests 10 values on a log scale.

**Limitation:** L1 selects at most n features when p > n (underdetermined). Among a group of correlated features, L1 arbitrarily selects one — which one depends on the data split. Use ElasticNet (L1 + L2) for more stable group selection.

### Tree-Based Feature Importance

Ensemble tree models compute feature importance as the total reduction in impurity (Gini or MSE) attributed to each feature across all trees.

```python
from sklearn.ensemble import RandomForestClassifier
rf = RandomForestClassifier(n_estimators=200, random_state=42)
rf.fit(X_train, y_train)
importances = rf.feature_importances_  # array of shape (n_features,)
```

**Gradient boosting importance** (XGBoost, LightGBM, CatBoost) is similar but also offers:
- `gain`: total gain of splits using the feature — generally more reliable than frequency.
- `cover`: total number of samples affected by splits on this feature.
- `weight`: number of times the feature is used in splits — biased toward high-cardinality features.

**Decision rule:** Rank by importance, inspect the distribution. There is usually a natural elbow where importance drops sharply. Features below 1% of total importance are typically safe to drop.

**Limitation:** Impurity-based importance is biased toward high-cardinality features (more possible split points = more chance to appear important). Use permutation importance or SHAP for less biased estimates.

### Permutation Importance

Measures how much model performance degrades when a single feature's values are randomly shuffled (breaking its relationship with the target).

```python
from sklearn.inspection import permutation_importance
result = permutation_importance(rf, X_val, y_val, n_repeats=10, random_state=42)
# result.importances_mean — mean degradation per feature
# result.importances_std — standard deviation across repeats
```

Features with near-zero or negative permutation importance can be safely dropped. This method is model-agnostic and computed on the validation set — making it a true out-of-sample importance estimate.

---

## SelectKBest vs SelectPercentile

Both are sklearn wrappers for filter-based selection, differing only in how many features they retain.

### SelectKBest

Selects exactly k features with the highest scores.

```python
from sklearn.feature_selection import SelectKBest, mutual_info_classif
sel = SelectKBest(score_func=mutual_info_classif, k=25)
sel.fit(X_train, y_train)
X_reduced = sel.transform(X_train)
```

**k selection strategy:** Run cross-validation with k = [5, 10, 15, 20, 25, 30, 50] and plot CV score vs k. Choose k at the plateau — where adding more features yields diminishing returns.

### SelectPercentile

Selects the top p% of features by score. Useful when you have a variable number of features across different datasets and want consistent relative selection.

```python
from sklearn.feature_selection import SelectPercentile
sel = SelectPercentile(score_func=f_classif, percentile=20)  # top 20%
```

**When to prefer SelectPercentile:** Automated pipelines applied to datasets of varying size where a fixed k may be too aggressive or too lenient.

---

## Variance Inflation Factor (VIF) — When to Drop Correlated Features

VIF quantifies how much a feature's variance is inflated by collinearity with other features.

**Formula:** `VIF_i = 1 / (1 - R^2_i)` where `R^2_i` is the R-squared of regressing feature i on all other features.

```python
from statsmodels.stats.outliers_influence import variance_inflation_factor
vif_data = pd.DataFrame({
    'feature': X.columns,
    'VIF': [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]
})
```

**Interpretation thresholds:**
- VIF = 1: No multicollinearity.
- VIF 1–5: Moderate, generally acceptable.
- VIF 5–10: High; consider removing or combining.
- VIF > 10: Severe multicollinearity. The feature adds almost no information beyond what others provide.

**Iterative VIF removal:** Remove the feature with the highest VIF, recompute, repeat until all VIFs are below your threshold. This is the correct procedure — removing one feature changes the VIF of all others.

**Note:** VIF is most relevant for linear and logistic regression where multicollinearity inflates standard errors and makes coefficients unreliable. Tree-based models are generally robust to correlated features (they simply use one of the correlated pair at each split and ignore the other).

---

## Feature Selection for Classification vs Regression

### Classification-Specific Considerations

- Use `mutual_info_classif` and `f_classif` — both take the class label into account.
- For multi-class problems, the F-test averages over all class pairs. MI naturally handles multiple classes.
- Class imbalance affects filter statistics: a feature may appear informative simply because it correlates with the majority class. Consider stratified folds and balanced accuracy as the CV metric.
- When the positive class is rare (< 5%), features that are zero for most samples will appear uninformative by variance threshold — inspect separately.

### Regression-Specific Considerations

- Use `mutual_info_regression` and `f_regression`.
- Pearson correlation with the target is a quick first filter: `X.corrwith(y).abs().sort_values(ascending=False)`.
- For heavy-tailed targets, spearman rank correlation is more reliable than Pearson.
- When target distribution is highly skewed, consider log-transforming the target before computing filter statistics — this stabilizes variance and produces more reliable scores.

---

## How Many Features to Keep

There is no universal rule, but several empirical guidelines:

1. **10–20 samples per feature** for linear models. A dataset with 1,000 rows should have at most 50–100 features.
2. **Feature count vs CV score curve:** Plot cross-validation performance as a function of the number of retained features (sorted by importance). The optimal count is usually at the elbow.
3. **Diminishing returns threshold:** Add features in decreasing importance order. Stop when adding the next feature improves CV score by less than 0.1–0.5% (domain-dependent).
4. **Business/interpretability constraint:** If the model must be explainable, cap features at 10–20 regardless of dataset size.
5. **Tree models can handle more:** Random forests and gradient boosted trees are robust up to hundreds of features if dataset size supports it (> 10,000 rows). Linear models need more aggressive selection.

---

## Cross-Validating Feature Selection to Avoid Leakage

Feature selection itself can overfit if performed outside the cross-validation loop. If you select features based on the full training set and then cross-validate the model, the selected features have "seen" the validation folds indirectly.

**Correct approach:** Nest the feature selection step inside cross-validation using a Pipeline.

```python
from sklearn.pipeline import Pipeline
from sklearn.feature_selection import SelectKBest, mutual_info_classif
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

pipe = Pipeline([
    ('selector', SelectKBest(score_func=mutual_info_classif, k=20)),
    ('model', RandomForestClassifier(n_estimators=100, random_state=42))
])

scores = cross_val_score(pipe, X, y, cv=5, scoring='roc_auc')
# The selector is fit inside each fold on training data only
```

**Why this matters:** With 100 features and 500 samples, selecting the best 20 by MI on the full set can inflate AUC by 0.05–0.15 purely from overfitting in the selection step. Nested CV provides a true unbiased estimate.

**For RFECV:** It already performs cross-validation internally, but fit it only on the training portion of an outer CV fold for a fully unbiased estimate.

---

## SHAP-Based Feature Selection

SHAP (SHapley Additive exPlanations) values attribute each prediction's deviation from the mean to individual features. Aggregating SHAP values across the dataset produces a global importance measure that is more reliable than impurity-based importance.

```python
import shap
import xgboost as xgb

model = xgb.XGBClassifier(n_estimators=200).fit(X_train, y_train)
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_val)  # shape: (n_samples, n_features)

# Mean absolute SHAP value per feature
mean_shap = np.abs(shap_values).mean(axis=0)
feature_importance = pd.Series(mean_shap, index=feature_names).sort_values(ascending=False)
```

### Why SHAP over impurity importance

- SHAP correctly attributes importance in the presence of correlated features. Impurity importance double-counts correlated features; SHAP distributes the credit.
- SHAP importance is computed on the validation set — it reflects out-of-sample behavior.
- SHAP values are directional: you can see whether high feature values push predictions up or down, enabling better interpretation.

### SHAP-based selection procedure

1. Train a gradient boosted model on all features.
2. Compute mean absolute SHAP values on a held-out validation set.
3. Rank features by mean |SHAP|.
4. Iteratively remove the lowest-importance features, monitoring CV score.
5. Stop removing when CV score begins to drop meaningfully (more than 0.5% relative).

**Typical finding:** The top 20–30% of features by SHAP importance account for 80–90% of model performance. The remainder can be dropped with minimal accuracy loss.

### SHAP interaction values

`shap.TreeExplainer` can also compute pairwise interaction SHAP values (`shap_interaction_values`). Features that have high pairwise SHAP interactions should be kept together — removing one breaks the interaction signal captured by the model.

---

## Practical Feature Selection Workflow

A robust selection pipeline for a new dataset:

1. **Step 1 — Variance filter:** Remove constant and quasi-constant features (`VarianceThreshold(threshold=0.01)`).
2. **Step 2 — Correlation filter:** Remove one feature from each pair with |correlation| > 0.90. Prefer to keep the feature with higher univariate MI score.
3. **Step 3 — Univariate scoring:** Score remaining features with mutual information. Drop features below MI threshold (e.g., MI < 0.005 for datasets with > 1,000 samples).
4. **Step 4 — Model-based selection:** Train a tree model (LightGBM or RandomForest, 200 trees, default hyperparameters). Compute permutation importance or SHAP values on a held-out split. Rank features.
5. **Step 5 — Iterative pruning:** Starting from the bottom of the importance ranking, drop features in groups of 5–10 and recheck cross-validated performance.
6. **Step 6 — VIF check (for linear models):** After the above, compute VIF and iteratively remove features with VIF > 10.

This cascade approach is efficient: cheap filters run first, expensive model-based methods run on a pre-filtered subset.

---

## Common Pitfalls in Feature Selection

| Pitfall | Consequence | Fix |
|---|---|---|
| Selecting features outside CV loop | Overfit, inflated CV metrics | Wrap selector in Pipeline |
| Using test set for selection | Data leakage, invalid evaluation | Fit selector only on training fold |
| Dropping correlated features without domain check | Lose a feature with causal significance | Review correlation pairs before dropping |
| Relying solely on impurity importance | Biased toward high-cardinality features | Use permutation importance or SHAP |
| Selecting k arbitrarily without CV | May keep too few or too many | Plot CV score vs k and find elbow |
| Ignoring feature interactions | May drop features important in combination | Check pairwise SHAP interactions |
| Applying same selection for all models | Filter method optimal for linear models is sub-optimal for trees | Match selection method to model family |

---

## Summary

Feature selection is not a one-time step — it is a feedback loop integrated into the modeling pipeline. The right approach depends on dataset size, model family, and interpretability requirements. Filter methods are fast first passes; embedded methods (Lasso, tree importance) are practical for most production workflows; SHAP provides the most reliable and interpretable importance estimates for tree-based models. Always validate selection inside cross-validation to ensure that reported performance is honest, and always treat the test set as strictly held-out until final evaluation.