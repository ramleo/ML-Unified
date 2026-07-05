"""Data drift detection router — /drift endpoints."""
from __future__ import annotations

import io
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import StreamingResponse

from routers.drift._state import (
    record_input, record_snapshot,
    get_recent, get_trend, get_history,
    save_version, get_versions, get_previous_version_stats,
)
from routers.drift._baseline import get_baseline, extract_batch_stats, baseline_from_version_stats
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
    compare_to_training: bool = Query(default=False, description="If true, always compare against training baseline instead of previous batch"),
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

    m    = MODELS[model_id]
    rows = df.to_dict(orient="records")

    # Choose baseline: previous batch version or training baseline
    prev_stats    = get_previous_version_stats(model_id) if not compare_to_training else None
    training_base = get_baseline(model_id, m)
    if prev_stats:
        baseline            = baseline_from_version_stats(prev_stats)
        compared_against    = get_versions(model_id)[-1]["label"]
        compared_against_v  = get_versions(model_id)[-1]["version"]
    else:
        baseline            = training_base
        compared_against    = "Training baseline"
        compared_against_v  = 1

    trend  = get_trend(model_id)
    result = compute_drift(m["schema"], rows, baseline, mode="upload")
    result["source"]              = "upload"
    result["filename"]            = file.filename or "dataset.csv"
    result["label"]               = label or file.filename or "Batch"
    result["trend"]               = trend
    result["compared_against"]    = compared_against
    result["compared_against_v"]  = compared_against_v

    # Save this batch as a new version
    batch_stats = extract_batch_stats(m["schema"], rows)
    version_entry = save_version(model_id, label, batch_stats)
    result["version_num"] = version_entry["version"]

    record_snapshot(model_id, result, label=label)
    return result


@router.get("/{model_id}/versions")
def get_drift_versions(model_id: str):
    from app import MODELS  # noqa: PLC0415
    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")
    vers = get_versions(model_id)
    # Prepend V1 training baseline as a virtual entry
    training = [{"version": 1, "label": "Training baseline", "ts": None, "is_training": True}]
    batch_vers = [{"version": v["version"], "label": v["label"], "ts": v["ts"], "is_training": False}
                  for v in vers]
    return {"versions": training + batch_vers}


@router.get("/{model_id}/history")
def get_drift_history(model_id: str):
    from app import MODELS  # noqa: PLC0415
    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")
    return {"history": get_history(model_id)}


@router.post("/{model_id}/explain")
async def explain_drift(
    model_id: str,
    request: Request,
    provider: str = Query(default="groq", description="LLM provider: groq | gemini | cohere"),
):
    from app import MODELS  # noqa: PLC0415
    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")

    body = await request.json()

    from routers.drift._explain import explain_stream  # noqa: PLC0415
    return StreamingResponse(
        explain_stream(body, provider),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
