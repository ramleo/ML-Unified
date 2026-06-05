import io
import os
from fastapi.testclient import TestClient
from app import app, MODELS, SCHEMA_DIR, MODEL_DIR

client = TestClient(app)

# ── Health & meta ─────────────────────────────────────────────────────────────

def test_metrics_empty():
    """Fresh service returns valid metrics structure."""
    r = client.get("/metrics")
    assert r.status_code == 200
    data = r.json()
    assert data["service"] == "ml-api"
    assert "uptime_s"       in data
    assert "total_requests" in data
    assert "error_rate"     in data
    assert "endpoints"      in data
    assert isinstance(data["endpoints"], list)

def test_metrics_records_requests():
    """After a real request, /metrics logs it."""
    client.get("/models")
    r = client.get("/metrics")
    assert r.status_code == 200
    data = r.json()
    assert data["total_requests"] >= 1
    assert any(e["path"] == "/models" for e in data["endpoints"])

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert isinstance(data["models"], list)
    assert len(data["models"]) >= 4

def test_app_config_default():
    r = client.get("/app-config")
    assert r.status_code == 200
    assert "vision_url" in r.json()

def test_app_config_env(monkeypatch):
    monkeypatch.setenv("ML_VISION_URL", "https://ml-vision.onrender.com")
    r = client.get("/app-config")
    assert r.status_code == 200
    assert r.json()["vision_url"] == "https://ml-vision.onrender.com"

def test_list_models():
    r = client.get("/models")
    assert r.status_code == 200
    models = r.json()
    ids = [m["id"] for m in models]
    assert "iris" in ids
    assert "titanic" in ids
    assert "diabetes" in ids
    assert "insurance" in ids

def test_list_models_fields():
    r = client.get("/models")
    m = next(x for x in r.json() if x["id"] == "iris")
    assert "title" in m
    assert "task" in m
    assert "accent" in m
    assert "metric" in m

# ── Schema ────────────────────────────────────────────────────────────────────

def test_get_schema_iris():
    r = client.get("/schemas/iris")
    assert r.status_code == 200
    s = r.json()
    assert s["id"] == "iris"
    assert s["task"] == "classification"
    assert isinstance(s["fields"], list)
    assert len(s["fields"]) == 4
    assert "sample" in s

def test_get_schema_insurance():
    r = client.get("/schemas/insurance")
    assert r.status_code == 200
    s = r.json()
    assert s["task"] == "regression"
    assert isinstance(s["fields"], list)

def test_get_schema_not_found():
    r = client.get("/schemas/nonexistent")
    assert r.status_code == 404

# ── Predict — classification ──────────────────────────────────────────────────

def test_predict_iris_setosa():
    payload = {"SepalLengthCm": 5.1, "SepalWidthCm": 3.5,
               "PetalLengthCm": 1.4, "PetalWidthCm": 0.2}
    r = client.post("/predict/iris", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "prediction" in data
    assert "probabilities" in data
    assert isinstance(data["probabilities"], list)
    assert len(data["probabilities"]) == 3
    assert abs(sum(data["probabilities"]) - 1.0) < 1e-6

def test_predict_iris_virginica():
    payload = {"SepalLengthCm": 6.7, "SepalWidthCm": 3.0,
               "PetalLengthCm": 5.2, "PetalWidthCm": 2.3}
    r = client.post("/predict/iris", json=payload)
    assert r.status_code == 200
    assert r.json()["prediction"] in ("Iris-setosa", "Iris-versicolor", "Iris-virginica")

def test_predict_titanic():
    payload = {"Pclass": 1, "Sex": "female", "Age": 29.0, "SibSp": 0,
               "Parch": 0, "Fare": 211.3, "Embarked": "S"}
    r = client.post("/predict/titanic", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "prediction" in data
    assert "probabilities" in data

def test_predict_diabetes():
    payload = {"Pregnancies": 2, "Glucose": 138, "BloodPressure": 62,
               "SkinThickness": 35, "Insulin": 0, "BMI": 33.6,
               "DiabetesPedigreeFunction": 0.627, "Age": 47}
    r = client.post("/predict/diabetes", json=payload)
    assert r.status_code == 200
    assert "prediction" in r.json()

# ── Predict — regression ──────────────────────────────────────────────────────

def test_predict_insurance():
    payload = {
        "Age": 35, "Annual Income": 75000, "Number of Dependents": 2,
        "Health Score": 72.5, "Previous Claims": 1, "Vehicle Age": 5,
        "Credit Score": 680, "Insurance Duration": 8,
        "Gender": "Male", "Marital Status": "Married",
        "Education Level": "Bachelor's", "Occupation": "Employed",
        "Location": "Urban", "Policy Type": "Comprehensive",
        "Smoking Status": "No", "Exercise Frequency": "Weekly",
        "Property Type": "House"
    }
    r = client.post("/predict/insurance", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "prediction" in data
    assert isinstance(data["prediction"], float)
    assert data["prediction"] > 0

# ── Predict — error cases ─────────────────────────────────────────────────────

def test_predict_model_not_found():
    r = client.post("/predict/nonexistent", json={"a": 1})
    assert r.status_code == 404

# ── Analyze CSV ───────────────────────────────────────────────────────────────

SAMPLE_CSV = b"col_a,col_b,target\n1,2,0\n3,4,1\n5,6,0\n7,8,1\n9,10,1\n"

def test_analyze_csv_classification():
    r = client.post("/analyze", files={"file": ("test.csv", io.BytesIO(SAMPLE_CSV), "text/csv")})
    assert r.status_code == 200
    data = r.json()
    assert "columns" in data
    assert "suggested_target" in data
    assert "suggested_task" in data
    assert data["rows"] == 5
    assert data["suggested_target"] == "target"
    assert data["suggested_task"] == "classification"

def test_analyze_csv_regression():
    rows = "\n".join(f"{i},{i*2},{1000.5 + i * 237.3}" for i in range(12))
    csv = ("feature1,feature2,price\n" + rows + "\n").encode()
    r = client.post("/analyze", files={"file": ("test.csv", io.BytesIO(csv), "text/csv")})
    assert r.status_code == 200
    data = r.json()
    assert data["suggested_task"] == "regression"

def test_analyze_csv_bad_file():
    r = client.post("/analyze", files={"file": ("test.csv", io.BytesIO(b"not a csv!!@@##"), "text/csv")})
    assert r.status_code in (200, 400)

# ── Unsupervised ──────────────────────────────────────────────────────────────

CLUSTER_CSV = (
    b"x,y,z\n"
    + b"".join(f"{1+i*0.1},{1+i*0.1},{1+i*0.1}\n".encode() for i in range(8))
    + b"".join(f"{5+i*0.1},{5+i*0.1},{5+i*0.1}\n".encode() for i in range(8))
    + b"".join(f"{9+i*0.1},{1+i*0.1},{9+i*0.1}\n".encode() for i in range(8))
)

def test_unsupervised_kmeans():
    r = client.post("/unsupervised", files={"file": ("clusters.csv", io.BytesIO(CLUSTER_CSV), "text/csv")},
                    data={"algorithm": "K-Means", "n_clusters": "3", "n_dims": "2"})
    assert r.status_code == 200
    data = r.json()
    assert "plot_data" in data
    assert "stats" in data
    assert data["stats"].get("n_clusters") == 3

def test_unsupervised_pca():
    r = client.post("/unsupervised", files={"file": ("clusters.csv", io.BytesIO(CLUSTER_CSV), "text/csv")},
                    data={"algorithm": "PCA", "n_dims": "2"})
    assert r.status_code == 200
    data = r.json()
    assert "plot_data" in data

def test_unsupervised_dbscan():
    r = client.post("/unsupervised", files={"file": ("clusters.csv", io.BytesIO(CLUSTER_CSV), "text/csv")},
                    data={"algorithm": "DBSCAN", "eps": "0.5", "min_samples": "2", "n_dims": "2"})
    assert r.status_code == 200
    assert "plot_data" in r.json()

# ── Train ─────────────────────────────────────────────────────────────────────

def _cleanup_model(model_id: str):
    MODELS.pop(model_id, None)
    for path in [
        os.path.join(SCHEMA_DIR, f"{model_id}.json"),
        os.path.join(MODEL_DIR,  f"{model_id}_pipeline.pkl"),
        os.path.join(MODEL_DIR,  f"{model_id}_labels.pkl"),
    ]:
        if os.path.exists(path):
            os.remove(path)

def test_train_classification():
    rows = "\n".join(f"{i},{i * 2},{i % 2}" for i in range(20))
    csv  = ("feature1,feature2,target\n" + rows + "\n").encode()

    r = client.post("/train",
        files={"file": ("train.csv", io.BytesIO(csv), "text/csv")},
        data={"model_name": "CI Test Classifier", "target_col": "target",
              "task": "classification", "algorithm": "Random Forest",
              "accent": "#818cf8"})
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "ci-test-classifier"
    assert "%" in data["metric"]
    assert data["metricLabel"] == "Accuracy"

    ids = [m["id"] for m in client.get("/models").json()]
    assert "ci-test-classifier" in ids

    pred = client.post("/predict/ci-test-classifier", json={"feature1": 5.0, "feature2": 10.0})
    assert pred.status_code == 200
    assert "prediction" in pred.json()

    _cleanup_model("ci-test-classifier")

def test_train_regression():
    rows = "\n".join(f"{i},{i * 1.5},{100.0 + i * 23.7}" for i in range(20))
    csv  = ("feat_a,feat_b,price\n" + rows + "\n").encode()

    r = client.post("/train",
        files={"file": ("train.csv", io.BytesIO(csv), "text/csv")},
        data={"model_name": "CI Test Regressor", "target_col": "price",
              "task": "regression", "algorithm": "Random Forest",
              "accent": "#34d399"})
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "ci-test-regressor"
    assert data["metricLabel"] == "MAE"
    assert "±" in data["metric"]

    ids = [m["id"] for m in client.get("/models").json()]
    assert "ci-test-regressor" in ids

    pred = client.post("/predict/ci-test-regressor", json={"feat_a": 5.0, "feat_b": 7.5})
    assert pred.status_code == 200
    assert isinstance(pred.json()["prediction"], float)

    _cleanup_model("ci-test-regressor")

def test_train_invalid_task():
    csv = b"a,b,c\n1,2,3\n4,5,6\n"
    r = client.post("/train",
        files={"file": ("train.csv", io.BytesIO(csv), "text/csv")},
        data={"model_name": "Bad Task Model", "target_col": "c",
              "task": "invalid_task", "algorithm": "Random Forest",
              "accent": "#818cf8"})
    assert r.status_code == 400

def test_train_missing_target_col():
    csv = b"a,b,c\n1,2,3\n4,5,6\n"
    r = client.post("/train",
        files={"file": ("train.csv", io.BytesIO(csv), "text/csv")},
        data={"model_name": "Bad Target Model", "target_col": "nonexistent",
              "task": "classification", "algorithm": "Random Forest",
              "accent": "#818cf8"})
    assert r.status_code == 400
