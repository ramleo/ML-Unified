<!-- Source: https://lightgbm.readthedocs.io/en/stable/Features.html, https://lightgbm.readthedocs.io/en/stable/Parameters.html — fetched 2026-07-01 -->

# LightGBM Reference Guide

## What LightGBM Is

LightGBM (Light Gradient Boosting Machine) is a gradient boosting framework by Microsoft Research, designed for efficiency and scalability. It achieves faster training speed and lower memory usage than XGBoost on large datasets via two core algorithmic innovations: GOSS and EFB.

---

## Core Algorithmic Innovations

### Histogram-Based Split Finding
Instead of pre-sorted values, LightGBM buckets continuous feature values into discrete bins (default 255). This reduces split-finding complexity from O(#data) to O(#bins). Memory usage drops by storing integer bins rather than floats. **Histogram subtraction trick:** a child's histogram = parent histogram − sibling histogram, halving computation for one child per level.

### GOSS — Gradient-based One-Side Sampling
Traditional sampling treats all instances equally. GOSS retains all instances with large gradients (high training error) and randomly samples instances with small gradients. To correct the distribution, small-gradient samples are upweighted by a constant factor. Result: focuses computation on informative instances while maintaining accuracy, enabling large-data speed-ups.

### EFB — Exclusive Feature Bundling
In high-dimensional sparse datasets many features are mutually exclusive (rarely non-zero simultaneously). EFB bundles such features into a single feature without loss of information. This reduces the effective number of features from O(#features) to O(#bundles), dramatically cutting split evaluation cost.

### Leaf-Wise Tree Growth
LightGBM grows trees **leaf-wise** (best-first): at each step it selects the leaf with maximum delta loss to split, producing asymmetric trees. This achieves lower loss than level-wise growth for the same number of leaves. **Caveat:** on small datasets, leaf-wise growth can overfit — control with `max_depth` and `min_data_in_leaf`.

### Native Categorical Feature Handling
Instead of one-hot encoding (which produces deep, unbalanced trees), LightGBM partitions categorical features into two subsets. The algorithm sorts the histogram by accumulated values to find the optimal binary partition in approximately O(k log k) time for k categories. This avoids 2^(k-1) brute-force subset enumeration.

---

## Supported Tasks and Metrics

**Tasks:** Regression (L2, L1, Huber, Quantile, Poisson, Gamma, Tweedie), binary classification, multiclass, cross-entropy, ranking (LambdaRank, pairwise)

**Metrics:** L1/L2 loss, Huber, binary/multiclass logloss, AUC, NDCG, MAP, accuracy, MCC, Gamma/Tweedie deviance

---

## Distributed Learning

| Mode | Mechanism | Communication cost |
|------|-----------|-------------------|
| Feature Parallel | Each worker holds full data; share best split points only | Low |
| Data Parallel | "Reduce Scatter" to merge feature histograms across workers | O(0.5 × #feature × #bin) |
| Voting Parallel | Top-k feature voting; reduces communication to constant | Constant |

---

## Key Parameters

### Core / Task Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `boosting_type` | `gbdt` | Algorithm: `gbdt` (standard), `rf` (random forest), `dart` (dropout trees), `goss` |
| `objective` | `regression` | Task type: regression variants, `binary`, `multiclass`, `lambdarank`, custom |
| `metric` | `""` | Evaluation metric(s); empty = defaults to objective metric |
| `num_class` | 1 | Required for `multiclass`; number of classes |

### Tree Structure

| Parameter | Default | Description |
|-----------|---------|-------------|
| `num_leaves` | 31 | Maximum leaves per tree; **primary complexity control** for leaf-wise growth |
| `max_depth` | -1 | Depth cap to prevent overfitting; ≤0 = no limit |
| `min_data_in_leaf` | 20 | Minimum samples per leaf; key overfitting guard |
| `min_sum_hessian_in_leaf` | 1e-3 | Minimum hessian sum per leaf; prevents trivial splits |
| `max_delta_step` | 0.0 | Constrains leaf output magnitude; ≤0 = no constraint |

### Training Schedule

| Parameter | Default | Description |
|-----------|---------|-------------|
| `num_iterations` | 100 | Number of boosting rounds (alias: `n_estimators`) |
| `learning_rate` | 0.1 | Shrinkage rate; lower = slower convergence, typically better generalization |
| `early_stopping_rounds` | 0 | Stop if validation metric doesn't improve for N consecutive rounds |

### Regularization

| Parameter | Default | Description |
|-----------|---------|-------------|
| `reg_alpha` | 0.0 | L1 regularization; produces sparsity in leaf weights |
| `reg_lambda` | 0.0 | L2 regularization; shrinks leaf weights |
| `min_gain_to_split` | 0.0 | Minimum information gain required for a split (like XGBoost's gamma) |

### Sampling

| Parameter | Default | Description |
|-----------|---------|-------------|
| `subsample` | 1.0 | Row sampling fraction per iteration (requires `subsample_freq` > 0 for gbdt) |
| `colsample_bytree` | 1.0 | Feature sampling fraction per iteration; < 1.0 reduces overfitting |
| `max_bin` | 255 | Histogram bin count; higher = more accurate splits, slower training |

### Class Imbalance

| Parameter | Default | Description |
|-----------|---------|-------------|
| `is_unbalance` | False | Automatically reweights positive/negative classes for binary classification |
| `scale_pos_weight` | 1.0 | Manual weight multiplier for positive class (do not combine with `is_unbalance`) |

### Output Control

| Parameter | Default | Description |
|-----------|---------|-------------|
| `verbose` | 1 | < 0 = fatal only, 0 = error, 1 = info, > 1 = debug |

---

## Practical Guidance

**Overfitting — reduce by:**
- Lowering `num_leaves` (most impactful for leaf-wise trees)
- Increasing `min_data_in_leaf` (e.g., 50–200 for large datasets)
- Reducing `learning_rate` and increasing `num_iterations` with early stopping
- Adding `reg_lambda` (e.g., 0.1–10) and/or `reg_alpha`
- Reducing `colsample_bytree` (e.g., 0.6–0.8)
- Setting `max_depth` (e.g., 7–15)

**Speed — improve by:**
- Increasing `max_bin` reduces accuracy but speeds up training
- Reducing `num_leaves`
- Using `boosting_type='goss'` for very large datasets
- Enabling GPU training with `device='gpu'`

**Categorical features:** Pass column indices via `categorical_feature` parameter; do not one-hot encode them first.

**num_leaves vs max_depth:** For leaf-wise growth, `num_leaves` is the primary control. A tree with `max_depth=7` can have up to 2^7=128 leaves; set `num_leaves` well below this to avoid overfitting.

**LightGBM vs XGBoost:** LightGBM is typically faster and uses less memory on large datasets due to GOSS+EFB+histograms. XGBoost's `tree_method='hist'` closes much of the speed gap. LightGBM's leaf-wise growth often achieves lower loss with fewer trees but requires more careful overfitting control.
