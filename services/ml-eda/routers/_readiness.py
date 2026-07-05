"""ML readiness, insights, narrative, MI, PCA, and SPLOM computation."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics import mutual_info_score
from sklearn.preprocessing import KBinsDiscretizer, StandardScaler


def compute_insights(columns: list, stats: dict, overview: dict, correlations: dict | None) -> list:
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
    return insights


def compute_quality_score(overview: dict, stats: dict) -> int:
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
    return max(0, round(score))


def compute_readiness(df: pd.DataFrame, columns: list, stats: dict, overview: dict) -> list:
    readiness = []
    for c in columns:
        issues, verdict = [], "pass"
        if c["nunique"] == overview["rows"] and overview["rows"] > 10:
            issues.append("100% unique — likely an ID column")
            verdict = "fail"
        if c["is_numeric"] and c["name"] in stats:
            if stats[c["name"]]["std"] < 0.01 and stats[c["name"]]["std"] >= 0:
                issues.append("Near-zero variance — won't help model")
                verdict = "fail"
        elif not c["is_numeric"] and c["nunique"] <= 1:
            issues.append("Constant column — won't help model")
            verdict = "fail"
        if c["missing_pct"] > 20:
            issues.append(f"{c['missing_pct']}% missing — drop or impute")
            verdict = "fail" if verdict != "fail" else verdict
        elif c["missing_pct"] > 5:
            issues.append(f"{c['missing_pct']}% missing — impute recommended")
            if verdict == "pass":
                verdict = "warn"
        if not c["is_numeric"] and c["nunique"] > 50 and c["nunique"] < overview["rows"]:
            issues.append(f"{c['nunique']} unique categories — needs target/freq encoding")
            if verdict == "pass":
                verdict = "warn"
        if not c["is_numeric"]:
            sample_vals = df[c["name"]].dropna().head(5).astype(str).tolist()
            looks_like_date = any(
                any(ch in v for ch in ["-", "/"]) and any(ch.isdigit() for ch in v)
                for v in sample_vals
            )
            if looks_like_date and c["nunique"] > 10:
                issues.append("Looks like a date — extract year/month/day features")
                if verdict == "pass":
                    verdict = "warn"
        if c["is_numeric"] and c["name"] in stats and abs(stats[c["name"]]["skew"]) > 2:
            issues.append(f"Highly skewed (skew={stats[c['name']]['skew']}) — log transform recommended")
            if verdict == "pass":
                verdict = "warn"
        rec = "Ready to use" if not issues else "; ".join(issues)
        readiness.append({"name": c["name"], "verdict": verdict, "reason": rec})
    return readiness


def compute_narrative(overview: dict, columns: list, stats: dict, correlations: dict | None,
                      num_cols: list, cat_cols: list, readiness: list, quality_score: int) -> str:
    num_count = len(num_cols)
    cat_count = len(cat_cols)
    col_desc  = f"{num_count} numeric, {cat_count} categorical" if cat_count else f"{num_count} numeric"
    miss_cols = [c for c in columns if c["missing_pct"] > 5]
    miss_note = ""
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
            vc = (lambda df_col: df_col)(None)  # placeholder — narrative only uses already-computed data
            break
    quality_label = "excellent" if quality_score >= 80 else "fair" if quality_score >= 60 else "poor"
    n_fail = len([r for r in readiness if r["verdict"] == "fail"])
    n_warn = len([r for r in readiness if r["verdict"] == "warn"])
    return (
        f"This dataset has {overview['rows']:,} rows and {overview['cols']} columns ({col_desc}). "
        f"Data quality is {quality_label} ({quality_score}/100).{miss_note}{dup_note}{corr_note} "
        f"{n_fail} column(s) flagged as ML-unready; {n_warn} need attention."
    )


def compute_mi(df: pd.DataFrame) -> dict | None:
    mi_cols = df.columns.tolist()[:15]
    if len(mi_cols) < 2:
        return None
    kbd  = KBinsDiscretizer(n_bins=10, encode="ordinal", strategy="quantile", subsample=None)
    disc: dict = {}
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
        mi    = mutual_info_score(x, y)
        hx    = mutual_info_score(x, x)
        hy    = mutual_info_score(y, y)
        denom = max(hx, hy)
        return round(float(mi / denom), 3) if denom > 0 else 0.0

    mi_matrix = [[_norm_mi(disc[ci], disc[cj]) for cj in mi_cols] for ci in mi_cols]
    return {"labels": mi_cols, "matrix": mi_matrix}


def compute_pca(df: pd.DataFrame, num_cols: list[str], cat_cols: list[str]) -> dict | None:
    pca_num_cols = [c for c in num_cols if df[c].isnull().sum() / len(df) < 0.5]
    if len(pca_num_cols) < 3:
        return None
    try:
        n_components = min(3, len(pca_num_cols))
        pca_df  = df[pca_num_cols].fillna(df[pca_num_cols].median())
        scaled  = StandardScaler().fit_transform(pca_df)
        pca     = PCA(n_components=n_components)
        coords  = pca.fit_transform(scaled).tolist()
        if n_components < 3:
            for row in coords:
                while len(row) < 3:
                    row.append(0.0)
        ev = [round(float(v) * 100, 1) for v in pca.explained_variance_ratio_]
        while len(ev) < 3:
            ev.append(0.0)
        low_card_num = [c for c in num_cols if 2 <= df[c].nunique() <= 15]
        color_opts   = list(dict.fromkeys(cat_cols[:8] + low_card_num[:4]))
        cat_color_map: dict = {}
        for cc in color_opts:
            try:
                cat_color_map[cc] = df[cc].fillna("N/A").astype(str).tolist()
            except Exception:
                pass
        color_col = color_opts[0] if color_opts else None
        return {
            "coords": coords, "explained_variance": ev, "labels": pca_num_cols,
            "color_col": color_col, "cat_cols": color_opts, "cat_color_map": cat_color_map,
        }
    except Exception:
        return None


def compute_splom(df: pd.DataFrame, num_cols: list[str], cat_cols: list[str]) -> dict | None:
    splom_cols = [c for c in num_cols if df[c].isnull().sum() / len(df) < 0.5][:8]
    if len(splom_cols) < 2:
        return None
    try:
        splom_df  = df[splom_cols].dropna()
        n_sample  = min(400, len(splom_df))
        if n_sample == 0:
            return None
        sample = splom_df.sample(n_sample, random_state=42) if len(splom_df) > n_sample else splom_df
        data   = {c: [round(float(v), 4) for v in sample[c].tolist()] for c in splom_cols}
        color_map: dict = {}
        color_col, color_vals = None, None
        for cc in cat_cols[:5] + [c for c in num_cols if 2 <= df[c].nunique() <= 15][:3]:
            if cc in df.columns:
                try:
                    vals = df.loc[sample.index, cc].fillna("N/A").astype(str).tolist()
                    color_map[cc] = vals
                    if color_col is None:
                        color_col, color_vals = cc, vals
                except Exception:
                    pass
        return {"cols": splom_cols, "data": data, "n": n_sample,
                "color_col": color_col, "color_vals": color_vals, "color_map": color_map}
    except Exception:
        return None


def compute_low_variance(stats: dict) -> list[str]:
    low: set = set()
    for col, s in stats.items():
        col_range = s["max"] - s["min"]
        if col_range > 0 and s["std"] / col_range < 0.05:
            low.add(col)
        elif s["std"] < 1e-6:
            low.add(col)
    return list(low)
