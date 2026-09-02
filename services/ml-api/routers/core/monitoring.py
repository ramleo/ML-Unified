"""Monitoring router: /metrics, /models, /schemas, /models/{id}, actuals, unsupervised."""
import collections
import io
import json
import logging
import os
import time
from typing import Dict

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sklearn.cluster import KMeans, DBSCAN
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from routers.core.shared import (
    MODELS, _BUILTIN_IDS, SCHEMA_DIR, MODEL_DIR, _delete_model_from_hf,
)
from shared.progress import StreamingTask

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Request monitoring state (exported for middleware in app.py) ──────────────
_SKIP_PATHS: set = {"/", "/health", "/metrics", "/app-config", "/favicon.ico", "/system-info"}
_req_log: collections.deque = collections.deque(maxlen=1000)
_svc_start: float = time.time()


@router.get("/metrics")
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


@router.get("/models")
def list_models():
    """Every registered model, described.

    Read defensively on purpose. This used to index m["schema"]["title"] and
    friends directly, so a single entry written without a schema — the Pipeline
    Builder's AutoML stage did exactly that — raised KeyError and returned 500
    for the *whole list*, taking the Data Drift tool down with it. One bad
    entry should cost you that entry, not the endpoint.
    """
    out = []
    for mid, m in MODELS.items():
        schema = m.get("schema")
        if not isinstance(schema, dict):
            logger.warning("model '%s' has no schema — listing it with placeholders", mid)
            schema = {}
        out.append({
            "id":          mid,
            "title":       schema.get("title", mid),
            "description": schema.get("description", ""),
            "task":        schema.get("task", m.get("task", "unknown")),
            "accent":      schema.get("accent", "#64748b"),
            "model":       schema.get("model", m.get("algo", "unknown")),
            "metric":      schema.get("metric", ""),
            "metricLabel": schema.get("metricLabel", ""),
            "classes":     m.get("classes"),
            "class_names": (schema.get("output") or {}).get("class_names"),
            "builtin":     mid in _BUILTIN_IDS,
        })
    return out


@router.get("/schemas/{model_id}")
def get_schema(model_id: str):
    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")
    s = dict(MODELS[model_id]["schema"])
    s["classes"]     = MODELS[model_id]["classes"]
    s["class_names"] = s.get("output", {}).get("class_names")
    return s


@router.delete("/models/{model_id}")
def delete_model(model_id: str):
    if model_id in _BUILTIN_IDS:
        raise HTTPException(400, "Cannot delete a built-in demo model.")
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
        try:
            if os.path.exists(_p):
                os.remove(_p)
        except OSError as exc:
            print(f"WARNING: could not remove local file {_p}: {exc}", flush=True)
    _sp = os.path.join(SCHEMA_DIR, f"{model_id}.json")
    try:
        if os.path.exists(_sp):
            os.remove(_sp)
    except OSError as exc:
        print(f"WARNING: could not remove local file {_sp}: {exc}", flush=True)
    _delete_model_from_hf(model_id)
    return {"deleted": model_id}


@router.get("/models/{model_id}/actuals")
def get_actuals(model_id: str):
    if model_id not in MODELS:
        raise HTTPException(404, "Model not found")
    _mem = MODELS[model_id].get("actuals")
    if _mem:
        return _mem
    _path = os.path.join(MODEL_DIR, f"{model_id}_actuals.json")
    if not os.path.exists(_path):
        raise HTTPException(404, "No actuals data — retrain this model to generate it")
    with open(_path) as _f:
        data = json.load(_f)
    MODELS[model_id]["actuals"] = data
    return data


@router.post("/unsupervised")
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
            stats["color_labels"] = unique_labels
        stats["color_col"] = _color_col if _color_col else ""
        p.finish(result={"plot_data": plot_data, "stats": stats})

    return StreamingResponse(
        task.stream(_work),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
