"""Standalone audio ingestion for multimodal RAG (MMRAG-06) — a bare
audio file (podcast, meeting recording, voice memo), no video attached.

Reuses mm_video.py's transcribe_video() unmodified: that function only
ever shells out to ffmpeg on a file path and calls Whisper — it never
touches video frames, so it already works identically for a standalone
audio file. The only genuinely new code here is detecting an audio
upload and writing it to a temp file for ffmpeg to read.
"""
from __future__ import annotations

import os
import tempfile

AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma")
AUDIO_CONTENT_TYPES = ("audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4",
                       "audio/m4a", "audio/x-m4a", "audio/ogg", "audio/flac", "audio/aac")


def looks_like_audio(filename: str, content_type: str) -> bool:
    return filename.lower().endswith(AUDIO_EXTENSIONS) or content_type in AUDIO_CONTENT_TYPES


def prepare_audio(file_bytes: bytes, filename: str) -> str:
    """Write to a temp file (ffmpeg needs a real path, not bytes) — keeps
    the original extension so ffmpeg sniffs the container correctly."""
    suffix = os.path.splitext(filename)[1] or ".mp3"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(file_bytes)
    tmp.close()
    return tmp.name


def close_audio(tmp_path: str) -> None:
    try:
        os.unlink(tmp_path)
    except OSError:
        pass


def transcribe_audio_upload(file_bytes: bytes, filename: str, source: str):
    """Runs the full standalone-audio pipeline as one atomic call (same
    "no sub-steps to report" shape as build_image_chunk() for images):
    write to a temp file, transcribe (transcribe_video() is generic over
    any ffmpeg-decodable path, video or bare audio), generate chapters,
    clean up. Returns (chunks, chunk_summary, transcript_text,
    transcript_segments, chapters)."""
    from routers.rag.mm_video import generate_chapters, transcribe_video
    from routers.rag.mm_deepfake import detect_audio_deepfake_signals

    tmp_path = prepare_audio(file_bytes, filename)
    try:
        chunks, transcript_count, transcript_text, transcript_segments = transcribe_video(tmp_path, source)
        # Voice-clone artifact check only — no video frames exist for a
        # standalone audio upload, so the AV-desync half doesn't apply here.
        deepfake = detect_audio_deepfake_signals(tmp_path)
    finally:
        close_audio(tmp_path)

    summary = {"text": transcript_count, "table": 0, "figure": 0}
    chapters = generate_chapters(transcript_segments) if transcript_segments else []
    return chunks, summary, transcript_text, transcript_segments, chapters, deepfake
