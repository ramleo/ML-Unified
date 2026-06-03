#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import (RandomForestClassifier, GradientBoostingClassifier,
                               RandomForestRegressor, GradientBoostingRegressor)
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_absolute_error, silhouette_score
from typing import Any, Dict
import joblib, pandas as pd, json, os, io, re

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
            n_found = len(set(l for l in labels if l >= 0))
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
        estimator = (
            RandomForestClassifier(n_estimators=100, random_state=42)
            if algorithm == "Random Forest"
            else GradientBoostingClassifier(n_estimators=100, random_state=42)
        )
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
        estimator = (
            GradientBoostingRegressor(n_estimators=100, random_state=42)
            if algorithm == "Gradient Boosting"
            else RandomForestRegressor(n_estimators=100, random_state=42)
        )
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)