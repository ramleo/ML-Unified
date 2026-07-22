"""Video ingestion for multimodal RAG — samples a handful of key frames and
captions+OCRs each exactly like a PDF figure page, PLUS transcribes any
audio track. Split out of mm_ingest.py to stay under the project's
file-length limit.

Audio transcription reuses Groq's Whisper endpoint (whisper-large-v3-turbo)
— the same GROQ_API_KEY server secret already trusted everywhere else in
this codebase, no new API/credential surface. ffmpeg (already a system
dependency, added to the Dockerfile for opencv's video decoding) extracts
the audio track to WAV first. Both extraction and transcription fail
silently (never raise) — a video with no/failed audio still ingests its
visual frames.
"""
from __future__ import annotations

import base64
import logging
import os
import subprocess
import tempfile

from routers.document._vision import _vision_cascade_raw, mistral_ocr_pages
from routers.rag.ingest import chunk_document
from routers.rag.mm_caption import extract_caption

logger = logging.getLogger(__name__)

MAX_VIDEO_FRAMES = 6
_OCR_TEXT_CAP = 2000
_TRANSCRIBE_MODEL = "whisper-large-v3-turbo"

VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".avi", ".mkv")
VIDEO_CONTENT_TYPES = ("video/mp4", "video/quicktime", "video/webm",
                       "video/x-msvideo", "video/x-matroska")


def looks_like_video(filename: str, content_type: str) -> bool:
    return filename.lower().endswith(VIDEO_EXTENSIONS) or content_type in VIDEO_CONTENT_TYPES


def _frame_prompt(timestamp_s: float) -> str:
    return (
        f"This is a frame captured at {timestamp_s:.1f} seconds into a video. "
        "Write a factual 2-4 sentence description of what's shown: subject, "
        "setting, and any visible text/numbers/UI elements (transcribe exactly). "
        'Return JSON only: {"caption": "<your description>"}.'
    )


def _caption_frame(b64: str, timestamp_s: float) -> str:
    caption = extract_caption(_vision_cascade_raw(b64, _frame_prompt(timestamp_s)), 600)
    ocr_md, _ = mistral_ocr_pages([b64])
    ocr_text = ocr_md.strip()[:_OCR_TEXT_CAP]
    if not ocr_text:
        return caption
    if not caption:
        return ocr_text
    return f"{caption}\n\nExact text from frame (OCR):\n{ocr_text}"


def prepare_video(file_bytes: bytes):
    """Write to a temp file (cv2 needs a real path, not bytes) and open it.
    Returns (cap, tmp_path, n_frames, total_frames, fps)."""
    import cv2

    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.write(file_bytes)
    tmp.close()
    cap = cv2.VideoCapture(tmp.name)
    if not cap.isOpened():
        cap.release()
        os.unlink(tmp.name)
        raise ValueError("Could not open video — unsupported or corrupt format.")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_frames = min(MAX_VIDEO_FRAMES, total_frames) if total_frames > 0 else MAX_VIDEO_FRAMES
    return cap, tmp.name, n_frames, total_frames, fps


def process_frame(cap, frame_idx: int, n_frames: int, total_frames: int, fps: float,
                  source: str) -> tuple[list[dict], str, dict]:
    """Seek to and caption ONE evenly-spaced sampled frame (1-indexed).
    Returns (chunks, frame_b64, page_summary)."""
    import cv2

    target = int((frame_idx - 1) * total_frames / n_frames) if total_frames > 0 else 0
    cap.set(cv2.CAP_PROP_POS_FRAMES, target)
    ok, frame = cap.read()
    page_summary = {"text": 0, "table": 0, "figure": 0, "video": 0}
    if not ok:
        return [], "", page_summary

    ok, buf = cv2.imencode(".png", frame)
    if not ok:
        return [], "", page_summary
    b64 = base64.b64encode(buf.tobytes()).decode()

    timestamp_s = target / fps if fps else 0.0
    caption = _caption_frame(b64, timestamp_s)
    if not caption:
        return [], b64, page_summary

    chunk = {"text": caption, "source": source, "chunk_index": frame_idx - 1,
             "chunk_type": "video", "page": frame_idx}
    page_summary["video"] = 1
    return [chunk], b64, page_summary


def close_video(cap, tmp_path: str) -> None:
    cap.release()
    try:
        os.unlink(tmp_path)
    except OSError:
        pass


def _extract_audio_wav(video_path: str) -> bytes | None:
    """16kHz mono WAV, the format Whisper expects. Returns None if there's
    no audio track or extraction otherwise fails — never raises."""
    wav_path = video_path + ".wav"
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
             "-ar", "16000", "-ac", "1", wav_path],
            capture_output=True, timeout=60,
        )
        if result.returncode != 0 or not os.path.exists(wav_path):
            return None
        with open(wav_path, "rb") as f:
            data = f.read()
        return data if len(data) > 44 else None  # 44 bytes = empty WAV header only
    except Exception as exc:
        logger.warning("Audio extraction failed: %s", exc)
        return None
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass


def _transcribe_audio(wav_bytes: bytes) -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return ""
    try:
        import httpx
        with httpx.Client(timeout=90) as client:
            r = client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                data={"model": _TRANSCRIBE_MODEL, "response_format": "text"},
            )
            r.raise_for_status()
            return r.text.strip()
    except Exception as exc:
        logger.warning("Audio transcription failed: %s", exc)
        return ""


def transcribe_video(video_path: str, source: str) -> tuple[list[dict], int]:
    """Extract + transcribe the audio track, chunked the same way plain-text
    documents are (chunk_document). Returns (chunks, chunk_count); both empty
    if there's no audio or transcription failed — callers should treat that
    as "visual-only," not an error."""
    wav_bytes = _extract_audio_wav(video_path)
    if not wav_bytes:
        return [], 0

    transcript = _transcribe_audio(wav_bytes)
    if not transcript.strip():
        return [], 0

    chunks = chunk_document(transcript, source)
    for c in chunks:
        c["chunk_type"] = "text"
    return chunks, len(chunks)
