import io
import json
import numpy as np
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from vision_app import app

client = TestClient(app)


def _sse_result(response):
    """Parse an SSE streaming response; raise on error, return final result dict."""
    result = None
    for line in response.iter_lines():
        if isinstance(line, bytes):
            line = line.decode()
        if not line.startswith("data:"):
            continue
        ev = json.loads(line[5:].strip())
        if ev.get("error"):
            raise AssertionError(ev["error"])
        if ev.get("result"):
            result = ev["result"]
    return result


def _make_png(w=64, h=64, color=(128, 64, 32)) -> io.BytesIO:
    from PIL import Image as PILImage
    img = PILImage.new("RGB", (w, h), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ── Health ────────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["service"] == "ml-vision"


# ── Metrics ───────────────────────────────────────────────────────────────────

def test_metrics_empty():
    """Fresh service with no logged requests returns valid empty metrics."""
    r = client.get("/metrics")
    assert r.status_code == 200
    data = r.json()
    assert data["service"] == "ml-vision"
    assert "uptime_s"       in data
    assert "total_requests" in data
    assert "avg_ms"         in data
    assert "p95_ms"         in data
    assert "error_rate"     in data
    assert "endpoints"      in data
    assert isinstance(data["endpoints"], list)

def test_metrics_records_requests():
    """After a real request, metrics shows at least one logged entry."""
    client.get("/image-models")
    r = client.get("/metrics")
    assert r.status_code == 200
    data = r.json()
    assert data["total_requests"] >= 1
    assert any(e["path"] == "/image-models" for e in data["endpoints"])


# ── Image classifier meta ─────────────────────────────────────────────────────

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
    r = client.get("/imagenet-classes")
    assert r.status_code in (200, 500)
    if r.status_code == 200:
        data = r.json()
        assert "classes" in data
        assert "total"   in data
        assert data["total"] == len(data["classes"])

def test_classify_image_bad_model():
    jpg = b"\xff\xd8\xff\xe0" + b"\x00" * 100
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

    fake_logits = np.zeros((1, 1000), dtype=np.float32)
    fake_logits[0, 207] = 12.0

    mock_session = MagicMock()
    mock_session.run.return_value = [fake_logits]
    mock_session.get_inputs.return_value = [MagicMock(name="input")]

    fake_labels = ["background"] + [f"class_{i}" for i in range(999)]
    fake_labels[207] = "golden retriever"

    import vision_app as app_module
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
    assert data["top_confidence"] > 0.99
    assert len(data["predictions"]) == 3
    assert data["predictions"][0]["label"]    == "golden retriever"
    assert data["predictions"][0]["class_id"] == "207"

def test_classify_image_low_confidence():
    """When all logits are equal, top score ≈ 0.001 → low_confidence flag set."""
    from PIL import Image as PILImage
    img = PILImage.new("RGB", (100, 100), color=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    flat_logits = np.zeros((1, 1000), dtype=np.float32)
    mock_session = MagicMock()
    mock_session.run.return_value = [flat_logits]
    mock_session.get_inputs.return_value = [MagicMock(name="input")]
    fake_labels = [f"class_{i}" for i in range(1000)]

    import vision_app as app_module
    with patch.object(app_module, "_img_cache",  {"session": mock_session}), \
         patch.object(app_module, "_img_active", ["mobilenetv2"]), \
         patch.object(app_module, "_IMAGENET_LABELS", fake_labels):
        r = client.post("/classify-image",
            files={"file": ("test.png", buf, "image/png")},
            data={"model_name": "mobilenetv2", "top_k": "5"})

    assert r.status_code == 200
    assert r.json()["low_confidence"] is True


# ── Image Processing ──────────────────────────────────────────────────────────

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
    assert data["width"] == 32
    assert data["height"] == 64

def test_process_image_bad_operation():
    r = client.post("/process-image",
        files={"file": ("test.png", _make_png(), "image/png")},
        data={"operation": "nonexistent_op"})
    assert r.status_code == 400


# ── Object Detection ──────────────────────────────────────────────────────────

def test_list_detect_models():
    r = client.get("/detect-models")
    assert r.status_code == 200
    models = r.json()
    ids = [m["id"] for m in models]
    assert "tiny_yolov3" in ids
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
    """Exercises TinyYOLOv3 index parsing, PIL drawing, and base64 output."""
    fake_boxes   = np.zeros((1, 1, 4), dtype=np.float32)
    fake_boxes[0, 0] = [48.0, 64.0, 432.0, 576.0]
    fake_scores  = np.zeros((1, 80, 1), dtype=np.float32)
    fake_scores[0, 0, 0] = 0.95
    fake_indices = np.array([[0, 0, 0]], dtype=np.int64)

    mock_session = MagicMock()
    mock_session.run.return_value = [fake_boxes, fake_scores, fake_indices]

    import vision_app as app_module
    fake_slot = {"model_type": "det", "model_id": "tiny_yolov3", "session": mock_session}
    with patch.object(app_module, "_large_vision_cache", fake_slot), \
         patch("os.path.exists", lambda p: True):
        with client.stream("POST", "/detect-objects",
                files={"file": ("test.png", _make_png(640, 480), "image/png")},
                data={"model_name": "tiny_yolov3", "confidence": "0.5"}) as r:
            assert r.status_code == 200
            data = _sse_result(r)

    assert data is not None
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
    fake_boxes   = np.zeros((1, 2, 4), dtype=np.float32)
    fake_boxes[0, 0] = [48.0, 64.0, 240.0, 320.0]
    fake_boxes[0, 1] = [96.0, 128.0, 384.0, 512.0]
    fake_scores  = np.zeros((1, 80, 2), dtype=np.float32)
    fake_scores[0, 0, 0] = 0.9
    fake_scores[0, 2, 1] = 0.2
    fake_indices = np.array([[0, 0, 0], [0, 2, 1]], dtype=np.int64)

    mock_session = MagicMock()
    mock_session.run.return_value = [fake_boxes, fake_scores, fake_indices]

    import vision_app as app_module
    fake_slot = {"model_type": "det", "model_id": "tiny_yolov3", "session": mock_session}
    with patch.object(app_module, "_large_vision_cache", fake_slot), \
         patch("os.path.exists", lambda p: True):
        with client.stream("POST", "/detect-objects",
                files={"file": ("test.png", _make_png(640, 480), "image/png")},
                data={"model_name": "tiny_yolov3", "confidence": "0.5"}) as r:
            assert r.status_code == 200
            data = _sse_result(r)

    assert data is not None
    assert data["count"] == 1
    assert data["detections"][0]["label"] == "person"


# ── Image Segmentation ────────────────────────────────────────────────────────

def test_list_seg_models():
    r = client.get("/seg-models")
    assert r.status_code == 200
    models = r.json()
    assert isinstance(models, list)
    assert len(models) >= 2
    ids = [m["id"] for m in models]
    assert "segformer_b0"      in ids
    assert "color_segmentation" in ids
    for m in models:
        assert "label"   in m
        assert "size_mb" in m

def test_segment_image_color():
    """PIL colour segmentation — no mock needed, runs fully in-process."""
    r = client.post("/segment-image",
        files={"file": ("test.png", _make_png(64, 64), "image/png")},
        data={"model_name": "color_segmentation"})
    assert r.status_code == 200
    data = r.json()
    assert data["model"] == "color_segmentation"
    assert isinstance(data["classes_found"], list)
    for c in data["classes_found"]:
        assert 0.0 <= c["percentage"] <= 100.0
        assert c["color"].startswith("#")
    assert data["image_b64"].startswith("data:image/png;base64,")
    assert data["orig_width"]  == 64
    assert data["orig_height"] == 64

def test_segment_image_uniform():
    """Uniform-colour image produces at least one colour region."""
    r = client.post("/segment-image",
        files={"file": ("test.png", _make_png(32, 32, color=(0, 100, 200)), "image/png")},
        data={"model_name": "color_segmentation"})
    assert r.status_code == 200
    data = r.json()
    assert data["image_b64"].startswith("data:image/png;base64,")
    assert isinstance(data["classes_found"], list)

def test_segment_image_bad_model():
    r = client.post("/segment-image",
        files={"file": ("test.png", _make_png(32, 32), "image/png")},
        data={"model_name": "nonexistent_seg_model"})
    assert r.status_code == 400

def test_segment_image_segformer_inference():
    """SegFormer-B0 path: mocks ONNX session + model-on-disk check."""
    import vision_app as app_module

    # logits shape: (1, 150, 128, 128) — make class 2 (sky) dominant
    fake_logits = np.full((1, 150, 128, 128), -10.0, dtype=np.float32)
    fake_logits[0, 2, :, :] = 10.0   # class 2 = "sky"

    mock_session = MagicMock()
    mock_session.run.return_value = [fake_logits]

    fake_slot = {
        "model_type": "seg",
        "model_id":   "segformer_b0",
        "session":    mock_session,
    }

    # Pretend the model file exists so the 503 guard doesn't fire
    with patch.object(app_module, "_large_vision_cache", fake_slot), \
         patch("os.path.exists", lambda p: True):
        with client.stream("POST", "/segment-image",
                files={"file": ("test.png", _make_png(64, 64), "image/png")},
                data={"model_name": "segformer_b0"}) as r:
            assert r.status_code == 200
            data = _sse_result(r)

    assert data is not None
    assert data["model"]      == "segformer_b0"
    assert data["orig_width"] == 64
    assert isinstance(data["classes_found"], list)
    assert any(c["label"] == "sky" for c in data["classes_found"])
    assert data["image_b64"].startswith("data:image/png;base64,")
