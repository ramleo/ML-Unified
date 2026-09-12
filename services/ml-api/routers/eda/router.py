"""EDA router — /eda, /eda/clean and /eda/suggest.

Folded in from the standalone ml-eda service (2026-09-12). It was
deployed, healthy, and returning 500 for any CSV with a numeric column
of fewer than four non-null values — pandas gives NaN for the kurtosis
of three points and JSON cannot carry NaN. Nothing referenced it from
the site, so nobody found out. See _utils.json_safe.
"""
from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, Form, UploadFile, File

from ._utils import _to_native, json_safe
from ._stats import compute_stats, compute_distributions, compute_correlations
from ._readiness import (
    compute_insights, compute_quality_score, compute_readiness,
    compute_narrative, compute_mi, compute_pca, compute_splom, compute_low_variance,
)
from ._clean import run_clean
from ._suggest import router as suggest_router  # noqa: F401  (mounted by app.py)

router = APIRouter()


# The site's other upload routes cap at 10 MB and so does the global body
# middleware; stating it here means the limit survives if this router is ever
# mounted somewhere without that middleware.
MAX_CSV_BYTES = 10 * 1024 * 1024


@router.post("/eda")
async def exploratory_analysis(file: UploadFile = File(...)):
    from fastapi import HTTPException
    content = await file.read()
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(400, "File too large (max 10 MB)")
    if not content:
        raise HTTPException(400, "Empty file")
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")

    if df.empty or len(df.columns) < 1:
        raise HTTPException(400, "CSV must have at least 1 column and 1 row")

    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(exclude="number").columns.tolist()

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

    stats         = compute_stats(df, num_cols)
    distributions = compute_distributions(df, num_cols, cat_cols)
    correlations  = compute_correlations(df, num_cols)

    sample = {
        "columns": df.columns.tolist(),
        "rows": [[_to_native(v) for v in row]
                 for row in df.head(5).itertuples(index=False, name=None)],
    }

    dup_mask = df.duplicated(keep="first")
    dup_df   = df[dup_mask].head(50)
    duplicate_rows = {
        "columns": df.columns.tolist(),
        "rows": [[_to_native(v) for v in row]
                 for row in dup_df.itertuples(index=False, name=None)],
    } if overview["duplicates"] > 0 else None

    insights      = compute_insights(columns, stats, overview, correlations)
    quality_score = compute_quality_score(overview, stats)
    readiness     = compute_readiness(df, columns, stats, overview)
    narrative     = compute_narrative(overview, columns, stats, correlations,
                                      num_cols, cat_cols, readiness, quality_score)
    mi_result     = compute_mi(df)
    pca_result    = compute_pca(df, num_cols, cat_cols)
    splom_result  = compute_splom(df, num_cols, cat_cols)
    low_variance  = compute_low_variance(stats)

    # One choke point. Every statistic below can produce NaN on a small or
    # degenerate column, and each one that does would otherwise be a 500.
    return json_safe({
        "overview":          overview,
        "columns":           columns,
        "stats":             stats,
        "distributions":     distributions,
        "correlations":      correlations,
        "sample":            sample,
        "duplicate_rows":    duplicate_rows,
        "insights":          insights,
        "quality_score":     quality_score,
        "readiness":         readiness,
        "narrative":         narrative,
        "mi":                mi_result,
        "pca":               pca_result,
        "splom":             splom_result,
        "low_variance_cols": low_variance,
    })


@router.post("/eda/clean")
async def clean_dataset(file: UploadFile = File(...), config: str = Form(...)):
    from fastapi import HTTPException
    content  = await file.read()
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(400, "File too large (max 10 MB)")
    if not content:
        raise HTTPException(400, "Empty file")
    filename = file.filename or "data.csv"
    return run_clean(content, config, filename)
