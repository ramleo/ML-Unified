"""Builds the final SSE 'done' event payload for mm_ingest.py — split out
to stay under the project's file-length limit."""
from __future__ import annotations

from routers.rag.pii import detect_pii_types
from routers.rag.entities import extract_entities


def build_done_event(*, source: str, session_id: str, save_scope: str, chunks: list[dict],
                     summary: dict, file_type: str, page_images: list[str],
                     revision_candidate: dict | None, transcript_text: str,
                     transcript_segments: list[dict], chapters: list[dict]) -> dict:
    return {
        "done": True,
        "source": source,
        "session_id": session_id,
        "save_scope": save_scope,
        "chunks_added": len(chunks),
        "chunk_summary": summary,
        # "pdf"|"csv"|"video"|"audio"|"image" — already computed by the
        # caller (mm_ingest.py) for analytics/text_segments-exclusion above,
        # but never actually surfaced to the frontend until now. Lets the UI
        # tell "standalone image/video upload" apart from "PDF" reliably,
        # instead of guessing from chunk-type counts (a real image upload
        # CAN produce a "table" chunk when it contains a readable chart/grid
        # — chunk counts alone aren't a safe proxy for the source file type).
        "file_type": file_type,
        # Which entity types (MMRAG-03: money/date/percent) appear ANYWHERE
        # in this document, computed once here rather than folded into
        # `summary` above — that dict already powers the "N chunks" count
        # badge and per-page aggregation across 4 different file-type
        # processors; keeping this separate avoids touching that surface
        # just to answer "should the entity filter chips even show."
        "entity_types": sorted({e["type"] for c in chunks for e in extract_entities(c.get("text", ""))}),
        # Plain-text chunks, in order — powers a live search/highlight box
        # in the summary panel for non-video docs. Excluded for video: its
        # audio transcript is ALSO tagged chunk_type "text", but already has
        # a richer, timestamped view (transcript_segments below) — this
        # would just duplicate it under a second search box.
        "text_segments": (
            [{"page": c.get("page"), "text": c.get("text", "")} for c in chunks if c.get("chunk_type") == "text"]
            if file_type not in ("video", "audio") else []
        ),
        "page_images": page_images,
        # Informational only — the frontend asks the user before doing
        # anything; nothing is ever auto-replaced.
        "possible_revision_of": revision_candidate,
        # Non-text chunks only (tables/figures/images) — powers a per-document
        # summary view without a separate query. Plain text chunks are
        # excluded: often numerous/large, and not what a "what did we
        # extract" glance actually needs.
        "notable_chunks": [
            {"chunk_type": c.get("chunk_type"), "page": c.get("page"), "text": c.get("text"),
             # Real seconds into the video for a frame chunk (MMRAG-09) —
             # None for every other chunk type.
             "timestamp_s": c.get("timestamp_s"),
             # Raw list, not JSON-encoded — this goes straight into the SSE
             # response, not through Chroma (unlike ingest.py's copy, which
             # must be scalar), so no encode/decode round-trip needed here.
             "bbox": c.get("bbox"),
             "objects": c.get("objects") or None,
             "signatures": c.get("signatures") or None,
             "tampering": c.get("tampering") or None,
             "duplicates": c.get("duplicates") or None,
             "number_mismatch": c.get("number_mismatch") or None,
             "pii_types": ",".join(detect_pii_types(c.get("text", ""))) or None,
             "blurry": (c.get("quality") or {}).get("blurry") or None,
             # Same extract_entities() call ingest.py's index_chunks() uses
             # to build Chroma metadata (entities are derived purely from
             # `text`, so this is deterministic, not a second real
             # computation) — just never surfaced in the SSE response
             # before, so the frontend could only ever see a chunk's
             # entities via a later query-time citation, not right after
             # upload like objects/pii_types already could.
             "entities": extract_entities(c.get("text", "")) or None}
            for c in chunks if c.get("chunk_type") != "text"
        ],
        # Full, unchunked video transcript (empty/absent for non-video
        # uploads or a silent/failed-audio video) — for reading end-to-end
        # in the summary view and downloading, separate from the chunked
        # copy used for retrieval.
        "transcript": transcript_text or None,
        "transcript_segments": transcript_segments,
        # Auto-generated chapter markers (empty for non-video uploads, a
        # short/silent transcript, or if the one extra LLM call failed —
        # never blocks ingestion on this being unavailable).
        "chapters": chapters,
    }
