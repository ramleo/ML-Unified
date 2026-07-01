<!-- Source: https://xgboost.readthedocs.io/en/stable/tutorials/model.html, https://xgboost.readthedocs.io/en/stable/parameter.html — fetched 2026-07-01 -->

# XGBoost Reference Guide

## What XGBoost Is

XGBoost (Extreme Gradient Boosting) is a scalable, regularized gradient boosted decision tree library. It is designed for both performance (systems optimization) and accuracy (ML principles). It consistently ranks among the top performers on structured/tabular data.

---

## How the Algorithm Works

### Model Structure
Prediction is a sum over K trees:
`ŷᵢ = Σₖ fₖ(xᵢ)` where each fₖ is a CART (Classification and Regression Tree).

Trees "try to complement each other" — the ensemble is stronger than any individual tree.

### Additive Training
Trees are learned one at a time (sequentially):
`ŷᵢ⁽ᵗ⁾ = ŷᵢ⁽ᵗ⁻¹⁾ + fₜ(xᵢ)`

At each step, a new tree fₜ is added that minimizes the objective given all previously learned trees.

### Regularized Objective
`obj(θ) = L(θ) + Ω(θ)`

- **L(θ):** Training loss (any differentiable loss function)
- **Ω(θ):** Tree complexity penalty: `γT + ½λ Σⱼ wⱼ²`
  - T = number of leaves, γ = leaf count penalty, λ = L2 weight regularization

This explicit regularization controls bias-variance tradeoff more formally than heuristic approaches (e.g., impurity-based splitting alone).

### Tree Learning via Taylor Expansion
Objective at step t is approximated using second-order Taylor expansion of the loss:
`obj⁽ᵗ⁾ ≈ Σᵢ [gᵢfₜ(xᵢ) + ½hᵢfₜ²(xᵢ)] + Ω(fₜ)`

- gᵢ = first derivative (gradient) of loss w.r.t. ŷᵢ⁽ᵗ⁻¹⁾
- hᵢ = second derivative (hessian)

This formulation allows optimizing **any differentiable loss** with the same tree solver.

### Structure Score and Split Gain
For a given tree structure, optimal leaf weights and minimum objective are:
`obj* = −½ Σⱼ Gⱼ²/(Hⱼ+λ) + γT`

**Split gain** (used to evaluate candidate splits):
`Gain = ½ [G_L²/(H_L+λ) + G_R²/(H_R+λ) − (G_L+G_R)²/(H_L+H_R+λ)] − γ`

If Gain < γ, the split is rejected — this is the principled basis for pruning.

### Key Design Principles
- Loss function flexibility: any differentiable loss via gradient/hessian
- Formal regularization (γ, λ, α) prevents overfitting more robustly than heuristics
- Principled optimization: tree structure and leaf weights are jointly optimized
- Second-order information (Hessian) avoids line search, enabling faster convergence

### XGBoost vs Random Forests
Both use tree ensembles. Key difference: Random Forests train trees independently (parallel); XGBoost trains sequentially, each tree correcting previous errors.

---

## Key Parameters

### General Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `booster` | `gbtree` | Booster type: `gbtree`, `gblinear`, `dart` |
| `device` | `cpu` | Compute device: `cpu`, `cuda`, `cuda:<n>` |
| `nthread` | max available | Parallel threads for training |
| `verbosity` | 1 | 0=silent, 1=warning, 2=info, 3=debug |
| `validate_parameters` | False | Enable input parameter validation |

### Tree Booster Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `eta` / `learning_rate` | 0.3 | Shrinkage step size to prevent overfitting; typical range 0.01–0.3 |
| `max_depth` | 6 | Maximum tree depth; typical range 3–10 |
| `gamma` / `min_split_loss` | 0 | Minimum loss reduction required for a split (higher = more conservative) |
| `min_child_weight` | 1 | Minimum sum of instance hessian in a child node (controls overfitting) |
| `subsample` | 1 | Fraction of training rows sampled per tree; 0.5–0.9 reduces overfitting |
| `colsample_bytree` | 1 | Fraction of columns sampled per tree |
| `colsample_bylevel` | 1 | Fraction of columns sampled per tree level |
| `colsample_bynode` | 1 | Fraction of columns sampled per split node |
| `lambda` / `reg_lambda` | 1 | L2 regularization on leaf weights |
| `alpha` / `reg_alpha` | 0 | L1 regularization on leaf weights (produces sparsity) |
| `max_delta_step` | 0 | Maximum weight update per leaf; useful for imbalanced classification |
| `tree_method` | `auto` | Algorithm: `exact`, `approx`, `hist` (hist recommended for large data) |
| `grow_policy` | `depthwise` | `depthwise` (BFS) or `lossguide` (best-first, like LightGBM) |
| `max_leaves` | 0 | Max leaves to add per tree (lossguide only; 0 = unlimited) |
| `max_bin` | 256 | Max discrete bins for continuous features (hist tree method) |
| `sampling_method` | `uniform` | `uniform` or `gradient_based` (GPU only) |

### Learning Task Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `objective` | `reg:squarederror` | Learning task; determines loss function |
| `eval_metric` | task-dependent | Evaluation metric(s): `rmse`, `mae`, `logloss`, `auc`, `error`, `ndcg`, etc. |
| `seed` | 0 | Random seed for reproducibility |
| `base_score` | auto | Global bias / initial prediction (auto-estimated from data) |

### Objective Options

**Regression:** `reg:squarederror`, `reg:squaredlogerror`, `reg:logistic`, `reg:pseudohubererror`, `reg:absoluteerror`, `reg:quantileerror`, `reg:gamma`, `reg:tweedie`

**Classification:** `binary:logistic` (outputs probability), `binary:logitraw` (outputs margin), `binary:hinge`, `multi:softmax` (outputs class), `multi:softprob` (outputs probability per class)

**Specialized:** `count:poisson`, `survival:cox`, `survival:aft`, `rank:ndcg`, `rank:map`, `rank:pairwise`

---

## Practical Guidance

**Starting point for tuning:**
- Set `n_estimators` high (500–1000) with early stopping
- `learning_rate`: 0.05–0.1
- `max_depth`: 4–6
- `subsample`: 0.8, `colsample_bytree`: 0.8
- `gamma`: 0.1–1.0 if overfitting
- `min_child_weight`: 3–10 for imbalanced data

**For large datasets:** Use `tree_method='hist'` — equivalent to LightGBM's histogram algorithm.

**Class imbalance:** Use `scale_pos_weight = neg_count / pos_count` with `binary:logistic`; or set `max_delta_step=1`.

**Missing values:** XGBoost handles NaN natively — learns optimal default direction per split during training.

**Regularization priority:** Start with `lambda` (L2), then add `alpha` (L1) only if sparsity is desired. `gamma` controls tree complexity directly.
