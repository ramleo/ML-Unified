"""
Astrophotography Anomaly Detector — pending-list #52.

Classic CV, no neural network: differencing time-adjacent frames from a
fixed-tripod night-sky photo session, then Hough-line detection on the
difference, is the real, published technique used by hobbyist meteor/
satellite-trail detectors (e.g. github.com/shin3tky/detect_meteors, and
the Hough-transform approach in published satellite-trail-detection
papers). The key discriminator, not just "any line is an anomaly":

- A star that shifts slightly between two frames (sky rotation, no
  tracking mount) leaves a DIPOLE in the signed difference image — bright
  where it moved to, dark where it moved from.
- A meteor or satellite trail, present in only one of the two frames,
  leaves a MONOPOLE — one-sided, no matching opposite-sign counterpart.

Deliberately NOT done, disclosed rather than glossed over:
- No star-based registration/plate-solving (what DeepSkyStacker/Siril
  actually do before stacking). This assumes a static tripod — frames are
  compared/stacked exactly as uploaded, in order.
- Meteor-vs-satellite labels are always "possible", never a confirmed
  verdict — no ground-truth dataset exists to validate the classifier,
  same qualitative-label discipline as prompt-injection-playground (#53)
  and ai-code-detector (#55) rather than a fabricated confidence number.
- "No anomalies found" means nothing crossed the detection threshold, not
  that nothing happened — faint meteors can fall below it.
"""

import base64
import io
import logging

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_DIM = 1600
_MIN_FRAMES = 2
_MAX_FRAMES = 30
_HOUGH_THRESHOLD = 30
_HOUGH_MIN_LINE_LENGTH = 20
_HOUGH_MAX_LINE_GAP = 5
_DIPOLE_BAND_PX = 6  # perpendicular sampling band half-width
_DIPOLE_MAX_RATIO = 0.35  # |minor_sign_area| / |major_sign_area| above this -> dipole (star), reject
_LINK_MAX_ANGLE_DEG = 12.0
_LINK_MAX_ENDPOINT_DIST = 60.0


class Streak:
    def __init__(self, x1, y1, x2, y2, monopole_strength: float):
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.monopole_strength = monopole_strength

    @property
    def length(self) -> float:
        return float(np.hypot(self.x2 - self.x1, self.y2 - self.y1))

    @property
    def angle_deg(self) -> float:
        return float(np.degrees(np.arctan2(self.y2 - self.y1, self.x2 - self.x1)) % 180)

    @property
    def midpoint(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


def _resize_long_edge(img: np.ndarray, max_dim: int) -> np.ndarray:
    h, w = img.shape[:2]
    scale = max_dim / max(h, w)
    if scale >= 1.0:
        return img
    return cv2.resize(img, (int(w * scale), int(h * scale)))


def _decode_gray_and_color(file_bytes: bytes) -> tuple[np.ndarray, np.ndarray]:
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    color = np.array(img)
    color = _resize_long_edge(color, _MAX_DIM)
    gray = cv2.cvtColor(color, cv2.COLOR_RGB2GRAY).astype(np.float32)
    return gray, color


def _diff_pair(gray_a: np.ndarray, gray_b: np.ndarray) -> np.ndarray:
    """Signed difference (b - a), NOT absolute — sign is what lets the
    dipole filter tell a star-shift apart from a real one-sided streak."""
    return gray_b - gray_a


def _sample_side_sums(diff: np.ndarray, x1, y1, x2, y2, band_px: int) -> tuple[float, float]:
    """Sum of positive-diff and negative-diff pixels in a band around the
    line's perpendicular normal, on each side of the line segment."""
    dx, dy = x2 - x1, y2 - y1
    length = max(np.hypot(dx, dy), 1e-6)
    nx, ny = -dy / length, dx / length  # unit normal

    h, w = diff.shape
    n_samples = max(int(length), 2)
    ts = np.linspace(0, 1, n_samples)
    xs = x1 + ts * dx
    ys = y1 + ts * dy

    pos_total, neg_total = 0.0, 0.0
    for r in range(1, band_px + 1):
        for sign in (1, -1):
            sx = np.clip((xs + sign * r * nx).astype(int), 0, w - 1)
            sy = np.clip((ys + sign * r * ny).astype(int), 0, h - 1)
            vals = diff[sy, sx]
            pos_total += float(np.clip(vals, 0, None).sum())
            neg_total += float(np.clip(-vals, 0, None).sum())
    return pos_total, neg_total


def _dedupe_streaks(streaks: list[Streak], max_dist: float = 15.0, max_angle: float = 8.0) -> list[Streak]:
    """Hough commonly returns several near-identical segments for one real
    line. Keep the strongest (most monopole) representative of each
    angle+position cluster rather than treating duplicates as separate
    anomalies."""
    ordered = sorted(streaks, key=lambda s: s.monopole_strength, reverse=True)
    kept: list[Streak] = []
    for s in ordered:
        is_dup = False
        for k in kept:
            angle_diff = min(abs(s.angle_deg - k.angle_deg), 180 - abs(s.angle_deg - k.angle_deg))
            dist = float(np.hypot(s.midpoint[0] - k.midpoint[0], s.midpoint[1] - k.midpoint[1]))
            if angle_diff <= max_angle and dist <= max_dist:
                is_dup = True
                break
        if not is_dup:
            kept.append(s)
    return kept


def _detect_streaks(diff: np.ndarray) -> list[Streak]:
    abs_diff = np.abs(diff)
    if abs_diff.max() <= 0:
        return []
    abs_u8 = np.clip(abs_diff, 0, 255).astype(np.uint8)
    # Otsu separates the mostly-black night-sky background from real
    # brightness changes far more reliably here than a fixed/percentile
    # cutoff: the "signal" population (star dipole edges + any real
    # streak) is a small, variable fraction of the frame, which is exactly
    # the bimodal-histogram case Otsu is designed for.
    _otsu_val, mask = cv2.threshold(abs_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    lines = cv2.HoughLinesP(
        mask, rho=1, theta=np.pi / 180, threshold=_HOUGH_THRESHOLD,
        minLineLength=_HOUGH_MIN_LINE_LENGTH, maxLineGap=_HOUGH_MAX_LINE_GAP,
    )
    if lines is None:
        return []

    candidates = []
    for (x1, y1, x2, y2) in lines[:, 0, :]:
        pos_sum, neg_sum = _sample_side_sums(diff, float(x1), float(y1), float(x2), float(y2), _DIPOLE_BAND_PX)
        major = max(pos_sum, neg_sum)
        minor = min(pos_sum, neg_sum)
        if major <= 1e-6:
            continue
        ratio = minor / major
        monopole_strength = major - minor
        if ratio <= _DIPOLE_MAX_RATIO:
            candidates.append(Streak(int(x1), int(y1), int(x2), int(y2), monopole_strength))

    return _dedupe_streaks(candidates)


def _classify_sequence(pair_streaks: list[list[Streak]]) -> list[dict]:
    """A single-frame flash (meteor) brightens the sky in one pair-diff and
    then dims it back in the NEXT pair-diff at the same location — so a
    single real event naturally produces two monopole detections, not
    one. Forward-link a streak to its best angle/position match in the
    next pair to merge these into one anomaly per real event, rather than
    double-counting.

    Deliberately does NOT attempt a meteor-vs-satellite verdict: a
    satellite's frame-to-frame position shift is almost entirely ALONG
    its own line direction (real orbital motion projected onto the sky),
    which is geometrically near-indistinguishable from "the same flash,
    stationary" using position drift alone — tested against synthetic
    ground truth and found unreliable (a moving satellite streak and a
    stationary flash both produce near-zero measured drift). Real
    meteor-vs-satellite classification needs proper multi-frame
    trajectory/velocity modeling that published detection systems use;
    faking a confident label here would be exactly the kind of
    overclaiming this project has repeatedly caught and corrected (e.g.
    #46's grounding-failure disclosure)."""
    n_pairs = len(pair_streaks)
    consumed = [set() for _ in range(n_pairs)]
    chains: list[list[tuple[int, Streak]]] = []

    for i in range(n_pairs):
        for j, streak in enumerate(pair_streaks[i]):
            if j in consumed[i]:
                continue
            chain = [(i, streak)]
            consumed[i].add(j)
            cur_pair, cur_streak = i, streak
            while cur_pair + 1 < n_pairs:
                best_k, best_dist = None, None
                for k, other in enumerate(pair_streaks[cur_pair + 1]):
                    if k in consumed[cur_pair + 1]:
                        continue
                    angle_diff = min(abs(cur_streak.angle_deg - other.angle_deg), 180 - abs(cur_streak.angle_deg - other.angle_deg))
                    if angle_diff > _LINK_MAX_ANGLE_DEG:
                        continue
                    dist = float(np.hypot(cur_streak.midpoint[0] - other.midpoint[0], cur_streak.midpoint[1] - other.midpoint[1]))
                    if dist <= _LINK_MAX_ENDPOINT_DIST and (best_dist is None or dist < best_dist):
                        best_k, best_dist = k, dist
                if best_k is None:
                    break
                consumed[cur_pair + 1].add(best_k)
                cur_pair += 1
                cur_streak = pair_streaks[cur_pair][best_k]
                chain.append((cur_pair, cur_streak))
            chains.append(chain)

    anomalies = []
    for chain in chains:
        first_pair, _ = chain[0]
        last_pair, _ = chain[-1]
        best_pair, best_streak = max(chain, key=lambda ps: ps[1].monopole_strength)
        anomalies.append({
            "pair_index": best_pair,
            "frame_pair_range": [first_pair, last_pair + 1],
            "streak": best_streak,
            "label": "possible meteor or satellite trail",
        })
    return anomalies


def _crop_and_annotate(color_frame: np.ndarray, streak: Streak, pad: int = 40) -> str:
    h, w = color_frame.shape[:2]
    x0 = max(0, min(streak.x1, streak.x2) - pad)
    y0 = max(0, min(streak.y1, streak.y2) - pad)
    x1 = min(w, max(streak.x1, streak.x2) + pad)
    y1 = min(h, max(streak.y1, streak.y2) + pad)
    crop = color_frame[y0:y1, x0:x1].copy()
    cv2.line(crop, (streak.x1 - x0, streak.y1 - y0), (streak.x2 - x0, streak.y2 - y0), (255, 0, 128), 2)
    buf = cv2.imencode(".jpg", cv2.cvtColor(crop, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])[1]
    return base64.b64encode(buf).decode()


def _median_stack(color_frames: list[np.ndarray]) -> str:
    shapes = {f.shape for f in color_frames}
    if len(shapes) > 1:
        h = min(f.shape[0] for f in color_frames)
        w = min(f.shape[1] for f in color_frames)
        color_frames = [f[:h, :w] for f in color_frames]
    stack = np.median(np.stack(color_frames, axis=0), axis=0).astype(np.uint8)
    buf = cv2.imencode(".jpg", cv2.cvtColor(stack, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])[1]
    return base64.b64encode(buf).decode()


def run_astro_anomaly_detect(file_bytes_list: list[bytes]) -> dict:
    if len(file_bytes_list) < _MIN_FRAMES:
        raise HTTPException(status_code=400, detail=f"Upload at least {_MIN_FRAMES} photos from the same session.")
    if len(file_bytes_list) > _MAX_FRAMES:
        raise HTTPException(status_code=400, detail=f"Sessions are capped at {_MAX_FRAMES} photos.")

    grays, colors = [], []
    for fb in file_bytes_list:
        try:
            gray, color = _decode_gray_and_color(fb)
        except Exception:
            raise HTTPException(status_code=400, detail="Could not decode one of the uploaded images.")
        grays.append(gray)
        colors.append(color)

    shapes = {g.shape for g in grays}
    if len(shapes) > 1:
        h = min(g.shape[0] for g in grays)
        w = min(g.shape[1] for g in grays)
        grays = [g[:h, :w] for g in grays]
        colors = [c[:h, :w] for c in colors]

    pair_streaks: list[list[Streak]] = []
    for i in range(len(grays) - 1):
        diff = _diff_pair(grays[i], grays[i + 1])
        pair_streaks.append(_detect_streaks(diff))

    anomalies_raw = _classify_sequence(pair_streaks)

    anomalies = []
    for a in anomalies_raw:
        streak: Streak = a["streak"]
        frame_idx = a["pair_index"]  # crop drawn on the frame with the clearest (strongest monopole) signal
        anomalies.append({
            "frame_pair": a["frame_pair_range"],
            "label": a["label"],
            "length_px": round(streak.length, 1),
            "angle_deg": round(streak.angle_deg, 1),
            "preview": _crop_and_annotate(colors[frame_idx], streak),
        })

    median_stack_b64 = _median_stack(colors)

    warnings = []
    if len(shapes) > 1:
        warnings.append("Uploaded photos had different dimensions — cropped to the smallest common size.")

    return {"anomalies": anomalies, "median_stack": median_stack_b64, "warnings": warnings, "frame_count": len(grays)}


@router.post("/mm-astro-anomaly/detect")
async def astro_anomaly_detect(images: list[UploadFile] = File(...)):
    file_bytes_list = [await f.read() for f in images]
    return run_astro_anomaly_detect(file_bytes_list)
