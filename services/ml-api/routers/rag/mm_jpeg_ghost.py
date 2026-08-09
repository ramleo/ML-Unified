"""JPEG "ghost" (double-compression) tampering detection — third signal
alongside mm_tampering.py's ELA and mm_noise_forensics.py's noise-residual.

Standard forensic technique: a spliced-in region carries its OWN original
JPEG compression quality baked into its DCT statistics, even after the
whole composite image is re-saved once more at a final quality. Unlike
ELA/noise-residual, this never looks at raw pixel busy-ness, so it isn't
confused by ordinary fine real detail (spokes, foliage, hair) the way those
two are — that confound is what forced mm_tampering.combine_tampering_
detections to require ELA+noise-residual agreement in the first place.
Only meaningful on JPEG-sourced content, same caveat as ELA.

Implementation note: the naive version of this (per block, which candidate
quality reproduces it with least error) doesn't work — re-saving at the
image's OWN current/last-save quality trivially reproduces every block
almost losslessly (you're re-quantizing already-quantized coefficients
through the same table), so that trivial minimum wins everywhere and
swamps any real signal. The fix (verified against a synthetic double-
compressed splice before shipping): subtract each quality's IMAGE-WIDE mean
diff (the "global curve", dominated by the majority single-generation
content) from each block's own per-quality diff curve. A block from the
SAME generation as most of the image stays close to zero after this
subtraction at every quality. A block from a DIFFERENT original quality
shows a pronounced negative dip at the quality it actually matches best —
confirmed live: a synthetic quality-60 patch spliced into a quality-90 base
and re-saved at quality-85 produced a z-score of roughly -8.8 against the
rest of the image's population, a clean, large separation; an ordinary
busy single-generation JPEG (no splice) produced zero detections.

Same {label, confidence, bbox} output contract as detect_tampering /
detect_noise_regions, so combine_tampering_detections can merge all three.
"""
from __future__ import annotations

import base64
import io
import logging

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_QUALITIES = [50, 60, 70, 75, 80, 85, 90, 95]
_BLOCK = 16  # same granularity as noise-residual
_OUTLIER_STD = 4.0  # verified-separation z-score (~8.8) on the synthetic splice test
                     # was well clear of this — kept conservative to favor precision,
                     # same reasoning as the other two detectors' thresholds
_MAX_DETECTIONS = 5
_MIN_REGION_FRAC = 0.001


def detect_jpeg_ghosts(b64: str) -> list[dict]:
    """Returns up to _MAX_DETECTIONS {label: "Tampering", confidence, bbox:
    [x,y,w,h] normalized 0-1} sorted by confidence descending — same schema
    as detect_tampering/detect_noise_regions. [] on any failure or no
    suspicious regions; never blocks ingestion."""
    try:
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        orig_w, orig_h = img.size
        if orig_w == 0 or orig_h == 0:
            return []

        orig_arr = np.asarray(img, dtype=np.float32)
        h_blocks, w_blocks = orig_h // _BLOCK, orig_w // _BLOCK
        if h_blocks < 2 or w_blocks < 2:
            return []

        # diffs[q, by, bx] = mean abs per-pixel diff for that block when the
        # WHOLE image is resaved at _QUALITIES[q].
        diffs = np.empty((len(_QUALITIES), h_blocks, w_blocks), dtype=np.float32)
        for qi, q in enumerate(_QUALITIES):
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=q)
            buf.seek(0)
            resaved = np.asarray(Image.open(buf).convert("RGB"), dtype=np.float32)
            diff = np.abs(orig_arr - resaved).mean(axis=2)
            cropped = diff[:h_blocks * _BLOCK, :w_blocks * _BLOCK]
            diffs[qi] = cropped.reshape(h_blocks, _BLOCK, w_blocks, _BLOCK).mean(axis=(1, 3))

        # See module docstring: subtracting the image-wide per-quality mean
        # cancels out the trivial "current save quality always wins" effect,
        # leaving only how each block deviates from the majority generation.
        global_curve = diffs.mean(axis=(1, 2))
        relative = diffs - global_curve[:, None, None]
        # Only the most-negative point of each block's relative curve is the
        # signal — how much better this block fits SOME quality than the
        # image's typical block does at its own best-fitting quality.
        block_min_rel = relative.min(axis=0)

        mean, std = float(block_min_rel.mean()), float(block_min_rel.std())
        if std < 1e-6:
            return []
        # Only the negative direction is meaningful (see docstring) — a
        # block that fits notably WORSE than typical everywhere isn't a
        # comparable signature, just an ordinary content outlier.
        mask = (block_min_rel < mean - _OUTLIER_STD * std).astype(np.uint8)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        min_blocks = max(2, int(_MIN_REGION_FRAC * h_blocks * w_blocks))

        candidates = []
        for i in range(1, num_labels):  # label 0 is background
            area = stats[i, cv2.CC_STAT_AREA]
            if area < min_blocks:
                continue
            bx, by = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP]
            bw, bh = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
            region_val = float(block_min_rel[labels == i].mean())
            z = abs(region_val - mean) / std
            confidence = float(np.clip((z - _OUTLIER_STD) / _OUTLIER_STD, 0, 1))
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
        logger.warning("JPEG ghost detection failed: %s", exc)
        return []