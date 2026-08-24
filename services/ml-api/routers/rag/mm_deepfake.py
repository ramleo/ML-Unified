"""Deepfake/synthetic-media forensics — two independent signal-processing
heuristics, NOT a trained deepfake classifier. Same spirit as mm_tampering.py
(ELA)/mm_moire.py (FFT)/mm_prnu.py (wavelet residual + PCE): interpretable,
disclosed-limitation techniques, chosen specifically because this project has
no torch/mediapipe/dlib and runs on a CPU-only hosted Space. A heavier
landmark-model approach (SyncNet, MediaPipe Face Mesh + DTW on precise lip-
aperture distance) would likely do better, and was deliberately not adopted —
not because it wouldn't work, but because it needs a new heavy inference
dependency this project has consistently avoided elsewhere. Revisit if that
tradeoff changes.

1. Audio-visual lip-sync desync (video only). Face+mouth-corner landmarks via
   YuNet (OpenCV Zoo's own official face detector for the 5.x DNN engine —
   Haar cascades no longer ship with opencv-python-headless 5.x at all,
   confirmed: cv2.CascadeClassifier doesn't exist and cv2.data.haarcascades
   is empty in this build). Motion energy = frame-to-frame pixel diff in a
   small crop around the mouth corners, resampled to a fixed 0.1s grid,
   compared against the audio's RMS envelope on the same grid.

   Real finding from validation: plain correlation (both a max-lag cross-
   correlation and a proper zero-lag Pearson) FAILED outright on a real test
   clip — the genuinely-synced case scored WORSE (in one case, negative)
   than a 1s-shifted or fully-shuffled negative control. Root cause: fixed-
   rate correlation has no tolerance for the natural timing jitter between
   speech and lip motion. Switching to Dynamic Time Warping (DTW) path cost
   — which tolerates that jitter — recovered a real, correctly-directed
   signal: on a 13.9s real recorded-speech clip, synced DTW cost was 0.267,
   clearly below the full range of 5 independently shuffled negative
   controls (0.289-0.322) and below a 1s-shifted control (0.274).

   This is a SINGLE-CLIP validation, not a broad dataset, and the margin
   between synced (0.267) and shifted (0.274) was small — this heuristic
   reliably catches a fully scrambled audio/video pairing but is weaker at
   catching a subtle few-hundred-ms offset. Treat the resulting flag as a
   coarse indicator, not a verdict, same framing as mm_tampering.py.

2. Voice-clone/synthetic-audio artifact (any audio — video's track or a
   standalone upload). Short-time spectral flatness (geometric/arithmetic
   mean of the STFT magnitude per time frame) variance over the clip. A real
   13.9s human-speech test clip scored variance 0.018; three different
   macOS system TTS voices (Samantha/Alex/Fred) reading the same script all
   scored 0.039-0.050 — a consistent, real, ~2-3x effect, though in the
   OPPOSITE direction from the initial hypothesis (synthetic voices showed
   HIGHER flatness variance, not lower). Disclosed limitation: only tested
   against macOS system TTS, not sophisticated neural voice-clone tools
   (e.g. ElevenLabs) — the more realistic fraud-call threat — which may not
   share this signature at all.
"""
from __future__ import annotations

import logging
import os
import subprocess

import cv2
import numpy as np
from scipy.io import wavfile
from scipy.signal import stft

logger = logging.getLogger(__name__)

_YUNET_PATH = os.path.join(os.path.dirname(__file__), "models", "face-detection-yunet.onnx")
_FACE_SCORE_THRESH = 0.5

_SAMPLE_INTERVAL_S = 0.1
_MAX_SAMPLES = 200          # ~20s at the 0.1s grid — longer clips are truncated, not downsampled
_MIN_SAMPLES_FOR_AV = 20    # DTW needs enough grid points to mean anything
_MIN_AUDIO_S_FOR_VOICE = 1.0  # need at least ~1s for a meaningful STFT series

# Calibrated against the single real validation clip above (synced 0.267,
# shifted 0.274, shuffled 0.289-0.322) — wide bounds with real margin on the
# shuffled side, but note the synced/shifted gap is genuinely small, which is
# exactly the disclosed weak spot in the module docstring, not hidden here.
_DTW_CLEAN_CEILING = 0.28
_DTW_FLAG_FLOOR = 0.32

# Calibrated against the same session's real-speech (0.018) vs. 3 macOS
# system voices (0.039-0.050).
_FLAT_VAR_CLEAN_CEILING = 0.025
_FLAT_VAR_FLAG_FLOOR = 0.045


def _extract_wav(src_path: str, wav_path: str) -> bool:
    """Own ffmpeg extraction (not a shared import from mm_video_audio.py's
    private helper) — by the time this module runs, transcribe_video() has
    already deleted its own WAV, and this keeps the two modules decoupled."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", src_path, "-vn", "-acodec", "pcm_s16le",
             "-ar", "16000", "-ac", "1", wav_path],
            capture_output=True, timeout=60,
        )
        return result.returncode == 0 and os.path.exists(wav_path) and os.path.getsize(wav_path) > 44
    except Exception as exc:
        logger.warning("Deepfake-signal audio extraction failed: %s", exc)
        return False


def _mouth_motion_series(video_path: str, timestamps: np.ndarray) -> np.ndarray:
    """Frame-to-frame pixel-diff energy in a small crop around the mouth
    corners (YuNet landmark indices 10-13 of its 15-value detection row).
    NaN for any timestamp where no face was found; filled with the series
    mean at the end so a few dropped frames don't break DTW. Empty array if
    NO frame in the whole series found a face."""
    cap = cv2.VideoCapture(video_path)
    try:
        ok, first = cap.read()
        if not ok:
            return np.array([])
        h, w = first.shape[:2]
        detector = cv2.FaceDetectorYN_create(_YUNET_PATH, "", (w, h), score_threshold=_FACE_SCORE_THRESH)

        energies: list[float] = []
        prev_crop = None
        for t in timestamps:
            cap.set(cv2.CAP_PROP_POS_MSEC, float(t) * 1000)
            ok, frame = cap.read()
            if not ok:
                energies.append(np.nan)
                prev_crop = None
                continue
            n, faces = detector.detect(frame)
            if not n or faces is None or len(faces) == 0:
                energies.append(np.nan)
                prev_crop = None
                continue
            face = faces[0]
            mx1, my1, mx2, my2 = face[10], face[11], face[12], face[13]
            cx, cy = (mx1 + mx2) / 2, (my1 + my2) / 2
            half_w = max(12.0, abs(mx2 - mx1) * 0.9)
            half_h = max(10.0, abs(mx2 - mx1) * 0.55)
            x0, y0 = int(max(0, cx - half_w)), int(max(0, cy - half_h))
            x1, y1 = int(min(w, cx + half_w)), int(min(h, cy + half_h))
            crop = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32)
            crop = cv2.resize(crop, (40, 30))
            energies.append(float(np.abs(crop - prev_crop).mean()) if prev_crop is not None else np.nan)
            prev_crop = crop

        arr = np.array(energies)
        if np.isnan(arr).all():
            return np.array([])
        return np.nan_to_num(arr, nan=float(np.nanmean(arr)))
    except Exception as exc:
        logger.warning("Mouth motion extraction failed: %s", exc)
        return np.array([])
    finally:
        cap.release()


def _audio_rms_envelope(wav_path: str, timestamps: np.ndarray, window_s: float = _SAMPLE_INTERVAL_S) -> np.ndarray:
    sr, data = wavfile.read(wav_path)
    if data.ndim > 1:
        data = data.mean(axis=1)
    data = data.astype(np.float64)
    half_win = int(window_s * sr / 2)
    env = []
    for t in timestamps:
        c = int(t * sr)
        seg = data[max(0, c - half_win):c + half_win]
        env.append(float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0)
    return np.array(env)


def _dtw_cost(a: np.ndarray, b: np.ndarray) -> float:
    """Normalized DTW path cost between two z-normalized 1D series — LOWER
    means better-aligned. See module docstring for why this replaced a
    correlation-based approach that failed outright."""
    a = (a - a.mean()) / (a.std() + 1e-8)
    b = (b - b.mean()) / (b.std() + 1e-8)
    n, m = len(a), len(b)
    d = np.full((n + 1, m + 1), np.inf)
    d[0, 0] = 0.0
    for i in range(1, n + 1):
        ai = a[i - 1]
        row, prev_row = d[i], d[i - 1]
        for j in range(1, m + 1):
            cost = abs(ai - b[j - 1])
            row[j] = cost + min(prev_row[j], row[j - 1], prev_row[j - 1])
    return float(d[n, m] / (n + m))


def _av_desync_flag(video_path: str, wav_path: str) -> dict | None:
    try:
        sr, data = wavfile.read(wav_path)
        duration_s = len(data) / sr if sr else 0.0
    except Exception:
        return None
    if duration_s < 2.0:
        return None

    timestamps = np.arange(0, duration_s, _SAMPLE_INTERVAL_S)[:_MAX_SAMPLES]
    if len(timestamps) < _MIN_SAMPLES_FOR_AV:
        return None

    motion = _mouth_motion_series(video_path, timestamps)
    if motion.size == 0:
        return None  # no face found in any sampled frame

    audio_env = _audio_rms_envelope(wav_path, timestamps)
    cost = _dtw_cost(motion, audio_env)
    confidence = float(np.clip((cost - _DTW_CLEAN_CEILING) / (_DTW_FLAG_FLOOR - _DTW_CLEAN_CEILING), 0.0, 1.0))
    return {
        "flagged": confidence > 0.0,
        "confidence": round(confidence, 3),
        "note": ("Mouth motion doesn't track speech energy as closely as expected — a coarse "
                 "indicator of possible lip-sync desync (face swap or dubbed audio), not a "
                 "verdict. Validated on one real clip; reliably catches a fully scrambled "
                 "audio/video pairing, weaker at catching a subtle timing offset."
                 if confidence > 0.0 else ""),
    }


def _spectral_flatness_variance(wav_path: str) -> float | None:
    try:
        sr, data = wavfile.read(wav_path)
        if data.ndim > 1:
            data = data.mean(axis=1)
        data = data.astype(np.float64)
        if len(data) < sr * _MIN_AUDIO_S_FOR_VOICE:
            return None
        _, _, zxx = stft(data, fs=sr, nperseg=1024)
        mag = np.abs(zxx) + 1e-12
        gm = np.exp(np.mean(np.log(mag), axis=0))
        am = np.mean(mag, axis=0)
        return float((gm / am).var())
    except Exception as exc:
        logger.warning("Spectral flatness computation failed: %s", exc)
        return None


def _voice_artifact_flag(wav_path: str) -> dict | None:
    var = _spectral_flatness_variance(wav_path)
    if var is None:
        return None
    confidence = float(np.clip(
        (var - _FLAT_VAR_CLEAN_CEILING) / (_FLAT_VAR_FLAG_FLOOR - _FLAT_VAR_CLEAN_CEILING), 0.0, 1.0))
    return {
        "flagged": confidence > 0.0,
        "confidence": round(confidence, 3),
        "note": ("Spectral flatness varies more over time than natural speech typically does — "
                 "a pattern seen consistently in synthetic/TTS voices during testing, not proof "
                 "of voice cloning. Only validated against system text-to-speech, not "
                 "sophisticated neural voice-clone tools, which may not share this signature."
                 if confidence > 0.0 else ""),
    }


def detect_video_deepfake_signals(video_path: str) -> dict:
    """One-shot, whole-clip analysis — call once per video, using the same
    tmp video path already open in the caller (still valid until close_video
    unlinks it). Never raises. Returns
    {"av_desync": {...}|None, "voice_artifact": {...}|None}."""
    wav_path = video_path + ".df.wav"
    if not _extract_wav(video_path, wav_path):
        return {"av_desync": None, "voice_artifact": None}
    try:
        return {"av_desync": _av_desync_flag(video_path, wav_path),
                "voice_artifact": _voice_artifact_flag(wav_path)}
    except Exception as exc:
        logger.warning("Deepfake signal detection failed: %s", exc)
        return {"av_desync": None, "voice_artifact": None}
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass


def detect_audio_deepfake_signals(audio_path: str) -> dict:
    """Voice-artifact only — for standalone audio uploads (mm_audio.py),
    where no video frames exist for the AV-desync signal."""
    wav_path = audio_path + ".df.wav"
    if not _extract_wav(audio_path, wav_path):
        return {"voice_artifact": None}
    try:
        return {"voice_artifact": _voice_artifact_flag(wav_path)}
    except Exception as exc:
        logger.warning("Deepfake signal detection failed: %s", exc)
        return {"voice_artifact": None}
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass


def describe_deepfake_signals(signals: dict | None) -> str:
    """Baked into stored text, same rationale as every other detector's
    describe_* — groundedness/citation scoring only ever reads chunk text."""
    if not signals:
        return ""
    parts = []
    av = signals.get("av_desync")
    if av and av.get("flagged"):
        parts.append(f"Possible audio/lip-motion desync ({round(av['confidence'] * 100)}% confidence) — {av['note']}")
    voice = signals.get("voice_artifact")
    if voice and voice.get("flagged"):
        parts.append(f"Possible synthetic/cloned voice ({round(voice['confidence'] * 100)}% confidence) — {voice['note']}")
    return "\n\n".join(parts)
