# Session 2026-07-20/21 — Multimodal RAG Built, Groq Vision Fixes, Live-Debugging Marathon (Part 203)

Continuation after Part 202. Covers: closing out the remaining Document Intelligence
backlog (Groq vision swap + hardening, HITL correction feedback loop with an honest
persistence retraction), building Multimodal RAG from scratch (5th and final item on
the Part 159 real-world use-cases shortlist), and then four rounds of real-user-driven
bug fixing on it, each rooted in actual logs/network captures rather than guesses.

---

## 1. Document Intelligence — remaining backlog closed

- **Groq vision model swap**: `llama-4-scout` retired by Groq (2026-07-17) → 404s in
  logs. Swapped to `qwen/qwen3.6-27b` (Groq's own recommended replacement, confirmed
  via live docs fetch, not memory). Free-tier 8K TPM then 429'd on real image calls —
  fixed with `max_tokens` reduction, then a real live test revealed the model (a
  reasoning model) leaks `<think>...</think>` blocks and can truncate mid-reasoning
  under a tight budget — fixed with `_strip_thinking()` + a terser retry prompt.
  3 real bugs, each found via live Space logs, each fixed and redeployed individually
  (b7f7a09, 910cb11, 28fdfd5-adjacent fixes).
- **HITL correction feedback loop**: field edits POST to `/document/correction`,
  recent corrections injected as few-shot prompt guidance for that doc type — verified
  live that a correction to one receipt's merchant name generalized (not literal-copied)
  to a different receipt's own extraction. Built file-backed persistence to survive
  restarts — then **deliberately restarted the Space via the API to test the claim**,
  proved it does NOT survive (container recreation wipes local disk), and reverted the
  guide/claims to honest "resets on restart" rather than keep a false persistence
  promise. Saved as a standing lesson: `feedback_hf_space_ephemeral_disk.md`.
- Five earlier-listed DI improvements from Part 198's backlog (complexity-based model
  routing, multi-column reading order, image deskew, edit diff view, document history)
  were confirmed already shipped in Part 202 — nothing left there.

## 2. Multimodal RAG — built end-to-end (plan-mode, then implementation)

Last item on the Part 159 shortlist. Planned via Explore + Plan subagents, then built
directly. Deliberately reused existing infra rather than building new:
- Table extraction via Document Intelligence's `find_tables()`.
- Vision captioning via the same Groq→Mistral→Gemini cascade.
- Hybrid retrieval/rerank/citation pipeline from the existing text-RAG system.

**New backend**: `routers/rag/mm_ingest.py` (SSE `/rag/mm-ingest`), `mm_pdf.py`
(per-page PDF extraction), `mm_caption.py` (shared caption-JSON parsing), `mm_similar.py`
(optional CLIP-based "find similar figures," fully isolated from the Q&A path).
Typed chunks: text / table / figure / image, each carrying `chunk_type`/`page`, fed
through the *same* Chroma collection and hybrid retrieval as plain-text uploads.

**A real gap fixed while building, not after**: `RagState` had no per-chunk metadata
list — `bm25_retrieve()` (half of every hybrid/RRF result) had no path to carry
`chunk_type`/`page`/`bbox` at all. Added `state.chunk_meta`, additive everywhere.

**Standalone image upload** added same day (user follow-up): upload a photo directly,
no PDF needed, get a thorough caption, then chat about it. Reused the vision cascade
with a different, more open-ended prompt.

**New frontend**: `/tools/multimodal-rag` — upload zone (PDF or image), two
honestly-caveated toggles ("find visually similar figures," "share with all visitors
right now" — never "permanent," learned from the HITL persistence incident), live
citation thumbnails, inline chat reusing `useRagChat`.

Commits: ML-Unified bc6fef8 (initial), portfolio e5dd172; image upload 6fa6c0e+fce8353
+19566d0+2391a47 / portfolio 58c9158.

## 3. Live-debugging round 1 — 5 user reports, 3 more bugs found chasing them

User reports (with screenshots): static "Thinking…" text, "Find similar figures"
always saying unavailable, a PNG invoice rejected as unsupported, a second upload
leaving the first document's citations/thumbnail still showing (car photo captioned
as a face), and a resume Q&A answering from the *unrelated* general-RAG knowledge base
(clustering/data-leakage docs) instead of the uploaded resume.

Fixes: animated thinking dots; gate the similar-figures button on whether CLIP mode
was actually enabled for that upload; broaden image detection (content-type header +
more magic-byte signatures + PIL fallback); delete the previous upload's chunks before
indexing a new one + verify a citation's source matches the loaded doc before
rendering its thumbnail; add `restrict_to_uploads` to `QueryRequest` so Multimodal RAG
never falls back to the general KB or the open web.

Chasing the KB-leakage fix surfaced **3 further real bugs**, each confirmed via live
logs/diagnostics before fixing, none guessed:
1. The semantic cache keyed only on `tool_context` — a **fixed constant** for this
   tool — so different sessions/documents could share one cache slot and leak answers
   across users. Folded `session_id` into the cache key; `restrict_to_uploads` bypasses
   the cache outright.
2. `rerank()`'s absolute confidence floor (tuned for a large noisy general corpus)
   discarded the *only* retrieved candidate in restrict-to-uploads mode — proven via
   done-event diagnostics (`candidates_retrieved=1, chunks_retrieved=0`). Floor
   disabled for that mode.
3. Page thumbnails rendering at ~2.8% scale — `_RENDER_DPI = 2.0` was meant as a zoom
   *factor* but `_render_page` divided by 72 again (`Matrix(2.0/72, 2.0/72)`). Renamed
   to `_RENDER_ZOOM`, removed the erroneous division; confirmed 1190×1684px output.

Commits: ML-Unified 4119a15+d9e3dc8+422f74b+40fd5aa, portfolio 6c4d3c5.

## 4. Bring-your-own-key surfaced

Discussion: fallback cascade vs BYOK vs both. Recommendation — cascade first (fixes
the default path for every visitor silently), BYOK second (escape valve for someone
who wants a dedicated quota). User: "go with your recommendation." Built the cascade
(generation.py, `stream_with_fallback` — falls through to another provider only if
the failure happens *before* any token streams, never mid-answer), verified live with
a deliberately-invalid Gemini key falling through to Groq. Then BYOK: turned out the
plumbing (`userKey`, `_resolve_key`, the shared `ToolsAIChatSettings` panel) already
existed for the floating assistant — just needed a "Provider" toggle button on the
Multimodal RAG page. Verified via raw network-request-body inspection that the typed
key genuinely reaches the backend. Commits: ML-Unified ce462b5, portfolio 448cf6c.

## 5. Live-debugging round 2 — progress bar, "same answer" question, ugly prefix

Three more reports: no progress bar during extract/embed, every provider giving
similar-sounding answers, and `[Image: user:bicycle.jpeg:...]` showing up ugly in
citation text.

- **Real per-page progress**: PDF extraction had to be restructured so the async SSE
  generator awaits one page at a time (previously one opaque executor call for the
  whole document — impossible to yield mid-extraction). Split `mm_ingest.py` (grew to
  468 lines) into `mm_pdf.py` + `mm_caption.py` to stay under the file-length cap.
  Standalone images (single atomic vision call) get an "indeterminate" flag instead of
  a fake percentage.
- **"Same answer" explained, then made verifiable**: under `restrict_to_uploads`,
  every provider is told to answer *only* from the same short fixed caption — limited
  room for divergence is expected, not a bug. Added `served_provider`/`served_model`
  to the done event (backend already had the data) + an "Answered via X" tag in the UI
  so it's provable, not just asserted.
- **Redundant prefix removed**: `citations.py`'s `build_system_prompt` already labels
  chunks with source/page/type when building the LLM's context, so the
  `[Image: source]`/`[Figure, page N]` baked into the stored chunk text was pure
  noise in the citation UI. Dropped it.

Verified via curl (real per-page SSE events, clean citation text) and Playwright —
network-response inspection proved the browser received the incremental page events
even though completion was too fast to catch via screenshot timing. Commits:
ML-Unified fbf17f2, portfolio cdaf6bf.

## 6. Live-debugging round 3 — Mistral silently ignored

User selected Mistral, pasted their own key, "Answered via" tag showed **groq**.
Root cause: the shared 7-provider settings panel (built for `agent.py`'s "Deep search"
mode, which correctly implements all 7) was reused on the normal chat path, but
`generation.py`'s `open_stream()` only recognized 4 providers — selecting Mistral or
Perplexity raised an internal `ValueError`, caught by the fallback cascade as "failed
before any output," silently discarding the user's real key. Fixed by reusing
`agent.py`'s already-proven `_OPENAI_COMPAT_BASES` pattern instead of reinventing.
Also caught: `generation.py`'s own docstring already claimed to mirror a
"Groq → Mistral → Gemini" cascade, but Mistral was never actually in
`FALLBACK_CANDIDATES` — added it, reusing the `MISTRAL_API_KEY` server secret the
document/vision pipeline already trusts. Perplexity deliberately left BYOK-only, no
server default. Verified live both directions (Mistral now genuinely serves with the
server key; Perplexity with no key still fails with a clean, honest error instead of
silently rerouting). Commit: ML-Unified be9b174.

## 7. Live-debugging round 4 — Cohere, and a real process correction

User reported the identical symptom with Cohere ("Answered via groq" despite
selecting Cohere + a real key). **Assistant jumped to testing with the server's key
instead of investigating the user's actual request** — user stopped this twice ("why
are you guessing?"), correctly identifying that a test using different credentials
than the real failure doesn't constitute evidence about it. Assistant's own accounting:
momentum from the just-completed Mistral fix (where "verify with any call" was valid,
since that was testing a code change) carried over to a bug report where it wasn't
valid (nothing was confirmed broken yet — the question was what happened to *this*
specific request, answerable only from its own logs).

Corrected: pulled real Space logs for the actual request. Found genuine evidence —
Cohere's API returned a real `429`, not a code defect like Mistral's. But also found
a real, separate inefficiency: `expand_query()` was reusing whatever provider/key the
user selected for query expansion, *before* the generation cascade even ran — so
selecting Cohere fired **two** real Cohere calls per question against the same rate
limit (expansion + generation), both 429'ing 118ms apart. Fixed by decoupling
expansion onto a fixed, fast, server-key-only provider (groq/llama-3.1-8b-instant),
never the caller's selection. Also added `classify_error()` (rate limited / invalid
key / timed out / unavailable) and `primary_provider`/`primary_failure` tracking so
the UI can say *why* a fallback happened — "cohere unavailable (rate limited) —
answered via groq" — instead of silently naming a different provider than the one
picked. Verified live: exactly one Cohere call now (down from two), transparency
fields correctly populated. Commits: ML-Unified 304af1f, portfolio f4769ac.

## 8. Key lessons reinforced

- **A previous debugging pattern succeeding is not license to reapply it unexamined.**
  "Verify with a real call" was right for confirming a code fix (Mistral); it was
  guessing when reapplied to "what happened in a specific past request" (Cohere) —
  the right move there is pulling the actual logs, not running a new, differently-
  configured call and treating its outcome as evidence about someone else's.
- **Don't claim persistence without testing the actual failure mode** — a file write
  surviving a local reload proves nothing about surviving a real container restart;
  only an actual restart does (proven twice now: HITL corrections, this session).
- **Shared UI/config (a 7-provider settings panel) can silently outrun what every
  code path actually implements** — the settings panel was correct for one endpoint
  and silently wrong for another; worth checking "is this really wired up" per path,
  not assuming a shared component implies shared backend support.
- **A working fallback can still be a bug in disguise** — the cascade did its job
  (user got an answer) in both the Mistral and Cohere cases, but silently answering
  from a different provider than the one explicitly selected, with a stored key
  ignored, is a real trust/transparency problem even when nothing "crashes."
