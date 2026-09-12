"""
Crime Scene Reconstruction (photogrammetry) — pending-list #32.

A real, disclosed-limitations incremental Structure-from-Motion pipeline:
SIFT feature matching, essential-matrix relative pose estimation for the
first pair, then PnP-based incremental camera registration for each
additional photo, triangulating a sparse colored point cloud as it goes.
Uses only opencv-python-headless (SIFT has been patent-free and in the main
cv2 module since 4.4 — no opencv-contrib needed) and numpy; no new
dependency.

Deliberately NOT done, and disclosed rather than faked:
- No bundle adjustment (global joint refinement of all poses/points at
  once) and no loop closure — pose error accumulates with each additional
  photo, the same class of limitation as visual SLAM without loop closure.
- No dense reconstruction or mesh — output is a sparse point cloud from
  matched keypoints only.
- No camera calibration — intrinsics are estimated from image dimensions
  alone (a standard but approximate heuristic), so the reconstruction is
  up-to-scale and only approximately shaped. An optional two-point
  real-world-distance calibration converts to approximate units, never
  claimed as a measurement.
This is an educational demonstration of the real technique behind
SfM/COLMAP-style photogrammetry tools, not a forensic-grade tool.
"""

import base64
import io
import logging

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel, Field

from security.file_gate import scan_upload_bytes

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_IMAGES = 6
_MIN_IMAGES = 2
_MAX_IMAGE_BYTES = 8 * 1024 * 1024
_MIN_GOOD_MATCHES = 20
_MIN_PNP_POINTS = 6
_RATIO_TEST = 0.75
_OUTLIER_MEDIAN_MULTIPLE = 6.0


def _decode_image_b64(image_b64: str) -> np.ndarray:
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode this as an image.")
    if len(raw) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image too large (max 8MB).")
    scan_upload_bytes(raw, path="/rag/mm-crime-scene/reconstruct")
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode this as an image.")
    return np.array(img)


def _estimate_intrinsics(w: int, h: int) -> np.ndarray:
    """No calibration step exists — approximates focal length from image
    dimensions (a standard heuristic, not a measurement) assuming a
    roughly-normal-lens smartphone camera."""
    f = 1.2 * max(w, h)
    return np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1]], dtype=np.float64)


def _match_features(des_a: np.ndarray, des_b: np.ndarray) -> list:
    if des_a is None or des_b is None:
        return []
    bf = cv2.BFMatcher()
    raw = bf.knnMatch(des_a, des_b, k=2)
    good = []
    for pair in raw:
        if len(pair) != 2:
            continue
        m, n = pair
        if m.distance < _RATIO_TEST * n.distance:
            good.append(m)
    return good


def _cheirality_mask(pts3d_h: np.ndarray, R: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Keeps only points with positive depth in BOTH camera-0 (identity
    pose) and the given (R, t) camera — points "behind" either camera are
    triangulation artifacts, not real geometry."""
    pts3d = (pts3d_h[:3] / pts3d_h[3]).T
    depth0 = pts3d[:, 2]
    depth1 = (R @ pts3d.T + t.reshape(3, 1))[2, :]
    return (depth0 > 0) & (depth1 > 0), pts3d


def _sample_colors(image: np.ndarray, pts2d: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    xs = np.clip(pts2d[:, 0].astype(int), 0, w - 1)
    ys = np.clip(pts2d[:, 1].astype(int), 0, h - 1)
    return image[ys, xs]


def reconstruct(images: list[np.ndarray]) -> dict:
    n = len(images)
    grays = [cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) for img in images]
    sift = cv2.SIFT_create()
    kps, descs = [], []
    for g in grays:
        kp, des = sift.detectAndCompute(g, None)
        kps.append(kp)
        descs.append(des)

    h0, w0 = grays[0].shape
    K = _estimate_intrinsics(w0, h0)

    warnings: list[str] = []
    points3d: list[np.ndarray] = []
    colors: list[np.ndarray] = []
    camera_poses = [{"image_index": 0, "R": np.eye(3), "t": np.zeros(3)}]

    good01 = _match_features(descs[0], descs[1])
    if len(good01) < _MIN_GOOD_MATCHES:
        return {
            "points": [], "camera_poses": [{"position": [0, 0, 0], "image_index": 0}],
            "warnings": [f"Photos 1 and 2 only share {len(good01)} matched feature points "
                         f"(need at least {_MIN_GOOD_MATCHES}) — try photos with more visual "
                         f"overlap and surface texture."],
        }

    pts0 = np.float32([kps[0][m.queryIdx].pt for m in good01])
    pts1 = np.float32([kps[1][m.trainIdx].pt for m in good01])
    E, mask = cv2.findEssentialMat(pts0, pts1, K, method=cv2.RANSAC, prob=0.999, threshold=1.0)
    if E is None:
        return {"points": [], "camera_poses": [{"position": [0, 0, 0], "image_index": 0}],
                "warnings": ["Could not estimate camera geometry between photos 1 and 2 — try a different pair."]}
    inlier = mask.ravel().astype(bool)
    _, R1, t1, _ = cv2.recoverPose(E, pts0[inlier], pts1[inlier], K)

    P0 = K @ np.hstack([np.eye(3), np.zeros((3, 1))])
    P1 = K @ np.hstack([R1, t1])
    pts4d = cv2.triangulatePoints(P0, P1, pts0[inlier].T, pts1[inlier].T)
    good_mask, pts3d = _cheirality_mask(pts4d, R1, t1)
    kept_idx = np.where(inlier)[0][good_mask]
    points3d.extend(pts3d[good_mask])
    colors.extend(_sample_colors(images[1], pts1[inlier][good_mask]))

    camera_poses.append({"image_index": 1, "R": R1, "t": t1.flatten()})
    prev_point_map = {good01[i].trainIdx: len(points3d) - len(kept_idx) + j
                       for j, i in enumerate(np.where(inlier)[0][good_mask])}

    for i in range(2, n):
        good = _match_features(descs[i - 1], descs[i])
        if len(good) < _MIN_GOOD_MATCHES:
            warnings.append(f"Photos {i} and {i + 1} only share {len(good)} matched feature "
                             f"points (need at least {_MIN_GOOD_MATCHES}) — stopping the chain "
                             f"here rather than guessing.")
            break

        obj_pts, img_pts, new_matches = [], [], []
        for m in good:
            if m.queryIdx in prev_point_map:
                obj_pts.append(points3d[prev_point_map[m.queryIdx]])
                img_pts.append(kps[i][m.trainIdx].pt)
            else:
                new_matches.append(m)

        if len(obj_pts) < _MIN_PNP_POINTS:
            warnings.append(f"Not enough of photo {i + 1}'s matches connect to the existing "
                             f"reconstruction ({len(obj_pts)} found, need {_MIN_PNP_POINTS}) — "
                             f"stopping the chain here.")
            break

        ok, rvec, tvec, pnp_inliers = cv2.solvePnPRansac(
            np.float32(obj_pts), np.float32(img_pts), K, None)
        if not ok:
            warnings.append(f"Could not estimate photo {i + 1}'s camera pose — stopping the chain here.")
            break
        R_i, _ = cv2.Rodrigues(rvec)
        t_i = tvec.flatten()
        camera_poses.append({"image_index": i, "R": R_i, "t": t_i})

        new_point_map: dict[int, int] = {}
        for m in good:
            if m.queryIdx in prev_point_map:
                new_point_map[m.trainIdx] = prev_point_map[m.queryIdx]

        if new_matches:
            R_prev, t_prev = camera_poses[-2]["R"], camera_poses[-2]["t"]
            P_prev = K @ np.hstack([R_prev, t_prev.reshape(3, 1)])
            P_curr = K @ np.hstack([R_i, t_i.reshape(3, 1)])
            pts_prev = np.float32([kps[i - 1][m.queryIdx].pt for m in new_matches])
            pts_curr = np.float32([kps[i][m.trainIdx].pt for m in new_matches])
            pts4d_new = cv2.triangulatePoints(P_prev, P_curr, pts_prev.T, pts_curr.T)
            good_mask_new, pts3d_new = _cheirality_mask(pts4d_new, R_i, t_i)
            new_colors = _sample_colors(images[i], pts_curr[good_mask_new])
            base_idx = len(points3d)
            points3d.extend(pts3d_new[good_mask_new])
            colors.extend(new_colors)
            kept_new = np.where(good_mask_new)[0]
            for j, orig_idx in enumerate(kept_new):
                new_point_map[new_matches[orig_idx].trainIdx] = base_idx + j

        prev_point_map = new_point_map

    if points3d:
        pts_arr = np.array(points3d)
        centroid = np.median(pts_arr, axis=0)
        dists = np.linalg.norm(pts_arr - centroid, axis=1)
        threshold = _OUTLIER_MEDIAN_MULTIPLE * (np.median(dists) + 1e-6)
        keep = dists <= threshold
        points3d = pts_arr[keep].tolist()
        colors = np.array(colors)[keep].tolist()
    else:
        colors = []

    return {
        "points": [[*p, *[int(c) for c in col]] for p, col in zip(points3d, colors)],
        "camera_poses": [{"position": cp["t"].tolist(), "image_index": cp["image_index"]}
                          for cp in camera_poses],
        "warnings": warnings,
    }


class CalibrationPoint(BaseModel):
    x: float
    y: float


class ReconstructRequest(BaseModel):
    images: list[str] = Field(..., min_length=_MIN_IMAGES, max_length=_MAX_IMAGES)
    calibration_point_a: CalibrationPoint | None = None
    calibration_point_b: CalibrationPoint | None = None
    calibration_real_distance_cm: float | None = None


@router.post("/mm-crime-scene/reconstruct")
def reconstruct_scene(req: ReconstructRequest):
    images = [_decode_image_b64(b64) for b64 in req.images]
    result = reconstruct(images)

    if (req.calibration_point_a and req.calibration_point_b
            and req.calibration_real_distance_cm and result["points"]):
        pts = np.array([p[:3] for p in result["points"]])
        # Find the reconstructed points nearest (in original pixel space via
        # camera-0's projection) to each clicked calibration pixel.
        h0, w0 = images[0].shape[:2]
        K = _estimate_intrinsics(w0, h0)
        proj = (K @ pts.T).T
        proj_px = proj[:, :2] / proj[:, 2:3]
        idx_a = np.argmin(np.linalg.norm(
            proj_px - [req.calibration_point_a.x, req.calibration_point_a.y], axis=1))
        idx_b = np.argmin(np.linalg.norm(
            proj_px - [req.calibration_point_b.x, req.calibration_point_b.y], axis=1))
        measured = np.linalg.norm(pts[idx_a] - pts[idx_b])
        if measured > 1e-6:
            scale = req.calibration_real_distance_cm / measured
            result["points"] = [[*(np.array(p[:3]) * scale), *p[3:]] for p in result["points"]]
            for cp in result["camera_poses"]:
                cp["position"] = [c * scale for c in cp["position"]]
            result["scale_applied"] = True
    else:
        result["scale_applied"] = False

    return result
