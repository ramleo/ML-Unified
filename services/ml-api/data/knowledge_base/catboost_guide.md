<!-- Source: https://catboost.ai/docs/en/concepts/algorithm-main-stages, https://catboost.ai/docs/en/references/training-parameters/common — fetched 2026-07-01 -->

# CatBoost Reference Guide

## What CatBoost Is

CatBoost (Categorical Boosting) is a gradient boosted decision tree library by Yandex (open-sourced 2017). Its primary differentiators are: native categorical feature handling without preprocessing, **ordered boosting** to eliminate prediction shift (a subtle form of target leakage), and **symmetric (oblivious) trees** as default base learners.

---

## Core Algorithm

### Ordered Boosting
Standard gradient boosting computes gradients using the same data used to build the model, causing gradient estimates to be biased (prediction shift). CatBoost uses **ordered boosting**: it processes training instances in a random permutation and for each instance computes the residual using a model trained only on instances preceding it in the permutation. This eliminates target leakage from gradient estimation.

### Categorical Feature Handling — Ordered Target Statistics
Instead of one-hot encoding, CatBoost converts categorical values to numeric using **target statistics** (TS):

`TS(cat_value) = (Σ yᵢ [xᵢ = cat_value] + prior) / (count(cat_value) + 1)`

To prevent target leakage, CatBoost computes ordered TS: for each sample the TS is computed only from preceding samples in the random permutation. Multiple permutations are used across training iterations. This allows native handling of high-cardinality categoricals without risk of overfitting.

**one_hot_max_size:** Categories with ≤ this many distinct values are one-hot encoded instead (avoids TS for low-cardinality features).

### Symmetric (Oblivious) Trees
By default CatBoost uses **symmetric trees**: the same split condition is applied at every node of a given tree level. This produces balanced trees where all leaves at a given depth use the same feature+threshold. Benefits: fast prediction (index into a fixed table), regularization effect (symmetric constraint reduces variance), and GPU-friendly structure.

Alternative `grow_policy` values (Depthwise, Lossguide) produce standard asymmetric trees like XGBoost/LightGBM.

### Main Training Stages per Tree
1. **Preliminary split calculation** — candidate splits are computed upfront
2. **Feature transformation** (if applicable):
   - Categorical features → numeric via ordered target statistics
   - Text features → numeric representations
   - Embedding features → processed numeric form
3. **Tree structure selection** — determines splits and topology
4. **Leaf value computation** — calculates final predictions for leaves
5. **Overfitting detection** — halts training automatically if validation metrics deteriorate

---

## Key Training Parameters

### Core Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `iterations` | 1000 | Maximum number of trees (aliases: `n_estimators`, `num_boost_round`, `num_trees`) |
| `learning_rate` | 0.03 | Gradient step size; auto-calibrated for some loss functions |
| `random_seed` | 0 | Reproducibility seed (alias: `random_state`) |
| `thread_count` | -1 | CPU threads; -1 = all available |
| `loss_function` | `Logloss` (clf) / `RMSE` (reg) | Training objective (alias: `objective`) |
| `eval_metric` | Same as `loss_function` | Metric for overfitting detection and model selection |
| `custom_metric` | None | Additional metrics to track (not optimized) |

### Tree Structure

| Parameter | Default | Description |
|-----------|---------|-------------|
| `depth` | 6 | Tree depth (alias: `max_depth`); range: up to 16 (CPU), up to 8 (GPU pairwise) |
| `grow_policy` | `SymmetricTree` | Tree construction: `SymmetricTree`, `Depthwise`, `Lossguide` |
| `min_data_in_leaf` | 1 | Min training samples per leaf (alias: `min_child_samples`); Lossguide/Depthwise only |
| `max_leaves` | 31 | Max leaf count (alias: `num_leaves`); Lossguide only |

### Regularization

| Parameter | Default | Description |
|-----------|---------|-------------|
| `l2_leaf_reg` | 3.0 | L2 regularization coefficient on leaf weights (alias: `reg_lambda`) |
| `bagging_temperature` | 1 | Bayesian bootstrap intensity; 0 = no randomness, higher = more random |
| `subsample` | 0.66–0.8 | Row sampling rate; applies with Poisson/Bernoulli/MVS bootstrap types |
| `rsm` | 1 | Random subspace method: fraction of features per split (alias: `colsample_bylevel`) |

### Boosting Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `boosting_type` | Context-dependent | `Ordered` (default on small datasets) or `Plain` (standard gradient boosting) |
| `bootstrap_type` | `Bayesian` (most common) | Sampling method: `Bayesian`, `Bernoulli`, `MVS`, `Poisson`, `No` |
| `sampling_frequency` | `PerTreeLevel` | When to sample: `PerTree` or `PerTreeLevel` |

### Categorical Feature Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `cat_features` | None | Indices or names of categorical columns; no preprocessing needed |
| `one_hot_max_size` | 2–255 (context) | Use one-hot encoding for categoricals with ≤ this many unique values |

### Overfitting Detection

| Parameter | Default | Description |
|-----------|---------|-------------|
| `od_type` | `IncToDec` | Detection method: `IncToDec` (metric increase), `Iter` (fixed iteration count) |
| `od_wait` | 20 | Iterations to wait after best metric before stopping |

### Feature Management

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ignored_features` | None | Feature indices to exclude from training |
| `border_count` | 254 | Number of splits for numerical feature quantization (alias: `max_bin`) |

### Missing Values

| Parameter | Default | Description |
|-----------|---------|-------------|
| `nan_mode` | `Min` | NaN handling: `Min` (treat as less than all values), `Max`, `Forbidden` |
| `has_time` | False | Preserve original object order; disables random permutations |

---

## Supported Loss Functions

**Classification:** `Logloss`, `CrossEntropy`, `MultiClass`, `MultiClassOneVsAll`
**Regression:** `RMSE`, `MAE`, `Quantile`, `LogLinQuantile`, `Poisson`, `Huber`, `Tweedie`, `MAPE`
**Ranking:** `YetiRank`, `PairLogit`, `QueryRMSE`, `QuerySoftMax`

---

## Practical Guidance

**Categorical features:** Pass column names/indices via `cat_features`; do not encode beforehand. CatBoost handles frequency encoding, target statistics, and combinations automatically.

**Overfitting control:**
- Reduce `depth` (default 6 is already conservative for symmetric trees)
- Increase `l2_leaf_reg` (try 1–10)
- Reduce `learning_rate` and increase `iterations` with early stopping
- Reduce `rsm` (e.g., 0.5–0.8) for feature subsampling

**Ordered vs Plain boosting:** `Ordered` is slower but more resistant to overfitting on small/medium datasets. `Plain` is faster and often equivalent on large datasets.

**GPU training:** Set `task_type='GPU'`; reduces max depth to 8 for pairwise losses.

**CatBoost vs XGBoost/LightGBM:** CatBoost requires less preprocessing (no encoding, handles NaN natively). Ordered boosting provides strong out-of-box generalization. Symmetric trees make prediction very fast. Generally wins on datasets with many categorical features; competitive on pure numerical data.
