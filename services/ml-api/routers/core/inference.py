"""Inference router: /predict/{model_id}, /analyze, /explain endpoints."""
import io
import os

import pandas as pd
from fastapi import APIRouter, HTTPException, Request, UploadFile, File

from routers.core.shared import MODELS, ACCENT_PALETTE
from routers.core.automl_helpers import _llm_explanation, _rule_explanation
from routers import drift as _drift_router

router = APIRouter()


@router.post("/predict/{model_id}")
async def predict(model_id: str, request: Request):
    data = await request.json()
    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")

    m      = MODELS[model_id]
    schema = m["schema"]
    row    = dict(data)

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

    df = df.apply(pd.to_numeric, errors='ignore')

    pipeline = m["pipeline"]
    le       = m["le"]
    fe = m.get("fe")
    if fe is not None and fe.fe_config:
        try:
            pre_fe = schema.get("pre_fe_cols")
            if pre_fe:
                _pfs = schema.get("pre_fe_sample", {})
                for _c in pre_fe:
                    if _c not in df.columns:
                        df[_c] = _pfs.get(_c, float("nan"))
                df = df[[c for c in pre_fe if c in df.columns]]
            df = fe.transform(df)
        except Exception as _fe_pred_err:
            print(f"FE transform in predict failed (skipped): {_fe_pred_err}", flush=True)

    _drift_router.record_input(model_id, dict(data))

    if schema["task"] == "classification":
        pred  = pipeline.predict(df)[0]
        label = le.inverse_transform([pred])[0]
        proba = pipeline.predict_proba(df)[0].tolist()
        return {
            "prediction":  str(label),
            "probabilities": proba,
            "classes":     m["classes"],
            "class_names": schema.get("output", {}).get("class_names"),
        }
    elif schema["task"] == "clustering":
        algo = schema.get("model", "K-Means")
        if algo in ("t-SNE", "PCA"):
            return {"prediction": -1, "cluster_label": "Visualization only", "n_clusters": "N/A"}
        try:
            cluster = int(pipeline.predict(df)[0])
        except Exception:
            cluster = -1
        label = "Noise" if cluster == -1 else f"Cluster {cluster + 1}"
        return {
            "prediction":    cluster,
            "cluster_label": label,
            "n_clusters":    schema.get("output", {}).get("n_clusters", "?"),
        }
    else:
        pred = float(pipeline.predict(df)[0])
        return {"prediction": pred}


@router.post("/analyze")
async def analyze_csv(file: UploadFile = File(...)):
    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")
    if len(df.columns) < 2:
        raise HTTPException(400, "CSV must have at least 2 columns")

    columns = []
    for col in df.columns:
        is_num = bool(pd.api.types.is_numeric_dtype(df[col]))
        col_info = {
            "name":       col,
            "dtype":      str(df[col].dtype),
            "nunique":    int(df[col].nunique()),
            "is_numeric": is_num,
            "missing":    int(df[col].isna().sum()),
        }
        if is_num:
            vals = df[col].dropna()
            if len(vals) > 1:
                col_info["std"]  = float(vals.std())
                col_info["mean"] = float(vals.mean())
                col_info["min"]  = float(vals.min())
                col_info["max"]  = float(vals.max())
                try:
                    col_info["skew"] = float(vals.skew())
                except Exception:
                    col_info["skew"] = 0.0
        columns.append(col_info)

    suggested_target = df.columns[-1]
    t = df[suggested_target]
    suggested_task = (
        "classification"
        if (not pd.api.types.is_numeric_dtype(t) or t.nunique() <= 10)
        else "regression"
    )

    total_missing = int(df.isna().sum().sum())

    return {
        "columns":          columns,
        "suggested_target": suggested_target,
        "suggested_task":   suggested_task,
        "rows":             len(df),
        "accent_palette":   ACCENT_PALETTE,
        "total_missing":    total_missing,
    }


@router.post("/explain")
async def explain_automl(request: Request):
    """Generate an LLM explanation for an AutoML result."""
    body            = await request.json()
    automl          = body.get("automl_data", {})
    user_key        = (body.get("user_api_key") or "").strip()
    provider        = (body.get("provider") or "gemini-2.5").strip().lower()
    custom_base_url = (body.get("custom_base_url") or "").strip()
    custom_model    = (body.get("custom_model") or "").strip()

    if not user_key:
        _server_keys = {
            "gemini-2.5": os.environ.get("GEMINI_API_KEY", ""),
            "gemini-3.5": os.environ.get("GEMINI_API_KEY", ""),
            "anthropic":  os.environ.get("ANTHROPIC_API_KEY", ""),
            "openai":     os.environ.get("OPENAI_API_KEY", ""),
            "groq":         os.environ.get("GROQ_API_KEY", ""),
            "groq-mixtral": os.environ.get("GROQ_API_KEY", ""),
        }
        user_key = _server_keys.get(provider, "")

    winner     = automl.get("winner", "")
    cv_results = automl.get("cv_results", [])
    task       = automl.get("task", "classification")
    sel_metric = automl.get("selection_metric", "Accuracy")
    is_imbal   = automl.get("is_imbalanced", False)
    feat_imp   = automl.get("feature_importance", [])
    n_rows     = automl.get("n_rows", 0)

    llm_error: str | None = None
    if user_key:
        try:
            llm_exp = _llm_explanation(user_key, winner, cv_results, task,
                                       sel_metric, is_imbal, feat_imp, n_rows, provider,
                                       custom_base_url, custom_model)
        except Exception as e:
            llm_exp = None
            llm_error = str(e)
        if llm_exp:
            return {"explanation": llm_exp, "source": provider}

    rule_exp = _rule_explanation(winner, cv_results, task, sel_metric,
                                 is_imbal, feat_imp, n_rows)
    return {
        "explanation": {"why_won": rule_exp, "score_analysis": "", "key_dirs": "", "recommendations": []},
        "source": "rule",
        **({"llm_error": llm_error} if llm_error else {}),
    }


@router.get("/models/{model_id}/export")
def export_model(model_id: str):
    """Download the trained sklearn pipeline as a .pkl file."""
    import joblib
    from fastapi.responses import StreamingResponse

    if model_id not in MODELS:
        raise HTTPException(status_code=404, detail="Model not found")

    pipeline = MODELS[model_id].get("pipeline")
    if pipeline is None:
        raise HTTPException(status_code=404, detail="No pipeline stored for this model")

    buf = io.BytesIO()
    joblib.dump(pipeline, buf)
    buf.seek(0)

    filename = f"{model_id}_pipeline.pkl"
    return StreamingResponse(
        buf,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
