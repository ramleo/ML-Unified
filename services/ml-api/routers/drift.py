from collections import defaultdict, deque

import numpy as np
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/drift", tags=["drift"])

# Rolling buffer: model_id -> deque of raw input dicts (last 200 predictions)
_recent: dict[str, deque] = defaultdict(lambda: deque(maxlen=200))


def record_input(model_id: str, fields: dict) -> None:
    """Called by /predict to log the raw input for drift tracking."""
    _recent[model_id].append(fields)


@router.get("/{model_id}")
def get_drift(model_id: str):
    from app import MODELS  # noqa: PLC0415 — avoid circular import

    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")

    schema = MODELS[model_id]["schema"]
    recent = list(_recent[model_id])
    n_recent = len(recent)

    skip = set(schema.get("id_cols", [])) | set(schema.get("ensure_cols", []))
    features = []

    for field in schema.get("fields", []):
        name = field["name"]
        if name in skip:
            continue

        ftype = field.get("type")

        if ftype == "number":
            fmin = float(field.get("min", 0))
            fmax = float(field.get("max", 1))
            ref_mean = (fmin + fmax) / 2
            # 3σ spans the full range → σ = range/6
            ref_std = max((fmax - fmin) / 6, 1e-9)

            vals = [
                float(r[name])
                for r in recent
                if name in r and r[name] is not None
            ]
            if vals:
                r_mean = float(np.mean(vals))
                r_std = float(np.std(vals)) if len(vals) > 1 else 0.0
                z = abs(r_mean - ref_mean) / ref_std
                drift_score = round(min(1.0, z / 3), 4)  # saturates at 3σ
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
            opts = [o["value"] for o in field.get("options", [])]
            n_opts = len(opts)
            if n_opts == 0:
                continue
            ref_p = 1.0 / n_opts  # uniform baseline

            vals = [r[name] for r in recent if name in r and r[name] is not None]
            if vals:
                counts = {o: vals.count(o) for o in opts}
                r_dist = {o: counts[o] / len(vals) for o in opts}
                # mean absolute deviation from uniform
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
        "n_recent":      n_recent,
        "overall_score": round(overall, 4),
        "overall_level": _level(overall, 0.35, 0.65),
        "baseline":      "schema",
        "features":      features,
    }


def _level(score: float, med_thresh: float, high_thresh: float) -> str:
    if score >= high_thresh:
        return "high"
    if score >= med_thresh:
        return "medium"
    return "low"
