# Optuna Hyperparameter Optimization: Complete Reference

## Overview

Optuna is an open-source, define-by-run hyperparameter optimization framework developed by Preferred Networks. It uses automated search strategies — primarily Bayesian optimization via the Tree-structured Parzen Estimator (TPE) — to find optimal hyperparameters efficiently with far fewer trials than grid search or random search.

Optuna is model-agnostic and framework-agnostic. It works with scikit-learn, XGBoost, LightGBM, CatBoost, PyTorch, TensorFlow, and any other framework where you can write a Python objective function. It supports pruning of unpromising trials, distributed parallel search, multi-objective optimization, and rich visualization of the optimization history.

The central abstraction in Optuna is the **study**, which contains one or more **trials**. Each trial proposes a set of hyperparameter values, evaluates the objective function, and reports a scalar result. The study accumulates trial history and uses it to propose better values in subsequent trials.

---

## How Optuna Differs from Grid Search and Random Search

### Grid Search

Grid search evaluates every combination of a predefined set of values for each hyperparameter. If you have 5 hyperparameters each with 4 candidate values, grid search requires 4^5 = 1,024 evaluations. This grows exponentially (the curse of dimensionality) and becomes computationally infeasible for more than 3–4 hyperparameters with many values.

Grid search has no learning component: each trial is independent, and early results do not influence later choices.

### Random Search

Random search samples hyperparameter values independently at random from specified distributions. Bergstra and Bengio (2012) showed that random search outperforms grid search in high-dimensional spaces because it covers the hyperparameter space more efficiently — any hyperparameter that is unimportant will not waste budget on exhaustive enumeration.

Random search is still sample-inefficient in one key way: it does not learn from previous trials. A random search run of 100 trials will choose the 100th trial's values with no regard for what the first 99 trials revealed.

### Optuna (Bayesian Optimization via TPE)

Optuna builds a probabilistic model of the objective function as trials accumulate. After each trial, it updates its model and proposes the next hyperparameter values that are most likely to improve the objective. This means later trials are informed by earlier ones, and good regions of the hyperparameter space are explored more densely.

In practice, Optuna typically reaches a given performance level with 3–10x fewer trials than random search, and far fewer than grid search, for problems with 5 or more hyperparameters.

---

## TPE Sampler: Tree-structured Parzen Estimator

### Core Mechanics

The TPE sampler (the default sampler in Optuna) models the objective function indirectly. Instead of building a surrogate for `f(x)` (the objective value as a function of hyperparameters `x`), it models two distributions:

- `l(x)`: the density of hyperparameter configurations among "good" trials (those with objective values below a threshold gamma, typically the top 25% of trials)
- `g(x)`: the density of hyperparameter configurations among "bad" trials (the remaining 75%)

The next trial's hyperparameters are chosen by maximizing the ratio `l(x) / g(x)`. This acquisition function is analogous to the Expected Improvement criterion in Gaussian Process-based Bayesian optimization, but is computed more efficiently using kernel density estimates over the observed trial history.

### The Gamma Threshold

The gamma parameter controls the fraction of trials classified as "good." The default in Optuna is `gamma = 0.25` (top 25%). A smaller gamma (e.g., 0.10) makes the sampler more conservative — it focuses more tightly on the best configurations seen so far, which can speed convergence but risks getting stuck in local optima. A larger gamma (e.g., 0.40) makes the sampler more exploratory.

### Warm-Up Period

TPE requires a minimum number of startup trials (default `n_startup_trials=10`) before it has enough data to estimate the `l(x)` and `g(x)` densities meaningfully. During this warm-up period, Optuna uses random sampling. The warm-up period is effectively random search that bootstraps the Bayesian model.

The implication: if your total budget is fewer than 15–20 trials, TPE offers no advantage over random search. In practice, use at least 30 trials for any Optuna study, and prefer 50–100 for models with 5+ hyperparameters.

### Multivariate TPE

Optuna 2.2+ supports `multivariate=True` in `TPESampler`, which models joint distributions over hyperparameters instead of independent marginal distributions. This captures interactions between hyperparameters (e.g., the fact that a high learning rate pairs well with a high momentum value). Multivariate TPE generally outperforms independent TPE for problems with strong hyperparameter interactions but requires more trials to converge because the joint distribution is harder to estimate.

Enable it as:
```python
sampler = optuna.samplers.TPESampler(multivariate=True)
study = optuna.create_study(direction="maximize", sampler=sampler)
```

---

## n_trials Recommendations

### General Rules

- **Small search spaces (2–4 hyperparameters, narrow ranges)**: 20–40 trials is often sufficient.
- **Medium search spaces (5–10 hyperparameters)**: 50–100 trials is the standard recommendation. This gives the TPE sampler enough history to build reliable density estimates.
- **Large search spaces (10+ hyperparameters, wide ranges, or complex interactions)**: 100–300 trials. Consider multivariate TPE and pruning to make the budget go further.
- **Neural architecture search or deep learning**: 100–500+ trials, often with pruning to cut off unpromising runs early.

### Why More Trials Beyond a Point Yield Diminishing Returns

Once Optuna has identified the promising region of hyperparameter space, additional trials mostly refine within that region. The marginal improvement per trial decreases. A practical stopping criterion is to monitor the best objective value over the last 20 trials — if it has not improved, the study has likely converged.

### Practical Recommendation for AutoML Use Cases

For automated ML pipelines where training time is moderate (seconds to a few minutes per trial), a budget of 50 trials per model type is a reasonable default. For fast models (linear models, shallow trees), 100 trials is practical. For slow models (gradient boosting on large datasets, neural networks), 30–50 trials with early stopping and pruning is more appropriate.

---

## Pruning: Cutting Off Unpromising Trials

### What Pruning Does

Pruning (also called early stopping at the study level, not the model level) allows Optuna to terminate a trial before it completes if the trial appears unpromising based on intermediate results reported during training. This is analogous to early stopping in neural network training but applied at the hyperparameter optimization level.

Pruning requires the objective function to report intermediate values at defined checkpoints using `trial.report(value, step)` and to check whether to stop with `trial.should_prune()`.

### MedianPruner

`MedianPruner` is the most commonly used pruner. It prunes a trial at step `s` if the intermediate value at step `s` is worse than the median of all intermediate values at step `s` across all previous trials.

```python
pruner = optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=10)
study = optuna.create_study(direction="maximize", pruner=pruner)
```

- `n_startup_trials=5`: do not prune during the first 5 trials (insufficient data for the median)
- `n_warmup_steps=10`: do not prune within the first 10 steps of any trial (the model may not have stabilized)

MedianPruner is conservative and works well for most use cases.

### SuccessiveHalvingPruner

`SuccessiveHalvingPruner` implements the Asynchronous Successive Halving Algorithm (ASHA). It runs many trials at a small budget, promotes the top fraction to a larger budget, and repeats. This is particularly efficient for neural network training where the number of epochs is the step count.

```python
pruner = optuna.pruners.SuccessiveHalvingPruner(min_resource=1, reduction_factor=3)
```

With `reduction_factor=3`, 1/3 of trials are promoted at each halving step. SuccessiveHalvingPruner is more aggressive than MedianPruner and achieves better speedups when the ranking of trials is consistent across budgets (a property called "early performance predictiveness").

### HyperbandPruner

`HyperbandPruner` combines multiple successive halving runs with different bracket sizes, providing better coverage of the exploration-exploitation trade-off. It is the most sophisticated pruner in Optuna and is recommended for neural architecture search or when you have a very large n_trials budget.

### When Not to Use Pruning

Pruning is not useful when:
- The model trains very quickly (e.g., logistic regression, shallow trees) — there are no meaningful intermediate steps to report
- The objective is deterministic and training cannot be interrupted
- The relationship between early performance and final performance is weak (e.g., models that improve non-monotonically during training)

---

## Define-by-Run API

### Concept

Optuna uses a define-by-run API, meaning the hyperparameter search space is defined dynamically inside the objective function using `trial.suggest_*` methods, rather than declared statically before the optimization starts.

This gives Optuna unique flexibility: the search space can branch based on hyperparameter values, and new hyperparameters can be added at any time.

```python
def objective(trial):
    model_type = trial.suggest_categorical("model_type", ["rf", "xgb", "lgbm"])
    
    if model_type == "rf":
        n_estimators = trial.suggest_int("rf_n_estimators", 50, 500)
        max_depth = trial.suggest_int("rf_max_depth", 3, 15)
        model = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth)
    
    elif model_type == "xgb":
        lr = trial.suggest_float("xgb_lr", 1e-4, 0.3, log=True)
        n_estimators = trial.suggest_int("xgb_n_estimators", 50, 500)
        model = XGBClassifier(learning_rate=lr, n_estimators=n_estimators)
    
    # ... training and evaluation
    return cv_score
```

The define-by-run API is especially powerful for conditional hyperparameter spaces — where valid hyperparameters for one setting are different from those for another setting (e.g., regularization type determines which regularization strength parameter applies).

### suggest_* Methods and Typical Ranges

| Method | Use Case | Example |
|--------|----------|---------|
| `trial.suggest_float(name, low, high)` | Continuous parameters | learning rate, regularization strength |
| `trial.suggest_float(name, low, high, log=True)` | Log-scale continuous | `suggest_float("lr", 1e-5, 1e-1, log=True)` |
| `trial.suggest_int(name, low, high)` | Integer parameters | n_estimators, max_depth |
| `trial.suggest_int(name, low, high, step=N)` | Stepped integers | `suggest_int("batch_size", 32, 256, step=32)` |
| `trial.suggest_categorical(name, choices)` | Discrete choices | `["gini", "entropy"]`, `[True, False]` |

Typical hyperparameter ranges for common models:

**Gradient Boosting (XGBoost / LightGBM):**
- `learning_rate`: `(1e-4, 0.3, log=True)` — most optimal values fall between 0.01 and 0.1
- `n_estimators`: `(100, 1000)` — pair with early stopping in model, not in Optuna
- `max_depth`: `(3, 9)` — deeper trees overfit; GBM trees are usually 4–6
- `subsample`: `(0.5, 1.0)` — row sampling per tree; values below 0.5 underfit
- `colsample_bytree`: `(0.3, 1.0)` — column sampling; often 0.5–0.8 is optimal
- `min_child_weight` (XGBoost) or `min_child_samples` (LightGBM): `(1, 50)`
- `reg_alpha` (L1): `(1e-8, 10.0, log=True)`
- `reg_lambda` (L2): `(1e-8, 10.0, log=True)`

**Random Forest:**
- `n_estimators`: `(100, 1000)` — more trees rarely hurts but has diminishing returns past 300–500
- `max_depth`: `(5, 30)` or `None` — unlimited depth can overfit on small datasets
- `min_samples_split`: `(2, 20)`
- `min_samples_leaf`: `(1, 10)`
- `max_features`: `["sqrt", "log2", None, 0.5, 0.7]`

**Logistic Regression / Ridge:**
- `C` (inverse regularization strength): `(1e-4, 100, log=True)`
- `solver`: `["lbfgs", "liblinear", "saga"]` (conditional on penalty type)

---

## Sampler Options

### TPESampler (Default)

Best general-purpose sampler. Uses Bayesian optimization via Tree-structured Parzen Estimators. Recommended for most use cases.

```python
sampler = optuna.samplers.TPESampler(
    n_startup_trials=10,    # trials before TPE activates (random phase)
    n_ei_candidates=24,     # candidates sampled from l(x) when computing EI
    gamma=lambda x: min(int(np.ceil(0.25 * np.sqrt(x))), 25),  # top fraction
    multivariate=False,     # set True for correlated hyperparameters
    seed=42
)
```

### CmaEsSampler

CMA-ES (Covariance Matrix Adaptation Evolution Strategy) is an evolutionary algorithm that adapts a multivariate Gaussian distribution to model the promising region of the search space. It is particularly effective for continuous hyperparameter spaces and generally outperforms TPE on purely continuous problems with strong correlations.

```python
sampler = optuna.samplers.CmaEsSampler(seed=42)
```

Limitation: CMA-ES does not handle categorical hyperparameters well. Use it only when all hyperparameters are continuous or integer-valued.

Requires at least 5–10x the number of hyperparameters as startup trials before it activates (it falls back to random sampling until then).

### RandomSampler

Pure random search. Useful as a baseline to compare against Bayesian optimization. Always run a random search baseline to confirm that TPE or CMA-ES is actually buying you anything.

```python
sampler = optuna.samplers.RandomSampler(seed=42)
```

### QMCSampler (Quasi-Monte Carlo)

QMCSampler uses quasi-random sequences (Sobol or Halton) instead of pseudo-random sampling. These sequences have lower discrepancy than random sequences, meaning they cover the search space more uniformly. QMCSampler is useful as a better-than-random baseline, especially for moderate-dimensional continuous spaces (5–20 hyperparameters).

```python
sampler = optuna.samplers.QMCSampler(qmc_type="sobol", seed=42)
```

### GridSampler

Optuna includes a `GridSampler` for exhaustive grid search, useful when the search space is small and you want to guarantee coverage.

```python
search_space = {"n_estimators": [100, 300, 500], "max_depth": [3, 5, 7]}
sampler = optuna.samplers.GridSampler(search_space)
```

---

## Metric Selection

### Classification Metrics

- **Accuracy**: Use only for balanced datasets. Optuna maximizes accuracy by default if specified, but it can be a misleading metric for imbalanced classes.
- **AUC-ROC**: The most common metric for binary classification in Optuna studies. It is threshold-independent and handles class imbalance better than accuracy. Specify `direction="maximize"`.
- **F1 Score (macro or weighted)**: Use for multi-class imbalanced problems. Macro F1 weights all classes equally; weighted F1 weights by class frequency.
- **Log-Loss (cross-entropy)**: Appropriate when calibrated probabilities matter. Specify `direction="minimize"`.
- **AUC-PR (Precision-Recall AUC)**: Preferred over AUC-ROC for severe class imbalance (e.g., fraud detection with 0.1% positive rate).

### Regression Metrics

- **RMSE**: Standard for regression; penalizes large errors heavily. `direction="minimize"`.
- **MAE**: More robust to outliers than RMSE. `direction="minimize"`.
- **R-squared**: Can be maximized but is less stable across different dataset scales. RMSE or MAE is usually preferred.
- **MAPE**: Percentage error; avoid when target values can be zero or near zero.

### Cross-Validation vs Single Split

Always use cross-validation as the objective metric in Optuna studies for small-to-medium datasets (up to ~50,000 rows). A single train/validation split has high variance that can mislead the Bayesian optimizer into over-tuning to noise. Use 5-fold cross-validation as the default; use 3-fold when training is slow.

```python
from sklearn.model_selection import cross_val_score

def objective(trial):
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 500),
        "max_depth": trial.suggest_int("max_depth", 3, 9),
        "learning_rate": trial.suggest_float("learning_rate", 1e-3, 0.3, log=True),
    }
    model = XGBClassifier(**params, random_state=42, eval_metric="logloss")
    scores = cross_val_score(model, X_train, y_train, cv=5, scoring="roc_auc")
    return scores.mean()

study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=100)
```

---

## Multi-Objective Optimization

### When to Use It

Multi-objective optimization is appropriate when you have two or more competing objectives, such as:
- Maximizing AUC while minimizing inference latency
- Maximizing accuracy while minimizing model size (number of parameters)
- Maximizing recall while maximizing precision (instead of using F1 as a composite)

### Pareto Front

Optuna's multi-objective mode finds the Pareto front — the set of trials that are not dominated by any other trial (no other trial is better on all objectives simultaneously). You then choose a point on the Pareto front based on your deployment constraints.

```python
study = optuna.create_study(directions=["maximize", "minimize"])
# directions: ["maximize AUC", "minimize training time"]
study.optimize(objective, n_trials=200)

pareto_trials = study.best_trials  # list of non-dominated trials
```

### Sampler for Multi-Objective

Use `NSGAIISampler` (Non-dominated Sorting Genetic Algorithm II) for multi-objective optimization. TPE is designed for single-objective optimization and is less effective in multi-objective settings.

```python
sampler = optuna.samplers.NSGAIISampler(population_size=50, seed=42)
study = optuna.create_study(directions=["maximize", "minimize"], sampler=sampler)
```

A population size of 50 is reasonable for 2–3 objectives with 5–10 hyperparameters. Increase to 100 for more complex problems.

---

## Visualizing Optimization History

Optuna provides built-in visualization via `optuna.visualization` (requires plotly):

### Optimization History Plot

```python
optuna.visualization.plot_optimization_history(study)
```

Shows the best objective value found so far across trials. A curve that flattens early indicates fast convergence (possibly premature). A curve still improving near the end of the budget suggests more trials would help.

### Hyperparameter Importance Plot (fANOVA)

```python
optuna.visualization.plot_param_importances(study)
```

Uses fANOVA (functional ANOVA) to estimate the fraction of objective variance explained by each hyperparameter. This is analogous to ANOVA-based sensitivity analysis. Hyperparameters with near-zero importance can be safely fixed to reduce the search space in subsequent studies.

A hyperparameter with 5% or less fANOVA importance is generally not worth tuning — fix it to the value found in the best trial and remove it from future search.

### Contour Plot

```python
optuna.visualization.plot_contour(study, params=["learning_rate", "max_depth"])
```

Shows the objective value as a function of two hyperparameters with all others marginalized. Identifies the performance ridge in a 2D subspace and reveals sensitivity to specific parameter pairs.

### Parallel Coordinate and Slice Plots

`plot_parallel_coordinate(study)` shows all hyperparameter values per trial colored by objective value — useful for identifying which value combinations co-occur in the best trials. `plot_slice(study)` shows the marginal effect of each hyperparameter independently across all trials.

---

## Hyperparameter Importance: fANOVA

### What fANOVA Measures and How to Use It

fANOVA (functional Analysis of Variance) partitions objective variance into components attributable to each hyperparameter. A high fANOVA score means that hyperparameter explains a large fraction of the variation in objective values across trials. Note that fANOVA importance is conditional on search space width — a hyperparameter searched over a wide range will appear more important simply because it varies more.

After an initial study of 50–100 trials, fix hyperparameters with less than 5% fANOVA importance to their best-trial values and run a second study on the reduced space. This two-stage approach (broad exploration followed by exploitation on a pruned space) often outperforms a single large-budget study.

---

## Parallelism and Distributed Optimization

Optuna supports in-process parallelism via `study.optimize(objective, n_trials=100, n_jobs=4)`. Setting `n_jobs=-1` uses all available cores; there is no benefit to exceeding the number of physical cores. For multi-machine parallelism, use a shared PostgreSQL or MySQL database as the study storage via `optuna.storages.RDBStorage`. Multiple workers participate in the same study, each writing trial results back to the database under optimistic locking.

A critical caution: with high parallelism (16+ concurrent jobs), TPE quality degrades toward random search because proposals are made before prior trials complete. For heavy parallel workloads, CMA-ES or NSGA-II (which are population-based and designed for parallel evaluation) outperform TPE.

---

## Best Practices for Trial Budgets

### Define a Stopping Criterion

Do not rely solely on a fixed `n_trials` budget. Use a callback to stop early when improvement stalls — check if the best value has not changed in the last 20 trials and call `study.stop()`. A tolerance of 1e-4 in the objective is a reasonable threshold for most ML metrics.

### Warm-Starting and Seeding

Warm-start a new study by enqueuing the best parameters from a prior study: `study.enqueue_trial(prior_study.best_params)`. This skips the random exploration phase when a good starting point is already known. For reproducibility, always pass `seed=42` to the sampler constructor and set `random_state` inside model constructors in the objective function.

### Logging and Objective Function Design

Disable verbose per-trial logging with `optuna.logging.set_verbosity(optuna.logging.WARNING)` and use callbacks to log only new best results. Keep the objective function stateless and thread-safe; do not store mutable global state. Handle exceptions by returning `float("nan")` or raising `optuna.exceptions.TrialPruned()` — Optuna excludes NaN trials from best-value tracking. Report intermediate values at regular steps (epoch or cross-validation fold) to enable pruning.

---

## Summary: Key Decision Rules

- **n_trials**: 50 is a safe default for medium search spaces; use 100 for large spaces; use 30 with pruning for slow models.
- **Sampler**: TPE for most cases; CMA-ES for purely continuous spaces; NSGA-II for multi-objective.
- **Pruner**: MedianPruner for most cases; SuccessiveHalvingPruner or HyperbandPruner for neural networks with epoch-level reporting.
- **Startup trials**: Always allow at least 10 random trials before TPE activates.
- **Metric**: Use cross-validated AUC for classification; cross-validated RMSE for regression; always use cross-validation, not a single split.
- **fANOVA**: After an initial study, inspect importance and fix unimportant hyperparameters before refining.
- **Search space**: Use log-scale for learning rates, regularization strengths, and any parameter spanning multiple orders of magnitude.
- **Parallelism**: n_jobs=4 is practical for most workloads; beyond 8 parallel jobs, TPE quality degrades and CMA-ES or NSGA-II is preferred.
- **Reproducibility**: Always set sampler seed; always set model random_state inside objective.