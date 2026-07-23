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
import json
import logging
import os
import subprocess
import tempfile

from routers.document._vision import _vision_cascade_raw, mistral_ocr_pages
from routers.rag.ingest import chunk_document
from routers.rag.mm_caption import clean_ocr_text, extract_caption

logger = logging.getLogger(__name__)

MAX_VIDEO_FRAMES = 6
_OCR_TEXT_CAP = 2000
_TRANSCRIBE_MODEL = "whisper-large-v3-turbo"

MIN_FRAMES_WITH_TRANSCRIPT = 2   # once real speech content exists, frames
                                 # mostly just confirm "still the same
                                 # scene" for a talking-head video — cut
                                 # sampling down rather than caption 6
                                 # near-identical moments
_SUBSTANTIAL_TRANSCRIPT_CHARS = 100


def reduced_frame_count(n_frames: int, transcript_chunks: list[dict]) -> int:
    """A real transcript means the audio, not the frames, carries the
    content — visual sampling adds little beyond confirming the scene
    hasn't changed. No transcript (silent/failed audio) keeps the full
    frame count, since frames are then the ONLY signal available."""
    total_chars = sum(len(c["text"]) for c in transcript_chunks)
    if total_chars >= _SUBSTANTIAL_TRANSCRIPT_CHARS:
        return min(n_frames, MIN_FRAMES_WITH_TRANSCRIPT)
    return n_frames

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
    ocr_text = clean_ocr_text(ocr_md)[:_OCR_TEXT_CAP]
    if not ocr_text:
        return caption
    if not caption:
        return ocr_text
    return f"{caption}\n\nExact text from frame (OCR):\n{ocr_text}"


def prepare_video(file_bytes: bytes):
    """Write to a temp file (cv2 needs a real path, not bytes) and open it.
    Returns (cap, tmp_path, n_frames, duration_s)."""
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
    duration_s = (total_frames / fps) if (total_frames > 0 and fps > 0) else 0.0
    n_frames = min(MAX_VIDEO_FRAMES, total_frames) if total_frames > 0 else MAX_VIDEO_FRAMES
    return cap, tmp.name, n_frames, duration_s


def process_frame(cap, frame_idx: int, n_frames: int, duration_s: float,
                  source: str) -> tuple[list[dict], str, dict]:
    """Seek to and caption ONE evenly-spaced sampled frame (1-indexed).
    Returns (chunks, frame_b64, page_summary).

    Seeks by TIMESTAMP (CAP_PROP_POS_MSEC), not frame count
    (CAP_PROP_POS_FRAMES) — observed live: frame-index seeking on a
    real H.264 (inter-frame-compressed) video silently returned the
    SAME frame for three different target indices, producing
    byte-identical captions. Timestamp-based seeking is the standard,
    much more reliable fix for this class of OpenCV/ffmpeg behavior."""
    import cv2

    target_ms = (frame_idx - 1) * (duration_s * 1000 / n_frames) if duration_s > 0 else 0
    cap.set(cv2.CAP_PROP_POS_MSEC, target_ms)
    ok, frame = cap.read()
    page_summary = {"text": 0, "table": 0, "figure": 0, "video": 0}
    if not ok:
        return [], "", page_summary

    ok, buf = cv2.imencode(".png", frame)
    if not ok:
        return [], "", page_summary
    b64 = base64.b64encode(buf.tobytes()).decode()

    timestamp_s = target_ms / 1000
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


_MAX_WHISPER_BYTES = 24 * 1024 * 1024  # Groq's cap is 25MB; keep a safety margin
_WAV_BYTES_PER_SEC = 16000 * 2         # 16kHz mono 16-bit PCM = 32000 bytes/sec


def _extract_audio_wav_to_file(video_path: str, wav_path: str) -> bool:
    """16kHz mono WAV, the format Whisper expects, written to wav_path (not
    returned as bytes — a real file is needed so a long recording's audio
    can be measured and split before transcription). False if there's no
    audio track or extraction otherwise fails — never raises."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
             "-ar", "16000", "-ac", "1", wav_path],
            capture_output=True, timeout=120,
        )
        return result.returncode == 0 and os.path.exists(wav_path) and os.path.getsize(wav_path) > 44
    except Exception as exc:
        logger.warning("Audio extraction failed: %s", exc)
        return False


def _wav_duration_s(wav_path: str) -> float:
    return max(0.0, (os.path.getsize(wav_path) - 44) / _WAV_BYTES_PER_SEC)  # 44-byte WAV header


def _split_wav(wav_path: str, chunk_duration_s: float) -> list[str]:
    """Slice a long WAV into sequential sub-files of ~chunk_duration_s each,
    via ffmpeg (re-encodes the actual audio at each cut point, not a raw
    byte split — every chunk is its own valid, independently-decodable
    WAV). Only called when the full file already exceeds Groq's size cap."""
    total_s = _wav_duration_s(wav_path)
    paths = []
    start, idx = 0.0, 0
    while start < total_s:
        out_path = f"{wav_path}.part{idx}.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-i", wav_path, "-ss", str(start), "-t", str(chunk_duration_s),
             "-c", "copy", out_path],
            capture_output=True, timeout=60,
        )
        if os.path.exists(out_path) and os.path.getsize(out_path) > 44:
            paths.append(out_path)
        start += chunk_duration_s
        idx += 1
    return paths


def _transcribe_long_audio(wav_path: str) -> tuple[str, list[dict]]:
    """Transcribes a WAV of any length — splitting into Groq-size-limited
    chunks only when the file actually exceeds the cap, transcribing each
    sequentially, and stitching results back together with each chunk's
    segment timestamps offset by its real position in the full recording."""
    if os.path.getsize(wav_path) <= _MAX_WHISPER_BYTES:
        with open(wav_path, "rb") as f:
            return _transcribe_audio(f.read())

    chunk_duration_s = (_MAX_WHISPER_BYTES / _WAV_BYTES_PER_SEC) * 0.95  # margin for WAV header/encoding overhead
    chunk_paths = _split_wav(wav_path, chunk_duration_s)
    logger.info("Audio exceeds Whisper's size cap — split into %d chunks of ~%.0fs each",
               len(chunk_paths), chunk_duration_s)

    full_text_parts: list[str] = []
    all_segments: list[dict] = []
    offset = 0.0
    for chunk_path in chunk_paths:
        try:
            with open(chunk_path, "rb") as f:
                text, segments = _transcribe_audio(f.read())
            full_text_parts.append(text)
            for seg in segments:
                all_segments.append({"start": seg["start"] + offset, "end": seg["end"] + offset, "text": seg["text"]})
            offset += _wav_duration_s(chunk_path)
        finally:
            try:
                os.unlink(chunk_path)
            except OSError:
                pass
    return " ".join(p for p in full_text_parts if p), all_segments


def _transcribe_audio(wav_bytes: bytes) -> tuple[str, list[dict]]:
    """Returns (full_text, segments) where each segment is
    {"start": float, "end": float, "text": str} in source order — the data
    a timestamped view or an .srt export needs. Both empty on any failure."""
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return "", []
    try:
        import httpx
        with httpx.Client(timeout=90) as client:
            r = client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                data={"model": _TRANSCRIBE_MODEL, "response_format": "verbose_json"},
            )
            r.raise_for_status()
            data = r.json()
            raw_segments = data.get("segments", [])
            segments = [{"start": s.get("start", 0.0), "end": s.get("end", 0.0),
                        "text": (s.get("text") or "").strip()} for s in raw_segments]
            last_end = segments[-1]["end"] if segments else 0
            logger.info("Whisper transcription: %d segments, audio_duration=%.1fs, last_segment_end=%.1fs",
                       len(segments), data.get("duration", 0), last_end)
            return (data.get("text") or "").strip(), segments
    except Exception as exc:
        logger.warning("Audio transcription failed: %s", exc)
        return "", []


def transcribe_video(video_path: str, source: str) -> tuple[list[dict], int, str, list[dict]]:
    """Extract + transcribe the audio track, chunked the same way plain-text
    documents are (chunk_document) for retrieval, PLUS the full unchunked
    transcript and its timestamped segments for display/download. Returns
    (chunks, chunk_count, transcript_text, segments); all empty if there's
    no audio or transcription failed — callers should treat that as
    "visual-only," not an error."""
    wav_path = video_path + ".wav"
    if not _extract_audio_wav_to_file(video_path, wav_path):
        return [], 0, "", []

    try:
        transcript, segments = _transcribe_long_audio(wav_path)
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass

    if not transcript.strip():
        return [], 0, "", []

    chunks = chunk_document(transcript, source)
    for c in chunks:
        c["chunk_type"] = "text"
    return chunks, len(chunks), transcript, segments


_MIN_SEGMENTS_FOR_CHAPTERS = 4  # a handful of short segments isn't worth chaptering
_MAX_CHAPTERS = 6


def generate_chapters(segments: list[dict]) -> list[dict]:
    """One LLM call over the timestamped transcript to produce a handful of
    chapter markers (like YouTube auto-chapters) — {"time": seconds,
    "label": short title}. Returns [] on any failure or too little content;
    never blocks ingestion on this being unavailable."""
    if len(segments) < _MIN_SEGMENTS_FOR_CHAPTERS:
        return []
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return []

    transcript_lines = "\n".join(f"[{s['start']:.0f}s] {s['text']}" for s in segments)
    prompt = (
        f"Here is a timestamped transcript:\n{transcript_lines}\n\n"
        f"Identify up to {_MAX_CHAPTERS} distinct topic changes/chapters in it. "
        'Return JSON only: {"chapters": [{"time": <seconds, integer>, "label": '
        '"<short 3-6 word title>"}]}. Each time must be one of the timestamps '
        "that actually appears above. Order chapters chronologically. If the "
        "whole transcript is really just one topic, return a single chapter."
    )
    try:
        import httpx
        with httpx.Client(timeout=60) as client:
            r = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": "llama-3.3-70b-versatile",
                      "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": 500, "response_format": {"type": "json_object"}},
            )
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"]
            data = json.loads(raw)
            return [{"time": float(c["time"]), "label": str(c["label"])[:60]}
                    for c in data.get("chapters", []) if "time" in c and "label" in c]
    except Exception as exc:
        logger.warning("Chapter generation failed: %s", exc)
        return []
