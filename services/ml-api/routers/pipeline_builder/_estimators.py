"""Model construction and data prep shared by the Pipeline Builder stages.

Split out of automl_stage.py, which had grown past the length limit. Nothing
here touches FastAPI or the request models: a frame in, an estimator or an
encoded array out, so it is testable without standing a server up.
"""
from __future__ import annotations

import base64
import io
import logging

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, KFold
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger(__name__)

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
            ("scaler", StandardScaler()),
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
        # allow_writing_files=False or CatBoost tries to mkdir catboost_info in
        # the working directory, which is read-only on the Space — every fit
        # failed there while succeeding locally.
        kw = dict(iterations=n_est, depth=max_d or 6, learning_rate=lr,
                  verbose=0, random_state=42, allow_writing_files=False)
        return cb.CatBoostClassifier(**kw) if is_clf else cb.CatBoostRegressor(**kw)
    raise ValueError(f"Unknown algorithm: {algo}")


def _maybe_sample(X: pd.DataFrame, y: np.ndarray, cap: int, task: str):
    """Stratified row sampling to cap compute time on large datasets."""
    if len(X) <= cap:
        return X, y, 0
    from sklearn.utils import resample
    stratify = y if task == "classification" else None
    try:
        Xs, ys = resample(X, y, n_samples=cap, stratify=stratify, random_state=42, replace=False)
    except Exception as exc:
        logger.warning("Stratified sampling failed, falling back to unstratified (class balance may shift): %s", exc)
        Xs, ys = resample(X, y, n_samples=cap, random_state=42, replace=False)
    return Xs, ys, len(X)
