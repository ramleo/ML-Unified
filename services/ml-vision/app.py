#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import Any, Dict
import io
import os
import threading

app = FastAPI(title="ML Vision")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HERE             = os.path.dirname(os.path.abspath(__file__))
VISION_CACHE_DIR = os.path.join(HERE, "vision_cache")
os.makedirs(VISION_CACHE_DIR, exist_ok=True)

_MAX_IMG_DIM = 1200


@app.get("/health")
def health():
    return {"status": "ok", "service": "ml-vision"}


# ── Image Classification ─────────────────────────────────────────────────────

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


def _ensure_img_model_file(model_id: str) -> str:
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


# ── Image Processing ─────────────────────────────────────────────────────────

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


# ── Object Detection ─────────────────────────────────────────────────────────

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

# Shared slot — only ONE large ONNX model in RAM at a time (detection OR segmentation).
# This keeps peak memory within Render free tier's 512 MB budget.
_large_vision_cache: Dict[str, Any] = {}
_large_vision_lock:  threading.Lock  = threading.Lock()

# Background warmup: download model files to disk on startup so the first inference
# request doesn't have to wait for a 135 MB download and timeout (502 on Render free tier).
_warmup_done = threading.Event()


def _warmup_models() -> None:
    for fn in (lambda: _ensure_det_model("tiny_yolov3"), _ensure_segformer_model):
        try:
            fn()
        except Exception as exc:
            print(f"[warmup] download failed: {exc}", flush=True)
    _warmup_done.set()


@app.on_event("startup")
async def startup() -> None:
    threading.Thread(target=_warmup_models, daemon=True).start()


def _ensure_det_model(model_id: str) -> str:
    path = os.path.join(VISION_CACHE_DIR, f"det_{model_id}.onnx")
    if not os.path.exists(path):
        import urllib.request  # noqa: PLC0415
        urllib.request.urlretrieve(_DETECTION_MODEL_CONFIGS[model_id]["url"], path)
    return path


def _load_det_session(model_id: str):
    import gc
    import onnxruntime as ort  # noqa: PLC0415
    path = _ensure_det_model(model_id)
    with _large_vision_lock:
        _large_vision_cache.clear()
        gc.collect()
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

    with _large_vision_lock:
        cached = (
            _large_vision_cache.get("model_type") == "det"
            and _large_vision_cache.get("model_id") == model_name
        )
        session = _large_vision_cache.get("session") if cached else None

    if session is None:
        det_path = os.path.join(VISION_CACHE_DIR, f"det_{model_name}.onnx")
        if not os.path.exists(det_path):
            raise HTTPException(503, "Vision service is warming up — please try again in ~30 seconds")
        try:
            session = _load_det_session(model_name)
        except Exception as e:
            raise HTTPException(500, f"Failed to load detection model: {e}")
    size = cfg["input_size"]

    content = await file.read()
    try:
        from PIL import Image as PILImage, ImageDraw  # noqa: PLC0415
        import numpy as np                             # noqa: PLC0415
        import base64                                  # noqa: PLC0415
        img = PILImage.open(io.BytesIO(content)).convert("RGB")
    except Exception as e:
        raise HTTPException(400, f"Could not load image: {e}")

    orig_w, orig_h = img.width, img.height

    try:
        # TinyYOLOv3 — letterbox: maintain aspect ratio, pad grey to 416×416
        scale  = min(size / orig_w, size / orig_h)
        nw, nh = int(orig_w * scale), int(orig_h * scale)
        pad_x  = (size - nw) // 2
        pad_y  = (size - nh) // 2
        canvas = PILImage.new("RGB", (size, size), (128, 128, 128))
        canvas.paste(img.resize((nw, nh), PILImage.LANCZOS), (pad_x, pad_y))

        arr = np.array(canvas, dtype=np.float32) / 255.0
        arr = arr.transpose(2, 0, 1)
        arr = np.expand_dims(arr, axis=0)
        image_shape = np.array([[size, size]], dtype=np.float32)

        inp = session.get_inputs()
        feed: Dict[str, Any] = {inp[0].name: arr}
        if len(inp) >= 2:
            feed[inp[1].name] = image_shape

        outputs = session.run(None, feed)

        boxes_out   = np.array(outputs[0])
        scores_out  = np.array(outputs[1])
        indices_raw = np.array(outputs[2])

        if indices_raw.ndim < 2 or indices_raw.size == 0:
            indices_2d: np.ndarray = np.empty((0, 3), dtype=np.int64)
        else:
            indices_2d = indices_raw.reshape(-1, 3)

        detections = []
        for idx_ in indices_2d:
            batch_idx = int(idx_[0])
            class_idx = int(idx_[1])
            box_idx   = int(idx_[2])

            if (batch_idx >= scores_out.shape[0]
                    or class_idx >= scores_out.shape[1]
                    or box_idx   >= scores_out.shape[2]
                    or batch_idx >= boxes_out.shape[0]
                    or box_idx   >= boxes_out.shape[1]):
                continue

            s = float(scores_out[batch_idx, class_idx, box_idx])
            if s < confidence:
                continue

            name_idx = class_idx + 1
            if name_idx >= len(_COCO_CLASSES):
                continue

            b = boxes_out[batch_idx, box_idx]
            y1_lb, x1_lb = float(b[0]), float(b[1])
            y2_lb, x2_lb = float(b[2]), float(b[3])

            x1 = (x1_lb - pad_x) / scale
            y1 = (y1_lb - pad_y) / scale
            x2 = (x2_lb - pad_x) / scale
            y2 = (y2_lb - pad_y) / scale

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

        if max(img.width, img.height) > _MAX_IMG_DIM:
            img.thumbnail((_MAX_IMG_DIM, _MAX_IMG_DIM), PILImage.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
    except HTTPException:
        raise
    except Exception as e:
        shape_info = ""
        try:
            shape_info = f" | output shapes: {[np.array(o).shape for o in outputs]}"  # type: ignore[name-defined]
        except Exception:
            pass
        raise HTTPException(500, f"Detection failed: {e}{shape_info}")

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


# ── Image Segmentation (PIL colour-quantisation, no ONNX) ────────────────────
# ── SegFormer-B0 (ADE20K 150-class semantic segmentation) ─────────────────────
# 4.4 MB quantized ONNX — loads in ~1 s, infers in ~2-5 s on Render free tier.

_SEGFORMER_URL = (
    "https://huggingface.co/Xenova/segformer-b0-finetuned-ade-512-512"
    "/resolve/main/onnx/model_quantized.onnx"
)
_SEGFORMER_PATH = os.path.join(VISION_CACHE_DIR, "segformer_b0_quantized.onnx")

_SEGFORMER_CLASSES: list = [
    "wall", "building", "sky", "floor", "tree", "ceiling", "road", "bed",
    "window", "grass", "cabinet", "sidewalk", "person", "earth", "door",
    "table", "mountain", "plant", "curtain", "chair", "car", "water",
    "painting", "sofa", "shelf", "house", "sea", "mirror", "rug", "field",
    "armchair", "seat", "fence", "desk", "rock", "wardrobe", "lamp",
    "bathtub", "railing", "cushion", "base", "box", "column", "signboard",
    "chest of drawers", "counter", "sand", "sink", "skyscraper", "fireplace",
    "refrigerator", "grandstand", "path", "stairs", "runway", "case",
    "pool table", "pillow", "screen door", "stairway", "river", "bridge",
    "bookcase", "blind", "coffee table", "toilet", "flower", "book", "hill",
    "bench", "countertop", "stove", "palm", "kitchen island", "computer",
    "swivel chair", "boat", "bar", "arcade machine", "hovel", "bus", "towel",
    "light", "truck", "tower", "chandelier", "awning", "streetlight", "booth",
    "television", "airplane", "dirt track", "apparel", "pole", "land",
    "bannister", "escalator", "ottoman", "bottle", "buffet", "poster",
    "stage", "van", "ship", "fountain", "conveyer belt", "canopy", "washer",
    "plaything", "swimming pool", "stool", "barrel", "basket", "waterfall",
    "tent", "bag", "minibike", "cradle", "oven", "ball", "food", "step",
    "tank", "trade name", "microwave", "pot", "animal", "bicycle", "lake",
    "dishwasher", "screen", "blanket", "sculpture", "hood", "sconce", "vase",
    "traffic light", "tray", "ashcan", "fan", "pier", "crt screen", "plate",
    "monitor", "bulletin board", "shower", "radiator", "glass", "clock", "flag",
]


def _make_segformer_palette() -> list:
    import colorsys  # noqa: PLC0415
    out = []
    for i in range(150):
        h = (i * 0.618033988) % 1.0   # golden-ratio hue spacing
        r, g, b = colorsys.hsv_to_rgb(h, 0.75, 0.90)
        out.append((int(r * 255), int(g * 255), int(b * 255)))
    return out

_SEGFORMER_PALETTE: list = _make_segformer_palette()


def _ensure_segformer_model() -> str:
    if not os.path.exists(_SEGFORMER_PATH):
        import urllib.request  # noqa: PLC0415
        urllib.request.urlretrieve(_SEGFORMER_URL, _SEGFORMER_PATH)
    return _SEGFORMER_PATH


def _load_segformer_session():
    import gc
    import onnxruntime as ort  # noqa: PLC0415
    path = _ensure_segformer_model()
    with _large_vision_lock:
        _large_vision_cache.clear()
        gc.collect()
        session = ort.InferenceSession(path)
        _large_vision_cache["model_type"] = "seg"
        _large_vision_cache["model_id"]   = "segformer_b0"
        _large_vision_cache["session"]    = session
    return session


# ── PIL colour-quantisation fallback (instant, zero memory) ───────────────────

_SEG_VIZ: list = [
    (128, 0,   0), (0,   128, 0), (0,   0,   128), (128, 128, 0),
    (0,   128, 128), (128, 0, 128), (64,  64,  0), (0,   64,  64),
    (64,  0,   64), (192, 128, 0), (0,   192, 128), (192, 0,   128),
]


def _colour_label(r: int, g: int, b: int) -> str:
    import colorsys  # noqa: PLC0415
    h, s, v      = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    h_deg        = h * 360
    s_pct, v_pct = s * 100, v * 100
    if v_pct < 18:
        return "shadow/dark"
    if s_pct < 14:
        return "sky/light" if v_pct > 80 else "structure/neutral"
    if 75 <= h_deg <= 165:
        return "vegetation"
    if 195 <= h_deg <= 265:
        return "sky/water"
    if 10 <= h_deg < 75:
        return "earth/ground"
    if h_deg < 10 or h_deg > 340:
        return "warm object"
    return "mixed region"


def _pil_segment(img, orig_w: int, orig_h: int) -> dict:
    from PIL import Image as PILImage  # noqa: PLC0415
    import numpy as np                 # noqa: PLC0415
    import base64                      # noqa: PLC0415
    thumb = img.copy()
    thumb.thumbnail((480, 480), PILImage.LANCZOS)
    quantized   = thumb.quantize(colors=8, method=PILImage.Quantize.FASTOCTREE)
    palette_raw = quantized.getpalette()
    q_arr       = np.array(quantized, dtype=np.uint8)
    total_px    = q_arr.size
    new_palette: list = [0] * 768
    classes_found: list = []
    seen: dict = {}
    for idx in range(8):
        vr, vg, vb = _SEG_VIZ[idx]
        new_palette[idx*3], new_palette[idx*3+1], new_palette[idx*3+2] = vr, vg, vb
        r, g, b     = palette_raw[idx*3], palette_raw[idx*3+1], palette_raw[idx*3+2]
        pct         = int(np.sum(q_arr == idx)) / total_px * 100
        if pct < 1.0:
            continue
        label = _colour_label(r, g, b)
        if label in seen:
            seen[label] += 1
            label = f"{label} {seen[label]}"
        else:
            seen[label] = 1
        classes_found.append({"label": label, "percentage": round(pct, 1),
                               "color": f"#{vr:02x}{vg:02x}{vb:02x}"})
    seg_img = quantized.copy()
    seg_img.putpalette(new_palette)
    seg_rgb = seg_img.convert("RGB").resize((orig_w, orig_h), PILImage.NEAREST)
    buf = io.BytesIO()
    seg_rgb.save(buf, format="PNG")
    return {
        "model":         "color_segmentation",
        "model_label":   "Color Segmentation",
        "classes_found": sorted(classes_found, key=lambda x: -x["percentage"]),
        "image_b64":     "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(),
        "orig_width":    orig_w,
        "orig_height":   orig_h,
    }


@app.get("/seg-models")
def list_seg_models():
    return [
        {
            "id":          "segformer_b0",
            "label":       "SegFormer-B0",
            "description": "SegFormer-B0 — ADE20K 150 classes, 4.4 MB quantized ONNX",
            "size_mb":     4,
        },
        {
            "id":          "color_segmentation",
            "label":       "Color Segmentation",
            "description": "Fast PIL colour-region analysis — instant, no model",
            "size_mb":     0,
        },
    ]


@app.post("/segment-image")
async def segment_image(
    file:       UploadFile = File(...),
    model_name: str        = Form("segformer_b0"),
):
    from PIL import Image as PILImage  # noqa: PLC0415
    import numpy as np                 # noqa: PLC0415
    import base64                      # noqa: PLC0415

    raw = await file.read()
    try:
        img = PILImage.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(400, "Cannot read image file")

    orig_w, orig_h = img.width, img.height

    if model_name == "color_segmentation":
        return _pil_segment(img, orig_w, orig_h)

    if model_name != "segformer_b0":
        raise HTTPException(400, f"Unknown model: {model_name}")

    if not os.path.exists(_SEGFORMER_PATH):
        raise HTTPException(503, "Vision service is warming up — please try again in ~30 seconds")

    with _large_vision_lock:
        cached  = (_large_vision_cache.get("model_type") == "seg"
                   and _large_vision_cache.get("model_id") == "segformer_b0")
        session = _large_vision_cache.get("session") if cached else None

    if session is None:
        try:
            session = _load_segformer_session()
        except Exception as e:
            raise HTTPException(500, f"Failed to load segmentation model: {e}")

    # Preprocess: resize to 512×512, ImageNet normalise → (1, 3, 512, 512)
    arr  = np.array(img.resize((512, 512), PILImage.LANCZOS), dtype=np.float32) / 255.0
    arr  = (arr - np.array([0.485, 0.456, 0.406])) / np.array([0.229, 0.224, 0.225])
    arr  = arr.transpose(2, 0, 1)[np.newaxis].astype(np.float32)

    try:
        logits = session.run(["logits"], {"pixel_values": arr})[0]  # (1, 150, 128, 128)
    except Exception:
        raise HTTPException(500, "Segmentation failed — please try again")

    # Postprocess: argmax → upscale → overlay
    label_map  = np.argmax(logits[0], axis=0).astype(np.uint8)        # (128, 128)
    label_full = np.array(
        PILImage.fromarray(label_map, mode="L").resize((orig_w, orig_h), PILImage.NEAREST)
    )

    unique, counts = np.unique(label_full, return_counts=True)
    total_px       = orig_w * orig_h
    colour_mask    = np.zeros((orig_h, orig_w, 4), dtype=np.uint8)
    classes_found: list = []

    for cls_id, count in sorted(zip(unique.tolist(), counts.tolist()), key=lambda x: -x[1]):
        pct = count / total_px * 100
        if pct < 0.5 or cls_id >= len(_SEGFORMER_CLASSES):
            continue
        r, g, b = _SEGFORMER_PALETTE[cls_id]
        px = np.where(label_full == cls_id)
        colour_mask[px[0], px[1], :3] = (r, g, b)
        colour_mask[px[0], px[1],  3] = 160
        classes_found.append({
            "label":      _SEGFORMER_CLASSES[cls_id],
            "percentage": round(pct, 1),
            "color":      f"#{r:02x}{g:02x}{b:02x}",
        })

    composite = PILImage.alpha_composite(
        img.convert("RGBA"),
        PILImage.fromarray(colour_mask, mode="RGBA"),
    ).convert("RGB")

    buf = io.BytesIO()
    composite.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    return {
        "model":         "segformer_b0",
        "model_label":   "SegFormer-B0 (ADE20K 150 classes)",
        "classes_found": classes_found,
        "image_b64":     f"data:image/png;base64,{b64}",
        "orig_width":    orig_w,
        "orig_height":   orig_h,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
