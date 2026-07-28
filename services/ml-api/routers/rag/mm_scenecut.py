"""FFT-based scene-cut detection for smarter video-frame sampling (MMRAG-11).

Uniform time-spaced sampling (the previous approach) can waste the small
frame budget on near-duplicate content — 6 evenly-spaced frames of a video
that only actually changes scene twice mostly just repeat the same shot.
This probes the video at a coarse, cheap cadence, compares consecutive
probes in the frequency domain (a 2D FFT magnitude spectrum, not raw pixel
diffing — robust to small camera shake/compression noise that a pixel diff
would flag as a "cut"), and prefers sampling right where the spectrum
actually jumps. Falls back to plain uniform spacing whenever the video
doesn't show that kind of structure (e.g. a static talking-head shot),
since forcing "cuts" out of noise there would be worse than even spacing.
No new dependency — numpy and cv2 are already required by mm_video.py.
"""
from __future__ import annotations

import statistics

import numpy as np

_PROBE_INTERVAL_S = 0.5
_MAX_PROBES = 40
_SIGNATURE_SIZE = 64  # small enough that a 2D FFT over it is effectively free


def _uniform_timestamps(duration_s: float, n_frames: int) -> list[float]:
    return [i * duration_s / n_frames for i in range(n_frames)]


def _frame_signature(frame_bgr) -> np.ndarray:
    import cv2
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (_SIGNATURE_SIZE, _SIGNATURE_SIZE))
    spectrum = np.fft.fftshift(np.fft.fft2(small))
    return np.log1p(np.abs(spectrum))


def detect_scene_cut_timestamps(cap, duration_s: float, n_frames: int) -> list[float]:
    """Returns up to n_frames timestamps (seconds), chronologically sorted,
    biased toward real scene changes when the video has any; otherwise the
    same uniform spacing mm_video.py used before this feature existed."""
    import cv2

    if duration_s <= 0 or n_frames <= 1:
        return [0.0] if n_frames >= 1 else []

    interval = max(_PROBE_INTERVAL_S, duration_s / _MAX_PROBES)
    probe_times: list[float] = []
    t = 0.0
    while t < duration_s and len(probe_times) < _MAX_PROBES:
        probe_times.append(t)
        t += interval

    signatures: list[np.ndarray | None] = []
    for pt in probe_times:
        cap.set(cv2.CAP_PROP_POS_MSEC, pt * 1000)
        ok, frame = cap.read()
        signatures.append(_frame_signature(frame) if ok else None)

    diffs: list[tuple[float, float]] = []  # (spectral distance, timestamp of the later frame)
    for i in range(1, len(signatures)):
        if signatures[i] is None or signatures[i - 1] is None:
            continue
        dist = float(np.linalg.norm(signatures[i] - signatures[i - 1]))
        diffs.append((dist, probe_times[i]))

    if not diffs:
        return _uniform_timestamps(duration_s, n_frames)

    magnitudes = [d for d, _ in diffs]
    median = statistics.median(magnitudes)
    # No diff stands out from the noise floor — nothing that looks like a
    # real cut, just ordinary frame-to-frame variation. Uniform sampling is
    # the honest choice here, not a forced/arbitrary "cut."
    if median == 0 or max(magnitudes) < median * 2.0:
        return _uniform_timestamps(duration_s, n_frames)

    min_gap = duration_s / (n_frames * 2)
    chosen = [0.0]
    for dist, ts in sorted(diffs, key=lambda d: -d[0]):
        if len(chosen) >= n_frames:
            break
        if all(abs(ts - c) >= min_gap for c in chosen):
            chosen.append(ts)

    # Detected cuts alone don't fill the frame budget (e.g. one real cut in
    # an otherwise static video) — round out the remaining slots with
    # uniform spacing rather than leaving frames unsampled.
    if len(chosen) < n_frames:
        for ts in _uniform_timestamps(duration_s, n_frames):
            if len(chosen) >= n_frames:
                break
            if all(abs(ts - c) >= min_gap for c in chosen):
                chosen.append(ts)

    return sorted(chosen)[:n_frames]
