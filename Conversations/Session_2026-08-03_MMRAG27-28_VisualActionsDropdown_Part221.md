# Session Part 221 — 2026-08-03

## Context
Continuation of Part 220. User asked "what next?" — I confirmed the two remaining
backlog items (Adaptive query routing, Evidence-gated agentic verification) and
proceeded through both, then a CV-features research request, then a 6-item
follow-up backlog the user is working through "one by one, just tell" first.
Item 0 (visual-actions dropdown) shipped this session; items 1-5 (signature/stamp
detection, tampering detection, perceptual-hash duplicates, Table Transformer,
Segment Anything) remain unstarted.

## MMRAG-27 — Adaptive query routing

Investigated first: `retrieve.py`'s `reciprocal_rank_fusion()` had `type_boost`
(per chunk-type) but no per-SOURCE-LIST weight — every list (dense/bm25/vision/
graph) contributed identically regardless of what kind of question was asked.
User chose, when asked, to layer **both** classification mechanisms rather than
pick one: an always-on keyword/regex heuristic (new `query_router.py`,
`classify_query_heuristic()` — exact_value/visual/keyword/conceptual buckets,
priority-ordered) plus the existing `expand_query()` LLM call extended to also
emit an intent label in the same response, used only to refine the heuristic's
least-specific "conceptual" fallback. User explicitly chose **backend-only**,
no new UI, since the existing retrieval-trace chips already show which signal
won per citation.

**Built**: `INTENT_SIGNAL_WEIGHTS` table (mild tilts, never hard zeros — e.g.
`exact_value: {graph: 1.6, bm25: 1.1, dense: 0.9, vision: 0.7}`).
`reciprocal_rank_fusion()` gained `list_weights` param. Threaded through
`hybrid_retrieve`/`tiered_hybrid_retrieve`/`multi_query_retrieve` via a new
`expansion_intent` param. `expand.py`'s prompt/return type changed to
`(variants, intent | None)`.

**Verified live** end-to-end, including the harder path: uploaded an invoice +
a synthetic contract sharing "Acme Corp"/"$150.00", confirmed `graph` fired
with `exact_value` weighting; uploaded a synthetic chart (March bar colored
red among blue bars), asked a color question, confirmed `vision` fired at
rank 1 and the LLM answer was correctly grounded ("colored red").

## MMRAG-28 — Evidence-gated agentic verification

Investigation found the backlog item's premise was stale: `query.py` already
had a self-correction retry (from MMRAG-04), not a purely informational badge
— it just only fired on overall "low" groundedness and regenerated blind (never
told the LLM which sentences were flagged). Two real gaps closed, both
confirmed with the user first (the "medium" extension was a genuine cost/
coverage tradeoff — user chose coverage):
1. The far more common "medium" bucket (0.35-0.55) never triggered anything
   even with specific sentences flagged unsupported.
2. The retry wasn't actually evidence-gated — no correction directive.

**Built**: `groundedness.build_verification_note()` — formats flagged sentences
into an explicit correction directive. `citations.build_system_prompt()` gained
a `verification_note` param. `query.py`'s retry trigger extended to
`low OR (medium AND ungrounded_sentences)`; single-retry cap and "keep only if
not worse" safety unchanged.

**Verified**: local parsing tests (empty/populated cases), live deploy + raw
API round-trip, and a real live case where a bait question ("what year was it
invented") returned `level: "medium"` with 4 flagged sentences — direct proof
the new branch evaluates live. Honestly flagged one gap: never got an actual
`retry` SSE event to fire live in this small demo corpus (broadened retrieval
kept landing on identical candidates, so the pre-existing `broadened != chunks`
guard correctly declined) — relied on code-reading for that last leg, said so
rather than claiming full proof.

## User Guide updates (three rounds this session)

1. Added the "Why was this cited?" trace's vision/graph signals + adaptive
   weighting explanation, extended "Key facts chips" to person/org/location +
   8-chip cap. Required first **splitting `userGuide.ts`** (517 lines, over the
   400-line cap) into `userGuide/*.ts` by section.
2. User asked "verify if whatever is there in the guide is there in
   multimodal rag" (asked twice, emphasized) — ran **5 parallel Explore
   agents**, one per guide section, auditing ~47 claims against actual code.
   46 confirmed; 2 real inaccuracies found and fixed: the "Contains [type]"
   PII badge claimed nothing is ever hidden, but shared-link viewers actually
   get it redacted (guide's own Sharing section already said this elsewhere,
   just not cross-referenced here); the API key section claimed it's "sent
   directly to that provider," but it actually transits this tool's own
   backend first.
3. Added a "Self-correction on a weak score" bullet documenting the
   MMRAG-28 retry behavior, which had never been documented even before
   today's extension — verified the actual visible UX (answer streams, then
   clears and restarts) by reading `useRagChat.ts`'s retry-event handler
   rather than assuming.

## Bug fix: "Detect faces" not on the auto-shown preview

Root cause: `MmRagRunner.tsx`'s `handleIngested` hardcoded `objects: null`
when auto-showing the just-uploaded page-1 preview, even though detections
already existed in `notableChunks`. Fixed to look them up. Verified live with
Playwright (local dev pointed at the deployed HF Space backend — this
session's established fast-verification pattern) using a real face photo:
button appeared immediately, click drew a correct box.

## CV features research (text-only, no build)

User asked for online research on further computer-vision additions. Ranked
shortlist delivered: signature/stamp/seal detection and Error Level Analysis
tampering detection as the strongest fits (cheap, extend existing patterns);
perceptual-hash duplicate detection as solid but smaller; Table Transformer
and Segment Anything flagged as real upgrades but meaningfully heavier for a
CPU-only free-tier Space, not pre-emptively justified. Explicitly ruled out
ColPali/ColQwen-style visual retrieval as redundant with the already-shipped
Cohere Embed v4 approach (MMRAG-24), which was a deliberate substitution for
the same torch-free constraint, not a gap.

User then turned this into a 6-item backlog (item 0: a UI redesign; items 1-5:
the CV features above) to work through "one by one, just tell first."

## Item 0 — Visual-actions dropdown (shipped, with 3 live-caught follow-up bugs)

**Design** (plan-mode, approved): for a standalone image/video upload only
(never a PDF's embedded photo), consolidate the scattered "Detect faces" /
"Find visually similar" buttons into one dropdown that also surfaces
already-computed data (caption+OCR, full object list) as new display-only
options — chat stays unchanged. PDF/mixed-content citations keep the
original two buttons untouched.

**Real bug caught mid-build**: the first `isImageOrVideoOnly` heuristic
(chunk-type counts: `table===0 && figure===0`) broke on live testing — a
standalone image containing a readable grid/chart can legitimately produce
its own "table" chunk alongside its "image" chunk (confirmed reading
`mm_image.py`), so chunk counts aren't a safe file-type proxy. Root-caused
to a real gap: the backend already computed `file_type` but **never included
it in the response payload** (`mm_ingest_payload.py`) — fixed by exposing it
and wiring it through `_types.ts`/`IngestProgressRail.tsx`/`EvidenceColumn.tsx`
properly instead of working around it with a fragile heuristic.

**Bug 2 (user-reported, with screenshots)**: clicking the "table" sibling
citation of an image (the false-positive table chunk from Bug 1's root cause)
showed a near-empty dropdown — only "Describe," missing objects/faces/similar
— because the dropdown was reading detection data from the *specifically
clicked* citation's own metadata (empty for a table-type chunk) instead of
the underlying photo's real "image"-type chunk. Fixed by looking up the
sibling media chunk regardless of which citation was clicked; verified live
by reproducing the exact scenario (uploaded the user's own bicycle.jpeg,
clicked citation #2/TABLE, confirmed the dropdown now shows all 7 objects).

**Bug 3 (user-reported, with screenshots, three rounds)**:
1. "Squeezed, lots of unused space" + "labels overlapping" — found the whole
   page was capped at `max-w-7xl` (1280px) leaving most of a wide viewport
   unused, and OIV7's hierarchical taxonomy (Tire/Wheel/Bicycle wheel firing
   on the same physical wheel) put multiple box labels at the identical
   fixed corner position, rendering as garbled overlapping text. Fixed:
   widened page to 1600px, right column 320px→440px, thumbnail max-height
   320→460; labels sharing a near-identical box corner now stack vertically
   by index instead of colliding.
2. "When I don't choose any action, Evidence has space; as soon as I select
   an action, the space is reduced" — Evidence (`flex-1`) and the thumbnail
   row (`shrink-0`) share one fixed-height column, so any growth in the
   thumbnail row when a dropdown action rendered text ate directly into
   Evidence's share. First fix (capping the description/objects block at
   160px + capping the whole row at a 560px max-height) only bounded the
   problem, didn't eliminate it — the row could still grow from 0 to 560px,
   still visibly moving Evidence within that range. **Real fix**: changed
   the row from `maxHeight: 560` to a **fixed** `height: 560` — content
   shorter than that leaves room inside the row itself, content longer
   scrolls inside the row itself, so Evidence's neighboring share can never
   move. Verified with an actual pixel measurement (`boundingBox()`), not
   just a screenshot: the preview panel's y-position was bit-for-bit
   identical (845.15625) before and after selecting a dropdown action.

## Process notes
- User's "just tell" pattern used again this session (the CV research
  request, item 0-5 responses) — text-only until explicit "proceed."
- Two "did you commit and push?" checks this session caught real gaps —
  once genuinely forgotten (Evidence-height/dropdown-data fixes sat
  uncommitted after live verification), fixed immediately both times by
  actually running `git log`/`git status` rather than asserting from memory.
- Repeated pattern of user reporting a UI issue with real screenshots, me
  reproducing the EXACT scenario live (same file, same click sequence)
  rather than a similar-but-different test case, each time before claiming
  fixed — caught real bugs a synthetic test likely would have missed (the
  table-sibling citation dropdown gap specifically only shows up with an
  image whose OCR misreads part of it as a table).
- Local dev pointed at the deployed HF Space backend (via temporarily
  editing `.env.local`, always reverted after) remained this session's fast
  verification loop for frontend-only changes — no waiting on a full HF
  Space rebuild to test UI logic against real backend data.

## Status: all described work is committed, pushed, and deployed
Backend (`ML-Unified`): `8ff1677` (MMRAG-27), `15f5a9f` (MMRAG-28), `ffd87da`
(file_type payload fix) — all pushed to GitHub and uploaded to the
`wram1708/ml-unified` HF Space, rebuilds confirmed via raw-file diff + live
API calls, not just stage=RUNNING.
Frontend (`ml-portfolio`): `94936f6` through `4b48ec0` (8 commits this
session) — all pushed to GitHub, Vercel auto-deploys.

## Explicitly NOT done this session
- Backlog items 1-5: signature/stamp/seal detection, Error Level Analysis
  tampering detection, perceptual-hash near-duplicate detection, Table
  Transformer table-structure recognition, Segment Anything pixel masks —
  researched and scoped in discussion, not built.

## Files touched
**Backend** (`ML-Unified/services/ml-api/`): new `routers/rag/query_router.py`;
modified `routers/rag/retrieve.py`, `routers/rag/expand.py`, `routers/rag/query.py`,
`routers/rag/groundedness.py`, `routers/rag/citations.py`, `routers/rag/mm_ingest_payload.py`.
**Frontend** (`ml-portfolio/src/`): new `app/tools/multimodal-rag/userGuide/*.ts`
(6 files, split from `userGuide.ts`); modified `app/tools/multimodal-rag/userGuide.ts`,
`components/GroundednessBadge.tsx` (read-only, confirmed accurate),
`app/tools/multimodal-rag/MmRagRunner.tsx`, `app/tools/multimodal-rag/EvidenceColumn.tsx`,
`app/tools/multimodal-rag/CitationThumbnailPanel.tsx`, `app/tools/multimodal-rag/_types.ts`,
`app/tools/multimodal-rag/IngestProgressRail.tsx`, `app/tools/multimodal-rag/page.tsx`.
