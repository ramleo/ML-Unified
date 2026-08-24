# Session 2026-07-25 — Shareable Links Hardening, Analytics Dashboard, Feature Brainstorm (Part207)

Continuation after Part 206. Picked up the deferred judgment-call backlog one item
at a time (each confirmed before building), closed out the entire Multimodal RAG
backlog, then shifted into open-ended feature brainstorming for resume/portfolio
value — including web research and one sensitive feature request that was
investigated and redirected rather than built as literally asked.

## 1. Shareable session URL — built, then hardened twice more

1. **Base feature** (24h expiry, warning dialog, owner-only revoke — the three
   decisions the user picked via clarifying questions): new `routers/rag/share.py`
   (create_share/resolve_share_token/revoke_share), `QueryRequest.share_token`
   resolved to the owning session_id inside `_sse_generator` before any retrieval —
   zero changes to retrieve.py needed. Frontend: `ShareSessionPanel.tsx` (share/copy/
   revoke) + a `?share=<token>` URL param puts `MmRagRunner.tsx` into a read/chat-only
   view. Known, documented limitation: a shared viewer gets full chat + citations but
   not the page-thumbnail preview or per-document summary panel (those depend on the
   uploader's local React state, deliberately not persisted server-side). Verified
   live end-to-end via Playwright: link created → opened in a second tab → correct
   grounded answer → revoked from the owner tab → viewer's next question correctly
   rejected (ML-Unified `2451b56`, portfolio `cf6800e`).
2. **Traceable watermark**: user asked what stops a screenshot; explained no
   client-side technique actually prevents one (drew the DRM-video contrast — that
   protection lives in a licensed hardware/codec path that doesn't exist for HTML
   text) — the realistic alternative is traceability, not prevention. Built
   `ShareWatermark.tsx`: a faint, repeating tiled overlay (share-token prefix + date)
   over the chat/citation area, shared-view only. Verified live: 60 tiles rendered
   correctly, owner's own tab confirmed clean (portfolio `52e02e5`).
3. **IP-lock + PII redaction**: user asked "how to make it safe even if I share it
   with someone" — proposed both, user said "both." IP binding: a token binds to
   whichever IP resolves it first, rejects a different IP after that, never
   binds/blocks on an undetectable IP. PII redaction: new `redact_pii()` in `pii.py`
   applied to BOTH the LLM's context and the citation text itself (redacting only
   one side would leave the raw value visible in the other) — gated on
   `redact = bool(req.share_token)`, so only shared viewers are ever redacted.
   Mid-build correctness catch: these additions pushed `query.py` to 414 lines, over
   the 400-line cap — split `/health`/`/prepare-jina` into new `routers/rag/health.py`
   (back to 359). Verified live: real email/phone/SSN redacted in both the citation
   AND the AI's own answer for a shared query; spoofed-IP query correctly rejected;
   same-IP repeat query correctly allowed (ML-Unified `210c729`, portfolio `1794976`).

## 2. Ingestion diffing — resolved the "revised version" judgment call

Match rule: same filename OR high text-similarity (user chose "both"). Action:
always ask before doing anything, never auto-replace (user's explicit choice).
`_find_revision_candidate()` in `mm_ingest.py` compares a new upload's filename and
first-4000-chars text (difflib, 0.65 threshold) against other docs in the SAME
session only. Purely informational — the `done` event's `possible_revision_of`
field drives a `RevisionPromptBanner.tsx` ("Replace old" / "Keep both"). These
additions pushed `MmRagRunner.tsx` to 419 lines — extracted `RevisionPromptBanner.tsx`
and `DocumentChipsRow.tsx` (back to 358). Unit-tested 5 cases, then verified live:
identical re-upload → `same_filename` (1.0), renamed-but-identical copy →
`similar_content` (1.0), unrelated CSV → no flag; Playwright confirmed the real UI
banner + "Replace old" + exactly one document remaining after (ML-Unified `32db663`,
portfolio `8bfbf58`+`d299ad6`).

## 3. Usage/analytics dashboard — the last deferred backlog item, then redesigned

Decisions (via clarifying questions): in-memory only (resets on restart, no external
DB), public page, aggregate-only (never individual queries/filenames/content),
tracking uploads-by-type + query count/latency/cache-hit-rate + provider mix. New
`routers/rag/analytics.py` (`record_upload`/`record_query`/`GET /rag/analytics`) —
cache hits don't attribute to any provider since no LLM was actually called. New
public page `/tools/rag-analytics`, linked via a "Usage stats" button. Verified live:
curl showed baseline zeros then correct increments; Playwright drove a real UI
upload+question and confirmed the dashboard picked up the new counts (ML-Unified
`7c23de9`, portfolio `439d5f2`+`623473c`).

Same day, redesigned purely visually (same data/endpoint) per an explicit design
brief the user asked me to lay out first, then approved: added `lucide-react` as a
new dependency (framer-motion was already installed) — gradient stat cards with
per-metric icons/colors, animated count-up numbers, an interactive SVG donut chart
for provider mix (hover shows exact count/share), animated fill-in bars, a skeleton
loading state, and per-panel empty states. Split into
StatCard/ProviderDonut/UploadTypeBars/AnalyticsSkeleton/EmptyState/useCountUp to keep
`page.tsx` small. Verified live via screenshot + a functional hover check (donut
center swapped from "2 total" to "1 groq" on hover) (portfolio `cd79b88`+`9dc989b`).

**With XLSX explicitly skipped by the user ("skip xlsx, it is not necessary right
now"), this closes the entire Multimodal RAG backlog** and the full "Real-World
AI/ML Use Cases" shortlist except LLM Fine-tuning Pipeline and Time Series
Forecasting (both still not started, both need GPU access).

## 4. Feature brainstorm — web-researched, nothing built yet

User asked for additional resume-worthy features (documents/images/video/NLP/NLU or
any novel idea), explicitly asking me to search the web and think of something not
already common. Three rounds of research (2026 AI-engineer hiring trends, GraphRAG/
agentic-memory/video-RAG research, audio/meeting-summarizer market data) grounded a
21-item backlog spanning cross-document contradiction detection, agentic query
decomposition, answer-groundedness scoring, visual grounding, temporal video moment
retrieval, speaker diarization, standalone audio ingestion, multilingual Q&A,
Fourier-transform-based blur/scene-cut/denoising techniques, and two real-use-case
pivots (a Contract/Invoice Reconciliation Assistant and a Meeting/Call Intelligence
Assistant) — full list and rationale saved to `project_realworld_usecases.md`.

**One request investigated and redirected rather than built as asked**: the user
asked whether a feature could tell if someone in a video is being genuine or lying,
then explicitly asked for a reliability probability, framing it as "internal, not
commercial." Researched real numbers: human baseline ~54% (barely above chance, Bond
& DePaulo meta-analysis of ~1000 studies), published ML approaches average ~60-67% in
realistic conditions (the rare 90%+ claims come from lab-acted-lie datasets that
don't generalize — a known limitation called out in systematic reviews), voice-stress
analysis specifically performs near-chance in real field conditions (the same reason
polygraphs are legally inadmissible). Explained clearly that "internal use" changes
legal exposure but not the underlying accuracy — a near-chance signal misleads
equally either way. Agreed fallback, not yet built: an honestly-labeled "confidence/
hesitation cue" feature showing the real ~55-65% accuracy ceiling directly in the UI,
never a clean genuine/not-genuine verdict.

## 5. MMRAG Feature Backlog — saved as a named, ID-referenceable table

User asked for the full brainstormed list consolidated, prioritized into a build
order, and saved as a table with a name to reference in future sessions. Saved to
memory as `project_mmrag_feature_backlog.md` (MMRAG-01 through MMRAG-21, tiered by
build-first-ness), indexed in `MEMORY.md`. Reproduced here word-for-word, exactly as
saved to memory, per the explicit "copy paste word to word" instruction:

# MMRAG Feature Backlog

Brainstormed 2026-07-25, web-researched against 2026 AI-engineer hiring trends. Reference
any row by its ID (e.g. "let's build MMRAG-07") in future sessions — full rationale for
each idea also lives in project-realworld-usecases.

| ID | Feature | Category | Tier | Effort | Notes |
|----|---------|----------|------|--------|-------|
| MMRAG-01 | Blur/quality detection at upload (Fourier high-frequency energy) | CV + Fourier | 1 | Low | No GPU/model needed — pure NumPy/OpenCV FFT, self-contained, demoable before/after |
| MMRAG-02 | Cross-document contradiction detector | NLP/NLU | 1 | Medium | Extends existing per-figure number-mismatch logic to cross-document scope; top "novel" pick |
| MMRAG-03 | Domain-specific NER (medical/legal/financial entities) | NLP/NLU | 1 | Medium | Called out in research as a hiring differentiator vs. generic NER |
| MMRAG-04 | Answer groundedness scoring (mini Self-RAG) | NLP/NLU | 1 | Medium | Ties directly to the 2026 "evaluation is a resume must-have" trend |
| MMRAG-05 | Query decomposition for compound cross-doc questions | Agentic RAG | 2 | Medium | Entry point into real agentic RAG — 2026's fastest-growing keyword |
| MMRAG-06 | Standalone audio ingestion (podcast/call/voice memo) | Audio | 2 | Low-Medium | Whisper pipeline already exists in mm_video.py — mostly decoupling, not new |
| MMRAG-07 | Visual grounding on citations (bounding box on source image) | CV | 2 | Medium | One extra vision call per citation |
| MMRAG-08 | "Why was this cited" trace panel | Explainability | 2 | Medium | Exposes dense/BM25/rerank/type-boost scores — most RAG demos are a black box here |
| MMRAG-09 | Temporal moment retrieval for video (timestamp + jump-to) | Video | 3 | High | Maps to active 2026 VideoRAG research, not yet commoditized |
| MMRAG-10 | Speaker diarization on video/audio transcripts | Audio/NLP | 3 | Medium-High | Real market demand (meeting-summarizer tools) |
| MMRAG-11 | FFT-based scene-cut detection for smarter frame sampling | CV + Fourier | 3 | Medium | Formalizes near-duplicate-frame skipping via frequency-domain frame diffing |
| MMRAG-12 | Multilingual Q&A (answer in asker's language) | NLP | 3 | Medium | Whisper already supports multilingual transcription |
| MMRAG-13 | Region-level captioning (segment image, caption per region) | CV | 3 | Medium-High | Chart vs. logo vs. photo captioned separately |
| MMRAG-14 | Chart data extraction (actual numeric values, not description) | CV | 3 | High | Needs chart-understanding model/technique, not just captioning |
| MMRAG-15 | Face detection + redaction for shared sessions | CV + Privacy | 3 | Medium | Visual counterpart to existing text PII redaction on shared links |
| MMRAG-16 | Near-duplicate frame detection (perceptual hash) | CV | 3 | Low-Medium | Simpler precursor/companion to MMRAG-11 |
| MMRAG-17 | Frequency-domain denoising for scanned documents | CV + Fourier | 3 | Medium | Removes halftone/moiré artifacts before OCR |
| MMRAG-18 | FFT over usage-analytics timestamps (periodicity detection) | Analytics + Fourier | 3 | Low | Fun tangent on existing analytics dashboard data, not core RAG |
| MMRAG-19 | Confidence/hesitation cue feature (honestly-labeled, NOT a lie detector) | NLP + Audio + CV | 3 | Medium-High | Must show real ~55-65% accuracy ceiling in UI; never a genuine/not-genuine verdict — see project-realworld-usecases for full research/rationale |
| MMRAG-20 | Contract/Invoice Reconciliation Assistant (real-use-case pivot) | Product pivot | 4 | High | Combines MMRAG-02 + existing number-mismatch + multi-doc RAG into a focused AP/AR product story |
| MMRAG-21 | Meeting/Call Intelligence Assistant (real-use-case pivot) | Product pivot | 4 | High | Combines MMRAG-06 + MMRAG-10 + existing video pipeline into a standalone tool |

**Tiers**: 1 = quick wins, build first (small/self-contained, high demo value). 2 = medium
lift, strong agentic/multimodal signal. 3 = bigger or more novel/research-adjacent lifts.
4 = product pivots that reframe existing capability rather than add a new feature.

**How to apply:** When asked "what's next" for Multimodal RAG, offer Tier 1 items first
unless the user asks for a specific ID or a pivot (Tier 4).

## 6. Pending at end of session

- Nothing in the MMRAG Feature Backlog has been built yet — pure brainstorm, awaiting
  an explicit "build MMRAG-XX" decision.
- The confidence/hesitation-cue fallback (MMRAG-19) was agreed to in principle but
  not scoped or built.
- Real-world use cases shortlist: only LLM Fine-tuning Pipeline and Time Series
  Forecasting remain unstarted (both need GPU access) — unrelated to this session's
  work.
