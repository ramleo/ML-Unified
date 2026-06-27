"""Pipeline Builder — preprocessing, feature-engineering, and feature-selection stages."""
from __future__ import annotations

import base64
import io
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routers.core.automl_preprocess_helpers import (
    apply_imputation,
    apply_feature_selection,
)

router = APIRouter()


# ── Request / Response models ──────────────────────────────────────────────────

class PreprocessConfig(BaseModel):
    mv_num: str = "mean"
    mv_cat: str = "most_frequent"
    remove_duplicates: bool = True
    remove_outliers: bool = False
    outlier_method: str = "iqr"
    outlier_thresh: float = 1.5
    drop_cols: List[str] = []
    fix_skewness: bool = False


class PreprocessRequest(BaseModel):
    csv_b64: str
    target: str
    config: PreprocessConfig = PreprocessConfig()


class PreprocessResponse(BaseModel):
    rows_before: int
    rows_after: int
    cols_before: int
    cols_after: int
    missing_filled: int
    duplicates_removed: int
    outliers_removed: int
    processed_csv_b64: str


class FEConfig(BaseModel):
    transforms: Optional[Dict[str, List[str]]] = None
    date_cols: Optional[List[str]] = None
    date_parts: Optional[List[str]] = None
    cyclical: Optional[List[Dict[str, Any]]] = None
    interactions: Optional[List[List[str]]] = None
    poly_cols: Optional[List[str]] = None
    poly_degree: int = 2


class FERequest(BaseModel):
    csv_b64: str
    target: str
    config: FEConfig = FEConfig()


class FEResponse(BaseModel):
    features_before: int
    features_added: int
    new_columns: List[str]
    processed_csv_b64: str


class FSConfig(BaseModel):
    method: str = "variance"
    top_k: int = 10


class FSRequest(BaseModel):
    csv_b64: str
    target: str
    config: FSConfig = FSConfig()


class FSResponse(BaseModel):
    features_before: int
    features_after: int
    dropped_features: List[str]
    kept_features: List[str]
    processed_csv_b64: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _decode_csv(csv_b64: str) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(base64.b64decode(csv_b64)))


def _encode_csv(df: pd.DataFrame) -> str:
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return base64.b64encode(buf.getvalue()).decode()


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/preprocess", response_model=PreprocessResponse)
def preprocess(req: PreprocessRequest):
    try:
        cfg = req.config
        df = _decode_csv(req.csv_b64)
        rows_before = len(df)
        cols_before = len(df.columns)
        missing_before = int(df.isna().sum().sum())

        # Drop requested columns
        if cfg.drop_cols:
            df = df.drop(columns=cfg.drop_cols, errors="ignore")

        # Remove duplicates
        duplicates_removed = 0
        if cfg.remove_duplicates:
            before = len(df)
            df = df.drop_duplicates()
            duplicates_removed = before - len(df)

        # Separate target
        if req.target not in df.columns:
            raise HTTPException(status_code=400, detail=f"Target column '{req.target}' not found")
        y = df[req.target].copy()
        df_feat = df.drop(columns=[req.target])

        num_cols = df_feat.select_dtypes(include="number").columns.tolist()
        cat_cols = df_feat.select_dtypes(exclude="number").columns.tolist()

        # Imputation
        df_feat, y, cat_cols = apply_imputation(df_feat, y, cfg.mv_num, cfg.mv_cat, num_cols, cat_cols)

        # Outlier handling (clip — no rows removed)
        outliers_removed = 0
        if cfg.remove_outliers:
            num_now = df_feat.select_dtypes(include="number").columns.tolist()
            thresh = cfg.outlier_thresh
            if cfg.outlier_method == "iqr":
                for col in num_now:
                    q1 = df_feat[col].quantile(0.25)
                    q3 = df_feat[col].quantile(0.75)
                    iqr = q3 - q1
                    lo = q1 - thresh * iqr
                    hi = q3 + thresh * iqr
                    df_feat[col] = df_feat[col].clip(lo, hi)
            elif cfg.outlier_method == "zscore":
                for col in num_now:
                    mean_v = float(df_feat[col].mean())
                    std_v = float(df_feat[col].std())
                    if std_v > 0:
                        lo = mean_v - thresh * std_v
                        hi = mean_v + thresh * std_v
                        df_feat[col] = df_feat[col].clip(lo, hi)

        # Fix skewness
        if cfg.fix_skewness:
            num_now = df_feat.select_dtypes(include="number").columns.tolist()
            for col in num_now:
                try:
                    if df_feat[col].skew() > 0.75:
                        df_feat[col] = np.log1p(np.maximum(df_feat[col], 0))
                except Exception:
                    pass

        # Recombine
        df_out = df_feat.copy()
        y_aligned = y.reindex(df_feat.index)
        df_out[req.target] = y_aligned.values

        missing_after = int(df_out.isna().sum().sum())
        missing_filled = max(0, missing_before - missing_after)

        return {
            "rows_before": rows_before,
            "rows_after": len(df_out),
            "cols_before": cols_before,
            "cols_after": len(df_out.columns),
            "missing_filled": missing_filled,
            "duplicates_removed": duplicates_removed,
            "outliers_removed": outliers_removed,
            "processed_csv_b64": _encode_csv(df_out),
            "stats": {
                "rows_before": int(rows_before),
                "rows_after": int(len(df_out)),
                "cols_before": int(cols_before),
                "cols_after": int(len(df_out.columns)),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feature-eng", response_model=FEResponse)
def feature_eng(req: FERequest):
    try:
        cfg = req.config
        df = _decode_csv(req.csv_b64)
        cols_before = len(df.columns)
        new_columns: list[str] = []

        for col, t_list in (cfg.transforms or {}).items():
            if col not in df.columns:
                continue
            vals = pd.to_numeric(df[col], errors="coerce")
            if "log1p" in t_list:
                name = f"{col}_log1p"
                df[name] = np.log1p(np.maximum(vals, 0))
                new_columns.append(name)
            if "sqrt" in t_list:
                name = f"{col}_sqrt"
                df[name] = np.sqrt(np.maximum(vals, 0))
                new_columns.append(name)
            if "yeo_johnson" in t_list:
                try:
                    from sklearn.preprocessing import PowerTransformer
                    pt = PowerTransformer(method="yeo-johnson")
                    arr = vals.fillna(float(vals.median())).values.reshape(-1, 1)
                    name = f"{col}_yj"
                    df[name] = pt.fit_transform(arr).ravel()
                    new_columns.append(name)
                except Exception:
                    pass
            if "percentile" in t_list:
                name = f"{col}_pct"
                df[name] = vals.rank(pct=True)
                new_columns.append(name)
            if "outlier_flag" in t_list:
                name = f"{col}_outlier"
                mean_v, std_v = float(vals.mean()), float(vals.std())
                df[name] = ((vals < mean_v - 3 * std_v) | (vals > mean_v + 3 * std_v)).astype(int)
                new_columns.append(name)
            if "missing_flag" in t_list:
                name = f"{col}_missing"
                df[name] = df[col].isna().astype(int)
                new_columns.append(name)
            if "bin_equal" in t_list:
                try:
                    name = f"{col}_bin"
                    df[name] = pd.cut(vals, bins=5, labels=False)
                    new_columns.append(name)
                except Exception:
                    pass
            if "bin_quantile" in t_list:
                try:
                    name = f"{col}_qbin"
                    df[name] = pd.qcut(vals, q=5, labels=False, duplicates="drop")
                    new_columns.append(name)
                except Exception:
                    pass

        date_parts = cfg.date_parts or ["year", "month", "day", "dayofweek"]
        for col in (cfg.date_cols or []):
            if col not in df.columns:
                continue
            try:
                dt = pd.to_datetime(df[col], errors="coerce")
                for part in date_parts:
                    name = f"{col}_{part}"
                    df[name] = getattr(dt.dt, part)
                    new_columns.append(name)
            except Exception:
                pass

        for item in (cfg.cyclical or []):
            col = item.get("col", "")
            period = float(item.get("period", 24))
            if col not in df.columns:
                continue
            try:
                vals = pd.to_numeric(df[col], errors="coerce")
                df[f"{col}_sin"] = np.sin(2 * np.pi * vals / period)
                df[f"{col}_cos"] = np.cos(2 * np.pi * vals / period)
                new_columns += [f"{col}_sin", f"{col}_cos"]
            except Exception:
                pass

        for pair in (cfg.interactions or []):
            if len(pair) != 2:
                continue
            a, b = pair
            if a not in df.columns or b not in df.columns:
                continue
            try:
                name = f"{a}_x_{b}"
                df[name] = pd.to_numeric(df[a], errors="coerce") * pd.to_numeric(df[b], errors="coerce")
                new_columns.append(name)
            except Exception:
                pass

        poly_cols = [c for c in (cfg.poly_cols or []) if c in df.columns]
        if len(poly_cols) >= 2:
            try:
                from sklearn.preprocessing import PolynomialFeatures
                Xp = df[poly_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
                pf = PolynomialFeatures(
                    degree=int(cfg.poly_degree),
                    include_bias=False,
                    interaction_only=True,
                )
                arr = pf.fit_transform(Xp)
                for i, raw_name in enumerate(pf.get_feature_names_out(poly_cols)):
                    if " " in raw_name:
                        safe = raw_name.replace(" ", "_x_")
                        df[safe] = arr[:, i]
                        new_columns.append(safe)
            except Exception:
                pass

        features_added = len(new_columns)
        df_out = df
        return {
            "features_before": cols_before,
            "features_added": features_added,
            "new_columns": new_columns,
            "processed_csv_b64": _encode_csv(df_out),
            "stats": {
                "cols_before": int(cols_before),
                "cols_after": int(len(df_out.columns)),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feature-select", response_model=FSResponse)
def feature_select(req: FSRequest):
    try:
        df = _decode_csv(req.csv_b64)
        if req.target not in df.columns:
            raise HTTPException(status_code=400, detail=f"Target column '{req.target}' not found")

        cols_before = len(df.columns)
        features_before = cols_before - 1
        X = df.drop(columns=[req.target])
        y = df[req.target]
        cols_before_set = set(X.columns)

        X_out = apply_feature_selection(X, y, req.config.method, req.config.top_k)
        kept_features = list(X_out.columns)
        dropped_features = [c for c in cols_before_set if c not in kept_features]

        df_out = X_out.copy()
        df_out[req.target] = y.reindex(X_out.index).values

        return {
            "features_before": features_before,
            "features_after": len(kept_features),
            "dropped_features": dropped_features,
            "kept_features": kept_features,
            "processed_csv_b64": _encode_csv(df_out),
            "stats": {
                "cols_before": int(cols_before),
                "cols_after": int(len(df_out.columns)),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
