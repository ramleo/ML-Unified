import io
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File

router = APIRouter()


@router.post("/eda")
async def exploratory_analysis(file: UploadFile = File(...)):
    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")

    if df.empty or len(df.columns) < 1:
        raise HTTPException(400, "CSV must have at least 1 column and 1 row")

    overview = {
        "rows":          len(df),
        "cols":          len(df.columns),
        "duplicates":    int(df.duplicated().sum()),
        "missing_total": int(df.isnull().sum().sum()),
        "missing_pct":   round(df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100, 1),
    }

    columns = []
    for col in df.columns:
        is_num  = pd.api.types.is_numeric_dtype(df[col])
        missing = int(df[col].isnull().sum())
        columns.append({
            "name":        col,
            "dtype":       str(df[col].dtype),
            "is_numeric":  is_num,
            "missing":     missing,
            "missing_pct": round(missing / len(df) * 100, 1),
            "nunique":     int(df[col].nunique()),
        })

    num_cols = df.select_dtypes(include="number").columns.tolist()
    stats = {}
    for col in num_cols:
        s = df[col].dropna()
        if len(s) == 0:
            continue
        q25, q75 = float(s.quantile(0.25)), float(s.quantile(0.75))
        iqr      = q75 - q25
        outliers = int(((s < q25 - 1.5 * iqr) | (s > q75 + 1.5 * iqr)).sum())
        stats[col] = {
            "mean":     round(float(s.mean()), 4),
            "median":   round(float(s.median()), 4),
            "std":      round(float(s.std()), 4),
            "min":      round(float(s.min()), 4),
            "max":      round(float(s.max()), 4),
            "q25":      round(q25, 4),
            "q75":      round(q75, 4),
            "outliers": outliers,
        }

    distributions = {}
    for col in num_cols[:12]:
        s = df[col].dropna()
        if len(s) == 0:
            continue
        n_bins = min(20, max(5, int(len(s) ** 0.5)))
        counts, edges = np.histogram(s, bins=n_bins)
        distributions[col] = {
            "type":   "histogram",
            "bins":   [round(float(b), 4) for b in edges[:-1]],
            "counts": counts.tolist(),
        }

    cat_cols = df.select_dtypes(exclude="number").columns.tolist()
    for col in cat_cols[:6]:
        vc = df[col].value_counts().head(10)
        distributions[col] = {
            "type":   "bar",
            "labels": [str(v) for v in vc.index.tolist()],
            "counts": vc.values.tolist(),
        }

    correlations = None
    if len(num_cols) >= 2:
        corr = df[num_cols].corr().round(3)
        correlations = {
            "labels": num_cols,
            "matrix": [[None if np.isnan(v) else v for v in row]
                       for row in corr.values.tolist()],
        }

    return {
        "overview":      overview,
        "columns":       columns,
        "stats":         stats,
        "distributions": distributions,
        "correlations":  correlations,
    }
