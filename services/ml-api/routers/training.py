import numpy as np
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/training", tags=["training"])


def _feat_names(preprocessor, n: int) -> list[str]:
    try:
        return list(preprocessor.get_feature_names_out())
    except Exception:
        return [f"f{i}" for i in range(n)]


def _aggregate(values: np.ndarray, feat_names_out: list[str], orig_fields: list[str]) -> dict[str, float]:
    agg: dict[str, float] = {f: 0.0 for f in orig_fields}
    for i, fname in enumerate(feat_names_out):
        col_part = fname.split("__", 1)[1] if "__" in fname else fname
        for orig in orig_fields:
            if col_part == orig or col_part.startswith(orig + "_"):
                agg[orig] += float(values[i])
                break
    return agg


def _build_importances(values: np.ndarray, preprocessor, orig_fields: list[str], field_labels: dict) -> list[dict]:
    names = _feat_names(preprocessor, len(values))
    agg = _aggregate(values, names, orig_fields)
    total = sum(agg.values()) or 1.0
    return sorted(
        [
            {
                "name":       f,
                "label":      field_labels.get(f, f),
                "importance": round(agg[f] / total, 4),
            }
            for f in orig_fields
        ],
        key=lambda x: x["importance"],
        reverse=True,
    )


@router.get("/{model_id}")
def get_training(model_id: str):
    from app import MODELS  # lazy — avoids circular import at load time

    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")

    m            = MODELS[model_id]
    pipeline     = m["pipeline"]
    schema       = m["schema"]
    estimator    = pipeline.steps[-1][1]
    preprocessor = pipeline[:-1]

    orig_fields  = [f["name"]                    for f in schema.get("fields", [])]
    field_labels = {f["name"]: f.get("label", f["name"]) for f in schema.get("fields", [])}

    # Feature importances — tree models use feature_importances_; LogReg uses |coef_|
    feature_importances = None
    if hasattr(estimator, "feature_importances_"):
        fi = np.asarray(estimator.feature_importances_)
        feature_importances = _build_importances(fi, preprocessor, orig_fields, field_labels)
    elif hasattr(estimator, "coef_"):
        coef = np.abs(np.asarray(estimator.coef_))
        if coef.ndim == 2:
            coef = coef.mean(axis=0)
        feature_importances = _build_importances(coef, preprocessor, orig_fields, field_labels)

    # Training loss curve — only GradientBoosting stores train_score_ per iteration
    training_curve = None
    if hasattr(estimator, "train_score_"):
        ts = np.asarray(estimator.train_score_)
        n  = len(ts)
        if n > 50:
            indices = [int(i * (n - 1) / 49) for i in range(50)]
            sampled = [round(float(ts[i]), 4) for i in indices]
        else:
            sampled = [round(float(v), 4) for v in ts]
        training_curve = {
            "values":       sampled,
            "n_estimators": n,
            "label":        "Training Deviance",
        }

    return {
        "model_id":            model_id,
        "algorithm":           type(estimator).__name__,
        "feature_importances": feature_importances,
        "training_curve":      training_curve,
    }
