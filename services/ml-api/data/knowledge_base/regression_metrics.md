<!-- Source: https://scikit-learn.org/stable/modules/model_evaluation.html — fetched 2026-07-01 -->

# Regression Metrics (scikit-learn)

---

## R² Score (Coefficient of Determination)

**Measures:** Proportion of target variance explained by the model.

**Formula:** R² = 1 - (SS_res / SS_tot)
- SS_res = sum of squared residuals; SS_tot = total sum of squares around the mean

**Range:** (-inf, 1]
- 1.0 = perfect fit; 0.0 = model equals predicting the mean; negative = worse than mean baseline

**When to use:** Default metric for regression; cross-model comparison; general-purpose.

**Caveats:**
- Does not indicate absolute prediction error magnitude
- Can be inflated by complex models evaluated on training data
- Sensitive to outliers via squared terms
- Scoring API: `scoring='r2'`

---

## Mean Squared Error (MSE)

**Measures:** Average squared difference between predictions and actuals. Penalizes large errors heavily.

**Formula:** MSE = (1/n) x sum(y_true - y_pred)^2

**Range:** [0, inf); lower is better; 0 = perfect.

**When to use:** When large errors are disproportionately costly; standard training loss for linear models.

**Caveats:**
- Not in same units as target (use RMSE for interpretability)
- Outlier-sensitive due to squaring
- Scoring API: `'neg_mean_squared_error'` (negated)

---

## Root Mean Squared Error (RMSE)

**Measures:** Square root of MSE; expresses error in the same units as the target.

**Formula:** RMSE = sqrt(MSE)

**Range:** [0, inf); lower is better.

**When to use:** Preferred over MSE for communicating error in original units to stakeholders.

**Caveats:** Retains MSE's outlier sensitivity. Scoring API: `'neg_root_mean_squared_error'`.

---

## Mean Absolute Error (MAE)

**Measures:** Average absolute difference between predictions and actuals. All errors weighted equally.

**Formula:** MAE = (1/n) x sum(|y_true - y_pred|)

**Range:** [0, inf); lower is better; same units as target.

**When to use:**
- Equal importance to all error magnitudes
- Robust evaluation resistant to outliers
- When predicting the median is the goal (MAE is the strictly consistent loss for the median)

**Caveats:**
- Underpenalizes large errors compared to MSE
- Scoring API: `'neg_mean_absolute_error'`

---

## Mean Absolute Percentage Error (MAPE)

**Measures:** Average absolute percentage error relative to actuals; unitless.

**Formula:** MAPE = (1/n) x sum(|y_true - y_pred| / |y_true|) x 100%

**Range:** [0, inf); lower is better; expressed as percentage.

**When to use:**
- Relative errors matter more than absolute magnitude
- Comparing performance across targets with different scales
- Business contexts where percentage accuracy is the standard

**Caveats:**
- Undefined when y_true = 0 (division by zero)
- Biased toward underpredictions (asymmetric penalty structure)
- Disproportionately high for small true values
- Scoring API: `'neg_mean_absolute_percentage_error'`

---

## Explained Variance Score

**Measures:** Proportion of variance explained; similar to R² but computed differently.

**Formula:** Explained Variance = 1 - Var(y_true - y_pred) / Var(y_true)

**Range:** (-inf, 1]; 1.0 = perfect.

**When to use:** Alternative to R² when separating bias from variance components matters.

**Caveats:**
- Equals R² when residuals have zero mean; diverges when systematic bias is present
- Less commonly reported than R²

---

## Median Absolute Error

**Measures:** Median (not mean) of absolute errors; maximally robust central tendency of error.

**Formula:** median(|y_true - y_pred|)

**Range:** [0, inf); lower is better; same units as target.

**When to use:**
- Extreme outliers dominate the MAE
- Median performance matters more than mean (e.g., latency SLAs)
- Highly skewed error distributions

**Caveats:**
- Cannot be easily used as a direct training loss
- Less influenced by tail error improvements

---

## Max Error

**Measures:** Worst-case absolute error across all predictions.

**Formula:** max(|y_true - y_pred|)

**Range:** [0, inf); lower is better.

**When to use:** Safety-critical applications where even a single large error is unacceptable.

**Caveats:** Highly sensitive to a single outlier prediction; one bad sample dominates the metric.

---

## Pinball Loss (Quantile Loss)

**Measures:** Asymmetric loss for predicting a specific quantile of the response distribution, not the mean.

**Formula:** asymmetric penalty controlled by quantile level alpha
- Underprediction penalty: alpha x |error|; overprediction penalty: (1 - alpha) x |error|

**Range:** [0, inf); lower is better; interpretation depends on alpha.

**When to use:**
- Predicting specific quantiles (e.g., 99th percentile for SLA modeling)
- Asymmetric costs: overprediction and underprediction have different consequences
- Use with `HistGradientBoostingRegressor(loss='quantile', quantile=alpha)`

**Caveats:** Requires specifying the target quantile; not suitable for mean estimation.

---

## Mean Poisson / Gamma / Tweedie Deviance

**Measures:** Deviance-based losses for targets with specific distributional assumptions.

| Metric | Target Distribution | Typical Use |
|--------|--------------------|----|
| Mean Poisson Deviance | Non-negative counts | Claim frequency, event counts |
| Mean Gamma Deviance | Strictly positive, right-skewed | Insurance claim severity, rainfall |
| Mean Tweedie Deviance (power param) | Compound Poisson-Gamma | Claim amounts (frequency x severity) |

**Range:** [0, inf); lower is better.

**When to use:** When target distribution deviates significantly from Gaussian (verify distributional assumptions first).

**Caveats:**
- Poisson: requires non-negative targets
- Gamma: requires strictly positive targets (no zeros)
- Tweedie: power parameter must match the data-generating process

---

## Metric Selection Guide

| Scenario | Recommended Metric |
|----------|--------------------|
| General regression | R², RMSE |
| Outliers present | MAE, Median Absolute Error |
| Relative errors matter | MAPE |
| Tail / worst-case critical | Max Error, Pinball (high quantile) |
| Count data | Mean Poisson Deviance |
| Strictly positive skewed data | Mean Gamma Deviance |
| Probability-weighted outcomes | Mean Tweedie Deviance |
