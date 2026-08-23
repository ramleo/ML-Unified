"""Phase-correlation frame alignment for the Plant Growth time-lapse GIF
export — corrects for camera shake (pure translation) between shots in an
uploaded photo series, so the exported GIF doesn't visibly "jump" between
frames from ordinary handheld reframing.

Deliberately NOT part of the growth measurement itself: _measure_frame
already handles a shifted/reframed shot by re-detecting each plant's own
box per frame (crop-then-measure, see mm_plant_growth.py's module
docstring) — camera shake was never a measurement-accuracy problem. This
module exists purely to make the GIF EXPORT (PlantGrowthGif.tsx, entirely
client-side, no backend call of its own) look smoother, since the frontend
has no way to re-crop/re-detect on its own.

Real, disclosed limitation: cv2.phaseCorrelate only recovers pure
translation (the camera panned/shifted sideways) — it does NOT correct for
a zoom or distance change between shots, which mm_plant_growth.py's own
module docstring already names as an existing "consistent framing"
assumption this tool has always made. A frame whose original pixel
dimensions differ from the reference frame's is resized to match before
correlating, which can itself introduce a small error if the two photos'
aspect ratios genuinely differ (same "same distance/zoom" assumption,
not a new one).
"""
from __future__ import annotations

import logging

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_ALIGN_MAX_DIM = 256  # alignment doesn't need full resolution; keeps phaseCorrelate fast


def _downsample_gray(img: Image.Image) -> tuple[np.ndarray, float]:
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    h, w = gray.shape
    scale = min(1.0, _ALIGN_MAX_DIM / max(h, w))
    if scale < 1.0:
        gray = cv2.resize(gray, (max(1, int(w * scale)), max(1, int(h * scale))))
    return gray, scale


def compute_frame_alignment(imgs: list[Image.Image | None]) -> list[list[float]]:
    """Returns one [dx, dy] offset per input image, in the REFERENCE
    frame's original-pixel units, relative to the first successfully-
    decoded image — [0.0, 0.0] for that reference frame itself and for any
    frame that failed to decode or align. A caller shifts each frame's own
    draw position by SUBTRACTING its offset (moving the frame back toward
    the reference) before compositing, so a camera pan doesn't show up as
    visible jitter across the exported sequence."""
    offsets: list[list[float]] = [[0.0, 0.0] for _ in imgs]
    ref_idx = next((i for i, im in enumerate(imgs) if im is not None), None)
    if ref_idx is None:
        return offsets
    try:
        ref_gray, ref_scale = _downsample_gray(imgs[ref_idx])
    except Exception as exc:
        logger.warning("Plant growth alignment reference prep failed: %s", exc)
        return offsets

    for i, img in enumerate(imgs):
        if i == ref_idx or img is None:
            continue
        try:
            gray, _scale = _downsample_gray(img)
            if gray.shape != ref_gray.shape:
                # Different original photo dimensions (or aspect ratio) than
                # the reference — resize onto the reference's downsampled
                # grid so phaseCorrelate (which requires matching shapes)
                # can run at all. See module docstring's caveat.
                gray = cv2.resize(gray, (ref_gray.shape[1], ref_gray.shape[0]))
            (dx, dy), _response = cv2.phaseCorrelate(ref_gray, gray)
            offsets[i] = [round(dx / ref_scale, 2), round(dy / ref_scale, 2)]
        except Exception as exc:
            logger.warning("Plant growth alignment failed for frame %d: %s", i, exc)
    return offsets
