# Hyperparameter Ranges — Practical Reference

Practical starting ranges for tree-based and linear models on tabular data. These are empirically validated defaults — tune from here rather than searching blind.

---

## XGBoost

| Parameter | Typical Range | Notes |
|-----------|--------------|-------|
| `n_estimators` | 100–1000 | Use early stopping to find optimal |
| `learning_rate` | 0.01–0.3 | Lower LR needs more trees; 0.05–0.1 is a good start |
| `max_depth` | 3–8 | Deeper trees overfit; 4–6 is usually optimal |
| `min_child_weight` | 1–10 | Higher = more conservative, reduces overfitting |
| `subsample` | 0.6–1.0 | Row sampling per tree; 0.8 is a safe default |
| `colsample_bytree` | 0.5–1.0 | Feature sampling per tree; 0.8 is a safe default |
| `gamma` | 0–5 | Minimum loss reduction to split; 0 means always split |
| `reg_alpha` (L1) | 0–1 | Useful for sparse feature sets |
| `reg_lambda` (L2) | 0–10 | Default 1; increase to regularize |
| `scale_pos_weight` | `neg/pos` | For imbalanced classification; set to ratio of negative/positive samples |

**Search order**: Fix `n_estimators` high with early stopping → tune `max_depth` + `min_child_weight` → tune `subsample` + `colsample_bytree` → tune `learning_rate` (lower it, add more trees).

---

## LightGBM

| Parameter | Typical Range | Notes |
|-----------|--------------|-------|
| `n_estimators` | 100–2000 | With early stopping |
| `learning_rate` | 0.01–0.2 | Start at 0.05 |
| `num_leaves` | 20–300 | Main complexity control; `< 2^max_depth` |
| `max_depth` | -1 (unlimited) or 6–12 | Prefer controlling via `num_leaves` |
| `min_child_samples` | 10–100 | Minimum samples per leaf; prevents overfitting on small data |
| `subsample` | 0.6–1.0 | Row sampling (`bagging_fraction`) |
| `colsample_bytree` | 0.5–1.0 | Feature sampling (`feature_fraction`) |
| `reg_alpha` | 0–1 | L1 regularization |
| `reg_lambda` | 0–10 | L2 regularization |
| `is_unbalance` | True/False | Auto-adjusts weights for imbalance |

**Key difference from XGBoost**: `num_leaves` is the primary complexity control. With `max_depth=6`, XGBoost has max 64 leaves; LightGBM can have 300+ at the same depth setting.

---

## CatBoost

| Parameter | Typical Range | Notes |
|-----------|--------------|-------|
| `iterations` | 100–2000 | Equivalent to `n_estimators` |
| `learning_rate` | 0.01–0.3 | Auto-tuned if not set |
| `depth` | 4–10 | CatBoost trees are symmetric (oblivious); depth 6–8 is typical |
| `l2_leaf_reg` | 1–10 | L2 regularization on leaves |
| `border_count` | 32–255 | Quantization borders for numeric features |
| `bagging_temperature` | 0–1 | 0 = no bagging, 1 = full Bayesian bootstrap |
| `random_strength` | 0–10 | Noise for split selection; helps avoid overfitting |

**CatBoost advantage**: Pass categorical column indices via `cat_features` — no manual encoding needed. It handles them via target statistics internally.

---

## Random Forest

| Parameter | Typical Range | Notes |
|-----------|--------------|-------|
| `n_estimators` | 100–500 | More trees = better, diminishing returns after 300 |
| `max_depth` | None or 10–30 | `None` (fully grown) is often best; limit for speed |
| `min_samples_split` | 2–20 | Minimum samples to split a node |
| `min_samples_leaf` | 1–10 | Minimum samples in a leaf |
| `max_features` | `"sqrt"`, `"log2"`, 0.5 | `sqrt` is standard for classification, `1/3` for regression |
| `max_samples` | 0.5–1.0 | Bootstrap sample size (if bootstrap=True) |
| `class_weight` | `"balanced"` | For imbalanced classification |

**Note**: Random Forest is less sensitive to hyperparameters than gradient boosting. Default settings often work well. Focus tuning budget on `max_features` and `min_samples_leaf`.

---

## Logistic Regression / Ridge / Lasso

| Parameter | Typical Range | Notes |
|-----------|--------------|-------|
| `C` (LogReg) | 0.001–100 | Inverse of regularization strength; log scale search |
| `alpha` (Ridge/Lasso) | 0.001–100 | Regularization strength; log scale search |
| `solver` | `"lbfgs"`, `"saga"` | `saga` for L1 or large datasets |
| `max_iter` | 100–1000 | Increase if convergence warnings appear |
| `penalty` | `"l1"`, `"l2"`, `"elasticnet"` | L1 gives sparsity; L2 is default |

**Always scale features** before fitting linear models. Use `StandardScaler` or `MinMaxScaler`.

---

## SVM

| Parameter | Typical Range | Notes |
|-----------|--------------|-------|
| `C` | 0.01–100 | Regularization; higher = less regularization |
| `gamma` | `"scale"`, `"auto"`, 0.001–1 | RBF kernel width; `scale` is a good default |
| `kernel` | `"rbf"`, `"linear"`, `"poly"` | `rbf` for nonlinear, `linear` for high-dim sparse |

**Scale features** before SVM. SVMs do not scale to large datasets (>50k rows) — use SGDClassifier instead.

---

## Optuna Search Spaces

```python
def objective(trial):
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 1000),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
    }
```

Use `log=True` for parameters that span orders of magnitude (`learning_rate`, `C`, `alpha`).

---

## General Tuning Principles

1. **Use early stopping** for gradient boosting — set `n_estimators` high (1000+) and let early stopping find the right count. Avoids overfitting and saves compute.

2. **Search in log space** for regularization parameters and learning rates — the difference between 0.001 and 0.01 matters as much as 0.1 vs 1.0.

3. **Fix one group at a time** — tune tree structure (`max_depth`, `num_leaves`) first, then sampling params, then regularization, then learning rate.

4. **More data beats more tuning** — hyperparameter tuning typically gives 1–3% improvement; getting more/better data often gives 5–20%.

5. **Don't tune on test set** — use cross-validation or a held-out validation set for tuning. Report test set performance only once, at the end.
