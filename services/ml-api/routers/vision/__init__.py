"""Vision router package — exposes combined router and init_vision_models()."""
from fastapi import APIRouter

from .classify import router as _clf
from .processing import router as _proc
from .detection import router as _det
from .segmentation import router as _seg

# No prefix — frontend calls /classify-image, /detect-objects, etc. at root.
router = APIRouter()
router.include_router(_clf)
router.include_router(_proc)
router.include_router(_det)
router.include_router(_seg)


def init_vision_models() -> None:
    """
    Download detection and segmentation model files to disk on startup.

    Called from ml-unified's lifespan background thread so the first real
    inference request doesn't have to wait for a 35-140 MB download (which
    would cause a 502 on Render/HF free tier).
    """
    from .detection import _ensure_det_model
    from .segmentation import _ensure_segformer_model

    for fn in (lambda: _ensure_det_model("tiny_yolov3"), _ensure_segformer_model):
        try:
            fn()
        except Exception as exc:
            print(f"[vision warmup] download failed: {exc}", flush=True)
