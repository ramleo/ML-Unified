"""Putting a Pipeline Builder model into the shared MODELS registry, properly.

MODELS is read by more than the tool that writes to it: /models lists every
entry, and the drift detector pulls a training baseline out of each one. Both
assume a "schema" key. A stage that stored a bare pipeline made every one of
those readers fail — `/models` returned 500 for the whole list because one
entry had no schema, which took the Data Drift tool down with it.

So registration goes through here, and the entry is built the same shape the
AutoML trainer produces.
"""
from __future__ import annotations

import pandas as pd

from routers.core.shared import MODELS

_ACCENT = "#22c55e"  # Express mode's green, so these are recognisable in a list


def _fields_for(X: pd.DataFrame) -> list[dict]:
    """Describe each input column the way the schema consumers expect.

    Same rule as the AutoML trainer: numeric with more than fifteen distinct
    values is a number, anything else is a category.
    """
    fields: list[dict] = []
    for col in X.columns:
        is_cat = not pd.api.types.is_numeric_dtype(X[col]) or X[col].nunique() <= 15
        if is_cat:
            opts = [{"value": str(v), "label": str(v)} for v in sorted(X[col].dropna().unique().tolist())]
            fields.append({"name": col, "label": col, "type": "select", "options": opts})
        else:
            cmin = round(float(X[col].min()), 4)
            cmax = round(float(X[col].max()), 4)
            rng = cmax - cmin
            fields.append({
                "name": col, "label": col, "type": "number",
                "min": cmin, "max": cmax,
                "step": max(round(rng / 100, 4) if rng > 0 else 1.0, 0.0001),
            })
    return fields


def register_pb_model(
    model_id: str,
    pipeline,
    X: pd.DataFrame,
    target: str,
    task_type: str,
    algo: str,
    score: float,
    class_names: list[str] | None = None,
) -> None:
    """Store a Pipeline Builder model as a first-class registry entry."""
    is_clf = task_type == "classification"
    metric = "f1_weighted" if is_clf else "neg_mean_absolute_error"

    output: dict = {"type": task_type, "target_col": target}
    if class_names:
        output["class_names"] = class_names

    MODELS[model_id] = {
        "pipeline": pipeline,
        "target":   target,
        "task":     task_type,
        "cols":     list(X.columns),
        "pb":       True,
        "algo":     algo,
        "score":    score,
        "classes":  class_names,
        "schema": {
            "id":          model_id,
            "title":       f"Pipeline Builder — {algo}",
            "description": f"Trained in the Pipeline Builder on {len(X.columns)} features, predicting {target}.",
            "task":        task_type,
            "accent":      _ACCENT,
            "model":       algo,
            "metric":      metric,
            "metricLabel": "F1 (weighted)" if is_clf else "MAE",
            "id_cols":     [],
            "ensure_cols": [],
            "fields":      _fields_for(X),
            "output":      output,
        },
    }
