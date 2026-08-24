# Session Part 213 — 2026-07-28/29

## Context
Continued from Part 212 (groundedness bugs, MMRAG-08 trace panel, guide
search). This session worked through the MMRAG backlog in order —
MMRAG-09 through MMRAG-12 — asking "give list of MMRAG completed and
pending" first, then "proceed with mmrag N" for each. A recurring pattern
emerged: several backlog items turned out to be partially or fully already
built before this session touched them, so each item started with a code
investigation before writing anything, not an assumption the row's
description was still an accurate gap.

## MMRAG-09 — Temporal moment retrieval for video (timestamp + jump-to)

Investigation found most of "temporal moment retrieval" already built:
transcript-based citation click-to-seek, clickable chapter markers, .srt
export, speaker diarization, and a "most re-watched moments" heatmap all
already worked. The actual gap was narrow: a citation for a captioned
**video frame** (a visual-only chunk — e.g. "what's on the whiteboard",
nothing spoken) stored only a 1-6 sample index (`page`), not a real
timestamp — clicking it just showed a static thumbnail, never opened the
video or seeked anywhere.

- Backend: `mm_video.py::process_frame` now stores `timestamp_s` (real
  seconds) on each frame chunk. Threaded through the same places MMRAG-08
  established a pattern for: Chroma metadata (`ingest.py`), both
  `dense_retrieve`/`bm25_retrieve` (`retrieve.py`), `build_source_doc`
  (`citations.py`).
- Frontend: `MmRagRunner.tsx`'s `jumpToCitation` gained a
  `chunkType === "video"` branch seeking the video via a new `videoSeek`
  state, parallel to the existing `highlightedSegment` state for
  transcript citations. `DocumentSummaryPanel.tsx` takes a new `seekTime`
  prop with an effect setting `videoRef.current.currentTime = seekTime`.
- Bug caught before shipping: the seek effect must check
  `seekTime === null`, not falsy — frame 1 is legitimately at
  `timestamp_s: 0.0`.
- Housekeeping: `mm_ingest.py` was already at 392 lines (over the
  project's 350-line threshold) before this session touched it —
  modularized as a prerequisite, extracting the tiny ingestion cache and
  the "done" SSE payload builder into `mm_ingest_cache.py` /
  `mm_ingest_payload.py`, landing at 314 lines.
- **Verified live**: uploaded the real test video, asked a visual-only
  question, got two Video Frame citations (p.1 @ 0.0s, p.2 @ 6.9s).
  Clicking each confirmed via `document.querySelector('video').currentTime`
  in the live deployed page: exactly 6.9, then exactly 0.
- **Bug report mid-session**: user reported "nothing is happening" on a
  real click, screenshot showed the summary panel still collapsed. Fresh
  reproduction with the exact same question worked correctly — root-caused
  as a stale browser tab (loaded before the Vercel deploy propagated),
  confirmed by grepping the live JS bundle for a marker string. Advised a
  hard refresh.
- Commits: ML-Unified `36692c7`; ml-portfolio `ad2e349`.

## MMRAG-10 — Speaker diarization

Checked the code before building anything — already fully done from an
earlier, undocumented-in-the-backlog-row session: `mm_diarize.py` (Gemini
native audio diarization), wired into `mm_video.py::transcribe_video`,
speaker labels already shown in the transcript panel and `.srt` export,
already documented in the user guide. Confirmed actually working (not
just present) via this session's own earlier live ingest test, which
already returned `"speaker": "Speaker 1"` on every segment. No code
changes — just marked done in the backlog memory.

## MMRAG-11 — FFT-based scene-cut detection for frame sampling

Genuinely unbuilt. Previous frame sampling was blind uniform time-spacing
— wasteful for a video with real scene changes (6 evenly-spaced frames of
a 2-scene video mostly repeat the same shot).

- New `mm_scenecut.py`: probes the video at a coarse cadence (0.5s,
  capped at 40 probes), computes a 2D FFT log-magnitude spectrum per probe
  (64×64 grayscale, cheap), compares consecutive probes' spectra by L2
  distance. If the largest distance isn't at least 2× the median, there's
  no real cut — falls back to the original uniform spacing untouched.
  Otherwise takes the largest-distance timestamps (min-gap-enforced) as
  sample points, topping up any remaining budget with uniform spacing.
  Frequency-domain (not raw pixel diffing) for the same reason as the
  existing blur-quality check (MMRAG-01) — robust to camera shake/
  compression noise a pixel diff would misflag as a cut.
- `mm_video.py::process_frame` refactored to take an explicit
  `timestamp_s` instead of deriving one from a frame-index/uniform-count
  ratio, so the caller can supply either uniform or scene-cut timestamps.
- **Verified live, fallback path only**: re-ingested the same static
  talking-head test video — zero errors, timestamps identical to the
  pre-MMRAG-11 uniform output (0.0s, 6.9s), confirming the fallback branch
  works end-to-end. The actual cut-detection branch is implemented and
  code-reviewed but **not exercised by a real multi-scene video** — no
  such fixture was available this session. Recorded as an honest gap in
  memory, not overclaimed as fully proven.
- Commits: ML-Unified `b1591ea`; ml-portfolio `6a32ceb` (guide only).

## MMRAG-12 — Multilingual Q&A

User asked what languages are supported before this was built; answered
that nothing was implemented yet, offered to check current behavior
first — user said proceed.

Live-tested a real Hindi question ("दीवार किस रंग की है?") against the
real uploaded video **before writing any code**: Groq's llama-3.3-70b
already answered correctly in Hindi, translating the English source
caption on its own, unprompted. So "answer in the asker's language" was
not actually broken.

- Added an explicit system-prompt instruction anyway
  (`citations.py::build_system_prompt`) — cheap, guards against the other
  two fallback providers (Mistral/Gemini) not mirroring language as
  reliably.
- **Real bug found by testing, not guessed**: that same correct Hindi
  answer scored groundedness **0.185 — "Low," flagged unsupported**.
  Root cause: `groundedness.py` embeds answer/source sentences with the
  retrieval embedder (all-MiniLM-L6-v2, English-centric) — cross-script
  similarity comes out unreliably low even for an accurate translation.
  Fixed by detecting an answer/source script mismatch (mostly non-ASCII
  answer letters vs. mostly-ASCII source) and returning `None` — same as
  "nothing to score" — instead of a confidently wrong badge.
- Second bug in the same pass: `_split_sentences`'s regex only split on
  `.!?` — a multi-sentence Hindi/Chinese/Arabic answer (ending in
  `।`/`。`/`؟`) collapsed into one giant "sentence" for embedding, the
  same dilution failure already fixed for chunk text in Part 212's
  groundedness work, now on the answer side. Extended the regex to
  include `।؟。！？`, using `\s*` not `\s+` since CJK text often has no
  space after its terminator.
- Known gap, scoped out: `likely_used_indices` (the "directly cited" vs.
  "additional context" citation split) uses literal n-gram word overlap,
  which also silently returns nothing for a non-English answer against
  English chunks. Degrades gracefully (one flat citation list, not a
  crash) — left unfixed, documented in memory.
- **Verified live**: Hindi question, fresh session (first attempt hit a
  session that expired mid-HF-Space-rebuild) — correct answer,
  `"groundedness": null` confirmed in the raw SSE response.
- User then asked to also test Telugu live: "గోడ ఏ రంగులో ఉంది?" →
  "గోడ ఆకుపచ్చ రంగులో ఉంది." (correct — "the wall is green"),
  `groundedness: null` confirmed again, same script-mismatch logic
  (not a hardcoded language list) covering it automatically.
- User asked "why groundedness: null" and "what languages are
  supported" as follow-ups — answered directly: no fixed language list
  for the answer-language behavior (bounded only by the LLM's own
  ability); the groundedness-skip is a non-ASCII-script check, verified
  for Hindi/Telugu, unverified for Latin-script non-English languages
  (Spanish/French/German etc. wouldn't trigger the skip at all).
- Then asked to update the user guide to explain `groundedness: null`
  explicitly — added a clearer, more prominent explanation to both the
  "Groundedness score" bullet and the "Ask in your own language" bullet,
  including a plain-English note that null is "we chose not to guess,"
  not a bug. One edit briefly broke the guide's TypeScript syntax (a
  backtick inside the backtick-delimited template literal closed it
  early) — caught immediately via `tsc --noEmit`, fixed by removing the
  inline backtick-quoted code span.
- Commits: ML-Unified `31aa3b2`; ml-portfolio `b38ba3e`, `361f025`.

## Housekeeping note (flagged, not fixed)
`userGuide.ts` was already at 416 lines (over the 350-line threshold)
before this session's edits, now at 486 — a single markdown-content
string constant, not logic. Flagged directly to the user rather than
silently splitting it or silently ignoring the rule; no action taken
without an explicit request.

## Commit summary

| Repo | Commit | What |
|---|---|---|
| ML-Unified | `36692c7` | MMRAG-09 backend — timestamp_s on video-frame chunks |
| ml-portfolio | `ad2e349` | MMRAG-09 frontend — video-frame citation jump-to-seek |
| ML-Unified | `b1591ea` | MMRAG-11 — FFT scene-cut detection for frame sampling |
| ml-portfolio | `6a32ceb` | MMRAG-11 — user guide doc |
| ML-Unified | `31aa3b2` | MMRAG-12 — multilingual prompt instruction + groundedness script-mismatch fix |
| ml-portfolio | `b38ba3e` | MMRAG-12 — user guide doc |
| ml-portfolio | `361f025` | MMRAG-12 — clarify groundedness null in guide |

(MMRAG-10: no commits — confirmed already fully built/live/documented,
backlog memory updated only.)

## Pending / next candidates
- MMRAG-13 (region-level captioning), MMRAG-14 (chart data extraction),
  MMRAG-15 (face redaction), MMRAG-16 (near-duplicate frame detection —
  now largely covered by MMRAG-11's scene-cut work, worth checking first
  before building), MMRAG-17 (denoising for scans), MMRAG-18 (analytics
  FFT), MMRAG-19 (confidence/hesitation cues), MMRAG-20/21 (product
  pivots) remain unbuilt — see `project_mmrag_feature_backlog.md` in
  Claude's memory store.
- MMRAG-11's scene-cut-detection branch (as opposed to its fallback) is
  unverified against a real multi-scene video — worth testing with one
  if/when available.
- `userGuide.ts`'s file length (486 lines, pre-existing over-threshold
  growth) — flagged, not actioned.
