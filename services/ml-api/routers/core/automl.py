"""AutoML router: /automl/preprocess, /train, /feature-engineer endpoints."""
import base64
import io
import json

import pandas as pd
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sklearn.preprocessing import StandardScaler

from routers.core.shared import (
    MODELS, SCHEMA_DIR, MODEL_DIR, slugify, _upload_model_to_hf, _detect_gpu, ACCENT_PALETTE,
)
from routers.core.automl_helpers import FeatureEngineeringTransformer
from routers.core.automl_train_work import build_work_fn
from routers.core.automl_preprocess_helpers import (
    apply_imputation, apply_encoding, apply_feature_selection, build_cat_transformers,
)
from shared.progress import StreamingTask
from routers.core import automl_fe as _fe_router
from routers.core import automl_optuna_explain as _optuna_exp_router
from security.file_gate import scan_upload_bytes

router = APIRouter()
# Mount /feature-engineer from its own module
router.include_router(_fe_router.router)
router.include_router(_optuna_exp_router.router)


@router.post("/automl/preprocess")
async def automl_preprocess(request: Request):
    """Preprocess an uploaded AutoML CSV in-memory and return the result."""
    import numpy as _np  # noqa: PLC0415

    body = await request.json()
    filename      = body.get("filename", "")
    options       = body.get("options", {})
    target_column = body.get("target_column", "")
    fe_config_prep = body.get("fe_config", {})

    csv_b64 = body.get("csv_b64", "")
    if not csv_b64:
        raise HTTPException(400, "csv_b64 is required")

    try:
        csv_bytes = base64.b64decode(csv_b64)
        scan_upload_bytes(csv_bytes, path="/automl/preprocess")
        df = pd.read_csv(io.BytesIO(csv_bytes))
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")

    bool_cols = df.select_dtypes(include="bool").columns.tolist()
    if bool_cols:
        df[bool_cols] = df[bool_cols].astype(_np.int8)

    rows_before = len(df)
    cols_before = len(df.columns)

    feature_cols = [c for c in df.columns if c != target_column]
    target_series = df[target_column] if target_column and target_column in df.columns else None
    df_feat = df[feature_cols].copy()

    # 0. Drop user-selected columns
    drop_cols = [c for c in (options.get("drop_columns") or []) if c in df_feat.columns]
    user_cols_dropped = len(drop_cols)
    if drop_cols:
        df_feat = df_feat.drop(columns=drop_cols)

    # 0b. Remove duplicate rows
    if options.get("remove_duplicates"):
        df_feat = df_feat.drop_duplicates()
        if target_series is not None:
            target_series = target_series.loc[df_feat.index]

    num_cols = df_feat.select_dtypes(include="number").columns.tolist()
    cat_cols = df_feat.select_dtypes(exclude="number").columns.tolist()

    # 1. Missing value imputation
    old_mv = options.get("missing_values")
    mv_num = options.get("mv_num") or old_mv
    mv_cat = options.get("mv_cat") or (
        "most_frequent" if old_mv in ("mean", "median", "knn", "mice") else old_mv
    )
    df_feat, target_series, cat_cols = apply_imputation(
        df_feat, target_series, mv_num, mv_cat, num_cols, cat_cols
    )

    # 2. Remove outliers (IQR)
    if options.get("remove_outliers") and num_cols:
        mask = pd.Series([True] * len(df_feat), index=df_feat.index)
        for c in num_cols:
            q1 = df_feat[c].quantile(0.25)
            q3 = df_feat[c].quantile(0.75)
            iqr = q3 - q1
            mask &= (df_feat[c] >= q1 - 1.5 * iqr) & (df_feat[c] <= q3 + 1.5 * iqr)
        df_feat = df_feat[mask]
        if target_series is not None:
            target_series = target_series.loc[df_feat.index]

    num_cols = df_feat.select_dtypes(include="number").columns.tolist()
    cat_cols = df_feat.select_dtypes(exclude="number").columns.tolist()

    # 3. Fix skewness
    if options.get("fix_skewness") and num_cols:
        import numpy as _np2  # noqa: PLC0415
        for c in num_cols:
            if df_feat[c].min() >= 0:
                try:
                    if abs(float(df_feat[c].skew())) > 0.75:
                        df_feat[c] = _np2.log1p(df_feat[c])
                except Exception:
                    pass

    # 4. Categorical encoding
    encode_method = options.get("encode_method")
    if encode_method is None:
        if options.get("encode_nominal"):
            encode_method = "onehot"
        elif options.get("encode_ordinal"):
            encode_method = "ordinal"
        else:
            encode_method = "none"

    ordinal_cols = options.get("ordinal_columns", [])
    df_feat, ohe_cols_added = apply_encoding(
        df_feat, cat_cols, encode_method, ordinal_cols, target_series, _np
    )

    # 5. Standardize numeric features
    final_num_cols = df_feat.select_dtypes(include="number").columns.tolist()
    if options.get("standardize") and final_num_cols:
        df_feat[final_num_cols] = StandardScaler().fit_transform(df_feat[final_num_cols])

    # 6. Feature engineering
    pre_fe_cols = list(df_feat.columns)
    _pre_fe_sample_out: dict = {}
    for _pfc in pre_fe_cols:
        if pd.api.types.is_numeric_dtype(df_feat[_pfc]):
            _pre_fe_sample_out[_pfc] = round(float(df_feat[_pfc].median()), 4)
        else:
            _m = df_feat[_pfc].mode()
            _pre_fe_sample_out[_pfc] = str(_m[0]) if not _m.empty else ""
    fe_cols_added = 0
    fe_b64_out    = ""
    _fe_tfm_prep  = FeatureEngineeringTransformer(fe_config_prep)
    if fe_config_prep:
        try:
            df_feat = _fe_tfm_prep.fit_transform(df_feat)
            _fe_bool = df_feat.select_dtypes(include="bool").columns.tolist()
            if _fe_bool:
                df_feat[_fe_bool] = df_feat[_fe_bool].astype(_np.int8)
            fe_cols_added = len(df_feat.columns) - len(pre_fe_cols)
            import joblib as _jl  # noqa: PLC0415
            _fe_buf = io.BytesIO()
            _jl.dump(_fe_tfm_prep, _fe_buf)
            fe_b64_out = base64.b64encode(_fe_buf.getvalue()).decode()
        except Exception as _fe_prep_err:
            print(f"FE in preprocess failed (skipped): {_fe_prep_err}", flush=True)
            _fe_tfm_prep = FeatureEngineeringTransformer({})
            fe_cols_added = 0
            fe_b64_out    = ""

    # 7. Feature selection
    features_before = len(df_feat.columns)
    fs = options.get("feature_selection", {})
    fs_method = (fs.get("method") or "none").lower()
    top_k = max(1, int(fs.get("top_k") or 10))
    if fs_method != "none":
        df_feat = apply_feature_selection(df_feat, target_series, fs_method, top_k)
    features_after = len(df_feat.columns)

    # Recombine with target
    if target_series is not None:
        df_out = df_feat.copy()
        df_out[target_column] = target_series.reindex(df_feat.index).values
    else:
        df_out = df_feat.copy()

    rows_after = len(df_out)
    cols_after = len(df_out.columns)

    csv_buf = io.StringIO()
    df_out.to_csv(csv_buf, index=False)
    csv_b64_out = base64.b64encode(csv_buf.getvalue().encode()).decode()

    columns_out = _build_column_analysis(df_out)
    suggested_target = target_column if target_column and target_column in df_out.columns else df_out.columns[-1]
    t2 = df_out[suggested_target]
    suggested_task = (
        "classification"
        if (not pd.api.types.is_numeric_dtype(t2) or t2.nunique() <= 10)
        else "regression"
    )
    preprocessed_filename = (
        filename.rsplit(".", 1)[0] + "_preprocessed.csv"
        if "." in filename else filename + "_preprocessed.csv"
    )
    return {
        "csv_b64": csv_b64_out, "preprocessed_filename": preprocessed_filename,
        "rows_before": rows_before, "rows_after": rows_after,
        "cols_before": cols_before, "cols_after": cols_after,
        "features_before": features_before, "features_after": features_after,
        "user_cols_dropped": user_cols_dropped, "ohe_cols_added": ohe_cols_added,
        "fe_cols_added": fe_cols_added, "fe_b64": fe_b64_out,
        "pre_fe_cols": pre_fe_cols, "pre_fe_sample": _pre_fe_sample_out,
        "columns": columns_out, "suggested_target": suggested_target,
        "suggested_task": suggested_task, "rows": rows_after,
        "accent_palette": ACCENT_PALETTE, "total_missing": int(df_out.isna().sum().sum()),
    }


def _build_column_analysis(df_out):
    columns_out = []
    for col in df_out.columns:
        is_num = bool(pd.api.types.is_numeric_dtype(df_out[col]))
        col_info = {"name": col, "dtype": str(df_out[col].dtype), "nunique": int(df_out[col].nunique()),
                    "is_numeric": is_num, "missing": int(df_out[col].isna().sum())}
        if is_num:
            vals = df_out[col].dropna()
            if len(vals) > 1:
                col_info["std"]  = float(vals.std())
                col_info["mean"] = float(vals.mean())
                col_info["min"]  = float(vals.min())
                col_info["max"]  = float(vals.max())
                try:
                    col_info["skew"] = float(vals.skew())
                except Exception:
                    col_info["skew"] = 0.0
        columns_out.append(col_info)
    return columns_out


@router.post("/train")
async def train_model(
    file:                UploadFile = File(...),
    model_name:          str        = Form(...),
    target_col:          str        = Form(""),
    task:                str        = Form(...),
    algorithm:           str        = Form(...),
    accent:              str        = Form(...),
    n_clusters:          int        = Form(3),
    feature_engineering: str        = Form("{}"),
    fe_b64:              str        = Form(""),
    pre_fe_cols_json:    str        = Form("[]"),
    pre_fe_sample_json:  str        = Form("{}"),
    tune:                str        = Form("false"),
    n_trials:            int        = Form(10),
    selected_models:     str        = Form('["Random Forest","XGBoost","LightGBM","CatBoost","Extra Trees"]'),
    use_smote:           str        = Form("true"),
    drop_cols_json:      str        = Form("[]"),
    opt_metric:          str        = Form("auto"),
    sampler:             str        = Form("tpe"),
    secondary_metric:    str        = Form("none"),
    col_encoding_json:   str        = Form("{}"),
    preset_params_json:  str        = Form("{}"),
):
    import joblib as _jl  # noqa: PLC0415
    from sklearn.compose import ColumnTransformer as _CT  # noqa: PLC0415
    from sklearn.impute import SimpleImputer as _SI  # noqa: PLC0415
    from sklearn.pipeline import Pipeline as _PL  # noqa: PLC0415
    from sklearn.preprocessing import OneHotEncoder as _OHE, StandardScaler as _SS  # noqa: PLC0415

    _tune     = tune.lower()     in ("true", "1", "yes") if isinstance(tune, str)     else bool(tune)
    _use_smote = use_smote.lower() in ("true", "1", "yes") if isinstance(use_smote, str) else bool(use_smote)
    tune      = _tune
    use_smote = _use_smote

    content = await file.read()
    scan_upload_bytes(content, path="/train")
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")

    if task not in ("classification", "regression", "clustering"):
        raise HTTPException(400, "task must be 'classification', 'regression', or 'clustering'")
    if task != "clustering" and target_col not in df.columns:
        raise HTTPException(400, f"Target column '{target_col}' not found")

    model_id = slugify(model_name)
    if not model_id:
        raise HTTPException(400, "Invalid model name — use letters, numbers, or spaces")

    try:
        _preset_params: dict = json.loads(preset_params_json or "{}")
    except Exception:
        _preset_params = {}
    try: _fe_config = json.loads(feature_engineering or "{}")
    except Exception: _fe_config = {}
    try:
        _pre_fe_cols_from_prep = json.loads(pre_fe_cols_json or "[]")
    except Exception:
        _pre_fe_cols_from_prep = []
    try:
        _pre_fe_sample: dict = json.loads(pre_fe_sample_json or "{}")
    except Exception:
        _pre_fe_sample = {}

    if task == "clustering":
        X = df.copy()
        y = None
    else:
        df = df.dropna(subset=[target_col])
        X = df.drop(columns=[target_col]).copy()
        y = df[target_col]

    id_like = [c for c in X.columns if X[c].dtype == object and X[c].nunique() == len(X)]
    if id_like:
        X = X.drop(columns=id_like)

    _bool_cols = X.select_dtypes(include="bool").columns.tolist()
    if _bool_cols:
        X = X.copy()
        X[_bool_cols] = X[_bool_cols].astype("int8")

    if fe_b64:
        _fe_transformer = _jl.load(io.BytesIO(base64.b64decode(fe_b64)))
        _pre_fe_cols    = _pre_fe_cols_from_prep or list(X.columns)
    else:
        _pre_fe_cols    = list(X.columns)
        for _pfc in _pre_fe_cols:
            if pd.api.types.is_numeric_dtype(X[_pfc]):
                _pre_fe_sample[_pfc] = round(float(X[_pfc].median()), 4)
            else:
                _m = X[_pfc].mode()
                _pre_fe_sample[_pfc] = str(_m[0]) if not _m.empty else ""
        _fe_transformer = FeatureEngineeringTransformer(_fe_config)
        if _fe_config:
            try:
                X = _fe_transformer.fit_transform(X)
                _new_bool = X.select_dtypes(include="bool").columns.tolist()
                if _new_bool:
                    X[_new_bool] = X[_new_bool].astype("int8")
            except Exception as _fe_err:
                print(f"Feature engineering failed (skipped): {_fe_err}", flush=True)
                _fe_transformer = FeatureEngineeringTransformer({})

    # Drop user-selected columns
    try:
        _user_drop = [c for c in json.loads(drop_cols_json or "[]") if c in X.columns]
    except Exception:
        _user_drop = []
    if _user_drop:
        X = X.drop(columns=_user_drop)

    num_cols = X.select_dtypes(include="number").columns.tolist()
    cat_cols = X.select_dtypes(exclude="number").columns.tolist()

    try:
        col_enc = json.loads(col_encoding_json or "{}")
    except Exception:
        col_enc = {}

    transformers = []
    if num_cols:
        transformers.append(("num", _PL([("imp", _SI(strategy="median")), ("scaler", _SS())]), num_cols))
    transformers.extend(build_cat_transformers(cat_cols, col_enc))

    if not transformers:
        raise HTTPException(400, "No usable feature columns found after cleaning")

    try:
        _selected_models = set(json.loads(selected_models))
    except Exception:
        _selected_models = {"Random Forest", "XGBoost", "LightGBM", "CatBoost", "Extra Trees",
                            "Decision Tree", "KNN", "Logistic Regression", "Ridge"}

    _n_trials = max(5, min(200, n_trials))
    streaming_task = StreamingTask()
    _work = build_work_fn(
        X=X, y=y, task=task, algorithm=algorithm, accent=accent,
        model_id=model_id, model_name=model_name, target_col=target_col,
        fe_transformer=_fe_transformer, pre_fe_cols=_pre_fe_cols, pre_fe_sample=_pre_fe_sample,
        n_clusters=n_clusters, tune=tune, n_trials=_n_trials,
        selected_models=_selected_models, num_cols=num_cols, cat_cols=cat_cols,
        transformers=transformers, use_smote=use_smote,
        opt_metric=opt_metric,
        sampler=sampler,
        secondary_metric=secondary_metric,
        preset_params=_preset_params,
    )
    return StreamingResponse(
        streaming_task.stream(_work),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/model/{model_id}/download")
async def download_model(model_id: str):
    from fastapi.responses import FileResponse
    import os
    pkl_path = os.path.join(MODEL_DIR, f"{model_id}_pipeline.pkl")
    if not os.path.exists(pkl_path):
        raise HTTPException(404, f"Model file not found for id: {model_id}")
    return FileResponse(
        path=pkl_path,
        media_type="application/octet-stream",
        filename=f"{model_id}_pipeline.pkl",
    )


# /feature-engineer is served by _fe_router (automl_fe.py)
