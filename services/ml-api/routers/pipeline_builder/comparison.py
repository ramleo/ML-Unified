"""Pipeline Builder — side-by-side pipeline comparison."""
from __future__ import annotations

import base64
import io
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sklearn.model_selection import cross_val_score, StratifiedKFold, KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder

from routers.core.automl_preprocess_helpers import apply_imputation, apply_feature_selection

router = APIRouter()


# ── Request model ──────────────────────────────────────────────────────────────

class PipelineSpec(BaseModel):
    preprocess: Optional[Dict[str, Any]] = None
    fe: Optional[Dict[str, Any]] = None
    fs: Optional[Dict[str, Any]] = None
    automl: Optional[Dict[str, Any]] = None


class CompareRequest(BaseModel):
    csv_b64: str
    target: str
    task_type: str = "classification"
    pipeline_a: PipelineSpec = PipelineSpec()
    pipeline_b: PipelineSpec = PipelineSpec()


# ── Internal helpers ───────────────────────────────────────────────────────────

def _decode_csv(csv_b64: str) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(base64.b64decode(csv_b64)))


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


def _get_estimator(algo: str, task_type: str):
    is_clf = task_type == "classification"
    if algo == "RandomForest":
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
        return RandomForestClassifier(n_estimators=100, random_state=42) if is_clf else RandomForestRegressor(n_estimators=100, random_state=42)
    elif algo == "XGBoost":
        import xgboost as xgb
        return xgb.XGBClassifier(n_estimators=100, verbosity=0, random_state=42, eval_metric="logloss") if is_clf else xgb.XGBRegressor(n_estimators=100, verbosity=0, random_state=42)
    elif algo == "LightGBM":
        import lightgbm as lgb
        return lgb.LGBMClassifier(n_estimators=100, verbosity=-1, random_state=42) if is_clf else lgb.LGBMRegressor(n_estimators=100, verbosity=-1, random_state=42)
    elif algo == "CatBoost":
        import catboost as cb
        return cb.CatBoostClassifier(iterations=100, verbose=0, random_state=42) if is_clf else cb.CatBoostRegressor(iterations=100, verbose=0, random_state=42)
    else:
        raise ValueError(f"Unknown algorithm: {algo}")


def _apply_preprocess(df: pd.DataFrame, target: str, cfg: Optional[Dict[str, Any]]) -> pd.DataFrame:
    if not cfg:
        return df
    if cfg.get("drop_cols"):
        df = df.drop(columns=cfg["drop_cols"], errors="ignore")
    if cfg.get("remove_duplicates", False):
        df = df.drop_duplicates()
    if target not in df.columns:
        return df
    y = df[target].copy()
    df_feat = df.drop(columns=[target])
    num_cols = df_feat.select_dtypes(include="number").columns.tolist()
    cat_cols = df_feat.select_dtypes(exclude="number").columns.tolist()
    df_feat, y, cat_cols = apply_imputation(df_feat, y, cfg.get("mv_num", "mean"), cfg.get("mv_cat", "most_frequent"), num_cols, cat_cols)
    if cfg.get("remove_outliers", False):
        thresh = cfg.get("outlier_thresh", 1.5)
        method = cfg.get("outlier_method", "iqr")
        for col in df_feat.select_dtypes(include="number").columns:
            if method == "iqr":
                q1, q3 = df_feat[col].quantile(0.25), df_feat[col].quantile(0.75)
                iqr = q3 - q1
                df_feat[col] = df_feat[col].clip(q1 - thresh * iqr, q3 + thresh * iqr)
            elif method == "zscore":
                m, s = float(df_feat[col].mean()), float(df_feat[col].std())
                if s > 0:
                    df_feat[col] = df_feat[col].clip(m - thresh * s, m + thresh * s)
    if cfg.get("fix_skewness", False):
        for col in df_feat.select_dtypes(include="number").columns:
            try:
                if df_feat[col].skew() > 0.75:
                    df_feat[col] = np.log1p(np.maximum(df_feat[col], 0))
            except Exception:
                pass
    df_out = df_feat.copy()
    df_out[target] = y.reindex(df_feat.index).values
    return df_out


def _apply_fe(df: pd.DataFrame, cfg: Optional[Dict[str, Any]]) -> pd.DataFrame:
    if not cfg:
        return df
    for col, t_list in (cfg.get("transforms") or {}).items():
        if col not in df.columns:
            continue
        vals = pd.to_numeric(df[col], errors="coerce")
        if "log1p" in t_list:
            df[f"{col}_log1p"] = np.log1p(np.maximum(vals, 0))
        if "sqrt" in t_list:
            df[f"{col}_sqrt"] = np.sqrt(np.maximum(vals, 0))
    date_parts = cfg.get("date_parts") or ["year", "month", "day", "dayofweek"]
    for col in (cfg.get("date_cols") or []):
        if col not in df.columns:
            continue
        try:
            dt = pd.to_datetime(df[col], errors="coerce")
            for part in date_parts:
                df[f"{col}_{part}"] = getattr(dt.dt, part)
        except Exception:
            pass
    return df


def _apply_fs(df: pd.DataFrame, target: str, cfg: Optional[Dict[str, Any]]) -> pd.DataFrame:
    if not cfg or target not in df.columns:
        return df
    X = df.drop(columns=[target])
    y = df[target]
    X_out = apply_feature_selection(X, y, cfg.get("method", "variance"), cfg.get("top_k", 10))
    df_out = X_out.copy()
    df_out[target] = y.reindex(X_out.index).values
    return df_out


def _run_automl(df: pd.DataFrame, target: str, task_type: str, cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    models = (cfg or {}).get("models", ["RandomForest", "XGBoost", "LightGBM", "CatBoost"])
    n_folds = (cfg or {}).get("n_folds", 3)
    X = df.drop(columns=[target])
    y = df[target]

    if task_type == "classification":
        y_enc = LabelEncoder().fit_transform(y.astype(str))
        scoring = "f1_weighted"
        cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    else:
        y_enc = pd.to_numeric(y, errors="coerce").fillna(0).values
        scoring = "neg_mean_absolute_error"
        cv = KFold(n_splits=n_folds, shuffle=True, random_state=42)

    leaderboard = []
    for algo in models:
        try:
            est = _get_estimator(algo, task_type)
            pipe = Pipeline([("prep", _build_preprocessor(X)), ("est", est)])
            scores = cross_val_score(pipe, X, y_enc, cv=cv, scoring=scoring)
            sc = float(scores.mean())
            if task_type == "regression":
                sc = -sc
            leaderboard.append({"algo": algo, "score": sc})
        except Exception as exc:
            logger.warning("Comparison: %s failed cross-validation, excluded from leaderboard: %s", algo, exc)
            leaderboard.append({"algo": algo, "score": -999.0})

    leaderboard.sort(key=lambda x: x["score"], reverse=True)
    winner = leaderboard[0]
    if winner["score"] == -999.0:
        logger.error("Comparison: every model failed — returned 'winner' is not a real comparison outcome")
    return {"score": winner["score"], "winner": winner["algo"]}


def _run_pipeline(csv_b64: str, target: str, task_type: str, spec: PipelineSpec) -> Dict[str, Any]:
    t0 = time.time()
    df = _decode_csv(csv_b64)
    df = _apply_preprocess(df, target, spec.preprocess)
    df = _apply_fe(df, spec.fe)
    df = _apply_fs(df, target, spec.fs)
    result = _run_automl(df, target, task_type, spec.automl)
    time_ms = int((time.time() - t0) * 1000)
    return {**result, "time_ms": time_ms}


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post("/compare")
def compare(req: CompareRequest):
    try:
        result_a = _run_pipeline(req.csv_b64, req.target, req.task_type, req.pipeline_a)
        result_b = _run_pipeline(req.csv_b64, req.target, req.task_type, req.pipeline_b)

        winner = "a" if result_a["score"] >= result_b["score"] else "b"
        difference = abs(result_a["score"] - result_b["score"])

        return {
            "pipeline_a": result_a,
            "pipeline_b": result_b,
            "winner": winner,
            "difference": round(difference, 6),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
