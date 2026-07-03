"""Core drift computation: per-field processors and overall score."""
from __future__ import annotations

import numpy as np

from routers.drift._stats import (
    psi_numeric, psi_categorical, ks_test, histogram,
    is_number, level, psi_level,
)


def compute_drift(
    schema: dict,
    rows: list[dict],
    baseline: dict,
    mode: str = "predictions",
) -> dict:
    n_recent = len(rows)
    skip     = set(schema.get("id_cols", [])) | set(schema.get("ensure_cols", []))

    features: list[dict] = []
    used_pipeline_baseline = False

    for field in schema.get("fields", []):
        name  = field["name"]
        ftype = field.get("type")
        if name in skip:
            continue

        if ftype == "number":
            feat = _process_numeric(field, name, rows, n_recent, baseline, mode)
            if feat["name"] in baseline:
                used_pipeline_baseline = True
            features.append(feat)

        elif ftype == "select":
            features.append(_process_categorical(field, name, rows, n_recent))

    overall = max((f["drift_score"] for f in features), default=0.0)
    return {
        "n_recent":      n_recent,
        "overall_score": round(overall, 4),
        "overall_level": level(overall, 0.35, 0.65),
        "baseline":      "training" if used_pipeline_baseline else "schema",
        "source":        "predictions",
        "features":      features,
    }


def _process_numeric(
    field: dict,
    name: str,
    rows: list[dict],
    n_recent: int,
    baseline: dict,
    mode: str,
) -> dict:
    if name in baseline:
        ref_mean = baseline[name]["mean"]
        ref_std  = baseline[name]["std"]
    else:
        fmin     = float(field.get("min", 0))
        fmax     = float(field.get("max", 1))
        ref_mean = (fmin + fmax) / 2
        ref_std  = max((fmax - fmin) / 6, 1e-9)

    vals = [
        float(r[name])
        for r in rows
        if name in r and r[name] is not None and is_number(r[name])
    ]
    null_count = n_recent - len(vals)
    null_rate  = round(null_count / n_recent, 4) if n_recent else 0.0

    if vals:
        r_mean = float(np.mean(vals))
        r_std  = float(np.std(vals)) if len(vals) > 1 else 0.0
        z            = abs(r_mean - ref_mean) / ref_std
        drift_score  = round(min(1.0, z / 3), 4)
        psi_val      = psi_numeric(vals, ref_mean, ref_std)
        hist         = histogram(vals, ref_mean, ref_std)
        ks_stat = ks_pval = None
        if mode == "upload" and len(vals) >= 5:
            ks_stat, ks_pval = ks_test(vals, ref_mean, ref_std)
    else:
        r_mean = r_std = None
        drift_score = psi_val = 0.0
        hist        = None
        ks_stat = ks_pval = None

    feat: dict = {
        "name":        name,
        "label":       field.get("label", name),
        "type":        "numeric",
        "ref_mean":    round(ref_mean, 4),
        "ref_std":     round(ref_std, 4),
        "recent_mean": round(r_mean, 4) if r_mean is not None else None,
        "recent_std":  round(r_std, 4)  if r_std  is not None else None,
        "drift_score": drift_score,
        "drift_level": level(drift_score, 0.35, 0.65),
        "psi":         round(psi_val, 4),
        "psi_level":   psi_level(psi_val),
        "null_rate":   null_rate,
        "n_recent":    len(vals),
    }
    if ks_stat is not None:
        feat["ks_stat"]   = round(float(ks_stat), 4)
        feat["ks_pvalue"] = round(float(ks_pval), 4)
    if hist:
        feat["histogram"] = hist
    return feat


def _process_categorical(
    field: dict,
    name: str,
    rows: list[dict],
    n_recent: int,
) -> dict:
    opts   = [str(o["value"]) for o in field.get("options", [])]
    n_opts = len(opts)
    if not opts:
        return {}

    if n_opts > 20:
        vals = [str(r[name]) for r in rows if name in r and r[name] is not None]
        return {
            "name":             name,
            "label":            field.get("label", name),
            "type":             "categorical",
            "high_cardinality": True,
            "n_opts":           n_opts,
            "n_unique_recent":  len(set(vals)),
            "drift_score":      0.0,
            "drift_level":      "low",
            "psi":              0.0,
            "psi_level":        "low",
            "null_rate":        0.0,
        }

    cat_freq = field.get("cat_freq")
    if cat_freq:
        raw   = {str(k): float(v) for k, v in cat_freq.items()}
        total = sum(raw.get(o, 0.0) for o in opts) or 1.0
        ref_dist = {o: raw.get(o, 0.0) / total for o in opts}
        cat_baseline = "training"
    else:
        ref_p    = 1.0 / n_opts
        ref_dist = {o: ref_p for o in opts}
        cat_baseline = "uniform"

    vals = [
        str(r[name]) for r in rows
        if name in r and r[name] is not None and str(r[name]).strip()
    ]
    null_count = n_recent - len(vals)
    null_rate  = round(null_count / n_recent, 4) if n_recent else 0.0

    if vals:
        n_vals  = len(vals)
        r_dist  = {o: vals.count(o) / n_vals for o in opts}
        drift_score = round(
            sum(abs(r_dist[o] - ref_dist[o]) for o in opts) / n_opts, 4
        )
        psi_val = psi_categorical(r_dist, ref_dist, opts)
    else:
        r_dist      = {o: 0.0 for o in opts}
        drift_score = 0.0
        psi_val     = 0.0

    return {
        "name":         name,
        "label":        field.get("label", name),
        "type":         "categorical",
        "options":      opts,
        "ref_dist":     {o: round(ref_dist[o], 4) for o in opts},
        "recent_dist":  {o: round(r_dist.get(o, 0.0), 4) for o in opts},
        "drift_score":  drift_score,
        "drift_level":  level(drift_score, 0.15, 0.30),
        "psi":          round(psi_val, 4),
        "psi_level":    psi_level(psi_val),
        "null_rate":    null_rate,
        "n_recent":     len(vals),
        "cat_baseline": cat_baseline,
    }
