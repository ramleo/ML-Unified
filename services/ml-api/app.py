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
from sklearn.ensemble import (RandomForestClassifier, GradientBoostingClassifier,
                               RandomForestRegressor, GradientBoostingRegressor)
from sklearn.cluster import KMeans, DBSCAN
# xgboost, lightgbm, catboost are imported lazily inside train_model to save ~200 MB
# of shared-library memory at startup (critical on Render free tier 512 MB limit)
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold, KFold
from sklearn.metrics import (accuracy_score, mean_absolute_error, mean_squared_error,
                             silhouette_score, f1_score, roc_auc_score, r2_score)
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

# ── Request monitoring ────────────────────────────────────────────────────────
_SKIP_PATHS = {"/", "/health", "/metrics", "/app-config", "/favicon.ico"}
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
    for fpath in _HF_PKL_FILES:
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
        MODELS[mid] = {
            "pipeline": pipeline,
            "le":       le,
            "classes":  le.classes_.tolist() if le is not None else None,
            "schema":   schema,
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

    pipeline = m["pipeline"]
    le       = m["le"]

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

    columns = [
        {
            "name":       col,
            "dtype":      str(df[col].dtype),
            "nunique":    int(df[col].nunique()),
            "is_numeric": bool(pd.api.types.is_numeric_dtype(df[col])),
        }
        for col in df.columns
    ]

    suggested_target = df.columns[-1]
    t = df[suggested_target]
    suggested_task = (
        "classification"
        if (not pd.api.types.is_numeric_dtype(t) or t.nunique() <= 10)
        else "regression"
    )

    return {
        "columns":          columns,
        "suggested_target": suggested_target,
        "suggested_task":   suggested_task,
        "rows":             len(df),
        "accent_palette":   ACCENT_PALETTE,
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


def _llm_explanation(api_key: str, winner: str, cv_results: list, task: str,
                     selection_metric: str, is_imbalanced: bool,
                     feature_importance: list, n_rows: int):
    try:
        import anthropic  # noqa: PLC0415
        client = anthropic.Anthropic(api_key=api_key)
        if task == "regression":
            results_text = "\n".join(
                f"  {r['algorithm']}: MAE = {r['score']:.4f}" for r in cv_results
            )
        else:
            results_text = "\n".join(
                f"  {r['algorithm']}: {selection_metric} = {r['score'] * 100:.2f}%"
                for r in cv_results
            )
        fi_text = "\n".join(
            f"  {i + 1}. {f['feature']} ({f['importance']:.1f}%)"
            for i, f in enumerate(feature_importance[:5])
        ) if feature_importance else "  Not available"
        imbalance_note = (
            " The dataset has class imbalance, so F1-macro was used as the "
            "selection metric instead of accuracy."
        ) if is_imbalanced else ""
        prompt = (
            f"You are explaining AutoML model selection results to a data analyst.\n\n"
            f"Dataset: {n_rows:,} rows, task: {task}{imbalance_note}\n"
            f"3 algorithms tested with 3-fold cross-validation:\n{results_text}\n\n"
            f"Winner: {winner}\n\n"
            f"Top features by importance:\n{fi_text}\n\n"
            f"Write 2–3 clear sentences explaining why {winner} was selected and what "
            f"the top features suggest about what drives the predictions. Be concise "
            f"and avoid jargon. No bullet points."
        )
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception:
        return None


@app.post("/train")
async def train_model(
    file:       UploadFile = File(...),
    model_name: str        = Form(...),
    target_col: str        = Form(""),
    task:       str        = Form(...),
    algorithm:  str        = Form(...),
    accent:     str        = Form(...),
    n_clusters: int        = Form(3),
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

    num_cols = X.select_dtypes(include="number").columns.tolist()
    cat_cols = X.select_dtypes(exclude="number").columns.tolist()

    transformers = []
    if num_cols:
        transformers.append(("num", Pipeline([("imp", SimpleImputer(strategy="median"))]), num_cols))
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
    _n_clusters = n_clusters
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
                    sel_metric = "f1_macro" if is_imbal else "accuracy"
                    sel_label  = "F1-macro" if is_imbal else "Accuracy"

                    X_cv, y_cv = _cv_sample(X, y_enc)
                    cv_split   = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)

                    p.update(15, "Testing Random Forest (3-fold CV)…")
                    rf_pl  = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                       ("model", RandomForestClassifier(n_estimators=100, random_state=42))])
                    rf_cv  = float(cross_val_score(rf_pl, X_cv, y_cv, cv=cv_split, scoring=sel_metric).mean())

                    p.update(35, "Testing XGBoost (3-fold CV)…")
                    xgb_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                       ("model", XGBClassifier(n_estimators=100, random_state=42,
                                                               eval_metric="logloss", verbosity=0))])
                    xgb_cv = float(cross_val_score(xgb_pl, X_cv, y_cv, cv=cv_split, scoring=sel_metric).mean())

                    p.update(55, "Testing LightGBM (3-fold CV)…")
                    lgb_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                       ("model", LGBMClassifier(n_estimators=100, random_state=42, verbose=-1))])
                    lgb_cv = float(cross_val_score(lgb_pl, X_cv, y_cv, cv=cv_split, scoring=sel_metric).mean())

                    cv_results = [
                        {"algorithm": "Random Forest", "score": round(rf_cv,  4)},
                        {"algorithm": "XGBoost",       "score": round(xgb_cv, 4)},
                        {"algorithm": "LightGBM",      "score": round(lgb_cv, 4)},
                    ]
                    winner = max(cv_results, key=lambda r: r["score"])["algorithm"]
                    _effective_algorithm = winner

                    if winner == "XGBoost":
                        estimator = XGBClassifier(n_estimators=100, random_state=42,
                                                  eval_metric="logloss", verbosity=0)
                    elif winner == "LightGBM":
                        estimator = LGBMClassifier(n_estimators=100, random_state=42, verbose=-1)
                    else:
                        estimator = RandomForestClassifier(n_estimators=100, random_state=42)

                    automl_result = {
                        "winner":           winner,
                        "selection_metric": sel_label,
                        "is_imbalanced":    is_imbal,
                        "n_rows":           len(X),
                        "cv_results":       cv_results,
                        "task":             "classification",
                    }
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
            X_train, X_test, y_train, y_test = train_test_split(X, y_enc, test_size=split, random_state=42)
            train_pct = 68 if automl_result else 20
            p.update(train_pct, f"Training {_effective_algorithm} classifier…")
            pipeline.fit(X_train, y_train)
            p.update(82, "Evaluating on test set…")
            y_pred       = pipeline.predict(X_test)
            score        = accuracy_score(y_test, y_pred)
            metric       = f"{score * 100:.1f}%"
            metric_label = "Accuracy"
            extra_metrics = []
            f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)
            extra_metrics.append({"label": "F1 (weighted)", "value": f"{f1:.3f}"})
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
                pass

            if automl_result:
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
                    automl_result["explanation"]        = llm_exp or rule_exp
                    automl_result["explanation_source"] = "app_key" if llm_exp else "rule"
                else:
                    automl_result["explanation"]        = rule_exp
                    automl_result["explanation_source"] = "rule"
                automl_result["can_upgrade"] = automl_result["explanation_source"] == "rule"

        else:  # regression
            p.update(10, "Preparing regression target…")
            y_num = pd.to_numeric(_y, errors="coerce")
            y_enc = y_num.fillna(float(y_num.median()))

            if _algorithm == "AutoML":
                try:
                    X_cv, y_cv = _cv_sample(X, y_enc)
                    cv_split   = KFold(n_splits=3, shuffle=True, random_state=42)

                    p.update(15, "Testing Random Forest (3-fold CV)…")
                    rf_pl  = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                       ("model", RandomForestRegressor(n_estimators=100, random_state=42))])
                    rf_cv  = -float(cross_val_score(rf_pl, X_cv, y_cv, cv=cv_split,
                                                    scoring="neg_mean_absolute_error").mean())

                    p.update(35, "Testing XGBoost (3-fold CV)…")
                    xgb_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                       ("model", XGBRegressor(n_estimators=100, random_state=42, verbosity=0))])
                    xgb_cv = -float(cross_val_score(xgb_pl, X_cv, y_cv, cv=cv_split,
                                                    scoring="neg_mean_absolute_error").mean())

                    p.update(55, "Testing LightGBM (3-fold CV)…")
                    lgb_pl = Pipeline([("prep", ColumnTransformer(transformers, remainder="drop")),
                                       ("model", LGBMRegressor(n_estimators=100, random_state=42, verbose=-1))])
                    lgb_cv = -float(cross_val_score(lgb_pl, X_cv, y_cv, cv=cv_split,
                                                    scoring="neg_mean_absolute_error").mean())

                    cv_results = [
                        {"algorithm": "Random Forest", "score": round(rf_cv,  4)},
                        {"algorithm": "XGBoost",       "score": round(xgb_cv, 4)},
                        {"algorithm": "LightGBM",      "score": round(lgb_cv, 4)},
                    ]
                    winner = min(cv_results, key=lambda r: r["score"])["algorithm"]
                    _effective_algorithm = winner

                    if winner == "XGBoost":
                        estimator = XGBRegressor(n_estimators=100, random_state=42, verbosity=0)
                    elif winner == "LightGBM":
                        estimator = LGBMRegressor(n_estimators=100, random_state=42, verbose=-1)
                    else:
                        estimator = RandomForestRegressor(n_estimators=100, random_state=42)

                    automl_result = {
                        "winner":           winner,
                        "selection_metric": "MAE",
                        "is_imbalanced":    False,
                        "n_rows":           len(X),
                        "cv_results":       cv_results,
                        "task":             "regression",
                    }
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
            train_pct = 68 if automl_result else 20
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

            if automl_result:
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
                    automl_result["explanation"]        = llm_exp or rule_exp
                    automl_result["explanation_source"] = "app_key" if llm_exp else "rule"
                else:
                    automl_result["explanation"]        = rule_exp
                    automl_result["explanation_source"] = "rule"
                automl_result["can_upgrade"] = automl_result["explanation_source"] == "rule"

        p.update(88, "Building schema…")
        feature_cols = X.columns.tolist()
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
            "id_cols":     [],
            "ensure_cols": [],
            "fields":      fields,
            "sample":      sample,
            "output":      output_meta,
        }

        p.update(93, "Saving model to disk…")
        with open(os.path.join(SCHEMA_DIR, f"{_model_id}.json"), "w") as f:
            json.dump(schema, f, indent=2)
        joblib.dump(pipeline, os.path.join(MODEL_DIR, f"{_model_id}_pipeline.pkl"))
        if le is not None:
            joblib.dump(le, os.path.join(MODEL_DIR, f"{_model_id}_labels.pkl"))

        MODELS[_model_id] = {
            "pipeline": pipeline,
            "le":       le,
            "classes":  le.classes_.tolist() if le is not None else None,
            "schema":   schema,
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
    """Generate an LLM explanation for an AutoML result using a user-supplied API key."""
    body       = await request.json()
    automl     = body.get("automl_data", {})
    user_key   = (body.get("user_api_key") or "").strip()

    if not user_key:
        raise HTTPException(400, "user_api_key is required")

    winner     = automl.get("winner", "")
    cv_results = automl.get("cv_results", [])
    task       = automl.get("task", "classification")
    sel_metric = automl.get("selection_metric", "Accuracy")
    is_imbal   = automl.get("is_imbalanced", False)
    feat_imp   = automl.get("feature_importance", [])
    n_rows     = automl.get("n_rows", 0)

    llm_exp = _llm_explanation(user_key, winner, cv_results, task,
                               sel_metric, is_imbal, feat_imp, n_rows)
    if llm_exp:
        return {"explanation": llm_exp, "source": "user_key"}

    rule_exp = _rule_explanation(winner, cv_results, task, sel_metric,
                                 is_imbal, feat_imp, n_rows)
    return {"explanation": rule_exp, "source": "rule"}


app.include_router(_shap_router.router)
app.include_router(_pipeline_router.router)
app.include_router(_training_router.router)
app.include_router(_drift_router.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
