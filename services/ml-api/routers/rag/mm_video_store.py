"""In-memory store for raw uploaded video bytes, keyed by source — powers
click-to-seek playback in the frontend (an actual <video> element, not
just static frame thumbnails). Ephemeral like everything else in this
Space: small capacity, evicted when a document is removed, gone on
restart. Split into its own module since serving/storing raw bytes for
playback is a genuinely separate concern from mm_video.py's frame and
transcript extraction.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

router = APIRouter()

_MAX_VIDEOS = 3  # small cap — raw video bytes are much larger than
                 # everything else kept in memory (chunks, page images)
_store: dict[str, tuple[bytes, str]] = {}  # source -> (bytes, content_type)


def store_video(source: str, data: bytes, content_type: str) -> None:
    _store[source] = (data, content_type or "video/mp4")
    while len(_store) > _MAX_VIDEOS:
        oldest = next(iter(_store))
        del _store[oldest]


def evict_video(source: str) -> None:
    _store.pop(source, None)


@router.get("/video/{source:path}")
def get_video(source: str, request: Request):
    """Serves the raw video with basic HTTP Range support — required for
    browsers to seek a <video> element rather than only play from 0:00."""
    item = _store.get(source)
    if not item:
        raise HTTPException(status_code=404,
                            detail="Video not available — session ended, evicted for space, or not a video upload.")
    data, content_type = item
    size = len(data)
    range_header = request.headers.get("range")
    if range_header:
        try:
            spec = range_header.replace("bytes=", "").split("-")
            start = int(spec[0]) if spec[0] else 0
            end = int(spec[1]) if len(spec) > 1 and spec[1] else size - 1
            end = min(end, size - 1)
            chunk = data[start:end + 1]
            return Response(content=chunk, status_code=206, media_type=content_type, headers={
                "Content-Range": f"bytes {start}-{end}/{size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(len(chunk)),
            })
        except (ValueError, IndexError):
            pass  # malformed Range header — fall through to a full response
    return Response(content=data, media_type=content_type, headers={
        "Accept-Ranges": "bytes", "Content-Length": str(size),
    })
