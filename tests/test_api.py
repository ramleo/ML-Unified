import io
import os
import numpy as np
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app import app, MODELS, SCHEMA_DIR, MODEL_DIR

client = TestClient(app)

# ── Health & meta ─────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert isinstance(data["models"], list)
    assert len(data["models"]) >= 4

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
    # 12 rows with distinct numeric target → nunique > 10 → regression
    rows = "\n".join(f"{i},{i*2},{1000.5 + i * 237.3}" for i in range(12))
    csv = ("feature1,feature2,price\n" + rows + "\n").encode()
    r = client.post("/analyze", files={"file": ("test.csv", io.BytesIO(csv), "text/csv")})
    assert r.status_code == 200
    data = r.json()
    assert data["suggested_task"] == "regression"

def test_analyze_csv_bad_file():
    r = client.post("/analyze", files={"file": ("test.csv", io.BytesIO(b"not a csv!!@@##"), "text/csv")})
    # either parses (single column) or returns 400 — both are acceptable
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

    # verify registered in /models
    ids = [m["id"] for m in client.get("/models").json()]
    assert "ci-test-classifier" in ids

    # verify it can predict
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

    # verify registered in /models
    ids = [m["id"] for m in client.get("/models").json()]
    assert "ci-test-regressor" in ids

    # verify it can predict
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

# ── Image models meta ────────────────────────────────────────────────────────

def test_list_image_models():
    r = client.get("/image-models")
    assert r.status_code == 200
    models = r.json()
    ids = [m["id"] for m in models]
    assert "mobilenetv2" in ids
    assert "resnet50"    in ids
    assert "squeezenet"  in ids
    assert "googlenet"   in ids
    for m in models:
        assert "label"       in m
        assert "description" in m
        assert "input_size"  in m

def test_imagenet_classes_endpoint():
    # Labels file download is skipped in CI — just verify the endpoint exists
    # and returns 400/500 gracefully or 200 with correct shape
    r = client.get("/imagenet-classes")
    assert r.status_code in (200, 500)
    if r.status_code == 200:
        data = r.json()
        assert "classes" in data
        assert "total"   in data
        assert data["total"] == len(data["classes"])

def test_classify_image_bad_model():
    jpg = b"\xff\xd8\xff\xe0" + b"\x00" * 100   # minimal JPEG header bytes
    r = client.post("/classify-image",
        files={"file": ("img.jpg", io.BytesIO(jpg), "image/jpeg")},
        data={"model_name": "nonexistent_model", "top_k": "3"})
    assert r.status_code == 400

def test_classify_image_inference():
    """Exercises preprocessing → softmax → top-K with a mocked ONNX session."""
    from PIL import Image as PILImage
    img = PILImage.new("RGB", (300, 300), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    # 1000-class logits: class 207 (golden retriever) gets a big score
    fake_logits = np.zeros((1, 1000), dtype=np.float32)
    fake_logits[0, 207] = 12.0

    mock_session = MagicMock()
    mock_session.run.return_value = [fake_logits]
    mock_session.get_inputs.return_value = [MagicMock(name="input")]

    fake_labels = ["background"] + [f"class_{i}" for i in range(999)]
    fake_labels[207] = "golden retriever"

    import app as app_module
    with patch.object(app_module, "_img_cache",  {"session": mock_session}), \
         patch.object(app_module, "_img_active", ["mobilenetv2"]), \
         patch.object(app_module, "_IMAGENET_LABELS", fake_labels):
        r = client.post("/classify-image",
            files={"file": ("test.jpg", buf, "image/jpeg")},
            data={"model_name": "mobilenetv2", "top_k": "3"})

    assert r.status_code == 200
    data = r.json()
    assert data["model"]          == "mobilenetv2"
    assert data["model_label"]    == "MobileNetV2"
    assert not data["low_confidence"]
    assert data["top_confidence"] > 0.99        # softmax of dominant logit ≈ 1
    assert len(data["predictions"]) == 3
    assert data["predictions"][0]["label"]      == "golden retriever"
    assert data["predictions"][0]["class_id"]   == "207"

def test_classify_image_low_confidence():
    """When all logits are equal, top score ≈ 0.001 → low_confidence flag set."""
    from PIL import Image as PILImage
    img = PILImage.new("RGB", (100, 100), color=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    flat_logits = np.zeros((1, 1000), dtype=np.float32)  # uniform → each p ≈ 0.001
    mock_session = MagicMock()
    mock_session.run.return_value = [flat_logits]
    mock_session.get_inputs.return_value = [MagicMock(name="input")]
    fake_labels = [f"class_{i}" for i in range(1000)]

    import app as app_module
    with patch.object(app_module, "_img_cache",  {"session": mock_session}), \
         patch.object(app_module, "_img_active", ["mobilenetv2"]), \
         patch.object(app_module, "_IMAGENET_LABELS", fake_labels):
        r = client.post("/classify-image",
            files={"file": ("test.png", buf, "image/png")},
            data={"model_name": "mobilenetv2", "top_k": "5"})

    assert r.status_code == 200
    assert r.json()["low_confidence"] is True

# ── Image Processing ─────────────────────────────────────────────────────────

def _make_png(w=64, h=64, color=(128, 64, 32)) -> io.BytesIO:
    from PIL import Image as PILImage
    img = PILImage.new("RGB", (w, h), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def test_list_image_operations():
    r = client.get("/image-operations")
    assert r.status_code == 200
    ops = r.json()
    ids = [o["id"] for o in ops]
    assert "grayscale" in ids
    assert "blur"       in ids
    assert "sharpen"    in ids
    assert "edges"      in ids
    assert "rotate"     in ids
    for o in ops:
        assert "id"     in o
        assert "label"  in o
        assert "params" in o

def test_process_image_grayscale():
    r = client.post("/process-image",
        files={"file": ("test.png", _make_png(), "image/png")},
        data={"operation": "grayscale"})
    assert r.status_code == 200
    data = r.json()
    assert data["operation"]       == "grayscale"
    assert data["operation_label"] == "Grayscale"
    assert data["image_b64"].startswith("data:image/png;base64,")
    assert data["width"] == 64
    assert data["height"] == 64

def test_process_image_blur():
    r = client.post("/process-image",
        files={"file": ("test.png", _make_png(), "image/png")},
        data={"operation": "blur", "blur_radius": "5"})
    assert r.status_code == 200
    data = r.json()
    assert data["params_used"]["radius"] == 5
    assert data["image_b64"].startswith("data:image/png;base64,")

def test_process_image_rotate():
    r = client.post("/process-image",
        files={"file": ("test.png", _make_png(64, 32), "image/png")},
        data={"operation": "rotate", "rotate_angle": "90"})
    assert r.status_code == 200
    data = r.json()
    assert data["params_used"]["angle"] == 90.0
    # After 90° rotate with expand=True, width/height swap
    assert data["width"] == 32
    assert data["height"] == 64

def test_process_image_bad_operation():
    r = client.post("/process-image",
        files={"file": ("test.png", _make_png(), "image/png")},
        data={"operation": "nonexistent_op"})
    assert r.status_code == 400

# ── Object Detection ─────────────────────────────────────────────────────────

def test_list_detect_models():
    r = client.get("/detect-models")
    assert r.status_code == 200
    models = r.json()
    ids = [m["id"] for m in models]
    assert "ssd" in ids
    for m in models:
        assert "id"          in m
        assert "label"       in m
        assert "description" in m
        assert "input_size"  in m

def test_detect_objects_bad_model():
    jpg = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    r = client.post("/detect-objects",
        files={"file": ("img.jpg", io.BytesIO(jpg), "image/jpeg")},
        data={"model_name": "nonexistent_model"})
    assert r.status_code == 400

def test_detect_objects_inference():
    """Exercises box parsing, coordinate scaling, PIL drawing, and base64 output."""
    # One normalised box: person (class 1), confidence 0.95
    fake_boxes  = np.array([[[0.1, 0.1, 0.9, 0.9]]], dtype=np.float32)  # (1,1,4) y1,x1,y2,x2
    fake_labels = np.array([[1]], dtype=np.int64)                         # person
    fake_scores = np.array([[0.95]], dtype=np.float32)

    mock_session = MagicMock()
    mock_session.run.return_value = [fake_boxes, fake_labels, fake_scores]
    mock_session.get_inputs.return_value = [MagicMock(name="image")]

    import app as app_module
    with patch.object(app_module, "_det_cache",  {"session": mock_session}), \
         patch.object(app_module, "_det_active", ["ssd"]):
        r = client.post("/detect-objects",
            files={"file": ("test.png", _make_png(640, 480), "image/png")},
            data={"model_name": "ssd", "confidence": "0.5"})

    assert r.status_code == 200
    data = r.json()
    assert data["count"]                      == 1
    assert data["detections"][0]["label"]     == "person"
    assert data["detections"][0]["confidence"] == 0.95
    box = data["detections"][0]["box"]
    assert box["x1"] < box["x2"]
    assert box["y1"] < box["y2"]
    assert data["image_b64"].startswith("data:image/png;base64,")
    assert data["orig_width"]  == 640
    assert data["orig_height"] == 480

def test_detect_objects_confidence_filter():
    """Objects below the threshold must be excluded from results."""
    fake_boxes  = np.array([[[0.1, 0.1, 0.5, 0.5],
                              [0.2, 0.2, 0.8, 0.8]]], dtype=np.float32)
    fake_labels = np.array([[1, 3]], dtype=np.int64)   # person, car
    fake_scores = np.array([[0.9, 0.2]], dtype=np.float32)

    mock_session = MagicMock()
    mock_session.run.return_value = [fake_boxes, fake_labels, fake_scores]
    mock_session.get_inputs.return_value = [MagicMock(name="image")]

    import app as app_module
    with patch.object(app_module, "_det_cache",  {"session": mock_session}), \
         patch.object(app_module, "_det_active", ["ssd"]):
        r = client.post("/detect-objects",
            files={"file": ("test.png", _make_png(), "image/png")},
            data={"model_name": "ssd", "confidence": "0.5"})

    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1                          # car (0.2) filtered out
    assert data["detections"][0]["label"] == "person"

def test_train_missing_target_col():
    csv = b"a,b,c\n1,2,3\n4,5,6\n"
    r = client.post("/train",
        files={"file": ("train.csv", io.BytesIO(csv), "text/csv")},
        data={"model_name": "Bad Target Model", "target_col": "nonexistent",
              "task": "classification", "algorithm": "Random Forest",
              "accent": "#818cf8"})
    assert r.status_code == 400
