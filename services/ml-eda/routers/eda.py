import io
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics import mutual_info_score
from sklearn.preprocessing import KBinsDiscretizer, StandardScaler
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

    # ── ML Readiness panel ──────────────────────────────────────
    readiness = []
    for c in columns:
        issues, verdict = [], "pass"

        # ID-like column
        if c["nunique"] == overview["rows"] and overview["rows"] > 10:
            issues.append("100% unique — likely an ID column")
            verdict = "fail"

        # Near-constant
        if c["is_numeric"] and c["name"] in stats:
            if stats[c["name"]]["std"] < 0.01 and stats[c["name"]]["std"] >= 0:
                issues.append("Near-zero variance — won't help model")
                verdict = "fail"
        elif not c["is_numeric"] and c["nunique"] <= 1:
            issues.append("Constant column — won't help model")
            verdict = "fail"

        # High missing
        if c["missing_pct"] > 20:
            issues.append(f"{c['missing_pct']}% missing — drop or impute")
            verdict = "fail" if verdict != "fail" else verdict
        elif c["missing_pct"] > 5:
            issues.append(f"{c['missing_pct']}% missing — impute recommended")
            if verdict == "pass":
                verdict = "warn"

        # High cardinality categorical
        if not c["is_numeric"] and c["nunique"] > 50 and c["nunique"] < overview["rows"]:
            issues.append(f"{c['nunique']} unique categories — needs target/freq encoding")
            if verdict == "pass":
                verdict = "warn"

        # Datetime not engineered
        if not c["is_numeric"]:
            sample_vals = df[c["name"]].dropna().head(5).astype(str).tolist()
            looks_like_date = any(
                any(ch in v for ch in ["-", "/"])
                and any(ch.isdigit() for ch in v)
                for v in sample_vals
            )
            if looks_like_date and c["nunique"] > 10:
                issues.append("Looks like a date — extract year/month/day features")
                if verdict == "pass":
                    verdict = "warn"

        # High skew
        if c["is_numeric"] and c["name"] in stats and abs(stats[c["name"]]["skew"]) > 2:
            issues.append(f"Highly skewed (skew={stats[c['name']]['skew']}) — log transform recommended")
            if verdict == "pass":
                verdict = "warn"

        rec = "Ready to use" if not issues else "; ".join(issues)
        readiness.append({"name": c["name"], "verdict": verdict, "reason": rec})

    # ── Auto-generated narrative ─────────────────────────────────
    num_count  = len(num_cols)
    cat_count  = len(cat_cols)
    col_desc   = f"{num_count} numeric, {cat_count} categorical" if cat_count else f"{num_count} numeric"
    miss_cols  = [c for c in columns if c["missing_pct"] > 5]
    miss_note  = ""
    if miss_cols:
        worst = max(miss_cols, key=lambda c: c["missing_pct"])
        miss_note = f" {len(miss_cols)} column(s) have notable missing values — worst is '{worst['name']}' at {worst['missing_pct']}%."

    dup_note = f" {overview['duplicates']} duplicate row(s) found — deduplicate before training." if overview["duplicates"] > 0 else ""

    corr_note = ""
    if correlations:
        lbls, mat = correlations["labels"], correlations["matrix"]
        best_pair, best_v = None, 0.0
        for i in range(len(lbls)):
            for j in range(i + 1, len(lbls)):
                v = mat[i][j]
                if v is not None and abs(v) > abs(best_v):
                    best_v, best_pair = v, (lbls[i], lbls[j])
        if best_pair and abs(best_v) >= 0.5:
            direction = "positively" if best_v > 0 else "negatively"
            corr_note = f" Strongest relationship: '{best_pair[0]}' and '{best_pair[1]}' are {direction} correlated ({best_v:.2f})."

    target_note = ""
    for c in columns:
        if not c["is_numeric"] and 2 <= c["nunique"] <= 5:
            vc = df[c["name"]].value_counts(normalize=True)
            if len(vc) == 2:
                minority = round(vc.iloc[1] * 100, 1)
                balance = "balanced" if 35 <= minority <= 65 else "imbalanced"
                target_note = f" '{c['name']}' looks like a classification target ({balance}: {minority}% minority class)."
                break

    quality_label = "excellent" if quality_score >= 80 else "fair" if quality_score >= 60 else "poor"
    narrative = (
        f"This dataset has {overview['rows']:,} rows and {overview['cols']} columns ({col_desc}). "
        f"Data quality is {quality_label} ({quality_score}/100).{miss_note}{dup_note}{corr_note}{target_note} "
        f"{len([r for r in readiness if r['verdict']=='fail'])} column(s) flagged as ML-unready; "
        f"{len([r for r in readiness if r['verdict']=='warn'])} need attention."
    )

    # ── Mutual Information matrix ────────────────────────────────
    mi_result = None
    all_cols = df.columns.tolist()
    mi_cols  = all_cols[:15]  # cap at 15 columns
    if len(mi_cols) >= 2:
        # Discretize every column into bins for MI computation
        disc = {}
        kbd  = KBinsDiscretizer(n_bins=10, encode="ordinal", strategy="quantile", subsample=None)
        for col in mi_cols:
            try:
                s = df[col].fillna(df[col].mode().iloc[0] if not df[col].mode().empty else 0)
                if pd.api.types.is_numeric_dtype(s):
                    disc[col] = kbd.fit_transform(s.values.reshape(-1, 1)).ravel().astype(int)
                else:
                    codes, _ = pd.factorize(s)
                    disc[col] = codes
            except Exception:
                disc[col] = np.zeros(len(df), dtype=int)

        def _norm_mi(x: np.ndarray, y: np.ndarray) -> float:
            mi  = mutual_info_score(x, y)
            hx  = mutual_info_score(x, x)
            hy  = mutual_info_score(y, y)
            denom = max(hx, hy)
            return round(float(mi / denom), 3) if denom > 0 else 0.0

        mi_matrix = []
        for ci in mi_cols:
            row = []
            for cj in mi_cols:
                row.append(_norm_mi(disc[ci], disc[cj]))
            mi_matrix.append(row)

        mi_result = {"labels": mi_cols, "matrix": mi_matrix}

    # ── PCA 3D scatter ───────────────────────────────────────────
    pca_result = None
    pca_num_cols = [c for c in num_cols if df[c].isnull().sum() / len(df) < 0.5]
    if len(pca_num_cols) >= 3:
        try:
            n_components = min(3, len(pca_num_cols))
            pca_df = df[pca_num_cols].fillna(df[pca_num_cols].median())
            scaled = StandardScaler().fit_transform(pca_df)
            pca = PCA(n_components=n_components)
            coords_arr = pca.fit_transform(scaled)
            coords = coords_arr.tolist()
            # Pad to 3 cols if fewer than 3 numeric cols survived
            if n_components < 3:
                for row in coords:
                    while len(row) < 3:
                        row.append(0.0)
            ev = [round(float(v) * 100, 1) for v in pca.explained_variance_ratio_]
            while len(ev) < 3:
                ev.append(0.0)
            # Build color map: all categorical cols + low-cardinality numeric cols
            # Low-cardinality numerics (2-15 unique) are useful as class labels
            low_card_num = [c for c in num_cols if 2 <= df[c].nunique() <= 15]
            color_option_cols = list(dict.fromkeys(cat_cols[:8] + low_card_num[:4]))
            cat_color_map: dict = {}
            for cc in color_option_cols:
                try:
                    cat_color_map[cc] = df[cc].fillna("N/A").astype(str).tolist()
                except Exception:
                    pass
            color_col = color_option_cols[0] if color_option_cols else None
            pca_result = {
                "coords": coords,
                "explained_variance": ev,
                "labels": pca_num_cols,
                "color_col": color_col,
                "cat_cols": color_option_cols,
                "cat_color_map": cat_color_map,
            }
        except Exception:
            pca_result = None

    # ── SPLOM (Scatter Plot Matrix) ──────────────────────────────
    splom_result = None
    splom_cols = [c for c in num_cols if df[c].isnull().sum() / len(df) < 0.5][:8]
    if len(splom_cols) >= 2:
        try:
            splom_df = df[splom_cols].dropna()
            n_sample = min(400, len(splom_df))
            if n_sample > 0:
                splom_sample = splom_df.sample(n_sample, random_state=42) if len(splom_df) > n_sample else splom_df
                splom_data: dict = {c: [round(float(v), 4) for v in splom_sample[c].tolist()] for c in splom_cols}
                # Include one categorical color column if available (aligned to same rows)
                splom_color_col = None
                splom_color_vals = None
                splom_color_map: dict = {}
                for cc in cat_cols[:5] + [c for c in num_cols if 2 <= df[c].nunique() <= 15][:3]:
                    if cc in df.columns:
                        try:
                            vals = df.loc[splom_sample.index, cc].fillna("N/A").astype(str).tolist()
                            splom_color_map[cc] = vals
                            if splom_color_col is None:
                                splom_color_col = cc
                                splom_color_vals = vals
                        except Exception:
                            pass
                splom_result = {
                    "cols": splom_cols,
                    "data": splom_data,
                    "n": n_sample,
                    "color_col": splom_color_col,
                    "color_vals": splom_color_vals,
                    "color_map": splom_color_map,
                }
        except Exception:
            splom_result = None

    # ── Low-variance flags ───────────────────────────────────────
    low_variance_cols = set()
    for col, s in stats.items():
        col_range = s["max"] - s["min"]
        # Flag if std is very small relative to range (or absolutely near-zero)
        if col_range > 0 and s["std"] / col_range < 0.05:
            low_variance_cols.add(col)
        elif s["std"] < 1e-6:
            low_variance_cols.add(col)

    return {
        "overview":      overview,
        "columns":       columns,
        "stats":         stats,
        "distributions": distributions,
        "correlations":  correlations,
        "sample":        sample,
        "insights":      insights,
        "quality_score": quality_score,
        "readiness":        readiness,
        "narrative":        narrative,
        "mi":               mi_result,
        "pca":              pca_result,
        "splom":            splom_result,
        "low_variance_cols": list(low_variance_cols),
    }
