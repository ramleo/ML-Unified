"""Signature detection for standalone image and video-frame citations
(backlog item 1, "Signature/stamp/seal detection" — signature half only;
stamp/seal descoped, see module docstring below for why).

Same architecture and provenance pattern as mm_objects.py: ONNX Runtime,
no ultralytics/torch at runtime. Model is a YOLO11s single-class
("signature") detector, exported ONCE locally from public, non-gated
.pt weights (Mels22/Signature-Detection-Verification on Hugging Face,
Apache-2.0, trained on the SignverOD dataset) and committed here as a
versioned asset — same as yolov8s-oiv7.onnx.

Model provenance note: the more widely-cited tech4humans/yolov8s-signature-
detector (higher precision/recall) is HF-gated and requires manually
clicking "Agree" on its model page per-account — no way to script that
without browser credentials for the HF account this project's token
belongs to. Mels22's model is public/ungated, Apache-2.0 (friendlier than
tech4humans' AGPL-3.0 besides), and verified live against a real
cursive-font test image (0.667 confidence, correctly localized) before
being bundled — a real, working alternative, not a downgrade taken on
faith.

Stamp/seal descoped from this item: no equally clean self-hostable
DETECTOR was found (only a stamp/thumb/signature CLASSIFIER exists,
which labels a pre-cropped region rather than localizing one in a full
page — not useful for drawing a box). Left as a known gap for a future
pass once a real detector surfaces, rather than blocking signature
detection on it.
"""
from __future__ import annotations

import base64
import io
import logging
import os
import threading

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "signature-detector.onnx")
_INPUT_SIZE = 640
_CONF_THRESH = 0.35
_IOU_THRESH = 0.45
_MAX_DETECTIONS = 5  # a document rarely has more than a couple of signatures

_session = None
_session_lock = threading.Lock()


def _get_session():
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                import onnxruntime as ort
                _session = ort.InferenceSession(_MODEL_PATH, providers=["CPUExecutionProvider"])
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


def detect_signatures(b64: str) -> list[dict]:
    """Runs the detector over a base64 PNG/JPEG. Returns up to
    _MAX_DETECTIONS {label: "Signature", confidence, bbox: [x,y,w,h]
    normalized 0-1} sorted by confidence descending. [] on any failure or
    no detections — never blocks ingestion, same contract as
    mm_objects.detect_objects."""
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
        out = session.run(None, {session.get_inputs()[0].name: arr})[0]  # (1, 5, 8400)
        pred = out[0].T  # (8400, 5): 4 box coords + 1 class (signature) score

        boxes_cxcywh = pred[:, :4]
        confidences = pred[:, 4]
        keep_mask = confidences >= _CONF_THRESH
        if not keep_mask.any():
            return []
        boxes_cxcywh, confidences = boxes_cxcywh[keep_mask], confidences[keep_mask]

        cx, cy, w, h = boxes_cxcywh[:, 0], boxes_cxcywh[:, 1], boxes_cxcywh[:, 2], boxes_cxcywh[:, 3]
        x0 = (cx - w / 2 - pad_x) / scale
        x1 = (cx + w / 2 - pad_x) / scale
        y0 = (cy - h / 2 - pad_y) / scale
        y1 = (cy + h / 2 - pad_y) / scale
        boxes_xyxy = np.stack([
            np.clip(x0, 0, orig_w), np.clip(y0, 0, orig_h),
            np.clip(x1, 0, orig_w), np.clip(y1, 0, orig_h),
        ], axis=1)

        keep = _nms(boxes_xyxy, confidences)
        results = sorted(((float(confidences[k]), boxes_xyxy[k]) for k in keep), key=lambda t: -t[0])
        results = results[:_MAX_DETECTIONS]

        return [
            {"label": "Signature", "confidence": round(conf, 3),
             "bbox": [round(float(box[0] / orig_w), 4), round(float(box[1] / orig_h), 4),
                      round(float((box[2] - box[0]) / orig_w), 4), round(float((box[3] - box[1]) / orig_h), 4)]}
            for conf, box in results
        ]
    except Exception as exc:
        logger.warning("Signature detection failed: %s", exc)
        return []


def describe_signatures(signatures: list[dict] | None) -> str:
    """Same rationale as mm_objects.describe_objects: baked into the
    stored chunk text (not just the LLM prompt) so groundedness/citation
    scoring — which only ever reads chunk["text"] — can back a "does this
    have a signature" answer."""
    if not signatures:
        return ""
    n = len(signatures)
    return f"{n} signature{'s' if n != 1 else ''} detected in this image."
