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

combine_tampering_detections() below merges this module's ELA output with
mm_noise_forensics.detect_noise_regions() — a format-agnostic second
signal — into one final list, discounting ELA-only detections when the
upload wasn't actually JPEG-sourced (its core assumption doesn't hold
there) while leaving noise-residual and agreed-upon detections at full
strength.
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
    chunk["text"], can back a "does this look edited" answer. Wording is
    detector-agnostic since `regions` may have come from ELA, noise-residual,
    or both merged together — the caller doesn't need to know which."""
    if not regions:
        return ""
    n = len(regions)
    return (f"Possible tampering detected: {n} region{'s' if n != 1 else ''} with signs of "
            "possible editing (may indicate tampering) — not a certainty, verify visually.")


_MERGE_IOU_THRESH = 0.3
_ELA_NONJPEG_DISCOUNT = 0.6  # ELA's core assumption (a prior JPEG save) doesn't hold on a
                             # non-JPEG-sourced upload — still a weak hint, not dropped entirely


def _iou_xywh(a: list[float], b: list[float]) -> float:
    ax0, ay0, aw, ah = a
    bx0, by0, bw, bh = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax0 + aw, bx0 + bw), min(ay0 + ah, by0 + bh)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _union_bbox(a: list[float], b: list[float]) -> list[float]:
    x0, y0 = min(a[0], b[0]), min(a[1], b[1])
    x1, y1 = max(a[0] + a[2], b[0] + b[2]), max(a[1] + a[3], b[1] + b[3])
    return [round(x0, 4), round(y0, 4), round(x1 - x0, 4), round(y1 - y0, 4)]


def combine_tampering_detections(ela_regions: list[dict], noise_regions: list[dict],
                                  source_is_jpeg: bool) -> list[dict]:
    """Merges the two detectors' independent region lists into one, so the
    frontend only ever sees a single "tampering" field/dropdown option
    regardless of which technique(s) actually fired.

    - Overlapping ELA + noise-residual regions (IoU >= _MERGE_IOU_THRESH):
      two independent signals agreeing is strong evidence either way, so
      confidence is boosted (not just averaged) and never discounted, even
      on a non-JPEG upload.
    - ELA-only regions on a non-JPEG-sourced upload: discounted, since
      ELA's "this was previously JPEG-compressed" assumption doesn't hold —
      still surfaced as a weaker hint rather than dropped.
    - Noise-residual-only regions: never discounted, since it's
      format-agnostic by construction.
    """
    merged: list[dict] = []
    used_noise: set[int] = set()
    for ela_r in ela_regions:
        best_j, best_iou = None, 0.0
        for j, noise_r in enumerate(noise_regions):
            if j in used_noise:
                continue
            iou = _iou_xywh(ela_r["bbox"], noise_r["bbox"])
            if iou > best_iou:
                best_iou, best_j = iou, j
        if best_j is not None and best_iou >= _MERGE_IOU_THRESH:
            noise_r = noise_regions[best_j]
            used_noise.add(best_j)
            c1, c2 = ela_r["confidence"], noise_r["confidence"]
            merged.append({"label": "Tampering", "confidence": round(1 - (1 - c1) * (1 - c2), 3),
                           "bbox": _union_bbox(ela_r["bbox"], noise_r["bbox"])})
        else:
            conf = ela_r["confidence"] if source_is_jpeg else round(ela_r["confidence"] * _ELA_NONJPEG_DISCOUNT, 3)
            merged.append({"label": "Tampering", "confidence": conf, "bbox": ela_r["bbox"]})
    for j, noise_r in enumerate(noise_regions):
        if j not in used_noise:
            merged.append(noise_r)

    merged.sort(key=lambda r: -r["confidence"])
    return merged[:_MAX_DETECTIONS]
