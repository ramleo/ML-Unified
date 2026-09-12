"""Vision detection routes: /detect-models, /detect-objects."""
import io
import os
from typing import Any, Dict

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from .shared import (
    VISION_CACHE_DIR,
    _MAX_IMG_DIM,
    _large_vision_cache,
    _large_vision_lock,
    StreamingTask,
    download_model,
    ort_session,
)
from security.file_gate import scan_upload_bytes

router = APIRouter(tags=["vision"])

# ── COCO classes ──────────────────────────────────────────────────────────────

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
]  # index 0 = background; 1-80 = COCO classes

# ── Model configs ─────────────────────────────────────────────────────────────

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

# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_det_model(model_id: str) -> str:
    path = os.path.join(VISION_CACHE_DIR, f"det_{model_id}.onnx")
    if not os.path.exists(path):
        download_model(_DETECTION_MODEL_CONFIGS[model_id]["url"], path)
    return path


def _load_det_session(model_id: str):
    import gc
    path = _ensure_det_model(model_id)
    with _large_vision_lock:
        _large_vision_cache.clear()
        gc.collect()
        session = ort_session(path)
        _large_vision_cache["model_type"] = "det"
        _large_vision_cache["model_id"]   = model_id
        _large_vision_cache["session"]    = session
    return session


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/detect-models")
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


@router.post("/detect-objects")
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
    cfg        = _DETECTION_MODEL_CONFIGS[model_name]

    det_path = os.path.join(VISION_CACHE_DIR, f"det_{model_name}.onnx")
    if not os.path.exists(det_path):
        raise HTTPException(503, "Vision service is warming up — please try again in ~30 seconds")

    content = await file.read()
    scan_upload_bytes(content, path="/detect-objects")
    task    = StreamingTask()

    def work(p):
        from PIL import Image as PILImage, ImageDraw  # noqa: PLC0415
        import numpy as np                             # noqa: PLC0415
        import base64                                  # noqa: PLC0415

        p.update(5, "Decoding image")
        try:
            img = PILImage.open(io.BytesIO(content)).convert("RGB")
        except Exception as e:
            p.finish(error=f"Could not load image: {e}")
            return
        orig_w, orig_h = img.width, img.height

        with _large_vision_lock:
            cached  = (_large_vision_cache.get("model_type") == "det"
                       and _large_vision_cache.get("model_id") == model_name)
            session = _large_vision_cache.get("session") if cached else None

        p.update(20, "Model cached" if cached else "Loading model")
        if session is None:
            try:
                session = _load_det_session(model_name)
            except Exception as e:
                p.finish(error=f"Failed to load detection model: {e}")
                return

        size = cfg["input_size"]

        p.update(40, "Preprocessing image")
        try:
            scale  = min(size / orig_w, size / orig_h)
            nw, nh = int(orig_w * scale), int(orig_h * scale)
            pad_x  = (size - nw) // 2
            pad_y  = (size - nh) // 2
            canvas = PILImage.new("RGB", (size, size), (128, 128, 128))
            canvas.paste(img.resize((nw, nh), PILImage.LANCZOS), (pad_x, pad_y))
            arr         = np.array(canvas, dtype=np.float32) / 255.0
            arr         = arr.transpose(2, 0, 1)
            arr         = np.expand_dims(arr, axis=0)
            image_shape = np.array([[size, size]], dtype=np.float32)
            inp         = session.get_inputs()
            feed: Dict[str, Any] = {inp[0].name: arr}
            if len(inp) >= 2:
                feed[inp[1].name] = image_shape
        except Exception as e:
            p.finish(error=f"Preprocessing failed: {e}")
            return

        p.update(65, "Running inference")
        try:
            outputs     = session.run(None, feed)
            boxes_out   = np.array(outputs[0])
            scores_out  = np.array(outputs[1])
            indices_raw = np.array(outputs[2])
            if indices_raw.ndim < 2 or indices_raw.size == 0:
                indices_2d: np.ndarray = np.empty((0, 3), dtype=np.int64)
            else:
                indices_2d = indices_raw.reshape(-1, 3)

            detections = []
            for idx_ in indices_2d:
                batch_idx, class_idx, box_idx = int(idx_[0]), int(idx_[1]), int(idx_[2])
                if (batch_idx >= scores_out.shape[0] or class_idx >= scores_out.shape[1]
                        or box_idx >= scores_out.shape[2] or batch_idx >= boxes_out.shape[0]
                        or box_idx >= boxes_out.shape[1]):
                    continue
                s = float(scores_out[batch_idx, class_idx, box_idx])
                if s < confidence:
                    continue
                name_idx = class_idx + 1
                if name_idx >= len(_COCO_CLASSES):
                    continue
                b = boxes_out[batch_idx, box_idx]
                y1_lb, x1_lb, y2_lb, x2_lb = float(b[0]), float(b[1]), float(b[2]), float(b[3])
                x1 = max(0.0, (x1_lb - pad_x) / scale)
                y1 = max(0.0, (y1_lb - pad_y) / scale)
                x2 = min(float(orig_w), (x2_lb - pad_x) / scale)
                y2 = min(float(orig_h), (y2_lb - pad_y) / scale)
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
        except Exception as e:
            p.finish(error=f"Inference failed: {e}")
            return

        p.update(85, "Drawing detections")
        try:
            draw = ImageDraw.Draw(img)
            for det in detections:
                color  = _BOX_PALETTE[det["class_id"] % len(_BOX_PALETTE)]
                b      = det["box"]
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
        except Exception as e:
            p.finish(error=f"Drawing failed: {e}")
            return

        p.finish(result={
            "model":                model_name,
            "model_label":          cfg["label"],
            "count":                len(detections),
            "confidence_threshold": confidence,
            "detections":           detections,
            "image_b64":            f"data:image/png;base64,{b64}",
            "orig_width":           orig_w,
            "orig_height":          orig_h,
        })

    return StreamingResponse(task.stream(work), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
