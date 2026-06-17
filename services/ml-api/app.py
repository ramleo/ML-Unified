#!/usr/bin/env python3
from contextlib import asynccontextmanager
from routers import shap as _shap_router
from routers import pipeline as _pipeline_router
from routers import training as _training_router
from routers import drift as _drift_router
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from shared.progress import StreamingTask
from fastapi.middleware.cors import CORSMiddleware
import collections
import time
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, LabelEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression, Ridge as RidgeRegressor, Lasso, ElasticNet
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.svm import SVC, SVR
from sklearn.naive_bayes import GaussianNB
from sklearn.ensemble import (RandomForestClassifier, GradientBoostingClassifier,
                               RandomForestRegressor, GradientBoostingRegressor,
                               ExtraTreesClassifier, ExtraTreesRegressor)
from sklearn.cluster import KMeans, DBSCAN
# xgboost, lightgbm, catboost are imported lazily inside train_model to save ~200 MB
# of shared-library memory at startup (critical on Render free tier 512 MB limit)
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold, KFold, learning_curve
from sklearn.base import clone, BaseEstimator, TransformerMixin
from sklearn.preprocessing import PowerTransformer
from sklearn.metrics import (accuracy_score, mean_absolute_error, mean_squared_error,
                             silhouette_score, f1_score, roc_auc_score, r2_score,
                             precision_score, recall_score, confusion_matrix as sk_confusion_matrix,
                             median_absolute_error, mean_absolute_percentage_error)
from typing import Any, Dict
import io
import joblib
import json
import os
import re
import pandas as pd

@asynccontextmanager
async def _lifespan(app: FastAPI):
    import threading
    def _bg():
        try:
            _fetch_hf_models()
            _load()
            print(f"Models loaded: {list(MODELS.keys())}", flush=True)
        except Exception as exc:
            import traceback
            print("ERROR: _load() failed:", exc, flush=True)
            traceback.print_exc()
    threading.Thread(target=_bg, daemon=True).start()
    yield  # server binds and accepts requests immediately; models load in background

app = FastAPI(title="ML API", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── GPU detection ─────────────────────────────────────────────────────────────
def _detect_gpu() -> dict:
    try:
        import torch
        if torch.cuda.is_available():
            return {"available": True, "name": torch.cuda.get_device_name(0)}
    except Exception:
        pass
    try:
        import subprocess
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=3,
        )
        if r.returncode == 0 and r.stdout.strip():
            return {"available": True, "name": r.stdout.strip().split("\n")[0]}
    except Exception:
        pass
    return {"available": False, "name": None}

# ── Request monitoring ────────────────────────────────────────────────────────
_SKIP_PATHS = {"/", "/health", "/metrics", "/app-config", "/favicon.ico", "/system-info"}
_req_log: collections.deque = collections.deque(maxlen=1000)
_svc_start = time.time()


@app.middleware("http")
async def _monitor(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    if request.url.path not in _SKIP_PATHS:
        _req_log.append({
            "ts":     time.time(),
            "path":   request.url.path,
            "method": request.method,
            "status": response.status_code,
            "ms":     ms,
        })
    return response


@app.get("/metrics")
def get_metrics():
    logs = list(_req_log)
    uptime_s = int(time.time() - _svc_start)
    if not logs:
        return {"service": "ml-api", "uptime_s": uptime_s,
                "total_requests": 0, "avg_ms": 0, "p95_ms": 0,
                "error_rate": 0.0, "endpoints": []}
    by_path: Dict[str, list] = collections.defaultdict(list)
    for r in logs:
        by_path[r["path"]].append(r)
    endpoints = []
    for path, reqs in sorted(by_path.items(), key=lambda x: -len(x[1])):
        times = sorted(r["ms"] for r in reqs)
        errs  = sum(1 for r in reqs if r["status"] >= 400)
        endpoints.append({
            "path":       path,
            "count":      len(reqs),
            "avg_ms":     round(sum(times) / len(times), 1),
            "p95_ms":     times[min(int(len(times) * 0.95), len(times) - 1)],
            "error_rate": round(errs / len(reqs) * 100, 1),
        })
    all_ms  = sorted(r["ms"] for r in logs)
    all_err = sum(1 for r in logs if r["status"] >= 400)
    return {
        "service":        "ml-api",
        "uptime_s":       uptime_s,
        "total_requests": len(logs),
        "avg_ms":         round(sum(all_ms) / len(all_ms), 1),
        "p95_ms":         all_ms[min(int(len(all_ms) * 0.95), len(all_ms) - 1)],
        "error_rate":     round(all_err / len(logs) * 100, 1),
        "endpoints":      endpoints,
    }

HERE       = os.path.dirname(os.path.abspath(__file__))
SCHEMA_DIR = os.path.join(HERE, "schemas")
MODEL_DIR  = os.path.join(HERE, "models")
FRONTEND   = os.path.join(HERE, "frontend", "index.html")

MODELS: Dict[str, Any] = {}

_BUILTIN_IDS: frozenset[str] = frozenset({"titanic", "iris", "diabetes", "insurance"})

ACCENT_PALETTE = [
    "#818cf8", "#38bdf8", "#34d399", "#fbbf24",
    "#f87171", "#fb923c", "#a78bfa", "#4ade80",
]

def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

_HF_SPACE_ID = "wram1708/ml-unified"
_HF_PKL_FILES = [
    "models/diabetes_pipeline.pkl",
    "models/diabetes_labels.pkl",
    "models/iris_pipeline.pkl",
    "models/iris_labels.pkl",
    "models/titanic_pipeline.pkl",
    "models/titanic_labels.pkl",
    "models/insurance_pipeline.pkl",
]

def _fetch_hf_models():
    """Download pkl files from HF Space XET storage if running on HuggingFace."""
    if not os.environ.get("SPACE_ID"):
        return  # only run inside HF Spaces
    try:
        from huggingface_hub import hf_hub_download
        import shutil
    except ImportError:
        print("huggingface_hub not available — skipping model download", flush=True)
        return
    os.makedirs(MODEL_DIR, exist_ok=True)
    token = os.environ.get("HF_TOKEN")
    # Fixed model pkls
    all_fpaths = list(_HF_PKL_FILES)
    # Also try to fetch _fe.pkl and _actuals.json for every user-trained model
    if os.path.isdir(SCHEMA_DIR):
        for _sf in os.listdir(SCHEMA_DIR):
            if _sf.endswith(".json"):
                _mid = _sf[:-5]
                if _mid in _BUILTIN_IDS:
                    continue  # built-ins never have FE or actuals files
                for _suffix in ("_fe.pkl", "_actuals.json"):
                    _extra = f"models/{_mid}{_suffix}"
                    if _extra not in all_fpaths:
                        all_fpaths.append(_extra)
    for fpath in all_fpaths:
        local = os.path.join(HERE, fpath)
        if os.path.exists(local):
            continue
        try:
            print(f"HF: downloading {fpath} ...", flush=True)
            cached = hf_hub_download(
                repo_id=_HF_SPACE_ID,
                repo_type="space",
                filename=fpath,
                token=token,
            )
            shutil.copy2(cached, local)
            print(f"HF: {fpath} ready", flush=True)
        except Exception as exc:
            print(f"HF: could not download {fpath}: {exc}", flush=True)


def _upload_model_to_hf(model_id: str) -> None:
    """Upload newly trained model files to HF Space XET storage for persistence across restarts."""
    if not os.environ.get("SPACE_ID"):
        return
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("HF: HF_TOKEN not set — trained model will not persist across restarts", flush=True)
        return
    try:
        from huggingface_hub import HfApi as _HfApi  # noqa: PLC0415
        _api = _HfApi()
        _files = [
            (os.path.join(MODEL_DIR, f"{model_id}_pipeline.pkl"), f"models/{model_id}_pipeline.pkl"),
            (os.path.join(MODEL_DIR, f"{model_id}_fe.pkl"),       f"models/{model_id}_fe.pkl"),
            (os.path.join(SCHEMA_DIR, f"{model_id}.json"),        f"schemas/{model_id}.json"),
        ]
        if os.path.exists(os.path.join(MODEL_DIR, f"{model_id}_labels.pkl")):
            _files.append((
                os.path.join(MODEL_DIR, f"{model_id}_labels.pkl"),
                f"models/{model_id}_labels.pkl",
            ))
        if os.path.exists(os.path.join(MODEL_DIR, f"{model_id}_actuals.json")):
            _files.append((
                os.path.join(MODEL_DIR, f"{model_id}_actuals.json"),
                f"models/{model_id}_actuals.json",
            ))
        for _local, _repo_path in _files:
            if not os.path.exists(_local):
                continue
            _api.upload_file(
                path_or_fileobj=_local,
                path_in_repo=_repo_path,
                repo_id=_HF_SPACE_ID,
                repo_type="space",
                token=token,
            )
            print(f"HF: uploaded {_repo_path}", flush=True)
    except Exception as _exc:
        print(f"HF: upload after train failed (non-fatal): {_exc}", flush=True)

def _load():
    for fname in sorted(os.listdir(SCHEMA_DIR)):
        if not fname.endswith(".json"):
            continue
        mid    = fname[:-5]
        schema = json.load(open(os.path.join(SCHEMA_DIR, fname)))
        pkl_path = os.path.join(MODEL_DIR, f"{mid}_pipeline.pkl")
        if not os.path.exists(pkl_path):
            continue
        pipeline = joblib.load(pkl_path)
        le_path  = os.path.join(MODEL_DIR, f"{mid}_labels.pkl")
        le       = joblib.load(le_path) if os.path.exists(le_path) else None
        _fe_pkl  = os.path.join(MODEL_DIR, f"{mid}_fe.pkl")
        _fe_loaded = joblib.load(_fe_pkl) if os.path.exists(_fe_pkl) else FeatureEngineeringTransformer({})
        _act_pkl = os.path.join(MODEL_DIR, f"{mid}_actuals.json")
        _actuals_loaded = json.load(open(_act_pkl)) if os.path.exists(_act_pkl) else None
        MODELS[mid] = {
            "pipeline": pipeline,
            "le":       le,
            "classes":  le.classes_.tolist() if le is not None else None,
            "schema":   schema,
            "fe":       _fe_loaded,
            "actuals":  _actuals_loaded,
        }

@app.get("/")
def index():
    if os.path.exists(FRONTEND):
        vision_url = os.environ.get("ML_VISION_URL", "").rstrip("/")
        eda_url    = os.environ.get("ML_EDA_URL", "").rstrip("/")
        with open(FRONTEND, encoding="utf-8") as f:
            html = f.read()
        html = html.replace("let VISION_API = '';", f"let VISION_API = '{vision_url}';", 1)
        html = html.replace("let EDA_API = '';",    f"let EDA_API = '{eda_url}';",       1)
        return HTMLResponse(
            html,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
    return {"message": "ML API — see /docs"}

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    path = os.path.join(HERE, "frontend", "favicon.ico")
    if os.path.exists(path):
        return FileResponse(path, media_type="image/x-icon")
    return HTMLResponse(status_code=204)

@app.get("/icon.svg", include_in_schema=False)
def favicon_svg():
    path = os.path.join(HERE, "frontend", "icon.svg")
    if os.path.exists(path):
        return FileResponse(path, media_type="image/svg+xml",
                            headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return HTMLResponse(status_code=204)

@app.get("/health")
def health():
    return {"status": "ok", "models": list(MODELS.keys())}

@app.get("/system-info")
def system_info():
    return {"gpu": _detect_gpu()}

@app.get("/app-config")
def app_config():
    """Return runtime config consumed by the frontend (e.g. vision service URL)."""
    return {
        "vision_url": os.environ.get("ML_VISION_URL", ""),
        "eda_url":    os.environ.get("ML_EDA_URL", ""),
    }

@app.get("/models")
def list_models():
    return [
        {
            "id":          mid,
            "title":       m["schema"]["title"],
            "description": m["schema"].get("description", ""),
            "task":        m["schema"]["task"],
            "accent":      m["schema"]["accent"],
            "model":       m["schema"]["model"],
            "metric":      m["schema"]["metric"],
            "metricLabel": m["schema"]["metricLabel"],
            "classes":     m["classes"],
            "class_names": m["schema"].get("output", {}).get("class_names"),
            "builtin":     mid in _BUILTIN_IDS,
        }
        for mid, m in MODELS.items()
    ]

@app.get("/schemas/{model_id}")
def get_schema(model_id: str):
    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")
    s = dict(MODELS[model_id]["schema"])
    s["classes"]     = MODELS[model_id]["classes"]
    s["class_names"] = s.get("output", {}).get("class_names")
    return s


def _delete_model_from_hf(model_id: str) -> None:
    if not os.environ.get("SPACE_ID"):
        return
    token = os.environ.get("HF_TOKEN")
    if not token:
        return
    try:
        from huggingface_hub import HfApi as _HfApi
        _api = _HfApi()
        _candidates = [
            f"models/{model_id}_pipeline.pkl",
            f"models/{model_id}_fe.pkl",
            f"models/{model_id}_labels.pkl",
            f"models/{model_id}_actuals.json",
            f"schemas/{model_id}.json",
        ]
        for _rpath in _candidates:
            try:
                _api.delete_file(
                    path_in_repo=_rpath,
                    repo_id=_HF_SPACE_ID,
                    repo_type="space",
                    token=token,
                )
            except Exception:
                pass
    except Exception as _exc:
        print(f"HF: delete failed (non-fatal): {_exc}", flush=True)


@app.delete("/models/{model_id}")
def delete_model(model_id: str):
    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")
    MODELS.pop(model_id)
    for fname in [
        f"{model_id}_pipeline.pkl",
        f"{model_id}_fe.pkl",
        f"{model_id}_labels.pkl",
        f"{model_id}_actuals.json",
    ]:
        _p = os.path.join(MODEL_DIR, fname)
        if os.path.exists(_p):
            os.remove(_p)
    _sp = os.path.join(SCHEMA_DIR, f"{model_id}.json")
    if os.path.exists(_sp):
        os.remove(_sp)
    _delete_model_from_hf(model_id)
    return {"deleted": model_id}


@app.get("/models/{model_id}/actuals")
def get_actuals(model_id: str):
    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")
    # Serve from in-memory cache first (populated right after training)
    _mem = MODELS[model_id].get("actuals")
    if _mem:
        return _mem
    # Fall back to file (for models loaded on startup)
    _path = os.path.join(MODEL_DIR, f"{model_id}_actuals.json")
    if not os.path.exists(_path):
        raise HTTPException(404, "No actuals data — retrain this model to generate it")
    with open(_path) as _f:
        data = json.load(_f)
    MODELS[model_id]["actuals"] = data  # cache for next call
    return data


@app.post("/predict/{model_id}")
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

@app.post("/analyze")
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
                # skewness
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


@app.post("/automl/preprocess")
async def automl_preprocess(request: Request):
    """Preprocess an uploaded AutoML CSV in-memory and return the result."""
    import numpy as _np  # noqa: PLC0415
    import base64  # noqa: PLC0415

    body = await request.json()
    filename      = body.get("filename", "")
    options       = body.get("options", {})
    target_column = body.get("target_column", "")
    fe_config_prep = body.get("fe_config", {})

    # The frontend sends the CSV as base64 under "csv_b64"
    csv_b64 = body.get("csv_b64", "")
    if not csv_b64:
        raise HTTPException(400, "csv_b64 is required")

    try:
        csv_bytes = base64.b64decode(csv_b64)
        df = pd.read_csv(io.BytesIO(csv_bytes))
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")

    # Cast boolean columns to int8 to avoid SimpleImputer dtype error
    bool_cols = df.select_dtypes(include="bool").columns.tolist()
    if bool_cols:
        df[bool_cols] = df[bool_cols].astype(_np.int8)

    rows_before = len(df)
    cols_before = len(df.columns)

    # Separate target from features
    feature_cols = [c for c in df.columns if c != target_column]
    target_series = df[target_column] if target_column and target_column in df.columns else None

    df_feat = df[feature_cols].copy()

    # 0. Drop user-selected high-cardinality / ID columns
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

    # 1. Handle missing values — separate strategies for numeric and categorical
    # Supports mv_num / mv_cat (new) or missing_values (legacy, maps to both)
    old_mv = options.get("missing_values")
    mv_num = options.get("mv_num") or old_mv
    mv_cat = options.get("mv_cat") or (
        "most_frequent" if old_mv in ("mean", "median", "knn", "mice") else old_mv
    )

    def _impute_num(cols):
        if not cols:
            return
        if mv_num == "drop":
            nonlocal df_feat, target_series
            mask = df_feat[cols].notna().all(axis=1)
            df_feat = df_feat[mask]
            if target_series is not None:
                target_series = target_series.loc[df_feat.index]
        elif mv_num == "ffill":
            df_feat[cols] = df_feat[cols].ffill()
        elif mv_num == "bfill":
            df_feat[cols] = df_feat[cols].bfill()
        elif mv_num == "constant":
            df_feat[cols] = df_feat[cols].fillna(0)
        elif mv_num == "knn":
            from sklearn.impute import KNNImputer  # noqa: PLC0415
            df_feat[cols] = KNNImputer(n_neighbors=5).fit_transform(df_feat[cols])
        elif mv_num == "mice":
            from sklearn.experimental import enable_iterative_imputer  # noqa: PLC0415, F401
            from sklearn.impute import IterativeImputer  # noqa: PLC0415
            df_feat[cols] = IterativeImputer(max_iter=10, random_state=42).fit_transform(df_feat[cols])
        elif mv_num in ("mean", "median", "mode"):
            strategy = "most_frequent" if mv_num == "mode" else mv_num
            df_feat[cols] = SimpleImputer(strategy=strategy).fit_transform(df_feat[cols])

    def _impute_cat(cols):
        if not cols:
            return
        if mv_cat == "drop":
            nonlocal df_feat, target_series
            mask = df_feat[cols].notna().all(axis=1)
            df_feat = df_feat[mask]
            if target_series is not None:
                target_series = target_series.loc[df_feat.index]
        elif mv_cat == "ffill":
            df_feat[cols] = df_feat[cols].ffill()
        elif mv_cat == "bfill":
            df_feat[cols] = df_feat[cols].bfill()
        elif mv_cat == "constant":
            df_feat[cols] = df_feat[cols].fillna("Unknown")
        elif mv_cat in ("most_frequent", "mode"):
            df_feat[cols] = SimpleImputer(strategy="most_frequent").fit_transform(df_feat[cols])

    if mv_num or mv_cat:
        _impute_num(num_cols)
        # Re-derive cat_cols after possible row drops from numeric drop
        cat_cols = df_feat.select_dtypes(exclude="number").columns.tolist()
        _impute_cat(cat_cols)

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

    # Re-derive num/cat after possible row drops
    num_cols = df_feat.select_dtypes(include="number").columns.tolist()
    cat_cols = df_feat.select_dtypes(exclude="number").columns.tolist()

    # 3. Fix skewness (log1p on positive numeric columns)
    if options.get("fix_skewness") and num_cols:
        for c in num_cols:
            if df_feat[c].min() >= 0:
                try:
                    skew = float(df_feat[c].skew())
                    if abs(skew) > 0.75:
                        df_feat[c] = _np.log1p(df_feat[c])
                except Exception:
                    pass

    # 4. Categorical encoding
    # Resolve encode_method with backward-compat fallback to legacy booleans
    encode_method = options.get("encode_method")
    if encode_method is None:
        if options.get("encode_nominal"):
            encode_method = "onehot"
        elif options.get("encode_ordinal"):
            encode_method = "ordinal"
        else:
            encode_method = "none"

    ordinal_cols = options.get("ordinal_columns", [])
    nominal_cols = [c for c in cat_cols if c not in ordinal_cols]

    ohe_cols_added = 0
    if encode_method == "onehot" and nominal_cols:
        _cols_before_ohe = len(df_feat.columns)
        df_feat = pd.get_dummies(df_feat, columns=nominal_cols, drop_first=False)
        # pandas ≥2.0 returns bool dtype from get_dummies; cast to int8 so
        # select_dtypes(include="number") sees them correctly in feature selection.
        _bool_ohe = df_feat.select_dtypes(include="bool").columns.tolist()
        if _bool_ohe:
            df_feat[_bool_ohe] = df_feat[_bool_ohe].astype(_np.int8)
        ohe_cols_added = len(df_feat.columns) - _cols_before_ohe

    elif encode_method == "ordinal":
        cols_to_encode = ordinal_cols if ordinal_cols else cat_cols
        for c in cols_to_encode:
            if c in df_feat.columns:
                df_feat[c] = LabelEncoder().fit_transform(df_feat[c].astype(str))

    elif encode_method == "frequency" and cat_cols:
        for c in cat_cols:
            freq_map = df_feat[c].value_counts().to_dict()
            df_feat[c] = df_feat[c].map(freq_map)

    elif encode_method == "target" and cat_cols and target_series is not None:
        from sklearn.model_selection import KFold  # noqa: PLC0415
        # Convert target to numeric if needed (classification uses string labels)
        tgt = target_series.reindex(df_feat.index)
        if not pd.api.types.is_numeric_dtype(tgt):
            tgt = tgt.map({v: i for i, v in enumerate(tgt.unique())}).astype(float)
        else:
            tgt = tgt.astype(float)

        global_mean = float(tgt.mean())
        k_smooth    = 10  # smoothing factor

        for c in cat_cols:
            if c not in df_feat.columns:
                continue
            encoded = _np.zeros(len(df_feat), dtype=float)
            idx_arr = df_feat.index.to_numpy()

            kf = KFold(n_splits=5, shuffle=True, random_state=42)
            pos_arr = _np.arange(len(df_feat))
            for train_pos, val_pos in kf.split(pos_arr):
                train_idx = idx_arr[train_pos]
                val_idx   = idx_arr[val_pos]
                fold_tgt  = tgt.loc[train_idx]
                fold_col  = df_feat[c].loc[train_idx]
                stats = fold_col.groupby(fold_col).apply(
                    lambda g: (len(g), float(fold_tgt.loc[g.index].mean()))
                )
                for val_i in val_idx:
                    cat_val = df_feat[c].loc[val_i]
                    if cat_val in stats.index:
                        cnt, mean_ = stats[cat_val]
                        smoothed = (cnt * mean_ + k_smooth * global_mean) / (cnt + k_smooth)
                    else:
                        smoothed = global_mean
                    pos = int(_np.where(idx_arr == val_i)[0][0])
                    encoded[pos] = smoothed
            df_feat[c] = encoded

    # 6. Standardize numeric features
    final_num_cols = df_feat.select_dtypes(include="number").columns.tolist()
    if options.get("standardize") and final_num_cols:
        scaler = StandardScaler()
        df_feat[final_num_cols] = scaler.fit_transform(df_feat[final_num_cols])

    # 7. Feature engineering — applied BEFORE feature selection so that selection
    #    can score and prune FE-derived columns (e.g. polynomial interaction terms).
    pre_fe_cols   = list(df_feat.columns)
    # Sample values for every pre-FE column — stored so /predict can fill
    # columns that feature-selection later drops with real defaults (not NaN).
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
            # Re-cast any bool columns produced by FE
            _fe_bool = df_feat.select_dtypes(include="bool").columns.tolist()
            if _fe_bool:
                df_feat[_fe_bool] = df_feat[_fe_bool].astype(_np.int8)
            fe_cols_added = len(df_feat.columns) - len(pre_fe_cols)
            _fe_buf = io.BytesIO()
            joblib.dump(_fe_tfm_prep, _fe_buf)
            fe_b64_out = base64.b64encode(_fe_buf.getvalue()).decode()
        except Exception as _fe_prep_err:
            print(f"FE in preprocess failed (skipped): {_fe_prep_err}", flush=True)
            _fe_tfm_prep  = FeatureEngineeringTransformer({})
            fe_cols_added = 0
            fe_b64_out    = ""

    # 8. Feature selection — now operates on FE-enriched columns so polynomial
    #    and other derived features are visible to the selection method.
    features_before = len(df_feat.columns)
    fs = options.get("feature_selection", {})
    fs_method = (fs.get("method") or "none").lower()
    top_k = max(1, int(fs.get("top_k") or 10))

    if fs_method != "none":
        try:
            # Drop any remaining non-numeric (unencoded) columns — feature selection
            # is undefined for them and keeping them would inflate the column count.
            leftover_non_num = df_feat.select_dtypes(exclude="number").columns.tolist()
            if leftover_non_num:
                df_feat = df_feat.drop(columns=leftover_non_num)

            num_X = df_feat.select_dtypes(include="number").fillna(0)
            k = min(top_k, len(num_X.columns))
            y_fs = target_series.reindex(df_feat.index) if target_series is not None else None

            if fs_method == "variance" and len(num_X.columns) > k:
                keep = num_X.var().nlargest(k).index.tolist()
                df_feat = df_feat[keep]

            elif fs_method == "correlation" and len(num_X.columns) > 1:
                corr = num_X.corr().abs()
                upper = corr.where(_np.triu(_np.ones(corr.shape), k=1).astype(bool))
                to_drop = [c for c in upper.columns if any(upper[c] > 0.90)]
                df_feat = df_feat.drop(columns=to_drop, errors="ignore")
                remaining_num = df_feat.select_dtypes(include="number")
                if len(remaining_num.columns) > k:
                    keep = remaining_num.var().nlargest(k).index.tolist()
                    df_feat = df_feat[keep]

            elif fs_method == "rfe" and y_fs is not None and len(num_X.columns) >= k:
                from sklearn.feature_selection import RFE  # noqa: PLC0415
                from sklearn.ensemble import RandomForestClassifier as _RFC, RandomForestRegressor as _RFR  # noqa: PLC0415
                is_clf = y_fs.dtype == object or y_fs.nunique() < 20
                estimator = _RFC(n_estimators=50, random_state=42) if is_clf else _RFR(n_estimators=50, random_state=42)
                y_fit = LabelEncoder().fit_transform(y_fs.astype(str)) if is_clf else pd.to_numeric(y_fs, errors="coerce").fillna(0)
                rfe = RFE(estimator, n_features_to_select=k)
                rfe.fit(num_X, y_fit)
                keep = num_X.columns[rfe.support_].tolist()
                df_feat = df_feat[keep]

            elif fs_method == "kbest" and y_fs is not None and len(num_X.columns) >= k:
                from sklearn.feature_selection import SelectKBest, mutual_info_classif, mutual_info_regression  # noqa: PLC0415
                is_clf = y_fs.dtype == object or y_fs.nunique() < 20
                score_fn = mutual_info_classif if is_clf else mutual_info_regression
                y_fit = LabelEncoder().fit_transform(y_fs.astype(str)) if is_clf else pd.to_numeric(y_fs, errors="coerce").fillna(0)
                sel = SelectKBest(score_fn, k=k)
                sel.fit(num_X, y_fit)
                keep = num_X.columns[sel.get_support()].tolist()
                df_feat = df_feat[keep]
        except Exception as _fs_err:
            import logging as _log
            _log.warning("Feature selection failed: %s", _fs_err)

    features_after = len(df_feat.columns)

    # Recombine with target
    if target_series is not None:
        df_out = df_feat.copy()
        target_aligned = target_series.reindex(df_feat.index)
        df_out[target_column] = target_aligned.values
    else:
        df_out = df_feat.copy()

    rows_after = len(df_out)
    cols_after = len(df_out.columns)

    # Serialize to base64 CSV
    csv_buf = io.StringIO()
    df_out.to_csv(csv_buf, index=False)
    csv_str = csv_buf.getvalue()
    csv_b64_out = base64.b64encode(csv_str.encode()).decode()

    # Build analysis of preprocessed file (same shape as /analyze response)
    columns_out = []
    for col in df_out.columns:
        is_num = bool(pd.api.types.is_numeric_dtype(df_out[col]))
        col_info = {
            "name":       col,
            "dtype":      str(df_out[col].dtype),
            "nunique":    int(df_out[col].nunique()),
            "is_numeric": is_num,
            "missing":    int(df_out[col].isna().sum()),
        }
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

    # Suggest target/task from preprocessed data
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
        "csv_b64":               csv_b64_out,
        "preprocessed_filename": preprocessed_filename,
        "rows_before":           rows_before,
        "rows_after":            rows_after,
        "cols_before":           cols_before,
        "cols_after":            cols_after,
        "features_before":       features_before,
        "features_after":        features_after,
        "user_cols_dropped":     user_cols_dropped,
        "ohe_cols_added":        ohe_cols_added,
        "fe_cols_added":         fe_cols_added,
        "fe_b64":                fe_b64_out,
        "pre_fe_cols":           pre_fe_cols,
        "pre_fe_sample":         _pre_fe_sample_out,
        # analysis fields (same structure as /analyze)
        "columns":               columns_out,
        "suggested_target":      suggested_target,
        "suggested_task":        suggested_task,
        "rows":                  rows_after,
        "accent_palette":        ACCENT_PALETTE,
        "total_missing":         int(df_out.isna().sum().sum()),
    }


@app.post("/unsupervised")
async def run_unsupervised(
    file:        UploadFile = File(...),
    algorithm:   str        = Form(...),
    color_col:   str        = Form(""),
    n_clusters:  int        = Form(3),
    eps:         float      = Form(0.5),
    min_samples: int        = Form(5),
    perplexity:  float      = Form(30.0),
    n_dims:      int        = Form(2),
):
    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")
    if len(df.columns) < 2:
        raise HTTPException(400, "CSV must have at least 2 columns")
    if algorithm not in ("K-Means", "DBSCAN", "t-SNE", "PCA"):
        raise HTTPException(400, f"Unknown algorithm: {algorithm}")

    color_labels = None
    if color_col and color_col in df.columns:
        color_labels = df[color_col].astype(str).tolist()
        X = df.drop(columns=[color_col]).copy()
    else:
        X = df.copy()

    id_like = [c for c in X.columns if X[c].dtype == object and X[c].nunique() == len(X)]
    if id_like:
        X = X.drop(columns=id_like)

    num_cols = X.select_dtypes(include="number").columns.tolist()
    cat_cols = X.select_dtypes(exclude="number").columns.tolist()
    transformers = []
    if num_cols:
        transformers.append(("num", Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]), num_cols))
    if cat_cols:
        transformers.append(("cat", Pipeline([
            ("imp", SimpleImputer(strategy="most_frequent")),
            ("enc", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), cat_cols))
    if not transformers:
        raise HTTPException(400, "No usable numeric or categorical columns found")

    # Capture closure variables for the worker thread
    _alg          = algorithm
    _color_labels = color_labels
    _color_col    = color_col
    _n_clusters   = n_clusters
    _eps          = eps
    _min_samples  = min_samples
    _perplexity   = perplexity
    _n_dims       = n_dims

    task = StreamingTask()

    def _work(p):
        p.update(5, "Preparing feature matrix…")
        prep    = ColumnTransformer(transformers, remainder="drop")
        X_prep  = prep.fit_transform(X)
        n_samp  = len(X_prep)
        stats   = {"algorithm": _alg, "rows": n_samp}
        p.update(20, "Transformers fitted…")

        cluster_ids = None

        if _alg == "K-Means":
            p.update(25, f"Running K-Means (k={_n_clusters})…")
            k           = max(2, min(_n_clusters, n_samp - 1))
            km          = KMeans(n_clusters=k, random_state=42, n_init=10)
            cluster_ids = km.fit_predict(X_prep).tolist()
            sil         = silhouette_score(X_prep, cluster_ids) if k > 1 and len(set(cluster_ids)) > 1 else 0.0
            sizes       = {str(i): cluster_ids.count(i) for i in range(k)}
            stats.update({"n_clusters": k, "silhouette": round(sil, 3), "cluster_sizes": sizes})
            p.update(75, "K-Means complete — building plot…")

        elif _alg == "DBSCAN":
            p.update(25, "Reducing dimensions for DBSCAN…")
            n_comp_db = min(max(2, _n_dims), X_prep.shape[1])
            pca_db    = PCA(n_components=n_comp_db)
            coords_db = pca_db.fit_transform(X_prep)
            p.update(50, f"Running DBSCAN (eps={_eps})…")
            db          = DBSCAN(eps=max(0.01, _eps), min_samples=_min_samples)
            cluster_ids = db.fit_predict(coords_db).tolist()
            n_found     = len(set(c for c in cluster_ids if c >= 0))
            n_noise     = cluster_ids.count(-1)
            sil         = silhouette_score(coords_db, cluster_ids) if n_found > 1 and len(set(cluster_ids)) > 1 else 0.0
            stats.update({"n_clusters": n_found, "n_noise": n_noise, "silhouette": round(sil, 3)})
            p.update(85, "Building scatter plot…")

            def _pt_db(i):
                pt = {"x": round(float(coords_db[i, 0]), 4),
                      "y": round(float(coords_db[i, 1] if n_comp_db > 1 else 0.0), 4),
                      "cluster": int(cluster_ids[i]),
                      "label": _color_labels[i] if _color_labels else ""}
                if _n_dims >= 3 and n_comp_db >= 3:
                    pt["z"] = round(float(coords_db[i, 2]), 4)
                return pt

            plot_data = [_pt_db(i) for i in range(n_samp)]
            if _color_labels:
                stats["color_labels"] = sorted(set(_color_labels))
            stats["color_col"] = _color_col if _color_col else ""
            p.finish(result={"plot_data": plot_data, "stats": stats})
            return

        elif _alg == "t-SNE":
            perp   = min(float(_perplexity), max(5.0, (n_samp - 1) / 3))
            t_comp = min(max(2, _n_dims), 3)
            p.update(25, f"Running t-SNE (perplexity={perp:.0f}) — this may take a while…")
            tsne   = TSNE(n_components=t_comp, random_state=42, perplexity=perp,
                          max_iter=1000, init="pca" if X_prep.shape[1] >= 2 else "random")
            coords = tsne.fit_transform(X_prep)
            stats.update({"perplexity": round(perp, 1),
                          "kl_divergence": round(float(tsne.kl_divergence_), 4),
                          "color_col": _color_col if _color_col else ""})
            p.update(85, "t-SNE complete — building plot…")

            def _pt_tsne(i):
                pt = {"x": round(float(coords[i, 0]), 4), "y": round(float(coords[i, 1]), 4),
                      "cluster": -1, "label": _color_labels[i] if _color_labels else ""}
                if _n_dims >= 3 and t_comp >= 3:
                    pt["z"] = round(float(coords[i, 2]), 4)
                return pt

            plot_data = [_pt_tsne(i) for i in range(n_samp)]
            if _color_labels:
                unique_labels = sorted(set(_color_labels))
                label_to_id   = {lbl: idx for idx, lbl in enumerate(unique_labels)}
                for pt in plot_data:
                    pt["cluster"] = label_to_id[pt["label"]]
                stats["color_labels"] = unique_labels
            p.finish(result={"plot_data": plot_data, "stats": stats})
            return

        elif _alg == "PCA":
            n_comp = min(max(2, _n_dims), X_prep.shape[1])
            p.update(25, f"Running PCA ({n_comp} components)…")
            pca    = PCA(n_components=n_comp)
            coords = pca.fit_transform(X_prep)
            ev     = pca.explained_variance_ratio_.tolist()
            stats.update({
                "explained_variance": [round(v * 100, 2) for v in ev],
                "total_variance":     round(sum(ev) * 100, 2),
                "color_col":          _color_col if _color_col else "",
            })
            p.update(85, "PCA complete — building plot…")

            def _pt_pca(i):
                pt = {"x": round(float(coords[i, 0]), 4),
                      "y": round(float(coords[i, 1] if n_comp > 1 else 0.0), 4),
                      "cluster": -1, "label": _color_labels[i] if _color_labels else ""}
                if _n_dims >= 3 and n_comp >= 3:
                    pt["z"] = round(float(coords[i, 2]), 4)
                return pt

            plot_data = [_pt_pca(i) for i in range(n_samp)]
            if _color_labels:
                unique_labels = sorted(set(_color_labels))
                label_to_id   = {lbl: idx for idx, lbl in enumerate(unique_labels)}
                for pt in plot_data:
                    pt["cluster"] = label_to_id[pt["label"]]
                stats["color_labels"] = unique_labels
            p.finish(result={"plot_data": plot_data, "stats": stats})
            return

        # K-Means path — visualise with PCA
        p.update(80, "Building scatter plot…")
        n_comp  = min(max(2, _n_dims), X_prep.shape[1])
        pca_viz = PCA(n_components=n_comp)
        coords  = pca_viz.fit_transform(X_prep)

        def _pt_cl(i):
            pt = {"x": round(float(coords[i, 0]), 4),
                  "y": round(float(coords[i, 1] if n_comp > 1 else 0.0), 4),
                  "cluster": int(cluster_ids[i]),
                  "label": _color_labels[i] if _color_labels else ""}
            if _n_dims >= 3 and n_comp >= 3:
                pt["z"] = round(float(coords[i, 2]), 4)
            return pt

        plot_data = [_pt_cl(i) for i in range(n_samp)]
        if _color_labels:
            unique_labels = sorted(set(_color_labels))
            label_to_id   = {lbl: idx for idx, lbl in enumerate(unique_labels)}
            stats["color_labels"] = unique_labels
        stats["color_col"] = _color_col if _color_col else ""
        p.finish(result={"plot_data": plot_data, "stats": stats})

    return StreamingResponse(
        task.stream(_work),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── AutoML helpers ────────────────────────────────────────────────────────────

_AUTOML_MAX_CV_ROWS = 5000


def _cv_sample(X: pd.DataFrame, y, max_rows: int = _AUTOML_MAX_CV_ROWS):
    """Subsample for cross-validation on large datasets."""
    if len(X) <= max_rows:
        return X, y
    import numpy as _np  # noqa: PLC0415
    idx = _np.random.RandomState(42).choice(len(X), max_rows, replace=False)
    if hasattr(y, "iloc"):
        return X.iloc[idx].reset_index(drop=True), y.iloc[idx].reset_index(drop=True)
    return X.iloc[idx].reset_index(drop=True), y[idx]


def _extract_feature_importances(pipeline, num_cols: list, cat_cols: list) -> list:
    model = pipeline.named_steps.get("model")
    if model is None or not hasattr(model, "feature_importances_"):
        return []
    importances = model.feature_importances_
    prep = pipeline.named_steps["prep"]

    all_feats = list(num_cols)
    if cat_cols:
        try:
            ohe = prep.named_transformers_["cat"].named_steps["enc"]
            for i, col in enumerate(cat_cols):
                n_cats = len(ohe.categories_[i])
                all_feats.extend([col] * n_cats)
        except (KeyError, AttributeError):
            all_feats.extend(cat_cols)

    imp_map: dict = {}
    for i, feat in enumerate(all_feats):
        if i >= len(importances):
            break
        imp_map[feat] = imp_map.get(feat, 0.0) + float(importances[i])

    total = sum(imp_map.values()) or 1.0
    return [
        {"feature": k, "importance": round(v / total * 100, 1)}
        for k, v in sorted(imp_map.items(), key=lambda x: -x[1])
    ][:10]


def _optuna_tune(
    algorithm: str, task: str, X_cv, y_cv, transformers: list,
    cv_split, n_trials: int, is_imbal: bool, on_trial,
) -> tuple[dict, float]:
    import optuna  # noqa: PLC0415
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    from xgboost import XGBClassifier, XGBRegressor          # noqa: PLC0415
    from lightgbm import LGBMClassifier, LGBMRegressor        # noqa: PLC0415
    from catboost import CatBoostClassifier, CatBoostRegressor  # noqa: PLC0415
    scoring = (
        "neg_mean_absolute_error" if task == "regression"
        else ("f1_macro" if is_imbal else "f1_weighted")
    )

    def objective(trial):
        cw = "balanced" if is_imbal else None
        if algorithm == "Random Forest":
            params: dict = {
                "n_estimators":      trial.suggest_int("n_estimators", 50, 300),
                "max_depth":         trial.suggest_categorical("max_depth", [None, 5, 10, 15, 20]),
                "min_samples_split": trial.suggest_int("min_samples_split", 2, 10),
                "min_samples_leaf":  trial.suggest_int("min_samples_leaf", 1, 4),
                "max_features":      trial.suggest_categorical("max_features", ["sqrt", "log2"]),
            }
            est = (RandomForestClassifier(random_state=42, class_weight=cw, **params)
                   if task == "classification"
                   else RandomForestRegressor(random_state=42, **params))
        elif algorithm == "XGBoost":
            params = {
                "n_estimators":     trial.suggest_int("n_estimators", 50, 400),
                "max_depth":        trial.suggest_int("max_depth", 3, 10),
                "learning_rate":    trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "subsample":        trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "reg_alpha":        trial.suggest_float("reg_alpha", 0.0, 5.0),
                "reg_lambda":       trial.suggest_float("reg_lambda", 0.1, 5.0),
            }
            est = (XGBClassifier(random_state=42, eval_metric="logloss", verbosity=0, **params)
                   if task == "classification"
                   else XGBRegressor(random_state=42, verbosity=0, **params))
        elif algorithm == "LightGBM":
            params = {
                "n_estimators":     trial.suggest_int("n_estimators", 50, 400),
                "num_leaves":       trial.suggest_int("num_leaves", 20, 150),
                "learning_rate":    trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "subsample":        trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "reg_alpha":        trial.suggest_float("reg_alpha", 0.0, 5.0),
                "reg_lambda":       trial.suggest_float("reg_lambda", 0.0, 5.0),
            }
            est = (LGBMClassifier(random_state=42, verbose=-1, class_weight=cw, **params)
                   if task == "classification"
                   else LGBMRegressor(random_state=42, verbose=-1, **params))
        else:  # CatBoost
            params = {
                "iterations":    trial.suggest_int("iterations", 50, 400),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "depth":         trial.suggest_int("depth", 4, 10),
                "l2_leaf_reg":   trial.suggest_float("l2_leaf_reg", 1.0, 10.0),
            }
            est = (CatBoostClassifier(random_seed=42, verbose=0, **params)
                   if task == "classification"
                   else CatBoostRegressor(random_seed=42, verbose=0, **params))

        pl     = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")), ("model", est)])
        score  = float(cross_val_score(pl, X_cv, y_cv, cv=cv_split, scoring=scoring).mean())
        on_trial(trial.number + 1, score)
        return score

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42),
    )
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    return study.best_params, study.best_value


def _build_tuned_estimator(algorithm: str, task: str, best_params: dict, is_imbal: bool):
    from xgboost import XGBClassifier, XGBRegressor          # noqa: PLC0415
    from lightgbm import LGBMClassifier, LGBMRegressor        # noqa: PLC0415
    from catboost import CatBoostClassifier, CatBoostRegressor  # noqa: PLC0415
    cw = "balanced" if is_imbal else None
    if algorithm == "Random Forest":
        return (RandomForestClassifier(random_state=42, class_weight=cw, **best_params)
                if task == "classification"
                else RandomForestRegressor(random_state=42, **best_params))
    if algorithm == "XGBoost":
        return (XGBClassifier(random_state=42, eval_metric="logloss", verbosity=0, **best_params)
                if task == "classification"
                else XGBRegressor(random_state=42, verbosity=0, **best_params))
    if algorithm == "LightGBM":
        return (LGBMClassifier(random_state=42, verbose=-1, class_weight=cw, **best_params)
                if task == "classification"
                else LGBMRegressor(random_state=42, verbose=-1, **best_params))
    return (CatBoostClassifier(random_seed=42, verbose=0, **best_params)
            if task == "classification"
            else CatBoostRegressor(random_seed=42, verbose=0, **best_params))


def _rule_explanation(winner: str, cv_results: list, task: str,
                      selection_metric: str, is_imbalanced: bool,
                      feature_importance: list, n_rows: int) -> str:
    if task == "regression":
        sorted_r = sorted(cv_results, key=lambda x: x["score"])
        best_fmt = f"MAE of {sorted_r[0]['score']:.2f}"
        others   = [f"{r['algorithm']} ({r['score']:.2f})" for r in sorted_r[1:]]
    else:
        sorted_r = sorted(cv_results, key=lambda x: -x["score"])
        best_fmt = f"{selection_metric} of {sorted_r[0]['score'] * 100:.1f}%"
        others   = [f"{r['algorithm']} ({r['score'] * 100:.1f}%)" for r in sorted_r[1:]]

    text = f"{winner} achieved the best {best_fmt}"
    if others:
        text += f", outperforming {' and '.join(others)}"
    text += "."
    if is_imbalanced:
        text += " F1-macro was used as the selection criterion because your dataset has class imbalance."
    if feature_importance:
        top3 = [f["feature"] for f in feature_importance[:3]]
        text += f" The most influential features are: {', '.join(top3)}."
    return text


def _build_prompt(winner, cv_results, task, selection_metric, is_imbalanced, feature_importance, n_rows):
    def _fmt_score(r):
        score_str = f"{r['score'] * 100:.2f}%" if task == "classification" else f"{r['score']:.4f}"
        folds = r.get("fold_scores", [])
        if folds:
            fold_str = ", ".join(f"{s * 100:.2f}%" if task == "classification" else f"{s:.4f}" for s in folds)
            variance = max(folds) - min(folds)
            var_str = f"{variance * 100:.2f}%" if task == "classification" else f"{variance:.4f}"
            return f"  {r['algorithm']}: {selection_metric} = {score_str}  [folds: {fold_str}, spread: {var_str}]"
        return f"  {r['algorithm']}: {selection_metric} = {score_str}"

    results_text = "\n".join(_fmt_score(r) for r in cv_results)
    algo_list = ", ".join(r["algorithm"] for r in cv_results)
    fi_text = "\n".join(f"  {i+1}. {f['feature']} ({f['importance']:.1f}%)" for i, f in enumerate(feature_importance[:5])) if feature_importance else "  Not available"
    imbalance_note = " The dataset has class imbalance, so F1-macro was used as the selection metric instead of accuracy." if is_imbalanced else ""
    lower_is_better = task == "regression"
    return (
        f"You are an expert ML engineer explaining AutoML results to a data analyst.\n\n"
        f"Dataset: {n_rows:,} rows | Task: {task}{imbalance_note}\n"
        f"Selection metric: {selection_metric} ({'lower is better' if lower_is_better else 'higher is better'})\n"
        f"Algorithms tested (5-fold cross-validation):\n{results_text}\n\n"
        f"Winner: {winner}\n\nTop features by importance:\n{fi_text}\n\n"
        f"Analyze ALL models, not just the winner. Consider fold spread (high spread = unstable model).\n\n"
        f"Return ONLY a valid JSON object with exactly these 6 fields. No markdown, no code fences, no extra text — just the raw JSON:\n\n"
        f"{{\n"
        f'  "why_won": "2-3 sentences on why {winner} outperformed the others — reference the actual score margins and fold stability.",\n'
        f'  "score_analysis": "2-3 sentences comparing ALL {len(cv_results)} models — discuss how competitive the race was, which models were close, and what the fold spread reveals about stability.",\n'
        f'  "key_drivers": "2-3 sentences on what the top features reveal about prediction drivers and any patterns.",\n'
        f'  "recommendations": ["Specific next step referencing actual scores.", "Specific next step.", "Specific next step."],\n'
        f'  "model_comparison": [\n'
        f'    {{"algorithm": "<name>", "fitness_score": <0-100 integer rating for this dataset>, "reason": "1 sentence why this score."}}\n'
        f'    // one entry per algorithm: {algo_list}\n'
        f'  ],\n'
        f'  "actionable_insights": [\n'
        f'    {{"title": "3-5 word title", "detail": "1-2 specific sentences tied to the actual numbers."}},\n'
        f'    {{"title": "3-5 word title", "detail": "1-2 specific sentences tied to the actual numbers."}},\n'
        f'    {{"title": "3-5 word title", "detail": "1-2 specific sentences tied to the actual numbers."}}\n'
        f'  ]\n'
        f"}}\n\n"
        f"Be specific to the numbers provided. No generic filler. Avoid jargon."
    )


def _llm_explanation(api_key: str, winner: str, cv_results: list, task: str,
                     selection_metric: str, is_imbalanced: bool,
                     feature_importance: list, n_rows: int, provider: str = "gemini-2.5",
                     custom_base_url: str = "", custom_model: str = ""):
    import json as _json  # noqa: PLC0415
    prompt = _build_prompt(winner, cv_results, task, selection_metric, is_imbalanced, feature_importance, n_rows)
    raw_text = None
    try:
        if provider == "openai":
            import openai  # noqa: PLC0415
            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model=custom_model or "gpt-4o-mini", max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = resp.choices[0].message.content.strip()
        elif provider in ("groq", "groq-mixtral"):
            import openai  # noqa: PLC0415
            client = openai.OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
            default_model = "mixtral-8x7b-32768" if provider == "groq-mixtral" else "llama-3.3-70b-versatile"
            resp = client.chat.completions.create(
                model=custom_model or default_model, max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = resp.choices[0].message.content.strip()
        elif provider == "custom":
            import openai  # noqa: PLC0415
            if not custom_base_url or not custom_model:
                return None
            client = openai.OpenAI(api_key=api_key or "none", base_url=custom_base_url)
            resp = client.chat.completions.create(
                model=custom_model, max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = resp.choices[0].message.content.strip()
        elif provider in ("gemini-3.5", "gemini-2.5"):
            import google.generativeai as genai  # noqa: PLC0415
            genai.configure(api_key=api_key)
            default_model = "gemini-3.5-flash" if provider == "gemini-3.5" else "gemini-2.5-flash"
            model = genai.GenerativeModel(custom_model or default_model)
            resp = model.generate_content(prompt)
            raw_text = resp.text.strip()
        else:
            import anthropic  # noqa: PLC0415
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model=custom_model or "claude-haiku-4-5-20251001",
                max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = msg.content[0].text.strip()
    except Exception:
        return None
    if raw_text is None:
        return None
    # Strip markdown code fences if the model wrapped the JSON anyway
    import re as _re
    cleaned = raw_text.strip()
    cleaned = _re.sub(r'^```[a-z]*\n?', '', cleaned)
    cleaned = _re.sub(r'\n?```$', '', cleaned).strip()
    try:
        parsed = _json.loads(cleaned)
        return {
            "why_won":            str(parsed.get("why_won", "")),
            "score_analysis":     str(parsed.get("score_analysis", "")),
            "key_drivers":        str(parsed.get("key_drivers", "")),
            "recommendations":    parsed.get("recommendations", []),
            "model_comparison":   parsed.get("model_comparison", []),
            "actionable_insights": parsed.get("actionable_insights", []),
        }
    except (_json.JSONDecodeError, Exception):
        return {"why_won": raw_text, "score_analysis": "", "key_drivers": "", "recommendations": []}


class FeatureEngineeringTransformer(BaseEstimator, TransformerMixin):
    """Fit on train data only, transform both train and test."""

    def __init__(self, fe_config=None):
        self.fe_config = fe_config or {}

    def fit(self, X, y=None):
        import numpy as np
        cfg = self.fe_config
        X_df = pd.DataFrame(X) if not isinstance(X, pd.DataFrame) else X.copy()

        self._bin_edges_       = {}
        self._yeo_transformers_= {}
        self._iqr_bounds_      = {}
        self._rank_vals_       = {}
        self._date_mins_       = {}
        self._poly_transformer_= None
        self._poly_cols_       = []

        for col, transforms in cfg.get("numeric", {}).items():
            if col not in X_df.columns or not isinstance(transforms, dict):
                continue
            series = X_df[col].dropna()
            if series.empty:
                continue

            bin_method = transforms.get("bin", "none")
            bin_n      = int(transforms.get("bin_n", 5) or 5)
            if bin_method == "quantile":
                try:
                    _, edges = pd.qcut(series, q=bin_n, retbins=True, duplicates="drop")
                    self._bin_edges_[col] = edges
                except Exception:
                    pass
            elif bin_method == "equal_width":
                try:
                    _, edges = pd.cut(series, bins=bin_n, retbins=True)
                    self._bin_edges_[col] = edges
                except Exception:
                    pass
            elif bin_method == "custom":
                try:
                    raw = str(transforms.get("bin_custom", "") or "")
                    edges = sorted(float(x.strip()) for x in raw.split(",") if x.strip())
                    if len(edges) >= 2:
                        self._bin_edges_[col] = edges
                except Exception:
                    pass

            if transforms.get("yeo_johnson"):
                try:
                    pt = PowerTransformer(method="yeo-johnson")
                    pt.fit(series.values.reshape(-1, 1))
                    self._yeo_transformers_[col] = pt
                except Exception:
                    pass

            if transforms.get("outlier_flag"):
                q1, q3 = float(series.quantile(0.25)), float(series.quantile(0.75))
                iqr    = q3 - q1
                self._iqr_bounds_[col] = (q1 - 1.5 * iqr, q3 + 1.5 * iqr)

            if transforms.get("rank"):
                self._rank_vals_[col] = np.sort(series.values)

        for col, dcfg in cfg.get("dates", {}).items():
            if col not in X_df.columns or not isinstance(dcfg, dict):
                continue
            if dcfg.get("days_since_min"):
                try:
                    self._date_mins_[col] = pd.to_datetime(X_df[col], errors="coerce").min()
                except Exception:
                    pass

        poly_cols = [c for c in cfg.get("poly_cols", []) if c in X_df.columns]
        if len(poly_cols) >= 2:
            try:
                from sklearn.preprocessing import PolynomialFeatures
                pf = PolynomialFeatures(degree=2, interaction_only=True, include_bias=False)
                pf.fit(X_df[poly_cols].fillna(0))
                self._poly_transformer_ = pf
                self._poly_cols_        = poly_cols
            except Exception:
                pass

        return self

    def transform(self, X):
        import numpy as np
        cfg  = self.fe_config
        X_df = pd.DataFrame(X) if not isinstance(X, pd.DataFrame) else X.copy()

        # 1. Missing indicators (before any other transform)
        for col, transforms in cfg.get("numeric", {}).items():
            if col not in X_df.columns or not isinstance(transforms, dict):
                continue
            if transforms.get("missing_flag"):
                X_df[f"{col}_was_missing"] = X_df[col].isna().astype("int8")

        # 2. Numeric transforms
        for col, transforms in cfg.get("numeric", {}).items():
            if col not in X_df.columns or not isinstance(transforms, dict):
                continue
            if transforms.get("log1p"):
                X_df[f"{col}_log"] = np.log1p(X_df[col].clip(lower=0))
            if transforms.get("sqrt"):
                X_df[f"{col}_sqrt"] = np.sqrt(X_df[col].clip(lower=0))
            if transforms.get("yeo_johnson") and col in self._yeo_transformers_:
                try:
                    pt   = self._yeo_transformers_[col]
                    vals = pt.transform(X_df[col].fillna(0).values.reshape(-1, 1)).flatten()
                    X_df[f"{col}_yj"] = vals
                except Exception:
                    pass
            if transforms.get("rank") and col in self._rank_vals_:
                try:
                    train_sorted = self._rank_vals_[col]
                    n            = len(train_sorted)
                    raw          = X_df[col].values
                    ranks        = np.searchsorted(train_sorted, raw, side="left") / max(n, 1)
                    X_df[f"{col}_rank"] = np.where(pd.isna(X_df[col]), np.nan, ranks)
                except Exception:
                    pass

        # 3. Binning (using fitted edges)
        for col, edges in self._bin_edges_.items():
            if col not in X_df.columns:
                continue
            try:
                X_df[f"{col}_bin"] = pd.cut(
                    X_df[col], bins=edges, labels=False, include_lowest=True
                )
            except Exception:
                pass

        # 4. Outlier flags
        for col, (lower, upper) in self._iqr_bounds_.items():
            if col not in X_df.columns:
                continue
            X_df[f"{col}_is_outlier"] = (
                (X_df[col] < lower) | (X_df[col] > upper)
            ).astype("int8")

        # 5. Date extraction
        for col, dcfg in cfg.get("dates", {}).items():
            if col not in X_df.columns or not isinstance(dcfg, dict):
                continue
            try:
                dt = pd.to_datetime(X_df[col], errors="coerce")
                if dcfg.get("year"):
                    X_df[f"{col}_year"] = dt.dt.year
                if dcfg.get("month"):
                    X_df[f"{col}_month"] = dt.dt.month
                if dcfg.get("day"):
                    X_df[f"{col}_day"] = dt.dt.day
                if dcfg.get("dow"):
                    X_df[f"{col}_dow"] = dt.dt.dayofweek
                if dcfg.get("quarter"):
                    X_df[f"{col}_quarter"] = dt.dt.quarter
                if dcfg.get("is_weekend"):
                    X_df[f"{col}_is_weekend"] = (dt.dt.dayofweek >= 5).astype("int8")
                if dcfg.get("days_since_min") and col in self._date_mins_:
                    X_df[f"{col}_days_since_min"] = (dt - self._date_mins_[col]).dt.days
                if dcfg.get("cyclical"):
                    if dcfg.get("month"):
                        m = dt.dt.month
                        X_df[f"{col}_month_sin"] = np.sin(2 * np.pi * m / 12)
                        X_df[f"{col}_month_cos"] = np.cos(2 * np.pi * m / 12)
                    if dcfg.get("dow"):
                        d = dt.dt.dayofweek
                        X_df[f"{col}_dow_sin"] = np.sin(2 * np.pi * d / 7)
                        X_df[f"{col}_dow_cos"] = np.cos(2 * np.pi * d / 7)
                if not dcfg.get("keep_original"):
                    X_df = X_df.drop(columns=[col], errors="ignore")
            except Exception:
                pass

        # 6. Derived features
        for d in cfg.get("derived", []):
            col_a = d.get("col_a")
            col_b = d.get("col_b")
            op = d.get("op")
            if not col_a or not col_b or col_a not in X_df.columns or col_b not in X_df.columns:
                continue
            try:
                if op == "ratio":
                    X_df[f"{col_a}_div_{col_b}"] = X_df[col_a] / (X_df[col_b].replace(0, np.nan) + 1e-9)
                elif op == "diff":
                    X_df[f"{col_a}_minus_{col_b}"] = X_df[col_a] - X_df[col_b]
            except Exception:
                pass

        # 7. Polynomial interactions
        if self._poly_transformer_ is not None:
            try:
                from itertools import combinations as _comb
                avail = [c for c in self._poly_cols_ if c in X_df.columns]
                if len(avail) == len(self._poly_cols_):
                    poly_arr    = X_df[avail].fillna(0).to_numpy()
                    poly_out    = self._poly_transformer_.transform(poly_arr)
                    inter_names = [f"{a} {b}" for a, b in _comb(avail, 2)]
                    n_inter     = len(inter_names)
                    inter_vals  = poly_out[:, -n_inter:]
                    inter_df    = pd.DataFrame(inter_vals, columns=inter_names, index=X_df.index)
                    X_df        = pd.concat([X_df, inter_df], axis=1)
            except Exception as _poly_exc:
                print(f"Polynomial FE transform failed: {_poly_exc}", flush=True)

        return X_df


@app.post("/train")
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
    tune:                bool       = Form(False),
    n_trials:            int        = Form(10),
    selected_models:     str        = Form('["Random Forest","XGBoost","LightGBM","CatBoost","Extra Trees"]'),
):
    content = await file.read()
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

    # Parse feature engineering config
    try:
        import json as _json_fe
        _fe_config = _json_fe.loads(feature_engineering or "{}")
    except Exception:
        _fe_config = {}

    try:
        _pre_fe_cols_from_prep = _json_fe.loads(pre_fe_cols_json or "[]")
    except Exception:
        _pre_fe_cols_from_prep = []

    try:
        _pre_fe_sample: dict = _json_fe.loads(pre_fe_sample_json or "{}")
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

    # Cast boolean columns to int8 to avoid SimpleImputer dtype error
    _bool_cols = X.select_dtypes(include="bool").columns.tolist()
    if _bool_cols:
        X = X.copy()
        X[_bool_cols] = X[_bool_cols].astype("int8")

    if fe_b64:
        # FE was applied during /automl/preprocess — deserialize the pre-fit
        # transformer so it can be used for prediction.  The CSV (automlFile)
        # is already FE'd, so we must NOT re-apply it here.
        import base64 as _b64_train  # noqa: PLC0415
        _fe_transformer = joblib.load(io.BytesIO(_b64_train.b64decode(fe_b64)))
        _pre_fe_cols    = _pre_fe_cols_from_prep or list(X.columns)
    else:
        # Legacy path: no preprocessing was done, or preprocessing ran without
        # FE config.  Apply FE directly to the raw training CSV.
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

    num_cols = X.select_dtypes(include="number").columns.tolist()
    cat_cols = X.select_dtypes(exclude="number").columns.tolist()

    transformers = []
    if num_cols:
        transformers.append(("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), num_cols))
    if cat_cols:
        transformers.append(("cat", Pipeline([
            ("imp", SimpleImputer(strategy="most_frequent")),
            ("enc", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), cat_cols))

    if not transformers:
        raise HTTPException(400, "No usable feature columns found after cleaning")

    # Capture closure variables for the worker thread
    _task      = task
    _algorithm = algorithm
    _accent    = accent
    _model_id  = model_id
    _model_name = model_name
    _target_col = target_col
    _fe_tfm        = _fe_transformer
    _pre_fe_cols_  = _pre_fe_cols
    _pre_fe_sample_= _pre_fe_sample
    _n_clusters = n_clusters
    _tune       = tune
    _n_trials   = max(5, min(50, n_trials))
    import json as _json_fm
    try:
        _selected_models = set(_json_fm.loads(selected_models))
    except Exception:
        _selected_models = {"Random Forest", "XGBoost", "LightGBM", "CatBoost", "Extra Trees", "Decision Tree", "KNN", "Logistic Regression", "Ridge"}
    _y          = y

    streaming_task = StreamingTask()

    def _work(p):
        # Lazy-import boosting libraries — each ~20-200 MB of shared libs;
        # keeping them out of module-level imports frees ~200 MB at startup.
        from xgboost import XGBClassifier, XGBRegressor          # noqa: PLC0415
        from lightgbm import LGBMClassifier, LGBMRegressor        # noqa: PLC0415
        from catboost import CatBoostClassifier, CatBoostRegressor  # noqa: PLC0415

        preprocessor         = ColumnTransformer(transformers, remainder="drop")
        le                   = None
        plot_data            = None
        metric = metric_label = ""
        extra_metrics: list  = []
        automl_result        = None
        _actuals_data        = None
        _effective_algorithm = _algorithm

        p.update(5, "Preparing feature matrix…")

        if _task == "clustering":
            p.update(10, "Fitting preprocessing…")
            preprocessor.fit(X)
            X_prep = preprocessor.transform(X)
            n_comp = min(2, X_prep.shape[1])

            if _algorithm == "t-SNE":
                p.update(20, "Running t-SNE (this may take a while)…")
                reducer = TSNE(n_components=n_comp, random_state=42,
                               perplexity=min(30, max(5, len(X) // 10)))
                coords  = reducer.fit_transform(X_prep)
                labels  = [-1] * len(X)
                metric, metric_label = "N/A", "Visualization"
                pipeline = Pipeline([("prep", preprocessor)])

            elif _algorithm == "PCA":
                p.update(20, "Running PCA…")
                reducer = PCA(n_components=n_comp)
                coords  = reducer.fit_transform(X_prep)
                labels  = [-1] * len(X)
                ev      = reducer.explained_variance_ratio_
                metric, metric_label = f"{sum(ev)*100:.1f}%", "Variance Explained"
                pipeline = Pipeline([("prep", preprocessor)])

            elif _algorithm == "DBSCAN":
                p.update(20, "Running DBSCAN…")
                db      = DBSCAN(eps=0.5, min_samples=5)
                labels  = db.fit_predict(X_prep).tolist()
                n_found = len(set(lbl for lbl in labels if lbl >= 0))
                sil     = silhouette_score(X_prep, labels) if n_found > 1 and len(set(labels)) > 1 else 0.0
                metric, metric_label = f"{sil:.2f}", "Silhouette"
                pca_viz = PCA(n_components=n_comp)
                coords  = pca_viz.fit_transform(X_prep)
                pipeline = Pipeline([("prep", preprocessor)])

            else:  # K-Means
                p.update(20, f"Running K-Means (k={_n_clusters})…")
                km       = KMeans(n_clusters=_n_clusters, random_state=42, n_init=10)
                pipeline = Pipeline([("prep", preprocessor), ("model", km)])
                pipeline.fit(X)
                labels   = pipeline.predict(X).tolist()
                sil      = silhouette_score(X_prep, labels) if _n_clusters > 1 and len(set(labels)) > 1 else 0.0
                metric, metric_label = f"{sil:.2f}", "Silhouette"
                pca_viz  = PCA(n_components=n_comp)
                coords   = pca_viz.fit_transform(X_prep)

            p.update(80, "Building cluster plot…")
            if n_comp == 1:
                plot_data = [{"x": round(float(coords[i, 0]), 4), "y": 0.0, "cluster": int(labels[i])} for i in range(len(coords))]
            else:
                plot_data = [{"x": round(float(coords[i, 0]), 4), "y": round(float(coords[i, 1]), 4), "cluster": int(labels[i])} for i in range(len(coords))]

        elif _task == "classification":
            p.update(10, "Encoding labels…")
            le    = LabelEncoder()
            y_enc = le.fit_transform(_y.astype(str))

            if _algorithm == "AutoML":
                try:
                    # Detect class imbalance
                    cls_counts = pd.Series(y_enc).value_counts()
                    min_ratio  = float(cls_counts.min()) / len(y_enc)
                    is_imbal   = min_ratio < 0.20
                    sel_metric = "f1_macro" if is_imbal else "f1_weighted"
                    sel_label  = "F1-macro" if is_imbal else "F1 (weighted)"

                    X_cv, y_cv = _cv_sample(X, y_enc)
                    cv_split   = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
                    cw = "balanced" if is_imbal else None

                    cv_results = []

                    _pct_steps = [12, 26, 40, 55, 70]
                    _model_idx = 0

                    if "Random Forest" in _selected_models:
                        p.update(_pct_steps[_model_idx % 5], "Testing Random Forest (5-fold CV)…")
                        _model_idx += 1
                        try:
                            rf_pl  = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                               ("model", RandomForestClassifier(n_estimators=100, random_state=42, class_weight=cw))])
                            _rf_folds  = cross_val_score(rf_pl, X_cv, y_cv, cv=cv_split, scoring=sel_metric)
                            cv_results.append({"algorithm": "Random Forest", "score": round(float(_rf_folds.mean()), 4), "fold_scores": [round(float(s), 4) for s in _rf_folds]})
                        except Exception as _e:
                            print(f"Random Forest CV failed: {_e}", flush=True)

                    if "XGBoost" in _selected_models:
                        p.update(_pct_steps[_model_idx % 5], "Testing XGBoost (5-fold CV)…")
                        _model_idx += 1
                        try:
                            xgb_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                               ("model", XGBClassifier(n_estimators=100, random_state=42, eval_metric="logloss", verbosity=0))])
                            _xgb_folds = cross_val_score(xgb_pl, X_cv, y_cv, cv=cv_split, scoring=sel_metric)
                            cv_results.append({"algorithm": "XGBoost", "score": round(float(_xgb_folds.mean()), 4), "fold_scores": [round(float(s), 4) for s in _xgb_folds]})
                        except Exception as _e:
                            print(f"XGBoost CV failed: {_e}", flush=True)

                    if "LightGBM" in _selected_models:
                        p.update(_pct_steps[_model_idx % 5], "Testing LightGBM (5-fold CV)…")
                        _model_idx += 1
                        try:
                            lgb_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                               ("model", LGBMClassifier(n_estimators=100, random_state=42, class_weight=cw, verbose=-1))])
                            _lgb_folds = cross_val_score(lgb_pl, X_cv, y_cv, cv=cv_split, scoring=sel_metric)
                            cv_results.append({"algorithm": "LightGBM", "score": round(float(_lgb_folds.mean()), 4), "fold_scores": [round(float(s), 4) for s in _lgb_folds]})
                        except Exception as _e:
                            print(f"LightGBM CV failed: {_e}", flush=True)

                    if "CatBoost" in _selected_models:
                        p.update(_pct_steps[_model_idx % 5], "Testing CatBoost (5-fold CV)…")
                        _model_idx += 1
                        try:
                            cat_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                               ("model", CatBoostClassifier(iterations=100, random_seed=42, verbose=0))])
                            _cat_folds = cross_val_score(cat_pl, X_cv, y_cv, cv=cv_split, scoring=sel_metric)
                            cv_results.append({"algorithm": "CatBoost", "score": round(float(_cat_folds.mean()), 4), "fold_scores": [round(float(s), 4) for s in _cat_folds]})
                        except Exception as _e:
                            print(f"CatBoost CV failed: {_e}", flush=True)

                    if "Extra Trees" in _selected_models:
                        p.update(_pct_steps[_model_idx % 5], "Testing Extra Trees (5-fold CV)…")
                        _model_idx += 1
                        try:
                            et_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                              ("model", ExtraTreesClassifier(n_estimators=100, random_state=42, class_weight=cw))])
                            _et_folds = cross_val_score(et_pl, X_cv, y_cv, cv=cv_split, scoring=sel_metric)
                            cv_results.append({"algorithm": "Extra Trees", "score": round(float(_et_folds.mean()), 4), "fold_scores": [round(float(s), 4) for s in _et_folds]})
                        except Exception as _e:
                            print(f"Extra Trees CV failed: {_e}", flush=True)

                    if "Decision Tree" in _selected_models:
                        p.update(_pct_steps[_model_idx % 5], "Testing Decision Tree (5-fold CV)…")
                        _model_idx += 1
                        try:
                            dt_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                              ("model", DecisionTreeClassifier(random_state=42, class_weight=cw))])
                            _dt_folds = cross_val_score(dt_pl, X_cv, y_cv, cv=cv_split, scoring=sel_metric)
                            cv_results.append({"algorithm": "Decision Tree", "score": round(float(_dt_folds.mean()), 4), "fold_scores": [round(float(s), 4) for s in _dt_folds]})
                        except Exception as _e:
                            print(f"Decision Tree CV failed: {_e}", flush=True)

                    if "KNN" in _selected_models:
                        p.update(_pct_steps[_model_idx % 5], "Testing KNN (5-fold CV)…")
                        _model_idx += 1
                        try:
                            knn_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                               ("model", KNeighborsClassifier(n_neighbors=5))])
                            _knn_folds = cross_val_score(knn_pl, X_cv, y_cv, cv=cv_split, scoring=sel_metric)
                            cv_results.append({"algorithm": "KNN", "score": round(float(_knn_folds.mean()), 4), "fold_scores": [round(float(s), 4) for s in _knn_folds]})
                        except Exception as _e:
                            print(f"KNN CV failed: {_e}", flush=True)

                    if "Logistic Regression" in _selected_models:
                        p.update(_pct_steps[_model_idx % 5], "Testing Logistic Regression (5-fold CV)…")
                        _model_idx += 1
                        try:
                            lr_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                              ("model", LogisticRegression(max_iter=1000, random_state=42, class_weight=cw))])
                            _lr_folds = cross_val_score(lr_pl, X_cv, y_cv, cv=cv_split, scoring=sel_metric)
                            cv_results.append({"algorithm": "Logistic Regression", "score": round(float(_lr_folds.mean()), 4), "fold_scores": [round(float(s), 4) for s in _lr_folds]})
                        except Exception as _e:
                            print(f"Logistic Regression CV failed: {_e}", flush=True)

                    if "SVM" in _selected_models:
                        p.update(_pct_steps[_model_idx % 5], "Testing SVM (5-fold CV)…")
                        _model_idx += 1
                        try:
                            svm_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                               ("model", SVC(kernel="rbf", probability=True, class_weight=cw, random_state=42))])
                            _svm_folds = cross_val_score(svm_pl, X_cv, y_cv, cv=cv_split, scoring=sel_metric)
                            cv_results.append({"algorithm": "SVM", "score": round(float(_svm_folds.mean()), 4), "fold_scores": [round(float(s), 4) for s in _svm_folds]})
                        except Exception as _e:
                            print(f"SVM CV failed: {_e}", flush=True)

                    if "Naive Bayes" in _selected_models:
                        p.update(_pct_steps[_model_idx % 5], "Testing Naive Bayes (5-fold CV)…")
                        _model_idx += 1
                        try:
                            nb_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                              ("model", GaussianNB(var_smoothing=1e-2))])
                            _nb_folds = cross_val_score(nb_pl, X_cv, y_cv, cv=cv_split, scoring=sel_metric)
                            cv_results.append({"algorithm": "Naive Bayes", "score": round(float(_nb_folds.mean()), 4), "fold_scores": [round(float(s), 4) for s in _nb_folds]})
                        except Exception as _e:
                            print(f"Naive Bayes CV failed: {_e}", flush=True)

                    if "Gradient Boosting" in _selected_models:
                        p.update(_pct_steps[_model_idx % 5], "Testing Gradient Boosting (5-fold CV)…")
                        _model_idx += 1
                        try:
                            gb_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                              ("model", GradientBoostingClassifier(n_estimators=100, random_state=42))])
                            _gb_folds = cross_val_score(gb_pl, X_cv, y_cv, cv=cv_split, scoring=sel_metric)
                            cv_results.append({"algorithm": "Gradient Boosting", "score": round(float(_gb_folds.mean()), 4), "fold_scores": [round(float(s), 4) for s in _gb_folds]})
                        except Exception as _e:
                            print(f"Gradient Boosting CV failed: {_e}", flush=True)

                    if "AdaBoost" in _selected_models:
                        from sklearn.ensemble import AdaBoostClassifier  # noqa: PLC0415
                        p.update(_pct_steps[_model_idx % 5], "Testing AdaBoost (5-fold CV)…")
                        _model_idx += 1
                        try:
                            ada_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                               ("model", AdaBoostClassifier(n_estimators=100, random_state=42))])
                            _ada_folds = cross_val_score(ada_pl, X_cv, y_cv, cv=cv_split, scoring=sel_metric)
                            cv_results.append({"algorithm": "AdaBoost", "score": round(float(_ada_folds.mean()), 4), "fold_scores": [round(float(s), 4) for s in _ada_folds]})
                        except Exception as _e:
                            print(f"AdaBoost CV failed: {_e}", flush=True)

                    if not cv_results:
                        raise RuntimeError("All selected models failed CV")

                    winner = max(cv_results, key=lambda r: r["score"])["algorithm"]
                    _effective_algorithm = winner

                    if winner == "XGBoost":
                        estimator = XGBClassifier(n_estimators=100, random_state=42,
                                                  eval_metric="logloss", verbosity=0)
                    elif winner == "LightGBM":
                        estimator = LGBMClassifier(n_estimators=100, random_state=42,
                                                   class_weight=cw, verbose=-1)
                    elif winner == "CatBoost":
                        estimator = CatBoostClassifier(iterations=100, random_seed=42, verbose=0)
                    elif winner == "Extra Trees":
                        estimator = ExtraTreesClassifier(n_estimators=100, random_state=42,
                                                         class_weight=cw)
                    elif winner == "Decision Tree":
                        estimator = DecisionTreeClassifier(random_state=42, class_weight=cw)
                    elif winner == "KNN":
                        estimator = KNeighborsClassifier(n_neighbors=5)
                    elif winner == "Logistic Regression":
                        estimator = LogisticRegression(max_iter=1000, random_state=42, class_weight=cw)
                    elif winner == "SVM":
                        estimator = SVC(kernel="rbf", probability=True, class_weight=cw, random_state=42)
                    elif winner == "Naive Bayes":
                        estimator = GaussianNB()
                    elif winner == "Gradient Boosting":
                        estimator = GradientBoostingClassifier(n_estimators=100, random_state=42)
                    elif winner == "AdaBoost":
                        from sklearn.ensemble import AdaBoostClassifier  # noqa: PLC0415
                        estimator = AdaBoostClassifier(n_estimators=100, random_state=42)
                    else:
                        estimator = RandomForestClassifier(n_estimators=100, random_state=42,
                                                           class_weight=cw)

                    automl_result = {
                        "winner":           winner,
                        "selection_metric": sel_label,
                        "is_imbalanced":    is_imbal,
                        "n_rows":           len(X),
                        "n_input_cols":     len(X.columns),
                        "cv_results":       cv_results,
                        "task":             "classification",
                        "gpu":              _detect_gpu(),
                    }

                    if _tune:
                        p.update(65, f"Winner: {winner}. Tuning with Optuna ({_n_trials} trials)…")
                        try:
                            _best_params, _best_val = _optuna_tune(
                                winner, "classification", X_cv, y_cv, transformers,
                                cv_split, _n_trials, is_imbal,
                                lambda t, s: p.update(
                                    65 + int(t / _n_trials * 13),
                                    f"Optuna trial {t}/{_n_trials} — best {sel_label}: {s:.4f}",
                                ),
                            )
                            estimator = _build_tuned_estimator(winner, "classification", _best_params, is_imbal)
                            automl_result["optuna_params"]      = _best_params
                            automl_result["optuna_best_score"]  = round(_best_val, 4)
                            automl_result["optuna_n_trials"]    = _n_trials
                            p.update(78, f"Tuning done. Training {winner} with best params…")
                        except Exception as _oe:
                            print(f"Optuna tuning failed, using default params: {_oe}", flush=True)
                            p.update(78, f"Tuning failed — using default {winner} params…")
                    else:
                        p.update(65, f"Winner: {winner}. Training on full dataset…")

                except Exception as _exc:
                    # CV failed — fall back to Random Forest
                    print(f"AutoML CV failed, falling back to Random Forest: {_exc}", flush=True)
                    estimator = RandomForestClassifier(n_estimators=100, random_state=42)
                    _effective_algorithm = "Random Forest"

            else:
                if _algorithm == "XGBoost":
                    estimator = XGBClassifier(n_estimators=100, random_state=42,
                                              eval_metric="logloss", verbosity=0)
                elif _algorithm == "LightGBM":
                    estimator = LGBMClassifier(n_estimators=100, random_state=42, verbose=-1)
                elif _algorithm == "CatBoost":
                    estimator = CatBoostClassifier(iterations=100, random_seed=42, verbose=0)
                elif _algorithm == "Random Forest":
                    estimator = RandomForestClassifier(n_estimators=100, random_state=42)
                else:
                    estimator = GradientBoostingClassifier(n_estimators=100, random_state=42)

            pipeline = Pipeline([("prep", preprocessor), ("model", estimator)])
            split    = 0.2 if len(X) >= 10 else 0.1
            X_train, X_test, y_train, y_test = train_test_split(
                X, y_enc, test_size=split, random_state=42, stratify=y_enc)
            if automl_result:
                automl_result["n_train"] = len(X_train)
                automl_result["n_test"]  = len(X_test)
            train_pct = (79 if (_tune and automl_result) else 68 if automl_result else 20)
            p.update(train_pct, f"Training {_effective_algorithm} classifier…")
            pipeline.fit(X_train, y_train)
            p.update(82, "Evaluating on test set…")
            y_pred       = pipeline.predict(X_test)
            is_imbal_result = automl_result.get("is_imbalanced", False) if automl_result else False
            f1_w = f1_score(y_test, y_pred, average="weighted", zero_division=0)
            f1_m = f1_score(y_test, y_pred, average="macro",    zero_division=0)
            acc  = accuracy_score(y_test, y_pred)
            # F1-weighted is always more reliable than accuracy for classification
            score        = f1_m if is_imbal_result else f1_w
            metric       = f"{score:.3f}"
            metric_label = "F1-macro" if is_imbal_result else "F1 (weighted)"
            extra_metrics = []
            extra_metrics.append({"label": "Accuracy", "value": f"{acc * 100:.1f}%"})
            try:
                n_cls = len(set(y_enc))
                if n_cls == 2:
                    proba = pipeline.predict_proba(X_test)[:, 1]
                    auc   = roc_auc_score(y_test, proba)
                else:
                    proba = pipeline.predict_proba(X_test)
                    auc   = roc_auc_score(y_test, proba, multi_class="ovr", average="macro")
                extra_metrics.append({"label": "ROC-AUC", "value": f"{auc:.3f}"})
            except Exception:
                auc = None

            if automl_result:
                prec_w = precision_score(y_test, y_pred, average="weighted", zero_division=0)
                rec_w  = recall_score(y_test, y_pred, average="weighted", zero_division=0)
                wm = {
                    "accuracy":    round(float(acc),    4),
                    "f1_weighted": round(float(f1_w),   4),
                    "precision":   round(float(prec_w), 4),
                    "recall":      round(float(rec_w),  4),
                }
                if auc is not None:
                    wm["roc_auc"] = round(float(auc), 4)
                automl_result["winner_metrics"] = wm

                # Confusion matrix
                cm = sk_confusion_matrix(y_test, y_pred)
                automl_result["confusion_matrix"] = cm.tolist()
                automl_result["class_names"] = [str(c) for c in le.classes_]

                # Learning curve — adaptive CV folds (3-fold for large datasets)
                _lc_rows   = len(X)
                _lc_folds  = 3 if _lc_rows > 5000 else 5
                automl_result["lc_cv_folds"] = _lc_folds
                try:
                    p.update(83, "Computing learning curve…")
                    lc_sizes, lc_train_sc, lc_val_sc = learning_curve(
                        clone(pipeline), X_cv, y_cv,
                        cv=StratifiedKFold(n_splits=_lc_folds, shuffle=True, random_state=42),
                        train_sizes=[0.2, 0.4, 0.6, 0.8, 1.0],
                        scoring=sel_metric, n_jobs=1,
                    )
                    automl_result["learning_curve"] = {
                        "train_sizes":   [int(s) for s in lc_sizes],
                        "train_scores":  [round(float(s.mean()), 4) for s in lc_train_sc],
                        "val_scores":    [round(float(s.mean()), 4) for s in lc_val_sc],
                        "metric_label":  sel_label,
                        "cv_folds":      _lc_folds,
                    }
                except Exception as _lc_err:
                    print(f"Learning curve failed: {_lc_err}", flush=True)
                    automl_result["lc_skip_reason"] = "Could not generate — likely OOM or timeout on current resources"

                p.update(84, "Extracting feature importances…")
                automl_result["feature_importance"] = _extract_feature_importances(
                    pipeline, num_cols, cat_cols)
                rule_exp = _rule_explanation(
                    automl_result["winner"], automl_result["cv_results"], "classification",
                    automl_result["selection_metric"], automl_result["is_imbalanced"],
                    automl_result["feature_importance"], len(X),
                )
                app_key = os.environ.get("ANTHROPIC_API_KEY", "")
                if app_key:
                    p.update(86, "Generating AI explanation…")
                    llm_exp = _llm_explanation(
                        app_key, automl_result["winner"], automl_result["cv_results"],
                        "classification", automl_result["selection_metric"],
                        automl_result["is_imbalanced"], automl_result["feature_importance"],
                        len(X),
                    )
                    automl_result["explanation"]        = llm_exp or {"why_won": rule_exp, "score_analysis": "", "key_drivers": "", "recommendations": []}
                    automl_result["explanation_source"] = "app_key" if llm_exp else "rule"
                else:
                    automl_result["explanation"]        = {"why_won": rule_exp, "score_analysis": "", "key_drivers": "", "recommendations": []}
                    automl_result["explanation_source"] = "rule"
                automl_result["can_upgrade"] = automl_result["explanation_source"] == "rule"

        else:  # regression
            _actuals_data = None
            p.update(10, "Preparing regression target…")
            y_num = pd.to_numeric(_y, errors="coerce")
            y_enc = y_num.fillna(float(y_num.median()))

            if _algorithm == "AutoML":
                try:
                    X_cv, y_cv = _cv_sample(X, y_enc)
                    cv_split   = KFold(n_splits=5, shuffle=True, random_state=42)

                    cv_results = []

                    _pct_steps_r = [12, 26, 40, 55, 70]
                    _model_idx_r = 0

                    if "Random Forest" in _selected_models:
                        p.update(_pct_steps_r[_model_idx_r % 5], "Testing Random Forest (5-fold CV)…")
                        _model_idx_r += 1
                        try:
                            rf_pl  = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                               ("model", RandomForestRegressor(n_estimators=100, random_state=42))])
                            _rf_folds_r  = cross_val_score(rf_pl, X_cv, y_cv, cv=cv_split, scoring="neg_mean_absolute_error")
                            cv_results.append({"algorithm": "Random Forest", "score": round(-float(_rf_folds_r.mean()), 4), "fold_scores": [round(-float(s), 4) for s in _rf_folds_r]})
                        except Exception as _e:
                            print(f"Random Forest CV failed: {_e}", flush=True)

                    if "XGBoost" in _selected_models:
                        p.update(_pct_steps_r[_model_idx_r % 5], "Testing XGBoost (5-fold CV)…")
                        _model_idx_r += 1
                        try:
                            xgb_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                               ("model", XGBRegressor(n_estimators=100, random_state=42, verbosity=0))])
                            _xgb_folds_r = cross_val_score(xgb_pl, X_cv, y_cv, cv=cv_split, scoring="neg_mean_absolute_error")
                            cv_results.append({"algorithm": "XGBoost", "score": round(-float(_xgb_folds_r.mean()), 4), "fold_scores": [round(-float(s), 4) for s in _xgb_folds_r]})
                        except Exception as _e:
                            print(f"XGBoost CV failed: {_e}", flush=True)

                    if "LightGBM" in _selected_models:
                        p.update(_pct_steps_r[_model_idx_r % 5], "Testing LightGBM (5-fold CV)…")
                        _model_idx_r += 1
                        try:
                            lgb_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                               ("model", LGBMRegressor(n_estimators=100, random_state=42, verbose=-1))])
                            _lgb_folds_r = cross_val_score(lgb_pl, X_cv, y_cv, cv=cv_split, scoring="neg_mean_absolute_error")
                            cv_results.append({"algorithm": "LightGBM", "score": round(-float(_lgb_folds_r.mean()), 4), "fold_scores": [round(-float(s), 4) for s in _lgb_folds_r]})
                        except Exception as _e:
                            print(f"LightGBM CV failed: {_e}", flush=True)

                    if "CatBoost" in _selected_models:
                        p.update(_pct_steps_r[_model_idx_r % 5], "Testing CatBoost (5-fold CV)…")
                        _model_idx_r += 1
                        try:
                            cat_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                               ("model", CatBoostRegressor(iterations=100, random_seed=42, verbose=0))])
                            _cat_folds_r = cross_val_score(cat_pl, X_cv, y_cv, cv=cv_split, scoring="neg_mean_absolute_error")
                            cv_results.append({"algorithm": "CatBoost", "score": round(-float(_cat_folds_r.mean()), 4), "fold_scores": [round(-float(s), 4) for s in _cat_folds_r]})
                        except Exception as _e:
                            print(f"CatBoost CV failed: {_e}", flush=True)

                    if "Extra Trees" in _selected_models:
                        p.update(_pct_steps_r[_model_idx_r % 5], "Testing Extra Trees (5-fold CV)…")
                        _model_idx_r += 1
                        try:
                            et_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                              ("model", ExtraTreesRegressor(n_estimators=100, random_state=42))])
                            _et_folds_r = cross_val_score(et_pl, X_cv, y_cv, cv=cv_split, scoring="neg_mean_absolute_error")
                            cv_results.append({"algorithm": "Extra Trees", "score": round(-float(_et_folds_r.mean()), 4), "fold_scores": [round(-float(s), 4) for s in _et_folds_r]})
                        except Exception as _e:
                            print(f"Extra Trees CV failed: {_e}", flush=True)

                    if "Decision Tree" in _selected_models:
                        p.update(_pct_steps_r[_model_idx_r % 5], "Testing Decision Tree (5-fold CV)…")
                        _model_idx_r += 1
                        try:
                            dt_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                              ("model", DecisionTreeRegressor(random_state=42))])
                            _dt_folds_r = cross_val_score(dt_pl, X_cv, y_cv, cv=cv_split, scoring="neg_mean_absolute_error")
                            cv_results.append({"algorithm": "Decision Tree", "score": round(-float(_dt_folds_r.mean()), 4), "fold_scores": [round(-float(s), 4) for s in _dt_folds_r]})
                        except Exception as _e:
                            print(f"Decision Tree CV failed: {_e}", flush=True)

                    if "KNN" in _selected_models:
                        p.update(_pct_steps_r[_model_idx_r % 5], "Testing KNN (5-fold CV)…")
                        _model_idx_r += 1
                        try:
                            knn_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                               ("model", KNeighborsRegressor(n_neighbors=5))])
                            _knn_folds_r = cross_val_score(knn_pl, X_cv, y_cv, cv=cv_split, scoring="neg_mean_absolute_error")
                            cv_results.append({"algorithm": "KNN", "score": round(-float(_knn_folds_r.mean()), 4), "fold_scores": [round(-float(s), 4) for s in _knn_folds_r]})
                        except Exception as _e:
                            print(f"KNN CV failed: {_e}", flush=True)

                    if "Ridge" in _selected_models:
                        p.update(_pct_steps_r[_model_idx_r % 5], "Testing Ridge (5-fold CV)…")
                        _model_idx_r += 1
                        try:
                            ridge_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                                 ("model", RidgeRegressor(alpha=1.0))])
                            _ridge_folds_r = cross_val_score(ridge_pl, X_cv, y_cv, cv=cv_split, scoring="neg_mean_absolute_error")
                            cv_results.append({"algorithm": "Ridge", "score": round(-float(_ridge_folds_r.mean()), 4), "fold_scores": [round(-float(s), 4) for s in _ridge_folds_r]})
                        except Exception as _e:
                            print(f"Ridge CV failed: {_e}", flush=True)

                    if "Lasso" in _selected_models:
                        p.update(_pct_steps_r[_model_idx_r % 5], "Testing Lasso (5-fold CV)…")
                        _model_idx_r += 1
                        try:
                            lasso_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                                 ("model", Lasso(alpha=1.0, max_iter=5000))])
                            _lasso_folds_r = cross_val_score(lasso_pl, X_cv, y_cv, cv=cv_split, scoring="neg_mean_absolute_error")
                            cv_results.append({"algorithm": "Lasso", "score": round(-float(_lasso_folds_r.mean()), 4), "fold_scores": [round(-float(s), 4) for s in _lasso_folds_r]})
                        except Exception as _e:
                            print(f"Lasso CV failed: {_e}", flush=True)

                    if "ElasticNet" in _selected_models:
                        p.update(_pct_steps_r[_model_idx_r % 5], "Testing ElasticNet (5-fold CV)…")
                        _model_idx_r += 1
                        try:
                            enet_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                                ("model", ElasticNet(alpha=1.0, max_iter=5000))])
                            _enet_folds_r = cross_val_score(enet_pl, X_cv, y_cv, cv=cv_split, scoring="neg_mean_absolute_error")
                            cv_results.append({"algorithm": "ElasticNet", "score": round(-float(_enet_folds_r.mean()), 4), "fold_scores": [round(-float(s), 4) for s in _enet_folds_r]})
                        except Exception as _e:
                            print(f"ElasticNet CV failed: {_e}", flush=True)

                    if "SVR" in _selected_models:
                        p.update(_pct_steps_r[_model_idx_r % 5], "Testing SVR (5-fold CV)…")
                        _model_idx_r += 1
                        try:
                            svr_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                               ("model", SVR(kernel="rbf"))])
                            _svr_folds_r = cross_val_score(svr_pl, X_cv, y_cv, cv=cv_split, scoring="neg_mean_absolute_error")
                            cv_results.append({"algorithm": "SVR", "score": round(-float(_svr_folds_r.mean()), 4), "fold_scores": [round(-float(s), 4) for s in _svr_folds_r]})
                        except Exception as _e:
                            print(f"SVR CV failed: {_e}", flush=True)

                    if "Gradient Boosting" in _selected_models:
                        p.update(_pct_steps_r[_model_idx_r % 5], "Testing Gradient Boosting (5-fold CV)…")
                        _model_idx_r += 1
                        try:
                            gb_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                              ("model", GradientBoostingRegressor(n_estimators=100, random_state=42))])
                            _gb_folds_r = cross_val_score(gb_pl, X_cv, y_cv, cv=cv_split, scoring="neg_mean_absolute_error")
                            cv_results.append({"algorithm": "Gradient Boosting", "score": round(-float(_gb_folds_r.mean()), 4), "fold_scores": [round(-float(s), 4) for s in _gb_folds_r]})
                        except Exception as _e:
                            print(f"Gradient Boosting CV failed: {_e}", flush=True)

                    if not cv_results:
                        raise RuntimeError("All selected models failed CV")

                    winner = min(cv_results, key=lambda r: r["score"])["algorithm"]
                    _effective_algorithm = winner

                    if winner == "XGBoost":
                        estimator = XGBRegressor(n_estimators=100, random_state=42, verbosity=0)
                    elif winner == "LightGBM":
                        estimator = LGBMRegressor(n_estimators=100, random_state=42, verbose=-1)
                    elif winner == "CatBoost":
                        estimator = CatBoostRegressor(iterations=100, random_seed=42, verbose=0)
                    elif winner == "Extra Trees":
                        estimator = ExtraTreesRegressor(n_estimators=100, random_state=42)
                    elif winner == "Decision Tree":
                        estimator = DecisionTreeRegressor(random_state=42)
                    elif winner == "KNN":
                        estimator = KNeighborsRegressor(n_neighbors=5)
                    elif winner == "Ridge":
                        estimator = RidgeRegressor(alpha=1.0)
                    elif winner == "Lasso":
                        estimator = Lasso(alpha=1.0, max_iter=5000)
                    elif winner == "ElasticNet":
                        estimator = ElasticNet(alpha=1.0, max_iter=5000)
                    elif winner == "SVR":
                        estimator = SVR(kernel="rbf")
                    elif winner == "Gradient Boosting":
                        estimator = GradientBoostingRegressor(n_estimators=100, random_state=42)
                    else:
                        estimator = RandomForestRegressor(n_estimators=100, random_state=42)

                    automl_result = {
                        "winner":           winner,
                        "selection_metric": "MAE",
                        "is_imbalanced":    False,
                        "n_rows":           len(X),
                        "n_input_cols":     len(X.columns),
                        "cv_results":       cv_results,
                        "task":             "regression",
                        "gpu":              _detect_gpu(),
                    }

                    if _tune:
                        p.update(65, f"Winner: {winner}. Tuning with Optuna ({_n_trials} trials)…")
                        try:
                            _best_params_r, _best_val_r = _optuna_tune(
                                winner, "regression", X_cv, y_cv, transformers,
                                cv_split, _n_trials, False,
                                lambda t, s: p.update(
                                    65 + int(t / _n_trials * 13),
                                    f"Optuna trial {t}/{_n_trials} — best MAE: {-s:.4f}",
                                ),
                            )
                            estimator = _build_tuned_estimator(winner, "regression", _best_params_r, False)
                            automl_result["optuna_params"]     = _best_params_r
                            automl_result["optuna_best_score"] = round(-_best_val_r, 4)
                            automl_result["optuna_n_trials"]   = _n_trials
                            p.update(78, f"Tuning done. Training {winner} with best params…")
                        except Exception as _oe:
                            print(f"Optuna tuning failed, using default params: {_oe}", flush=True)
                            p.update(78, f"Tuning failed — using default {winner} params…")
                    else:
                        p.update(65, f"Winner: {winner}. Training on full dataset…")

                except Exception as _exc:
                    print(f"AutoML CV failed, falling back to Random Forest: {_exc}", flush=True)
                    estimator = RandomForestRegressor(n_estimators=100, random_state=42)
                    _effective_algorithm = "Random Forest"

            else:
                if _algorithm == "XGBoost":
                    estimator = XGBRegressor(n_estimators=100, random_state=42, verbosity=0)
                elif _algorithm == "LightGBM":
                    estimator = LGBMRegressor(n_estimators=100, random_state=42, verbose=-1)
                elif _algorithm == "CatBoost":
                    estimator = CatBoostRegressor(iterations=100, random_seed=42, verbose=0)
                elif _algorithm == "Gradient Boosting":
                    estimator = GradientBoostingRegressor(n_estimators=100, random_state=42)
                else:
                    estimator = RandomForestRegressor(n_estimators=100, random_state=42)

            pipeline = Pipeline([("prep", preprocessor), ("model", estimator)])
            split    = 0.2 if len(X) >= 10 else 0.1
            X_train, X_test, y_train, y_test = train_test_split(X, y_enc, test_size=split, random_state=42)
            if automl_result:
                automl_result["n_train"] = len(X_train)
                automl_result["n_test"]  = len(X_test)
            train_pct = (79 if (_tune and automl_result) else 68 if automl_result else 20)
            p.update(train_pct, f"Training {_effective_algorithm} regressor…")
            pipeline.fit(X_train, y_train)
            p.update(82, "Evaluating on test set…")
            import numpy as np  # noqa: PLC0415
            y_pred       = pipeline.predict(X_test)
            mae          = mean_absolute_error(y_test, y_pred)
            metric       = f"±{mae:.2f}"
            metric_label = "MAE"
            rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
            r2   = r2_score(y_test, y_pred)
            extra_metrics = [{"label": "RMSE", "value": f"{rmse:.2f}"}]
            if r2 >= 0.60:
                extra_metrics.append({"label": "R²", "value": f"{r2:.3f}"})

            # Persist actuals for scatter plot endpoint
            import random as _rnd_act  # noqa: PLC0415
            _ya = np.array(y_test)
            _yp = np.array(y_pred)
            _n_act = len(_ya)
            _act_idxs = sorted(_rnd_act.sample(range(_n_act), min(300, _n_act)))
            _actuals_data: dict = {
                "actual":    [round(float(v), 4) for v in _ya[_act_idxs]],
                "predicted": [round(float(v), 4) for v in _yp[_act_idxs]],
                "mae":  round(float(mae), 4),
                "rmse": round(float(rmse), 4),
                "residual_std": round(float(np.std(_ya - _yp)), 4),
            }
            if r2 >= 0.60:
                _actuals_data["r2"] = round(float(r2), 4)

            if automl_result:
                y_test_arr = np.array(y_test)
                mape    = float(mean_absolute_percentage_error(y_test_arr, y_pred))
                med_ae  = float(median_absolute_error(y_test_arr, y_pred))
                max_err = float(np.max(np.abs(y_test_arr - y_pred)))
                wm_reg = {
                    "mae":       round(float(mae),    4),
                    "rmse":      round(float(rmse),   4),
                    "mape":      round(mape,           4),
                    "max_error": round(max_err,        4),
                    "median_ae": round(med_ae,         4),
                }
                if r2 >= 0.60:
                    wm_reg["r2"] = round(float(r2), 4)
                automl_result["winner_metrics"] = wm_reg

                # Scatter: predicted vs actual (sample to 300)
                import random as _rnd
                n_pts = len(y_test_arr)
                idxs  = sorted(_rnd.sample(range(n_pts), min(300, n_pts)))
                automl_result["scatter_actual"]    = [round(float(v), 4) for v in y_test_arr[idxs]]
                automl_result["scatter_predicted"] = [round(float(v), 4) for v in y_pred[idxs]]

                # Learning curve — adaptive CV folds (3-fold for large datasets)
                _lc_rows_r  = len(X)
                _lc_folds_r = 3 if _lc_rows_r > 5000 else 5
                automl_result["lc_cv_folds"] = _lc_folds_r
                try:
                    p.update(83, "Computing learning curve…")
                    lc_sizes, lc_train_sc, lc_val_sc = learning_curve(
                        clone(pipeline), X, y_enc,
                        cv=KFold(n_splits=_lc_folds_r, shuffle=True, random_state=42),
                        train_sizes=[0.2, 0.4, 0.6, 0.8, 1.0],
                        scoring="neg_mean_absolute_error", n_jobs=1,
                    )
                    automl_result["learning_curve"] = {
                        "train_sizes":  [int(s) for s in lc_sizes],
                        "train_scores": [round(-float(s.mean()), 4) for s in lc_train_sc],
                        "val_scores":   [round(-float(s.mean()), 4) for s in lc_val_sc],
                        "metric_label": "MAE",
                        "cv_folds":     _lc_folds_r,
                    }
                except Exception as _lc_err:
                    print(f"Learning curve failed: {_lc_err}", flush=True)
                    automl_result["lc_skip_reason"] = "Could not generate — likely OOM or timeout on current resources"

                p.update(84, "Extracting feature importances…")
                automl_result["feature_importance"] = _extract_feature_importances(
                    pipeline, num_cols, cat_cols)
                rule_exp = _rule_explanation(
                    automl_result["winner"], automl_result["cv_results"], "regression",
                    "MAE", False, automl_result["feature_importance"], len(X),
                )
                app_key = os.environ.get("ANTHROPIC_API_KEY", "")
                if app_key:
                    p.update(86, "Generating AI explanation…")
                    llm_exp = _llm_explanation(
                        app_key, automl_result["winner"], automl_result["cv_results"],
                        "regression", "MAE", False,
                        automl_result["feature_importance"], len(X),
                    )
                    automl_result["explanation"]        = llm_exp or {"why_won": rule_exp, "score_analysis": "", "key_drivers": "", "recommendations": []}
                    automl_result["explanation_source"] = "app_key" if llm_exp else "rule"
                else:
                    automl_result["explanation"]        = {"why_won": rule_exp, "score_analysis": "", "key_drivers": "", "recommendations": []}
                    automl_result["explanation_source"] = "rule"
                automl_result["can_upgrade"] = automl_result["explanation_source"] == "rule"

        p.update(88, "Building schema…")
        feature_cols = [c for c in _pre_fe_cols_ if c in X.columns]
        fields: list = []
        sample: dict = {}
        for col in feature_cols:
            is_cat = not pd.api.types.is_numeric_dtype(X[col]) or X[col].nunique() <= 15
            if is_cat:
                opts     = [{"value": str(v), "label": str(v)} for v in sorted(X[col].dropna().unique())]
                col_vals = X[col].dropna()
                n_col    = len(col_vals)
                cat_freq = {str(v): round(int((col_vals == v).sum()) / n_col, 6) for v in col_vals.unique()} if n_col else {}
                fields.append({"name": col, "label": col, "type": "select", "options": opts, "cat_freq": cat_freq})
                mode = X[col].mode()
                sample[col] = str(mode[0]) if not mode.empty else ""
            else:
                cmin = round(float(X[col].min()), 4)
                cmax = round(float(X[col].max()), 4)
                rng  = cmax - cmin
                step = max(round(rng / 100, 4) if rng > 0 else 1.0, 0.0001)
                fields.append({"name": col, "label": col, "type": "number",
                               "min": cmin, "max": cmax, "step": step})
                sample[col] = round(float(X[col].median()), 4)

        output_meta: dict = {"type": _task}
        if _task == "clustering":
            output_meta["n_clusters"] = _n_clusters
        else:
            output_meta["target_col"] = _target_col
        if _task == "classification" and le is not None:
            output_meta["class_names"] = [str(c) for c in le.classes_]

        schema = {
            "id":          _model_id,
            "title":       _model_name,
            "description": f"Auto-trained {_task} model using {_effective_algorithm}.",
            "task":        _task,
            "accent":      _accent,
            "model":       _effective_algorithm,
            "metric":      metric,
            "metricLabel": metric_label,
            "id_cols":      [],
            "ensure_cols":  [],
            "pre_fe_cols":   _pre_fe_cols_,
            "pre_fe_sample": _pre_fe_sample_,
            "fields":        fields,
            "sample":        sample,
            "output":      output_meta,
        }

        p.update(93, "Saving model to disk…")
        with open(os.path.join(SCHEMA_DIR, f"{_model_id}.json"), "w") as f:
            json.dump(schema, f, indent=2)
        joblib.dump(pipeline, os.path.join(MODEL_DIR, f"{_model_id}_pipeline.pkl"))
        joblib.dump(_fe_tfm, os.path.join(MODEL_DIR, f"{_model_id}_fe.pkl"))
        if le is not None:
            joblib.dump(le, os.path.join(MODEL_DIR, f"{_model_id}_labels.pkl"))
        if _actuals_data is not None:
            _act_path = os.path.join(MODEL_DIR, f"{_model_id}_actuals.json")
            with open(_act_path, "w") as _af:
                json.dump(_actuals_data, _af)
            print(f"ACTUALS: saved {_act_path} ({len(_actuals_data.get('actual', []))} pts)", flush=True)
        else:
            print(f"ACTUALS: _actuals_data is None for {_model_id} (task={_task})", flush=True)
        _upload_model_to_hf(_model_id)

        MODELS[_model_id] = {
            "pipeline": pipeline,
            "le":       le,
            "classes":  le.classes_.tolist() if le is not None else None,
            "schema":   schema,
            "fe":       _fe_tfm,
            "actuals":  _actuals_data,
        }

        resp = {
            "id":           _model_id,
            "title":        _model_name,
            "metric":       metric,
            "metricLabel":  metric_label,
            "extraMetrics": extra_metrics,
            "accent":       _accent,
        }
        if plot_data is not None:
            resp["plot_data"]  = plot_data
            resp["n_clusters"] = _n_clusters
        if automl_result is not None:
            resp["automl"] = automl_result

        p.finish(result=resp)

    return StreamingResponse(
        streaming_task.stream(_work),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/explain")
async def explain_automl(request: Request):
    """Generate an LLM explanation for an AutoML result.

    user_api_key is optional — if omitted, the server falls back to its own
    env-configured keys (GEMINI_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, GROQ_API_KEY).
    """
    body            = await request.json()
    automl          = body.get("automl_data", {})
    user_key        = (body.get("user_api_key") or "").strip()
    provider        = (body.get("provider") or "gemini-2.5").strip().lower()
    custom_base_url = (body.get("custom_base_url") or "").strip()
    custom_model    = (body.get("custom_model") or "").strip()

    # Fall back to server env key when no user key is supplied
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

    if user_key:
        llm_exp = _llm_explanation(user_key, winner, cv_results, task,
                                   sel_metric, is_imbal, feat_imp, n_rows, provider,
                                   custom_base_url, custom_model)
        if llm_exp:
            return {"explanation": llm_exp, "source": provider}

    rule_exp = _rule_explanation(winner, cv_results, task, sel_metric,
                                 is_imbal, feat_imp, n_rows)
    return {"explanation": {"why_won": rule_exp, "score_analysis": "", "key_drivers": "", "recommendations": []}, "source": "rule"}


app.include_router(_shap_router.router)
app.include_router(_pipeline_router.router)
app.include_router(_training_router.router)
app.include_router(_drift_router.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
