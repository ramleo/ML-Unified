<!-- Source: https://shap.readthedocs.io/en/latest/ — fetched 2026-07-01 -->

# SHAP Interpretation

## What It Does

SHAP (SHapley Additive exPlanations) explains individual ML model predictions using Shapley values from cooperative game theory. Each feature receives a value representing its fair marginal contribution to the prediction relative to the expected model output. The sum of all SHAP values plus the base value (mean prediction) equals the actual prediction for that instance.

---

## Core Concepts

**Shapley Values** — the unique attribution satisfying four axioms: efficiency (values sum to prediction minus base), symmetry, dummy (zero-contribution features get zero), and additivity. No other attribution method satisfies all four simultaneously.

**Base Value** — expected model output across background data. Positive SHAP = feature pushed prediction above base. Negative SHAP = feature pushed prediction below base. Near-zero SHAP = feature had little influence on this instance.

**Explanation Object** — `shap.Explanation` stores SHAP values, base values, and original feature data. All modern plots accept it directly.

---

## Explainers

| Explainer | Best For | Accuracy |
|---|---|---|
| `TreeExplainer` | XGBoost, LightGBM, CatBoost, sklearn forests/trees | Exact, fast |
| `LinearExplainer` | Linear/logistic regression, Ridge, Lasso | Exact |
| `DeepExplainer` | TensorFlow / PyTorch networks | Approximate (DeepLIFT-based) |
| `GradientExplainer` | Gradient-based neural nets | Approximate (integrated gradients) |
| `KernelExplainer` | Any model (model-agnostic) | Approximate, slowest |

Always prefer a model-specific explainer over `KernelExplainer` — it can be orders of magnitude faster and is exact.

---

## Key Visualizations

**`shap.plots.waterfall(explanation[i])`** — single prediction breakdown, step-by-step from base value to final prediction. Best for communicating one decision to stakeholders.

**`shap.plots.beeswarm(explanation)`** — global view; one dot per sample per feature. X-axis = SHAP value, color = feature value (red = high). Reveals direction, magnitude, and distribution of each feature's impact across the dataset.

**`shap.plots.bar(explanation)`** — mean absolute SHAP per feature. Quick global importance ranking; hides distributional detail.

**`shap.plots.force(explanation[i])`** — horizontal force diagram for a single prediction. Red bars push up, blue push down.

**`shap.plots.scatter(explanation[:, "feature_name"])`** — SHAP value vs. feature value for one feature, optionally colored by a second feature. Reveals non-linear effects and interactions. Replaces the legacy `dependence_plot`.

---

## Important Parameters

- **`masker`** (KernelExplainer) — controls how absent features are handled. `shap.maskers.Independent(data)` uses marginal distribution; `shap.maskers.Partition(data)` uses conditional.
- **`max_evals`** (KernelExplainer) — more evaluations = more accurate SHAP values, but slower.
- **`check_additivity=False`** (TreeExplainer) — skip the additivity check for speed on large datasets.
- **Background dataset** (DeepExplainer, KernelExplainer) — 50–500 representative samples. Use `shap.kmeans(X_train, k)` to summarize large training sets.

---

## Supported Data Types

SHAP supports tabular, text (sentiment, summarization, QA), image (classification, captioning), and genomic data via the appropriate explainer and masker combination.

---

## When to Use

- Post-hoc explanation of any trained model without retraining.
- Debugging unexpected predictions or model behavior.
- Feature selection: rank by mean absolute SHAP on a validation set.
- Compliance and regulatory documentation of per-prediction reasoning.
- Comparing two model versions by their SHAP distributions.

---

## Caveats

- SHAP explains the **model**, not the real-world causal process. High SHAP importance does not imply causality.
- In binary classification, SHAP values are in **log-odds space**. Individual values are not additive probability changes — applying sigmoid to their sum gives the probability, not summing the values directly.
- Correlated features **split their SHAP values** between them. Individual importance can be misleading when multicollinearity is high.
- `KernelExplainer` is slow on large datasets; subsample background data (`shap.sample(X, 100)`).
- `DeepExplainer` and `GradientExplainer` are approximations; results can differ from exact Shapley values.
- Different background datasets for KernelSHAP / DeepSHAP yield different base values and therefore different SHAP values. Background dataset choice is a modeling decision.
- `TreeExplainer` with `feature_perturbation="interventional"` requires a background dataset and is slower but more theoretically sound for correlated features.
