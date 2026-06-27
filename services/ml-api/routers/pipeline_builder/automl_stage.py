"""Pipeline Builder — AutoML, Optuna tuning, SHAP explanation, and ensemble stages."""
from __future__ import annotations

import base64
import io
import uuid
from typing import List

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sklearn.model_selection import cross_val_score, StratifiedKFold, KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder

from routers.core.shared import MODELS

router = APIRouter()


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _decode_csv(csv_b64: str) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(base64.b64decode(csv_b64)))


def _encode_y(y: pd.Series, task_type: str):
    if task_type == "classification":
        return LabelEncoder().fit_transform(y.astype(str))
    return pd.to_numeric(y, errors="coerce").fillna(0).values


def _scoring_and_cv(task_type: str, n_folds: int):
    if task_type == "classification":
        return "f1_weighted", StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    return "neg_mean_absolute_error", KFold(n_splits=n_folds, shuffle=True, random_state=42)


def _build_preprocessor(X: pd.DataFrame):
    from sklearn.pipeline import Pipeline as _PL
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler, OrdinalEncoder
    from sklearn.compose import ColumnTransformer

    num_cols = X.select_dtypes(include="number").columns.tolist()
    cat_cols = X.select_dtypes(exclude="number").columns.tolist()
    transformers = []
    if num_cols:
        transformers.append(("num", _PL([
            ("imp", SimpleImputer(strategy="median")),
            ("scl", StandardScaler()),
        ]), num_cols))
    if cat_cols:
        transformers.append(("cat", _PL([
            ("imp", SimpleImputer(strategy="most_frequent")),
            ("enc", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
        ]), cat_cols))
    return ColumnTransformer(transformers, remainder="drop")


def _get_estimator(algo: str, task_type: str, params: dict | None = None):
    """Build a fresh estimator. params override defaults when provided."""
    is_clf = task_type == "classification"
    p = params or {}
    n_est = p.get("n_estimators", 100)
    max_d = p.get("max_depth", None)
    lr = p.get("learning_rate", 0.1)

    if algo == "RandomForest":
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
        kw = dict(n_estimators=n_est, max_depth=max_d, random_state=42)
        return RandomForestClassifier(**kw) if is_clf else RandomForestRegressor(**kw)
    if algo == "XGBoost":
        import xgboost as xgb
        kw = dict(n_estimators=n_est, max_depth=max_d or 6, learning_rate=lr,
                  verbosity=0, random_state=42)
        return (xgb.XGBClassifier(**kw, eval_metric="logloss")
                if is_clf else xgb.XGBRegressor(**kw))
    if algo == "LightGBM":
        import lightgbm as lgb
        kw = dict(n_estimators=n_est, max_depth=max_d or -1, learning_rate=lr,
                  verbosity=-1, random_state=42)
        return lgb.LGBMClassifier(**kw) if is_clf else lgb.LGBMRegressor(**kw)
    if algo == "CatBoost":
        import catboost as cb
        kw = dict(iterations=n_est, depth=max_d or 6, learning_rate=lr,
                  verbose=0, random_state=42)
        return cb.CatBoostClassifier(**kw) if is_clf else cb.CatBoostRegressor(**kw)
    raise ValueError(f"Unknown algorithm: {algo}")


# ── Request / Response models ──────────────────────────────────────────────────

class AutoMLConfig(BaseModel):
    models: List[str] = ["RandomForest", "XGBoost", "LightGBM", "CatBoost"]
    n_folds: int = 5


class AutoMLRequest(BaseModel):
    csv_b64: str
    target: str
    task_type: str = "classification"
    config: AutoMLConfig = AutoMLConfig()


class OptunaConfig(BaseModel):
    n_trials: int = 30


class OptunaRequest(BaseModel):
    model_id: str
    csv_b64: str
    target: str
    task_type: str = "classification"
    config: OptunaConfig = OptunaConfig()


class SHAPRequest(BaseModel):
    model_id: str
    csv_b64: str
    target: str


class EnsembleConfig(BaseModel):
    type: str = "voting"
    models: List[str] = ["RandomForest", "XGBoost", "LightGBM"]


class EnsembleRequest(BaseModel):
    csv_b64: str
    target: str
    task_type: str = "classification"
    config: EnsembleConfig = EnsembleConfig()


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/automl")
def run_automl(req: AutoMLRequest):
    try:
        df = _decode_csv(req.csv_b64)
        if req.target not in df.columns:
            raise HTTPException(status_code=400, detail=f"Target column '{req.target}' not found")

        X = df.drop(columns=[req.target])
        y_enc = _encode_y(df[req.target], req.task_type)
        scoring, cv = _scoring_and_cv(req.task_type, req.config.n_folds)

        leaderboard = []
        for algo in req.config.models:
            try:
                pipe = Pipeline([("pre", _build_preprocessor(X)), ("est", _get_estimator(algo, req.task_type))])
                sc = float(cross_val_score(pipe, X, y_enc, cv=cv, scoring=scoring).mean())
                if req.task_type == "regression":
                    sc = -sc
                leaderboard.append({"algo": algo, "score": sc})
            except Exception as algo_err:
                leaderboard.append({"algo": algo, "score": -999.0, "error": str(algo_err)})

        leaderboard.sort(key=lambda x: x["score"], reverse=True)
        winner = leaderboard[0]

        final_pipe = Pipeline([("pre", _build_preprocessor(X)), ("est", _get_estimator(winner["algo"], req.task_type))])
        final_pipe.fit(X, y_enc)

        model_id = f"pb_{uuid.uuid4().hex[:8]}"
        metric = "f1_weighted" if req.task_type == "classification" else "neg_mean_absolute_error"
        MODELS[model_id] = {
            "pipeline": final_pipe, "target": req.target, "task": req.task_type,
            "cols": list(X.columns), "pb": True, "algo": winner["algo"], "score": winner["score"],
        }
        return {
            "leaderboard": leaderboard,
            "winner": {"algo": winner["algo"], "score": winner["score"], "metric": metric},
            "model_id": model_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optuna")
def run_optuna(req: OptunaRequest):
    try:
        stored = MODELS.get(req.model_id)
        if not stored:
            raise HTTPException(status_code=404, detail=f"Model '{req.model_id}' not found")

        algo = stored["algo"]
        df = _decode_csv(req.csv_b64)
        if req.target not in df.columns:
            raise HTTPException(status_code=400, detail=f"Target column '{req.target}' not found")

        X = df.drop(columns=[req.target])
        y_enc = _encode_y(df[req.target], req.task_type)
        scoring, _ = _scoring_and_cv(req.task_type, 5)
        cv_opt = (StratifiedKFold(3, shuffle=True, random_state=42)
                  if req.task_type == "classification"
                  else KFold(3, shuffle=True, random_state=42))

        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        def objective(trial):
            try:
                params = {
                    "n_estimators": trial.suggest_int("n_estimators", 50, 300),
                    "max_depth": trial.suggest_int("max_depth", 3, 10),
                    "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                }
                pipe = Pipeline([("pre", _build_preprocessor(X)),
                                 ("est", _get_estimator(algo, req.task_type, params))])
                val = float(cross_val_score(pipe, X, y_enc, cv=cv_opt, scoring=scoring).mean())
                return -val if req.task_type == "regression" else val
            except Exception:
                return -999.0

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=min(30, req.config.n_trials))
        best_params = study.best_params
        score_after = study.best_value
        if req.task_type == "regression":
            score_after = -score_after

        final_pipe = Pipeline([("pre", _build_preprocessor(X)),
                               ("est", _get_estimator(algo, req.task_type, best_params))])
        final_pipe.fit(X, y_enc)

        new_model_id = f"pb_{uuid.uuid4().hex[:8]}"
        MODELS[new_model_id] = {
            "pipeline": final_pipe, "target": req.target, "task": req.task_type,
            "cols": list(X.columns), "pb": True, "algo": algo, "score": score_after,
        }
        return {
            "score_before": stored["score"],
            "score_after": score_after,
            "improvement": score_after - stored["score"],
            "best_params": best_params,
            "new_model_id": new_model_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/shap")
def run_shap(req: SHAPRequest):
    try:
        stored = MODELS.get(req.model_id)
        if not stored:
            raise HTTPException(status_code=404, detail=f"Model '{req.model_id}' not found")

        df = _decode_csv(req.csv_b64)
        X = df.drop(columns=[req.target], errors="ignore")
        pipeline = stored["pipeline"]
        preprocessor = pipeline[:-1]
        estimator = pipeline[-1]

        try:
            X_transformed = preprocessor.transform(X)
        except Exception as prep_err:
            raise HTTPException(status_code=500, detail=f"Preprocessing failed: {prep_err}")

        try:
            import shap
            explainer = shap.TreeExplainer(estimator)
            shap_values = explainer.shap_values(X_transformed)
        except Exception as shap_err:
            raise HTTPException(status_code=500, detail=f"SHAP explanation failed: {shap_err}")

        if isinstance(shap_values, list):
            vals = np.abs(np.array(shap_values)).mean(axis=0)
        elif shap_values.ndim == 3:
            vals = np.abs(shap_values).mean(axis=0)
        else:
            vals = np.abs(shap_values)

        mean_abs = vals.mean(axis=0) if vals.ndim == 2 else vals

        try:
            feat_names = list(preprocessor.get_feature_names_out())
        except Exception:
            feat_names = [f"f{i}" for i in range(len(mean_abs))]

        pairs = sorted(zip(feat_names, mean_abs.tolist()), key=lambda x: x[1], reverse=True)[:15]
        return {"feature_importance": [{"feature": n, "importance": float(v)} for n, v in pairs]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ensemble")
def run_ensemble(req: EnsembleRequest):
    try:
        df = _decode_csv(req.csv_b64)
        if req.target not in df.columns:
            raise HTTPException(status_code=400, detail=f"Target column '{req.target}' not found")

        X = df.drop(columns=[req.target])
        y_enc = _encode_y(df[req.target], req.task_type)
        scoring, cv = _scoring_and_cv(req.task_type, 5)

        from sklearn.base import clone
        preprocessor = _build_preprocessor(X)
        estimators_list = [(algo, _get_estimator(algo, req.task_type)) for algo in req.config.models]

        individual_scores = {}
        for algo, est in estimators_list:
            try:
                pipe = Pipeline([("pre", clone(preprocessor)), ("est", est)])
                sc = float(cross_val_score(pipe, X, y_enc, cv=cv, scoring=scoring).mean())
                individual_scores[algo] = -sc if req.task_type == "regression" else sc
            except Exception:
                individual_scores[algo] = -999.0

        wrapped = [(algo, Pipeline([("pre", clone(preprocessor)), ("est", clone(est))]))
                   for algo, est in estimators_list]

        if req.task_type == "classification":
            from sklearn.ensemble import VotingClassifier
            try:
                ensemble = VotingClassifier(estimators=wrapped, voting="soft")
                scores = cross_val_score(ensemble, X, y_enc, cv=cv, scoring=scoring)
            except Exception:
                ensemble = VotingClassifier(estimators=wrapped, voting="hard")
                scores = cross_val_score(ensemble, X, y_enc, cv=cv, scoring=scoring)
        else:
            from sklearn.ensemble import VotingRegressor
            ensemble = VotingRegressor(estimators=wrapped)
            scores = cross_val_score(ensemble, X, y_enc, cv=cv, scoring=scoring)

        ensemble_score = float(scores.mean())
        if req.task_type == "regression":
            ensemble_score = -ensemble_score

        return {
            "score": ensemble_score,
            "ensemble_type": req.config.type,
            "individual_scores": individual_scores,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
