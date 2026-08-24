# Session 2026-08-17 — Plant Growth Quantification: New Tool + Multi-Plant Modes (Part 239)

Continuation of Part 238 (Depth Parallax occlusion/relief fixes). User asked to shelve (not abandon)
Depth Parallax's occlusion/3D-relief work — it needs improvement, but isn't the active task — and
asked what's next on the consolidated pending list. Picked **Plant Growth Quantification** (CV backlog
row #53), rated Low effort and, like the just-shipped Watermark tool, needing zero paid API calls.

## 1. Base tool build

New standalone tool: upload 2-30 timelapse photos of the same plant, get a leaf-area growth curve.
Measurement is a simple HSV green-hue threshold (`H` 30-95 in OpenCV's 0-180 scale, with saturation/
value floors to exclude shadow/blown-highlight false positives) — no ML model, pure local compute,
same category as the earlier Watermark tool.

**Backend**: new `services/ml-api/routers/rag/mm_plant_growth.py`, modeled directly on
`mm_watermark.py`'s pattern (base64 in/out, no budget gating). `measure_leaf_area()` returns
`area_fraction` (leaf pixels / total pixels) plus a `mask_preview` — a green-overlay PNG showing
exactly what was counted as plant, the tool's core "honesty check" so a user isn't trusting a bare
number blindly. Endpoint computes `growth_pct` per frame relative to frame 0's baseline, flags any
frame `low_confidence` if `area_fraction < 1%` (likely wrong framing/no plant found).

**Frontend**: new `ml-portfolio/src/app/tools/plant-growth/` (page/Runner/hook three-file split).
Multi-file upload (`<input type="file" multiple>`) was a genuinely new pattern for this codebase —
confirmed via exploration that no existing tool took more than one file. Growth curve rendered as a
hand-rolled inline SVG (no charting library in this repo — `realtime-analytics/AnalyticsCharts.tsx`'s
`Sparkline` was the reference pattern, adapted rather than reused directly).

**Two real bugs caught during live Playwright verification, both fixed before shipping**:
- Top-right chart label clipped against the SVG's top edge (increased `PT` padding 12→26).
- Rightmost point's `%` label clipped off the right edge (`text-anchor` now varies: `start` for the
  first point, `end` for the last, `middle` for interior points, instead of always `middle`).

Verified live end-to-end via Playwright with synthetic test images (0%→+406.2%→+956.2% growth curve
rendering correctly, mask previews, editable per-photo day labels). Commits: ML-Unified `fc20a94`,
ml-portfolio `b4ecb8b`. HF Space upload done same session (CLAUDE.md rule 4).

## 2. Multi-plant auto-detect (across a photo series)

User asked: what if one photo has multiple plants? Answer: the base tool had no per-region concept
at all — `measure_leaf_area()` blended every green pixel in the whole frame into one meaningless
number. User then explicitly asked to reuse object detection to find and separate multiple plants —
confirmed the existing 601-class OIV7 detector already has `Plant`/`Houseplant`/`Flowerpot` classes,
same reuse pattern as the earlier plate-detection and weapon-detection features (zero new model).

**Backend**: `_detect_plant_boxes()` calls the existing `mm_objects.py`'s `detect_objects()`, filters
to plant classes, sorts left-to-right. `_crop()` pads each box 15% (matching `mm_objects.py`'s own
person/vehicle crop convention) and crops. **Cross-frame track matching**: frame 0's box count is
canonical (it's already the growth baseline); later frames supply up to that many boxes by position.
A plant missing from a later frame (occluded/moved) is marked `low_confidence: true` with an honest
"not found this day" signal rather than a fabricated number. Response reshaped to
`{"plants": [{"index", "frames": [...]}]}` — always a list, even for the single-plant case, no dual
contract. `auto_detect: bool = True` is a real, visible toggle (not silent magic) so a user can fall
back to whole-frame measurement if detection misfires on a photo.

**Frontend**: "Auto-detect multiple plants" checkbox (default on); a "Plant 1 / Plant 2 / …" pill
selector appears only when more than one track exists — zero UI change for the common single-plant
case. Mask-preview thumbnails in multi-plant mode show the crop itself, not the full photo.

Verified via mocked-`detect_objects` unit tests (no real multi-plant photo was available locally to
trigger genuine detection): confirmed independent per-plant growth curves, the frame-count-mismatch
"missing this day" fallback, and full backward compatibility with the single-track path. Live
Playwright pass confirmed the new response shape renders correctly end-to-end through the browser
(exercising the 0-boxes-detected fallback path, since synthetic squares don't trigger a real
detector). Commits: ML-Unified `6ea2e1a`, ml-portfolio `3769ef4`. HF Space upload + live verification
done same session.

## 3. Single-photo multi-plant comparison mode

User pushed back twice ("that's what I said, you didn't understand my requirement") on an initial
misread — clarified via AskUserQuestion that they wanted BOTH capabilities: growth-over-time (already
built) AND a genuinely different mode — one photo, multiple plants, compare their CURRENT size to
each other, no time axis, no second photo required.

**Backend**: dropped the hard 2-frame minimum to 1. New `_compare_single_photo()` branch: requires
`auto_detect=True` (nothing to compare with detection off), needs 2+ detected plant boxes or raises
a specific actionable 400 ("Found fewer than 2 plants... try a photo with multiple distinct plants,
or add a second photo to measure growth over time instead"). Response gains a `"mode"` field
(`"growth"` or `"compare"`) as an explicit discriminant.

**Real bug found and fixed during unit testing, before shipping**: initially computed `relative_pct`
from each plant's `area_fraction` (leaf pixels / that plant's OWN crop size) — but a tightly-cropped
small plant and a tightly-cropped large plant both read as "mostly foliage" regardless of true size,
since the crop area itself scales with the box. Three synthetic plants of very different real sizes
(1600/8000/16800 px²) all came back ~59% area_fraction and ~100% relative to each other — the
comparison was meaningless. Fixed by adding `leaf_pixel_count` (absolute pixel count) to the shared
measurement function and using that instead — same test then correctly returned 14.3% / 47.6% / 100%,
matching the real size ratios.

**Frontend**: `usePlantGrowthRunner.ts`'s response type became a discriminated union
(`{mode: "growth", ...} | {mode: "compare", ...}`); backend HTTPException `detail` messages now
surface verbatim in the UI instead of a generic fallback. New `CompareView` component: horizontal
bars sorted descending by `relative_pct`, each with its crop thumbnail. Upload button relabels to
"Compare plants (N)" at exactly 1 pending photo, "Measure growth (N)" otherwise; hint text explains
the mode switch instead of blocking with "need 2 photos."

Verified live via Playwright: single-photo error path (0 real plants detected on a synthetic image)
correctly surfaced the exact backend message end-to-end; 2-photo growth path re-confirmed with no
regression. Commits: ML-Unified `9d0f953`, ml-portfolio `64faac5`.

**HF Space deploy hit a real, expected timing issue**: the first post-upload verification call
returned the OLD response shape (`mode: None`, old error text) — not a code bug, just the Space
rebuild still in progress (`RUNNING_APP_STARTING`, not yet `RUNNING`). Polled the Space runtime API
until `RUNNING`, then re-verified — both `mode: "growth"` (525% growth, matching local test exactly)
and the new `mode: "compare"` error path confirmed correct on the live deployed endpoint.

## 4. Real-world image test — the collage confusion

User shared a screenshot showing 4 "plants" being compared from what was actually a single photo, with
percentages that didn't make sense to them (two of the four looked like the same plant). Diagnosed
before seeing the file: this was very likely a **collage image** — a single file already assembled
from multiple separate photos (common "plant progress" post format) — which the detector has no way
to distinguish from "multiple distinct plants coexisting in one real scene." User then supplied the
actual file (`~/Downloads/some-satisfying-before-and-after-pics.png`).

Confirmed by reading the image directly: a genuine two-panel before/after collage, ONE plant,
"February 2024" vs. "September 2024" captions baked into the image, dramatically fuller by September.
The detector's 4 boxes came from: the two real panel photos of the same plant, PLUS incidental
background plants visible in each half (a windowsill plant in the Feb panel, something near a metal
rack in the Sept panel) — the tool has no plant re-identification (no concept of "these two boxes are
the same individual plant at different times") and doesn't read embedded caption text, so it just
compared all 4 detected regions as if they were 4 simultaneous, unrelated plants.

**Resolution, not a code fix**: this input doesn't fit either of the tool's two modes — compare mode
assumes genuinely distinct simultaneous plants, growth mode assumes separate photo files per time
point. Split the collage in half with a one-off PIL crop (`/tmp/plant_feb2024.png` /
`/tmp/plant_sep2024.png`) and recommended the user upload those two crops as separate photos through
growth mode instead, which would measure the real change correctly. No code changed for this — a
genuine tool-scope/input-mismatch explanation, not a bug fix.

## 5. Collage re-check, live growth verification, and the auto-split feature ask

User uploaded the same collage image again, this time through compare mode directly, and asked why it
still showed 4 plants when there are only 2 real ones. Same root cause as section 4, re-confirmed:
Plant 4/Plant 2 were the real subject split across the two panels, Plant 3/Plant 1 were incidental
background plants visible in each half. No code change — explanation only, referencing the same
disclosed limitation.

User then said "yes" to actually running the two pre-split crops (`/tmp/plant_feb2024.png`,
`/tmp/plant_sep2024.png`, made in section 4) through the live tool to see the real number. POSTed them
directly to the deployed HF Space endpoint (`https://wram1708-ml-unified.hf.space/rag/mm-plant-growth`,
growth mode, 2 frames, `auto_detect: true`) via curl rather than the browser UI. Real result: **the
actual plant went from 8.65% to 30.47% leaf-area fraction, Feb→Sept = +252.1% growth.** The paired
background-plant track (Plant 1) was correctly flagged `low_confidence: true` / `growth_pct: -100.0`
when it wasn't found in the Sept crop, rather than being given a fabricated number — matching the
tool's existing honest-missing-data design from section 2.

User then asked for a NEW feature: auto-detect that an uploaded single image is a multi-panel collage,
split it, and route the pieces into growth mode automatically — instead of the user manually
pre-splitting as done above. Before doing any planning, flagged the core feasibility concern: **object
detection alone cannot distinguish "a collage of the same plant across time" from "a real scene with
several distinct plants side-by-side"** (the exact case compare mode was built for, e.g. the original
3-seedling photo). Both look identical to the detector — multiple plant boxes in one image, no
temporal or same-subject signal available. An auto-split feature would need a genuinely separate
detection step (panel/collage-seam layout detection, not plant detection) to be reliable. User
confirmed this is the right target to plan for, entered plan mode — but then interrupted the
plan-mode workflow (rejected `ExitPlanMode` mid-flow) specifically because a full Explore/Plan-agent
research pass wasn't warranted for what they'd already scoped in conversation; redirected instead to
a direct, non-plan-mode update of this log.

**Status: feature not yet planned or built.** No plan file has been finalized for the collage-auto-
split feature. Next session should pick this up by asking whether to properly scope it now (given the
feasibility concern above — likely needs a new collage/panel-seam detector, separate from the existing
plant detector) or judge it not worth the complexity versus telling users to pre-split collages
manually (the workaround already proven to work correctly in this section).

## Commits this session

1. `fc20a94` (ML-Unified) / `b4ecb8b` (ml-portfolio) — base Plant Growth Quantification tool
2. `6ea2e1a` (ML-Unified) / `3769ef4` (ml-portfolio) — multi-plant auto-detect across a photo series
3. `9d0f953` (ML-Unified) / `64faac5` (ml-portfolio) — single-photo multi-plant comparison mode

## How to apply going forward

- **Per-crop vs. per-frame measurement pitfalls**: a metric computed relative to its OWN crop/region
  size (a fraction) silently loses absolute-scale information the moment you're comparing across
  differently-sized crops — this is the same *category* of mistake as Part 238's occlusion blur-bias
  bug (using the wrong aggregation operation for the actual question being asked). Caught this time
  via a synthetic three-different-sizes unit test BEFORE shipping, not from a live user report.
- **Object detection has no identity/re-identification concept**: reusing an existing detector (as
  done here, and for plate/weapon detection before) finds WHAT is in a box, never whether two boxes
  across time or across a collage are "the same real-world subject." Any feature built on top of raw
  detection needs to stay honest about that boundary rather than implying more understanding than
  the model actually has.
- **HF Space rebuild timing**: a post-upload verification call that returns stale/old data isn't
  automatically a real failure — check the Space runtime `stage` field before concluding the deploy
  is broken; `RUNNING_APP_STARTING` just means "still rebuilding," not "failed."
- User relaxed the "ask before every Playwright action" pattern further this session — approved
  full verification passes without re-confirming each click, consistent with Part 238's established
  relaxation.
- **Collage-vs-multi-plant detection is a known open question, not yet resolved**: any future work on
  auto-splitting collages needs a new layout/seam-detection step, separate from the existing plant
  object detector — do not assume the existing detection pipeline extends to this for free.
- When a request is small enough to have already been scoped in plain conversation, don't default to
  a full plan-mode Explore/Plan-agent pass — the user will interrupt and redirect to a direct answer
  or edit if the ceremony isn't warranted.
