# Session Part 214 — 2026-07-29

## Context
Continued from Part 213 (MMRAG-09 through MMRAG-12). This session finished
the MMRAG-13/14 backlog items, investigated MMRAG-15 and found the
premise it was scoped against doesn't currently exist, and built a new
small feature (an explicit "Detect faces" button) that came out of that
investigation but is deliberately NOT the same thing as MMRAG-15.

## MMRAG-13 — Region-level captioning (finished + a real follow-up bug)

Built and deployed: PDF pages with 2+ distinct large raster regions (e.g.
a chart AND an unrelated logo) now get one focused caption per region
instead of one blended whole-page caption. `mm_pdf.py::_visual_regions`
finds/dedupes/caps qualifying regions; `citations.py`'s "these visuals
are probably the same subject" caveat was re-keyed on distinct PAGE
numbers (not raw chunk count), since same-page regions from this feature
are deliberately distinct, not ambiguous. Verified live with a synthetic
2-region test PDF (bar chart + logo) — 2 correctly separated captions.

**User-driven follow-up, same day**: user pointed out their resume's
career timeline (a row of ~6 small company logos) wasn't captioned at
all. Investigated the real file directly — confirmed each logo
individually measured only ~0.6-1.2% of the page, below the
single-image area threshold, so the whole timeline was silently
invisible (neither text-extractable nor large enough to caption).
Fixed by clustering nearby raster images (any size) into one region when
either a qualifying big image is present or ≥3 small ones are grouped
within a gap threshold.

**A regression caught and fixed BEFORE reporting success**: the first
clustering version ran as two separate passes (small images clustered
among themselves, excluded only if directly overlapping a big region) —
tested against the real resume and found it wrongly split the donut
chart and its adjacent skill-icon column (21pt apart, one "Soft Skills"
section) into two separate captions. Root-caused to two bugs: (1) two
separate passes instead of one unified clustering pass over every raster
image regardless of size, (2) an expand-one-side-then-intersect gap check
that only tolerated half the intended threshold (a real 21pt gap missed a
nominal 20pt setting). Fixed both, re-verified: page 1 (donut + icons)
back to 1 correct caption, page 2 (timeline) now correctly captioned
("career timeline lists job roles, companies, and corresponding
employment dates from July 2006 to December 2025") — previously zero
figure chunks there at all.
Commits: ML-Unified `67a7ecd`, `0d67489`; ml-portfolio `e88526e`, `a0bfaaa`.

## MMRAG-14 — Chart data extraction (actual numeric values)

Confirmed genuinely unbuilt by direct code search (no structured
chart-data extraction existed, only prose captions + OCR text). Built:
the SAME vision call that produces a figure's caption now also asks for
the chart's actual [category, value] rows via a richer JSON schema — no
extra vision call. Extracted values land in their own `chunk_type:
"table"` chunk, reusing RagTableView.tsx's existing CSV-download/
mini-bar-chart-plot UI for free. `build_table_markdown()` (renamed from
mm_pdf.py's private `_table_markdown`) moved to the shared `mm_caption.py`
so both `mm_pdf.py` (PDF figures) and `mm_image.py` (standalone images)
can use it. Local unit tests confirmed `extract_chart_data()` handles a
clean case, a non-chart case, and a truncated-JSON case correctly before
any live deploy.

**Verified live with real, known ground truth**: generated a real
matplotlib bar chart with programmatically-set values (Q1: 120, Q2: 150,
Q3: 95, Q4: 210), uploaded it — extracted table was an EXACT match to
every value. Asked "what was the exact Q3 revenue?" through the real
chat — got back "$95,000" (correctly reasoning through the chart's
"in $1000s" label), grounded in the extracted number, not a paraphrase.

**Honest limitation, documented in guide + memory**: only tested against
a clean synthetic chart with printed data labels — a real chart with a
rotated/cramped axis, log scale, no data labels, or overlapping bars
hasn't been tested and could be meaningfully harder to read accurately.
Commits: ML-Unified `fa88e93`; ml-portfolio `753d2ee`, `be81bf3` (guide
+ limitation note, added after user explicitly asked for it).

## MMRAG-15 — Face detection + redaction: investigated, deliberately NOT built

Before writing any code, traced how sharing actually works
(`share.py`, `query.py`'s `redact` flag). Found: a shared-link viewer
currently sees NO images at all — `documents`/`pageImages` only ever
populate from the local uploader's OWN browser session and are never
re-served to a shared viewer; `page_images` aren't even stored
server-side today (only transient in the SSE "done" event + a
short-lived hash-keyed cache). So MMRAG-15's actual premise (protecting
a face visible via a shared link) doesn't apply yet — building
redaction now would be dead code with nothing to protect.

Asked the user how to proceed (skip / build the bigger "let shared
viewers see images too" feature / build unused redaction now). User
asked for a recommendation; recommended skip-for-now, since building
unused infrastructure goes against how this project works. User agreed
and asked to log it as a real backlog item instead of losing the
finding — added **MMRAG-22** ("Show citation images/thumbnails to
shared-session viewers, with face redaction built in") to the backlog,
with MMRAG-15's row updated to point to it rather than marked done.
No code changes for this item.

## New feature — explicit "Detect faces" button (not MMRAG-15)

User then asked, separately: independent of the sharing/redaction
question, can face detection be added as a general feature for anyone
uploading an image/video? Confirmed yes — unrelated to MMRAG-15/22,
since this is for the uploader's own use, not a third-party-sharing
privacy concern. Found the existing YOLOv8s-oiv7 object detector
(already run at ingest time for MMRAG-07) already has "Human face" as
one of its 601 classes — detection itself is already happening, free.

Asked the user to choose between (a) teaching the existing implicit
"where is X" question-matching to also recognize "face" as a generic
term, or (b) a dedicated always-visible "Detect faces" button showing
every face regardless of question. User chose (b).

Built: `CitationThumbnailPanel.tsx` gained a `showFaces` toggle and a
new `objects` prop (the FULL per-citation detection list, not just the
single question-matched one `matchedObject` already carried);
`MmRagRunner.tsx` threads `activeCitation.objects` through. Button only
renders when at least one confident "Human face" detection exists on
that specific citation — no dead button for a photo/frame with none.
No backend changes at all — purely a frontend surface over data already
being sent.

**Verified live, both the negative and positive case**: a real video
frame where the detector found only "Man"/"Clothing" (no separately
confident face detection on that frame) — button correctly stayed
hidden, confirmed via direct API check this was real detector behavior,
not a wiring bug. A real face photo (87.7% "Human face" confidence) —
button appeared, clicking it drew a correctly-positioned box with a
"Face (88%)" label. Verification hit a false alarm along the way: an
initial manual pixel-math cross-check of screenshot coordinates kept
showing "no label rendered" — traced to a bug in the verification
method itself (stale/mismatched coordinate captures across separate
tool calls), not the feature; a debug red outline + `scrollIntoView`
in the same evaluate call resolved it definitively.
Commit: ml-portfolio `0dbf9da` (feature), `637eb09` (guide).

## Commit summary

| Repo | Commit | What |
|---|---|---|
| ML-Unified | `67a7ecd` | MMRAG-13 — region-level captioning for multi-figure pages |
| ML-Unified | `0d67489` | MMRAG-13 follow-up — unified clustering, catch small-image groups (career timelines) |
| ml-portfolio | `e88526e` | MMRAG-13 — user guide doc |
| ml-portfolio | `a0bfaaa` | MMRAG-13 follow-up — user guide doc |
| ML-Unified | `fa88e93` | MMRAG-14 — chart data extraction |
| ml-portfolio | `753d2ee` | MMRAG-14 — user guide doc |
| ml-portfolio | `be81bf3` | MMRAG-14 — accuracy-limitation note in guide |
| ml-portfolio | `0dbf9da` | "Detect faces" button (frontend only) |
| ml-portfolio | `637eb09` | "Detect faces" — user guide doc |

(MMRAG-15: no commits — investigated and deliberately not built; logged
as MMRAG-22 in the backlog instead.)

## Pending / next candidates
- MMRAG-16 (near-duplicate frame detection) — likely largely covered by
  MMRAG-11's scene-cut work already; worth checking before building.
- MMRAG-17 (scan denoising), MMRAG-18 (analytics FFT), MMRAG-19
  (confidence/hesitation cues), MMRAG-20/21 (product pivots), MMRAG-22
  (shared-session images + face redaction) remain unbuilt.
- MMRAG-11's actual cut-detection branch (vs. its fallback) still
  unverified against a real multi-scene video.
- MMRAG-14's chart extraction accuracy on a real (non-synthetic,
  harder-to-read) chart is untested.
