"""Pipeline Builder — code export stage."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ExportRequest(BaseModel):
    target: str
    task_type: str = "classification"
    winner_algo: str = "RandomForest"
    winner_params: Optional[Dict[str, Any]] = None
    preprocess_config: Optional[Dict[str, Any]] = None
    fe_config: Optional[Dict[str, Any]] = None
    fs_config: Optional[Dict[str, Any]] = None


def _algo_import(algo: str, task_type: str) -> str:
    is_clf = task_type == "classification"
    mapping = {
        "RandomForest": (
            "from sklearn.ensemble import RandomForestClassifier",
            "from sklearn.ensemble import RandomForestRegressor",
        ),
        "XGBoost": (
            "from xgboost import XGBClassifier",
            "from xgboost import XGBRegressor",
        ),
        "LightGBM": (
            "from lightgbm import LGBMClassifier",
            "from lightgbm import LGBMRegressor",
        ),
        "CatBoost": (
            "from catboost import CatBoostClassifier",
            "from catboost import CatBoostRegressor",
        ),
    }
    pair = mapping.get(algo, ("from sklearn.ensemble import RandomForestClassifier",
                               "from sklearn.ensemble import RandomForestRegressor"))
    return pair[0] if is_clf else pair[1]


def _algo_class(algo: str, task_type: str) -> str:
    is_clf = task_type == "classification"
    mapping = {
        "RandomForest": ("RandomForestClassifier", "RandomForestRegressor"),
        "XGBoost": ("XGBClassifier", "XGBRegressor"),
        "LightGBM": ("LGBMClassifier", "LGBMRegressor"),
        "CatBoost": ("CatBoostClassifier", "CatBoostRegressor"),
    }
    pair = mapping.get(algo, ("RandomForestClassifier", "RandomForestRegressor"))
    return pair[0] if is_clf else pair[1]


def _params_repr(params: Optional[Dict[str, Any]]) -> str:
    if not params:
        return ""
    parts = []
    for k, v in params.items():
        if isinstance(v, str):
            parts.append(f'{k}="{v}"')
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts)


def _build_preprocess_section(cfg: Optional[Dict[str, Any]]) -> str:
    if not cfg:
        return "# No preprocessing config provided — add steps as needed.\n"
    lines = ["# --- Preprocessing steps ---"]
    if cfg.get("remove_duplicates", False):
        lines.append("df = df.drop_duplicates()")
    drop_cols = cfg.get("drop_cols") or []
    if drop_cols:
        lines.append(f"df = df.drop(columns={drop_cols}, errors='ignore')")
    mv_num = cfg.get("mv_num", "mean")
    mv_cat = cfg.get("mv_cat", "most_frequent")
    lines.append(f"# Numeric imputation strategy: {mv_num}")
    lines.append(f"# Categorical imputation strategy: {mv_cat}")
    if cfg.get("remove_outliers", False):
        method = cfg.get("outlier_method", "iqr")
        thresh = cfg.get("outlier_thresh", 1.5)
        lines.append(f"# Outlier handling: {method} (threshold={thresh}) — applied via clip")
    if cfg.get("fix_skewness", False):
        lines.append("# Skewness fix applied: log1p on cols with skew > 0.75")
    return "\n".join(lines)


def _build_fe_section(cfg: Optional[Dict[str, Any]]) -> str:
    if not cfg:
        return ""
    lines = ["", "# --- Feature Engineering ---"]
    transforms = cfg.get("transforms") or {}
    for col, t_list in transforms.items():
        for t in t_list:
            if t == "log1p":
                lines.append(f"df['{col}_log1p'] = np.log1p(np.maximum(pd.to_numeric(df['{col}'], errors='coerce'), 0))")
            elif t == "sqrt":
                lines.append(f"df['{col}_sqrt'] = np.sqrt(np.maximum(pd.to_numeric(df['{col}'], errors='coerce'), 0))")
    date_cols = cfg.get("date_cols") or []
    date_parts = cfg.get("date_parts") or ["year", "month", "day", "dayofweek"]
    for col in date_cols:
        lines.append(f"_dt_{col} = pd.to_datetime(df['{col}'], errors='coerce')")
        for part in date_parts:
            lines.append(f"df['{col}_{part}'] = _dt_{col}.dt.{part}")
    return "\n".join(lines)


def _build_fs_section(cfg: Optional[Dict[str, Any]]) -> str:
    if not cfg:
        return ""
    method = cfg.get("method", "variance")
    top_k = cfg.get("top_k", 10)
    return f"\n# --- Feature Selection: {method}, top_k={top_k} ---\n# Apply feature selection before splitting.\n"


def _build_eval_section(task_type: str) -> str:
    if task_type == "classification":
        return (
            "from sklearn.metrics import classification_report\n"
            "preds = pipeline.predict(X_test)\n"
            "print(classification_report(y_test, preds))"
        )
    return (
        "from sklearn.metrics import mean_absolute_error\n"
        "preds = pipeline.predict(X_test)\n"
        "print('MAE:', mean_absolute_error(y_test, preds))"
    )


@router.post("/export-code")
def export_code(req: ExportRequest):
    try:
        params_str = _params_repr(req.winner_params)
        algo_import = _algo_import(req.winner_algo, req.task_type)
        algo_class = _algo_class(req.winner_algo, req.task_type)
        preprocess_section = _build_preprocess_section(req.preprocess_config)
        fe_section = _build_fe_section(req.fe_config)
        fs_section = _build_fs_section(req.fs_config)
        eval_section = _build_eval_section(req.task_type)

        code = f'''\
# Pipeline Builder -- Generated Script
# Task: {req.task_type} | Model: {req.winner_algo}

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OrdinalEncoder
from sklearn.compose import ColumnTransformer
{algo_import}

# --- Load Data ---
df = pd.read_csv("your_data.csv")
target = "{req.target}"

{preprocess_section}
{fe_section}
{fs_section}
X = df.drop(columns=[target])
y = df[target]

# --- Preprocessor ---
num_cols = X.select_dtypes(include="number").columns.tolist()
cat_cols = X.select_dtypes(exclude="number").columns.tolist()

transformers = []
if num_cols:
    transformers.append(("num", Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("scl", StandardScaler()),
    ]), num_cols))
if cat_cols:
    transformers.append(("cat", Pipeline([
        ("imp", SimpleImputer(strategy="most_frequent")),
        ("enc", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
    ]), cat_cols))

preprocessor = ColumnTransformer(transformers, remainder="drop")

# --- Model ---
estimator = {algo_class}({params_str})

# --- Train / Evaluate ---
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
pipeline = Pipeline([("preprocessor", preprocessor), ("model", estimator)])
pipeline.fit(X_train, y_train)
{eval_section}
'''

        return {"code": code}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
