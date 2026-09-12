"""Extract training baseline stats from fitted sklearn pipeline, and batch stats for versioning."""
from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

_baseline_cache: dict[str, dict] = {}


def get_baseline(model_id: str, model_entry: dict) -> dict:
    if model_id not in _baseline_cache:
        _baseline_cache[model_id] = _extract_pipeline_stats(
            model_entry["pipeline"], model_entry["schema"]
        )
    return _baseline_cache[model_id]


def _find_preprocessor(pipeline):
    """The fitted ColumnTransformer, whatever its step happens to be called.

    This was `named_steps.get("prep")`. The built-in models name that step
    "preprocessor" and the Pipeline Builder named it "pre", so the lookup
    returned None for every one of them, the baseline came back empty, and
    _compute quietly substituted (min+max)/2 for the training mean — reporting
    an invented number as a measurement. Matching on type rather than on a
    name nobody agreed on is what stops that recurring.
    """
    from sklearn.compose import ColumnTransformer

    steps = getattr(pipeline, "named_steps", None)
    if not steps:
        return None
    for name in ("prep", "preprocessor", "pre"):
        step = steps.get(name)
        if isinstance(step, ColumnTransformer):
            return step
    for step in steps.values():
        if isinstance(step, ColumnTransformer):
            return step
    return None


def _extract_pipeline_stats(pipeline, schema: dict) -> dict:
    """Pull mean/std per numeric field from the fitted sklearn pipeline.

    Priority: StandardScaler.mean_/scale_ > SimpleImputer.statistics_ > schema range.
    """
    stats: dict = {}
    try:
        prep = _find_preprocessor(pipeline)
        if prep is None:
            logger.warning(
                "no ColumnTransformer found in this pipeline — drift will fall back "
                "to the declared schema range, which is a guess and not a measurement"
            )
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
    except Exception as exc:
        logger.error(
            "Training baseline extraction failed — drift comparisons for this "
            "model will use an empty/partial baseline with no warning otherwise: %s",
            exc,
        )

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
