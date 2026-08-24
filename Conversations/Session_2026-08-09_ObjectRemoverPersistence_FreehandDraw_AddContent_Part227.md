# Session 2026-08-09 — Persistence, Freehand Drawing, Add-Content, AI-Fill Quota Fix (Part 227)

Continuation of Part 226 (Image Inpainting & Object Remover built). This session closed out the
three items that were left "pending" at the end of that session, plus a live production bug found
and fixed the same day.

## 1. Persist the inpainted result across citation switches

Removals used to live only in `useInpaint.ts`'s local state and vanished the moment the user looked
at a different citation. Recommended in-memory persistence (survives citation switches, not a page
reload — smallest fix for the actual pain point, no new storage layer). User confirmed via
AskUserQuestion.

**Design**: lifted `resultImg`/`removedBboxes` into each document's new `edits` map
(`Record<string, PersistedEdit>`) in `_types.ts`'s `Doc`, owned by `MmRagRunner.tsx`'s `documents`
state via a new `updateDocEdit` callback, threaded down through `EvidenceColumn.tsx` →
`CitationThumbnailPanel.tsx`. `useInpaint.ts` seeds from `initialEdit` and re-syncs on `editKey`
(`source:page`) change — done via React's "adjust state during render" pattern (comparing a
`syncedKey` ref during render), not a `useEffect`, since eslint's `react-hooks/set-state-in-effect`
flagged the effect version and a render-time adjustment also avoids a one-frame flash of the stale
image.

**Verified live** (Playwright): removed "Bicycle" on `bicycle.jpeg`, switched to `goldfish-image.jpeg`,
switched back — removal still there. Reset, switched away and back — stayed clean, didn't reappear.

Commit: `b49837f` (frontend only, no backend change).

## 2. Freehand mask drawing

User asked for both automated (click a detected box) AND freehand (draw your own shape) removal to
coexist, not replace each other — confirmed this was already the plan.

**Design**: new `FreehandDrawLayer.tsx` — a transparent pointer-capture layer rendered as the LAST
sibling in the image's relative wrapper only while "Draw region" mode is on, so it naturally
intercepts all pointer events (no separate code to disable the detected-box ✕ buttons underneath).
Tracks pointer down/move/up, drops points closer than 1.5% of image size apart, draws the
in-progress stroke as an SVG polyline, and on release computes a bbox from the point cloud and
calls the SAME `onComplete(bbox, mask)` a detected box's ✕ already calls — `mm_inpaint.py` already
polygon-fills any mask with ≥3 points (previously only ever populated by SAM), so **zero backend
change** was needed for this feature.

**Verified live**: drew two separate freehand shapes on `bicycle.jpeg`, both chained correctly
(matches the multi-region-removal chaining fixed in Part 226); "Stop drawing" correctly released
pointer capture so detected-box ✕ buttons worked again immediately after.

Commit: `477d8d7` (frontend only).

## 3. Add content back into a removed region (text / image / AI-fill)

User asked: "can we have option to add something in the region which was removed?" Clarified via
AskUserQuestion into three concrete options, all wanted ("all the above").

**Text and image paste**: pure client-side canvas compositing (`imageComposite.ts`'s
`compositeOntoImage()` helper) — no backend call, instant, no cost.

**AI-fill**: this required real research before building anything, done live in-session rather than
assumed:
- Gemini's free tier: tested with a real user-provided API key — hard quota **limit: 0** for
  `gemini-2.5-flash-preview-image` (not a rate limit, a hard cap; confirmed via the actual 429
  response body, not assumed).
- Groq / Mistral: web-researched — neither has an image-*generation* model at all (only
  image-*understanding*/vision-input for Groq; text+vision-input for Mistral).
- Self-hosting an open model (FLUX Kontext, Qwen-Image-Edit): ruled out for the same reason this
  project already rejected Stable Diffusion inpainting — 12B-20B params, far too large for the free
  CPU-only HF Space tier.
- What worked, verified with **two real test calls before writing any code**: FLUX.1 Kontext [dev]
  via its **public Hugging Face Space** (`black-forest-labs/FLUX.1-Kontext-Dev`) through
  `gradio_client` — free, no API key (inference runs on that Space's own shared ZeroGPU quota, not
  ours). Test 1: recolored a bicycle red→blue, same pose/background. Test 2 (the real scenario):
  simulated a white-filled rectangle over part of the photo, asked it to "fill in the blank white
  area … matching the surrounding photo," got back a seamless reconstruction of the covered
  saddle/frame with the rest of the photo untouched.

**Design**: new backend `services/ml-api/routers/rag/mm_ai_fill.py` (`POST /rag/mm-ai-fill`),
`gradio_client.Client` cached module-level behind a lock (same `_ensure_loaded()`-style pattern
every other `mm_*.py` lazy-load uses). `useInpaint.ts` extended (not a separate hook) with
`addText`/`addImage`/`addAiFill`, all mutating the same persisted `resultImg`/`removedBboxes` state
removal already owns, plus new `filledIndices: number[]` (which removed regions have since had
content added, hides their "+" affordance). New `AddContentControls.tsx` — a "+" button per
unfilled removed region, opening an inline (not floating, avoids clipping) editor with Text/Image/AI
fill tabs, rendered only when `!drawMode` (mutually exclusive with `FreehandDrawLayer` for the same
reason).

**Verified live end-to-end**: local unit test of the endpoint function before deploy, HF Space
upload + `RUNNING` + `/docs` 200 check, direct curl POST proving real pixel behavior, then a full
Playwright pass — text label ("SOLD") composited and persisted; a second freehand region tested with
AI-fill ("a small wicker basket") showed the real ~40s "Generating…" state, then a genuine
photorealistic result reusing the actual road/tree background from the photo; confirmed the AI-fill
result also persists across a citation switch.

**Honest limitation surfaced by testing, not hidden**: because the test image's "Bicycle" detection
box covered ~85%×79% of the frame (a close-up product photo) and had already been removed +
text-labeled, the AI-fill test image was ~90%+ blank. FLUX Kontext regenerated more than just the
small target patch — it's a whole-image instruction-following editor, not exact-mask inpainting, so
"the blank area" is ambiguous when blank dominates the frame. This was flagged to the user as a real
characteristic (not a bug) in the summary rather than glossed over.

Commits: `e1aea87` (backend, + HF Space upload) + `2142c53` (frontend).

## 4. Live production bug: ZeroGPU quota exhaustion, found and fixed same day

User hit the AI-fill feature live shortly after and got "AI fill is temporarily unavailable — try
again in a moment." Asked "what is this error and why — just tell" (no fix yet, diagnosis only).

**Diagnosis, evidence-first**: confirmed the Space itself was `RUNNING` and `/docs` returned 200 (not
down). Reproduced the failure with a direct curl to the deployed endpoint (502, generic message).
Reproduced the SAME call directly via `gradio_client` locally to get the real underlying exception
(the backend's `except Exception` was swallowing it) — found:
`gradio_client.exceptions.AppError: You have exceeded your ZeroGPU runs limit. Authenticate with a
Hugging Face token for more quota.` Root cause: all of this session's testing (5+ real calls) burned
through the anonymous-caller ZeroGPU quota on the public Space.

**Solution, verified before implementing**: tested locally that passing the project's existing HF
token (`Client(_SPACE, token=...)`) resolved it — a call that failed anonymously succeeded
immediately once authenticated (confirmed via a real call, not assumed from the error message alone
— also had to fix the parameter name, `token=` not `hf_token=`, found via `inspect.signature`).

**Implementation**: added `HF_TOKEN` as an HF Space **repository secret** (not hardcoded in source)
via `HfApi.add_space_secret`, then `mm_ai_fill.py` reads `os.environ.get("HF_TOKEN")` and passes it
to `Client()`, falling back to anonymous (old low-quota behavior) if unset rather than failing
outright.

**Verified live end-to-end** after deploy: direct curl POST to the deployed `/rag/mm-ai-fill`
succeeded (200, real bicycle image returned) — confirmed the fix works in production, not just
locally.

Commit: `3530682` (backend, + HF Space upload + Space secret).

## Also discussed, not built

**A more robust fix for the "regenerates too much" limitation** (item 3's honest caveat) — proposed
but not yet implemented, pending explicit direction:
1. Crop a padded region around the target `bbox` before sending to Kontext (tighter context, less
   ambiguity about "the blank area") instead of sending the whole page image.
2. Composite the AI result back with a hard mask — only copy pixels inside the original
   `bbox`/mask from the result onto the pre-edit image, discarding anything else the model changed.
   This is the real guarantee: regardless of what the model does elsewhere in its returned image,
   the final result is provably unchanged outside the intended region.

## Commit hashes (chronological)

- `b49837f` — persist edits across citation switches (frontend)
- `477d8d7` — freehand mask drawing (frontend)
- `e1aea87` — AI-fill backend + HF Space upload
- `2142c53` — add-content frontend (text/image/AI-fill controls)
- `3530682` — ZeroGPU quota fix (authenticated gradio_client call) + HF Space upload + Space secret

## Pending / not started

Unchanged from Part 226's list except items 1-2 are now done:

1. ~~Freehand mask drawing~~ — done this session.
2. ~~Persisting the inpainted result~~ — done this session.
3. **PDF/mixed-content citations** — inpainting/add-content still only works on standalone
   image/video uploads, not a PDF's embedded photo.
4. **Crop + hard-mask compositing for AI-fill** — proposed fix for the "regenerates too much"
   limitation, not yet implemented.
5. **Watermark embedding** — deepfake *detection* exists, embedding doesn't.
6. **Live-webcam surveillance/intrusion alerting** — object detection core exists, the live-camera
   wrapper doesn't.
7. **Plate-specific ALPR** — OCR primitives exist, no dedicated plate-crop-then-OCR pipeline.
8. **TTS narration** for the audio-describer use case — captioning exists, no speech output.
9. **Text-to-Image Generator** (standalone tool)
10. **Social Reels Creator** (standalone tool)
11. **Gesture-Controlled Desktop** (standalone tool)
12. **Medical Scan Analyzer** (standalone tool)
13. **Sign Language Translator** (standalone tool)