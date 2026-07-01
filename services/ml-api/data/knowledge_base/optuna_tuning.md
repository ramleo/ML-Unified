<!-- Source: https://optuna.readthedocs.io/en/stable/tutorial/10_key_features/001_first.html, https://optuna.readthedocs.io/en/stable/tutorial/10_key_features/003_efficient_optimization_algorithms.html — fetched 2026-07-01 -->

# Optuna Hyperparameter Tuning

## What It Does

Optuna is a Python hyperparameter optimization framework. It uses intelligent sampling algorithms — primarily Bayesian optimization via Tree-structured Parzen Estimators (TPE) — to find optimal hyperparameters with far fewer trials than grid or random search. It is model-agnostic and works with any framework where you can write a Python objective function.

---

## Core Concepts

**Study** — an optimization session created via `optuna.create_study(direction="maximize")`. Accumulates all trial history and proposes better values over time.

**Trial** — a single call of the objective function evaluating one set of hyperparameter values.

**Objective function** — accepts a `trial` object, uses `trial.suggest_*` methods to sample parameters, and returns a scalar metric to minimize or maximize.

**Define-by-run API** — the search space is defined dynamically inside the objective function, not declared statically. Enables conditional search spaces (e.g., different params depending on which model type is sampled).

### Key workflow
```python
study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=100)
best = study.best_params   # dict of optimal values
```

---

## suggest_* Methods

| Method | Use Case |
|---|---|
| `trial.suggest_float(name, low, high)` | Continuous parameter |
| `trial.suggest_float(name, low, high, log=True)` | Log-scale (learning rates, regularization) |
| `trial.suggest_int(name, low, high)` | Integer parameter |
| `trial.suggest_int(name, low, high, step=N)` | Stepped integer (e.g. batch sizes) |
| `trial.suggest_categorical(name, choices)` | Discrete choices |

Always use `log=True` for learning rates, regularization strengths, and any parameter spanning multiple orders of magnitude.

---

## Sampling Algorithms

Optuna provides nine samplers; choose based on problem type:

| Sampler | When to Use |
|---|---|
| **TPESampler** (default) | General-purpose; best for mixed search spaces with categorical params |
| **CmaEsSampler** | Purely continuous/integer spaces; outperforms TPE on correlated continuous params |
| **GPSampler** | Low-dimensional continuous spaces; probabilistic, similar to GP-EI |
| **NSGAIISampler** | Multi-objective optimization |
| **QMCSampler** | Better-than-random baseline; systematic low-discrepancy coverage |
| **RandomSampler** | Baseline comparison; useful for small budgets < 15 trials |
| **GridSampler** | Small discrete spaces requiring exhaustive coverage |

**TPE warm-up:** TPE uses random sampling for the first `n_startup_trials` (default 10) before the Bayesian model has enough data. With fewer than ~15 total trials, TPE offers no advantage over random search.

**Multivariate TPE:** `TPESampler(multivariate=True)` models joint distributions over hyperparameters, capturing interactions. Requires more trials to converge but outperforms independent TPE when hyperparameters interact strongly.

---

## Pruning Algorithms

Pruners terminate unpromising trials early based on intermediate results reported via `trial.report(value, step)` and `trial.should_prune()`.

| Pruner | Notes |
|---|---|
| **MedianPruner** | Prunes if intermediate value is worse than median of prior trials at same step. Safe default. |
| **SuccessiveHalvingPruner** | Runs many trials at small budget, promotes top fraction. More aggressive; good for deep learning. |
| **HyperbandPruner** | Combines multiple successive halving brackets. Best for large budgets and neural architecture search. |
| **PercentilePruner** | Eliminates bottom percentile performers |
| **ThresholdPruner** | Halts trials exceeding a predefined value |
| **NopPruner** | Disables pruning |

**When not to prune:** fast-training models (logistic regression, shallow trees) with no meaningful intermediate checkpoints, or models that improve non-monotonically during training.

**For non-deep-learning tasks:** TPESampler + HyperbandPruner outperforms RandomSampler + MedianPruner per benchmarks.

**For deep learning:**
- Limited resources, no categorical params → TPE or GP-EI
- Sufficient resources, no categorical params → CMA-ES or Random Search
- With categorical/conditional params → Random Search or genetic algorithms

---

## n_trials Guidance

| Search Space | Recommended n_trials |
|---|---|
| 2–4 hyperparameters, narrow ranges | 20–40 |
| 5–10 hyperparameters (typical ML) | 50–100 |
| 10+ hyperparameters, wide ranges | 100–300 |
| Deep learning / NAS | 100–500+ with pruning |

A study has likely converged when the best objective value has not improved over the last 20 trials.

---

## Multi-Objective Optimization

Use when you have competing objectives (e.g., maximize AUC while minimizing latency):

```python
study = optuna.create_study(directions=["maximize", "minimize"],
                            sampler=optuna.samplers.NSGAIISampler())
study.optimize(objective, n_trials=200)
pareto_trials = study.best_trials  # non-dominated trials
```

TPE is designed for single-objective optimization; use NSGAIISampler for multi-objective.

---

## Key Visualizations (`optuna.visualization`)

- **`plot_optimization_history`** — best value over trials. Flattening curve = convergence; still rising = add more trials.
- **`plot_param_importances`** — fANOVA-based hyperparameter importance. Params with < 5% importance can be fixed to best-trial value and removed from future searches.
- **`plot_contour`** — objective as a function of two hyperparameters; reveals performance ridges.
- **`plot_parallel_coordinate`** — all hyperparameter values per trial, colored by objective.

---

## Caveats

- With high parallelism (16+ concurrent jobs), TPE quality degrades toward random search because proposals are made before prior trials complete. Use CMA-ES or NSGA-II for heavy parallel workloads.
- fANOVA importance is sensitive to search space width — a param searched over a wide range appears more important simply because it varies more.
- Always use cross-validated metrics as the objective (not a single train/val split) to avoid optimizing to noise.
- Set `seed` on the sampler and `random_state` inside model constructors for reproducibility.
- Disable verbose per-trial logging: `optuna.logging.set_verbosity(optuna.logging.WARNING)`.
