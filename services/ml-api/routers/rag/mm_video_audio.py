"""Audio extraction + Whisper transcription + LLM chaptering for video ingestion
— split out of mm_video.py to stay under the project's file-length limit. Reuses
Groq's Whisper endpoint (whisper-large-v3-turbo), same GROQ_API_KEY server secret
used elsewhere in this codebase, no new credential surface. ffmpeg (already a system
dependency) extracts audio to WAV first. Extraction and transcription fail silently
(never raise) — a video with no/failed audio just yields no transcript chunks.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess

logger = logging.getLogger(__name__)

_TRANSCRIBE_MODEL = "whisper-large-v3-turbo"

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


_CHUNK_WORD_SIZE = 450  # matches chunk_document()'s default chunk_size


def _chunk_segments_with_speakers(segments: list[dict], source: str) -> list[dict]:
	"""Groups consecutive timestamped segments into word-count-bounded
	chunks, prefixing each segment's text with its speaker label when
	known — carries the "who said what" signal into retrieval, instead of
	a flat, speaker-agnostic slice of the transcript."""
	chunks: list[dict] = []
	parts: list[str] = []
	words = 0
	for seg in segments:
		piece = f"{seg['speaker']}: {seg['text']}" if seg.get("speaker") else seg["text"]
		parts.append(piece)
		words += len(piece.split())
		if words >= _CHUNK_WORD_SIZE:
			chunks.append({"text": " ".join(parts), "source": source, "chunk_index": len(chunks)})
			parts, words = [], 0
	if parts:
		chunks.append({"text": " ".join(parts), "source": source, "chunk_index": len(chunks)})
	return chunks


def transcribe_video(video_path: str, source: str) -> tuple[list[dict], int, str, list[dict]]:
	"""Extract + transcribe the audio track. Retrieval chunks are built from
	the timestamped, speaker-labeled segments (not a flat re-chunk of the
	transcript string) so the LLM's context carries "who said what," the
	same signal the frontend's transcript view already shows. Also returns
	the full unchunked transcript and its segments for display/download.
	Returns
	(chunks, chunk_count, transcript_text, segments); all empty if there's
	no audio or transcription failed — callers should treat that as
	"visual-only," not an error."""
	wav_path = video_path + ".wav"
	if not _extract_audio_wav_to_file(video_path, wav_path):
		return [], 0, "", []

	try:
		transcript, segments = _transcribe_long_audio(wav_path)
		if segments:
			# Enhancement, not a requirement — adds a "speaker" key to each
			# segment in place. Runs before cleanup, on the SAME full wav
			# (not the per-chunk splits _transcribe_long_audio already
			# deleted) so diarization sees the entire recording at once.
			from routers.rag.mm_diarize import assign_speakers
			assign_speakers(segments, wav_path)
	finally:
		try:
			os.unlink(wav_path)
		except OSError:
			pass

	if not transcript.strip():
		return [], 0, "", []

	# Built from `segments` (with speaker prefixes), NOT chunk_document() on
	# the flat `transcript` string — a flat chunk carries no speaker info at
	# all, so the LLM answering a chat question never saw who said what,
	# only the frontend's transcript panel did (a real, separate gap from
	# the visual-identity confusion citations.py now also guards against —
	# this one specifically means "only one speaker throughout" is a signal
	# the model could use but previously never received).
	chunks = _chunk_segments_with_speakers(segments, source)
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
