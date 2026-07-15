"""Vision classification routes: /classify-image, /imagenet-classes, /image-models."""
import io
import os
from typing import Any, Dict

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .shared import VISION_CACHE_DIR

router = APIRouter(tags=["vision"])

# ── Model configs ─────────────────────────────────────────────────────────────

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
        "description": "Tiny & fast — AlexNet accuracy at 50x fewer parameters",
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

# ── State ─────────────────────────────────────────────────────────────────────

_IMAGENET_LABELS: list = []
_img_cache:       Dict[str, Any] = {}
_img_active:      list = [None]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_labels() -> None:
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


def _ensure_img_model_file(model_id: str) -> str:
    path = os.path.join(VISION_CACHE_DIR, f"{model_id}.onnx")
    if not os.path.exists(path):
        import urllib.request  # noqa: PLC0415
        urllib.request.urlretrieve(_IMAGE_MODEL_CONFIGS[model_id]["url"], path)
    return path


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/imagenet-classes")
def list_imagenet_classes():
    try:
        _ensure_labels()
    except Exception as e:
        raise HTTPException(500, f"Failed to load ImageNet labels: {e}")
    return {"classes": _IMAGENET_LABELS, "total": len(_IMAGENET_LABELS)}


@router.get("/image-models")
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


@router.post("/classify-image")
async def classify_image(
    file:       UploadFile = File(...),
    model_name: str        = Form("mobilenetv2"),
    top_k:      int        = Form(5),
):
    if model_name not in _IMAGE_MODEL_CONFIGS:
        raise HTTPException(400, f"Unknown model '{model_name}'. Choose from: {list(_IMAGE_MODEL_CONFIGS)}")
    top_k = max(1, min(top_k, 10))
    cfg   = _IMAGE_MODEL_CONFIGS[model_name]

    try:
        _ensure_labels()
    except Exception as e:
        raise HTTPException(500, f"Failed to load ImageNet labels: {e}")

    if _img_active[0] != model_name:
        _img_cache.clear()
        try:
            import onnxruntime as ort  # noqa: PLC0415
            model_path = _ensure_img_model_file(model_name)
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
        arr  = arr.transpose(2, 0, 1)
        arr  = np.expand_dims(arr, axis=0)
    except Exception as e:
        raise HTTPException(400, f"Could not process image: {e}")

    input_name = session.get_inputs()[0].name
    scores     = session.run(None, {input_name: arr})[0][0]

    import numpy as np  # noqa: PLC0415
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
