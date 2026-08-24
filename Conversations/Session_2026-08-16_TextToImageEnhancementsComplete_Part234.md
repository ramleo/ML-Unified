# Session 2026-08-15/16 — Text-to-Image enhancement backlog closed out

Direct continuation of Part 233. That session closed the homepage-style redesign rollout across
all 14 tool pages. This session picked up the next item on the pending list — the Text-to-Image
enhancement backlog (items 4-10) — and ran it all the way through, plus several rounds of real
user-reported bugs and requests on top of the shipped features.

## Part 1 — Items 4-6: prompt enhancer, history, format conversion (free/cheap)

Built the three non-billed enhancements first since they needed no live-call sign-off:
- **Prompt enhancer**: new `POST /rag/mm-text-to-image/enhance-prompt`, reuses the existing free
  Groq→Mistral→Gemini→Cohere text cascade (not the paid image model), rewrites the prompt in place.
- **Generation history**: last 6 generations in `localStorage`, thumbnail strip.
- **Format conversion on download**: PNG/JPEG/WebP re-encoded client-side via canvas from the
  already-returned bytes, no extra API call.

Caught and fixed a real hydration mismatch during this round: the history hook read `localStorage`
during the initial client render (`useState(() => loadHistory())`), which the server can't do —
moved to a `useEffect` after mount instead.

## Part 2 — Items 7-9: sharpen, edit-this, variations (billed, asked first)

- **Sharpen ("Enhance")**: reuses `mm-deblur.py` whole-image sharpen, same shared image-edit budget
  pool citation-editing already draws from.
- **"Edit this image"**: reuses `mm-ai-fill.py`, but its existing prompt was hardcoded for filling a
  blank masked region (the citation-inpainting use case) — nonsensical on a freshly-generated image
  with no blank area. Added a `mode: "fill" | "edit"` field (default `"fill"`, so the existing
  caller is untouched) with a distinct free-form-edit instruction for `mode="edit"`.
- **Variations picker (1/2/4)**: parallel generation calls, explicit "uses Nx budget" cost warning
  before the click, partial-success handling if the budget runs out mid-batch.

Both live-tested with real billed calls before shipping (asked before each round, one at a time,
per the project's billed-API discipline).

## Part 3 — Item 10: seed reproducibility, tried and rejected with evidence

Added an experimental `seed` field to the generation request (`generationConfig.seed`), deployed,
then ran the actual test: same prompt, same seed (42), twice. Two genuinely different images came
back (different SHA-256, different byte length — 546436 vs 539208 bytes). `gemini-3.1-flash-lite-
image` does not honor `generationConfig.seed`. Removed the field entirely rather than leave dead,
misleading API surface, and documented the negative finding in the module docstring so it isn't
re-attempted without new evidence.

## Part 4 — Chat couldn't actually generate images (user-reported, real bug)

User sent a screenshot of the tool's embedded AI chat responding to a generation request with "I
cannot actually generate images in this chat" and suggesting external tools like DALL-E — the
underlying LLM has no image-gen tool call and no visibility into the page's own Generate button.

Fixed by adding an opt-in `ToolChatContext.onGenerateImage` callback (only Text-to-Image sets it):
a message like "generate an image of X" is intercepted before the normal RAG chat pipeline and
routed to the exact same `useTextToImageRunner.generate()` the Generate button calls, via an
imperative handle (`TextToImageRunnerHandle`) on the Runner component — forced to 1 image
regardless of the UI's Variations picker, so a vague chat request can't silently spend 4x budget.

**Follow-up request**: also support "compare anime vs photorealistic style of X" / "compare 2
different styles of X" — fires one generation per style and displays them. Generalized `generate()`
to accept per-image style overrides (`styleOverrides?: (string | null)[]`), added
`requestStyleComparison` to the imperative handle, and built `chatCompareIntent.ts` (regex-based
style-name/count parsing, kept local to the tool since it depends on `STYLE_OPTIONS`) separate from
the generic `chatImageIntent.ts`/`chatContext.ts` (tool-agnostic, reusable by any future tool page).

Split `useRagChat.ts`'s intent-detection and context-building logic into these new files when it
briefly crossed 423 lines — kept it under the 400-line cap.

**Follow-up request**: "place images side by side if 2, multiple rows if more than 2." The old
small-thumbnail swap row didn't scale. Built `TextToImageComparisonGrid.tsx` — fixed 2-column CSS
grid (wraps into more rows automatically for >2 images), each cell labeled by style, selected one
highlighted with an accent border. Added a `label`/`resultLabel` field threaded through
`useTextToImageRunner.ts` so each grid cell shows its style name.

All three (single chat generation, 2-style comparison, grid layout) verified live with real billed
calls and zoomed screenshots — not just code review.

## Part 5 — History thumbnails didn't actually work right (user-reported)

Three real gaps reported together:
1. No persistent highlight on which history thumbnail is "currently loaded" (only the browser's
   transient focus ring, which disappeared on any other interaction).
2. Clicking a thumbnail only restored the prompt text, not the actual image — required clicking
   Generate again (spending fresh budget) just to see an image that already existed.
3. Asked to confirm Sharpen/Edit-this stay correctly scoped to whichever image is currently
   selected, across grid swaps and history loads.

Fixed #1/#2 with a new `activeHistoryTimestamp` state and a rewritten `restoreFromHistory` that
sets `resultImage`/`resultMimeType` directly, not just the prompt. #3 was already correct —
`useTextToImageEdit.ts` resets its sharpen state whenever the `baseImage` prop changes — just
needed history-loading to route through that same `resultImage` state, which the #2 fix did.
Verified live by seeding two distinct history entries and clicking between them.

## Part 6 — Layout was cramped into a narrow column (user-reported)

Page was capped at `max-w-3xl` (768px) with everything stacked in one column regardless of
viewport width. Widened to `max-w-6xl` and split `TextToImageRunner.tsx` into a real two-column
grid (form left, result/history right) at the `xl` breakpoint.

**Real bug in the first attempt**: used a bare `1fr` for the right column, which hit a classic CSS
Grid gotcha — an `fr` track's minimum width defaults to `auto` (its content's natural size), not
zero, so wide content inside blew the track past the container and visibly dragged the whole
centered block off-axis (user reported "there is space on the left side of screen, why?"). Fixed
with `minmax(0, 1fr)` in both the page grid and the comparison grid's own columns. Verified via
direct DOM `getBoundingClientRect()` measurement (left/right margins exactly equal), not eyeballing
a screenshot — the fix looked plausible on sight but the numbers were the actual proof.

## Part 7 — Feature ideas survey + "Describe an image" (reverse feature)

User asked what else could be added; did a web search for 2026 image-gen tool features. Ruled out
ControlNet-style pose guidance, vector/SVG output, and reliable in-image text rendering as not
buildable on Gemini's API (need a fundamentally different model). Picked the cheapest, most
distinct option: **image-to-prompt (reverse)** — upload a photo, get a written description back,
seed the prompt box with it.

Reused the existing free vision cascade (`routers/document/_vision.py`'s `_vision_cascade_raw`,
Groq→Mistral→Gemini, already used for document captioning) — not the paid image model, no budget
cost. **Real gotcha caught before writing any code**: `_mistral_vision_raw` forces
`response_format=json_object` on every call, and `_vision_cascade_raw` returns on the FIRST
non-empty response — a plain-prose prompt would have either failed on the Mistral leg or leaked raw
`{...}` JSON into the user's prompt box whenever Mistral answered first. Fixed by asking every
cascade leg for the same `{"description": "..."}` shape and parsing with the existing `_parse_json`
helper. Live-verified: raw curl against the deployed endpoint (a UI screenshot correctly described,
no leaked JSON) and a real Playwright file-upload through the actual button.

**Real bug reported after shipping**: user uploaded an actual car photo and got
`{"description":"","ok":false}`. The pre-ship test image was a UI screenshot (misleadingly named
`car-uploaded-full.png` — actually a multimodal-rag UI capture), which never exercised a real
photograph. Could not reproduce deterministically — deployed a temporary debug build
(`_debug_raw` field on failure) to gather real evidence first rather than guess, ran 8 live test
calls with an actual cropped car photo, all 8 succeeded. Root cause matched the risk flagged when
the feature was built: the first-answering provider sometimes ignores "return ONLY JSON" on a real
photo. Shipped the fix anyway since it's correct by construction (falls back to raw text ONLY when
`_parse_json` finds no JSON at all, never when JSON was found but missing the `description` key,
which would leak braces) — and was explicit with the user that this is "fixed by evidence-matching,
not verified by direct repro," asking them to retry the original failing upload as the real test.

## Part 8 — Clear prompt + remove single history entry (user-reported)

Two more real gaps: no way to clear just the prompt text, and "Clear" on history wiped everything
instead of letting you remove one entry. Added a small × in the textarea's corner (clears prompt
only, style/aspect/variations untouched) and a per-thumbnail × (removes just that entry; if it was
the active one, only its highlight clears, the displayed image/prompt stay put). Extracted the
history card into `TextToImageHistoryPanel.tsx` when the per-thumbnail delete button pushed
`TextToImageRunner.tsx` to 413 lines, over the cap. Verified live: typed a prompt, cleared it;
seeded two history entries, removed one, confirmed the other survived.

## Part 9 — describe-image leaking raw reasoning text (user-reported, real bug)

User sent screenshots showing two linked symptoms:
1. The prompt box after "Describe an image" filled with a raw `<think>...</think>` reasoning
   block plus "**Analysis of the Image(s):**" commentary — not the clean single-paragraph
   description the endpoint was supposed to return.
2. Generating from that garbled description produced one result image that was itself a
   multi-panel collage (three car angles stacked in one frame) instead of a single clean shot.

Root cause: `_vision_cascade_raw` had landed on a reasoning-model leg (observed: Groq's qwen) that
prepends a `<think>...</think>` chain-of-thought block before its actual JSON answer. `_parse_json`
found no valid JSON in that response (the `<think>` block came first), so the code fell to its raw-
text fallback — and that fallback text was the entire reasoning dump, multi-section analysis and
all. Feeding "Analysis of the Image(s): ..." style text into the generator reads as a request for
multiple views, which is why the output came back as a collage rather than one image — a downstream
symptom of the same upstream leak, not a separate bug.

Fixed in `mm_text_to_image.py`'s `describe_image` endpoint:
- Added `_THINK_BLOCK_RE` (handles both a closed `<think>...</think>` and an unterminated `<think>`
  with no closing tag, matching a reasoning-model leak pattern already seen elsewhere in this
  codebase) — strips it from the raw response before `_parse_json` runs, so JSON that was actually
  present after the reasoning block now parses correctly.
- Added `_ANALYSIS_MARKER_RE` as a safety net on the raw-text fallback path itself: if a response
  still contains analysis-style markers ("Analysis of the Image(s)", markdown headers, bold-leading
  lines) even after `<think>`-stripping, the fallback is rejected and the endpoint returns
  `{"description": "", "ok": false}` instead of feeding garbled text to the generator — better to
  surface "try again" than silently produce a garbled collage image.
- Added the missing `import re` (file previously had no regex usage).

Backend file (`mm_text_to_image.py`) grew from 257 to 277 lines — still well under the 400-line cap.
Verified with `ast.parse()` for syntax correctness; user explicitly asked to commit/push/deploy
**without** a live test this round, so no live billed call or Playwright pass was run this time —
committed as `91f6fb4`, pushed to GitHub, and uploaded to the HF Space per the mandatory post-backend-
commit deploy rule. Live verification (re-uploading the original failing car photo) is still
outstanding, same as the describe-image fix from Part 7.

## Final state

Text-to-Image's enhancement backlog (items 4-10) is fully closed:
- Shipped: prompt enhancer, generation history (+ remove-single-entry), format conversion,
  sharpen, edit-this, variations picker, chat-triggered generation, chat style comparison + grid
  layout, image-to-prompt reverse feature, clear-prompt button.
- Rejected with evidence, not shelved for lack of testing: seed reproducibility.
- Fixed after real user reports (not caught in initial testing): chat refusing to generate, history
  thumbnails not loading/highlighting, cramped/off-axis layout, describe-image failing on real
  photos, missing clear controls, describe-image leaking raw `<think>` reasoning text into the
  prompt box (and the downstream collage-image symptom that caused).

## Commit hashes (chronological)

**ML-Unified (backend):**
1. `014dcb0` — enhance-prompt endpoint, mm-ai-fill mode="edit", experimental seed field
2. `5bf3d45` — seed field removed after live rejection, negative finding documented
3. `b1fd9ff` — describe-image endpoint (image-to-prompt reverse)
4. `4076ba3` — describe-image JSON-fallback robustness fix
5. `91f6fb4` — describe-image `<think>`-block strip + analysis-marker fallback rejection

**ml-portfolio (frontend):**
1. `5328030` — prompt enhancer, history, format conversion, sharpen/edit panel, variations picker
2. `f8cfef6` — chat-triggered generation + style comparison
3. `95966d5` — history thumbnails load the image and stay highlighted
4. `545a638` — wider layout, CSS Grid `minmax(0,1fr)` blowout fix
5. `6d231d1` — "Describe an image" upload button
6. `6b826ec` — clear-prompt button, remove-single-history-entry button

## Memory changes this session

- `project_text_to_image_tool.md` updated with every round above, including the two "fixed by
  construction, not directly reproduced" honesty notes (mm-ai-fill mode assumption check, the
  describe-image real-photo bug) and the web-search feature survey findings for future reference.
- `project_pending_master_list.md` — Text-to-Image row removed entirely; item fully closed.

## Pending / not yet resolved

- The Part 9 `<think>`-leak fix (`91f6fb4`) is committed, pushed, and deployed to the HF Space but
  NOT live-verified — user explicitly asked for commit+push+deploy without a test this round.
  Real verification (re-run "Describe an image" on a real photo, confirm clean single-paragraph
  output, confirm a subsequent generate produces one clean image not a collage) is still owed.
- Remaining pending items unchanged from before this session: Social Reels Creator,
  Gesture-Controlled Desktop, Sign Language Translator (all high-effort CV standalone tools),
  MMRAG-16 (text/image-paste into removed region, low effort, not started), LLM Fine-tuning
  Pipeline (needs GPU), Time Series Forecasting.