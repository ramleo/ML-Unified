#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Any, Dict
import joblib, pandas as pd, json, os

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
FRONTEND   = os.path.join(HERE, "..", "frontend", "index.html")

MODELS: Dict[str, Any] = {}

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
        return FileResponse(FRONTEND)
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
def predict(model_id: str, data: Dict[str, Any] = Body(...)):
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
    else:
        pred = float(pipeline.predict(df)[0])
        return {"prediction": pred}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)