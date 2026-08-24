# Session 2026-08-13/14 — Deblur pending-fixes, billed-API incident, logo ID fix

Continuation of the AI Sharpen/Deblur feature work from Part 230. This session tackled the
three items left on that file's "Pending / not yet resolved" list, then a real production
incident (repeated live testing drained the user's Gemini billing account) forced a change
in how live verification gets done going forward, then closed with a further real bug found
by the user (region-sharpen's logo identification was simply wrong) and its fix.

## Part 1 — Verified the MMRAG-adjacent "pending" backlog claims

User asked what was still pending from an earlier 11-item brainstormed backlog
(project_realworld_usecases.md, 2026-07-21/22). Stale 18-day-old memory said only
"table → chart on demand" was unbuilt. Verified against actual code (not memory) via grep
across both repos — found the feature WAS built (`RagTableView.tsx` + `RagTableChart.tsx` in
ml-portfolio's shared `src/components/`, wired in via `RagSourceCard.tsx`), just not visible
from a first grep scoped only to `app/tools/multimodal-rag/*.tsx`. Corrected the stale memory
file with this finding and a note to always also check `src/components/Rag*.tsx` for
Multimodal RAG features, not just the tool's own page directory.

## Part 2 — The three Part-230 pending fixes

All three were implemented, verified locally (mocked, zero API cost) before any deploy, then
deployed and HF-verified.

**Fix 1 — region-sharpen resize-down was lossy.** `_sharpen_region`'s paste-back resize
(`result_crop.resize((right-left, bottom-top))`) had no `resample=` argument, so PIL used its
default (NEAREST, not a high-quality filter) to resize a crop that had JUST been sharpened —
throwing away exactly the fine detail the whole call existed to recover. Whole-image sharpen
never hits this resize path at all (returns Gemini's output directly), which is why it could
look crisper for the same blur. Fixed: `Image.LANCZOS`.

**Fix 2 & 3 — TEXT/GRAPHIC misclassification and flip-flop.** `_classify_and_describe` was a
single vision-cascade call, so it could misclassify real text as GRAPHIC (~1/3 runs on an
earlier invoice test, silently suppressing a legitimate "high" confidence result) or flip-flop
on a genuinely ambiguous image. Fixed by running the classify call on BOTH independently-
sharpened regions CONCURRENTLY (`ThreadPoolExecutor`, so wall-clock cost stays ~1 call, not
2 — avoids reintroducing the earlier 60s-timeout regression) and only suppressing confidence
when BOTH calls agree GRAPHIC. Explicitly did NOT use "OCR-agreement overrides
classification" — that was considered and rejected: a pure graphic can make OCR hallucinate
the SAME fake reading twice (shared bias from one input image), which would produce a false
"high" asserting fabricated text as CONFIRMED, strictly worse than the current false "low".

Verified locally via mocked unit tests before deploy (disagreement → TEXT default,
agreement → GRAPHIC-suppressed, both behaving as designed) — zero live API calls for this
verification pass.

Deployed as `e34a71a` (ML-Unified). HF-verified `RUNNING`.

## Part 3 — Playwright test surfaces a real (unrelated) Gemini timeout, twice

User asked to Playwright-test the fix against the real car photo (found at
`/Users/wrks/Downloads/car.jpeg`, copied into `.playwright-mcp/` since Playwright's file
upload only allows configured root directories). First region-draw attempt used wrong
coordinates (grabbed the wheel/bumper, not the logo) — let it run to completion rather than
killing it, since a running request shouldn't be aborted mid-flight. Redrew with corrected
coordinates (badge is at ~77% across, ~57% down the car image, not ~55%/60% as first
guessed) — this one hit "Sharpen is temporarily unavailable."

Root-caused via real Space logs (not guessed): `routers.rag.mm_deblur WARNING Deblur failed:
The read operation timed out` — Gemini's own API never responded within `_call_gemini`'s
`httpx.Client(timeout=60)` budget. No Gemini HTTP log line at all near the failure (successful
calls always show one), confirming Gemini itself hung, not a code path issue. This line was
untouched by either of today's fixes. Redrew the region a third time (coordinates already
correct) — SAME error, SAME log signature, twice in a row.

Per CLAUDE.md's "two failures = stop" rule, stopped retrying live testing at that point.

## Part 4 — The billing incident

User asked directly why repeated sharpen requests were fired back-to-back. Honest
reconstruction: 3 synthetic curl sanity checks, then the Playwright car-photo test (2 region
attempts + 1 direct curl call to isolate frontend-vs-backend after the first failure), all
within ~15-20 minutes — each step felt individually justified ("debug first, never guess") but
were never added up as a batch against a billed, shared-quota API.

User then reported the real consequence: **Gemini billing account down to ₹247 remaining**,
called the behavior reckless. Billing dashboard screenshot showed ₹607.92 total for the month
(Aug 1-13), concentrated on Aug 9-11 (₹370 + ₹210), zero on Aug 13 (today, likely posting lag).
A follow-up "Gemini Cloud Assist" summary confirmed ₹594.54 of that (98%) came from ONE SKU:
"Generate_content image output token count for Gemini 3.1 Flash Lite Image" — i.e. entirely
the image-generation model used by sharpen/deblur and (unused) ai-fill, accumulated across the
whole days-long effort of building this feature, not concentrated in this one session. This
context didn't change the core mistake (batch-testing a billed endpoint without asking), which
stands independent of which day's invoice line it landed on.

**Corrective action taken:** saved `feedback_billed_api_testing.md` to persistent memory — the
standing rule going forward is no live calls to a paid/metered API for self-directed
verification without asking first, every time, one call at a time with explicit go-ahead
before each one; local mocked unit tests are the default verification method for logic
changes (as already demonstrated working cleanly for fixes 2 & 3 above).

## Part 5 — Daily call-budget guard (built, zero live cost)

User asked for a hard technical guardrail so this can't recur regardless of who or what
triggers repeated calls. Built `_image_gen_budget.py` (new, 45 lines) — an in-memory daily
call counter shared between `mm_deblur.py` and `mm_ai_fill.py` (the only two callers of
`gemini-3.1-flash-lite-image`), default cap 40/day via `GEMINI_IMAGE_DAILY_CAP` env var
(user confirmed 40 is fine, no override needed). A call over the cap is rejected with a clear
429 message BEFORE any network request — a blocked call costs nothing. Both files' broad
`except Exception` handlers updated to re-raise `HTTPException` as-is first, so the 429
message isn't flattened into the generic "temporarily unavailable" text.

Verified entirely locally (mocked counter test: 3 calls under cap=3 pass, 4th and 5th
blocked with 429; confirmed `_call_gemini` actually invokes the gate) — zero real API calls
for this verification. Deployed as `c94a991`. HF-verified `RUNNING` + `/docs` 200 only (no
live billed call made to verify the happy path, per the new rule — reasoned that a live call
here would just re-confirm something the code structure already makes near-certain, for real
cost, so skipped it).

## Part 6 — The actual logo-recognition fix

User pushed back hard on the region-description feature's accuracy: a real test on the actual
Nissan-badge crop returned "Identified as: 'black and white abstract pattern'" instead of
recognizing the logo — reopening the exact question that opened this whole feature ("how does
a vision model know it's Nissan"). Root cause, once actually dug into:

1. `_classify_and_describe` was fed the TIGHTLY-trimmed paste-back region (`region_a`, just
   the badge + a small margin) — not the wider `_CONTEXT_PAD`'d crop actually sent to Gemini
   for sharpening. A badge cropped down to almost nothing loses the surrounding grille/car
   context a vision model needs to recognize it, the same reason whole-image sharpen could
   correctly read "NISSAN" elsewhere in a full photo (per Part 230's docstring).
2. The call was going through `_vision_cascade_raw` (Groq `qwen3.6-27b` first, then Mistral
   `mistral-medium-latest`, Gemini only as last-resort fallback) — user correctly called this
   out as using a weaker model than expected, given the feature already pays for Gemini on
   the sharpen call itself.

Fixed both: `_attempt()` now also returns the wider context crop (`context_a`/`context_b`),
used ONLY for classification, never for OCR or the paste-back. Classification now calls
`gemini-3.6-flash` (a plain image-understanding model, separate from the image-generation
model used for sharpening) DIRECTLY instead of the cascade. Split the classify/describe logic
into a new `mm_deblur_classify.py` (109 lines) since the combined edit pushed `mm_deblur.py`
over the 400-line cap (415 lines) — file back to 312 after the split. This new classify call
is deliberately NOT gated by the image-gen daily budget cap (different model, much cheaper
cost profile per the budget module's own docstring, which explicitly scopes itself to "the
ONLY two callers of that specific [image-generation] model").

Verified locally (mocked): text-path regression test still passes after the refactor: Gemini
plain-text response format ("TYPE: GRAPHIC\nDESCRIPTION: ...") parses correctly through the
moved code. Zero live API calls for this verification. Deployed as `3df37cc`. HF-verified
`RUNNING` + `/docs` 200 only, no live billed call made (per the standing rule — user's own
next live test, at their own initiative, is the real verification here).

## A correction mid-thread, worth recording

User showed the actual badge crop and said "not nissan logo" — visually it read as an
Infiniti wing/oval emblem to me, not Nissan's round badge, so I said so. User then corrected
back: it IS Nissan (an Indian-market Nissan Magnite badge design, per the car — not the more
familiar circular Nissan logo). Accepted the correction without arguing further — the user
knows their own vehicle, and misreading an unfamiliar regional badge design was a genuine,
reasonable mistake on my part, not evidence against anything else in this session.

User then reported real-world confirmation: whole-image sharpen (full photo context) DID
correctly identify "Nissan" on a repeat test, consistent with the context-matters theory this
session's Part 6 fix was built on.

## Commit hashes (this session, chronological)

**ML-Unified (backend):**
1. `e34a71a` — LANCZOS resize fix + dual-corroborated region classification (Part 2)
2. `c94a991` — daily call cap on Gemini image-editing model (Part 5)
3. `3df37cc` — logo/brand identification via Gemini directly, wider context (Part 6)

No frontend (ml-portfolio) commits this session.

## Memory changes this session

- Corrected `project_realworld_usecases.md` — confirmed all 11 backlog items actually built
  (table→chart included), added a note to check `src/components/Rag*.tsx` when verifying
  Multimodal RAG features.
- New `feedback_billed_api_testing.md` — never batch live calls to a paid API for
  self-directed verification without asking first; local mocked tests are the default.

## Pending / not yet resolved

- Region-sharpen's logo/brand identification fix (Part 6) has NOT yet been live-verified by
  either party at the time this log was written — user was about to try "Sharpen region…"
  again on the real Nissan badge when this save request came in. Worth a follow-up check.
- The MMRAG backlog's ~7 still-unbuilt rows (MMRAG-07, 16, 17, 18, 19, 21, 22) — untouched
  this session, still open per `project_mmrag_feature_backlog.md`.
- The "Add content into a removed region" plan (`plan-multimodal-rag-curious-charm.md`) is
  stale in one respect: it describes AI-fill via free FLUX/gradio_client, but `mm_ai_fill.py`
  already exists and is live, built differently (calls paid Gemini directly). The plan's
  text/image-paste parts (pure client-side, free) still look unbuilt. Not touched this
  session.