"""Data drift detection router — /drift endpoints."""
from __future__ import annotations

import io
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, UploadFile, File

from routers.drift._state import (
    record_input, record_snapshot,
    get_recent, get_trend, get_history,
)
from routers.drift._baseline import get_baseline
from routers.drift._compute import compute_drift

router = APIRouter(prefix="/drift", tags=["drift"])

# Re-export so callers (app.py /predict) can still do:
#   from routers import drift as _drift_router; _drift_router.record_input(...)
__all__ = ["router", "record_input"]


@router.get("/{model_id}")
def get_drift(model_id: str):
    from app import MODELS  # noqa: PLC0415
    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")

    m        = MODELS[model_id]
    baseline = get_baseline(model_id, m)
    rows     = get_recent(model_id)
    trend    = get_trend(model_id)
    result   = compute_drift(m["schema"], rows, baseline, mode="predictions")
    result["trend"] = trend
    if rows:
        record_snapshot(model_id, result)
    return result


@router.post("/{model_id}/upload")
async def upload_drift(
    model_id: str,
    file: UploadFile = File(...),
    label: Optional[str] = Query(default=None, description="Optional batch label, e.g. 'Week 3'"),
):
    from app import MODELS  # noqa: PLC0415
    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")

    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")

    if df.empty:
        raise HTTPException(400, "CSV is empty")

    m        = MODELS[model_id]
    baseline = get_baseline(model_id, m)
    rows     = df.to_dict(orient="records")
    trend    = get_trend(model_id)
    result   = compute_drift(m["schema"], rows, baseline, mode="upload")
    result["source"]   = "upload"
    result["filename"] = file.filename or "dataset.csv"
    result["label"]    = label or file.filename or "Batch"
    result["trend"]    = trend
    record_snapshot(model_id, result, label=label)
    return result


@router.get("/{model_id}/history")
def get_drift_history(model_id: str):
    from app import MODELS  # noqa: PLC0415
    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")
    return {"history": get_history(model_id)}
