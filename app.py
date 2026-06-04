#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
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
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_absolute_error, silhouette_score
from typing import Any, Dict
import io
import joblib
import json
import os
import re
import threading
import pandas as pd

app = FastAPI(title="ML Unified")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

def _load():
    for fname in sorted(os.listdir(SCHEMA_DIR)):
        if not fname.endswith(".json"):
            continue
        mid    = fname[:-5]
        schema = json.load(open(os.path.join(SCHEMA_DIR, fname)))
        pipeline = joblib.load(os.path.join(MODEL_DIR, f"{mid}_pipeline.pkl"))
        le_path  = os.path.join(MODEL_DIR, f"{mid}_labels.pkl")
        le       = joblib.load(le_path) if os.path.exists(le_path) else None
        MODELS[mid] = {
            "pipeline": pipeline,
            "le":       le,
            "classes":  le.classes_.tolist() if le is not None else None,
            "schema":   schema,
        }

_load()

@app.get("/")
def index():
    if os.path.exists(FRONTEND):
        return FileResponse(
            FRONTEND,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    return {"message": "ML Unified API — see /docs"}

@app.get("/health")
def health():
    return {"status": "ok", "models": list(MODELS.keys())}

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

    # Add ensure_cols as None if not provided (e.g. Customer Feedback for insurance)
    for col in schema.get("ensure_cols", []):
        row.setdefault(col, None)

    df = pd.DataFrame([row])

    # Inject NaN for id columns the pipeline was trained with
    for col in schema.get("id_cols", []):
        df[col] = float("nan")

    # Parse date field into numeric components if schema defines one
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

    # Optional color column — separate before preprocessing
    color_labels = None
    if color_col and color_col in df.columns:
        color_labels = df[color_col].astype(str).tolist()
        X = df.drop(columns=[color_col]).copy()
    else:
        X = df.copy()

    # Drop 100%-unique string columns
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

    prep = ColumnTransformer(transformers, remainder="drop")
    X_prep = prep.fit_transform(X)
    n_samples = len(X_prep)

    stats = {"algorithm": algorithm, "rows": n_samples}
    cluster_ids = None

    if algorithm == "K-Means":
        k   = max(2, min(n_clusters, n_samples - 1))
        km  = KMeans(n_clusters=k, random_state=42, n_init=10)
        cluster_ids = km.fit_predict(X_prep).tolist()
        sil = silhouette_score(X_prep, cluster_ids) if k > 1 and len(set(cluster_ids)) > 1 else 0.0
        sizes = {str(i): cluster_ids.count(i) for i in range(k)}
        stats.update({"n_clusters": k, "silhouette": round(sil, 3), "cluster_sizes": sizes})

    elif algorithm == "DBSCAN":
        # Run on PCA-reduced space — full high-dimensional distances make eps=0.5 useless
        n_comp_db = min(max(2, n_dims), X_prep.shape[1])
        pca_db    = PCA(n_components=n_comp_db)
        coords_db = pca_db.fit_transform(X_prep)
        eps_val   = max(0.01, eps)
        db        = DBSCAN(eps=eps_val, min_samples=min_samples)
        cluster_ids = db.fit_predict(coords_db).tolist()
        n_found  = len(set(c for c in cluster_ids if c >= 0))
        n_noise  = cluster_ids.count(-1)
        sil = silhouette_score(coords_db, cluster_ids) if n_found > 1 and len(set(cluster_ids)) > 1 else 0.0
        stats.update({"n_clusters": n_found, "n_noise": n_noise, "silhouette": round(sil, 3)})
        def pt_db(i):
            p = {"x": round(float(coords_db[i, 0]), 4),
                 "y": round(float(coords_db[i, 1] if n_comp_db > 1 else 0.0), 4),
                 "cluster": int(cluster_ids[i]),
                 "label": color_labels[i] if color_labels else ""}
            if n_dims >= 3 and n_comp_db >= 3:
                p["z"] = round(float(coords_db[i, 2]), 4)
            return p
        plot_data = [pt_db(i) for i in range(n_samples)]
        if color_labels:
            unique_labels = sorted(set(color_labels))
            stats["color_labels"] = unique_labels
        stats["color_col"] = color_col if color_col else ""
        return {"plot_data": plot_data, "stats": stats}

    elif algorithm == "t-SNE":
        perp   = min(float(perplexity), max(5.0, (n_samples - 1) / 3))
        t_comp = min(max(2, n_dims), 3)
        tsne   = TSNE(n_components=t_comp, random_state=42, perplexity=perp,
                      max_iter=1000, init="pca" if X_prep.shape[1] >= 2 else "random")
        coords = tsne.fit_transform(X_prep)
        stats.update({"perplexity": round(perp, 1), "kl_divergence": round(float(tsne.kl_divergence_), 4),
                       "color_col": color_col if color_col else ""})
        def pt_tsne(i):
            p = {"x": round(float(coords[i, 0]), 4), "y": round(float(coords[i, 1]), 4),
                 "cluster": -1, "label": color_labels[i] if color_labels else ""}
            if n_dims >= 3 and t_comp >= 3:
                p["z"] = round(float(coords[i, 2]), 4)
            return p
        plot_data = [pt_tsne(i) for i in range(n_samples)]
        if color_labels:
            unique_labels = sorted(set(color_labels))
            label_to_id   = {lbl: i for i, lbl in enumerate(unique_labels)}
            for p in plot_data:
                p["cluster"] = label_to_id[p["label"]]
            stats["color_labels"] = unique_labels
        return {"plot_data": plot_data, "stats": stats}

    elif algorithm == "PCA":
        n_comp = min(max(2, n_dims), X_prep.shape[1])
        pca    = PCA(n_components=n_comp)
        coords = pca.fit_transform(X_prep)
        ev     = pca.explained_variance_ratio_.tolist()
        stats.update({
            "explained_variance": [round(v * 100, 2) for v in ev],
            "total_variance":     round(sum(ev) * 100, 2),
            "color_col":          color_col if color_col else "",
        })
        def pt_pca(i):
            p = {"x": round(float(coords[i, 0]), 4),
                 "y": round(float(coords[i, 1] if n_comp > 1 else 0.0), 4),
                 "cluster": -1, "label": color_labels[i] if color_labels else ""}
            if n_dims >= 3 and n_comp >= 3:
                p["z"] = round(float(coords[i, 2]), 4)
            return p
        plot_data = [pt_pca(i) for i in range(n_samples)]
        if color_labels:
            unique_labels = sorted(set(color_labels))
            label_to_id   = {lbl: i for i, lbl in enumerate(unique_labels)}
            for p in plot_data:
                p["cluster"] = label_to_id[p["label"]]
            stats["color_labels"] = unique_labels
        return {"plot_data": plot_data, "stats": stats}
    else:
        raise HTTPException(400, f"Unknown algorithm: {algorithm}")

    # For K-Means and DBSCAN: reduce to 2D/3D with PCA for scatter plot
    n_comp  = min(max(2, n_dims), X_prep.shape[1])
    pca_viz = PCA(n_components=n_comp)
    coords  = pca_viz.fit_transform(X_prep)
    def pt_cl(i):
        p = {"x": round(float(coords[i, 0]), 4),
             "y": round(float(coords[i, 1] if n_comp > 1 else 0.0), 4),
             "cluster": int(cluster_ids[i]),
             "label": color_labels[i] if color_labels else ""}
        if n_dims >= 3 and n_comp >= 3:
            p["z"] = round(float(coords[i, 2]), 4)
        return p
    plot_data = [pt_cl(i) for i in range(n_samples)]
    if color_labels:
        unique_labels = sorted(set(color_labels))
        label_to_id   = {lbl: i for i, lbl in enumerate(unique_labels)}
        stats["color_labels"] = unique_labels
    stats["color_col"] = color_col if color_col else ""
    return {"plot_data": plot_data, "stats": stats}


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

    # Drop 100%-unique string columns (IDs / free-text names)
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

    preprocessor = ColumnTransformer(transformers, remainder="drop")

    le = None
    plot_data = None

    # Lazy-import boosting libraries — each ~20-200 MB of shared libs;
    # keeping them out of module-level imports frees ~200 MB at startup.
    from xgboost import XGBClassifier, XGBRegressor          # noqa: PLC0415
    from lightgbm import LGBMClassifier, LGBMRegressor        # noqa: PLC0415
    from catboost import CatBoostClassifier, CatBoostRegressor  # noqa: PLC0415

    if task == "clustering":
        preprocessor.fit(X)
        X_prep = preprocessor.transform(X)
        n_comp = min(2, X_prep.shape[1])

        if algorithm == "t-SNE":
            reducer = TSNE(n_components=n_comp, random_state=42, perplexity=min(30, max(5, len(X)//10)))
            coords  = reducer.fit_transform(X_prep)
            labels  = [-1] * len(X)
            metric, metric_label = "N/A", "Visualization"
            pipeline = Pipeline([("prep", preprocessor)])
        elif algorithm == "PCA":
            reducer = PCA(n_components=n_comp)
            coords  = reducer.fit_transform(X_prep)
            labels  = [-1] * len(X)
            ev      = reducer.explained_variance_ratio_
            metric, metric_label = f"{sum(ev)*100:.1f}%", "Variance Explained"
            pipeline = Pipeline([("prep", preprocessor)])
        elif algorithm == "DBSCAN":
            db      = DBSCAN(eps=0.5, min_samples=5)
            labels  = db.fit_predict(X_prep).tolist()
            n_found = len(set(lbl for lbl in labels if lbl >= 0))
            sil     = silhouette_score(X_prep, labels) if n_found > 1 and len(set(labels)) > 1 else 0.0
            metric, metric_label = f"{sil:.2f}", "Silhouette"
            pca_viz = PCA(n_components=n_comp)
            coords  = pca_viz.fit_transform(X_prep)
            pipeline = Pipeline([("prep", preprocessor)])
        else:  # K-Means
            km       = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            pipeline = Pipeline([("prep", preprocessor), ("model", km)])
            pipeline.fit(X)
            labels   = pipeline.predict(X).tolist()
            sil      = silhouette_score(X_prep, labels) if n_clusters > 1 and len(set(labels)) > 1 else 0.0
            metric, metric_label = f"{sil:.2f}", "Silhouette"
            pca_viz  = PCA(n_components=n_comp)
            coords   = pca_viz.fit_transform(X_prep)

        if n_comp == 1:
            plot_data = [{"x": round(float(coords[i, 0]), 4), "y": 0.0, "cluster": int(labels[i])} for i in range(len(coords))]
        else:
            plot_data = [{"x": round(float(coords[i, 0]), 4), "y": round(float(coords[i, 1]), 4), "cluster": int(labels[i])} for i in range(len(coords))]
    elif task == "classification":
        le    = LabelEncoder()
        y_enc = le.fit_transform(y.astype(str))
        if algorithm == "XGBoost":
            estimator = XGBClassifier(n_estimators=100, random_state=42, eval_metric="logloss", verbosity=0)
        elif algorithm == "LightGBM":
            estimator = LGBMClassifier(n_estimators=100, random_state=42, verbose=-1)
        elif algorithm == "CatBoost":
            estimator = CatBoostClassifier(iterations=100, random_seed=42, verbose=0)
        elif algorithm == "Random Forest":
            estimator = RandomForestClassifier(n_estimators=100, random_state=42)
        else:
            estimator = GradientBoostingClassifier(n_estimators=100, random_state=42)
        pipeline = Pipeline([("prep", preprocessor), ("model", estimator)])
        split    = 0.2 if len(X) >= 10 else 0.1
        X_train, X_test, y_train, y_test = train_test_split(X, y_enc, test_size=split, random_state=42)
        pipeline.fit(X_train, y_train)
        score        = accuracy_score(y_test, pipeline.predict(X_test))
        metric       = f"{score * 100:.1f}%"
        metric_label = "Accuracy"
    else:
        y_num = pd.to_numeric(y, errors="coerce")
        y_enc = y_num.fillna(float(y_num.median()))
        if algorithm == "XGBoost":
            estimator = XGBRegressor(n_estimators=100, random_state=42, verbosity=0)
        elif algorithm == "LightGBM":
            estimator = LGBMRegressor(n_estimators=100, random_state=42, verbose=-1)
        elif algorithm == "CatBoost":
            estimator = CatBoostRegressor(iterations=100, random_seed=42, verbose=0)
        elif algorithm == "Gradient Boosting":
            estimator = GradientBoostingRegressor(n_estimators=100, random_state=42)
        else:
            estimator = RandomForestRegressor(n_estimators=100, random_state=42)
        pipeline = Pipeline([("prep", preprocessor), ("model", estimator)])
        split    = 0.2 if len(X) >= 10 else 0.1
        X_train, X_test, y_train, y_test = train_test_split(X, y_enc, test_size=split, random_state=42)
        pipeline.fit(X_train, y_train)
        mae          = mean_absolute_error(y_test, pipeline.predict(X_test))
        metric       = f"±{mae:.0f}"
        metric_label = "MAE"

    # Build schema fields
    feature_cols = X.columns.tolist()
    fields, sample = [], {}
    for col in feature_cols:
        is_cat = not pd.api.types.is_numeric_dtype(X[col]) or X[col].nunique() <= 15
        if is_cat:
            opts = [{"value": str(v), "label": str(v)} for v in sorted(X[col].dropna().unique())]
            fields.append({"name": col, "label": col, "type": "select", "options": opts})
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

    output_meta: dict = {"type": task}
    if task == "clustering":
        output_meta["n_clusters"] = n_clusters
    else:
        output_meta["target_col"] = target_col
    if task == "classification" and le is not None:
        output_meta["class_names"] = [str(c) for c in le.classes_]

    schema = {
        "id":          model_id,
        "title":       model_name,
        "description": f"Auto-trained {task} model using {algorithm}.",
        "task":        task,
        "accent":      accent,
        "model":       algorithm,
        "metric":      metric,
        "metricLabel": metric_label,
        "id_cols":     [],
        "ensure_cols": [],
        "fields":      fields,
        "sample":      sample,
        "output":      output_meta,
    }

    with open(os.path.join(SCHEMA_DIR, f"{model_id}.json"), "w") as f:
        json.dump(schema, f, indent=2)
    joblib.dump(pipeline, os.path.join(MODEL_DIR, f"{model_id}_pipeline.pkl"))
    if le is not None:
        joblib.dump(le, os.path.join(MODEL_DIR, f"{model_id}_labels.pkl"))

    MODELS[model_id] = {
        "pipeline": pipeline,
        "le":       le,
        "classes":  le.classes_.tolist() if le is not None else None,
        "schema":   schema,
    }

    resp = {
        "id":          model_id,
        "title":       model_name,
        "metric":      metric,
        "metricLabel": metric_label,
        "accent":      accent,
    }
    if plot_data is not None:
        resp["plot_data"]  = plot_data
        resp["n_clusters"] = n_clusters
    return resp


# ── Image Classification ────────────────────────────────────────────────────
# Uses ONNX Runtime (~15 MB) + models downloaded lazily from ONNX Model Zoo.
# tensorflow-cpu was removed — it exceeds Render free tier disk limits (~1 GB installed).

VISION_CACHE_DIR = os.path.join(HERE, "vision_cache")
os.makedirs(VISION_CACHE_DIR, exist_ok=True)

_IMAGE_MODEL_CONFIGS: Dict[str, Dict] = {
    "mobilenetv2": {
        "label":       "MobileNetV2",
        "input_size":  224,
        "description": "Fast & lightweight — ideal for real-time inference",
        "url": "https://media.githubusercontent.com/media/onnx/models/main/validated/vision/classification/mobilenet/model/mobilenetv2-12.onnx",
        "size_mb":     14,
    },
    "resnet50": {
        "label":       "ResNet50",
        "input_size":  224,
        "description": "Classic deep residual network — reliable baseline",
        "url": "https://media.githubusercontent.com/media/onnx/models/main/validated/vision/classification/resnet/model/resnet50-v2-7.onnx",
        "size_mb":     98,
    },
    "squeezenet": {
        "label":       "SqueezeNet 1.1",
        "input_size":  224,
        "description": "Tiny & fast — AlexNet accuracy at 50× fewer parameters",
        "url": "https://media.githubusercontent.com/media/onnx/models/main/validated/vision/classification/squeezenet/model/squeezenet1.1-7.onnx",
        "size_mb":     5,
    },
    "googlenet": {
        "label":       "GoogLeNet",
        "input_size":  224,
        "description": "Multi-scale Inception architecture — strong general accuracy",
        "url": "https://media.githubusercontent.com/media/onnx/models/main/validated/vision/classification/googlenet/model/googlenet-12.onnx",
        "size_mb":     28,
    },
}

_IMAGENET_LABELS: list  = []
_img_cache:       Dict[str, Any] = {}
_img_active:      list  = [None]


def _ensure_labels():
    if _IMAGENET_LABELS:
        return
    labels_path = os.path.join(VISION_CACHE_DIR, "imagenet_classes.txt")
    if not os.path.exists(labels_path):
        import urllib.request  # noqa: PLC0415
        urllib.request.urlretrieve(
            "https://raw.githubusercontent.com/pytorch/hub/master/imagenet_classes.txt",
            labels_path,
        )
    with open(labels_path) as f:
        _IMAGENET_LABELS[:] = [line.strip() for line in f.readlines()]


def _ensure_model_file(model_id: str) -> str:
    path = os.path.join(VISION_CACHE_DIR, f"{model_id}.onnx")
    if not os.path.exists(path):
        import urllib.request  # noqa: PLC0415
        urllib.request.urlretrieve(_IMAGE_MODEL_CONFIGS[model_id]["url"], path)
    return path


@app.get("/imagenet-classes")
def list_imagenet_classes():
    try:
        _ensure_labels()
    except Exception as e:
        raise HTTPException(500, f"Failed to load ImageNet labels: {e}")
    return {"classes": _IMAGENET_LABELS, "total": len(_IMAGENET_LABELS)}


@app.get("/image-models")
def list_image_models():
    return [
        {
            "id":          k,
            "label":       v["label"],
            "description": v["description"],
            "input_size":  v["input_size"],
            "size_mb":     v["size_mb"],
        }
        for k, v in _IMAGE_MODEL_CONFIGS.items()
    ]


@app.post("/classify-image")
async def classify_image(
    file:       UploadFile = File(...),
    model_name: str        = Form("mobilenetv2"),
    top_k:      int        = Form(5),
):
    if model_name not in _IMAGE_MODEL_CONFIGS:
        raise HTTPException(400, f"Unknown model '{model_name}'. Choose from: {list(_IMAGE_MODEL_CONFIGS)}")
    top_k = max(1, min(top_k, 10))
    cfg   = _IMAGE_MODEL_CONFIGS[model_name]

    # Download labels once
    try:
        _ensure_labels()
    except Exception as e:
        raise HTTPException(500, f"Failed to load ImageNet labels: {e}")

    # Lazy-load ONNX session — one model in memory at a time
    if _img_active[0] != model_name:
        _img_cache.clear()
        try:
            import onnxruntime as ort  # noqa: PLC0415
            model_path = _ensure_model_file(model_name)
            session    = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
            _img_cache["session"] = session
            _img_active[0]        = model_name
        except Exception as e:
            raise HTTPException(500, f"Failed to load model '{model_name}': {e}")

    session = _img_cache["session"]
    size    = cfg["input_size"]

    content = await file.read()
    try:
        from PIL import Image as PILImage  # noqa: PLC0415
        import numpy as np                 # noqa: PLC0415
        img  = PILImage.open(io.BytesIO(content)).convert("RGB")
        img  = img.resize((size, size), PILImage.LANCZOS)
        arr  = np.array(img, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr  = (arr - mean) / std
        arr  = arr.transpose(2, 0, 1)       # HWC → CHW
        arr  = np.expand_dims(arr, axis=0)  # → (1, 3, H, W)
    except Exception as e:
        raise HTTPException(400, f"Could not process image: {e}")

    input_name = session.get_inputs()[0].name
    scores     = session.run(None, {input_name: arr})[0][0]  # (1000,)

    import numpy as np  # noqa: PLC0415 — already cached by Python; just re-binds name
    scores = np.exp(scores - scores.max())
    scores = scores / scores.sum()

    top_idx        = scores.argsort()[::-1][:top_k]
    top_confidence = float(scores[top_idx[0]])

    return {
        "model":          model_name,
        "model_label":    cfg["label"],
        "low_confidence": top_confidence < 0.05,
        "top_confidence": round(top_confidence, 4),
        "predictions": [
            {
                "rank":       i + 1,
                "class_id":   str(top_idx[i]),
                "label":      _IMAGENET_LABELS[top_idx[i]] if top_idx[i] < len(_IMAGENET_LABELS) else f"class_{top_idx[i]}",
                "confidence": round(float(scores[top_idx[i]]), 4),
            }
            for i in range(top_k)
        ],
    }


# ── Image Processing ────────────────────────────────────────────────────────
# Classical image operations via Pillow — no model weights required.

_IMG_OPERATIONS: Dict[str, Dict] = {
    "grayscale":  {"label": "Grayscale",       "params": []},
    "blur":       {"label": "Gaussian Blur",   "params": [{"name": "blur_radius",       "label": "Radius",   "min": 1,    "max": 20,  "default": 3,   "step": 1}]},
    "sharpen":    {"label": "Sharpen",         "params": [{"name": "sharpen_factor",    "label": "Strength", "min": 1.0,  "max": 5.0, "default": 2.0, "step": 0.5}]},
    "edges":      {"label": "Edge Detection",  "params": []},
    "rotate":     {"label": "Rotate",          "params": [{"name": "rotate_angle",      "label": "Angle °",  "min": -180, "max": 180, "default": 90,  "step": 1}]},
    "brightness": {"label": "Brightness",      "params": [{"name": "brightness_factor", "label": "Factor",   "min": 0.1,  "max": 3.0, "default": 1.5, "step": 0.1}]},
    "contrast":   {"label": "Contrast",        "params": [{"name": "contrast_factor",   "label": "Factor",   "min": 0.1,  "max": 3.0, "default": 1.5, "step": 0.1}]},
    "flip_h":     {"label": "Flip Horizontal", "params": []},
    "flip_v":     {"label": "Flip Vertical",   "params": []},
    "emboss":     {"label": "Emboss",          "params": []},
    "invert":     {"label": "Invert Colors",   "params": []},
}

_MAX_IMG_DIM = 1200  # cap output resolution to keep base64 response size reasonable


@app.get("/image-operations")
def list_image_operations():
    return [{"id": k, "label": v["label"], "params": v["params"]} for k, v in _IMG_OPERATIONS.items()]


@app.post("/process-image")
async def process_image(
    file:               UploadFile = File(...),
    operation:          str        = Form(...),
    blur_radius:        float      = Form(3.0),
    sharpen_factor:     float      = Form(2.0),
    rotate_angle:       float      = Form(90.0),
    brightness_factor:  float      = Form(1.5),
    contrast_factor:    float      = Form(1.5),
):
    if operation not in _IMG_OPERATIONS:
        raise HTTPException(400, f"Unknown operation '{operation}'. Choose from: {list(_IMG_OPERATIONS)}")

    content = await file.read()
    try:
        from PIL import Image as PILImage, ImageFilter, ImageEnhance, ImageOps  # noqa: PLC0415
        import base64                                                             # noqa: PLC0415
        img = PILImage.open(io.BytesIO(content)).convert("RGB")
    except Exception as e:
        raise HTTPException(400, f"Could not load image: {e}")

    # Downscale very large images before processing so response stays small
    if max(img.width, img.height) > _MAX_IMG_DIM:
        img.thumbnail((_MAX_IMG_DIM, _MAX_IMG_DIM), PILImage.LANCZOS)

    params_used: Dict[str, Any] = {}

    if operation == "grayscale":
        img = img.convert("L").convert("RGB")
    elif operation == "blur":
        r = max(1, min(int(round(blur_radius)), 20))
        img = img.filter(ImageFilter.GaussianBlur(radius=r))
        params_used["radius"] = r
    elif operation == "sharpen":
        f = round(max(1.0, min(float(sharpen_factor), 5.0)), 1)
        img = ImageEnhance.Sharpness(img).enhance(f)
        params_used["factor"] = f
    elif operation == "edges":
        img = img.filter(ImageFilter.FIND_EDGES)
    elif operation == "rotate":
        a = max(-180.0, min(float(rotate_angle), 180.0))
        img = img.rotate(a, expand=True)
        params_used["angle"] = a
    elif operation == "brightness":
        f = round(max(0.1, min(float(brightness_factor), 3.0)), 1)
        img = ImageEnhance.Brightness(img).enhance(f)
        params_used["factor"] = f
    elif operation == "contrast":
        f = round(max(0.1, min(float(contrast_factor), 3.0)), 1)
        img = ImageEnhance.Contrast(img).enhance(f)
        params_used["factor"] = f
    elif operation == "flip_h":
        img = ImageOps.mirror(img)
    elif operation == "flip_v":
        img = ImageOps.flip(img)
    elif operation == "emboss":
        img = img.filter(ImageFilter.EMBOSS)
    elif operation == "invert":
        img = ImageOps.invert(img)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    return {
        "operation":       operation,
        "operation_label": _IMG_OPERATIONS[operation]["label"],
        "params_used":     params_used,
        "image_b64":       f"data:image/png;base64,{b64}",
        "width":           img.width,
        "height":          img.height,
    }


# ── Object Detection ────────────────────────────────────────────────────────
# Uses SSD-12 (ResNet-34 backbone) from ONNX Model Zoo — Apache 2.0.
# Draws bounding boxes server-side with PIL and returns annotated image.

_COCO_CLASSES: list = [
    "__background__",
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]  # index 0 = background; 1–80 = COCO classes

_DETECTION_MODEL_CONFIGS: Dict[str, Dict] = {
    "tiny_yolov3": {
        "label":       "TinyYOLOv3",
        "description": "Tiny YOLOv3 — lightweight 35 MB model, COCO 80 classes (MIT license)",
        "url": (
            "https://media.githubusercontent.com/media/onnx/models/main/"
            "validated/vision/object_detection_segmentation/tiny-yolov3/model/tiny-yolov3-11.onnx"
        ),
        "input_size": 416,
        "size_mb":    35,
    },
}

_BOX_PALETTE = [
    "#e879f9", "#38bdf8", "#34d399", "#fbbf24",
    "#f87171", "#fb923c", "#818cf8", "#4ade80",
    "#f472b6", "#2dd4bf", "#facc15", "#a78bfa",
]

# Shared slot for large vision models (detection + segmentation).
# Only ONE model is kept in RAM at a time to stay within Render free tier (512 MB).
_large_vision_cache:  Dict[str, Any] = {}   # keys: "model_type", "model_id", "session"
_large_vision_lock:   threading.Lock  = threading.Lock()


def _ensure_det_model(model_id: str) -> str:
    path = os.path.join(VISION_CACHE_DIR, f"det_{model_id}.onnx")
    if not os.path.exists(path):
        import urllib.request  # noqa: PLC0415
        urllib.request.urlretrieve(_DETECTION_MODEL_CONFIGS[model_id]["url"], path)
    return path


def _load_det_session(model_id: str):
    """Load detection model into the shared slot, evicting whatever was there."""
    import onnxruntime as ort  # noqa: PLC0415
    path = _ensure_det_model(model_id)
    with _large_vision_lock:
        _large_vision_cache.clear()
        session = ort.InferenceSession(path)
        _large_vision_cache["model_type"] = "det"
        _large_vision_cache["model_id"]   = model_id
        _large_vision_cache["session"]    = session
    return session


@app.get("/detect-models")
def list_detect_models():
    return [
        {
            "id":          k,
            "label":       v["label"],
            "description": v["description"],
            "input_size":  v["input_size"],
            "size_mb":     v["size_mb"],
        }
        for k, v in _DETECTION_MODEL_CONFIGS.items()
    ]


@app.post("/detect-objects")
async def detect_objects(
    file:       UploadFile = File(...),
    model_name: str        = Form("tiny_yolov3"),
    confidence: float      = Form(0.3),
    max_dets:   int        = Form(20),
):
    if model_name not in _DETECTION_MODEL_CONFIGS:
        raise HTTPException(400, f"Unknown model '{model_name}'. Choose from: {list(_DETECTION_MODEL_CONFIGS)}")

    confidence = max(0.05, min(float(confidence), 0.95))
    max_dets   = max(1, min(int(max_dets), 50))
    cfg = _DETECTION_MODEL_CONFIGS[model_name]

    # Use shared slot — load only if not already the active model
    with _large_vision_lock:
        cached = (
            _large_vision_cache.get("model_type") == "det"
            and _large_vision_cache.get("model_id") == model_name
        )
        session = _large_vision_cache.get("session") if cached else None

    if session is None:
        try:
            session = _load_det_session(model_name)
        except Exception as e:
            raise HTTPException(500, f"Failed to load model '{model_name}': {e}")
    size    = cfg["input_size"]

    content = await file.read()
    try:
        from PIL import Image as PILImage, ImageDraw  # noqa: PLC0415
        import numpy as np                             # noqa: PLC0415
        import base64                                  # noqa: PLC0415
        img = PILImage.open(io.BytesIO(content)).convert("RGB")
    except Exception as e:
        raise HTTPException(400, f"Could not load image: {e}")

    orig_w, orig_h = img.width, img.height

    # TinyYOLOv3 — preprocess: resize to 416×416, normalise to [0,1] (no ImageNet mean/std)
    resized = img.resize((size, size), PILImage.LANCZOS)
    arr     = np.array(resized, dtype=np.float32) / 255.0
    arr     = arr.transpose(2, 0, 1)                       # HWC → CHW
    arr     = np.expand_dims(arr, axis=0)                  # → (1, 3, 416, 416)
    image_shape = np.array([[orig_h, orig_w]], dtype=np.float32)

    try:
        outputs = session.run(None, {"input_1": arr, "image_shape": image_shape})
    except Exception as e:
        raise HTTPException(500, f"Inference failed: {e}")

    # TinyYOLOv3 outputs:
    #   outputs[0] boxes   (1, max_boxes, 4)  — y1,x1,y2,x2 in original pixel coords
    #   outputs[1] scores  (1, 80, max_boxes) — per-class confidence
    #   outputs[2] indices (num_det, 3)        — [batch, class_id, box_idx] (post-NMS)
    boxes   = outputs[0][0]   # (max_boxes, 4)
    scores  = outputs[1][0]   # (80, max_boxes)
    indices = outputs[2]      # (num_det, 3)

    detections = []
    for row in indices:
        class_idx = int(row[1])
        box_idx   = int(row[2])
        s = float(scores[class_idx, box_idx])
        if s < confidence:
            continue

        name_idx = class_idx + 1           # offset: _COCO_CLASSES[0] = "__background__"
        if name_idx >= len(_COCO_CLASSES):
            continue

        b = boxes[box_idx]                 # [y1, x1, y2, x2] in original pixels
        y1, x1 = float(b[0]), float(b[1])
        y2, x2 = float(b[2]), float(b[3])

        x1, y1 = max(0.0, x1), max(0.0, y1)
        x2, y2 = min(float(orig_w), x2), min(float(orig_h), y2)

        if x2 <= x1 or y2 <= y1:
            continue

        detections.append({
            "class_id":   name_idx,
            "label":      _COCO_CLASSES[name_idx],
            "confidence": round(s, 4),
            "box":        {"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)},
        })

    detections.sort(key=lambda d: d["confidence"], reverse=True)
    detections = detections[:max_dets]

    # Draw boxes on original image
    draw = ImageDraw.Draw(img)
    for det in detections:
        color = _BOX_PALETTE[det["class_id"] % len(_BOX_PALETTE)]
        b     = det["box"]
        draw.rectangle([b["x1"], b["y1"], b["x2"], b["y2"]], outline=color, width=3)
        text   = f"{det['label']} {det['confidence']:.0%}"
        tx, ty = b["x1"], max(0, b["y1"] - 15)
        tw     = len(text) * 6 + 6
        draw.rectangle([tx, ty, tx + tw, ty + 14], fill=color)
        draw.text((tx + 3, ty + 2), text, fill="#000000")

    # Cap output resolution
    if max(img.width, img.height) > _MAX_IMG_DIM:
        img.thumbnail((_MAX_IMG_DIM, _MAX_IMG_DIM), PILImage.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    return {
        "model":                model_name,
        "model_label":          cfg["label"],
        "count":                len(detections),
        "confidence_threshold": confidence,
        "detections":           detections,
        "image_b64":            f"data:image/png;base64,{b64}",
        "orig_width":           orig_w,
        "orig_height":          orig_h,
    }


# ── Image Segmentation ───────────────────────────────────────────────────────

_SEG_CLASSES: list = [
    "__background__",
    "aeroplane", "bicycle", "bird", "boat", "bottle",
    "bus", "car", "cat", "chair", "cow",
    "diningtable", "dog", "horse", "motorbike", "person",
    "pottedplant", "sheep", "sofa", "train", "tvmonitor",
]

# Perceptually distinct palette (index 0 = background = transparent)
_SEG_PALETTE: list = [
    (0,   0,   0),    # background
    (128, 0,   0),    # aeroplane
    (0,   128, 0),    # bicycle
    (128, 128, 0),    # bird
    (0,   0,   128),  # boat
    (128, 0,   128),  # bottle
    (0,   128, 128),  # bus
    (128, 128, 128),  # car
    (64,  0,   0),    # cat
    (192, 0,   0),    # chair
    (64,  128, 0),    # cow
    (192, 128, 0),    # diningtable
    (64,  0,   128),  # dog
    (192, 0,   128),  # horse
    (64,  128, 128),  # motorbike
    (192, 128, 128),  # person
    (0,   64,  0),    # pottedplant
    (128, 64,  0),    # sheep
    (0,   192, 0),    # sofa
    (128, 192, 0),    # train
    (0,   64,  128),  # tvmonitor
]

_SEGMENTATION_MODEL_CONFIGS: Dict[str, Dict] = {
    "fcn_resnet50": {
        "label":       "FCN-ResNet50",
        "description": "Fully Convolutional Network — ResNet-50 backbone, Pascal VOC 21 classes",
        "url": (
            "https://media.githubusercontent.com/media/onnx/models/main/"
            "validated/vision/object_detection_segmentation/fcn/model/fcn-resnet50-11.onnx"
        ),
        "input_size":  480,
        "size_mb":     135,
    },
}

def _ensure_seg_model(model_id: str) -> str:
    import urllib.request  # noqa: PLC0415
    cfg  = _SEGMENTATION_MODEL_CONFIGS[model_id]
    path = os.path.join(VISION_CACHE_DIR, f"{model_id}.onnx")
    if not os.path.exists(path):
        urllib.request.urlretrieve(cfg["url"], path)
    return path


def _load_seg_session(model_id: str):
    """Load segmentation model into the shared slot, evicting whatever was there."""
    import onnxruntime as ort  # noqa: PLC0415
    path = _ensure_seg_model(model_id)
    with _large_vision_lock:
        _large_vision_cache.clear()
        session = ort.InferenceSession(path)
        _large_vision_cache["model_type"] = "seg"
        _large_vision_cache["model_id"]   = model_id
        _large_vision_cache["session"]    = session
    return session


@app.get("/seg-models")
def list_seg_models():
    return [
        {
            "id":          k,
            "label":       v["label"],
            "description": v["description"],
            "size_mb":     v["size_mb"],
        }
        for k, v in _SEGMENTATION_MODEL_CONFIGS.items()
    ]


@app.post("/segment-image")
async def segment_image(
    file:       UploadFile = File(...),
    model_name: str        = Form("fcn_resnet50"),
):
    if model_name not in _SEGMENTATION_MODEL_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model_name}")

    from PIL import Image as PILImage  # noqa: PLC0415
    import numpy as np                 # noqa: PLC0415
    import base64                      # noqa: PLC0415

    raw = await file.read()
    img = PILImage.open(io.BytesIO(raw)).convert("RGB")
    orig_w, orig_h = img.width, img.height

    cfg       = _SEGMENTATION_MODEL_CONFIGS[model_name]
    size      = cfg["input_size"]

    # Resize for inference (preserve aspect ratio)
    img_r = img.copy()
    img_r.thumbnail((size, size), PILImage.LANCZOS)

    # Use shared slot — load only if not already the active model
    with _large_vision_lock:
        cached = (
            _large_vision_cache.get("model_type") == "seg"
            and _large_vision_cache.get("model_id") == model_name
        )
        session = _large_vision_cache.get("session") if cached else None

    if session is None:
        try:
            session = _load_seg_session(model_name)
        except Exception as e:
            raise HTTPException(500, f"Failed to load model '{model_name}': {e}")

    arr = np.array(img_r, dtype=np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr  = (arr - mean) / std
    arr  = arr.transpose(2, 0, 1)[np.newaxis]  # (1, 3, H, W)

    input_name  = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name
    logits = session.run([output_name], {input_name: arr})[0]  # (1, 21, H, W)

    label_map = np.argmax(logits[0], axis=0).astype(np.uint8)  # (H, W)

    # Scale label map back to original image size
    lm_img    = PILImage.fromarray(label_map, mode="L")
    lm_resized = lm_img.resize((orig_w, orig_h), PILImage.NEAREST)
    label_full = np.array(lm_resized)

    # Build RGBA colour mask
    colour_mask = np.zeros((orig_h, orig_w, 4), dtype=np.uint8)
    classes_found = {}
    for cls_id, rgb in enumerate(_SEG_PALETTE):
        if cls_id == 0:
            continue  # skip background
        px = np.where(label_full == cls_id)
        count = len(px[0])
        if count == 0:
            continue
        colour_mask[px[0], px[1], :3] = rgb
        colour_mask[px[0], px[1],  3] = 180  # ~70% opacity
        classes_found[cls_id] = count

    mask_pil   = PILImage.fromarray(colour_mask, mode="RGBA")
    orig_rgba  = img.convert("RGBA")
    composite  = PILImage.alpha_composite(orig_rgba, mask_pil).convert("RGB")

    buf = io.BytesIO()
    composite.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    total_px = orig_w * orig_h
    detected = [
        {
            "class_id":    cid,
            "label":       _SEG_CLASSES[cid],
            "pixel_count": cnt,
            "percentage":  round(cnt / total_px * 100, 2),
            "color":       "#{:02x}{:02x}{:02x}".format(*_SEG_PALETTE[cid]),
        }
        for cid, cnt in sorted(classes_found.items(), key=lambda x: -x[1])
    ]

    return {
        "model":       model_name,
        "model_label": cfg["label"],
        "classes_found": detected,
        "image_b64":   f"data:image/png;base64,{b64}",
        "orig_width":  orig_w,
        "orig_height": orig_h,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)