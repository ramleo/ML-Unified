"""Monocular depth estimation — a single 2D photo in, a per-pixel depth map
out, used by the frontend to drive a live parallax "diorama" effect (near
things shift more than far things as the viewer moves the pointer/tilts the
device) plus a plain grayscale depth-map view.

Model: Depth-Anything-V2-Small (quantized ONNX, ~37MB, DINOv2-backed), from
onnx-community/depth-anything-v2-small-ONNX. License checked directly, not
from a badge: the DepthAnything/Depth-Anything-V2 upstream repo licenses the
Small checkpoint specifically as Apache-2.0 (Base/Large/Giant are
CC-BY-NC-4.0 — not used here). Hands-on verified before adopting: ran real
inference against a real photo (a car) and confirmed the output map cleanly
separated foreground from background with a smooth gradient, not noise —
same "verify before building" bar as every other model in this codebase.

Output is a *relative* depth map (higher value = nearer), not metric
distance — Depth-Anything-V2 doesn't claim real-world units, only correct
relative ordering within a single image. That's exactly what the parallax
effect needs and nothing more."""
from __future__ import annotations

import base64
import io
import logging
import os
import threading

import numpy as np
from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "depth", "model_quantized.onnx")
# Model was trained/exported at inputs sized in multiples of 14 (DINOv2 patch
# size) with the short side ~518 — mirrors onnx-community's own
# preprocessor_config.json rather than guessing.
_TARGET_SHORT_SIDE = 518
_PATCH_MULTIPLE = 14
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
_MAX_DIM = 1024  # cap the input photo's longer side before inference — a 37MB CPU model on a full-res upload would be slow for no visual-quality gain

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


def _preprocess(img: Image.Image) -> tuple[np.ndarray, tuple[int, int]]:
    w, h = img.size
    if max(w, h) > _MAX_DIM:
        scale = _MAX_DIM / max(w, h)
        w, h = round(w * scale), round(h * scale)
        img = img.resize((w, h), Image.BICUBIC)

    scale = _TARGET_SHORT_SIDE / min(w, h)
    new_w = max(_PATCH_MULTIPLE, round(w * scale / _PATCH_MULTIPLE) * _PATCH_MULTIPLE)
    new_h = max(_PATCH_MULTIPLE, round(h * scale / _PATCH_MULTIPLE) * _PATCH_MULTIPLE)
    resized = img.resize((new_w, new_h), Image.BICUBIC)

    arr = np.asarray(resized).astype(np.float32) / 255.0
    arr = (arr - _MEAN) / _STD
    arr = arr.transpose(2, 0, 1)[None].astype(np.float32)
    return arr, (w, h)


def estimate_depth(b64: str) -> dict:
    """Returns {"depth_map": b64 PNG (grayscale, same pixel size as the
    input photo) | None, "width": int, "height": int, "error": str | None}.
    depth_map values are relative (brighter = nearer), normalized 0-255
    per-image — there's no cross-image scale to preserve, each depth map
    only needs to be internally consistent for the parallax effect."""
    try:
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    except Exception as exc:
        logger.warning("Depth: could not decode image: %s", exc)
        return {"depth_map": None, "width": 0, "height": 0, "error": "could not decode image"}

    orig_w, orig_h = img.size

    try:
        batch, (proc_w, proc_h) = _preprocess(img)
        session = _get_session()
        out = session.run(None, {session.get_inputs()[0].name: batch})[0]
        depth = out[0]
        if depth.ndim == 3:
            depth = depth[0]

        d = depth - depth.min()
        d = d / (d.max() + 1e-8)
        depth_u8 = (d * 255).astype(np.uint8)

        depth_img = Image.fromarray(depth_u8, mode="L").resize((orig_w, orig_h), Image.BICUBIC)
        buf = io.BytesIO()
        depth_img.save(buf, format="PNG")
        depth_b64 = base64.b64encode(buf.getvalue()).decode()
        return {"depth_map": depth_b64, "width": orig_w, "height": orig_h, "error": None}
    except Exception as exc:
        logger.warning("Depth inference failed: %s", exc)
        return {"depth_map": None, "width": orig_w, "height": orig_h, "error": "inference failed"}


class DepthRequest(BaseModel):
    image: str  # b64 image, any common format


@router.post("/mm-depth")
def depth_endpoint(body: DepthRequest):
    if not body.image.strip():
        raise HTTPException(status_code=400, detail="image is required")
    return estimate_depth(body.image)
