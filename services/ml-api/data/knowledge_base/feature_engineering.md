<!-- Source: https://scikit-learn.org/stable/modules/preprocessing.html — fetched 2026-07-01 -->

# Feature Engineering (sklearn.preprocessing)

## What It Does

`sklearn.preprocessing` transforms raw feature vectors into representations suitable for ML estimators. Most algorithms benefit from standardized data; some require bounded inputs or specific distributions. All transformers follow the fit/transform pattern — always fit on training data only.

---

## Scaling Transformers

| Transformer | Formula | When to Use | Caveats |
|---|---|---|---|
| **StandardScaler** | `(x - mean) / std` | Linear models, SVMs, neural nets, PCA | Cannot center sparse matrices (`with_mean=False` for sparse) |
| **MinMaxScaler** | `(x - min) / (max - min)` → [0,1] | Neural nets, bounded input needed | Sensitive to outliers; new data can fall outside [0,1] |
| **MaxAbsScaler** | `x / max(|x|)` → [-1,1] | Sparse data (preserves sparsity) | Assumes data already centered near zero |
| **RobustScaler** | `(x - median) / IQR` | Data with significant outliers | Cannot fit sparse inputs (can transform them) |
| **Normalizer** | Row-wise L1/L2/max norm | Text classification, clustering, vector space models | Operates per-sample, not per-feature |

**Key parameter:** `with_mean=True / with_std=True` on StandardScaler — disable either independently.

---

## Non-linear Transformations

### PowerTransformer
Maps data to approximately Gaussian using parametric power transforms.

- **`method='yeo-johnson'`** — works for any values including negatives. Default.
- **`method='box-cox'`** — only for strictly positive data.
- By default applies zero-mean, unit-variance normalization to the output.
- Use when a column has skewed distribution and you need Gaussian-like input for a linear model or neural net.

### QuantileTransformer
Non-parametric rank-based transform to uniform [0,1] or normal distribution.

- `output_distribution='uniform'` (default) or `'normal'`.
- Robust to outliers — extreme values are compressed to the boundary.
- **Caveat:** Distorts correlations and distances between features; do not use before PCA or distance-based models if feature relationships matter.

---

## Categorical Encoders

### OrdinalEncoder
Maps categories to integers 0..n-1. Implies an ordering — use only for genuinely ordered categories (e.g., education level, satisfaction rating).

- `handle_unknown='use_encoded_value'` with `unknown_value=-1` to handle unseen categories at inference.
- Never apply to nominal (unordered) categories.

### OneHotEncoder
Creates one binary column per category. Suitable for nominal, low-cardinality features (< 15–20 unique values).

- `drop='first'` or `'if_binary'` — drop one column to avoid perfect multicollinearity in non-regularized linear models.
- `handle_unknown='infrequent_if_exist'` — encodes unseen categories as all-zeros or as infrequent bucket.
- `max_categories` — groups infrequent categories into a single "infrequent" bucket to control output width.
- `min_frequency` — define the cardinality threshold for infrequency.

### TargetEncoder (sklearn >= 1.3)
Encodes categories using target mean for that category. Handles high-cardinality automatically with a single dense output column.

- Uses k-fold cross-fitting in `fit_transform()` to prevent target leakage.
- **Critical:** `fit(X,y).transform(X)` is NOT equal to `fit_transform(X,y)` — always use `fit_transform` on training data.
- For test data: `fit(X_train, y_train).transform(X_test)`.

---

## Discretization

### KBinsDiscretizer
Partitions continuous features into discrete bins.

- `strategy='uniform'` — constant-width bins.
- `strategy='quantile'` — equally populated bins. More robust for skewed data.
- `strategy='kmeans'` — bins by k-means clustering per feature.
- `encode='ordinal'` (integer bins) or `'onehot'` (one-hot encoded output).
- **When to use:** Introduce non-linearity to linear models; handle non-monotonic relationships.

---

## Feature Generation

### PolynomialFeatures
Generates polynomial and interaction terms from numeric features.

- `degree=2` on [a, b] → [1, a, b, a², ab, b²].
- `interaction_only=True` — only cross-products, no squared terms.
- `include_bias=False` — omit the bias column (intercept) when the model adds its own.
- **Caveat:** Feature count grows as O(n^degree). With 20 features and degree=2, output is 231 columns. Use carefully; requires strong regularization.
- **Tree-based models do not need polynomial features** — they discover interactions natively.

### SplineTransformer
Generates B-spline basis functions (piecewise polynomials).

- `degree` — polynomial degree per piece (typically 3).
- `n_knots` — number of knot points.
- Advantages over PolynomialFeatures: no Runge's oscillation at boundaries, low condition number, more flexible with fixed low degree.
- Treats each feature independently — no interaction terms.

### FunctionTransformer
Wraps an arbitrary Python function as a sklearn transformer.

- `func=np.log1p` — apply log1p to all features.
- `validate=True` — ensure numeric input.
- `check_inverse=True` — verify `func` and `inverse_func` are inverses.

---

## Missing Value Handling

### MissingIndicator
Creates binary indicator columns marking which values were missing. Use alongside an imputer to give the model explicit signal about missingness patterns.

---

## Best Practices and Caveats

| Issue | Solution |
|---|---|
| Data leakage | Always `.fit()` on training data only; use `Pipeline` to enforce |
| Sparse data centering | Use `MaxAbsScaler` or `StandardScaler(with_mean=False)` |
| Outliers distorting scaling | Use `RobustScaler` instead of `StandardScaler` |
| Target encoder leakage | Use `fit_transform(X_train, y_train)` for training data |
| Collinearity in OHE | Use `OneHotEncoder(drop='first')` for non-regularized linear models |
| Unknown categories at inference | Set `handle_unknown='infrequent_if_exist'` in OneHotEncoder |
| High-cardinality features | Use `TargetEncoder` instead of one-hot encoding |

### Pipeline pattern (enforce correct fit/transform discipline)
```python
from sklearn.pipeline import make_pipeline
pipe = make_pipeline(StandardScaler(), LogisticRegression())
pipe.fit(X_train, y_train)
pipe.score(X_test, y_test)
```
