import io
import traceback

import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sklearn.base import is_classifier
from shared.progress import StreamingTask
from routers.core.shared import coerce_numeric

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

    df = coerce_numeric(df)
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
    """Run the best available SHAP explainer and return (shap_1d, base_value).

    Tries TreeExplainer first (fast, exact for ensembles), then LinearExplainer
    (for LogisticRegression / LinearSVC etc.), then errors out clearly.

    Handles the three output shapes that shap >= 0.40 can return:
      - list of (n_samples, n_features) arrays — one per class (older behaviour)
      - ndarray (n_samples, n_features, n_classes) — 3-D, newer classifiers
      - ndarray (n_samples, n_features) — regression or single-output
    """
    import shap  # lazy import — keeps startup fast on Render free tier

    # Convert sparse to dense (some externally-trained pipelines use sparse OHE)
    if hasattr(X_prep, "toarray"):
        X_prep = X_prep.toarray()

    try:
        explainer = shap.TreeExplainer(model)
    except Exception:
        # Fall back to LinearExplainer for linear models (LogisticRegression, Ridge, etc.)
        try:
            explainer = shap.LinearExplainer(model, np.zeros_like(X_prep))
        except Exception as exc:
            raise ValueError(f"No suitable SHAP explainer for {type(model).__name__}: {exc}") from exc

    try:
        sv = explainer.shap_values(X_prep, check_additivity=False)
    except Exception:
        # Interventional perturbation avoids the additivity issue for tree ensembles (e.g. RF)
        explainer = shap.TreeExplainer(model, feature_perturbation="interventional",
                                       data=X_prep)
        sv = explainer.shap_values(X_prep, check_additivity=False)
    ev = explainer.expected_value

    if task == "classification":
        if isinstance(sv, list):
            # Old format: list[class] of (n_samples, n_features)
            idx = pred_class if (pred_class is not None and pred_class < len(sv)) else 0
            shap_1d = np.asarray(sv[idx]).ravel()[:X_prep.shape[1]]
            ev_arr = np.asarray(ev).ravel()
            base = float(ev_arr[idx]) if idx < ev_arr.size else float(ev_arr[0])
        else:
            sv_arr = np.asarray(sv)
            ev_arr = np.asarray(ev).ravel()
            if sv_arr.ndim == 3:
                # Could be (n_samples, n_features, n_classes) or (n_classes, n_samples, n_features)
                if sv_arr.shape[0] == X_prep.shape[0]:
                    n_cls = sv_arr.shape[2]
                    idx = pred_class if (pred_class is not None and pred_class < n_cls) else n_cls - 1
                    shap_1d = sv_arr[0, :, idx]
                else:
                    n_cls = sv_arr.shape[0]
                    idx = pred_class if (pred_class is not None and pred_class < n_cls) else n_cls - 1
                    shap_1d = sv_arr[idx, 0, :]
                base = float(ev_arr[idx]) if idx < ev_arr.size else float(ev_arr[0])
            else:
                # 2-D (n_samples, n_features) — binary, values for class 1
                shap_1d = sv_arr[0]
                base = float(ev_arr[0]) if ev_arr.size > 0 else 0.0
    else:
        sv_arr = np.asarray(sv)
        shap_1d = sv_arr[0] if sv_arr.ndim == 2 else sv_arr.ravel()
        base = float(np.asarray(ev).flat[0])

    return np.asarray(shap_1d, dtype=float).ravel(), base


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

    data        = await request.json()
    model_params = data.get("model_params")  # dict or None — tuned params from Optuna
    df          = _prep_df(data, schema)

    _m           = m
    _schema      = schema
    _data        = data
    _df          = df
    _model_params = model_params

    task = StreamingTask()

    def _work(p):
        try:
            p.update(10, "Preprocessing features…")
            preprocessor, model = _extract(_m["pipeline"])
            _df_fe = _df.copy()
            _fe = _m.get("fe")
            if _fe is not None and _fe.fe_config:
                try:
                    _pre_fe = _schema.get("pre_fe_cols")
                    if _pre_fe:
                        _pfs = _schema.get("pre_fe_sample", {})
                        for _c in _pre_fe:
                            if _c not in _df_fe.columns:
                                _df_fe[_c] = _pfs.get(_c, float("nan"))
                        _df_fe = _df_fe[[c for c in _pre_fe if c in _df_fe.columns]]
                    _df_fe = _fe.transform(_df_fe)
                except Exception as _fe_err:
                    print(f"FE transform in SHAP failed (skipped): {_fe_err}", flush=True)
            X_prep = preprocessor.transform(_df_fe)
            feat_names_out = _feature_names(preprocessor, X_prep.shape[1])

            pred_class = None
            if _schema["task"] == "classification":
                pred_class = int(model.predict(X_prep)[0])

            p.update(30, "Computing SHAP values…")
            shap_1d, base_value = _compute(model, X_prep, _schema["task"], pred_class)

            p.update(88, "Aggregating feature importance…")
            orig_fields  = [f["name"]  for f in _schema.get("fields", [])]
            field_labels = {f["name"]: f.get("label", f["name"]) for f in _schema.get("fields", [])}
            result = _build_response(shap_1d, base_value, feat_names_out, orig_fields, field_labels, _data, _schema["task"], pred_class)
            if _model_params:
                result["used_params"] = _model_params
            p.finish(result=result)

        except Exception as exc:
            traceback.print_exc()
            p.finish(error=f"SHAP computation failed: {exc}")

    return StreamingResponse(
        task.stream(_work),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
