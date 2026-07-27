"""Closed-vocabulary object detection (COCO's 80 classes) for standalone
image and video-frame citations — MMRAG-07 follow-up ("where is the X").

Runs ONCE at ingest time per image/frame via ONNX Runtime + a pre-exported
YOLOv8n model, so a later "where is the cyclist" question is answered by a
free metadata lookup at query/chat time (frontend keyword-matches the
question against each citation's stored detections), not a fresh vision
call. Deliberately NOT the `ultralytics` package — it pulls in torchvision,
matplotlib, polars, and its own opencv-python (which conflicts with the
opencv-python-headless already used elsewhere in this codebase for video
frame sampling). onnxruntime needs only numpy/protobuf/flatbuffers.

Real limitation, by design: only finds COCO's ~80 everyday object classes
(person, bicycle, car, dog, chair, ...) — won't find something outside that
set (e.g. "the whiteboard"), and doesn't distinguish attributes like color
("the red bicycle" vs "the blue one") within a class. A genuinely correct
scope for v1, not a shortcut — the alternative (open-vocabulary detection or
a per-question vision call) is a materially heavier/slower feature.

Postprocessing (letterbox undo + NMS) verified against the standard
ultralytics bus.jpg demo image before this module was written — the 4
person + 1 bus detections matched the canonical reference result exactly.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import tempfile
import threading

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_MODEL_URL = "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolov8n.onnx"
_MODEL_PATH = os.path.join(tempfile.gettempdir(), "yolov8n.onnx")
_INPUT_SIZE = 640
_CONF_THRESH = 0.35
_IOU_THRESH = 0.45
_MAX_DETECTIONS = 8  # caps noise on a busy photo/frame

COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
    "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone",
    "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]

_session = None
_session_lock = threading.Lock()


def _ensure_model() -> str:
    """Downloads the official pre-exported yolov8n.onnx (Ultralytics' own
    GitHub release asset) on first use, cached for this process's lifetime.
    Space disk is ephemeral like everything else here — re-downloads after
    a restart, same tradeoff already accepted for the CLIP figure-similarity
    model, just a much smaller file (~13MB vs ~350MB)."""
    if os.path.exists(_MODEL_PATH) and os.path.getsize(_MODEL_PATH) > 1_000_000:
        return _MODEL_PATH
    import httpx
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        r = client.get(_MODEL_URL)
        r.raise_for_status()
        with open(_MODEL_PATH, "wb") as f:
            f.write(r.content)
    return _MODEL_PATH


def _get_session():
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                import onnxruntime as ort
                _session = ort.InferenceSession(_ensure_model(), providers=["CPUExecutionProvider"])
    return _session


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float = _IOU_THRESH) -> list[int]:
    idxs = scores.argsort()[::-1]
    keep: list[int] = []
    while len(idxs) > 0:
        i = idxs[0]
        keep.append(i)
        if len(idxs) == 1:
            break
        rest = idxs[1:]
        xx0 = np.maximum(boxes[i, 0], boxes[rest, 0])
        yy0 = np.maximum(boxes[i, 1], boxes[rest, 1])
        xx1 = np.minimum(boxes[i, 2], boxes[rest, 2])
        yy1 = np.minimum(boxes[i, 3], boxes[rest, 3])
        inter = np.maximum(0, xx1 - xx0) * np.maximum(0, yy1 - yy0)
        area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
        area_r = (boxes[rest, 2] - boxes[rest, 0]) * (boxes[rest, 3] - boxes[rest, 1])
        iou = inter / (area_i + area_r - inter + 1e-9)
        idxs = rest[iou <= iou_thresh]
    return keep


def detect_objects(b64: str) -> list[dict]:
    """Runs YOLOv8n over a base64 PNG/JPEG. Returns up to _MAX_DETECTIONS
    {label, confidence, bbox: [x,y,w,h] normalized 0-1} sorted by confidence
    descending. [] on any failure (model download, corrupt image, no
    detections) — never blocks ingestion."""
    try:
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        orig_w, orig_h = img.size
        if orig_w == 0 or orig_h == 0:
            return []

        scale = min(_INPUT_SIZE / orig_w, _INPUT_SIZE / orig_h)
        new_w, new_h = max(1, round(orig_w * scale)), max(1, round(orig_h * scale))
        resized = img.resize((new_w, new_h), Image.BILINEAR)
        canvas = Image.new("RGB", (_INPUT_SIZE, _INPUT_SIZE), (114, 114, 114))
        pad_x, pad_y = (_INPUT_SIZE - new_w) // 2, (_INPUT_SIZE - new_h) // 2
        canvas.paste(resized, (pad_x, pad_y))

        arr = np.asarray(canvas).astype(np.float32) / 255.0
        arr = arr.transpose(2, 0, 1)[None, ...]

        session = _get_session()
        out = session.run(None, {session.get_inputs()[0].name: arr})[0]  # (1, 84, 8400)
        pred = out[0].T  # (8400, 84): 4 box coords + 80 class scores
        boxes_cxcywh = pred[:, :4]
        class_ids = np.argmax(pred[:, 4:], axis=1)
        confidences = np.max(pred[:, 4:], axis=1)

        keep_mask = confidences >= _CONF_THRESH
        if not keep_mask.any():
            return []
        boxes_cxcywh, class_ids, confidences = boxes_cxcywh[keep_mask], class_ids[keep_mask], confidences[keep_mask]

        cx, cy, w, h = boxes_cxcywh[:, 0], boxes_cxcywh[:, 1], boxes_cxcywh[:, 2], boxes_cxcywh[:, 3]
        # Undo the letterbox padding/scale to get coords back in the
        # ORIGINAL image's pixel space, not the padded 640x640 input.
        x0 = (cx - w / 2 - pad_x) / scale
        x1 = (cx + w / 2 - pad_x) / scale
        y0 = (cy - h / 2 - pad_y) / scale
        y1 = (cy + h / 2 - pad_y) / scale
        boxes_xyxy = np.stack([
            np.clip(x0, 0, orig_w), np.clip(y0, 0, orig_h),
            np.clip(x1, 0, orig_w), np.clip(y1, 0, orig_h),
        ], axis=1)

        results = []
        for c in np.unique(class_ids):
            mask = class_ids == c
            b, s = boxes_xyxy[mask], confidences[mask]
            for k in _nms(b, s):
                results.append((COCO_CLASSES[c], float(s[k]), b[k]))
        results.sort(key=lambda t: -t[1])
        results = results[:_MAX_DETECTIONS]

        return [
            {"label": label, "confidence": round(conf, 3),
             "bbox": [round(float(box[0] / orig_w), 4), round(float(box[1] / orig_h), 4),
                      round(float((box[2] - box[0]) / orig_w), 4), round(float((box[3] - box[1]) / orig_h), 4)]}
            for label, conf, box in results
        ]
    except Exception as exc:
        logger.warning("Object detection failed: %s", exc)
        return []


def encode_objects(objects: list[dict] | None) -> str | None:
    return json.dumps(objects) if objects else None


def decode_objects(raw) -> list[dict]:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return []
