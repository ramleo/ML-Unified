# Session 2026-07-24/25 — Multimodal RAG Backlog Completion + Answer-Length Caching Design (Part206)

Continuation after Part 205. Picked up mid-backlog (7 of the original 10
pending items were already agreed, this session built most of them one at
a time with live verification after each), then closed with an extended
design discussion (no code yet) about making the Concise/Normal/Detailed
answer-length toggle cache-aware instead of wasting LLM calls.

## 1. Backlog items built and deployed this session, each verified live

1. **Citation page drill-down** — new `GET /rag/page-chunks/{source}?page=N`
   endpoint; every citation with a page number gained a "Show everything
   else on this page" link. Verified live via curl against a real invoice
   upload (ML-Unified `83340dd`, portfolio `0d91e97`).
2. **Confidence-aware answering** — `numbers_disagree()` flags when a
   figure's AI caption and its separate OCR pass cite disjoint numbers for
   the same image; red "Verify number" badge + a system-prompt caveat
   telling the LLM to hedge. Verified with a deliberately mismatched
   caption/OCR pair (`83340dd`).
3. **Table → CSV export** — "Download CSV" link above any Table citation,
   reusing the existing `parsePipeTable()` parser (portfolio `0d7e95d`).
   Verified via a real Playwright download capture matching the source
   CSV exactly.
4. **PII awareness badge** — new `routers/rag/pii.py`; detects
   email/phone/SSN/Luhn-checked-credit-card patterns in a chunk's own
   text, shows an amber "Contains [type]" badge. Detection only — never
   masks or withholds text from the LLM. Verified live with a synthetic
   resume PDF returning `"pii_types": "email,phone,ssn"` (ML-Unified
   `b4a1449`, portfolio `725eee6`).
5. **Answer-length toggle (Concise/Normal/Detailed)** — `answer_length`
   threaded into `build_system_prompt()`; building this surfaced and fixed
   a real staleness bug where `useRagChat`'s `send()` `useCallback` was
   missing several state dependencies (ML-Unified `3b6a37f`, portfolio
   `1d1bfc8`).
6. **Session-scoped "most re-watched moments" replay heatmap** — tracks
   explicit video seeks into 32 time buckets, first shipped as bars, then
   (per user's follow-up ask) rebuilt as a smooth KDE curve (Gaussian
   kernels summed across a 100-point grid) to match a YouTube-style
   "most replayed" look, while staying honestly labeled as session-only
   (no cross-viewer data exists for a private upload). Verified both
   mathematically (peak locations/heights matched exact seek timestamps)
   and visually via screenshot (portfolio `c074f44`).
7. **Manual chunk-type filter** — "Only search: All/Text/Table/Figure/
   Image/Video Frame" chips, implemented as a HARD filter (Chroma `$in`
   where-clause + BM25 post-filter) rather than the existing soft
   `type_boost` re-ranking. Verified live with two documents in one
   session (invoice text + CSV table): filtering to "table" while asking
   about the invoice correctly ignored it and pulled from the CSV instead
   (ML-Unified `318e9e3`, portfolio `7ef47c1`).
8. **Table → chart on demand** — new `RagTableChart.tsx`; auto-detects
   numeric columns (2+ distinct parseable values after stripping
   `$`/`%`/commas), renders a bar chart with column-picker chips when
   multiple numeric columns exist. Verified live: switching from "age" to
   "income" correctly re-plotted with exact matching values (portfolio
   `326d0dc`).

Each item was committed, pushed, and — for backend changes — uploaded to
the HF Space with the Space's serving commit hash explicitly confirmed
against the last upload before any functional test, per standing project
rule. Several rebuilds ran unusually long this session; each time, build/
run logs were pulled directly (`/logs/build`, `/logs/run`) to confirm
health before continuing to wait, rather than assuming.

## 2. Three real bugs found and fixed via live testing, not guesswork

Triggered by the user's own screenshot of a real citation showing raw
`\`\`\`json {"caption": ...` text leaking into a standalone image's
citation, plus a "why is there no table" question:

1. **Standalone images had zero path to a "table" chunk_type.** Root
   cause confirmed by reading `mm_image.py`: only PDFs ever call table
   detection; a flat image always became one "image" caption chunk.
   Fixed via `split_pipe_tables()` — Mistral OCR reconstructs real
   pipe-table markdown when an image has genuine ruled-line/grid
   structure, so that output is now split into its own "table" chunk.
   Verified with two synthetic images: a borderless PIL-text invoice
   correctly still produced `table: 0` (no real grid to detect), a
   properly grid-drawn table image correctly produced `table: 1` with
   accurate parsed rows.
2. **`extract_caption()` leaked raw JSON on parse failure.** Root cause:
   when a response had no closing `}` at all (severe truncation), the
   code never even attempted `json.loads`, so it skipped straight past
   the exception-handling regex fallback to dumping raw text. Fixed by
   restructuring so the regex fallback runs whenever strict parsing
   didn't yield a caption, not only on a thrown exception. Verified with
   direct unit tests reproducing the exact failure shapes (truncated
   mid-string, unescaped inner quote) — both now return clean text.
3. **A related but distinct issue found while testing #1 live**: Mistral,
   under its forced JSON mode, sometimes ignores the requested
   `{"caption": ...}` schema entirely and answers with its own key names
   (`{"description": ..., "text": ...}`) — valid JSON, wrong key. Fixed by
   trying `description`/`summary`/`caption_text`/`text` as fallback keys
   (in that priority order — `text` last, since it usually just
   re-duplicates what the separate OCR pass already covers) before giving
   up to a raw dump. Verified by replaying the exact malformed response
   captured live through the updated function.

All three root-caused with real evidence (HF Space log inspection,
synthetic test images built specifically to isolate the variable in
question, direct replay of the exact captured malformed response) before
writing any fix, consistent with the project's standing debug-first rule.
Commits: ML-Unified `ec987a4` + `70187fa`.

## 3. Judgment calls explicitly flagged and deferred, saved to memory

Four remaining backlog items were deliberately NOT built this session
because each needs an explicit decision first, not a default guess:

- **Shareable session URL** — real privacy wrinkle (whoever holds the
  link gets full, permanent, unauthenticated access to that session,
  PII included) — needs a scope/expiry decision.
- **Ingestion diffing** (detect a re-upload as a "revised version" of an
  existing doc) — needs a definition of "revised" before it can be built
  without risking silently conflating two different documents.
- **XLSX upload support** — needs adding `openpyxl` as a new dependency.
- **Usage/analytics dashboard** — explicitly the "road not taken," needs
  new tracking/storage infrastructure that doesn't exist today.

Saved to memory (`project_realworld_usecases.md`) so these aren't
re-litigated from scratch next session.

## 4. Answer-length caching — full design discussion, verbatim

The user asked a chain of clarifying questions about how the answer-length
toggle *should* behave, ending in a concrete, agreed design — reproduced
here word-for-word per explicit request, since this is a design decision
worth having exact, not summarized.

> **User:** so, if initially it was Detailed, next i click concise, the
> size of chat is reduced and it replaces the Detailed one right?...if i
> again want the Detailed one, it will not be available as it is replaced
> right?

> **Assistant:** Exactly right on both counts.
>
> Click Concise → it silently re-asks the same question with the new
> setting, and the Concise answer **replaces** the Detailed one in place
> — same spot in the chat, same citations refreshed, but the Detailed
> text is gone from view.
>
> And yes — if you then want the Detailed version back, it's not "saved"
> anywhere; clicking Detailed again would just trigger another silent
> re-ask and generate a fresh Detailed answer (possibly worded slightly
> differently than the first one, since it's a new AI call, not a cached
> copy). There's no history of "the three versions of this answer" kept
> side by side — only whichever length you last clicked is visible.
>
> If you'd rather keep all versions and flip between them without
> regenerating (e.g. cache each length the first time it's generated,
> then just switch the displayed text instantly on later clicks), that's
> a different, slightly bigger approach — let me know which behavior you
> actually want before I build it.

> **User:** which of them will not waste llm calls and save the rate
> limit and also help in less work next time?

> **Assistant:** The caching approach (Option B) — cache each length the
> first time it's generated for a given question, then instantly switch
> between already-seen lengths with zero extra calls; only a length you
> haven't asked for yet triggers a new LLM call.
>
> The re-ask-every-time approach would burn a fresh call every single
> time you click a button, even flipping back to a length you already saw
> seconds ago — wasteful and slower. Caching means: ask once → click
> through Concise/Normal/Detailed as much as you want after that → only
> the *first* time you land on each one costs a real call; every repeat
> click after that is instant and free.
>
> Tradeoff worth knowing: the cache only lives for that one question in
> that one session (not persisted anywhere), so it's zero-cost only
> within a single Q&A turn, not across new questions. Want me to build it
> this way?

> **User:** explain in simple terms - """Tradeoff worth knowing: the
> cache only lives for that one question in that one session (not
> persisted anywhere), so it's zero-cost only within a single Q&A turn,
> not across new questions."""

> **Assistant:** Simple version: the "remember this answer so I don't
> have to ask again" trick only works *within one question*.
>
> So if you ask "what is the video about?" and click through Concise →
> Normal → Detailed, each one gets generated once and then remembered —
> flipping between them costs nothing extra.
>
> But the moment you ask a *different* question — even something small
> like re-asking "what is the video about?" a second time later — that's
> treated as brand new. It starts the caching fresh from zero; nothing
> from the earlier question carries over. And if you refresh the page or
> come back later, all of that cached memory is gone too — it's not
> saved to disk anywhere, just held temporarily in that one browser tab
> for that one question.

> **User:** so same is the case with option A right and additionally llm
> calls are also wasted right?

> **Assistant:** Yes, exactly right on both points.
>
> **Same limitation:** Option A also doesn't survive a page refresh or a
> new question — nothing is saved anywhere in either approach, so that
> part is identical.
>
> **Plus it's worse on LLM calls:** Option A has no memory *at all*, not
> even within the same question. So if you're sitting on one question and
> click Concise → Detailed → Concise again, that's **three separate LLM
> calls** — including the third one, even though you already saw that
> exact Concise answer two clicks ago. Option B would only make **two**
> calls there (one for Concise, one for Detailed), since the second
> Concise click would just redisplay what's already cached.
>
> So Option A wastes calls even in the best case for it, while Option B
> only ever calls once per length, per question — same "doesn't persist
> long-term" ceiling, but meaningfully cheaper while you're actively
> using it.

> **User:** can you keep a possibility open so that in future if i have
> option to persist it, i should be able to modify the code accordingly
> without any problem?

> **Assistant:** Yes — easy to design for that from the start without
> overengineering it now. The key is to not scatter the caching logic
> directly into the UI code, but put it behind one small, clearly-named
> access point:
>
> Each question's cached answers live in one object shaped like
> { concise?: {text, sources}, normal?: {...}, detailed?: {...} }, keyed
> by the actual question text (not just its position in the list).
> All reads/writes go through two small functions — something like
> getCachedAnswer(question, length) and setCachedAnswer(question, length,
> answer) — instead of components touching the storage directly.
> That's the whole trick: today those two functions just read/write a
> plain in-memory JS object, so it works exactly as described (gone on
> refresh). Later, if you decide to persist it, you'd only ever need to
> change what's inside those two functions — swap the plain object for
> localStorage, or for a real backend call — and nothing else in the app
> needs to know or change, since every other piece of code only ever
> talks to those two functions, never to the storage directly.
>
> Want me to go ahead and build the toggle-caching feature now, structured
> this way?

> **User:** note in down and save all the above conversations including
> the latest one in "Conversations/" folder, and the latest one should be
> aded word to word, got it?

(This file is the result of that request — the design chain above is
reproduced verbatim per the explicit instruction; sections 1-3 summarize
the rest of the session in the established terse style.)

## 5. Pending at end of session

- The answer-length caching feature (design agreed above) has **not**
  been built yet — waiting on explicit go-ahead.
- Four backlog items remain deliberately deferred pending judgment calls
  (see section 3).
- No other open threads.
