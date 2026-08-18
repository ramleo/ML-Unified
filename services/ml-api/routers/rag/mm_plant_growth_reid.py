"""Plant re-identification: group an UNLABELED, UNORDERED batch of photos by
which physical plant they show, then order each group chronologically.

Growth mode (mm_plant_growth.py) requires the user to already know how many
plants exist and to hand-order the photos ("Day 0, Day 1..."). This module
removes both requirements for a batch that may interleave multiple different
plants with no labels — but doing so is a similarity-clustering problem, not
a hard classification, so it can be WRONG in both directions: a false merge
(two different plants judged the same) silently corrupts a growth curve,
while a false split (one plant judged as two) just costs the user one manual
re-merge click in review. Every decision this module makes is therefore
surfaced with a confidence flag rather than silently committed — the caller
(mm_plant_growth.py's /mm-plant-growth-group/propose route) always returns a
PROPOSAL for the user to review/edit before /measure actually runs
measurement, mirroring this tool's existing honest-uncertainty conventions
(low_confidence flags, the "this is your interpretation" growth-stages
caveat).

Clustering reuses clip-ViT-B-32 via sentence-transformers — already a base
dependency of this project, already loaded the same way by mm_similar.py for
an unrelated "find similar figures" feature. This module keeps its own lazy
singleton rather than importing mm_similar's, so plant-growth grouping isn't
coupled to that feature's Chroma collection ever failing to open. Chroma
itself is NOT used here: this is a one-shot batch of at most 30 images per
request, not a searchable corpus, so an in-memory cosine-similarity matrix is
simpler and sufficient.

Photos are embedded by their DETECTED PLANT CROP, not the whole frame —
embedding full photos would cluster by background/room instead of by plant.
A photo where 0 or 2+ plants are detected is out of scope for v1 and is
reported in `unclustered` with a reason, rather than guessing which region
(or none) to use.

Similarity thresholds are NOT tuned on a labeled plant-photo dataset (none
exists) — they're a starting point based on clip-ViT-B-32's well-documented
general behavior (near-duplicate/same-subject pairs commonly score >0.9;
unrelated-but-same-category images commonly land 0.6-0.85), deliberately
biased toward under-merging since a false merge is the worse failure mode.
Overridable via env vars; expected to be refined from real traffic.
"""
from __future__ import annotations

import base64
import io
import logging
import os
import threading

import numpy as np
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_model = None
_load_failed = False
_lock = threading.Lock()

_THRESHOLD_HIGH = float(os.environ.get("PLANT_REID_SIMILARITY_THRESHOLD_HIGH", "0.87"))
_THRESHOLD_LOW = float(os.environ.get("PLANT_REID_SIMILARITY_THRESHOLD_LOW", "0.78"))


class GroupPhoto(BaseModel):
    image: str  # b64 image, any common format, no label


class ProposeGroupsRequest(BaseModel):
    photos: list[GroupPhoto]
    auto_detect: bool = True  # reserved for schema symmetry with growth mode; grouping always needs a detected plant crop to embed, so this is currently a no-op


class ConfirmedGroup(BaseModel):
    group_id: int
    photo_indices: list[int]


class MeasureGroupsRequest(BaseModel):
    photos: list[GroupPhoto]
    groups: list[ConfirmedGroup]
    auto_detect: bool = True


def _get_clip_model():
    """Lazy-load CLIP on first use — most sessions never opt into group mode."""
    global _model, _load_failed
    if _model is not None or _load_failed:
        return _model
    with _lock:
        if _model is not None or _load_failed:
            return _model
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading clip-ViT-B-32 (~350 MB) for plant re-identification …")
            _model = SentenceTransformer("clip-ViT-B-32", device="cpu")
        except Exception as exc:
            logger.warning("CLIP load failed — plant grouping disabled: %s", exc)
            _load_failed = True
    return _model


def _embed_crops(crops: list[np.ndarray]) -> np.ndarray | None:
    model = _get_clip_model()
    if model is None:
        return None
    from PIL import Image as PILImage

    pil_imgs = [PILImage.fromarray(c) for c in crops]
    return model.encode(
        pil_imgs, batch_size=8, show_progress_bar=False,
        convert_to_numpy=True, normalize_embeddings=True,
    )


def _union_find_cluster(sim: np.ndarray, threshold_high: float) -> list[list[int]]:
    """Greedy union-find over pairwise cosine similarity — deliberately
    simpler than hierarchical clustering, which is unnecessary for the
    ≤30-image batches this tool caps requests at."""
    n = sim.shape[0]
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if sim[i, j] >= threshold_high:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def _find_ambiguous_pairs(
    sim: np.ndarray, groups: list[list[int]], threshold_low: float, threshold_high: float,
) -> dict[int, set[int]]:
    """Cross-group pairs landing in the near-miss band [low, high) mean the
    clusterer wasn't confident these are different plants either — flag
    both groups as ambiguous with each other rather than silently trusting
    the union-find's threshold_high cutoff alone."""
    idx_to_group = {i: gid for gid, idxs in enumerate(groups) for i in idxs}
    ambiguous: dict[int, set[int]] = {}
    n = sim.shape[0]
    for i in range(n):
        for j in range(i + 1, n):
            gi, gj = idx_to_group[i], idx_to_group[j]
            if gi != gj and threshold_low <= sim[i, j] < threshold_high:
                ambiguous.setdefault(gi, set()).add(gj)
                ambiguous.setdefault(gj, set()).add(gi)
    return ambiguous


def _read_exif_datetime(img) -> str | None:
    """DateTimeOriginal (preferred — when the photo was actually taken)
    lives in the Exif sub-IFD, not the base IFD reachable via a plain
    Image.getexif(); DateTime (fallback, often just file-modified time)
    lives in the base IFD directly."""
    try:
        exif = img.getexif()
        if not exif:
            return None
        try:
            exif_ifd = exif.get_ifd(0x8769)  # Exif sub-IFD
            dt_original = exif_ifd.get(0x9003)  # DateTimeOriginal
            if dt_original:
                return str(dt_original)
        except Exception:
            pass
        dt = exif.get(0x0132)  # DateTime
        return str(dt) if dt else None
    except Exception:
        return None


def _order_group(
    photo_idxs: list[int], exif_dt: dict[int, str | None], area_fraction: dict[int, float],
) -> tuple[list[int], str, str]:
    """Returns (ordered photo indices, order_source, order_confidence).

    EXIF timestamps are the only real chronological signal available (no
    file-modified-time is trustworthy after upload/re-encode). When absent,
    falls back to ascending leaf area — the same "growth is roughly
    monotonic" assumption this tool's manual growth-stages toggle already
    makes explicit to the user, here applied automatically so it must be
    flagged, not presented as detected fact."""
    have_exif = [i for i in photo_idxs if exif_dt.get(i)]
    missing_exif = [i for i in photo_idxs if not exif_dt.get(i)]

    if len(have_exif) == len(photo_idxs):
        return sorted(photo_idxs, key=lambda i: exif_dt[i]), "exif", "high"

    if not have_exif:
        return sorted(photo_idxs, key=lambda i: area_fraction.get(i, 0.0)), "leaf_area_fallback", "low"

    # Mixed: EXIF photos are trusted anchors in their real chronological
    # order; each non-EXIF photo is inserted by where its leaf area falls
    # relative to the anchors' area trend, not a global area sort (which
    # could contradict a known-good EXIF order if area isn't perfectly
    # monotonic).
    anchors = sorted(have_exif, key=lambda i: exif_dt[i])
    anchor_areas = [area_fraction.get(i, 0.0) for i in anchors]

    def interpolated_rank(i: int) -> float:
        a = area_fraction.get(i, 0.0)
        pos = 0
        while pos < len(anchor_areas) and anchor_areas[pos] <= a:
            pos += 1
        return pos - 0.5  # sits between anchor[pos-1] and anchor[pos]

    combined = [(i, float(rank)) for rank, i in enumerate(anchors)]
    combined += [(i, interpolated_rank(i)) for i in missing_exif]
    combined.sort(key=lambda pair: pair[1])
    return [i for i, _ in combined], "mixed", "low"


def propose_groups(photos: list[str], auto_detect: bool) -> dict:
    """Clusters an unlabeled photo batch by plant identity and orders each
    resulting group chronologically. Never raises — a bad/undecodable photo
    is reported in `unclustered`, not a 500 for the whole batch."""
    from routers.rag.mm_plant_growth import _crop, _detect_plant_boxes, _leaf_area_and_mask
    from PIL import Image as PILImage

    imgs: list = []
    for b64 in photos:
        try:
            imgs.append(PILImage.open(io.BytesIO(base64.b64decode(b64))).convert("RGB"))
        except Exception as exc:
            logger.warning("Plant re-id could not decode a photo: %s", exc)
            imgs.append(None)

    usable_idx: list[int] = []
    crops: list[np.ndarray] = []
    unclustered: list[dict] = []
    exif_dt: dict[int, str | None] = {}
    area_fraction: dict[int, float] = {}

    for i, img in enumerate(imgs):
        if img is None:
            unclustered.append({"photo_index": i, "reason": "could not decode this photo"})
            continue
        boxes = _detect_plant_boxes(photos[i])
        if len(boxes) == 0:
            unclustered.append({"photo_index": i, "reason": "no plant detected in this photo"})
            continue
        if len(boxes) >= 2:
            unclustered.append({
                "photo_index": i,
                "reason": "multiple plants detected in this photo — this mode expects one plant per photo",
            })
            continue
        crop = _crop(img, boxes[0])
        crops.append(crop)
        usable_idx.append(i)
        exif_dt[i] = _read_exif_datetime(img)
        area_fraction[i] = _leaf_area_and_mask(crop)["area_fraction"]

    if len(usable_idx) < 2:
        unclustered += [
            {"photo_index": i, "reason": "not enough usable photos to group"} for i in usable_idx
        ]
        return {"groups": [], "unclustered": unclustered}

    embeddings = _embed_crops(crops)
    if embeddings is None:
        unclustered += [
            {"photo_index": i, "reason": "plant grouping is temporarily unavailable"} for i in usable_idx
        ]
        return {"groups": [], "unclustered": unclustered, "error": "similarity model failed to load"}

    sim = embeddings @ embeddings.T  # embeddings are unit-normalized -> dot product is cosine similarity
    raw_groups = _union_find_cluster(sim, _THRESHOLD_HIGH)
    ambiguous_map = _find_ambiguous_pairs(sim, raw_groups, _THRESHOLD_LOW, _THRESHOLD_HIGH)

    logger.info(
        "Plant re-id: %d photos -> %d groups, sim min/median/max=%.3f/%.3f/%.3f",
        len(usable_idx), len(raw_groups),
        float(sim[np.triu_indices(len(usable_idx), k=1)].min(initial=1.0)),
        float(np.median(sim[np.triu_indices(len(usable_idx), k=1)])) if len(usable_idx) > 1 else 1.0,
        float(sim[np.triu_indices(len(usable_idx), k=1)].max(initial=0.0)),
    )

    groups_out = []
    for gid, local_idxs in enumerate(raw_groups):
        photo_idxs = [usable_idx[k] for k in local_idxs]
        ordered_photo_idxs, order_source, order_confidence = _order_group(
            photo_idxs, exif_dt, area_fraction,
        )

        cluster_confidence = "high"
        reason = None
        if gid in ambiguous_map:
            cluster_confidence = "ambiguous"
        elif len(local_idxs) == 1:
            k = local_idxs[0]
            other_sims = [sim[k, m] for m in range(len(usable_idx)) if m != k]
            if other_sims and max(other_sims) < _THRESHOLD_LOW:
                cluster_confidence = "ambiguous"
                reason = "no other photo matched closely"

        entry = {
            "group_id": gid,
            "photo_indices": ordered_photo_idxs,
            "order_source": order_source,
            "order_confidence": order_confidence,
            "cluster_confidence": cluster_confidence,
            "ambiguous_with": sorted(ambiguous_map.get(gid, set())),
        }
        if reason:
            entry["reason"] = reason
        groups_out.append(entry)

    return {"groups": groups_out, "unclustered": unclustered}


def _frame_label(photos: list[str], idx: int) -> str:
    try:
        from PIL import Image as PILImage

        img = PILImage.open(io.BytesIO(base64.b64decode(photos[idx]))).convert("RGB")
        dt = _read_exif_datetime(img)
        if dt:
            return dt
    except Exception:
        pass
    return f"Photo {idx + 1}"


def measure_groups(photos: list[str], groups: list[dict]) -> dict:
    """Runs each user-confirmed group through the existing growth-mode
    measurement pipeline, unchanged. Frame labels are the EXIF date string
    when available, else "Photo N" — never "Day N", which would imply a
    verified interval this feature doesn't have even when order_confidence
    was "high" for clustering (clustering confidence and interval-precision
    are different things)."""
    from routers.rag.mm_plant_growth import PlantGrowthFrame, _run_growth_mode

    results = []
    for g in groups:
        frames = [
            PlantGrowthFrame(image=photos[idx], label=_frame_label(photos, idx))
            for idx in g["photo_indices"]
        ]
        run = _run_growth_mode(frames, auto_detect=True)
        results.append({"group_id": g["group_id"], "plants": run.get("plants", [])})

    return {"mode": "group_growth", "groups": results}
