"""
PPE compliance check (hard hat / safety vest) — pending-list #29.

The existing 601-class OIV7 detector (`mm_objects.py`) has a generic
`Helmet` class but no safety-vest class of any kind (verified against
`OIV7_CLASSES` directly, not assumed) — a dedicated PPE model is
genuinely required here, unlike the plate/weapon/PPE-adjacent features
that reused existing detector classes.

Model: Hansung-Cho/yolov8-ppe-detection (MIT-licensed weights), a
YOLOv8n fine-tune with real positive/negative classes (Hardhat/
NO-Hardhat, Safety Vest/NO-Safety Vest, Mask/NO-Mask, Person, Safety
Cone, machinery, vehicle). Hands-on tested before building, not trusted
from the model card alone (same discipline as the fire-detection
rejection): an initial test on a very low-resolution photo gave a weak
result, investigated and found to be a resolution confound, not a model
problem — re-tested on 3 higher-resolution real photos and got a real,
confident pass (Hardhat 0.72-0.88, Safety Vest 0.39-0.69, correctly
avoided claiming "worn" PPE on a photo of gear just lying on the ground).

License/architecture note: the weights are MIT, but running them via
`ultralytics.YOLO` needs the AGPL-3.0 `ultralytics` package, which this
project does not otherwise depend on (the existing OIV7 detector avoids
this the same way: serve a locally-exported ONNX file through
`onnxruntime`, already a dependency). `best.pt` was exported to ONNX
once, locally, with a dev-only `ultralytics` install never added to
`requirements*.txt` — verified the ONNX output matches the tested `.pt`
output on the same 3 real photos before committing `yolov8n-ppe.onnx`.

Deliberately NOT done, disclosed rather than glossed over:
- Compliance is read from whichever explicit signal fired (Hardhat vs.
  NO-Hardhat, Safety Vest vs. NO-Safety Vest) — never inferred from "no
  positive detection," which is indistinguishable from a missed
  detection (exactly the failure mode the low-res test exposed).
- Per-person item attribution is a spatial heuristic (head/torso region
  overlap with each detected Person box), not real per-person tracking
  or pose estimation — a crowded/overlapping-people photo can
  misattribute an item to the wrong person.
"""

import base64
import io
import logging
import os
import threading

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel

from routers.rag.mm_objects import _nms

logger = logging.getLogger(__name__)
router = APIRouter()

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "yolov8n-ppe.onnx")
_INPUT_SIZE = 640
_CONF_THRESH = 0.25
_IOU_THRESH = 0.45
_MAX_IMAGE_BYTES = 8 * 1024 * 1024

_PPE_CLASSES = [
    "Hardhat", "Mask", "NO-Hardhat", "NO-Mask", "NO-Safety Vest",
    "Person", "Safety Cone", "Safety Vest", "machinery", "vehicle",
]
_HEAD_LABELS = {"Hardhat", "NO-Hardhat"}
_VEST_LABELS = {"Safety Vest", "NO-Safety Vest"}

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


def _infer_raw(img: Image.Image):
    orig_w, orig_h = img.size
    scale = min(_INPUT_SIZE / orig_w, _INPUT_SIZE / orig_h)
    new_w, new_h = max(1, round(orig_w * scale)), max(1, round(orig_h * scale))
    resized = img.resize((new_w, new_h), Image.BILINEAR)
    canvas = Image.new("RGB", (_INPUT_SIZE, _INPUT_SIZE), (114, 114, 114))
    pad_x, pad_y = (_INPUT_SIZE - new_w) // 2, (_INPUT_SIZE - new_h) // 2
    canvas.paste(resized, (pad_x, pad_y))

    arr = np.asarray(canvas).astype(np.float32) / 255.0
    arr = arr.transpose(2, 0, 1)[None, ...]

    session = _get_session()
    out = session.run(None, {session.get_inputs()[0].name: arr})[0]
    pred = out[0].T
    return pred, orig_w, orig_h, scale, pad_x, pad_y


def _decode_ppe_detections(pred, orig_w, orig_h, scale, pad_x, pad_y) -> list[dict]:
    boxes_cxcywh = pred[:, :4]
    class_ids = np.argmax(pred[:, 4:], axis=1)
    confidences = np.max(pred[:, 4:], axis=1)

    keep_mask = confidences >= _CONF_THRESH
    if not keep_mask.any():
        return []
    boxes_cxcywh, class_ids, confidences = boxes_cxcywh[keep_mask], class_ids[keep_mask], confidences[keep_mask]

    cx, cy, w, h = boxes_cxcywh[:, 0], boxes_cxcywh[:, 1], boxes_cxcywh[:, 2], boxes_cxcywh[:, 3]
    x0 = (cx - w / 2 - pad_x) / scale
    x1 = (cx + w / 2 - pad_x) / scale
    y0 = (cy - h / 2 - pad_y) / scale
    y1 = (cy + h / 2 - pad_y) / scale
    boxes_xyxy = np.stack([
        np.clip(x0, 0, orig_w), np.clip(y0, 0, orig_h),
        np.clip(x1, 0, orig_w), np.clip(y1, 0, orig_h),
    ], axis=1)

    detections = []
    for c in np.unique(class_ids):
        mask = class_ids == c
        b, s = boxes_xyxy[mask], confidences[mask]
        for k in _nms(b, s, iou_thresh=_IOU_THRESH):
            detections.append({"label": _PPE_CLASSES[int(c)], "confidence": float(s[k]), "box": b[k].tolist()})
    return detections


def _box_center(box: list[float]) -> tuple[float, float]:
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def _associate_people(detections: list[dict]) -> tuple[list[dict], list[dict]]:
    """Attributes Hardhat/NO-Hardhat boxes to a Person's head region (top
    ~40% of their box) and Safety Vest/NO-Safety Vest boxes to the torso
    region (middle band) by center-point containment + horizontal
    overlap. A real, disclosed simplification — no per-person tracking,
    so overlapping people can misattribute an item."""
    people = [d for d in detections if d["label"] == "Person"]
    head_items = [d for d in detections if d["label"] in _HEAD_LABELS]
    vest_items = [d for d in detections if d["label"] in _VEST_LABELS]
    consumed_head, consumed_vest = set(), set()

    def best_match(person_box, candidates, consumed, y_lo_frac, y_hi_frac):
        px0, py0, px1, py1 = person_box
        ph = py1 - py0
        y_lo, y_hi = py0 + ph * y_lo_frac, py0 + ph * y_hi_frac
        best_i, best_conf = None, -1.0
        for i, item in enumerate(candidates):
            if i in consumed:
                continue
            cx, cy = _box_center(item["box"])
            if px0 <= cx <= px1 and y_lo <= cy <= y_hi and item["confidence"] > best_conf:
                best_i, best_conf = i, item["confidence"]
        return best_i

    people_out = []
    for person in people:
        hi = best_match(person["box"], head_items, consumed_head, 0.0, 0.4)
        vi = best_match(person["box"], vest_items, consumed_vest, 0.2, 1.0)

        hardhat_status, hardhat_conf = "unclear", None
        if hi is not None:
            consumed_head.add(hi)
            item = head_items[hi]
            hardhat_status = "present" if item["label"] == "Hardhat" else "missing"
            hardhat_conf = item["confidence"]

        vest_status, vest_conf = "unclear", None
        if vi is not None:
            consumed_vest.add(vi)
            item = vest_items[vi]
            vest_status = "present" if item["label"] == "Safety Vest" else "missing"
            vest_conf = item["confidence"]

        people_out.append({
            "box": person["box"], "person_confidence": person["confidence"],
            "hardhat": hardhat_status, "hardhat_confidence": hardhat_conf,
            "safety_vest": vest_status, "safety_vest_confidence": vest_conf,
        })

    unattributed = (
        [head_items[i] for i in range(len(head_items)) if i not in consumed_head]
        + [vest_items[i] for i in range(len(vest_items)) if i not in consumed_vest]
    )
    return people_out, unattributed


_BOX_COLORS = {"present": (34, 197, 94), "missing": (239, 68, 68), "unclear": (156, 163, 175)}


def _annotate(color_img: np.ndarray, people: list[dict]) -> str:
    img = color_img.copy()
    for p in people:
        x0, y0, x1, y1 = [int(v) for v in p["box"]]
        cv2.rectangle(img, (x0, y0), (x1, y1), (99, 102, 241), 2)
        label = f"hardhat:{p['hardhat']} vest:{p['safety_vest']}"
        cv2.putText(img, label, (x0, max(0, y0 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (99, 102, 241), 1, cv2.LINE_AA)
    buf = cv2.imencode(".jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])[1]
    return base64.b64encode(buf).decode()


class PpeCheckRequest(BaseModel):
    image: str  # base64, no data URL prefix


def run_ppe_check(image_b64: str) -> dict:
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode this as an image.")
    if len(raw) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image too large (max 8MB).")
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode this as an image.")

    pred, ow, oh, scale, pad_x, pad_y = _infer_raw(img)
    detections = _decode_ppe_detections(pred, ow, oh, scale, pad_x, pad_y)
    people, unattributed = _associate_people(detections)

    warnings = []
    if not people:
        warnings.append("No person detected in this photo.")
    if unattributed:
        warnings.append(f"{len(unattributed)} PPE item(s) detected but couldn't be attributed to a specific person.")

    annotated = _annotate(np.asarray(img), people)

    return {
        "people": people,
        "unattributed": [{"label": u["label"], "confidence": u["confidence"]} for u in unattributed],
        "annotated_image": annotated,
        "warnings": warnings,
    }


@router.post("/mm-ppe-compliance/check")
def ppe_compliance_check(body: PpeCheckRequest):
    return run_ppe_check(body.image)
