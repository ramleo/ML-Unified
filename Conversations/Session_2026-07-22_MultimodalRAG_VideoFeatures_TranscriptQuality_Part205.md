# Session 2026-07-22/24 — Video Feature Backlog: Chapters, Search, Playback, Diarization, Transcript-Quality Fixes (Part205)

Continuation after Part 204. Picked up mid-debug on a real frame-seeking bug in
video ingestion, root-caused it fully, then worked through a user-prioritized
backlog of five video features one at a time — building, deploying, and
verifying each against the user's own real test file before moving to the
next — and closed with two real transcript-quality bugs found live.

---

## 1. Frame-seeking bug — root-caused with real evidence, not guesswork

User reported three "VIDEO FRAME" citations on their real UN-speech video with
**word-for-word identical captions**, despite an earlier fix (timestamp-based
seeking) supposedly already addressing duplicate frames. User explicitly
rejected two premature debugging attempts (pulling noisy full-Space logs) and
asked "what will you do differently this time" — the process correction from
earlier sessions held: no action without a plan stated first.

Real diagnosis, in order:
1. `ffprobe` on the actual file confirmed clean metadata (416 frames, 30fps,
   ~13.87s) — ruled out corrupt-file theories.
2. Ran the exact seeking logic **locally** against the real file — got 6
   genuinely distinct frame hashes. The fix itself was correct.
3. Uploaded the SAME file to the **deployed** Space and hashed the returned
   `page_images` — also 6 distinct hashes. Confirmed: not a seeking bug at
   all anymore.
4. The real explanation: the speaker stands almost motionless for the whole
   clip — frames are genuinely different images, but visually similar enough
   that a vision model naturally writes near-identical captions for them.
   Not a bug; an inherent limit of sampling static video.

## 2. Backlog picked up in strict order, one item built+verified before the next

User: "proceed in order." Five items, from an earlier brainstorm:

1. **Auto-generated chapters** — one LLM call over the full timestamped
   transcript produces up to 6 chapter markers (`{"time", "label"}`), like
   YouTube auto-chapters. Fails silently (empty list) on too little content
   or a failed call. Clickable chips jump to and highlight the nearest
   transcript segment.
2. **Citation → transcript deep-linking** *(actually built the session
   before this one, but exercised again here)* — a transcript-chunk citation
   auto-opens the summary panel and highlights the closest-matching segment
   (word-overlap scoring, since retrieval chunks don't align exactly with
   Whisper's own segment boundaries).
3. **In-transcript keyword search** — fully client-side: a search box
   highlights every match inline (`<mark>`), with up/down navigation and
   auto-scroll to the current match. No backend change.
4. **Speaker diarization** — see section 3 below; user initially deferred
   this (gated HF model friction), it came back later via a smarter
   alternative.
5. **Video playback with click-to-seek** — real design decision, flagged
   before building: this requires keeping the uploaded video's raw bytes in
   memory (small cap, evicted on document removal, never written to disk),
   a change from "the original file is never saved." New `mm_video_store.py`
   serves the video with **HTTP Range support** (verified live: a `Range:
   bytes=0-1023` request correctly returned `206 Partial Content` with
   proper `Content-Range`/`Accept-Ranges` headers — required for browser
   seeking, not just playback). Clicking any transcript line, chapter, or
   citation now seeks an actual `<video>` element, verified visually via
   Playwright screenshot (timer moved from 0:00 to 0:08 on a chapter click,
   matching segment highlighted simultaneously).

Each item required its own file-length management: `MmRagRunner.tsx` crossed
400 lines building chapters, so the whole document-summary/transcript block
was extracted into a new `DocumentSummaryPanel.tsx` (routine split, not a new
feature). `mm_ingest.py` crossed 400 lines twice more building video-store
support, requiring extraction of standalone-image captioning into a new
`mm_image.py` (mirroring the existing `mm_csv.py`/`mm_pdf.py`/`mm_video.py`
per-concern module pattern).

Commits: ML-Unified `fed2109`(chapters) `f7e2eb4`(video store+mm_image split);
portfolio `3b57384`(chapters) `fd15e54`(search) `50e44c5`(playback).

## 3. Speaker diarization — deferred, then solved via a smarter alternative

Initially flagged as the highest-friction item: the best open model
(`pyannote/speaker-diarization-3.1`) is **gated** on Hugging Face — requires
a human to manually accept the license on their own HF account and add an
`HF_TOKEN` secret; nothing code can do around that. User chose to skip it and
build #5 instead.

Later, user asked for alternatives. First pass of suggestions (AssemblyAI,
Deepgram, NVIDIA NeMo) all still traded one friction for another (new paid
account, or a much heavier dependency) — user pushed back: **"are you sure
there isn't a good alternative?"** Re-checked, found the actual best fit:
**Gemini's native multimodal audio understanding already supports speaker
diarization directly** (per Google's own docs) — zero new dependency, zero
new account, since Gemini is already an integrated provider in this codebase
with a working key. This was a real miss in the first-pass answer, corrected
only because the user asked a second time rather than accepting "no good
option" at face value.

Built as a pure enhancement layered onto the existing (already-proven)
Whisper transcript, not a replacement: new `mm_diarize.py` sends the
extracted audio to Gemini once, gets back independently-diarized time
intervals, and assigns a `"speaker"` label to each Whisper segment by
nearest-interval match. Verified with two real test videos:
- The user's real single-speaker video → consistently "Speaker 1" throughout.
- A synthetic two-voice conversation (macOS `say -v Samantha` / `say -v
  Fred`, alternating lines) → correctly diarized as alternating "Speaker
  1"/"Speaker 2" in sync with the actual alternating voices.

Speaker labels now show in the transcript view and in `.srt` exports.
Commit: ML-Unified `467a122`; portfolio `f3b7136`.

## 4. Two more real bugs found live, after the backlog was "done"

**Bug A — visual identity confusion.** User: chat said "the document
describes two men," despite the video showing only one. Root cause, visible
directly in the citations: two independently-captioned video frames of the
same speaker used different wording (one mentioned the pocket square, the
other the gray hair/beard) — with no cross-frame identity link, the LLM
reasonably read two differently-worded descriptions as two different people.
Fixed in `citations.py`: a conditional system-prompt note fires whenever a
single source contributes 2+ video/figure/image chunks, explaining they're
likely the same subject at different moments and not to assume multiple
people from wording differences alone — without assuming away genuinely
multi-subject content. Verified: re-asked "how many men are there?" on the
same real video → "There is one man." Commit: ML-Unified `20734b1`.

**Bug B — speaker signal never reached the LLM.** User, immediately after
Bug A's fix: pointed out the transcript already showed "Speaker 1" throughout
— could that have helped? Checked and found a real, separate gap: retrieval
chunks for the transcript were built via `chunk_document()` on the *flat*
transcript string, which carries zero speaker info — diarization's labels
only ever reached the frontend's transcript panel, never the chunks the LLM
actually reads to answer chat questions. Fixed by replacing that with
`_chunk_segments_with_speakers()`, building chunks directly from the
timestamped, speaker-labeled segments (prefixing each with `"Speaker N: "`
when known) instead of a speaker-agnostic re-chunk. Verified live: the
transcript chunk sent to the LLM now literally reads `"Speaker 1: have been
rolled back, Speaker 1: resources for sustainable development..."` throughout.
Commit: ML-Unified `d9eab49`.

## 5. Key lessons reinforced

- **A user asking "are you sure?" a second time is real signal, not
  friction.** The first pass of diarization alternatives was genuinely
  incomplete — Gemini's built-in audio diarization was sitting in the same
  codebase's own provider list and got missed until pushed on directly.
- **"No good alternative" should be a last resort, not a first answer** —
  worth explicitly re-checking what's *already integrated* before concluding
  external options are the only path.
- **A fix for one symptom doesn't mean the underlying signal actually reached
  the model** — Bug A's citations.py fix addressed the *visual* half of "how
  many people," but the *transcript* half of the same signal (consistent
  speaker labeling) was independently broken and needed its own fix. Worth
  checking both directions when a "the model is confused about identity"
  bug surfaces, not just the first plausible cause found.
- **Debug discipline held under real pressure.** Two tool-use rejections and
  explicit "why are you guessing" style pushback this session were both
  followed by stating a concrete, falsifiable plan before acting again —
  consistent with the standing rule from earlier sessions.
