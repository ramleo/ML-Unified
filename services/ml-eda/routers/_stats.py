"""Numeric stats, distributions, and correlation computation."""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_stats(df: pd.DataFrame, num_cols: list[str]) -> dict:
    stats: dict = {}
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
    return stats


def compute_distributions(df: pd.DataFrame, num_cols: list[str], cat_cols: list[str]) -> dict:
    distributions: dict = {}
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
    for col in cat_cols[:6]:
        vc = df[col].value_counts().head(10)
        distributions[col] = {
            "type":   "bar",
            "labels": [str(v) for v in vc.index.tolist()],
            "counts": vc.values.tolist(),
        }
    return distributions


def compute_correlations(df: pd.DataFrame, num_cols: list[str]) -> dict | None:
    if len(num_cols) < 2:
        return None
    corr = df[num_cols].corr().round(3)
    return {
        "labels": num_cols,
        "matrix": [
            [None if np.isnan(v) else v for v in row]
            for row in corr.values.tolist()
        ],
    }
