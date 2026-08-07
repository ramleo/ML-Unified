"""Noise-residual tampering detection — format-agnostic companion to
mm_tampering.py's JPEG-only ELA (Error Level Analysis).

Every camera sensor imprints a faint, statistically uniform noise texture
across an entire photo. A spliced-in region (pasted from another image,
cloned, or AI-regenerated) breaks that uniformity — it's either
suspiciously smoother (denoised/regenerated) or has a different noise
grain (different source). Unlike ELA, this works on any raster format
(PNG, WebP, BMP, TIFF, JPEG) since it operates on decoded pixels, not a
compression artifact — no reliance on JPEG's block-quantization behavior.

Same {label, confidence, bbox} output contract as detect_tampering, so
mm_tampering.combine_tampering_detections can merge the two detectors'
results into one list.
"""
from __future__ import annotations

import base64
import io
import logging

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_BLOCK = 16  # coarser than ELA's 8px grid — noise variance needs more samples per block to be stable
_OUTLIER_STD = 3.5
_LOCAL_SMOOTH = 5  # box-blur kernel (in blocks) used to build the "expected" local noise level
_MIN_CONFIDENCE = 0.45  # below this, too likely to be ordinary depth-of-field falloff
_EDGE_GUARD_STD = 1.25  # a block this far above the image's own mean edge density is
                        # "genuinely fine real detail" (spokes, wires, hair), not tampering
_MAX_DETECTIONS = 5
_MIN_REGION_FRAC = 0.001


def detect_noise_regions(b64: str) -> list[dict]:
    """Returns up to _MAX_DETECTIONS {label: "Tampering", confidence, bbox:
    [x,y,w,h] normalized 0-1} sorted by confidence descending — same schema
    as detect_tampering/detect_objects/detect_signatures. [] on any failure
    or no suspicious regions; never blocks ingestion."""
    try:
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        orig_w, orig_h = img.size
        if orig_w == 0 or orig_h == 0:
            return []

        gray = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2GRAY)
        denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)
        residual = np.abs(gray.astype(np.float32) - denoised.astype(np.float32))

        # Real fine detail — bicycle spokes, wire fences, hair, foliage — gets
        # smoothed away by the denoiser almost as aggressively as actual
        # sensor noise, producing the same "this block got flattened" residual
        # a genuine tampered/regenerated patch would. Sobel edge magnitude on
        # the ORIGINAL (pre-denoise) image tells the two apart: fine real
        # detail has a lot of real gradient there to begin with; a smoothed-in
        # fake patch generally doesn't.
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        edge_mag = cv2.magnitude(gx, gy)

        h_blocks, w_blocks = orig_h // _BLOCK, orig_w // _BLOCK
        if h_blocks < 2 or w_blocks < 2:
            return []
        cropped = residual[:h_blocks * _BLOCK, :w_blocks * _BLOCK]
        block_energy = cropped.reshape(h_blocks, _BLOCK, w_blocks, _BLOCK).mean(axis=(1, 3))
        cropped_edge = edge_mag[:h_blocks * _BLOCK, :w_blocks * _BLOCK]
        block_edge = cropped_edge.reshape(h_blocks, _BLOCK, w_blocks, _BLOCK).mean(axis=(1, 3))
        edge_mean, edge_std = float(block_edge.mean()), float(block_edge.std())

        # Compare each block against its LOCAL neighborhood's expected noise
        # level, not the whole image's. A real photo's noise texture varies
        # gradually across the frame on its own — depth-of-field blur, a
        # smooth sky next to a textured foreground — none of that is
        # tampering. A high-pass (block minus its local smoothed average)
        # cancels that gradual variation out and leaves only the SHARP local
        # jumps a genuine spliced-in patch actually creates.
        local_avg = cv2.blur(block_energy, (_LOCAL_SMOOTH, _LOCAL_SMOOTH))
        local_dev = block_energy - local_avg

        mean, std = float(local_dev.mean()), float(local_dev.std())
        if std < 1e-6:
            return []
        # Outliers in EITHER direction: suspiciously smooth (denoised/
        # regenerated patch) OR suspiciously grainy (mismatched source) —
        # both are "this block's noise texture doesn't match its
        # surroundings," just opposite symptoms of the same underlying tell.
        mask = (np.abs(local_dev - mean) > _OUTLIER_STD * std).astype(np.uint8)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        min_blocks = max(2, int(_MIN_REGION_FRAC * h_blocks * w_blocks))

        candidates = []
        for i in range(1, num_labels):  # label 0 is background
            area = stats[i, cv2.CC_STAT_AREA]
            if area < min_blocks:
                continue
            bx, by = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP]
            bw, bh = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
            region_dev = float(local_dev[labels == i].mean())
            confidence = float(np.clip(abs(region_dev - mean) / (4.0 * std), 0, 1))
            if confidence < _MIN_CONFIDENCE:
                continue
            # Only the "suspiciously grainier than neighbors" direction is
            # confusable with fine real detail — a "suspiciously smoother"
            # region (the other outlier direction, a plausible denoised/
            # regenerated patch) doesn't have this failure mode, so the
            # guard only applies here.
            if region_dev > 0 and edge_std > 1e-6:
                region_edge = float(block_edge[labels == i].mean())
                if region_edge > edge_mean + _EDGE_GUARD_STD * edge_std:
                    continue
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
        logger.warning("Noise-residual tampering detection failed: %s", exc)
        return []
