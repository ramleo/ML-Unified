"""Video ingestion for multimodal RAG — samples a handful of key frames and
captions+OCRs each exactly like a PDF figure page. Audio transcription and
chaptering split out to mm_video_audio.py to stay under the project's
file-length limit.
"""
from __future__ import annotations

import base64
import logging
import os
import tempfile

from routers.document._vision import _vision_cascade_raw, mistral_ocr_pages
from routers.rag.mm_caption import clean_ocr_text, extract_caption
from routers.rag.mm_objects import describe_objects, detect_objects
from routers.rag.mm_signatures import describe_signatures, detect_signatures
from routers.rag.mm_tampering import describe_tampering, detect_tampering
from routers.rag.mm_video_audio import generate_chapters, transcribe_video

logger = logging.getLogger(__name__)

MAX_VIDEO_FRAMES = 6
_OCR_TEXT_CAP = 2000

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


def process_frame(cap, timestamp_s: float, frame_idx: int, source: str) -> tuple[list[dict], str, dict]:
    """Seek to and caption ONE sampled frame at the given timestamp
    (frame_idx is just its 1-indexed display/citation order, no longer used
    to derive the timestamp itself — the caller decides WHERE to sample,
    via either uniform spacing or FFT scene-cut detection (MMRAG-11), see
    mm_scenecut.py). Returns (chunks, frame_b64, page_summary).

    Seeks by TIMESTAMP (CAP_PROP_POS_MSEC), not frame count
    (CAP_PROP_POS_FRAMES) — observed live: frame-index seeking on a
    real H.264 (inter-frame-compressed) video silently returned the
    SAME frame for three different target indices, producing
    byte-identical captions. Timestamp-based seeking is the standard,
    much more reliable fix for this class of OpenCV/ffmpeg behavior."""
    import cv2

    cap.set(cv2.CAP_PROP_POS_MSEC, timestamp_s * 1000)
    ok, frame = cap.read()
    page_summary = {"text": 0, "table": 0, "figure": 0, "video": 0}
    if not ok:
        return [], "", page_summary

    ok, buf = cv2.imencode(".png", frame)
    if not ok:
        return [], "", page_summary
    b64 = base64.b64encode(buf.tobytes()).decode()

    caption = _caption_frame(b64, timestamp_s)
    if not caption:
        return [], b64, page_summary

    # Closed-vocabulary object detection (MMRAG-07 follow-up) — precomputed
    # here so a later "where is the X" chat question is a free metadata
    # lookup, not a fresh vision call. See mm_objects.py for scope/rationale.
    objects = detect_objects(b64)
    obj_desc = describe_objects(objects)
    if obj_desc:
        # Baked into the stored text (not just the LLM prompt) so
        # groundedness/citation-overlap scoring — which only ever reads
        # chunk["text"] — stays in sync with what the answer can say.
        caption = f"{caption}\n\n{obj_desc}"

    # Signature detection (backlog item 1) — same treatment as mm_image.py:
    # own model/vocabulary, kept as a separate field from `objects`.
    signatures = detect_signatures(b64)
    sig_desc = describe_signatures(signatures)
    if sig_desc:
        caption = f"{caption}\n\n{sig_desc}"

    # ELA tampering detection (backlog item 2) — same treatment as mm_image.py.
    tampering = detect_tampering(b64)
    tamper_desc = describe_tampering(tampering)
    if tamper_desc:
        caption = f"{caption}\n\n{tamper_desc}"

    chunk = {"text": caption, "source": source, "chunk_index": frame_idx - 1,
             "chunk_type": "video", "page": frame_idx, "objects": objects, "signatures": signatures,
             "tampering": tampering,
             # Real seconds into the video (not the 1-indexed sample number
             # above) — MMRAG-09: lets a citation for a visual-only frame
             # (nothing spoken at that moment) jump the player to the exact
             # instant it was captured, the same way a transcript citation
             # already jumps to its spoken segment.
             "timestamp_s": round(timestamp_s, 1)}
    page_summary["video"] = 1
    return [chunk], b64, page_summary


def close_video(cap, tmp_path: str) -> None:
    cap.release()
    try:
        os.unlink(tmp_path)
    except OSError:
        pass
