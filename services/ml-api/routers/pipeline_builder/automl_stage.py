"""Pipeline Builder — AutoML, Optuna tuning, SHAP explanation, and ensemble stages."""
from __future__ import annotations

import base64
import io
import logging
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
from routers.pipeline_builder._registry import register_pb_model
from routers.pipeline_builder._estimators import (
    _decode_csv, _encode_y, _scoring_and_cv, _build_preprocessor,
    _get_estimator, _maybe_sample,
)

logger = logging.getLogger(__name__)

router = APIRouter()


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
    ensemble_type: str = "voting"
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
        X, y_enc, original_rows = _maybe_sample(X, y_enc, 15_000, req.task_type)
        scoring, cv = _scoring_and_cv(req.task_type, req.config.n_folds)

        leaderboard = []
        for algo in req.config.models:
            try:
                pipe = Pipeline([("prep", _build_preprocessor(X)), ("est", _get_estimator(algo, req.task_type))])
                sc = float(cross_val_score(pipe, X, y_enc, cv=cv, scoring=scoring).mean())
                if req.task_type == "regression":
                    sc = -sc
                leaderboard.append({"algo": algo, "score": sc})
            except Exception as algo_err:
                leaderboard.append({"algo": algo, "score": -999.0, "error": str(algo_err)})

        leaderboard.sort(key=lambda x: x["score"], reverse=True)
        winner = leaderboard[0]

        final_pipe = Pipeline([("prep", _build_preprocessor(X)), ("est", _get_estimator(winner["algo"], req.task_type))])
        final_pipe.fit(X, y_enc)

        model_id = f"pb_{uuid.uuid4().hex[:8]}"
        metric = "f1_weighted" if req.task_type == "classification" else "neg_mean_absolute_error"
        # LabelEncoder sorts, so this is exactly the label order the pipeline
        # was fitted against — _encode_y does not hand the encoder back.
        class_names = (
            sorted(df[req.target].astype(str).dropna().unique().tolist())
            if req.task_type == "classification" else None
        )
        register_pb_model(
            model_id, final_pipe, X, req.target, req.task_type,
            winner["algo"], winner["score"], class_names,
        )
        return {
            "leaderboard": leaderboard,
            "winner": {"algo": winner["algo"], "score": winner["score"], "metric": metric},
            "model_id": model_id,
            "sampled_from": original_rows if original_rows else None,
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
        X, y_enc, _ = _maybe_sample(X, y_enc, 10_000, req.task_type)
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
                pipe = Pipeline([("prep", _build_preprocessor(X)),
                                 ("est", _get_estimator(algo, req.task_type, params))])
                val = float(cross_val_score(pipe, X, y_enc, cv=cv_opt, scoring=scoring).mean())
                return -val if req.task_type == "regression" else val
            except Exception as exc:
                logger.warning("Optuna trial failed, scoring it -999.0: %s", exc)
                return -999.0

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=min(30, req.config.n_trials))
        if study.best_value == -999.0:
            logger.error("Optuna: every trial failed — returned 'best' result is not a real optimization outcome")
        best_params = study.best_params
        # objective returns -val for regression (where val = neg_mae, so -val = +MAE).
        # study.best_value is therefore already a positive MAE for regression.
        score_after = study.best_value

        final_pipe = Pipeline([("prep", _build_preprocessor(X)),
                               ("est", _get_estimator(algo, req.task_type, best_params))])
        final_pipe.fit(X, y_enc)

        new_model_id = f"pb_{uuid.uuid4().hex[:8]}"
        register_pb_model(
            new_model_id, final_pipe, X, req.target, req.task_type,
            algo, score_after, stored.get("classes"),
        )
        # For regression: improvement = how much MAE decreased (positive = better).
        # For classification: improvement = how much F1 increased (positive = better).
        improvement = (stored["score"] - score_after if req.task_type == "regression"
                       else score_after - stored["score"])
        return {
            "score_before": stored["score"],
            "score_after": score_after,
            "improvement": improvement,
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
        except Exception as exc:
            logger.warning("Could not recover real feature names for SHAP output, using f0/f1/...: %s", exc)
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
        from sklearn.model_selection import cross_val_predict, KFold, StratifiedKFold
        from sklearn.metrics import f1_score, mean_absolute_error
        from sklearn.base import clone

        df = _decode_csv(req.csv_b64)
        if req.target not in df.columns:
            raise HTTPException(status_code=400, detail=f"Target column '{req.target}' not found")

        X = df.drop(columns=[req.target])
        y_enc = _encode_y(df[req.target], req.task_type)
        X, y_enc, _ = _maybe_sample(X, y_enc, 15_000, req.task_type)
        _, cv = _scoring_and_cv(req.task_type, 5)
        is_clf = req.task_type == "classification"

        # Preprocess once — manual voting/stacking avoids sklearn VotingClassifier type-check issues with XGB/LGB.
        preprocessor = _build_preprocessor(X)
        X_pre = preprocessor.fit_transform(X)

        good_estimators = []
        individual_scores: dict = {}
        for algo in req.config.models:
            try:
                est = _get_estimator(algo, req.task_type)
                oof = cross_val_predict(est, X_pre, y_enc, cv=cv)
                sc = (float(f1_score(y_enc, oof, average="weighted")) if is_clf
                      else float(mean_absolute_error(y_enc, oof)))
                individual_scores[algo] = sc
                good_estimators.append((algo, _get_estimator(algo, req.task_type)))
            except Exception as exc:
                logger.warning("Ensemble: %s failed individual evaluation, excluded: %s", algo, exc)
                individual_scores[algo] = -999.0

        if not good_estimators:
            raise HTTPException(status_code=500, detail="All models failed during individual evaluation")

        if req.config.ensemble_type == "stacking":
            # Level-0: generate OOF meta-features for each base model
            splits = list(cv.split(X_pre, y_enc))
            meta_X = np.zeros((len(y_enc), len(good_estimators)))
            for i, (_, est) in enumerate(good_estimators):
                for train_idx, val_idx in splits:
                    m = clone(est)
                    m.fit(X_pre[train_idx], y_enc[train_idx])
                    meta_X[val_idx, i] = m.predict(X_pre[val_idx])
            # Level-1: meta-model cross-val score
            if is_clf:
                from sklearn.linear_model import LogisticRegression
                meta_model = LogisticRegression(max_iter=500, random_state=42)
                meta_cv = StratifiedKFold(3, shuffle=True, random_state=42)
            else:
                from sklearn.linear_model import Ridge
                meta_model = Ridge()
                meta_cv = KFold(3, shuffle=True, random_state=42)
            meta_preds = cross_val_predict(meta_model, meta_X, y_enc, cv=meta_cv)
            ensemble_score = (float(f1_score(y_enc, meta_preds, average="weighted")) if is_clf
                              else float(mean_absolute_error(y_enc, meta_preds)))
        else:
            # Voting: average OOF predictions across all good models
            if is_clf:
                try:
                    probas = [cross_val_predict(est, X_pre, y_enc, cv=cv, method="predict_proba")
                              for _, est in good_estimators]
                    ens_preds = np.argmax(np.mean(probas, axis=0), axis=1)
                except Exception as exc:
                    logger.warning("Soft voting failed, falling back to hard voting: %s", exc)
                    hard = np.array([cross_val_predict(est, X_pre, y_enc, cv=cv)
                                     for _, est in good_estimators])
                    ens_preds = np.array([np.bincount(hard[:, i].astype(int)).argmax()
                                          for i in range(hard.shape[1])])
                ensemble_score = float(f1_score(y_enc, ens_preds, average="weighted"))
            else:
                reg_preds = np.array([cross_val_predict(est, X_pre, y_enc, cv=cv)
                                      for _, est in good_estimators])
                ensemble_score = float(mean_absolute_error(y_enc, np.mean(reg_preds, axis=0)))

        return {
            "ensemble_score": ensemble_score,
            "ensemble_type": req.config.ensemble_type,
            "individual_scores": individual_scores,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
