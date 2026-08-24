# Session 2026-08-18 — Plant Growth: Collage Auto-Split, Blob Fallback, Camera, Card Truncation (Part 240)

Direct continuation of Part 239 (base Plant Growth Quantification tool + multi-plant auto-detect +
compare mode, all shipped 2026-08-17). This session pushed the same tool through five more feature
increments, each following the session's established "plan → build → verify live → commit/push →
HF upload → verify live" discipline, plus a homepage fix unrelated to the plant tool.

## 1. Collage auto-detect and auto-split

User asked to research the tool and add improvements; also separately asked to build the
"framing-guide" feature idea from an earlier explanation of why growth% depends on consistent
photo framing. First: revisited the collage problem from Part 239 (a before/after collage photo
being misread as multiple simultaneous plants) and built a real fix instead of just telling users to
pre-split manually.

**Backend**: new `mm_plant_growth_collage.py` — `detect_collage_seam()` looks for a straight seam
(sharp Sobel edge + a color/exposure jump between the two halves + a plant box centered on each
side) near the image midline. When found, `_auto_split_collage()` splits the photo there and runs it
through the existing 2-frame growth-mode measurement, returning `mode: "growth"` with a new
`auto_split_collage: true` flag. Verified against the real Feb/Sept collage photo from Part 239:
**+260.2% growth**, matching the +252.1% manually measured before (small diff = seam position vs.
manual midpoint crop).

**Real false positive caught and fixed during testing**: once the leaf-mask blob fallback (section 2)
started supplying more candidate boxes, a genuine single-scene stock illustration (3 seedlings) got
mis-detected as a collage — the seam check's column-average gradient was fooled by one plant's sharp
leaf edge averaging up over a mostly-flat background. Fixed by requiring the edge to be continuous
across ≥60% of the seam's length (a real stitched-photo seam runs nearly the full image dimension;
a single object's edge only covers a small fraction) — confirmed empirically: the false-positive case
covered only ~19% of image height at that column vs. ~91% for the real collage.

**Frontend**: banner explaining the auto-split and its left-to-right/top-to-bottom panel-order
assumption. Commits: ML-Unified `0eb6f2a`, ml-portfolio `2db44b9`.

## 2. Leaf-mask blob fallback for under-detected plants

User reported a real bug: uploading a stock illustration of 3 seedlings ("Measuring Growth") in
compare mode returned "found fewer than 2 plants" despite 3 being clearly visible. Told directly to
research and fix it, not accept it as a limitation.

Debugged with the actual image: the 601-class object detector found only 1 "Plant" box (0.408
confidence) — it recognized the middle seedling but missed the smallest and largest. New
`mm_plant_growth_blobs.py`: `detect_plant_blobs()` does connected-component analysis directly on the
tool's own HSV leaf mask (with a morphological close to bridge small gaps within one plant's own
foliage) — this doesn't depend on the detector's training distribution at all, only on foliage being
green and spatially separate. `_detect_plant_boxes()` now falls back to this when the object detector
finds fewer than 2 plants. Verified: the 3-seedling image now correctly returns 3 plants at
13.4% / 61.3% / 100% relative size — matching the real growth-stage progression in the illustration.

This is also what surfaced the collage false-positive in section 1 (more candidate boxes reaching the
seam check). Commits: ML-Unified `955d907`.

## 3. Greenness index and leaf count metrics

User asked to research web/online for improvements to the tool and list feature ideas. Researched
plant phenotyping literature (Leaf Analyzer, RGB-only vegetation indices, leaf counting via CV) and
consumer plant apps (PlantCam, Caladium). Presented a categorized list; user said "yes, do it" to the
three zero-cost/no-new-infra ideas: vegetation index, leaf count, and a framing-alignment guide.

**Backend**: new `mm_plant_growth_metrics.py` — `greenness_index()` computes mean NGRDI
((G-R)/(G+R)) over the leaf-masked pixels, an RGB-only vegetation index substituting for
infrared-based chlorophyll sensing (smartphones have no NIR channel) — a stress/yellowing signal
independent of leaf area. `count_leaves()` does connected components WITHOUT the closing operation
used for plant-separation (the opposite goal here: count individual leaves, don't merge them).
Both computed alongside `area_fraction` in `_leaf_area_and_mask()` and threaded through every
response path (growth mode, compare mode, missing-plant fallback). Verified real leaf_count can
legitimately DROP as a plant matures (6→4 "leaves" on the real Feb→Sept photo, +260% area growth)
since touching/overlapping leaves merge into one blob under simple connected components — a known,
documented CV limitation (matches the leaf-counting literature), disclosed via UI caveat text rather
than hidden. Commits: ML-Unified `2a60823`.

**Frontend**: leaf count caption under every thumbnail; hover tooltip with both metrics plus the
undercount caveat. Commits: ml-portfolio `005d648`.

## 4. Click-to-lightbox and growth-stages view

Two follow-up questions from a screenshot: (1) "where is the green overlay the note mentions?" —
answered by pulling the raw `mask_preview` image directly: the overlay IS there, just visually subtle
since it's a green tint on already-green leaves, especially at thumbnail size. (2) "can images expand
on hover/click?" — built a `Lightbox` component (fixed backdrop, Esc/click-outside to close) reused
across both growth-mode frame thumbnails and compare-mode plant thumbnails; confirmed the full-size
view does make the overlay much more legible. Commits: ml-portfolio `838f07b`.

Separately, user clarified that a "3 plants" seedling stock image was conceptually meant as ONE plant
at 3 growth stages, not 3 coexisting plants — asked if I understood, then asked for a "growth stages"
view. Explained why this differs from the collage case (no detectable seam exists here — it's one
continuous illustration, no stitched-photo boundary) and proposed a manual toggle instead of an
auto-detected fact. Built: a "Rank by size" / "View as growth stages" toggle in compare mode, the
latter re-plotting the same detected plants ordered left-to-right as a growth-chart line instead of
ranked bars, with an explicit "this is your interpretation, not detected automatically" disclaimer.

**Real bug caught and fixed during testing**: the first version computed stage growth% from each
plant's `areaFraction` (fraction of its own crop) — reintroducing the exact fraction-of-own-crop bug
from Part 239's compare-mode fix. Caught by checking the numbers: Plant 3 (the largest) showed LESS
growth than Plant 2, which is backwards. Fixed by switching to `relativePct` (already correctly
absolute-pixel-count-based). Re-verified: Plant 1→0%, Plant 2→+357.5%, Plant 3→+646.3%, correctly
monotonic. Commits: ml-portfolio `598c97c`.

Also fixed a genuine UI bug found via a user screenshot: removing a pending photo left the previous
measurement result on screen for a photo no longer selected — `removePhoto` now calls `reset()`.
Commits: ml-portfolio `f1b306d`.

## 5. Framing-check preview and live camera capture

Explained the researched "framing-guide" idea (Caladium's live ghost-overlay pattern) and why it
can't translate directly (this tool has no live camera preview, only an `<input type=file>` picker).
Built the realistic adaptation first: `PlantGrowthFramingCheck.tsx` — a "Check framing" option per
pending photo (from the 2nd onward) opening an opacity-slider blend against the first photo, so a
shifted pot/background/plant edge becomes visually obvious before measuring. Commits: ml-portfolio
`7d1ddd8`.

User then asked to add live camera capture too. Built `PlantGrowthCamera.tsx` — a "Take photo"
button using `getUserMedia`, additive to the file picker. Once a first photo exists, it's overlaid
semi-transparently on the live video feed in real time — the actual live ghost-overlay pattern,
finally possible with a live feed. Captured photos feed into the same `pending` list as file uploads.

**Honest verification limit disclosed upfront and again after building**: this sandboxed Playwright
browser only has a fake camera producing a black feed (`videoWidth: 0` until artificially patched via
`Object.defineProperty` for testing). Verified everything reachable without real pixels: permission-
denied path, the capture guard refusing a zero-dimension video, append-to-pending + auto-close on
capture, and the ghost-overlay DOM/opacity-slider structure on the second capture. Told the user
plainly that actual video rendering needs a real-device check. Commits: ml-portfolio `233c2d3`.

## 6. Homepage capability-card fixes (not plant-growth specific)

User pointed out via screenshot that the "Plant Growth Quantification" card's description (grown
across all the above increments) had made that card visibly taller than its siblings in the
homepage's capability grid. Fixed in `MLCapabilities.tsx`: clamped every card's description to 3
lines via `-webkit-line-clamp`, added a "See more" link that navigates to the tool (reusing the same
3-way internalLink/modal/new-tab priority the action button already used, consolidated into one
`handleNavigate` to remove triplicated onClick logic). Verified via direct DOM measurement (not
screenshots — this machine's headless Chromium renders blank screenshots for this page, a known
local-only issue, not a real bug) that all 19 cards now render at an identical 759px height.
Commits: ml-portfolio `e0a78ab`.

Follow-up: asked to make "See more" show the full description on hover instead of only on click, and
asked directly whether it would look ugly. Flagged two real risks before building — clipping by the
capability grid's `overflow-x: auto` scroll container, and an awkward hover-then-click double-behavior
on the same element — and offered a choice between a custom styled popover, a plain native tooltip,
or no hover at all. User chose the custom popover. Built `CapabilityDescriptionPreview.tsx`, portaled
to `document.body` specifically to escape the scroll-container clipping, position computed from the
trigger's live bounding rect and clamped to the viewport. Verified via DOM inspection (real Playwright
hover, not synthetic events — React's synthetic mouseenter doesn't fire on a dispatched native
`mouseenter`): popover appears with full text, correct position, closes on mouseleave, and clamps
correctly for cards near both viewport edges. Commits: ml-portfolio `1947c75`.

## Commits this session

Backend (ML-Unified): `0eb6f2a` → `955d907` → `2a60823`
Frontend (ml-portfolio): `2db44b9` → `838f07b` → `598c97c` → `f1b306d` → `7d1ddd8` → `233c2d3` →
`e0a78ab` → `1947c75`

## How to apply going forward

- **Plan before proceeding, even for well-understood requests**: established explicitly this session
  after the collage-auto-split feature request — show a plan (plain text is fine, doesn't require
  full plan-mode agent ceremony when scope is already clear from conversation) and get an explicit
  go-ahead before writing code. See [[feedback-plan-before-proceeding]].
- **Fraction-of-own-region vs. absolute-count is a recurring bug class in this tool**: hit twice now
  (Part 239's compare-mode `relative_pct`, this session's growth-stages `growthPct`) — never compare
  a per-region FRACTION across regions of different sizes; use an absolute count instead. Worth
  checking for a third time if this tool grows more aggregation views.
- **Headless screenshots are unreliable on this machine for the homepage** (not just WebGL,
  per the earlier depth-parallax finding) — the capabilities-grid screenshots came back solid blank
  even though the DOM/accessibility snapshot showed correct content. Verify via DOM measurement
  (`getBoundingClientRect`, `getComputedStyle`, `scrollHeight` vs `clientHeight`) rather than trusting
  a blank/wrong screenshot as a real bug.
- **React synthetic hover events need real Playwright hover, not dispatched native events** — a
  dispatched `mouseenter`/`mouseleave` via `dispatchEvent` does not reliably trigger React's
  `onMouseEnter`/`onMouseLeave` (React uses delegated `mouseover`/`mouseout` under the hood); use
  `browser_hover` on an actual element instead.
- **Live camera / getUserMedia features can't be fully verified in this sandbox** — only a fake
  black-frame camera is available. Structural/logic verification (permission handling, capture
  guards, state wiring) is possible and was done; actual video rendering needs a real-device check
  from the user.
- **Portal-to-body is the fix for popovers inside `overflow-x: auto` containers** — established twice
  this session (the plant-growth Lightbox pattern already did this; the capability-card hover preview
  needed the same treatment) — any new floating UI inside the horizontally-scrolling capability grid
  or the plant-growth tool's pending-photo strip should default to a portal, not inline absolute
  positioning.
