# Feature Engineering

Feature engineering is the process of transforming raw data into representations that machine learning models can learn from more effectively. It is widely considered the single highest-leverage activity in an applied ML workflow — more so than hyperparameter tuning or model selection. A well-engineered feature set routinely closes the gap between a weak baseline and a production-grade model.

---

## Why Feature Engineering Matters

Most real-world datasets are not ready for a model to consume directly. Raw features carry noise, skewed distributions, redundant information, and implicit structure that linear models cannot detect and that even tree-based models may exploit poorly without help.

### The core reasons to engineer features

- **Distributions matter for many models.** Linear regression, logistic regression, SVMs, and neural networks all assume or benefit from approximately normal input distributions. Right-skewed or heavy-tailed numeric columns violate this assumption and can dominate gradient updates.
- **Scale invariance is not universal.** K-nearest neighbors, SVMs, and regularized linear models are sensitive to feature magnitude. A salary column ranging 20,000–500,000 will dwarf a binary indicator without scaling.
- **Latent signal is often nonlinear.** A model that sees `area` and `price_per_sqft` separately captures less than one that also receives their product.
- **Cardinality creates sparsity problems.** A raw city column with 3,000 unique values creates a 3,000-column one-hot matrix. Smarter encodings compress this into dense, informative signals.
- **Datetime fields carry cyclical and seasonal structure** that vanilla numeric treatment destroys.

Good feature engineering surfaces these signals explicitly, reduces the hypothesis space the model must search, and often reduces the amount of data needed to generalize well.

---

## Numeric Transformations

### Log Transform (log1p)

The natural logarithm transform is the most common remedy for right-skewed numeric distributions — income, page views, transaction amounts, and counts are classic examples.

**Formula:** `x' = log(1 + x)`

Using `log1p` instead of `log` avoids undefined behavior when x = 0. After this transform, a column with values spanning three orders of magnitude (1, 10, 100, 1000) becomes (0, 2.3, 4.6, 6.9) — nearly linear spacing.

**When to apply:**
- Skewness > 0.75 (right-skewed). Compute `scipy.stats.skew(col)` before and after to confirm improvement.
- All values are non-negative.
- The column represents a count, duration, monetary amount, or ratio.

**When to avoid:**
- Values include negatives (use Box-Cox or Yeo-Johnson instead).
- The column is already approximately normal (skewness between -0.5 and 0.5).

**Concrete example:** A `annual_income` column with median 45,000 and max 2,000,000 has skewness ~3.2. After `log1p`, skewness drops to ~0.4, and a linear model's coefficients become interpretable.

### Square Root Transform

A milder compression than log, useful when data is moderately skewed (skewness 0.5–1.5) or when the column represents area, count, or Poisson-distributed events.

**Formula:** `x' = sqrt(x)`

Like log1p, requires non-negative inputs. For Poisson data, the square root stabilizes variance (variance of sqrt(X) ~ 1/4 for large lambda).

### Box-Cox Transform

A parametric family of power transforms that finds the lambda that best normalizes a distribution.

**Formula:** For lambda != 0: `x' = (x^lambda - 1) / lambda`. For lambda = 0: `x' = log(x)`.

Key values: lambda = 1 (no transform), lambda = 0 (log), lambda = 0.5 (sqrt), lambda = -1 (reciprocal).

`scipy.stats.boxcox` returns the optimal lambda via maximum likelihood. **Requires strictly positive values.**

For columns with zeros or negatives, use **Yeo-Johnson**, which extends Box-Cox to all real numbers and is available in `sklearn.preprocessing.PowerTransformer(method='yeo-johnson')`.

**Typical lambda range seen in practice:** -2 to 2. Extreme values (|lambda| > 2) often signal that a more fundamental data cleaning step is needed.

### Standardization (Z-score Scaling)

**Formula:** `x' = (x - mean) / std`

Transforms the column to zero mean and unit variance. Essential for:
- Regularized linear models (Lasso, Ridge, ElasticNet) — regularization penalizes coefficients, so they must be on comparable scales.
- SVMs with RBF kernel.
- Neural networks (speeds convergence).
- PCA (variance is the signal, so scale must be equalized).

Use `sklearn.preprocessing.StandardScaler`. **Fit only on training data; apply the fitted scaler to validation and test sets.** This is one of the most common data leakage mistakes.

### Min-Max Scaling

**Formula:** `x' = (x - min) / (max - min)` — maps to [0, 1].

More sensitive to outliers than standardization because min and max are heavily influenced by extremes. Use when:
- The model expects bounded inputs (e.g., neural networks with sigmoid output layer, image pixel values).
- The actual min and max are meaningful (e.g., percentage features that should stay in [0, 1]).

A robust variant uses the IQR: `x' = (x - median) / IQR` — implemented in `sklearn.preprocessing.RobustScaler`. Better for data with outliers that would otherwise compress the majority of values into a narrow band.

### Reciprocal and Other Transforms

The reciprocal `1/x` is useful for rates and speeds (converting seconds to speed, or vice versa). Apply only when the business logic supports it and values are bounded away from zero.

---

## Polynomial Features

### Degree-2 Polynomial Expansion

For a feature vector [a, b, c], a degree-2 expansion produces: [a, b, c, a^2, b^2, c^2, ab, ac, bc] — capturing both squared effects and pairwise interactions.

`sklearn.preprocessing.PolynomialFeatures(degree=2, include_bias=False)` generates this automatically.

**When useful:**
- The relationship between a feature and the target is clearly curved (visualize with scatter plots or partial dependence plots).
- You have a small number of numeric features (5–15). With 50 features, degree-2 expansion produces 1,325 columns — a dimensionality explosion that requires strong regularization.

**Degree-3 and beyond** are rarely used except in domain-specific physical models. The feature count grows as O(n^d) and overfitting risk increases sharply.

### Interaction Terms

Sometimes you want only the cross-products, not the squared terms. These can be created manually:

```
df['rooms_per_person'] = df['total_rooms'] / df['population']
df['price_area_interact'] = df['price'] * df['area']
```

Manual creation lets you encode domain knowledge — for example, in housing price prediction, `(latitude - median_lat) * (longitude - median_lon)` can capture geographic clustering effects that a model alone may not discover.

### Practical Decision Rule for Polynomial Features

Use polynomial features when:
1. You are using a linear model (polynomial features make linear models nonlinear).
2. You have fewer than 20 numeric features before expansion.
3. Cross-validation shows meaningful improvement without severe overfitting.

Tree-based models (Random Forest, XGBoost, LightGBM) do NOT need polynomial features — they discover interactions natively through splits. Adding polynomial features to tree models wastes memory and sometimes harms performance.

---

## Binning Strategies

Binning converts a continuous numeric column into discrete intervals (categories). It is useful when:
- The relationship is non-monotonic (e.g., risk peaks in the middle of an age range).
- You want to reduce the effect of outliers.
- The model is a linear one and you suspect a step-function relationship.

### Equal-Width Binning

Divides the range [min, max] into k equal-width buckets.

```
pd.cut(df['age'], bins=5, labels=['0-20','21-40','41-60','61-80','81+'])
```

**Problem:** Highly skewed distributions produce bins with vastly different counts (one bin with 90% of observations, another with 2%). Descriptive statistics become unreliable.

**Typical k:** 5–10 for exploratory work. Use domain knowledge to choose meaningful breakpoints (e.g., age bins 0-17, 18-30, 31-50, 51-65, 65+).

### Equal-Frequency Binning (Quantile Binning)

Divides data so each bin contains approximately the same number of observations.

```
pd.qcut(df['income'], q=4, labels=['Q1','Q2','Q3','Q4'])
```

More robust to skew. Preferred for feature engineering because each bin has statistical power. **Risk:** Bin boundaries shift between train and test — use the quantiles from training data to bin the test set (store the bin edges from `pd.qcut(..., retbins=True)`).

### Custom Binning

Domain experts often know the meaningful thresholds. Credit score bins (300-579 Poor, 580-669 Fair, 670-739 Good, 740-799 Very Good, 800-850 Exceptional) encode regulatory and actuarial knowledge that equal-frequency bins would miss. Always prefer custom bins when domain knowledge is available and validated.

---

## Datetime Feature Extraction

A raw datetime column is unusable by most models as a single integer. Decomposing it into components exposes meaningful periodicities.

### Standard Extractions

| Component | Pandas call | Typical range | Notes |
|---|---|---|---|
| Year | `.dt.year` | 2015–2025 | Useful as a trend variable |
| Month | `.dt.month` | 1–12 | Seasonal signal |
| Day of month | `.dt.day` | 1–31 | Pay cycles, rent dates |
| Day of week | `.dt.dayofweek` | 0 (Mon)–6 (Sun) | Weekday vs weekend behavior |
| Hour | `.dt.hour` | 0–23 | Intraday demand patterns |
| Quarter | `.dt.quarter` | 1–4 | Fiscal seasonality |
| Is weekend | `(dt.dayofweek >= 5).astype(int)` | 0/1 | Strong binary signal for many domains |
| Week of year | `.dt.isocalendar().week` | 1–53 | Retail, logistics |

### Cyclical Encoding

Month, day-of-week, and hour are cyclical — month 12 and month 1 are adjacent, but their raw integer values (12 and 1) are far apart. Linear models and distance-based models are misled by this.

**Solution — sine/cosine encoding:**

```
df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
```

This maps each period to a point on the unit circle, preserving adjacency. Always encode cyclical features this way for linear models, KNN, and neural networks.

### Time Since a Reference Point

Often more useful than the raw date: `days_since_signup`, `days_until_expiry`, `months_since_last_purchase`. These are monotonic or bounded signals that models handle better than raw timestamps.

---

## Ratio and Difference Features

### Ratio Features (A / B)

Ratios normalize one quantity by another, removing scale effects and often creating the "true" signal:

- `price_per_sqft = price / area`
- `revenue_per_user = total_revenue / active_users`
- `click_through_rate = clicks / impressions`
- `debt_to_income = total_debt / annual_income`

**Guard against division by zero:** `df['ratio'] = df['A'] / (df['B'] + 1e-6)` or filter rows where B == 0.

### Difference Features (A - B)

Captures change, gap, or excess:

- `price_above_median = price - city_median_price`
- `days_overdue = due_date - payment_date`
- `score_gap = first_score - second_score`

Difference features are especially useful when two correlated features encode a relative concept — replacing two correlated columns with their difference can reduce multicollinearity.

---

## Categorical Encodings

The choice of categorical encoding is one of the most impactful feature engineering decisions. The wrong choice can introduce hundreds of uninformative sparse columns or destroy ordinal information.

### One-Hot Encoding (OHE)

Creates one binary column per unique category.

**Use when:**
- Cardinality is low: < 15–20 unique values.
- The model is a linear one (logistic regression, linear SVM).
- The categories have no natural order.

**Pitfall:** With 500 categories, OHE produces 500 columns. Most are near-zero, causing severe sparsity and slowing training. For high-cardinality columns, use a different strategy.

Always drop one column (set `drop='first'` in `OneHotEncoder`) to avoid perfect multicollinearity in linear models.

### Ordinal Encoding

Maps categories to integers preserving a rank: Cold = 0, Warm = 1, Hot = 2.

**Use when** there is a genuine ordering (education level, satisfaction rating, credit grade). Never apply ordinal encoding to nominal categories (city names, product IDs) — it falsely implies that Tokyo > London because its integer is larger.

### Target Encoding (Mean Encoding)

Replaces each category with the mean of the target variable for that category.

```
city_means = train.groupby('city')['price'].mean()
df['city_encoded'] = df['city'].map(city_means)
```

**Advantages:** Handles high-cardinality naturally, produces a single dense column.

**Critical risk — target leakage:** Computing the mean on the full training set and applying it to the same rows leaks target information into features. Always use cross-fold target encoding (compute means from out-of-fold rows only) or use `sklearn.preprocessing.TargetEncoder` (scikit-learn >= 1.3), which applies smoothing and cross-validation internally.

**Smoothing formula:** `encoded = (count * category_mean + m * global_mean) / (count + m)` where m controls the strength of smoothing (typical m = 5–30). Low-count categories are pulled toward the global mean.

### Frequency Encoding

Replaces each category with its frequency (count or proportion) in the training data.

```
freq = train['city'].value_counts(normalize=True)
df['city_freq'] = df['city'].map(freq)
```

Useful when category popularity is itself a predictive signal. Preserves no information about the target but avoids leakage. Works well for tree models and as a complement to other encodings.

### Label Encoding

Assigns arbitrary integers to categories. **Only appropriate for tree-based models** (Random Forest, XGBoost, LightGBM, CatBoost) that split on inequality — they do not interpret integer values as a ranking. Avoid for linear models.

### Binary Encoding

Converts the integer label into binary digits: category 5 becomes [0, 1, 0, 1]. Produces log2(cardinality) columns instead of cardinality columns — a useful middle ground for cardinality 50–200.

---

## Feature Interaction Creation

Beyond polynomial features, domain-driven interaction features often outperform automated expansion:

- **Product:** `screen_size * refresh_rate` for display quality
- **Ratio:** `sqft / num_rooms` for room spaciousness
- **Boolean AND:** `is_weekend & is_holiday` for retail demand spikes
- **Min/Max of a pair:** `max(score_a, score_b)` for ensemble-style features
- **Rank within group:** percentile of price within city — captures relative positioning

To systematically discover interactions, apply a tree model (even a shallow one), extract its feature importances, and examine which pair-splits appear frequently. Manual review of those pairs guides which interactions to hard-code.

---

## Avoiding Data Leakage in Transforms

Data leakage occurs when information from the validation or test set contaminates the training process. It is the leading cause of models that look excellent on a holdout set but fail in production.

### Rules to prevent leakage

1. **Fit all scalers, encoders, and imputers on training data only.** Call `.fit()` on the training fold, then `.transform()` on both training and test. Never call `.fit_transform()` on the combined dataset.

2. **Target encoding must use out-of-fold means.** Computing `city_mean_price` from the entire training set and then using that feature in a cross-validated model creates fold-level leakage. Use `TargetEncoder` with `cv=5` or implement cross-fold computation manually.

3. **Datetime-based features must respect temporal ordering.** In time-series contexts, features like `rolling_7day_avg` must only look backward — never forward. When creating a feature for row with timestamp T, use only rows with timestamp < T.

4. **Store and reuse fitted transformers.** In production, the scaler and encoder fitted on training data must be serialized (e.g., with `joblib.dump`) and reused at inference time. Recomputing them on production data is a subtle form of leakage.

5. **Pipeline objects enforce the discipline.** Wrapping all transforms in a `sklearn.pipeline.Pipeline` ensures `.fit()` is called only once on training data and `.transform()` is applied consistently. This is the recommended pattern for all production feature engineering.

### Common leakage scenarios

- Normalizing the entire dataset before splitting into train/test.
- Computing missing-value means over the full dataset.
- Selecting features using correlation with the target computed over all rows.
- Using future timestamps to construct "current" features in time-series.

---

## When to Apply Each Transform — Decision Guide

| Situation | Recommended transform |
|---|---|
| Right-skewed numeric, all non-negative | log1p |
| Moderately skewed numeric | sqrt or Yeo-Johnson |
| Need best normalization, can search lambda | Box-Cox / Yeo-Johnson |
| Linear model, need same scale | StandardScaler |
| Neural network or bounded input needed | MinMaxScaler |
| Outliers present, robust scaling needed | RobustScaler |
| Low-cardinality nominal category (< 15) | One-hot encoding |
| Ordinal category with known ranking | Ordinal encoding |
| High-cardinality nominal (>= 15 unique) | Target encoding with smoothing |
| Category frequency is the signal | Frequency encoding |
| Cyclical time feature (month, hour) | Sine/cosine encoding |
| Cross-product signal suspected | Manual ratio or product feature |
| Using tree-based model | Skip scaling; use label/target encoding |

---

## Summary

Feature engineering is a structured craft, not guesswork. The key discipline is: understand the data distribution, apply the transform that best exposes the underlying signal to the model, and never let test-set information flow into fit-time computations. Every transform decision should be validated by comparing cross-validation scores before and after — an engineering change that does not improve held-out performance is not worth the added complexity.
