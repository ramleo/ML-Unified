import io
import traceback

import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from sklearn.base import is_classifier

router = APIRouter(prefix="/shap", tags=["shap"])


def _prep_df(data: dict, schema: dict) -> pd.DataFrame:
    """Build the input DataFrame the same way /predict does."""
    row = dict(data)
    for col in schema.get("ensure_cols", []):
        row.setdefault(col, None)
    df = pd.DataFrame([row])
    for col in schema.get("id_cols", []):
        df[col] = float("nan")

    date_field = schema.get("date_field")
    if date_field:
        raw = data.get(date_field)
        psd = pd.to_datetime(raw, errors="coerce")
        df["psd_year"]        = None if pd.isnull(psd) else int(psd.year)
        df["psd_month"]       = None if pd.isnull(psd) else int(psd.month)
        df["psd_day"]         = None if pd.isnull(psd) else int(psd.day)
        df["psd_day_of_week"] = None if pd.isnull(psd) else int(psd.dayofweek)
        df = df.drop(columns=[date_field], errors="ignore")

    return df


def _extract(pipeline):
    """Return (preprocessor, final_estimator) from a sklearn Pipeline."""
    if not hasattr(pipeline, "steps") or len(pipeline.steps) < 2:
        raise ValueError("Expected a sklearn Pipeline with at least 2 steps")
    return pipeline[:-1], pipeline.steps[-1][1]


def _feature_names(preprocessor, n_cols: int) -> list[str]:
    try:
        return list(preprocessor.get_feature_names_out())
    except Exception:
        return [f"f{i}" for i in range(n_cols)]


def _aggregate(shap_1d: np.ndarray, feat_names_out: list[str], orig_fields: list[str]) -> dict[str, float]:
    """
    Sum OHE-expanded SHAP values back to original field names.

    ColumnTransformer prefixes names as 'num__col' or 'cat__col_val'.
    We strip the prefix then match on original field name or startswith(field + '_').
    """
    agg: dict[str, float] = {f: 0.0 for f in orig_fields}
    for i, fname in enumerate(feat_names_out):
        col_part = fname.split("__", 1)[1] if "__" in fname else fname
        for orig in orig_fields:
            if col_part == orig or col_part.startswith(orig + "_"):
                agg[orig] += float(shap_1d[i])
                break
    return agg


def _compute(model, X_prep: np.ndarray, task: str, pred_class: int | None):
    """Run TreeExplainer and return (shap_1d, base_value)."""
    import shap  # lazy import — keeps startup fast on Render free tier

    explainer = shap.TreeExplainer(model)
    sv = explainer.shap_values(X_prep)
    ev = explainer.expected_value

    if task == "classification":
        if isinstance(sv, list):
            idx = pred_class if pred_class is not None and pred_class < len(sv) else 0
            shap_1d = sv[idx][0]
            base = float(ev[idx]) if hasattr(ev, "__len__") else float(ev)
        else:
            shap_1d = sv[0]
            base = float(ev)
    else:
        shap_1d = sv[0] if sv.ndim == 2 else sv
        base = float(ev)

    return np.asarray(shap_1d, dtype=float), base


def _build_response(shap_1d, base_value, feat_names_out, orig_fields, field_labels, input_values, task, pred_class):
    agg = _aggregate(shap_1d, feat_names_out, orig_fields)
    features = [
        {
            "name":  f,
            "label": field_labels.get(f, f),
            "value": input_values.get(f),
            "shap":  round(agg.get(f, 0.0), 4),
        }
        for f in orig_fields
    ]
    features.sort(key=lambda x: abs(x["shap"]), reverse=True)
    return {
        "base_value": round(base_value, 4),
        "features":   features,
        "task":       task,
        "pred_class": pred_class,
    }


# ── /shap/{model_id} ─────────────────────────────────────────────────────────

@router.post("/{model_id}")
async def compute_shap(model_id: str, request: Request):
    from app import MODELS  # imported here to avoid circular import at module load

    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")

    m      = MODELS[model_id]
    schema = m["schema"]

    if schema["task"] == "clustering":
        raise HTTPException(400, "SHAP is not available for unsupervised models")

    data = await request.json()
    df   = _prep_df(data, schema)

    try:
        preprocessor, model = _extract(m["pipeline"])
        X_prep = preprocessor.transform(df)
        feat_names_out = _feature_names(preprocessor, X_prep.shape[1])

        pred_class = None
        if schema["task"] == "classification":
            pred_class = int(model.predict(X_prep)[0])

        shap_1d, base_value = _compute(model, X_prep, schema["task"], pred_class)

        orig_fields  = [f["name"]  for f in schema.get("fields", [])]
        field_labels = {f["name"]: f.get("label", f["name"]) for f in schema.get("fields", [])}

        return _build_response(shap_1d, base_value, feat_names_out, orig_fields, field_labels, data, schema["task"], pred_class)

    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(500, f"SHAP computation failed: {exc}")


# ── /shap/custom/upload ──────────────────────────────────────────────────────

@router.post("/custom/upload")
async def compute_shap_custom(
    model_file: UploadFile = File(...),
    data_file:  UploadFile = File(...),
):
    """
    Compute SHAP for a user-uploaded sklearn Pipeline (.pkl) and a single-row CSV.
    """
    try:
        pipeline = joblib.load(io.BytesIO(await model_file.read()))
    except Exception as exc:
        raise HTTPException(400, f"Could not load model file: {exc}")

    try:
        df = pd.read_csv(io.BytesIO(await data_file.read()))
        if df.empty:
            raise HTTPException(400, "CSV has no data rows")
        df = df.head(1)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Could not parse CSV: {exc}")

    try:
        preprocessor, model = _extract(pipeline)
        X_prep = preprocessor.transform(df)
        feat_names_out = _feature_names(preprocessor, X_prep.shape[1])

        task = "classification" if is_classifier(model) else "regression"
        pred_class = None
        if task == "classification":
            try:
                pred_class = int(model.predict(X_prep)[0])
            except Exception:
                pred_class = 0

        shap_1d, base_value = _compute(model, X_prep, task, pred_class)

        orig_fields = df.columns.tolist()
        return _build_response(shap_1d, base_value, feat_names_out, orig_fields, {}, df.iloc[0].to_dict(), task, pred_class)

    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(500, f"SHAP computation failed: {exc}")
