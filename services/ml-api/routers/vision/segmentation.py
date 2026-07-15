"""Vision segmentation routes: /seg-models, /segment-image."""
import io
import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from .shared import (
    VISION_CACHE_DIR,
    _large_vision_cache,
    _large_vision_lock,
    StreamingTask,
    download_model,
    ort_session,
)

router = APIRouter(tags=["vision"])

# ── SegFormer-B0 config ───────────────────────────────────────────────────────
# 4.4 MB quantized ONNX — ADE20K 150-class semantic segmentation.
# Downloads from Hugging Face (Xenova/segformer-b0-finetuned-ade-512-512).

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
        h = (i * 0.618033988) % 1.0  # golden-ratio hue spacing
        r, g, b = colorsys.hsv_to_rgb(h, 0.75, 0.90)
        out.append((int(r * 255), int(g * 255), int(b * 255)))
    return out


_SEGFORMER_PALETTE: list = _make_segformer_palette()

# ── PIL colour-quantisation fallback ─────────────────────────────────────────

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


# ── SegFormer helpers ─────────────────────────────────────────────────────────

def _ensure_segformer_model() -> str:
    if not os.path.exists(_SEGFORMER_PATH):
        download_model(_SEGFORMER_URL, _SEGFORMER_PATH)
    return _SEGFORMER_PATH


def _load_segformer_session():
    import gc
    path = _ensure_segformer_model()
    with _large_vision_lock:
        _large_vision_cache.clear()
        gc.collect()
        session = ort_session(path)
        _large_vision_cache["model_type"] = "seg"
        _large_vision_cache["model_id"]   = "segformer_b0"
        _large_vision_cache["session"]    = session
    return session


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/seg-models")
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


@router.post("/segment-image")
async def segment_image(
    file:       UploadFile = File(...),
    model_name: str        = Form("segformer_b0"),
):
    from PIL import Image as PILImage  # noqa: PLC0415

    if model_name not in ("segformer_b0", "color_segmentation"):
        raise HTTPException(400, f"Unknown model: {model_name}")

    raw = await file.read()

    # color_segmentation is fast — return plain JSON (no streaming needed)
    if model_name == "color_segmentation":
        try:
            img = PILImage.open(io.BytesIO(raw)).convert("RGB")
        except Exception:
            raise HTTPException(400, "Cannot read image file")
        return _pil_segment(img, img.width, img.height)

    if not os.path.exists(_SEGFORMER_PATH):
        raise HTTPException(503, "Vision service is warming up — please try again in ~30 seconds")

    task = StreamingTask()

    def work(p):
        from PIL import Image as PILImage2  # noqa: PLC0415
        import numpy as np                  # noqa: PLC0415
        import base64                       # noqa: PLC0415

        p.update(5, "Decoding image")
        try:
            img = PILImage2.open(io.BytesIO(raw)).convert("RGB")
        except Exception:
            p.finish(error="Cannot read image file")
            return
        orig_w, orig_h = img.width, img.height

        with _large_vision_lock:
            cached  = (_large_vision_cache.get("model_type") == "seg"
                       and _large_vision_cache.get("model_id") == "segformer_b0")
            session = _large_vision_cache.get("session") if cached else None

        p.update(20, "Model cached" if cached else "Loading model")
        if session is None:
            try:
                session = _load_segformer_session()
            except Exception as e:
                p.finish(error=f"Failed to load segmentation model: {e}")
                return

        p.update(40, "Preprocessing image")
        try:
            arr = np.array(img.resize((512, 512), PILImage2.LANCZOS), dtype=np.float32) / 255.0
            arr = (arr - np.array([0.485, 0.456, 0.406])) / np.array([0.229, 0.224, 0.225])
            arr = arr.transpose(2, 0, 1)[np.newaxis].astype(np.float32)
        except Exception as e:
            p.finish(error=f"Preprocessing failed: {e}")
            return

        p.update(65, "Running inference")
        try:
            logits = session.run(["logits"], {"pixel_values": arr})[0]
        except Exception:
            p.finish(error="Segmentation failed — please try again")
            return

        p.update(85, "Building overlay")
        try:
            label_map  = np.argmax(logits[0], axis=0).astype(np.uint8)
            label_full = np.array(
                PILImage2.fromarray(label_map, mode="L").resize((orig_w, orig_h), PILImage2.NEAREST)
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
            composite = PILImage2.alpha_composite(
                img.convert("RGBA"),
                PILImage2.fromarray(colour_mask, mode="RGBA"),
            ).convert("RGB")
            buf = io.BytesIO()
            composite.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            p.finish(error=f"Overlay failed: {e}")
            return

        p.finish(result={
            "model":         "segformer_b0",
            "model_label":   "SegFormer-B0 (ADE20K 150 classes)",
            "classes_found": classes_found,
            "image_b64":     f"data:image/png;base64,{b64}",
            "orig_width":    orig_w,
            "orig_height":   orig_h,
        })

    return StreamingResponse(task.stream(work), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
