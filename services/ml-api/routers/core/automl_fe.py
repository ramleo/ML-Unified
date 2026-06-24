"""/feature-engineer endpoint — standalone router."""
import io

import pandas as pd
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.post("/feature-engineer")
async def feature_engineer(request: Request):
    """Apply feature engineering transforms to a CSV and return the result."""
    import base64 as _b64
    import numpy as _np

    body = await request.json()
    csv_b64 = body.get("csv_b64", "")
    config  = body.get("config", {})

    if not csv_b64:
        raise HTTPException(400, "csv_b64 is required")

    try:
        df = pd.read_csv(io.BytesIO(_b64.b64decode(csv_b64)))
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")

    cols_before = len(df.columns)
    new_columns: list[str] = []

    for col, t_list in (config.get("transforms") or {}).items():
        if col not in df.columns:
            continue
        vals = pd.to_numeric(df[col], errors="coerce")
        if "log1p" in t_list:
            name = f"{col}_log1p"; df[name] = _np.log1p(_np.maximum(vals, 0)); new_columns.append(name)
        if "sqrt" in t_list:
            name = f"{col}_sqrt"; df[name] = _np.sqrt(_np.maximum(vals, 0)); new_columns.append(name)
        if "yeo_johnson" in t_list:
            try:
                from sklearn.preprocessing import PowerTransformer
                pt = PowerTransformer(method="yeo-johnson")
                arr = vals.fillna(float(vals.median())).values.reshape(-1, 1)
                name = f"{col}_yj"; df[name] = pt.fit_transform(arr).ravel(); new_columns.append(name)
            except Exception:
                pass
        if "percentile" in t_list:
            name = f"{col}_pct"; df[name] = vals.rank(pct=True); new_columns.append(name)
        if "outlier_flag" in t_list:
            name = f"{col}_outlier"
            mean_v, std_v = float(vals.mean()), float(vals.std())
            df[name] = ((vals < mean_v - 3 * std_v) | (vals > mean_v + 3 * std_v)).astype(int)
            new_columns.append(name)
        if "missing_flag" in t_list:
            name = f"{col}_missing"; df[name] = df[col].isna().astype(int); new_columns.append(name)
        if "bin_equal" in t_list:
            try:
                name = f"{col}_bin"; df[name] = pd.cut(vals, bins=5, labels=False); new_columns.append(name)
            except Exception:
                pass
        if "bin_quantile" in t_list:
            try:
                name = f"{col}_qbin"; df[name] = pd.qcut(vals, q=5, labels=False, duplicates="drop"); new_columns.append(name)
            except Exception:
                pass

    date_parts = config.get("date_parts") or ["year", "month", "day", "dayofweek"]
    for col in (config.get("date_cols") or []):
        if col not in df.columns:
            continue
        try:
            dt = pd.to_datetime(df[col], errors="coerce")
            for part in date_parts:
                name = f"{col}_{part}"; df[name] = getattr(dt.dt, part); new_columns.append(name)
        except Exception:
            pass

    for item in (config.get("cyclical") or []):
        col    = item.get("col", "")
        period = float(item.get("period", 24))
        if col not in df.columns:
            continue
        try:
            vals = pd.to_numeric(df[col], errors="coerce")
            df[f"{col}_sin"] = _np.sin(2 * _np.pi * vals / period)
            df[f"{col}_cos"] = _np.cos(2 * _np.pi * vals / period)
            new_columns += [f"{col}_sin", f"{col}_cos"]
        except Exception:
            pass

    for pair in (config.get("interactions") or []):
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

    poly_cols = [c for c in (config.get("poly_cols") or []) if c in df.columns]
    if len(poly_cols) >= 2:
        try:
            from sklearn.preprocessing import PolynomialFeatures
            Xp = df[poly_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
            pf = PolynomialFeatures(degree=int(config.get("poly_degree", 2)),
                                    include_bias=False, interaction_only=True)
            arr = pf.fit_transform(Xp)
            for i, raw_name in enumerate(pf.get_feature_names_out(poly_cols)):
                if " " in raw_name:
                    safe = raw_name.replace(" ", "_x_")
                    df[safe] = arr[:, i]
                    new_columns.append(safe)
        except Exception:
            pass

    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return {
        "csv_b64":     _b64.b64encode(buf.getvalue()).decode(),
        "filename":    "engineered.csv",
        "cols_before": cols_before,
        "cols_after":  len(df.columns),
        "rows":        len(df),
        "new_columns": new_columns,
    }
