"""Meeting / Call Intelligence Assistant (MMRAG-21, lean scope).

Almost entirely orchestration of pieces that already exist and are proven live:
  - transcribe_video() (mm_video_audio, via mm_video): ffmpeg -> Groq Whisper,
    chunked for any length, AND runs speaker diarization (assign_speakers,
    Gemini) so the returned segments already carry a "speaker" label.
  - generate_chapters(): one LLM pass over the timestamped transcript -> topic
    markers, reused here as the meeting agenda.

The only genuinely new work is one structured extraction pass — summary,
decisions, action items — over the speaker-labelled transcript, plus per-speaker
talk-time arithmetic. Same fixed-server-key + budget + best-effort-JSON pattern
as routers/siem_triage.py. Extraction is instructed to never invent a decision
or action item that was not actually stated.

Lean scope: synchronous (a spinner on the client), best on clips up to ~10
minutes. The per-route body cap for /rag/mm-meeting is raised in
security/body_size.py so a real recording fits.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from security.rate_limit import limiter, LLM_LIMIT
from security.budget import check_and_record_call
from security.file_gate import scan_upload_bytes
from routers.rag.llm import complete
from routers.rag.query_helpers import _resolve_key
from routers.rag.mm_video import generate_chapters, transcribe_video

logger = logging.getLogger(__name__)
router = APIRouter()

# Same cascade the other public LLM tools use: cohere leads (free + reliable),
# mistral is the second opinion. No gemini — it is the only paid key.
_CANDIDATES = [("cohere", "command-a-03-2025"), ("mistral", "mistral-small-latest")]
_MAX_TRANSCRIPT_CHARS = 12000  # bound the extraction prompt (~a 10-min meeting)

_MEETING_SYSTEM = (
    "You are a meeting-notes assistant. You are given a speaker-labelled "
    "transcript of a meeting or call. Produce concise, faithful notes. Only "
    "include a decision or action item if it is ACTUALLY stated in the "
    "transcript — never invent one, and never guess an owner or due date that "
    "was not said. Reply with ONLY JSON, no other text: {\"summary\": \"<2-4 "
    "sentence plain summary>\", \"decisions\": [\"<decision>\", ...], "
    "\"action_items\": [{\"text\": \"<what needs doing>\", \"owner\": \"<who, "
    "or empty string>\", \"due\": \"<when, or empty string>\"}, ...]}. Use an "
    "empty list for a category with nothing in it."
)


def _speaker_transcript(segments: list[dict]) -> str:
    """One line per segment: '[mm:ss] Speaker N: text' — the human-readable
    transcript shown to the user and fed (capped) to the extractor."""
    lines = []
    for s in segments:
        t = int(s.get("start", 0))
        who = s.get("speaker") or ""
        prefix = f"[{t // 60:02d}:{t % 60:02d}] "
        prefix += f"{who}: " if who else ""
        lines.append(prefix + (s.get("text") or "").strip())
    return "\n".join(lines)


def _extract(transcript: str) -> dict:
    """Summary / decisions / action items via the fixed-server-key cascade.
    Returns safe empty fields if every provider fails or the output is
    unparseable — the transcript, agenda and talk-time still stand on their own."""
    empty = {"summary": "", "decisions": [], "action_items": []}
    body = transcript[:_MAX_TRANSCRIPT_CHARS]
    for provider, model in _CANDIDATES:
        key = _resolve_key(provider, None)
        if not key:
            continue
        try:
            raw = complete(provider, model, key,
                           [{"role": "user", "content": body}], system=_MEETING_SYSTEM)
        except Exception as exc:
            logger.warning("mm-meeting extract: %s failed: %s", provider, exc)
            continue
        parsed = _parse(raw)
        if parsed is not None:
            return parsed
        logger.warning("mm-meeting extract: %s returned unparseable output", provider)
    return empty


def _parse(raw: str) -> dict | None:
    if not raw:
        return None
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict):
        return None
    decisions = [str(x).strip() for x in (d.get("decisions") or []) if str(x).strip()]
    items = []
    for it in (d.get("action_items") or []):
        if isinstance(it, dict) and str(it.get("text", "")).strip():
            items.append({
                "text": str(it["text"]).strip(),
                "owner": str(it.get("owner", "")).strip(),
                "due": str(it.get("due", "")).strip(),
            })
    return {"summary": str(d.get("summary", "")).strip(), "decisions": decisions, "action_items": items}


def _transcribe(raw: bytes, filename: str) -> list[dict]:
    """Bytes -> speaker-labelled segments (transcribe_video runs Whisper +
    diarization). The long, blocking step; run in an executor from the stream."""
    suffix = os.path.splitext(filename)[1] or ".mp3"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(raw)
    tmp.close()
    try:
        _chunks, _count, _text, segments = transcribe_video(tmp.name, "meeting")
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    return segments


def _talk_time(segments: list[dict]) -> list[dict]:
    talk: dict[str, float] = {}
    for s in segments:
        spk = s.get("speaker") or "Unknown"
        talk[spk] = talk.get(spk, 0.0) + max(0.0, float(s.get("end", 0)) - float(s.get("start", 0)))
    return sorted(
        [{"label": k, "talk_seconds": round(v, 1)} for k, v in talk.items()],
        key=lambda x: -x["talk_seconds"],
    )


def analyze_meeting(raw: bytes, filename: str) -> dict:
    segments = _transcribe(raw, filename)
    if not segments:
        return {"ok": False, "error": "Could not transcribe any speech from this file."}
    transcript = _speaker_transcript(segments)
    extraction = _extract(transcript)
    return {
        "ok": True,
        "summary": extraction["summary"],
        "decisions": extraction["decisions"],
        "action_items": extraction["action_items"],
        "topics": [{"title": c.get("label", ""), "timestamp": int(c.get("time", 0))}
                   for c in generate_chapters(segments)],
        "speakers": _talk_time(segments),
        "transcript": transcript,
        "duration_seconds": int(segments[-1].get("end", 0)),
    }


@router.post("/mm-meeting")
@limiter.limit(LLM_LIMIT)
async def meeting_endpoint(request: Request, file: UploadFile = File(...)):
    raw = await file.read()
    scan_upload_bytes(raw, path="/rag/mm-meeting")
    check_and_record_call("mm-meeting", pool="mm_meeting", daily_cap_env="MM_MEETING_DAILY_CAP")
    return analyze_meeting(raw, file.filename or "meeting")


# ── Streaming variant: SSE progress for long meetings ──
# Emits a step event per phase so the client shows live progress, and — crucially
# for a long clip — keeps producing bytes so the transcription phase doesn't sit
# idle long enough to trip the proxy's timeout. The one long blocking step
# (transcription) runs in an executor while the generator emits heartbeats until
# it finishes. Same result payload as the sync endpoint, in the final "done" event.
_executor = ThreadPoolExecutor(max_workers=2)
_HEARTBEAT_S = 10


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _meeting_stream(raw: bytes, filename: str):
    loop = asyncio.get_event_loop()
    yield _sse({"step": "transcribe", "status": "running"})
    fut = loop.run_in_executor(_executor, _transcribe, raw, filename)
    while not fut.done():
        try:
            await asyncio.wait_for(asyncio.shield(fut), timeout=_HEARTBEAT_S)
        except asyncio.TimeoutError:
            yield _sse({"step": "transcribe", "status": "running", "heartbeat": True})
    try:
        segments = fut.result()
    except Exception as exc:
        logger.warning("mm-meeting stream: transcription failed: %s", exc)
        yield _sse({"error": "Transcription failed — try a shorter or cleaner clip."})
        return
    if not segments:
        yield _sse({"error": "Could not transcribe any speech from this file."})
        return
    yield _sse({"step": "transcribe", "status": "done"})

    speakers = _talk_time(segments)
    transcript = _speaker_transcript(segments)

    yield _sse({"step": "agenda", "status": "running"})
    topics = await loop.run_in_executor(
        _executor,
        lambda: [{"title": c.get("label", ""), "timestamp": int(c.get("time", 0))}
                 for c in generate_chapters(segments)],
    )
    yield _sse({"step": "agenda", "status": "done"})

    yield _sse({"step": "extract", "status": "running"})
    extraction = await loop.run_in_executor(_executor, _extract, transcript)
    yield _sse({"step": "extract", "status": "done"})

    yield _sse({"step": "done", "result": {
        "ok": True,
        "summary": extraction["summary"],
        "decisions": extraction["decisions"],
        "action_items": extraction["action_items"],
        "topics": topics,
        "speakers": speakers,
        "transcript": transcript,
        "duration_seconds": int(segments[-1].get("end", 0)),
    }})


@router.post("/mm-meeting/stream")
@limiter.limit(LLM_LIMIT)
async def meeting_stream_endpoint(request: Request, file: UploadFile = File(...)):
    raw = await file.read()
    scan_upload_bytes(raw, path="/rag/mm-meeting/stream")
    check_and_record_call("mm-meeting", pool="mm_meeting", daily_cap_env="MM_MEETING_DAILY_CAP")
    return StreamingResponse(_meeting_stream(raw, file.filename or "meeting"),
                             media_type="text/event-stream")


# ── Transcript Q&A ──
# The client already holds the transcript from /mm-meeting, so it posts that back
# with a question rather than re-transcribing. Answered strictly from the
# transcript, with its own budget pool so questions don't drain the analyse cap.
_QA_SYSTEM = (
    "You answer a question about a meeting using ONLY the transcript provided. "
    "If the answer is not in the transcript, say you couldn't find it in the "
    "meeting — do not guess. Be concise (1-3 sentences) and never invent a name, "
    "date, number or commitment that is not in the transcript."
)
_MAX_QA_TRANSCRIPT = 14000
_MAX_QUESTION = 400


class MeetingAskRequest(BaseModel):
    transcript: str
    question: str


@router.post("/mm-meeting/ask")
@limiter.limit(LLM_LIMIT)
def meeting_ask(request: Request, req: MeetingAskRequest):
    check_and_record_call("mm-meeting-ask", pool="mm_meeting_qa", daily_cap_env="MM_MEETING_QA_DAILY_CAP")
    question = (req.question or "").strip()[:_MAX_QUESTION]
    transcript = (req.transcript or "").strip()[:_MAX_QA_TRANSCRIPT]
    if not question or not transcript:
        return {"ok": False, "error": "Both a question and a transcript are required."}
    content = f"TRANSCRIPT:\n{transcript}\n\nQUESTION: {question}"
    for provider, model in _CANDIDATES:
        key = _resolve_key(provider, None)
        if not key:
            continue
        try:
            raw = complete(provider, model, key,
                           [{"role": "user", "content": content}], system=_QA_SYSTEM)
        except Exception as exc:
            logger.warning("mm-meeting ask: %s failed: %s", provider, exc)
            continue
        if raw and raw.strip():
            return {"ok": True, "answer": raw.strip()}
    return {"ok": False, "error": "Couldn't get an answer just now — try again in a moment."}
