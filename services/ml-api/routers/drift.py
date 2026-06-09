from collections import defaultdict, deque

import io
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File

router = APIRouter(prefix="/drift", tags=["drift"])

# Rolling buffer: model_id -> deque of raw input dicts (last 200 predictions)
_recent: dict[str, deque] = defaultdict(lambda: deque(maxlen=200))

# Cached pipeline stats: model_id -> {field_name: {mean, std, source}}
_baseline_cache: dict[str, dict] = {}


def record_input(model_id: str, fields: dict) -> None:
    """Called by /predict to log the raw input for drift tracking."""
    _recent[model_id].append(fields)


# ── Public endpoints ──────────────────────────────────────────────────────────

@router.get("/{model_id}")
def get_drift(model_id: str):
    from app import MODELS  # noqa: PLC0415

    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")

    m = MODELS[model_id]
    baseline = _get_baseline(model_id, m)
    rows = list(_recent[model_id])
    return _compute_drift(m["schema"], rows, baseline)


@router.post("/{model_id}/upload")
async def upload_drift(model_id: str, file: UploadFile = File(...)):
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

    m = MODELS[model_id]
    baseline = _get_baseline(model_id, m)
    rows = df.to_dict(orient="records")
    result = _compute_drift(m["schema"], rows, baseline)
    result["source"] = "upload"
    result["filename"] = file.filename or "dataset.csv"
    return result


# ── Pipeline baseline extraction ──────────────────────────────────────────────

def _get_baseline(model_id: str, model_entry: dict) -> dict:
    """Return cached training stats; extract from pipeline on first call."""
    if model_id not in _baseline_cache:
        _baseline_cache[model_id] = _extract_pipeline_stats(
            model_entry["pipeline"], model_entry["schema"]
        )
    return _baseline_cache[model_id]


def _extract_pipeline_stats(pipeline, schema: dict) -> dict:
    """
    Pull mean/std per numeric field from the fitted sklearn pipeline.

    Priority:
      1. StandardScaler.mean_ / .scale_  — most accurate (mean + std from training)
      2. SimpleImputer.statistics_       — training median; schema range used for std
      3. Nothing found                   — caller falls back to schema-range estimate
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
                fmin = float(field.get("min", 0))
                fmax = float(field.get("max", 1))
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
        pass  # any extraction failure → fall back to schema estimates

    return stats


def _step(transformer, name):
    """Safely get a named step from a Pipeline; return None if not found."""
    if hasattr(transformer, "named_steps"):
        return transformer.named_steps.get(name)
    return None


# ── Core drift computation ────────────────────────────────────────────────────

def _compute_drift(schema: dict, rows: list[dict], baseline: dict) -> dict:
    n_recent = len(rows)
    skip = set(schema.get("id_cols", [])) | set(schema.get("ensure_cols", []))
    features = []
    used_pipeline_baseline = False

    for field in schema.get("fields", []):
        name = field["name"]
        if name in skip:
            continue

        ftype = field.get("type")

        if ftype == "number":
            # Choose reference stats — pipeline > schema range
            if name in baseline:
                ref_mean = baseline[name]["mean"]
                ref_std  = baseline[name]["std"]
                used_pipeline_baseline = True
            else:
                fmin = float(field.get("min", 0))
                fmax = float(field.get("max", 1))
                ref_mean = (fmin + fmax) / 2
                ref_std  = max((fmax - fmin) / 6, 1e-9)

            vals = [
                float(r[name])
                for r in rows
                if name in r and r[name] is not None and _is_number(r[name])
            ]
            if vals:
                r_mean = float(np.mean(vals))
                r_std  = float(np.std(vals)) if len(vals) > 1 else 0.0
                z = abs(r_mean - ref_mean) / ref_std
                drift_score = round(min(1.0, z / 3), 4)
            else:
                r_mean = r_std = None
                drift_score = 0.0

            features.append({
                "name":        name,
                "label":       field.get("label", name),
                "type":        "numeric",
                "ref_mean":    round(ref_mean, 4),
                "ref_std":     round(ref_std, 4),
                "recent_mean": round(r_mean, 4) if r_mean is not None else None,
                "recent_std":  round(r_std, 4)  if r_std  is not None else None,
                "drift_score": drift_score,
                "drift_level": _level(drift_score, 0.35, 0.65),
                "n_recent":    len(vals),
            })

        elif ftype == "select":
            opts   = [o["value"] for o in field.get("options", [])]
            n_opts = len(opts)
            if n_opts == 0:
                continue
            ref_p = 1.0 / n_opts  # uniform baseline (no frequency data in OHE)

            vals = [
                str(r[name]) for r in rows
                if name in r and r[name] is not None and str(r[name]).strip()
            ]
            if vals:
                counts = {o: vals.count(o) for o in opts}
                r_dist = {o: counts[o] / len(vals) for o in opts}
                drift_score = round(
                    sum(abs(r_dist[o] - ref_p) for o in opts) / n_opts, 4
                )
            else:
                r_dist = {}
                drift_score = 0.0

            features.append({
                "name":        name,
                "label":       field.get("label", name),
                "type":        "categorical",
                "options":     opts,
                "ref_dist":    {o: round(ref_p, 4) for o in opts},
                "recent_dist": {o: round(r_dist.get(o, 0), 4) for o in opts},
                "drift_score": drift_score,
                "drift_level": _level(drift_score, 0.15, 0.30),
                "n_recent":    len(vals),
            })

    overall = max((f["drift_score"] for f in features), default=0.0)
    return {
        "n_recent":       n_recent,
        "overall_score":  round(overall, 4),
        "overall_level":  _level(overall, 0.35, 0.65),
        "baseline":       "training" if used_pipeline_baseline else "schema",
        "source":         "predictions",
        "features":       features,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_number(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def _level(score: float, med_thresh: float, high_thresh: float) -> str:
    if score >= high_thresh:
        return "high"
    if score >= med_thresh:
        return "medium"
    return "low"
