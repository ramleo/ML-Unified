# Regression Metrics in Machine Learning

## Overview

Regression tasks require measuring how close predicted continuous values are to actual target values. No single metric is universally best — each captures a different aspect of error, and the right choice depends on the target distribution, the cost of large vs. small errors, and whether interpretability in the original units matters.

---

## R-Squared — Coefficient of Determination

### Definition

R² (R-squared) measures the proportion of variance in the target variable that is explained by the model's predictions. It compares the model's residuals to the residuals of a trivial baseline that always predicts the mean of the target.

```
R² = 1 - SS_res / SS_tot

SS_res = sum((y_i - y_hat_i)^2)    # residual sum of squares
SS_tot = sum((y_i - y_bar)^2)      # total sum of squares
```

where y_bar is the mean of the observed target values.

### Interpretation

- **R² = 1.0**: Perfect fit — the model explains all variance in the target.
- **R² = 0.0**: The model performs exactly as well as predicting the mean for every sample. No explanatory power beyond the baseline.
- **R² < 0** (negative): The model performs worse than simply predicting the mean. This is not a mathematical impossibility — it occurs when the model's predictions are so poor that they introduce more error than the constant-mean baseline.

### Typical Ranges by Domain

- Physical sciences, engineering: R² > 0.95 is common; models are well-specified.
- Economics, social sciences: R² of 0.5–0.7 may be considered strong; human behavior is noisy.
- Medical outcomes, biology: R² of 0.3–0.6 is often acceptable; many unmeasured confounders.
- Time series prediction: R² can be misleading because temporal autocorrelation inflates apparent fit.

### Range

R² is unbounded below (can be any negative value) and is bounded above by 1.0. There is no lower bound in practice.

### When Negative R² Occurs

Negative R² indicates the model is worse than a horizontal line at y_bar. Common causes:

1. **Train-test domain mismatch**: Model was trained on data from a different distribution.
2. **Overfitting to noise**: Model memorized training data and completely fails on new data.
3. **Incorrect feature scaling**: Unscaled features caused a linear model to produce wildly out-of-range predictions.
4. **Evaluating on unseen classes or ranges**: Extrapolation beyond training data range.
5. **Bug in prediction pipeline**: Incorrect feature alignment between training and inference.

Negative R² on the test set while training R² is high is a clear signal of overfitting.

---

## Adjusted R-Squared

### Why Adjusted R² Exists

Adding any feature to a regression model — even a completely random one — will never decrease R² on the training set. This is because the model can always assign a zero or near-zero coefficient to an irrelevant feature, preserving the original R². As a result, R² alone cannot be used to compare models with different numbers of features: adding noise variables always improves it on training data.

### Definition

Adjusted R² corrects for the number of predictors:

```
Adjusted R² = 1 - (1 - R²) * (n - 1) / (n - p - 1)
```

where n is the number of training samples and p is the number of predictor variables.

### Behavior

- If a new feature improves the model by more than expected by chance, Adjusted R² increases.
- If a new feature is uninformative, Adjusted R² decreases or stays flat.
- Adjusted R² is always lower than or equal to R².
- With p = 0 (intercept-only model), Adjusted R² = R².

### Use Case

Use Adjusted R² when comparing models with different numbers of features on the same training dataset. Do not use it as the primary evaluation metric on test data — use R² or MAE/RMSE for test-set evaluation.

---

## Mean Squared Error (MSE)

### Definition

MSE is the average of the squared differences between predicted and actual values:

```
MSE = (1/n) * sum((y_i - y_hat_i)^2)
```

### Properties

- **Units**: The square of the original target units. If predicting house prices in dollars, MSE is in dollars-squared — hard to interpret directly.
- **Sensitivity to outliers**: Squaring errors means large errors are penalized quadratically. A single prediction that is off by 10 units contributes 100 to MSE, while ten predictions off by 1 unit each contribute only 10 total.
- **Always non-negative**: MSE = 0 only if all predictions are exactly correct.
- **Differentiable**: MSE has a smooth gradient everywhere, making it well-suited for gradient-based optimization.

### When MSE Is Appropriate

- When large errors are particularly costly and you want the model to prioritize avoiding them.
- As a training loss function for linear regression, neural networks, and other gradient-based models.
- When the target variable has few outliers and errors are expected to be normally distributed.
- When comparing models on the same dataset (absolute value does not matter, only relative ranking).

### Limitation

MSE is not interpretable in the original target units. Comparing MSE values across datasets with different scales is meaningless.

---

## Root Mean Squared Error (RMSE)

### Definition

RMSE is the square root of MSE:

```
RMSE = sqrt((1/n) * sum((y_i - y_hat_i)^2))
```

### Properties

- **Units**: Same as the original target variable. RMSE of 5000 for a house price model means predictions are off by roughly $5000 on average (with caveats — see below).
- **Interpretability**: Because RMSE is in the original units, it can be communicated to non-technical stakeholders.
- **Outlier sensitivity**: Still sensitive to outliers (inherited from MSE), though less extreme than MSE itself.
- **Relationship to MAE**: RMSE >= MAE always. The ratio RMSE/MAE indicates the degree of outlier influence. If RMSE >> MAE, large errors dominate.

### Interpreting RMSE

RMSE is not the same as the average absolute error — it is the square root of the average squared error, which gives extra weight to large errors. The "average error" interpretation is an approximation that holds when errors are roughly symmetric and normally distributed.

### When RMSE Is Appropriate

- When you need error in interpretable units and also want to penalize large errors.
- Standard reporting metric in regression competitions (Kaggle typically uses RMSE).
- When target values span a moderate range without extreme outliers.

---

## Mean Absolute Error (MAE)

### Definition

MAE is the average of the absolute differences between predicted and actual values:

```
MAE = (1/n) * sum(|y_i - y_hat_i|)
```

### Properties

- **Units**: Same as the original target variable — directly interpretable.
- **Robustness to outliers**: Unlike MSE/RMSE, MAE treats all errors linearly. An error of 10 is exactly 10 times worse than an error of 1. A single extreme outlier has limited influence.
- **Not differentiable at zero**: The absolute value function has no derivative at zero, which can cause issues for gradient-based optimization (subgradient methods are used instead).
- **Always non-negative**: MAE = 0 only with perfect predictions.

### Interpretation

MAE of 5000 in a house price model means the model's predictions are off by $5000 on average. This is the most straightforward interpretation of any regression metric.

### When MAE Is Appropriate

- When the target variable contains outliers that you do not want to disproportionately influence the metric.
- When all prediction errors should be weighted equally regardless of magnitude.
- When clear, interpretable error communication is required.
- In applications where the cost of error grows linearly (e.g., delivery time estimation — being 2 hours late is twice as bad as being 1 hour late, not four times as bad).

---

## MAPE — Mean Absolute Percentage Error

### Definition

MAPE expresses error as a percentage of the actual value:

```
MAPE = (100/n) * sum(|y_i - y_hat_i| / |y_i|)
```

### Properties

- **Scale-independent**: MAPE is expressed as a percentage, making it comparable across datasets with different target scales.
- **Intuitive**: "The model is off by 8% on average" is understandable to any stakeholder.
- **Asymmetry**: MAPE is not symmetric — underestimates and overestimates of the same absolute magnitude produce different MAPE contributions. An actual value of 100 predicted as 50 gives 50% error; an actual value of 100 predicted as 150 also gives 50% — but the absolute errors are the same.
- **Undefined for zero targets**: If any actual value is exactly 0, MAPE is undefined (division by zero).
- **Large values for near-zero targets**: When actual values are close to but not exactly zero, MAPE explodes. Predicting 0.5 when the actual is 0.01 gives 4900% MAPE.

### Variants

- **SMAPE (Symmetric MAPE)**: Uses the average of actual and predicted in the denominator, reducing asymmetry.
- **WMAPE (Weighted MAPE)**: Weights errors by actual value, avoiding the small-denominator problem.

### When MAPE Is Appropriate

- When the target variable is strictly positive and not near zero.
- When comparing model performance across products or categories with different price scales.
- For business communication where percentage error is more meaningful than absolute error.

### When to Avoid MAPE

- When target values can be zero or near-zero.
- When underestimates and overestimates carry equal cost (MAPE is asymmetric).
- When targets span many orders of magnitude (MAPE is dominated by low-value samples).

---

## Huber Loss

### Definition

Huber loss is a hybrid between MSE and MAE that is quadratic for small errors and linear for large errors:

```
L_delta(y, f(x)) = 
    0.5 * (y - f(x))^2,              if |y - f(x)| <= delta
    delta * |y - f(x)| - 0.5*delta^2, if |y - f(x)| > delta
```

The parameter delta (also written as epsilon or the threshold) determines the boundary between quadratic and linear behavior.

### Properties

- **Differentiable everywhere**: Unlike MAE, Huber loss has a smooth gradient at zero, which is better for optimization.
- **Robust to outliers**: For errors larger than delta, the loss grows linearly (like MAE), limiting the influence of extreme outliers.
- **Sensitive to small errors**: For errors smaller than delta, the loss is quadratic (like MSE), providing precise gradients for fine-grained optimization.
- **delta controls the transition**: Small delta (e.g., 0.5) makes Huber behave more like MAE; large delta (e.g., 100) makes it behave more like MSE.

### Choosing delta

In practice, delta is often set as the 90th percentile of absolute residuals from an initial fit, or tuned as a hyperparameter. A delta equal to the standard deviation of the errors is a common starting point.

### When Huber Loss Is Appropriate

- When the dataset contains outliers but you still want precise optimization for well-fitting samples.
- As a training loss for neural networks or gradient boosting when the target is noisy.
- When you need the differentiability of MSE but the outlier robustness approaching MAE.

---

## Residual Analysis

Examining model residuals — the differences (y_i - y_hat_i) — reveals whether model assumptions are violated and identifies areas for improvement.

### Residual vs. Fitted Plot

Plot residuals on the y-axis against predicted values on the x-axis. A well-behaved model should show:

- Residuals scattered randomly around zero with no systematic pattern.
- Roughly constant spread across all fitted values (homoscedasticity).

**Patterns that indicate problems:**
- **Funnel shape (wider spread at higher fitted values)**: Heteroscedasticity — the variance of errors grows with the target. Consider log-transforming the target.
- **Curved pattern**: The model is missing a nonlinear relationship. Add polynomial features or use a nonlinear model.
- **Clusters or separated groups**: Potential subpopulations in the data that should be modeled separately.

### Normal Q-Q Plot of Residuals

Plots the quantiles of residuals against theoretical normal distribution quantiles. Deviations from the diagonal line indicate non-normal residuals:

- **Heavy tails**: The model frequently makes large errors. Consider robust loss functions.
- **Skewed residuals**: Asymmetric error distribution — may need target transformation or a different model family.

### Scale-Location Plot

Plots the square root of absolute residuals against fitted values. A flat horizontal line indicates constant variance. An upward trend indicates heteroscedasticity.

---

## Comparing Models with Different Metrics

### Same Dataset, Different Metrics

When comparing two models on the same dataset using different metrics (e.g., Model A ranked by RMSE vs. Model B ranked by MAE), the rankings can differ. A model optimized with a squared loss (MSE/RMSE) will tend to have lower RMSE but potentially higher MAE than one optimized with an absolute loss. Always compare models using the same metric.

### Different Datasets

MSE and RMSE values cannot be compared across datasets with different target scales. A RMSE of 100 for predicting house prices (in thousands) means something entirely different than a RMSE of 100 for predicting body temperature. Use MAPE or a normalized metric for cross-dataset comparison.

### Model Selection Criterion

For model selection (choosing among candidate models), use evaluation on a held-out test set. Do not select models based on training set metrics — they reflect training fit, not generalization.

---

## When Each Metric Is Appropriate: Decision Guide

| Metric | Use When |
|--------|----------|
| R² | Communicating overall model quality; comparing explained variance |
| Adjusted R² | Comparing models with different numbers of features (on training data) |
| MSE | Training loss for gradient-based optimization; penalizing large errors |
| RMSE | Reporting error in original units; standard competition metric |
| MAE | Target has outliers; linear cost of error; interpretability is key |
| MAPE | Target is strictly positive; comparing across scales; business reporting |
| Huber | Noisy targets; want outlier robustness with smooth gradients |

### Guiding Principles

1. **If outliers matter and should be penalized heavily**: RMSE or MSE.
2. **If outliers are noise and should have limited influence**: MAE or Huber.
3. **If you need percentage-based interpretation**: MAPE (only when targets > 0).
4. **If comparing feature sets**: Adjusted R².
5. **If training a model**: MSE (smooth gradient) or Huber (robust + smooth).
6. **If communicating to stakeholders**: MAE (most intuitive) or MAPE (percentage).

---

## Practical Notes

### Target Transformation

When the target variable is right-skewed (e.g., house prices, income), applying a log transform before modeling can improve both model performance and metric behavior:

- Log-transformed target makes the distribution approximately normal.
- Errors in log space correspond to multiplicative errors in original space (similar to MAPE).
- Convert predictions back with `exp(y_hat)` after modeling.

### Evaluation on the Test Set

Always compute final metrics on a held-out test set that was not used during training or hyperparameter tuning. Cross-validation estimates are acceptable for model selection, but final reported numbers should come from a single fixed test set.

### Multiple Metrics Together

Reporting a single metric can be misleading. Best practice is to report RMSE (penalizes large errors), MAE (robust central tendency of errors), and R² (overall explained variance) together — they tell a more complete story of model performance.