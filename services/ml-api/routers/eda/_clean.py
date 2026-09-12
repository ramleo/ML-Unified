"""Dataset cleaning logic for POST /eda/clean."""
from __future__ import annotations

import base64
import io
import json

import numpy as np
import pandas as pd
from fastapi import HTTPException


def run_clean(file_bytes: bytes, config_str: str, filename: str) -> dict:
    try:
        cfg = json.loads(config_str)
    except Exception as e:
        raise HTTPException(400, f"Invalid config JSON: {e}")

    # Shape, not just syntax. Sending "outliers": "iqr" instead of an object
    # used to reach `.get("enabled")` on a string and raise, which FastAPI
    # turns into an unhandled 500 — and an unhandled 500 is produced OUTSIDE
    # the CORS middleware, so the browser reports a CORS failure and the real
    # cause is invisible from the client. A caller sending the wrong shape
    # deserves to be told which key is wrong.
    if not isinstance(cfg, dict):
        raise HTTPException(400, "Config must be a JSON object.")
    for key in ("imputation", "outliers"):
        if key in cfg and cfg[key] is not None and not isinstance(cfg[key], dict):
            raise HTTPException(
                400, f"Config key '{key}' must be an object, got {type(cfg[key]).__name__}.")
    if "drop_cols" in cfg and cfg["drop_cols"] is not None and not isinstance(cfg["drop_cols"], list):
        raise HTTPException(400, "Config key 'drop_cols' must be a list of column names.")

    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")

    rows_before    = len(df)
    cols_before    = len(df.columns)
    missing_before = int(df.isnull().sum().sum())

    # 1. Dedup
    if cfg.get("dedup", False):
        df = df.drop_duplicates()

    # 2. Drop ID cols
    drop_id_cols = cfg.get("drop_cols") or cfg.get("drop_id_cols") or []
    cols_dropped = [c for c in drop_id_cols if c in df.columns]
    if cols_dropped:
        df = df.drop(columns=cols_dropped)

    # 3. Imputation
    imp_cfg      = cfg.get("imputation") or {}
    imp_cols_cfg = imp_cfg.get("cols", None)
    num_cols     = df.select_dtypes(include="number").columns.tolist()
    cat_cols     = df.select_dtypes(exclude="number").columns.tolist()
    num_method   = imp_cfg.get("numeric_method") or imp_cfg.get("method", "none")
    cat_method   = imp_cfg.get("cat_method", "none")

    def _target_num():
        return [c for c in num_cols if imp_cols_cfg is None or c in imp_cols_cfg]

    def _target_cat():
        return [c for c in cat_cols if imp_cols_cfg is None or c in imp_cols_cfg]

    if num_method == "mean":
        from sklearn.impute import SimpleImputer
        t = _target_num()
        if t:
            df[t] = SimpleImputer(strategy="mean").fit_transform(df[t])
    elif num_method == "median":
        from sklearn.impute import SimpleImputer
        t = _target_num()
        if t:
            df[t] = SimpleImputer(strategy="median").fit_transform(df[t])
    elif num_method == "knn":
        from sklearn.impute import KNNImputer
        t = _target_num()
        if t:
            df[t] = KNNImputer(n_neighbors=imp_cfg.get("knn_k", 5)).fit_transform(df[t])
    elif num_method == "mice":
        from sklearn.experimental import enable_iterative_imputer  # noqa: F401
        from sklearn.impute import IterativeImputer
        t = _target_num()
        if t:
            df[t] = IterativeImputer().fit_transform(df[t])
    elif num_method == "interpolate":
        t = _target_num()
        if t:
            df[t] = df[t].interpolate()
    elif num_method == "ffill":
        t = _target_num()
        if t:
            df[t] = df[t].ffill()
    elif num_method == "bfill":
        t = _target_num()
        if t:
            df[t] = df[t].bfill()
    elif num_method == "constant":
        t   = _target_num()
        val = imp_cfg.get("constant_value", 0)
        try:
            val = float(val)
        except (TypeError, ValueError):
            val = 0
        for c in t:
            df[c] = df[c].fillna(val)
    elif num_method == "miceforest":
        try:
            import miceforest as mf
        except ImportError:
            raise HTTPException(400, "miceforest not installed on this server")
        kernel = mf.ImputationKernel(df, datasets=1, save_all_iterations=False)
        kernel.mice(1)
        df = kernel.complete_data(0)
    elif num_method == "fancyimpute":
        try:
            from fancyimpute import IterativeSVD
        except ImportError:
            raise HTTPException(400, "fancyimpute not installed on this server")
        t = _target_num()
        if t:
            df[t] = IterativeSVD().fit_transform(df[t])

    if cat_method == "mode":
        from sklearn.impute import SimpleImputer
        for col in _target_cat():
            df[[col]] = SimpleImputer(strategy="most_frequent").fit_transform(df[[col]])
    elif cat_method == "constant":
        cat_const = imp_cfg.get("cat_constant_value", "Unknown")
        for col in _target_cat():
            df[col] = df[col].fillna(cat_const)
    elif cat_method == "ffill":
        t = _target_cat()
        if t:
            df[t] = df[t].ffill()
    elif cat_method == "bfill":
        t = _target_cat()
        if t:
            df[t] = df[t].bfill()

    # 4. Outlier removal
    outliers_cfg     = cfg.get("outliers") or {}
    outliers_removed = 0
    rows_before_out  = len(df)
    if outliers_cfg.get("enabled", False):
        out_method   = outliers_cfg.get("method", "iqr")
        threshold    = outliers_cfg.get("threshold", 1.5)
        num_cols_now = df.select_dtypes(include="number").columns.tolist()
        out_cols_cfg = outliers_cfg.get("cols", None)
        if out_cols_cfg is not None:
            num_cols_now = [c for c in num_cols_now if c in out_cols_cfg]
        if out_method == "iqr":
            mask = pd.Series([True] * len(df), index=df.index)
            for col in num_cols_now:
                s = df[col].dropna()
                if len(s) == 0:
                    continue
                q25 = float(s.quantile(0.25))
                q75 = float(s.quantile(0.75))
                iqr = q75 - q25
                mask = mask & (df[col].between(q25 - threshold * iqr, q75 + threshold * iqr) | df[col].isnull())
            df = df[mask]
        elif out_method == "zscore":
            mask = pd.Series([True] * len(df), index=df.index)
            for col in num_cols_now:
                mean_val = df[col].mean()
                std_val  = df[col].std()
                if std_val == 0 or pd.isna(std_val):
                    continue
                z    = np.abs((df[col] - mean_val) / std_val)
                mask = mask & ((z < threshold) | df[col].isnull())
            df = df[mask]
        elif out_method == "winsorize":
            limits = threshold / 100.0
            for col in num_cols_now:
                df[col] = df[col].clip(df[col].quantile(limits), df[col].quantile(1.0 - limits))
        outliers_removed = rows_before_out - len(df)

    # 5. Power transform
    pt_cfg     = cfg.get("power_transform", False)
    pt_enabled = pt_cfg if isinstance(pt_cfg, bool) else pt_cfg.get("enabled", False)
    pt_cols_cfg = None if isinstance(pt_cfg, bool) else pt_cfg.get("cols", None)
    if pt_enabled:
        from sklearn.preprocessing import PowerTransformer
        num_cols_final = df.select_dtypes(include="number").columns.tolist()
        if pt_cols_cfg is not None:
            num_cols_final = [c for c in num_cols_final if c in pt_cols_cfg]
        if num_cols_final:
            df[num_cols_final] = PowerTransformer(method="yeo-johnson").fit_transform(df[num_cols_final])

    rows_after    = len(df)
    missing_after = int(df.isnull().sum().sum())
    summary = {
        "rows_before":      rows_before,
        "rows_after":       rows_after,
        "rows_removed":     rows_before - rows_after,
        "cols_before":      cols_before,
        "cols_after":       len(df.columns),
        "cols_dropped":     cols_dropped,
        "missing_before":   missing_before,
        "missing_after":    missing_after,
        "outliers_removed": outliers_removed,
    }
    csv_b64 = base64.b64encode(df.to_csv(index=False).encode("utf-8")).decode("utf-8")
    return {"summary": summary, "csv": csv_b64, "filename": f"cleaned_{filename}"}
