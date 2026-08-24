# Session Part 215 — 2026-07-30 / 2026-07-31

## Context
Continued from Part 214 (MMRAG-13/14/15 + Detect Faces button). This session
covered three real bug fixes found through live Playwright testing on
existing features, then built and hardened a new MMRAG backlog pivot
(MMRAG-20 — Contract/Invoice Reconciliation Assistant).

## Bug 1 — Small/distant faces not detected

User uploaded a UN General Assembly video and asked why "Detect faces"
didn't appear on a wide-shot frame. Investigated with a direct API
re-ingestion of the exact frame: the detector found "Man" and "Clothing"
but no "Human face" at all — not filtered by confidence, genuinely never
fired, because a face that's a small fraction of a wide shot doesn't clear
threshold at the model's fixed 640x640 input resolution.

**Fix**: `mm_objects.py` — when a person-class box (Man/Woman/Boy/Girl/
Person) is found and no face was detected in the full frame, crop to that
person's box (with padding) and rerun the SAME detector on just the crop,
restricted to searching for "Human face" only. Capped at 4 person-crops per
image, only triggers when needed. Refactored `detect_objects()` into
reusable `_infer_raw()`/`_decode_detections()` helpers to share the
inference pipeline between the full-frame pass and the crop pass.
Verified: the same UN frame that previously returned nothing now detects
"Human face" at 42.5% confidence, both locally and on the live redeployed
Space. Commit: `63ead0d`.

## Bug 2 — Hallucinated JSON key leaking raw JSON into captions

While testing, a PDF page's caption showed a literal raw JSON blob
(`{"cnotation": "..."}`) instead of clean prose. Root cause: the vision
model returned valid JSON but invented its own key name instead of
`"caption"`, which missed both the exact-key check and the existing
`_ALT_CAPTION_KEYS` fallback list, so `extract_caption()` fell all the way
to dumping the raw JSON string.

**Fix**: `mm_caption.py::extract_caption()` — added a last-resort fallback:
if no known key matches, use the longest string value in the parsed JSON
object (almost certainly the misnamed description). Verified against the
exact failing raw response plus two regression cases (real `"caption"` key,
plain non-JSON text) before deploying. Commit: `062b460`.

## Bug 3 — Only one of multiple same-label detections highlighted

User asked "where is goldfish?" on an image with two separate goldfish
detections (87% and 65% confidence) — only one got a bounding box.
`matchObjectToQuestion()` in `MmRagRunner.tsx` only ever returned a single
`DetectedObject`, even when the question matched a label shared by several
detections.

**Fix**: renamed to `matchObjectsToQuestion()`, returns ALL detections
sharing the matched label (not just the first/highest-confidence one).
`CitationThumbnailPanel.tsx`'s `matchedObject` prop became `matchedObjects`
(array), rendered with the same multi-box mapping pattern the "Detect
faces" toggle already used. Verified live: both goldfish now boxed
("Goldfish (65%)" and "Goldfish (87%)"). Commit: `9646a9d` (ml-portfolio).

## MMRAG-20 — Contract/Invoice Reconciliation Assistant

User asked "what's next" — most of the MMRAG backlog turned out to already
be built (re-audited MMRAG-01 through 06 directly against the code, found
blur detection, contradiction detection, NER, groundedness, query
decomposition, and standalone audio ingestion all already existed but were
never marked done in the tracking memory — corrected it). Remaining real
options were MMRAG-17/18/19/22 (all discussed and explicitly deprioritized
by the user) and the two Tier-4 product pivots (MMRAG-20/21). User chose
MMRAG-20 on my recommendation (its underlying pieces — contradiction
detection, entity extraction — are more mature than MMRAG-21's diarization
dependency).

**Planned via EnterPlanMode** (2 Explore agents + 1 Plan agent, all
findings independently re-verified by reading the actual code): extend the
existing `contradictions.py` (MMRAG-02) in place rather than build new
infrastructure — it already does session-scoped cross-document pairwise
comparison via embedding-similarity + one LLM judge call per candidate.
The one real gap: it pairs ALL cross-source chunks with no role concept,
so 1 contract + N invoices would also flag invoice-vs-invoice differences
as noise.

**Backend build**: `find_reconciliation()` + `POST /rag/reconciliation`
added to `contradictions.py` (172→274 lines). Pairs restricted to
(contract chunk, invoice chunk) only. Candidate pairs where either chunk
has a money/date entity (MMRAG-03, already computed at ingest) are judged
first within the same 6-pair budget. Role (contract/invoice) is a
request-body parameter, not stored server-side — kept out of ingest/Chroma
metadata entirely. Verified with an offline stubbed-logic test (confirmed
contract-vs-invoice-only pairing, boilerplate filtering, correct
flag/no-flag) before any deploy, then a real end-to-end test: synthetic
contract ($50,000/30-days) vs. two invoices — one deliberately mismatched
($52,500/45-days), one matching. Live LLM judge correctly flagged only the
mismatched one. Commit: `29eddb7`.

**Frontend build**: new `ml-portfolio/src/app/tools/contract-invoice-
reconciliation/` — `page.tsx`, `ReconciliationRunner.tsx`,
`ReconciliationDocChipsRow.tsx` (role-toggle chips), `ReconciliationReport.tsx`
(adapted from `ContradictionsPanel.tsx`), `_types.ts`, `userGuide.ts`,
`ReconciliationUserGuideModal.tsx`. Registered in `capabilities.ts`.

Two real corrections made mid-build, not in the original plan:
1. `useRagChat`'s `sessionId` persists to a SINGLE shared localStorage key
   across every tool — reusing it would have silently mixed reconciliation
   uploads into whatever session the user already had open in Multimodal
   RAG. `ReconciliationRunner` manages its own local session state instead
   (this tool has no chat surface anyway).
2. `IngestProgressRail.tsx` gained an optional `hideToggles` prop (default
   `false`, zero behavior change elsewhere) — a "share this with all
   visitors" checkbox doesn't make sense for a privacy-sensitive
   contract/invoice upload.

Commit: `5c4808e` (ml-portfolio). Verified live via Playwright: uploaded
all three fixtures, confirmed role auto-assignment (contract/invoice/
invoice), clicked "Check for discrepancies."

**Real finding from that live run, reported honestly, not hidden**: the
judge model (groq/llama-3.1-8b-instant) ALSO flagged `invoice_2` — which
actually matches the contract — because the contract said "due within 30
days of invoice date" and the invoice said "Due date: 30 days from issue":
same value, different wording, but the small model treated it as a
disagreement. A separate direct-API test with the same fixtures, run
moments earlier, did not make this mistake — model inconsistency, not a
deterministic bug in the pairing logic (which correctly restricted
comparisons to contract-vs-invoice in both runs).

## Follow-up fix (and a mid-fix regression, also caught and fixed)

User chose "improve without adding cost" as the next step, picked fixing
this false positive.

**First attempt**: added a second, independently-worded "confirmation"
judge call — only report a discrepancy if BOTH calls agree it's real.
Verified the AND-gate logic offline (3 stub cases, all correct), deployed,
then re-ran the exact live test **three times** to check consistency.
Result: 2 of 3 runs silently dropped the GENUINE $50,000-vs-$52,500
mismatch entirely — both judge calls happened to disagree on it (the small
model is noisy in both directions, not just toward over-flagging). This
traded false positives for false negatives, which is worse for a
discrepancy report meant for human review: losing a real finding silently
is worse than an occasional false positive the reader can dismiss by
reading the shown source passages.

**Actual fix**: never drop a flagged pair based on the confirmation call.
`find_reconciliation()` now always keeps a judge-flagged pair and adds a
`confirmed: bool` field instead. Frontend shows an amber "Unconfirmed"
badge when the second pass disagreed, rather than hiding the finding.
Verified offline (never-drop behavior) and live (deployed) — the real
mismatch survived even in a run where the confirmation call itself
disagreed (`"confirmed": false` shown, still reported). Also strengthened
`_RECONCILE_JUDGE_SYSTEM` with an explicit worked counter-example of the
exact "30 days" failure mode. Commits: `afc606b` (first attempt, backend),
`e5bfb54` (never-drop fix, backend), `9e7fb41` (confirmed-flag UI,
ml-portfolio).

## Closing discussion — "how can we improve, without cost"

Recommended two free (same-tier, no new spend) options, not yet built:
1. Swap the judge model from `llama-3.1-8b-instant` to
   `llama-3.3-70b-versatile` — already used for main chat answers in this
   same app, same free Groq API key, likely reduces the paraphrase-vs-real
   -mismatch confusion, at the cost of using more of the shared free-tier
   rate-limit budget and being slower per call.
2. Extend `entities.py`'s `_DATE_RE` to capture relative date/term
   patterns ("30 days", "net-30"), which it currently misses entirely
   (only matches calendar-style dates) — would let entity-based candidate
   prioritization actually work for term mismatches, not just money.

Awaiting user's choice; neither has been implemented yet.

## Commit summary

| Repo | Commit | What |
|---|---|---|
| ML-Unified | `63ead0d` | Crop-and-rerun person boxes to catch small/distant faces |
| ML-Unified | `062b460` | Fall back to longest string value when caption key is hallucinated |
| ml-portfolio | `9646a9d` | Highlight every matching detection, not just one (multi-goldfish fix) |
| ML-Unified | `29eddb7` | MMRAG-20 — contract/invoice reconciliation endpoint |
| ml-portfolio | `5c4808e` | MMRAG-20 — Contract/Invoice Reconciliation Assistant tool page |
| ML-Unified | `afc606b` | MMRAG-20 — confirmation pass (first attempt, later found to regress recall) |
| ML-Unified | `e5bfb54` | MMRAG-20 — never drop a flagged discrepancy on confirm disagreement |
| ml-portfolio | `9e7fb41` | MMRAG-20 — surface confirmation-pass disagreement in UI, not hide it |

## Pending / next candidates
- Judge model upgrade (llama-3.3-70b-versatile) for reconciliation +
  contradictions — proposed, not built, zero added cost.
- `entities.py` relative-date-term extraction ("30 days", "net-30") —
  proposed, not built.
- MMRAG-21 (Meeting/Call Intelligence pivot) — considered, not chosen.
- MMRAG-17/18/19/22 — explicitly deprioritized by the user this session.
- MMRAG-11's cut-detection branch and MMRAG-14's real-chart accuracy
  remain unverified against real (non-synthetic/non-fallback) inputs —
  carried over from earlier sessions, still open.
