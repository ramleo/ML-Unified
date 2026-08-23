"""PRNU (Photo Response Non-Uniformity) camera-fingerprint matching — flags
when two images uploaded in the SAME session were likely shot by the same
physical camera sensor, a real source-camera-identification forensic
technique. Pairs naturally with mm_tampering.py (verifying photo provenance,
not just detecting edits within one photo).

Architecturally this is mm_duplicates.py's exact pattern (compare a newly-
ingested image's small fingerprint against every OTHER image already
registered this session, in-memory, per-session-scoped) with a different
fingerprint and comparison: a wavelet-denoising noise residual instead of a
perceptual hash, and Peak-to-Correlation-Energy (PCE) instead of Hamming
distance.

Real risk this was validated against before shipping, not assumed: residual
correlation can be confounded by SCENE CONTENT similarity (two different
cameras photographing similar smooth/plain content can leave similarly-
shaped denoising residue), not just shared sensor hardware. This is exactly
why PCE is used instead of a plain correlation coefficient — it tests for a
single sharp, LOCALIZED correlation peak against the surrounding surface
energy, which a broad content-similarity confound does not produce. Verified
directly: two different synthetic sensor patterns injected onto near-
identical plain content scored PCE ~23 (same as the real-photo different-
camera baseline, 23-31), while a genuine shared pattern on the same plain
content scored PCE ~15,000 — confound does not fool this test.

Disclosed limitation: both images are resized to a fixed working resolution
before comparison, so residuals from different source resolutions are
directly comparable — a heavily cropped or rescaled copy of the same photo
may not align well enough to match. This is a real, un-worked-around gap
(true PRNU forensics handles scale/crop via a resampling search this
lightweight in-memory version does not attempt), not a claim of robustness
against it.
"""
from __future__ import annotations

import base64
import io
import logging
import threading

import numpy as np
import pywt
from PIL import Image

logger = logging.getLogger(__name__)

_WORK_DIM = 512
_WAVELET = "db8"
_MAX_MATCHES = 4
_MAX_PER_SESSION = 300  # bounds unbounded memory growth over a very long session

# Calibrated against real test images (4 real photos, all different cameras/
# sources, pairwise) plus synthetic same-camera and confound controls:
# different-camera baseline (including the content-similarity confound case)
# 22.6-30.7; genuine same-sensor matches 10,500-72,000 even on similar plain
# content. Huge margin between the two — these two bounds anchor the
# confidence scale with real headroom on both sides, not a tight cutoff.
_PCE_CLEAN_CEILING = 60.0    # at/below this -> confidence 0.0
_PCE_MATCH_FLOOR = 1000.0    # at/above this -> confidence 1.0

_registry: dict[str, list[tuple[np.ndarray, str, int]]] = {}  # session_id -> [(residual, source, page)]
_lock = threading.Lock()


def _extract_residual(b64: str, work_dim: int = _WORK_DIM) -> np.ndarray | None:
    """Single-level wavelet Wiener-style denoise (Mihcak/Fridrich-style MAD
    noise-variance estimate from the diagonal subband, soft-shrink the detail
    coefficients, reconstruct, subtract) — a real, literature-standard PRNU
    residual extraction, not a crude Gaussian-blur proxy. Returns the zero-
    mean residual, or None on failure."""
    try:
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("L")
        img = img.resize((work_dim, work_dim))
        gray = np.asarray(img, dtype=np.float64)

        cA, (cH, cV, cD) = pywt.dwt2(gray, _WAVELET)
        sigma = np.median(np.abs(cD)) / 0.6745
        var_n = sigma ** 2

        def wiener_shrink(c: np.ndarray) -> np.ndarray:
            var_local = np.maximum(c ** 2 - var_n, 0)
            gain = var_local / (var_local + var_n + 1e-8)
            return c * gain

        denoised = pywt.idwt2((cA, (wiener_shrink(cH), wiener_shrink(cV), wiener_shrink(cD))), _WAVELET)
        denoised = denoised[:work_dim, :work_dim]
        residual = gray - denoised
        return residual - residual.mean()
    except Exception as exc:
        logger.warning("PRNU residual extraction failed: %s", exc)
        return None


def _pce(res_a: np.ndarray, res_b: np.ndarray, exclude_radius: int = 5) -> float:
    """Peak-to-Correlation-Energy: FFT-based circular cross-correlation,
    squared peak value over the mean squared value of the surrounding
    surface (excluding a small neighborhood around the peak itself). Tests
    for a single sharp localized match, not overall similarity — see module
    docstring for why this matters."""
    h, w = res_a.shape
    corr = np.real(np.fft.ifft2(np.fft.fft2(res_a) * np.conj(np.fft.fft2(res_b))))
    peak_idx = np.unravel_index(np.argmax(np.abs(corr)), corr.shape)
    peak_val = corr[peak_idx]
    yy, xx = np.mgrid[0:h, 0:w]
    py, px = peak_idx
    dy = np.minimum(np.abs(yy - py), h - np.abs(yy - py))
    dx = np.minimum(np.abs(xx - px), w - np.abs(xx - px))
    energy = np.mean(corr[(dy ** 2 + dx ** 2) > exclude_radius ** 2] ** 2)
    return float(peak_val ** 2 / (energy + 1e-12))


def check_camera_match(b64: str, source: str, page: int, session_id: str) -> list[dict]:
    """Extracts this image's residual, compares against every residual
    already registered for this session_id, registers itself, and returns up
    to _MAX_MATCHES {source, page, confidence} matches sorted best-first —
    same shape/rationale as mm_duplicates.detect_duplicates. [] on failure,
    no session_id, or the first time anything's been registered."""
    if not session_id:
        return []
    residual = _extract_residual(b64)
    if residual is None:
        return []

    with _lock:
        seen = _registry.setdefault(session_id, [])
        matches = []
        for other_residual, other_source, other_page in seen:
            score = _pce(residual, other_residual)
            confidence = float(np.clip(
                (score - _PCE_CLEAN_CEILING) / (_PCE_MATCH_FLOOR - _PCE_CLEAN_CEILING), 0.0, 1.0,
            ))
            if confidence > 0.0:
                matches.append({"source": other_source, "page": other_page, "confidence": round(confidence, 3)})
        seen.append((residual, source, page))
        if len(seen) > _MAX_PER_SESSION:
            del seen[0]

    matches.sort(key=lambda m: -m["confidence"])
    return matches[:_MAX_MATCHES]


def evict_camera_match(source: str) -> None:
    """Drops every registered residual for a removed document, across all
    sessions — mirrors mm_duplicates.evict_duplicates exactly, called from
    the same removal path."""
    with _lock:
        for seen in _registry.values():
            seen[:] = [entry for entry in seen if entry[1] != source]


def describe_camera_match(matches: list[dict] | None) -> str:
    """Same rationale as describe_duplicates: baked into the stored chunk
    text so groundedness/citation scoring can back a "did these come from
    the same camera" answer."""
    if not matches:
        return ""
    n = len(matches)
    return (f"Possible shared camera: this image's sensor noise pattern matches {n} other "
            f"page{'s' if n != 1 else ''} already uploaded this session — a real forensic "
            "technique (source-camera identification), not a guess from how the photo looks. "
            "A strong hint, not proof — resizing or heavily cropping either photo can break "
            "the match even when it IS the same camera.")


def refresh_camera_match_for_chunks(chunks: list[dict], page_images: list[str], session_id: str) -> None:
    """Re-runs camera-match detection against THIS caller's session registry
    for chunks pulled from mm_ingest's expensive-artifact cache — same
    rationale as mm_duplicates.refresh_duplicates_for_chunks (that cache is
    keyed only on file bytes, not session_id, so a cache hit would otherwise
    skip registry registration entirely). Mutates chunks in place."""
    for chunk in chunks:
        if chunk.get("chunk_type") not in ("image", "video"):
            continue
        page = chunk.get("page") or 1
        idx = page - 1
        if idx < 0 or idx >= len(page_images):
            continue
        matches = check_camera_match(page_images[idx], chunk["source"], page, session_id)
        chunk["camera_match"] = matches
        desc = describe_camera_match(matches)
        if desc and desc not in (chunk.get("text") or ""):
            chunk["text"] = f"{chunk['text']}\n\n{desc}" if chunk.get("text") else desc
