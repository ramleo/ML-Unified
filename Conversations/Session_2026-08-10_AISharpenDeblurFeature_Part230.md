# Session 2026-08-10/11 — AI Sharpen/Deblur Feature (Part 230)

## Starting point
Continued from Part 229. User asked to verify the "Sharpen image (AI)" feature already
shipped, then asked a new question: "can we add option to clear a blurred image so that
we can see the content of image properly?" — this session builds that feature from
scratch, iterating through several real hallucination incidents live rather than assuming
correctness.

## Design exploration (before building)
- **Sharpening filter (unsharp mask)** — cheap, boosts edge contrast, doesn't recover
  genuinely lost detail. Rejected as too weak alone.
- **Real deblur model (NAFNet/Restormer)** — discriminative, no hallucination risk in
  principle, but heavy; ruled out per the project's prior rejection of Stable Diffusion
  inpainting for being too slow on the free CPU-only Space.
- **API option for a discriminative model** — tested live via `gradio_client` against two
  public HF Spaces: `SachaDee/NAFNet_Image_Debluring` (live, but barely improved a test
  image's legibility — too weak to ship alone) and `mohamed12ahmed/Restormer_Santi` (dead,
  `RUNTIME_ERROR`).
- **Stable Diffusion** — same generative hallucination risk as any other option, plus the
  already-known CPU-only-Space speed problem. Rejected.
- **Gemini paid image editing** (`gemini-3.1-flash-lite-image`, already used for AI-fill,
  same `GEMINI_API_KEY`) — tested live with a synthetic Gaussian-blurred invoice image
  (`INVOICE #4471`, `$942.50`, `2026-09-01`), came back byte-correct. Chosen as the
  approach, shipped with an explicit "AI-enhanced — verify against original" label per
  user decision ("proceed with your suggestion").

## Round 1 — whole-image sharpen (shipped)
- New `services/ml-api/routers/rag/mm_deblur.py`: `POST /mm-deblur`, same Gemini call
  pattern as `mm_ai_fill.py`.
- New `ml-portfolio/.../useSharpen.ts` hook, wired into `CitationThumbnailPanel.tsx`
  behind an always-visible "Sharpen image (AI)" button (initially gated on the existing
  whole-image `blurry` heuristic from `blur.py`, then un-gated — see next section).
- Verified live end-to-end on production (real HTTP POST + Playwright UI test on the live
  Vercel deploy) before calling it done.
- **Commits:** `b9cd2a8` (ML-Unified), `abd870d`..`e7899cc`* (ml-portfolio, see full list
  below — some of that range belongs to later rounds).

## The "blurry" gate was wrong
User uploaded a real photo (a car) with a deliberately blurred logo/plate — the "Sharpen"
button never appeared, because `blur.py`'s heuristic is a WHOLE-IMAGE average (variance of
Laplacian); a mostly-sharp photo with one small blurred patch never trips it. Fixed by
removing the gate entirely — Sharpen is now always available, same as "Draw region"/
"Download" (already safe: labeled, non-destructive, toggleable).

## First real hallucination incident
Whole-image sharpen on the car photo: correctly restored the "NISSAN" grille badge (real
evidence existed elsewhere in the sharp parts of the photo) but **invented Devanagari text
reading "Nissan Magnite" on the license plate** — the plate had no real legible content
left, so the model filled the gap with something plausible instead of admitting it
couldn't tell. This was the direct trigger for the rest of this session's design.

Follow-up question from the user: "how do investigating agencies do that?" — answered
honestly (multi-frame super-resolution from real captured frames, deconvolution only when
the blur kernel is known/mechanical, corroboration against other records — generative
AI fill is explicitly NOT forensically valid, for exactly this reason).

## Round 2 — region-scoped sharpen
User wanted the ability to select just one region rather than the whole photo (also
narrows the hallucination blast radius by construction).
- `mm_deblur.py`: optional `bbox` on `DeblurRequest`. Crops bbox + 25% context padding
  (`_CONTEXT_PAD`, model-context-only, never pasted), sharpens the crop, pastes the result
  back into the full image at the exact bbox rect — verified numerically (max pixel diff
  outside bbox = 0, both locally and on production).
- Frontend: `SharpenControls.tsx` (new, extracted from `CitationThumbnailPanel.tsx` to
  respect the 400-line file cap) — "Sharpen region…" toggles a `FreehandDrawLayer` reuse
  for box-drawing, `SharpenOverlay` renders the region-draw layer, progress bar, and
  disclaimer.
- **Commits:** `6181588` (backend), `fc8d634` (frontend).

## Corroboration check (robustness)
User: "I want the clearing process to be robust." Modeled on real forensic practice
(trust agreement between independent sources, never a single generative guess):
region-scoped sharpen now calls Gemini **twice independently** on the same crop, OCRs
(Mistral, already used elsewhere in ingest) each result, and compares via
`difflib.SequenceMatcher`. Agreement → confidence `"high"` + the corroborated text shown
directly; disagreement → confidence `"low"` + explicit "likely unreliable, do not trust
this detail" warning instead of asserting either guess.
- **Commits:** `76c680a` (backend), `e7899cc` (frontend).
- **Verified live:** heavier blur test (Gaussian radius 12, genuinely unreadable) produced
  TWO different fabrications across attempts — `"Model: S 6 / Specs: [fake part numbers]"`
  on one whole-image call, `"'Albert' de la 'Paz'"` (a person's name) on another — proving
  there's no real signal; the corroboration check correctly returned `"low"` both times.
  Moderate blur (the invoice test) correctly returned `"high"` with the right text.

## Text-clipping bug and the paste margin
Real bbox test (`INVOICE #4471` cropped a bit tight) came back as `INVOICE #44` — traced
step by step (raw model output → resize → sub-crop) to confirm the MODEL's own output had
the full text; the bug was that paste-back honored the literal drawn box exactly, clipping
a character that was reconstructed just outside it. Fixed with `_PASTE_MARGIN` (expand the
paste rect by a fraction of the box's own size, clamped to the context-padding crop) —
first tried 0.08, still clipped a moderately-tight real drawn box live, raised to 0.20.
Verified both: clipping gone, and pixel-diff-outside-margin still exactly 0.
- **Commits:** `0630d22` (0.08), `4f5e477` (0.08→0.20).

## Second real hallucination incident + 4 more fixes
User's own live test surfaced 4 issues in one message:
1. Whole-image re-sharpen still hallucinates the plate (known, accepted tradeoff).
2. A selected Nissan logo showed "two independent AI attempts disagreed — unreliable"
   even though the AI clearly knows what a Nissan badge looks like — OCR-based
   corroboration doesn't apply to non-text graphics.
3. No way to cancel an in-flight sharpen.
4. No Download option once you have a sharpened result but no separate inpaint edit.

Fixed all four:
- **Logo false-positive (round 1):** if BOTH OCR reads are completely empty, return
  confidence `None` (not `"low"`) — frontend falls back to the plain generic disclaimer.
- **Cancel button:** `useSharpen.ts` now holds the in-flight `AbortController` in a ref;
  `SharpenButtons` replaces the trigger buttons with a single "Cancel sharpening" button
  while a call is running. Backend has no server-side cancellation (best-effort, wasted
  compute is acceptable) — cancelling only stops the client from waiting.
- **Download for sharpened image:** the Download button used to check/download only
  `resultImg` (an inpaint edit) — now downloads whichever image is actually on screen
  (`sharpenedImg` if viewing it, else `resultImg`).
- **Whole-image option:** already existed as "Re-sharpen (whole)" — not actually missing,
  just not obviously discoverable by that label.
- **Commits:** `15a3f0a` (logo fix round 1, backend), `59b8336` (cancel + download,
  frontend).

## Logo false-positive round 2 — real root cause found via Space logs
Live re-test of the logo still showed "disagreed" sometimes. Round-1 fix only handled
BOTH-empty; didn't handle one-empty-one-noisy. Rather than guess, added a temporary
`logger.info` debug line, uploaded directly to the HF Space (not committed — throwaway),
called the endpoint, and read the actual Space run logs
(`huggingface.co/api/spaces/{id}/logs/run`, SSE stream). Found the real values:
`text_a='- 2017年'` (OCR hallucinating a couple of characters out of the grille's mesh
pattern) and `text_b=''`. Fixed by requiring BOTH readings to clear a minimum length
(`_MIN_TEXT_LEN = 4`) before treating disagreement as a real finding, not just non-empty.
Deployed and verified — 2 of 3 repeat test runs now correctly return `None`; a rarer case
(both sides producing ≥4 chars of DIFFERENT noise) can still surface as `"low"` — a second
round of Space-log debugging on that exact case was in progress (temporary debug log
re-added and re-uploaded, mid-investigation) when this session log was requested; **not
yet resolved**.
- **Commit:** `a882a1b`.

## Logo false-positive round 3 — found the deeper root cause (OCR itself hallucinates)
Continued the round-2 investigation with a second diagnostic-log deploy. Real Space-log
evidence this time: `text_a='- 2017年' text_b='- *The New York Times* (1995)' similarity=0.167`
— both readings comfortably clear the `_MIN_TEXT_LEN` floor, so the round-2 fix didn't
catch this. Same logs also showed Mistral OCR fabricating a fake LaTeX equation elsewhere.
Conclusion: Mistral OCR itself hallucinates elaborate, coherent-looking fake structured
text on pure graphics — not just short noise — so a length threshold has a hard ceiling
and can't fully solve this class of bug.

Discussed three options with the user (stop here since the warning message is technically
accurate even for a graphic / reword the caption to be more neutral / build a proper
text-vs-graphic detector). User proposed a middle path: keep the current behavior by
default, add an opt-in heavier check the user can trigger. Counter-proposed and the user
agreed: make it **automatic but scoped to only the ambiguous case** — one extra targeted
Gemini vision call ("does this contain real readable text, or is it a graphic/logo?"),
fired only when the OCR-based check is already ambiguous, never on the cheap common paths.

**Implementation (`_looks_like_text_region`, via `_vision_cascade_raw`):**
- First version gated ONLY the disagreement branch (mirroring where round-2's bug lived).
  Deployed, verified: 6 repeat test runs on the Nissan logo → mostly `None` as intended,
  but one run came back `"high"` with fabricated text — WORSE than the disagreement case,
  since it now asserted fake content as *confirmed* rather than just warning about it. Root
  cause: two independent OCR hallucinations can coincidentally agree with each other (same
  input image → shared model bias), so gating only the disagreement path missed the
  agreement path entirely.
- **Fixed immediately**, same session: moved the tie-breaker check BEFORE the
  agreement/disagreement branch entirely, so it gates both — any time OCR finds ≥4 chars
  on both attempts, confirm it's really text before trusting either "high" or "low".
- **Final verification (production):** 6/6 repeat runs on the Nissan logo → `None` (no more
  false "high" or "disagreed"). Real-text case (invoice) → 2/3 `None`, 1/3 correctly
  `"high"` with the right text — the occasional `None` on real text is the classifier's own
  imprecision, but it fails in the SAFE direction (falls back to the generic disclaimer,
  never asserts anything false).
- **Commits:** `5a8ae84` (tie-breaker, disagreement-only gating), `52c00c3` (moved gate to
  cover both branches — the actual fix for the false-"high" regression).

This closes the loop: the dangerous failure mode (false "high" asserting fabricated text)
and the confusing one (false "disagreed" warning on an obvious logo) are both fixed and
verified; a remaining minor imprecision (occasional false "None" on real text) fails safe
and was left as acceptable rather than chased further.

## Round 4 — identify what a sharpened region actually is (not just logos)

User pushed the scope further after the logo round-3 fix: "not only logos, it can be
anything, can we add vision-language model in the image sharpening process, in such a way
that after the region is sharpened, it should decide what that region is and give the
output." Framed as a real design proposal first (recommend before building, per session
norm): reuse the graphic branch that already existed for the TEXT/GRAPHIC tie-breaker —
instead of throwing the classification away and showing only the generic disclaimer, have
the same vision call name what it sees, and surface it as an "Identified as: ..." caption,
explicitly labeled a single uncorroborated AI opinion (no independent-agreement check
exists for free-text description the way there is for OCR'd text). User approved ("yes").

**Backend (`mm_deblur.py`):** added `_describe_region` (asked only on the graphic branch)
and a `description` field on the response.

**Bug 1 — caught on first live production test:** description came back as the literal
string `'{"description": "Adidas logo"}'` instead of a plain phrase. Root cause: the vision
cascade's Mistral leg forces `response_format: json_object` regardless of prompt wording
(see `_vision.py`) — whichever provider answers isn't guaranteed to respect free-text
formatting. Fixed by unwrapping JSON in `_describe_region`.

**Live Playwright verification (new code path, not a repeat failure):** uploaded a
synthetic badge test image (a blurred circular shape, since the real car photo only ever
existed as an inline chat screenshot, never a saved file) to the actual Vercel deploy, drew
a region over it, ran Sharpen region, confirmed the caption rendered exactly as designed:
`Identified as: "Power button" — unverified, single AI opinion`.

**Bug 2 — user hit it live on the actual Nissan-logo photo, "Sharpen is temporarily
unavailable — try again in a moment."** Root-caused via real Space logs (SSE stream), not
guessed: `_describe_region` was a SECOND separate vision-cascade call on top of the
existing TEXT/GRAPHIC tie-breaker call. Logs showed Groq (the cascade's first leg) hitting
429/503 (rate-limited or over capacity) on nearly every production call, each failure
costing ~30s before falling back to Mistral. Two such calls back to back on the user's real
request pushed total latency to ~70s — past the frontend's 60s abort timeout — so the
browser gave up and showed the generic unavailable message even though the backend kept
working and both calls eventually succeeded (visible as `200 OK` in the logs, just too
late for the client). **Fix:** merged the TEXT/GRAPHIC classification and the description
into ONE vision-cascade call (`_classify_and_describe`, parses either the requested
`TYPE:`/`DESCRIPTION:` plain-text format or a JSON object, same Mistral-forces-JSON
handling as bug 1) — restores the original one-call latency budget. Verified live: 3
consecutive production runs at 10–20s each, well under the 60s limit.

**Bug 3 — caught in the same round of live testing:** one run's description came back as
`"**"` — stray markdown with no actual content. Fixed by discarding any description with no
letters in it at all.

**Diagnostic note:** a later live test showed `description=None` on a synthetic test image
even with no code bug — traced (via a temporary debug field returned directly in the API
response, since the Space log stream proved too laggy to catch up to fresh requests in
real time) to the vision model itself sometimes answering `TYPE: TEXT` instead of `GRAPHIC`
for that specific synthetic shape (an ambiguous blurred circle+rectangle, not a real
logo) — model non-determinism on a weak test image, not a parsing bug. Debug scaffolding
was removed before the final deploy; confirmed the shipped file matches the last commit
exactly.

- **Commits (ML-Unified):** `ea28308` (add description to graphic branch), `99169de` (fix
  JSON-wrapped description), `9ceec2a` (merge classify+describe into one call — fixes the
  timeout regression), `3def20f` (drop malformed no-letters description).
- **Commits (ml-portfolio):** `afce21f` (surface `sharpenDescription` in the caption).
- **Live-verified twice:** once via Playwright on the actual Vercel UI (synthetic badge →
  correct caption), once via direct production API timing calls after the latency fix
  (3 runs, 10–20s each, no timeout).

## Session-established testing discipline (reinforced, not new)
- Local-first Python verification before every deploy (using the user's own pasted
  `GEMINI_API_KEY` for local test calls).
- Real HTTP POST against the live production endpoint after every HF Space upload +
  `RUNNING` poll, before any UI claim.
- Live Playwright verification on the actual Vercel deploy for every UI-facing change,
  including simulating real pointer drag events (`page.mouse.down/move/up`) for the
  freehand region-draw UI, since Playwright's built-in drag tool doesn't fit a canvas
  drag gesture.
- When behavior can't be explained from first principles, add a throwaway diagnostic log,
  deploy it, read the real Space logs, then fix based on evidence — done twice this
  session for the logo false-positive, both times overturning an initial guess.
- User explicitly corrected an unverified claim mid-session ("was previous sharpen better"
  led to discovering the region-mode resize round-trip is genuinely lossier than
  whole-image) and pushed back hard on any unverified "it's fixed" claim — consistent with
  established project norms.

## Commit hashes (this session, chronological)

**ML-Unified (backend):**
1. `b9cd2a8` — AI-sharpen action for blurry citation images (whole-image, round 1)
2. `6181588` — region-scoped AI sharpen
3. `76c680a` — corroborate region-sharpen with two independent AI reads
4. `0630d22` — paste-back margin 0.08 (clipping fix, first attempt)
5. `4f5e477` — paste-back margin 0.08 → 0.20
6. `15a3f0a` — logo false-positive fix, round 1 (both-empty check)
7. `a882a1b` — logo false-positive fix, round 2 (min-length check)
8. `5a8ae84` — logo false-positive fix, round 3 (vision tie-breaker, disagreement-only)
9. `52c00c3` — logo false-positive fix, round 3b (tie-breaker gates both branches)
10. `ea28308` — identify what a sharpened graphic region actually shows
11. `99169de` — fix JSON-wrapped description (Mistral forces response_format)
12. `9ceec2a` — merge classify+describe into one call (fixes timeout regression)
13. `3def20f` — drop malformed no-letters description

**ml-portfolio (frontend):**
1. `abd870d` — always show Sharpen button (removed blurry-heuristic gate)
2. `fc8d634` — region-scoped AI sharpen with progress bar
3. `e7899cc` — surface region-sharpen confidence/corroborated text
4. `59b8336` — cancel sharpening + download works for sharpened image
5. `afce21f` — surface region description ("Identified as: ...") in the caption

## Pending / not yet resolved
- Region-sharpen's forced resize-down (model's returned crop → original crop pixel size)
  is a real, acknowledged lossy step; whole-image sharpen doesn't have this round trip and
  can look crisper for the same underlying blur. Not addressed this session.
- The text-vs-graphic tie-breaker occasionally misclassifies real text as a graphic
  (observed 1/3 runs on the invoice test), which suppresses a legitimate "high" confidence
  result. Fails safe (falls back to the generic disclaimer, asserts nothing false) and was
  accepted as-is rather than chased further — flagged here in case it's worth revisiting.
- Logo false-positive is otherwise considered resolved (verified 6/6 clean on both the
  disagreement and agreement failure modes) — no longer an open item.
- Region description ("Identified as: ...") is considered resolved after round 4: the
  JSON-wrapping bug, the 60s-timeout regression, and the malformed-output edge case were
  all caught live and fixed. The vision model's own classification can still occasionally
  flip TEXT vs GRAPHIC on a genuinely ambiguous image (observed on a synthetic test shape,
  not yet observed on a real logo) — not a code bug, and not chased further since it fails
  safe (falls back to the generic disclaimer).