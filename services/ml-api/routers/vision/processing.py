"""Vision image-processing routes: /image-operations, /process-image."""
import io
from typing import Any, Dict

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .shared import _MAX_IMG_DIM

router = APIRouter(tags=["vision"])

# ── Operation registry ────────────────────────────────────────────────────────

_IMG_OPERATIONS: Dict[str, Dict] = {
    "grayscale":  {"label": "Grayscale",       "params": []},
    "blur":       {"label": "Gaussian Blur",   "params": [{"name": "blur_radius",       "label": "Radius",   "min": 1,    "max": 20,  "default": 3,   "step": 1}]},
    "sharpen":    {"label": "Sharpen",         "params": [{"name": "sharpen_factor",    "label": "Strength", "min": 1.0,  "max": 5.0, "default": 2.0, "step": 0.5}]},
    "edges":      {"label": "Edge Detection",  "params": []},
    "rotate":     {"label": "Rotate",          "params": [{"name": "rotate_angle",      "label": "Angle deg",  "min": -180, "max": 180, "default": 90,  "step": 1}]},
    "brightness": {"label": "Brightness",      "params": [{"name": "brightness_factor", "label": "Factor",   "min": 0.1,  "max": 3.0, "default": 1.5, "step": 0.1}]},
    "contrast":   {"label": "Contrast",        "params": [{"name": "contrast_factor",   "label": "Factor",   "min": 0.1,  "max": 3.0, "default": 1.5, "step": 0.1}]},
    "flip_h":     {"label": "Flip Horizontal", "params": []},
    "flip_v":     {"label": "Flip Vertical",   "params": []},
    "emboss":     {"label": "Emboss",          "params": []},
    "invert":     {"label": "Invert Colors",   "params": []},
}

# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/image-operations")
def list_image_operations():
    return [{"id": k, "label": v["label"], "params": v["params"]} for k, v in _IMG_OPERATIONS.items()]


@router.post("/process-image")
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
