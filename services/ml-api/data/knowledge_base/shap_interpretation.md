# SHAP Values: Interpretation and Best Practices

## Overview

SHAP (SHapley Additive exPlanations) is a unified framework for interpreting machine learning model predictions. It is grounded in cooperative game theory and provides a theoretically principled way to attribute the contribution of each input feature to a model's output for any individual prediction or across an entire dataset.

SHAP was introduced by Lundberg and Lee (2017) and builds on the concept of Shapley values from cooperative game theory. It has become the de-facto standard for model interpretability because it satisfies important theoretical axioms that simpler methods such as permutation importance or LIME do not fully respect.

---

## Shapley Values: Game Theory Foundation

### The Coalition Game Analogy

In cooperative game theory, a coalition game involves a set of players who cooperate to produce a total payout. The question is: how should the payout be fairly distributed among the players given that different subsets (coalitions) of players can achieve different payouts?

Shapley values answer this by computing each player's average marginal contribution across all possible orderings in which players can join the coalition. Formally, the Shapley value for player `i` is:

```
phi_i = sum over S (|S|! * (|N| - |S| - 1)! / |N|!) * [v(S union {i}) - v(S)]
```

Where:
- `N` is the full set of players (features)
- `S` is a subset of features not containing feature `i`
- `v(S)` is the model's prediction using only the features in subset `S`
- The outer sum is taken over all subsets `S` of `N \ {i}`

In the ML context, features are "players," the model prediction is the "payout," and the Shapley value for each feature is its fair share of the prediction relative to the baseline (expected model output).

### Key Theoretical Properties

SHAP values satisfy four axioms that make them uniquely fair:

1. **Efficiency**: The sum of all SHAP values equals the difference between the model's prediction for the instance and the expected model output across the training data. This means the explanation is complete — no contribution is unaccounted for.

2. **Symmetry**: If two features contribute identically to all coalitions, they receive equal SHAP values.

3. **Dummy**: A feature that contributes nothing to any coalition receives a SHAP value of zero.

4. **Linearity (Additivity)**: The Shapley value for a combined game is the sum of Shapley values for the component games. This means SHAP values for ensemble models can be decomposed and are additive across base learners in certain settings.

No other attribution method simultaneously satisfies all four axioms. This theoretical grounding is the primary reason SHAP is preferred over alternatives.

---

## Local vs Global Explanations

### Local Explanation

A local explanation answers the question: "Why did this model predict this value for this specific instance?"

Each individual prediction has its own set of SHAP values — one per feature. These values sum to the prediction minus the base value (mean prediction over the dataset). For a single instance, a positive SHAP value for a feature means that feature pushed the prediction higher than the base value; a negative SHAP value means it pushed the prediction lower.

Local explanations are most useful for:
- Auditing specific high-stakes decisions (loan denial, medical diagnosis)
- Debugging unexpected predictions
- Communicating model reasoning to end users on a per-record basis

### Global Explanation

A global explanation aggregates local explanations across many instances to describe the model's overall behavior. The most common approach is to take the mean absolute SHAP value for each feature across the dataset:

```
global_importance(feature_i) = mean(|phi_i(x)| for all x in dataset)
```

This gives a feature importance ranking that reflects average impact across all predictions, not just the training loss gradient. Global explanations answer: "Which features does this model rely on most, on average?"

Global explanations are useful for:
- Feature selection decisions
- Model validation against domain knowledge
- Regulatory documentation of model behavior
- Comparing two models' reliance on different features

---

## Interpreting SHAP Value Signs and Magnitudes

### Positive SHAP Values

A positive SHAP value for feature `i` in a given instance means that feature `i` increased the model's prediction relative to the expected prediction. In regression, this means the feature pushed the predicted numeric value upward. In binary classification with log-odds output, a positive SHAP value means the feature increased the probability of the positive class.

Example: In a house price model, if the feature "square footage = 2500 sqft" has a SHAP value of +45,000, it means having 2500 sqft contributed an additional $45,000 to the predicted price compared to the average prediction.

### Negative SHAP Values

A negative SHAP value means the feature pushed the prediction below the baseline. The feature's actual value in this instance made the model predict less than it would on average.

Example: In a credit risk model, if "missed_payments = 3" has a SHAP value of -0.15 (in log-odds), this feature decreased the probability of loan approval.

### SHAP Value of Zero

A SHAP value near zero means the feature had little or no influence on this particular prediction. This can happen when a feature's value is close to its average, or when the model does not rely heavily on that feature for that region of input space.

### Magnitude

The magnitude of a SHAP value (its absolute value) indicates the strength of the feature's influence on that prediction. Large absolute SHAP values indicate the feature was a dominant driver of the model's output for that instance.

---

## SHAP for Classification vs Regression

### Regression

In regression tasks, SHAP values are in the same units as the target variable. If predicting house prices in dollars, SHAP values are in dollars. The base value is the mean predicted price across the training set. The SHAP values for all features in an instance sum exactly to `prediction - base_value`.

### Binary Classification

For binary classification, SHAP values are typically computed in log-odds space (before the sigmoid is applied). The base value is `log-odds(base_rate)`. A SHAP value of +1.0 in log-odds corresponds to roughly a 2.7x increase in the odds of the positive class.

To convert SHAP values to probability impact, you need to apply the sigmoid transformation to the sum of base value and SHAP values. Individual SHAP values do not directly translate to probability differences because of the nonlinearity of the sigmoid — interpreting them as probability shifts is a common misinterpretation.

### Multi-class Classification

For multi-class problems, SHAP returns a matrix of values with shape `(n_instances, n_classes, n_features)`. Each class has its own set of SHAP values, reflecting how each feature shifted the model output toward or away from that class. You can plot SHAP values separately for each class, or sum absolute values across classes for a global feature importance.

---

## SHAP Visualization Types

### Beeswarm Plot (Summary Plot with Dots)

The beeswarm plot is the most information-dense global visualization. Each dot represents one instance and one feature. The x-axis shows the SHAP value (impact on model output). The y-axis shows features ranked by mean absolute SHAP value (most important at top). Color encodes the actual feature value (red = high, blue = low).

Reading a beeswarm plot:
- If high feature values (red) cluster on the positive SHAP side, the feature has a positive relationship with the target
- If high values cluster on the negative side, the relationship is inverse
- Wide horizontal spread means the feature is influential for many instances with varying magnitudes
- Tight clustering near zero means the feature rarely has a strong effect

Beeswarm plots reveal whether a feature's effect is monotone, whether there are outliers, and whether the feature has high variance in impact across instances.

### Force Plot

A force plot explains a single prediction. It shows the base value on the left and the final prediction on the right. Features that push the prediction higher (positive SHAP) are shown in red, features that push it lower are shown in blue. The width of each bar is proportional to the SHAP magnitude.

Force plots can be stacked vertically for many instances to create a "stacked force plot," which reveals patterns across a dataset — for instance, whether certain feature combinations always produce high-risk predictions.

### Waterfall Plot

A waterfall plot is another single-prediction visualization, drawn as a bar chart that starts at the base value and adds or subtracts each feature's SHAP value step by step until reaching the final prediction. Features are sorted by absolute impact.

Waterfall plots are preferred over force plots when you need to communicate to a non-technical audience, because the step-by-step format is more intuitive than overlapping bars.

### Summary Bar Plot

The summary bar plot shows mean absolute SHAP values per feature as horizontal bars. It is the simplest global importance visualization — equivalent to a SHAP-based feature importance ranking. It does not show direction of effect or distribution across instances. Use it when you need a quick ranked list of features without the distributional detail of a beeswarm plot.

### Dependence Plot

A SHAP dependence plot shows the relationship between one feature's values (x-axis) and its SHAP values (y-axis) for all instances. Color encodes the value of a second feature, chosen automatically by SHAP to highlight interactions. A linear trend in a dependence plot means the model treats the feature linearly. A non-linear trend means the model has learned a complex relationship.

Dependence plots are the primary tool for understanding how SHAP values for one feature vary as a function of that feature's value and its interactions with another feature.

---

## Feature Interactions

### Interaction SHAP Values

SHAP can compute pairwise interaction values using `shap.TreeExplainer(model).shap_interaction_values(X)`. This returns a 3D array of shape `(n_instances, n_features, n_features)`. The diagonal entries are main effects; off-diagonal entries are interaction effects between pairs of features.

The sum of all interaction values for an instance equals the total SHAP value for that instance, decomposed into main effects and interaction effects.

### Reading Dependence Plots for Interactions

When a dependence plot is colored by a second feature and shows a clear separation of colors at different x-values (the primary feature's value), this indicates an interaction effect. For example, if the SHAP values for "age" are high for one segment but only when "income" is also high (red), that is an interaction between age and income.

### Practical Importance of Interactions

Interaction effects matter for model auditing. A model might appear to use a protected attribute only weakly when looking at main effects, but could be encoding a strong interaction between that attribute and a correlated feature. Interaction SHAP values can detect these hidden dependencies.

---

## TreeSHAP vs KernelSHAP

### TreeSHAP

TreeSHAP is an exact, efficient algorithm for tree-based models (decision trees, random forests, gradient boosting machines such as XGBoost, LightGBM, and CatBoost). It computes exact Shapley values in polynomial time — O(TLD^2) where T is the number of trees, L is the maximum number of leaves, and D is the maximum depth.

TreeSHAP is preferred for tree models because:
- It is exact, not approximate
- It is fast enough to run on full training sets
- It correctly handles feature correlations within the tree structure
- It supports interaction values

Usage:
```python
import shap
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X)
```

### KernelSHAP

KernelSHAP is a model-agnostic approximation that works for any model by fitting a weighted linear model to masked inputs. It uses a kernel function to weight coalition samples in a way that makes the linear model's coefficients equal to Shapley values in expectation.

KernelSHAP is slow — it requires many model evaluations per instance. For a model with 20 features and 1000 instances, computing KernelSHAP may require millions of forward passes. It is also approximate; the accuracy depends on the number of background samples and coalitions evaluated.

Use KernelSHAP when:
- The model is not tree-based (neural networks, SVMs, linear models with custom pipelines)
- Exact computation is not needed and approximation error is acceptable

For linear models, use `shap.LinearExplainer` instead of KernelSHAP — it is exact and far faster.

### DeepSHAP

DeepSHAP (also called `shap.DeepExplainer`) approximates SHAP values for deep learning models using a backpropagation-based method related to DeepLIFT. It is faster than KernelSHAP for neural networks but still approximate. It requires a background dataset of representative samples (typically 50–200 instances).

---

## SHAP for Feature Selection

### Method

SHAP-based feature selection uses global importance (mean absolute SHAP values) to rank features, then eliminates those with near-zero importance. This is more reliable than gain-based or split-based importance from tree models because SHAP correctly decomposes credit for correlated features, whereas gain-based importance can arbitrarily assign importance to one of two correlated features.

### Practical Steps

1. Train an initial model on all features
2. Compute SHAP values on a held-out validation set
3. Rank features by mean absolute SHAP value
4. Remove features below a threshold (e.g., those with mean absolute SHAP < 0.001 or those below a percentile cutoff such as the bottom 10%)
5. Retrain and compare validation performance

### Advantage Over Permutation Importance

Permutation importance suffers when features are correlated: permuting one feature may cause unrealistic out-of-distribution instances because the correlated feature still holds its original value. SHAP values handle this more gracefully because they average over coalitions, not permutations of independent features.

---

## Common Misinterpretations

### Misinterpretation 1: SHAP as Causal Effect

SHAP values describe the model's behavior, not the real-world causal effect of a feature. A high SHAP value for "zip code" does not mean that changing zip code causes the prediction to change in the real world — it means the model used zip code in that way. Causal claims require causal analysis frameworks (do-calculus, instrumental variables), not SHAP.

### Misinterpretation 2: Individual SHAP Values as Probability Changes in Classification

In binary classification, SHAP values are in log-odds space. Adding up SHAP values and applying sigmoid gives the probability, but individual SHAP values are not additive probability changes. A SHAP value of +0.5 in log-odds does not mean the feature increased the probability by 50 percentage points.

### Misinterpretation 3: Negative SHAP = Irrelevant Feature

A feature can have a large negative SHAP value, meaning it is highly influential (it strongly decreased the prediction). Irrelevance is indicated by SHAP values near zero, not negative values. A feature with consistently large negative values is just as important as one with consistently large positive values.

### Misinterpretation 4: SHAP Works the Same for All Model Types

TreeSHAP (exact) and KernelSHAP (approximate) can give different answers for the same model. Different background datasets for KernelSHAP and DeepSHAP will also yield different values. The choice of background dataset (the "null coalition" distribution) materially affects the base value and therefore the SHAP values.

### Misinterpretation 5: SHAP Explains the Data-Generating Process

SHAP explains the model's predictions. If the model is poorly fitted, overfit, or based on spurious correlations, SHAP faithfully explains a bad model. High SHAP importance for a feature does not validate the feature's real-world relevance; it only confirms the model used it.

---

## SHAP with Ensemble Models

### Random Forests

For random forests, `shap.TreeExplainer` computes exact SHAP values by averaging over all trees. The base value is the mean prediction across all trees. Each tree's SHAP values are averaged, and the result reflects the ensemble's behavior, not any single tree.

### Gradient Boosted Trees (XGBoost, LightGBM, CatBoost)

TreeSHAP natively supports gradient boosted tree models. Because boosted models are additive (each tree adds a correction to the previous prediction), SHAP values decompose cleanly across trees. The final SHAP value for a feature is the sum of that feature's SHAP contributions across all trees.

### Stacking and Voting Ensembles

For stacking ensembles, SHAP can be applied to the meta-learner, treating the base learners' outputs as input features. This reveals which base learner's predictions were most influential. For voting ensembles, you can compute SHAP for each base learner separately and average, but this requires care because different learners have different base values.

### Neural Networks in Ensembles

When a neural network is part of an ensemble, use DeepSHAP for the neural component and combine with TreeSHAP values for tree components, weighting by ensemble weights if applicable.

---

## Practical Configuration and Performance Tips

### Background Dataset Size

For KernelSHAP and DeepSHAP, the background dataset (also called the reference set or null coalition) should be representative of the training distribution. Typical sizes are 50 to 500 instances. Too small leads to high variance in SHAP estimates; too large increases computation time. Using k-means clustering to summarize the background (via `shap.kmeans(X_train, k)`) is a standard approach.

### Subsampling for Large Datasets

For TreeSHAP on very large datasets, computing SHAP values for every training instance can be expensive. A common practice is to compute SHAP values on a random sample of 1,000 to 10,000 instances for global explanations. For local explanations on specific instances, always use the full data.

### Approximate TreeSHAP

TreeSHAP supports an `approximate=True` flag that uses path-dependent feature perturbation instead of interventional perturbation. This is faster but changes the interpretation slightly — path-dependent SHAP conditions on the training data distribution in the tree's decision path. Use the default (`approximate=False`) unless computation time is prohibitive.

### Reproducibility

SHAP values from KernelSHAP are stochastic because they sample coalitions. Set a random seed in your environment and control the number of evaluations (`nsamples` parameter in `KernelExplainer.shap_values`) to make results reproducible.

---

## Summary of Key Decision Rules

- Use `TreeExplainer` for all tree-based models; it is exact and fast.
- Use `LinearExplainer` for linear models (logistic regression, linear regression, ridge).
- Use `DeepExplainer` for neural networks when approximate values are acceptable.
- Use `KernelExplainer` as a last resort for black-box models with no dedicated explainer.
- Always report whether SHAP values are in log-odds or probability space for classification.
- For feature selection, use mean absolute SHAP on a validation set, not the training set.
- Do not interpret SHAP values as causal effects.
- Use beeswarm plots for global exploration; use waterfall or force plots for single-instance communication.
- Verify SHAP-based feature importance against domain knowledge before using it to remove features from a production model.