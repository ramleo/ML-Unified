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
from xgboost import XGBClassifier, XGBRegressor
from lightgbm import LGBMClassifier, LGBMRegressor
from catboost import CatBoostClassifier, CatBoostRegressor
from sklearn.cluster import KMeans, DBSCAN
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)