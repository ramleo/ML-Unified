"""Regression training helpers for the AutoML /train endpoint."""
import os

import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    RandomForestRegressor, GradientBoostingRegressor, ExtraTreesRegressor,
)
from sklearn.linear_model import Ridge as RidgeRegressor, Lasso, ElasticNet
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score,
    median_absolute_error, mean_absolute_percentage_error,
)
from sklearn.model_selection import cross_val_score, KFold, learning_curve
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.svm import SVR
from sklearn.tree import DecisionTreeRegressor

from routers.core.automl_helpers import (
    _cv_sample, _extract_feature_importances, _optuna_tune, _build_tuned_estimator,
    _rule_explanation, _llm_explanation,
)
from routers.core.shared import _detect_gpu


def run_regression(
    p, X, y, algorithm, selected_models, tune, n_trials,
    transformers, num_cols, cat_cols,
    XGBRegressor, LGBMRegressor, CatBoostRegressor,
    opt_metric: str = "auto",
    sampler: str = "tpe",
    secondary_metric: str = "none",
):
    import numpy as np  # noqa: PLC0415
    y_num = pd.to_numeric(y, errors="coerce")
    y_enc = y_num.fillna(float(y_num.median()))

    automl_result = None
    _effective_algorithm = algorithm

    if algorithm == "AutoML":
        automl_result, estimator, _effective_algorithm = _automl_reg(
            p, X, y_enc, selected_models, tune, n_trials, transformers,
            XGBRegressor, LGBMRegressor, CatBoostRegressor,
            opt_metric=opt_metric,
            sampler=sampler,
            secondary_metric=secondary_metric,
        )
    else:
        estimator = _single_reg_estimator(algorithm, XGBRegressor, LGBMRegressor, CatBoostRegressor)

    from sklearn.model_selection import train_test_split as _tts
    pipeline = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")), ("model", estimator)])
    split    = 0.2 if len(X) >= 10 else 0.1
    X_train, X_test, y_train, y_test = _tts(X, y_enc, test_size=split, random_state=42)
    if automl_result:
        automl_result["n_train"] = len(X_train)
        automl_result["n_test"]  = len(X_test)
    train_pct = (79 if (tune and automl_result) else 68 if automl_result else 20)
    p.update(train_pct, f"Training {_effective_algorithm} regressor…")
    pipeline.fit(X_train, y_train)
    p.update(82, "Evaluating on test set…")
    y_pred       = pipeline.predict(X_test)
    mae          = mean_absolute_error(y_test, y_pred)
    metric       = f"±{mae:.2f}"
    metric_label = "MAE"
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    r2   = r2_score(y_test, y_pred)
    extra_metrics = [{"label": "RMSE", "value": f"{rmse:.2f}"}]
    if r2 >= 0.60:
        extra_metrics.append({"label": "R²", "value": f"{r2:.3f}"})

    import random as _rnd_act  # noqa: PLC0415
    _ya = np.array(y_test)
    _yp = np.array(y_pred)
    _n_act = len(_ya)
    _act_idxs = sorted(_rnd_act.sample(range(_n_act), min(300, _n_act)))
    _actuals_data: dict = {
        "actual":    [round(float(v), 4) for v in _ya[_act_idxs]],
        "predicted": [round(float(v), 4) for v in _yp[_act_idxs]],
        "mae":  round(float(mae), 4),
        "rmse": round(float(rmse), 4),
        "residual_std": round(float(np.std(_ya - _yp)), 4),
    }
    if r2 >= 0.60:
        _actuals_data["r2"] = round(float(r2), 4)

    if automl_result:
        _fill_automl_reg_metrics(
            p, automl_result, pipeline, y_test, y_pred, mae, rmse, r2,
            X, y_enc, transformers, num_cols, cat_cols, tune, n_trials, opt_metric,
        )

    return {
        "pipeline": pipeline, "metric": metric, "metric_label": metric_label,
        "extra_metrics": extra_metrics, "automl_result": automl_result,
        "actuals_data": _actuals_data, "effective_algorithm": _effective_algorithm,
    }


def _fill_automl_reg_metrics(
    p, automl_result, pipeline, y_test, y_pred, mae, rmse, r2,
    X, y_enc, transformers, num_cols, cat_cols, tune, n_trials, opt_metric="auto",
):
    import numpy as np  # noqa: PLC0415
    y_test_arr = np.array(y_test)
    mape    = float(mean_absolute_percentage_error(y_test_arr, y_pred))
    med_ae  = float(median_absolute_error(y_test_arr, y_pred))
    max_err = float(np.max(np.abs(y_test_arr - y_pred)))
    wm_reg = {
        "mae":       round(float(mae),  4),
        "rmse":      round(float(rmse), 4),
        "r2":        round(float(r2),   4),
        "mape":      round(mape,         4),
        "max_error": round(max_err,      4),
        "median_ae": round(med_ae,       4),
    }
    automl_result["winner_metrics"] = wm_reg

    try:
        _bt_arr  = np.array(y_test)
        _bp_arr  = np.array(y_pred)
        _use_r2  = r2 >= 0.60
        _bt_samples = []
        _rng = np.random.default_rng(42)
        for _ in range(200):
            _idx = _rng.integers(0, len(_bt_arr), len(_bt_arr))
            if _use_r2:
                _bt_samples.append(float(r2_score(_bt_arr[_idx], _bp_arr[_idx])))
            else:
                _bt_samples.append(float(np.sqrt(mean_squared_error(_bt_arr[_idx], _bp_arr[_idx]))))
        automl_result["ci_95"] = {
            "lower":  round(float(np.percentile(_bt_samples, 2.5)),  4),
            "upper":  round(float(np.percentile(_bt_samples, 97.5)), 4),
            "metric": "r2" if _use_r2 else "rmse",
        }
    except Exception as _ci_err:
        print(f"CI bootstrap failed: {_ci_err}", flush=True)

    import random as _rnd  # noqa: PLC0415
    n_pts = len(y_test_arr)
    idxs  = sorted(_rnd.sample(range(n_pts), min(300, n_pts)))
    automl_result["scatter_actual"]    = [round(float(v), 4) for v in y_test_arr[idxs]]
    automl_result["scatter_predicted"] = [round(float(v), 4) for v in y_pred[idxs]]

    X_cv, y_cv = _cv_sample(X, y_enc)
    _lc_folds_r = 3
    automl_result["lc_cv_folds"] = _lc_folds_r
    _lc_reg_map = {"mae": ("neg_mean_absolute_error", "MAE", False),
                   "rmse": ("neg_root_mean_squared_error", "RMSE", False),
                   "r2": ("r2", "R²", True)}
    _lc_scoring_r, _lc_label_r, _lc_pos = _lc_reg_map.get(opt_metric, ("neg_mean_absolute_error", "MAE", False))
    automl_result["optuna_primary_metric"] = opt_metric
    try:
        p.update(83, "Computing learning curve…")
        lc_sizes, lc_train_sc, lc_val_sc = learning_curve(
            clone(pipeline), X_cv, y_cv,
            cv=KFold(n_splits=_lc_folds_r, shuffle=True, random_state=42),
            train_sizes=[0.4, 0.7, 1.0],
            scoring=_lc_scoring_r, n_jobs=1,
        )
        _sign = 1.0 if _lc_pos else -1.0
        automl_result["learning_curve"] = {
            "train_sizes":  [int(s) for s in lc_sizes],
            "train_scores": [round(_sign * float(s.mean()), 4) for s in lc_train_sc],
            "val_scores":   [round(_sign * float(s.mean()), 4) for s in lc_val_sc],
            "metric_label": _lc_label_r, "cv_folds": _lc_folds_r,
        }
    except Exception as _lc_err:
        print(f"Learning curve failed: {_lc_err}", flush=True)
        automl_result["lc_skip_reason"] = "Could not generate — likely OOM or timeout on current resources"

    try:
        p.update(84, "Extracting feature importances…")
        automl_result["feature_importance"] = _extract_feature_importances(pipeline, num_cols, cat_cols)
        rule_exp = _rule_explanation(
            automl_result["winner"], automl_result["cv_results"], "regression",
            "MAE", False, automl_result["feature_importance"], len(X),
        )
        app_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if app_key:
            p.update(86, "Generating AI explanation…")
            llm_exp = _llm_explanation(
                app_key, automl_result["winner"], automl_result["cv_results"],
                "regression", "MAE", False,
                automl_result["feature_importance"], len(X),
            )
            automl_result["explanation"]        = llm_exp or {"why_won": rule_exp, "score_analysis": "", "key_drivers": "", "recommendations": []}
            automl_result["explanation_source"] = "app_key" if llm_exp else "rule"
        else:
            automl_result["explanation"]        = {"why_won": rule_exp, "score_analysis": "", "key_drivers": "", "recommendations": []}
            automl_result["explanation_source"] = "rule"
        automl_result["can_upgrade"] = automl_result["explanation_source"] == "rule"
    except Exception as _exp_err:
        print(f"[reg] explanation/importance failed: {_exp_err}", flush=True)
        automl_result.setdefault("feature_importance", [])
        automl_result.setdefault("explanation", {"why_won": "", "score_analysis": "", "key_drivers": "", "recommendations": []})
        automl_result.setdefault("explanation_source", "rule")


def _automl_reg(p, X, y_enc, selected_models, tune, n_trials, transformers,
                XGBRegressor, LGBMRegressor, CatBoostRegressor,
                opt_metric: str = "auto",
                sampler: str = "tpe",
                secondary_metric: str = "none"):
    cv_split = KFold(n_splits=5, shuffle=True, random_state=42)
    X_cv, y_cv = _cv_sample(X, y_enc)
    cv_results = []
    _pct_steps_r = [12, 26, 40, 48, 55]
    _model_idx_r = 0

    _REG_MAP = {
        "Random Forest":     lambda: RandomForestRegressor(n_estimators=100, random_state=42),
        "XGBoost":           lambda: XGBRegressor(n_estimators=100, random_state=42, verbosity=0),
        "LightGBM":          lambda: LGBMRegressor(n_estimators=100, random_state=42, verbose=-1),
        "CatBoost":          lambda: CatBoostRegressor(iterations=100, random_seed=42, verbose=0),
        "Extra Trees":       lambda: ExtraTreesRegressor(n_estimators=100, random_state=42),
        "Decision Tree":     lambda: DecisionTreeRegressor(random_state=42),
        "KNN":               lambda: KNeighborsRegressor(n_neighbors=5),
        "Ridge":             lambda: RidgeRegressor(alpha=1.0),
        "Lasso":             lambda: Lasso(alpha=1.0, max_iter=5000),
        "ElasticNet":        lambda: ElasticNet(alpha=1.0, max_iter=5000),
        "SVR":               lambda: SVR(kernel="rbf"),
        "Gradient Boosting": lambda: GradientBoostingRegressor(n_estimators=100, random_state=42),
    }

    for name, mk_est in _REG_MAP.items():
        if name not in selected_models:
            continue
        p.update(_pct_steps_r[_model_idx_r % 5], f"Testing {name} (5-fold CV)…")
        _model_idx_r += 1
        try:
            _pl    = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")), ("model", mk_est())])
            _folds = cross_val_score(_pl, X_cv, y_cv, cv=cv_split, scoring="neg_mean_absolute_error")
            cv_results.append({"algorithm": name, "score": round(-float(_folds.mean()), 4), "fold_scores": [round(-float(s), 4) for s in _folds]})
        except Exception as _e:
            print(f"{name} CV failed: {_e}", flush=True)

    if not cv_results:
        raise RuntimeError("All selected models failed CV")

    winner = min(cv_results, key=lambda r: r["score"])["algorithm"]
    automl_result = {
        "winner": winner, "selection_metric": "MAE", "is_imbalanced": False,
        "n_rows": len(X), "n_input_cols": len(X.columns), "cv_results": cv_results,
        "task": "regression", "gpu": _detect_gpu(),
    }
    estimator = _REG_MAP.get(winner, lambda: RandomForestRegressor(n_estimators=100, random_state=42))()

    if tune:
        p.update(58, f"Winner: {winner}. Tuning with Optuna ({n_trials} trials)…")
        try:
            _best_params_r, _best_val_r, _optuna_trials_r, _param_importance_r, _secondary_trials_r = _optuna_tune(
                winner, "regression", X_cv, y_cv, transformers, cv_split, n_trials, False,
                lambda t, s: p.update(58 + int(t / n_trials * 22), f"Optuna trial {t}/{n_trials} — best MAE: {'n/a' if s != s else f'{-s:.4f}'}"),
                opt_metric=opt_metric,
                sampler=sampler,
                secondary_metric=secondary_metric,
            )
            estimator = _build_tuned_estimator(winner, "regression", _best_params_r, False)
            automl_result["optuna_params"]            = _best_params_r
            automl_result["optuna_best_score"]        = round(-_best_val_r, 4)
            automl_result["optuna_n_trials"]          = n_trials
            automl_result["optuna_trials"]            = _optuna_trials_r
            automl_result["optuna_param_importance"]  = _param_importance_r
            automl_result["optuna_sampler"] = sampler
            automl_result["optuna_secondary_metric"] = secondary_metric
            automl_result["optuna_secondary_trials"] = _secondary_trials_r
            p.update(80, f"Tuning done. Training {winner} with best params…")
        except Exception as _oe:
            print(f"Optuna tuning failed, using default params: {_oe}", flush=True)
            p.update(78, f"Tuning failed — using default {winner} params…")
    else:
        p.update(65, f"Winner: {winner}. Training on full dataset…")

    return automl_result, estimator, winner


def _single_reg_estimator(algorithm, XGBRegressor, LGBMRegressor, CatBoostRegressor):
    if algorithm == "XGBoost":
        return XGBRegressor(n_estimators=100, random_state=42, verbosity=0)
    if algorithm == "LightGBM":
        return LGBMRegressor(n_estimators=100, random_state=42, verbose=-1)
    if algorithm == "CatBoost":
        return CatBoostRegressor(iterations=100, random_seed=42, verbose=0)
    if algorithm == "Gradient Boosting":
        return GradientBoostingRegressor(n_estimators=100, random_state=42)
    return RandomForestRegressor(n_estimators=100, random_state=42)
