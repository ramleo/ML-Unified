"""Speaker diarization for video transcripts — reuses Gemini's native audio
understanding (already an integrated provider, GEMINI_API_KEY already
trusted elsewhere in this codebase) instead of a dedicated diarization
model. No new dependency, no gated Hugging Face model/license/token.

A pure enhancement layered onto the existing Whisper transcript, not a
replacement for it: Whisper's segments (already tested for chunking past
its own size cap, already proven accurate) stay the source of truth for
text/timestamps; this only adds a "speaker" label to each one, based on
which of Gemini's independently-diarized time intervals it falls into.
Fails silently at every step — never blocks ingestion.
"""
from __future__ import annotations

import base64
import json
import logging
import os

logger = logging.getLogger(__name__)

_DIARIZE_MODEL = "gemini-3.6-flash"
_MAX_DIARIZE_BYTES = 20 * 1024 * 1024  # keep this one-shot call bounded —
                                       # unlike Whisper, this isn't chunked
                                       # for larger files; skip rather than
                                       # risk a slow/expensive call


def _diarize_with_gemini(wav_path: str) -> list[dict]:
    """One Gemini call over the raw audio. Returns a list of
    {"start": seconds, "end": seconds, "speaker": "Speaker N"} — Gemini's
    own diarization intervals, independent of Whisper's segment boundaries.
    Empty list on any failure, missing key, or an oversized file."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key or os.path.getsize(wav_path) > _MAX_DIARIZE_BYTES:
        return []
    try:
        with open(wav_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        prompt = (
            "Transcribe this audio with speaker diarization. Identify each "
            'distinct speaker as "Speaker 1", "Speaker 2", etc. Return JSON '
            'only: {"segments": [{"start": <seconds>, "end": <seconds>, '
            '"speaker": "Speaker N"}]}. Cover the entire audio.'
        )
        parts = [{"inline_data": {"mime_type": "audio/wav", "data": b64}}, {"text": prompt}]
        import httpx
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{_DIARIZE_MODEL}:generateContent"
        with httpx.Client(timeout=90) as client:
            r = client.post(url, params={"key": key}, json={"contents": [{"role": "user", "parts": parts}]})
            r.raise_for_status()
            raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            start, end = raw.find("{"), raw.rfind("}") + 1
            data = json.loads(raw[start:end])
            return data.get("segments", [])
    except Exception as exc:
        logger.warning("Diarization failed: %s", exc)
        return []


def assign_speakers(segments: list[dict], wav_path: str) -> None:
    """Mutates each Whisper segment in place, adding a "speaker" key —
    whichever of Gemini's diarized intervals its midpoint falls closest
    to. No-op (segments unchanged) if diarization returns nothing."""
    diarized = _diarize_with_gemini(wav_path)
    if not diarized:
        return
    for seg in segments:
        mid = (seg["start"] + seg["end"]) / 2
        best = min(diarized, key=lambda d: abs((d.get("start", 0) + d.get("end", 0)) / 2 - mid))
        seg["speaker"] = best.get("speaker")
