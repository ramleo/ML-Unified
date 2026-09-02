"""Pure AutoML helper functions (no FastAPI, no shared imports)."""
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression, Ridge as RidgeRegressor, Lasso, ElasticNet
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.svm import SVC, SVR
from sklearn.naive_bayes import GaussianNB
from sklearn.ensemble import (
    RandomForestClassifier, GradientBoostingClassifier,
    RandomForestRegressor, GradientBoostingRegressor,
    ExtraTreesClassifier, ExtraTreesRegressor,
)
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline

# Re-export so callers only need to import from automl_helpers
from routers.core.fe_transformer import FeatureEngineeringTransformer  # noqa: F401

_AUTOML_MAX_CV_ROWS = 5000


def _cv_sample(X: pd.DataFrame, y, max_rows: int = _AUTOML_MAX_CV_ROWS):
    """Subsample for cross-validation on large datasets."""
    if len(X) <= max_rows:
        return X, y
    import numpy as _np  # noqa: PLC0415
    idx = _np.random.RandomState(42).choice(len(X), max_rows, replace=False)
    if hasattr(y, "iloc"):
        return X.iloc[idx].reset_index(drop=True), y.iloc[idx].reset_index(drop=True)
    return X.iloc[idx].reset_index(drop=True), y[idx]


def _extract_feature_importances(pipeline, num_cols: list, cat_cols: list) -> list:
    model = pipeline.named_steps.get("model")
    if model is None or not hasattr(model, "feature_importances_"):
        return []
    importances = model.feature_importances_
    prep = pipeline.named_steps["prep"]

    all_feats = list(num_cols)
    if cat_cols:
        try:
            ohe = prep.named_transformers_["cat"].named_steps["enc"]
            for i, col in enumerate(cat_cols):
                n_cats = len(ohe.categories_[i])
                all_feats.extend([col] * n_cats)
        except (KeyError, AttributeError):
            all_feats.extend(cat_cols)

    imp_map: dict = {}
    for i, feat in enumerate(all_feats):
        if i >= len(importances):
            break
        imp_map[feat] = imp_map.get(feat, 0.0) + float(importances[i])

    total = sum(imp_map.values()) or 1.0
    return [
        {"feature": k, "importance": round(v / total * 100, 1)}
        for k, v in sorted(imp_map.items(), key=lambda x: -x[1])
    ][:10]


def _optuna_tune(
    algorithm: str, task: str, X_cv, y_cv, transformers: list,
    cv_split, n_trials: int, is_imbal: bool, on_trial,
    opt_metric: str = "auto",
    sampler: str = "tpe",
    secondary_metric: str = "none",
) -> tuple[dict, float, list, dict, list]:
    import optuna  # noqa: PLC0415
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    from xgboost import XGBClassifier, XGBRegressor          # noqa: PLC0415
    from lightgbm import LGBMClassifier, LGBMRegressor        # noqa: PLC0415
    from catboost import CatBoostClassifier, CatBoostRegressor  # noqa: PLC0415
    if task == "regression":
        if opt_metric == "rmse":
            scoring = "neg_root_mean_squared_error"
        elif opt_metric == "r2":
            scoring = "r2"
        else:  # "auto" or "mae"
            scoring = "neg_mean_absolute_error"
    else:  # classification
        if opt_metric == "accuracy":
            scoring = "accuracy"
        elif opt_metric == "f1_weighted":
            scoring = "f1_weighted"
        elif opt_metric == "f1_macro":
            scoring = "f1_macro"
        elif opt_metric == "roc_auc":
            import numpy as _np  # noqa: PLC0415
            scoring = "roc_auc" if len(_np.unique(y_cv)) == 2 else "roc_auc_ovr"
        else:  # "auto"
            scoring = "f1_macro" if is_imbal else "f1_weighted"

    _sec_scoring_map = {}
    if task == "regression":
        _sec_scoring_map = {"mae": "neg_mean_absolute_error", "rmse": "neg_root_mean_squared_error", "r2": "r2"}
    else:
        _sec_scoring_map = {"accuracy": "accuracy", "f1_weighted": "f1_weighted", "f1_macro": "f1_macro"}
    _secondary_scoring = _sec_scoring_map.get(secondary_metric) if secondary_metric != "none" else None

    _first_error: list = []  # capture first trial error for user-facing message

    # For roc_auc binary: if minority class has fewer samples than n_splits,
    # StratifiedKFold can't guarantee both classes in every test fold → NaN/error.
    # Reduce folds automatically to max(2, minority_count).
    _effective_cv = cv_split
    if scoring == "roc_auc" and task == "classification":
        import numpy as _npcv  # noqa: PLC0415
        _uniq, _cnts = _npcv.unique(y_cv, return_counts=True)
        _min_cls = int(_cnts.min())
        _n_sp = cv_split.n_splits if hasattr(cv_split, "n_splits") else 5
        if _min_cls < _n_sp:
            from sklearn.model_selection import StratifiedKFold as _SKFAdj  # noqa: PLC0415
            _safe_splits = max(2, _min_cls)
            _effective_cv = _SKFAdj(n_splits=_safe_splits, shuffle=True, random_state=42)
            print(f"[Optuna] roc_auc: minority class has {_min_cls} samples — reduced to {_safe_splits}-fold CV", flush=True)

    def objective(trial):
        cw = "balanced" if is_imbal else None
        if algorithm == "Random Forest":
            params: dict = {
                "n_estimators":      trial.suggest_int("n_estimators", 50, 300),
                "max_depth":         trial.suggest_categorical("max_depth", [None, 5, 10, 15, 20]),
                "min_samples_split": trial.suggest_int("min_samples_split", 2, 10),
                "min_samples_leaf":  trial.suggest_int("min_samples_leaf", 1, 4),
                "max_features":      trial.suggest_categorical("max_features", ["sqrt", "log2"]),
            }
            est = (RandomForestClassifier(random_state=42, class_weight=cw, **params)
                   if task == "classification"
                   else RandomForestRegressor(random_state=42, **params))
        elif algorithm == "XGBoost":
            params = {
                "n_estimators":      trial.suggest_int("n_estimators", 50, 500),
                "max_depth":         trial.suggest_int("max_depth", 3, 12),
                "learning_rate":     trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
                "subsample":         trial.suggest_float("subsample", 0.5, 1.0),
                "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "min_child_weight":  trial.suggest_int("min_child_weight", 1, 10),
                "gamma":             trial.suggest_float("gamma", 0.0, 5.0),
                "reg_alpha":         trial.suggest_float("reg_alpha", 0.0, 5.0),
                "reg_lambda":        trial.suggest_float("reg_lambda", 0.1, 5.0),
            }
            est = (XGBClassifier(random_state=42, eval_metric="logloss", verbosity=0, **params)
                   if task == "classification"
                   else XGBRegressor(random_state=42, verbosity=0, **params))
        elif algorithm == "LightGBM":
            params = {
                "n_estimators":      trial.suggest_int("n_estimators", 50, 500),
                "num_leaves":        trial.suggest_int("num_leaves", 20, 200),
                "learning_rate":     trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
                "subsample":         trial.suggest_float("subsample", 0.5, 1.0),
                "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
                "reg_alpha":         trial.suggest_float("reg_alpha", 0.0, 5.0),
                "reg_lambda":        trial.suggest_float("reg_lambda", 0.0, 5.0),
            }
            est = (LGBMClassifier(random_state=42, verbose=-1, class_weight=cw, **params)
                   if task == "classification"
                   else LGBMRegressor(random_state=42, verbose=-1, **params))
        else:  # CatBoost
            params = {
                "iterations":    trial.suggest_int("iterations", 50, 400),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "depth":         trial.suggest_int("depth", 4, 10),
                "l2_leaf_reg":   trial.suggest_float("l2_leaf_reg", 1.0, 10.0),
            }
            est = (CatBoostClassifier(random_seed=42, verbose=0, allow_writing_files=False, **params)
                   if task == "classification"
                   else CatBoostRegressor(random_seed=42, verbose=0, allow_writing_files=False, **params))

        pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")), ("model", est)])
        try:
            if scoring in ("roc_auc", "roc_auc_ovr"):
                # sklearn 1.4 roc_auc scorer uses is_classifier() type detection which
                # fails for some estimators (CatBoost, XGBoost). Bypass it by calling
                # cross_val_predict → predict_proba directly, then computing AUC manually.
                from sklearn.model_selection import cross_val_predict as _cvp  # noqa: PLC0415
                from sklearn.metrics import roc_auc_score as _roc_fn  # noqa: PLC0415
                import numpy as _np_roc  # noqa: PLC0415
                _probas = _cvp(pl, X_cv, y_cv, cv=_effective_cv, method="predict_proba")
                _n_cls = _probas.shape[1]
                if _n_cls == 2:
                    score = float(_roc_fn(y_cv, _probas[:, 1]))
                else:
                    score = float(_roc_fn(y_cv, _probas, multi_class="ovr", average="macro"))
            else:
                score = float(cross_val_score(pl, X_cv, y_cv, cv=_effective_cv, scoring=scoring, error_score="raise").mean())
        except Exception as _cv_err:
            _msg = f"{type(_cv_err).__name__}: {_cv_err}"
            if not _first_error:
                _first_error.append(_msg)
            print(f"[Optuna] trial {trial.number + 1} CV error: {_msg}", flush=True)
            raise optuna.TrialPruned()
        if score != score:  # NaN
            _msg = f"scoring='{scoring}' returned NaN — check class distribution or feature values"
            if not _first_error:
                _first_error.append(_msg)
            print(f"[Optuna] trial {trial.number + 1} NaN score", flush=True)
            raise optuna.TrialPruned()
        on_trial(trial.number + 1, score)
        if _secondary_scoring:
            try:
                from sklearn.model_selection import KFold as _KF2, StratifiedKFold as _SKF2  # noqa: PLC0415
                _sec_cv = _SKF2(n_splits=2, shuffle=True, random_state=42) if task == "classification" else _KF2(n_splits=2, shuffle=True, random_state=42)
                _sec = float(cross_val_score(pl, X_cv, y_cv, cv=_sec_cv, scoring=_secondary_scoring).mean())
                trial.set_user_attr("secondary_score", _sec)
            except Exception:
                pass
        return score

    if sampler == "qmc":
        _sampler = optuna.samplers.QMCSampler(qmc_type="sobol", seed=42)
    else:
        _sampler = optuna.samplers.TPESampler(seed=42, multivariate=True, n_startup_trials=10)

    study = optuna.create_study(
        direction="maximize",
        sampler=_sampler,
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=0),
    )
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    import math as _math  # noqa: PLC0415
    trial_history = [
        {"trial": t.number + 1, "value": round(float(t.value), 4)}
        for t in study.trials
        if t.value is not None and not _math.isnan(t.value)
    ]

    try:
        raw_imp = optuna.importance.get_param_importances(study)
        param_importance = {k: round(float(v), 4) for k, v in raw_imp.items()}
    except Exception:
        param_importance = {}

    secondary_trials = []
    if _secondary_scoring:
        secondary_trials = [
            {"trial": t.number + 1, "value": round(float(t.user_attrs["secondary_score"]), 4)}
            for t in study.trials
            if "secondary_score" in t.user_attrs and not _math.isnan(t.user_attrs["secondary_score"])
        ]

    if not trial_history:
        err_detail = _first_error[0] if _first_error else "unknown — check server logs"
        print(f"All Optuna trials failed for metric '{scoring}': {err_detail}", flush=True)
        raise RuntimeError(
            f"All {n_trials} Optuna trials failed for metric '{opt_metric}'. "
            f"Cause: {err_detail}. "
            f"Try switching to f1_weighted or accuracy."
        )
    return study.best_params, study.best_value, trial_history, param_importance, secondary_trials


def _build_tuned_estimator(algorithm: str, task: str, best_params: dict, is_imbal: bool):
    from xgboost import XGBClassifier, XGBRegressor          # noqa: PLC0415
    from lightgbm import LGBMClassifier, LGBMRegressor        # noqa: PLC0415
    from catboost import CatBoostClassifier, CatBoostRegressor  # noqa: PLC0415
    cw = "balanced" if is_imbal else None
    if algorithm == "Random Forest":
        return (RandomForestClassifier(random_state=42, class_weight=cw, **best_params)
                if task == "classification"
                else RandomForestRegressor(random_state=42, **best_params))
    if algorithm == "XGBoost":
        return (XGBClassifier(random_state=42, eval_metric="logloss", verbosity=0, **best_params)
                if task == "classification"
                else XGBRegressor(random_state=42, verbosity=0, **best_params))
    if algorithm == "LightGBM":
        return (LGBMClassifier(random_state=42, verbose=-1, class_weight=cw, **best_params)
                if task == "classification"
                else LGBMRegressor(random_state=42, verbose=-1, **best_params))
    return (CatBoostClassifier(random_seed=42, verbose=0, allow_writing_files=False, **best_params)
            if task == "classification"
            else CatBoostRegressor(random_seed=42, verbose=0, allow_writing_files=False, **best_params))


