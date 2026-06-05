import io
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File

router = APIRouter()


def _to_native(v):
    if pd.isna(v):
        return None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    return str(v)


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
        raw_s    = s if len(s) <= 300 else s.sample(300, random_state=42)
        stats[col] = {
            "mean":     round(float(s.mean()), 4),
            "median":   round(float(s.median()), 4),
            "std":      round(float(s.std()), 4),
            "min":      round(float(s.min()), 4),
            "max":      round(float(s.max()), 4),
            "q25":      round(q25, 4),
            "q75":      round(q75, 4),
            "outliers": outliers,
            "skew":     round(float(s.skew()), 3),
            "kurtosis": round(float(s.kurtosis()), 3),
            "raw_vals": [round(float(v), 4) for v in raw_s.tolist()],
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

    # Sample data — first 5 rows
    sample = {
        "columns": df.columns.tolist(),
        "rows": [
            [_to_native(v) for v in row]
            for row in df.head(5).itertuples(index=False, name=None)
        ],
    }

    # Smart insights
    insights = []

    for c in columns:
        if c["missing_pct"] > 20:
            insights.append({"type": "danger",  "text": f"'{c['name']}' has {c['missing_pct']}% missing — consider dropping or imputing before training."})
        elif c["missing_pct"] > 5:
            insights.append({"type": "warning", "text": f"'{c['name']}' has {c['missing_pct']}% missing values."})

    if overview["duplicates"] > 0:
        dup_pct = round(overview["duplicates"] / overview["rows"] * 100, 1)
        level = "warning" if dup_pct > 5 else "info"
        insights.append({"type": level, "text": f"{overview['duplicates']} duplicate rows ({dup_pct}%) — deduplicate before training."})

    for col, s in stats.items():
        if abs(s["skew"]) > 2:
            insights.append({"type": "info", "text": f"'{col}' is highly skewed (skew={s['skew']}) — consider a log or Box-Cox transform."})

    for col, s in stats.items():
        if overview["rows"] > 0:
            out_pct = round(s["outliers"] / overview["rows"] * 100, 1)
            if out_pct > 10:
                insights.append({"type": "warning", "text": f"'{col}' has {s['outliers']} outliers ({out_pct}%) — check for data entry errors."})

    if correlations:
        labels = correlations["labels"]
        matrix = correlations["matrix"]
        seen: set = set()
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                v = matrix[i][j]
                if v is not None and abs(v) >= 0.9:
                    pair = tuple(sorted([labels[i], labels[j]]))
                    if pair not in seen:
                        seen.add(pair)
                        insights.append({"type": "danger", "text": f"'{labels[i]}' and '{labels[j]}' are highly correlated ({v:.2f}) — multicollinearity risk for linear models."})

    # Data quality score (0–100)
    score = 100.0
    score -= min(40, overview["missing_pct"] * 2)
    dup_pct_raw = overview["duplicates"] / max(overview["rows"], 1) * 100
    score -= min(15, dup_pct_raw * 3)
    if stats:
        avg_abs_skew = sum(abs(s["skew"]) for s in stats.values()) / len(stats)
        score -= min(10, avg_abs_skew * 2)
        if overview["rows"] > 0:
            avg_out_pct = sum(s["outliers"] / overview["rows"] * 100 for s in stats.values()) / len(stats)
            score -= min(15, avg_out_pct * 1.5)
    quality_score = max(0, round(score))

    return {
        "overview":      overview,
        "columns":       columns,
        "stats":         stats,
        "distributions": distributions,
        "correlations":  correlations,
        "sample":        sample,
        "insights":      insights,
        "quality_score": quality_score,
    }
