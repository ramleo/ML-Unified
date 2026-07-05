"""Extract training baseline stats from fitted sklearn pipeline, and batch stats for versioning."""
from __future__ import annotations

import numpy as np

_baseline_cache: dict[str, dict] = {}


def get_baseline(model_id: str, model_entry: dict) -> dict:
    if model_id not in _baseline_cache:
        _baseline_cache[model_id] = _extract_pipeline_stats(
            model_entry["pipeline"], model_entry["schema"]
        )
    return _baseline_cache[model_id]


def _extract_pipeline_stats(pipeline, schema: dict) -> dict:
    """Pull mean/std per numeric field from the fitted sklearn pipeline.

    Priority: StandardScaler.mean_/scale_ > SimpleImputer.statistics_ > schema range.
    """
    stats: dict = {}
    try:
        prep = pipeline.named_steps.get("prep")
        if prep is None:
            return stats

        skip = set(schema.get("id_cols", [])) | set(schema.get("ensure_cols", []))
        field_map = {
            f["name"]: f
            for f in schema.get("fields", [])
            if f["name"] not in skip
        }

        for t_name, transformer, cols in prep.transformers_:
            if t_name != "num":
                continue

            imp    = _step(transformer, "imp")
            scaler = _step(transformer, "scaler")

            for i, col in enumerate(cols):
                if col in skip or col not in field_map:
                    continue
                field = field_map[col]
                fmin  = float(field.get("min", 0))
                fmax  = float(field.get("max", 1))
                schema_std = max((fmax - fmin) / 6, 1e-9)

                if scaler is not None and hasattr(scaler, "mean_") and i < len(scaler.mean_):
                    stats[col] = {
                        "mean":   float(scaler.mean_[i]),
                        "std":    max(float(scaler.scale_[i]), 1e-9),
                        "source": "training",
                    }
                elif imp is not None and hasattr(imp, "statistics_") and i < len(imp.statistics_):
                    stats[col] = {
                        "mean":   float(imp.statistics_[i]),
                        "std":    schema_std,
                        "source": "training",
                    }
    except Exception:
        pass

    return stats


def _step(transformer, name):
    if hasattr(transformer, "named_steps"):
        return transformer.named_steps.get(name)
    return None


def extract_batch_stats(schema: dict, rows: list[dict]) -> dict:
    """Compute mean/std per numeric column from a batch of rows (for version storage)."""
    stats: dict = {}
    skip = set(schema.get("id_cols", [])) | set(schema.get("ensure_cols", []))
    for field in schema.get("fields", []):
        name  = field["name"]
        ftype = field.get("type")
        if name in skip or ftype != "number":
            continue
        vals = [float(r[name]) for r in rows if name in r and r[name] is not None]
        if len(vals) < 2:
            continue
        arr = np.array(vals, dtype=np.float32)
        stats[name] = {
            "mean":   float(arr.mean()),
            "std":    max(float(arr.std()), 1e-9),
            "source": "batch",
        }
    return stats


def baseline_from_version_stats(version_stats: dict) -> dict:
    """Convert stored version stats into the same format as get_baseline() output."""
    return {col: {"mean": s["mean"], "std": s["std"], "source": s["source"]}
            for col, s in version_stats.items()}
