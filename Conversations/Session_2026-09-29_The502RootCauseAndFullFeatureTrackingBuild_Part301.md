# Part 301 — The 502 root-cause (not OOM), logging finished, and per-tool feature tracking built end-to-end

Continues [Part 300](Session_2026-09-28_MMRAGAuditAndTheLoggingActivationSweep_Part300.md).
2026-09-29. Started by trying to live-verify step 4 (`citation_click`); the mmrag
Space was 502-flaky, which turned into the session's spine: **I misdiagnosed the
502s as OOM, the user's Space logs disproved it, and the real cause was
worker-starvation from an always-failing Mistral call.** Then finished the logging
vocabulary (steps 5–6 + gap-closers), and designed + built + verified a whole new
**per-tool feature-tracking** system (phases 0–3, including an RPC-backed dashboard).

Through-line: **the logs beat my theory.** Every confident-sounding inference this
session that wasn't backed by direct server evidence was wrong or incomplete; the
wins came from the user's raw logs and from reading the source.

---

## 1. The 502 misdiagnosis — and the correction

Step-4 `citation_click` couldn't be verified: `/rag/mm-ingest` 502'd in the browser
while `/health` was 200. I curled the endpoint directly — it worked once, then
502'd — and concluded **OOM**: the multimodal models (jina-v3, CLIP, SAM2, Whisper)
loading into a memory-limited Space. I even called it "confirmed with direct curl
evidence." **That was an inference stated as fact — the exact thing memory warns
against.**

Then the user pasted the actual Space logs. They disproved OOM outright:
- **No crash, no restart, no exit-137, no re-print of model loading** — one
  continuous process across hours.
- **Every `mm-ingest` that reached the app returned 200** (corpus grew 48→51).
- The browser's 502s **never appear in the app logs** → they were **HF proxy**
  responses for requests that never got a worker, i.e. **worker starvation**, not a
  crash.

What was hogging the worker: `/document/analyze` ran constantly, and **Mistral
failed on every call** — `mistral-medium` 429 (retried 3× with backoff, ~2.5s) then
`mistral-large` 403 (`tier_not_allowed`) — before Cohere (which works) even started.
Also true for vision (`_mistral_vision_raw` 429 → Gemini did it anyway). So every
analyze burned ~4s failing on a provider that could never succeed, holding the
single worker and bouncing concurrent ingests with proxy 502s.

**Corrected diagnosis (also from the logs, not a guess):** for a plain *text* PDF,
ingest loads only the text embedder — CLIP/SAM2 are lazy/other-tool, Whisper is a
Groq API call, captioning is an API. My "spin up several vision models" claim was
also too broad. See [[feedback_debug_first]], [[feedback_status_claims_need_evidence]].

## 2. Fix — drop always-failing Mistral from the document auto-path

`routers/document/_llm.py` + `_vision.py`: removed Mistral from the automatic
cascade **and** the "simple/fast" tier path (which called `_mistral` first on every
doc). Text path is now **Cohere → Gemini**; vision is **Gemini only**. Mistral stays
BYOK-selectable (same as Groq/Cerebras). No provider *swap* — a removal of dead
config, with the user's explicit OK ([[feedback_no_unilateral_provider_swaps]]).
ML-Unified `3889bd6`, HF-uploaded. **Verified live:** a fresh invoice analyze
reported `provider: "cohere"`, no Mistral lines — the ~4s dead time is gone.

## 3. fitz → pymupdf

The logs also showed `The 'fitz' API is deprecated`. Swapped `import fitz` →
`import pymupdf` (+ `fitz.` → `pymupdf.`) in `_extract.py` and `mm_pdf.py` —
identical API, silences the warning. ML-Unified `e488062`, HF-uploaded.

## 4. Deploy lesson — the HF token moved to the keychain

The first HF upload 401'd: the `hf` git remote is now a **plain URL with no embedded
creds**, and there's no `HF_TOKEN` env or `~/.cache/huggingface/token`. The token
lives in the **macOS keychain** (osxkeychain helper); retrieve it without printing
via `git credential fill` piped into Python. Also found the **old (rotated, leaked)
token hardcoded in the `reference_hf_deploy` memory** — scrubbed it and recorded the
keychain method. See [[reference_hf_deploy]], [[feedback_never_print_tokens]].

## 5. Logging steps 5–6 — vocabulary finished

Wired the last dead vocabulary (ml-portfolio `89f5726`), user's pick = **global/
central** where possible:
- `sample_load` — per-tool (7 sample buttons; `trackSampleLoad`).
- `paste_input` — ONE global `/tools/*` paste listener; length **bucket** only,
  never text; password-audit excluded (§5b).
- `run_retry` — derived **centrally** in `track()`: a run after that tool's prior
  error. Covers trackedFetch + trackToolRun with zero per-tool wiring.
- `scroll_depth` — ONE global hook, 25/50/75/100 buckets.
Verified live (sample_load, paste_input, scroll_depth all four buckets via a real
keyboard scroll). No privacy change — the page already discloses event-type +
enumerated meta + "length not text."

## 6. "Are we logging everything?" → the gap-closers

User pushed on coverage. Honest audit: 30 event types defined, 28 emitted. Two real
gaps closed (ml-portfolio `b9d2a3f`):
- **`error`** — the generic uncaught/render-error event had **0 call sites**; added
  a global `window` error + unhandledrejection handler, content-free (class+source
  only, never message/stack).
- **`feedback`** — NEW event; the RAG Good/Bad answer thumbs only set local state,
  the quality signal was discarded → `feedback{tool,rating}`.
- **Platform tier** — `guide_open` in shared `WorldUserGuideModal`/`AuthorUserGuideModal`,
  `tool_card_click` in `ProjectCard`.

## 7. Per-tool feature tracking — designed, built, verified (phases 0–3)

User wanted feature-level tracking (every bespoke control). Researched first
(Amplitude/Mixpanel): the naive "an event per control" is the **event-explosion
anti-pattern** — the standard is **one generic event + properties**. So: one
`feature_use` event with `{tool, control, action, value?}`, captured by **one
delegated listener** reading a `data-ev`/`data-wt` attribute. Spec:
`docs/FEATURE_TRACKING_SPEC.md` (`b205721`).

- **Phase 0+1** (`1fbc07e`): the listener + privacy line; **reuses the 232 existing
  `data-wt` anchors** → primary controls across all tools tracked with zero edits.
  Verified live.
- **Phase 2** (`c523609`, `9d53acb`, `f5d2cc5`, `2cab8bb`): explicit `data-ev` on
  every tool with a distinctive control beyond its (already-tracked) run button —
  mmrag (visual-action select + ~12 more), EDA sections, text-to-image, meeting
  transcript-seek, video playback, cloak/captcha sliders, gallery/re-id. Added
  `data-ev-value` so button groups (answer-length) carry the choice. Run-and-show
  tools intentionally not tagged. Verified live.
- **Phase 3** (`9a0a333`): RPC-backed dashboard. `supabase/feature_usage.sql` does
  `GROUP BY meta->>'tool','control','action','value'` server-side (feature_use is
  the highest-volume event — never page raw rows to JS); `/api/feature-usage` calls
  it; `AnalyticsFeatureUsage.tsx` renders per-tool ranked control bars + value
  chips in the realtime-analytics dashboard. **User ran the SQL; verified live
  end-to-end** — the panel showed today's real test events with the value breakdown
  (`answer-length → detailed · 1`).

Content-free throughout; only Phase 0 of this needed a privacy-page line.

## Key decisions

- **One `feature_use` event, not per-control names** — the researched, correct
  taxonomy; the detail lives in properties.
- **Reuse `data-wt` for free coverage** — the walkthrough already tagged each tool's
  key controls.
- **RPC over JS-aggregation for the read side** — the highest-volume event must be
  grouped server-side.
- **Mistral removed, not swapped** — dead config (429+403 always), Cohere already
  covered it; asked first.

## Lessons

- **The logs beat the theory.** OOM was a confident inference; the Space logs (no
  restart, every ingest 200) proved worker-starvation instead. Never call an
  inference "confirmed" without direct server evidence.
- **A 502 in the browser that isn't in the app log is a proxy/starvation signal,
  not a crash.**
- **A provider that returns 429/403 on every call is not a fallback — it's latency.**
  It cost ~4s of single-worker time per request.
- **Deploy creds drift.** The HF token silently moved from the remote URL to the
  keychain; a memory file still held the old leaked one. Verify the retrieval path,
  never trust a hardcoded token in a doc.
- **Vercel deploy lag is real per usual** — the API route deployed before the static
  bundle; the dashboard panel "missing" was just the old page bundle for a minute.

## Commits

| Repo | Commits |
|---|---|
| ML-Unified (backend, HF-uploaded) | `3889bd6` (drop Mistral) · `e488062` (fitz→pymupdf) |
| ML-Unified (docs) | `597ae90` (Part 300) · `2417c5c` (logging 5–6) · `92f0c1a` (gap-closers) · `b205721` (feature spec) · `888cb54`/`a652f0a` (phase 2) · `52ced91`/`bb0a55a` (phase 3) |
| ml-portfolio | `89f5726` (logging 5–6) · `b9d2a3f` (gap-closers) · `1fbc07e` (feat phase 0+1) · `c523609`/`9d53acb`/`f5d2cc5`/`2cab8bb` (phase 2) · `9a0a333` (phase 3 dashboard) |

## State after this session

- **mmrag 502s fixed** at the root (Mistral removed) — verified; document analyze
  now Cohere-first, no dead Mistral time.
- **Logging vocabulary complete** — all journey events + gap-closers emitting,
  content-free; steps 1–4 + 5–6 subset verified live.
- **Feature tracking complete (phases 0–3), live** — the realtime-analytics
  dashboard now shows per-tool control usage from the `feature_usage` RPC.
- **Watch:** `feature_use` is the highest-volume event — glance at the events table
  vs the 14-month retention occasionally.
- Backlog untouched otherwise (see [[project_pending_master_list]]).
</content>
