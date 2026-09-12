"""Shared conversions for the EDA responses."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _to_native(v):
    if pd.isna(v):
        return None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    return str(v)


def json_safe(obj):
    """Replace every non-finite float with None, recursively.

    JSON has no NaN and no Infinity, so Starlette's encoder raises and the
    whole request becomes a 500 with no clue in the body. This is not
    hypothetical: the deployed service returned 500 for any CSV with a
    numeric column of fewer than four non-null values, because pandas gives
    NaN for the kurtosis of three points. Standard deviation does the same
    below two values and skew below three.

    Individual computations still guard where a NaN means something
    specific — see compute_correlations. This is the boundary net, applied
    to the whole response, so a statistic added next year cannot reopen the
    same hole. A missing statistic is null, which the page can render as
    "not enough data"; a 500 tells the user nothing at all.
    """
    if isinstance(obj, float):
        return None if math.isnan(obj) or math.isinf(obj) else obj
    if isinstance(obj, np.floating):
        value = float(obj)
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    return obj
