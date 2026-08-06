"""ELA (Error Level Analysis) tampering detection for standalone image and
video-frame citations (backlog item 2). Pure image processing — no ONNX
model, unlike mm_objects.py/mm_signatures.py.

Re-saves the image as JPEG at a fixed quality and diffs it pixel-by-pixel
against the original. A region that was spliced/edited in after the image's
last real save hasn't "settled" into a stable JPEG compression error level
the way the untouched surroundings have, so it lights up brighter in that
diff. Only a reliable signal on JPEG-sourced content — a PNG/lossless
original, a screenshot, or an image already resaved many times can give
noisy or muted results, so this is surfaced to the user as "possible"
regions worth a look, not a verdict.
"""
from __future__ import annotations

import base64
import io
import logging

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_ELA_QUALITY = 90
_ELA_SCALE = 12       # amplifies the raw per-pixel diff enough to threshold
_BLOCK = 8              # JPEG's native compression block size
_MAX_DETECTIONS = 5
_MIN_REGION_FRAC = 0.001  # ignore blobs under ~0.1% of image area as noise


def detect_tampering(b64: str) -> list[dict]:
    """Returns up to _MAX_DETECTIONS {label: "Tampering", confidence, bbox:
    [x,y,w,h] normalized 0-1} sorted by confidence descending — same schema
    mm_objects/mm_signatures use, so the frontend can reuse one box-render
    path. [] on any failure or no suspicious regions found; never blocks
    ingestion."""
    try:
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        orig_w, orig_h = img.size
        if orig_w == 0 or orig_h == 0:
            return []

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_ELA_QUALITY)
        buf.seek(0)
        resaved = Image.open(buf).convert("RGB")

        diff = np.abs(np.asarray(img, dtype=np.int16) - np.asarray(resaved, dtype=np.int16))
        diff_gray = np.clip(diff.max(axis=2).astype(np.float32) * _ELA_SCALE, 0, 255)

        # Blockwise mean error on JPEG's own compression grid is a steadier
        # tamper signal than raw per-pixel noise — it smooths away JPEG's
        # inherent per-pixel jitter without smoothing away a genuinely
        # edited region, which spans many blocks at once.
        h_blocks, w_blocks = orig_h // _BLOCK, orig_w // _BLOCK
        if h_blocks < 2 or w_blocks < 2:
            return []
        cropped = diff_gray[:h_blocks * _BLOCK, :w_blocks * _BLOCK]
        block_err = cropped.reshape(h_blocks, _BLOCK, w_blocks, _BLOCK).mean(axis=(1, 3))

        mean, std = float(block_err.mean()), float(block_err.std())
        if std < 1e-6:
            return []
        threshold = mean + 2.0 * std
        mask = (block_err > threshold).astype(np.uint8)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        min_blocks = max(2, int(_MIN_REGION_FRAC * h_blocks * w_blocks))

        candidates = []
        for i in range(1, num_labels):  # label 0 is background
            area = stats[i, cv2.CC_STAT_AREA]
            if area < min_blocks:
                continue
            bx, by = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP]
            bw, bh = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
            region_err = float(block_err[labels == i].mean())
            confidence = float(np.clip((region_err - mean) / (4.0 * std), 0, 1))
            # int(...) here — stats[] entries are numpy int32, which
            # json.dumps (encode_objects, ingest.py) can't serialize; every
            # other numeric field in this module is already cast to a
            # native Python type before being returned.
            x0, y0 = int(bx * _BLOCK), int(by * _BLOCK)
            x1, y1 = min(orig_w, int((bx + bw) * _BLOCK)), min(orig_h, int((by + bh) * _BLOCK))
            candidates.append((confidence, x0, y0, x1, y1))

        candidates.sort(key=lambda t: -t[0])
        candidates = candidates[:_MAX_DETECTIONS]

        return [
            {"label": "Tampering", "confidence": round(conf, 3),
             "bbox": [round(x0 / orig_w, 4), round(y0 / orig_h, 4),
                      round((x1 - x0) / orig_w, 4), round((y1 - y0) / orig_h, 4)]}
            for conf, x0, y0, x1, y1 in candidates
        ]
    except Exception as exc:
        logger.warning("Tampering detection failed: %s", exc)
        return []


def describe_tampering(regions: list[dict] | None) -> str:
    """Same rationale as mm_objects.describe_objects / mm_signatures
    .describe_signatures: baked into the stored chunk text (not just the
    LLM prompt) so groundedness/citation scoring, which only ever reads
    chunk["text"], can back a "does this look edited" answer."""
    if not regions:
        return ""
    n = len(regions)
    return (f"Possible tampering detected: {n} region{'s' if n != 1 else ''} with elevated "
            "JPEG compression error (may indicate editing) — not a certainty, verify visually.")
