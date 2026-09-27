# Part 299 — Handbook rebuild, Testwright copy fixes, and clearing the MMRAG backlog

Continues [Part 298](Session_2026-09-27_TokenLeakAndFourTestwrightFeatures_Part298.md).
2026-09-27. A long build session: rebuilt the stale handbook, fixed stale
Testwright copy, then worked the MMRAG backlog to zero — dropping two items,
shipping three tools, and growing the meeting tool from a lean version into
essentially the full product.

Through-line: **verify against ground truth before claiming done.** Every tool
this session had a real bug caught only by a live/ground-truth check, not by
reading the code — a bad SVG attribute, false-positive notches, a StrictMode
blob revoke. The discipline paid for itself three times over.

---

## 1. Handbook rebuild (the last pending item from Parts 295/297/298)

The committed `public/handbook.md` was built when Text-to-SQL was still a tool
card. Since then it graduated to a platform, Testwright was added, and the 4
security tools gained in-app guides — so the handbook was stale and a *naive*
regenerate would **drop the Text-to-SQL chapter** (its card left
`capabilities.ts`).

**Root fix, not a patch:** the build only made chapters from capability cards,
so graduated platforms had no home. Added `read_platforms()` to
`scripts/handbook_sources.py` (reads `registry.json` + each platform's shipped
world guide `src/app/<route>/guide.ts|worldGuide.ts`, or a deep chapter
`docs/chapters/<id>.md`) and a **new "Platforms" Part 1** in
`scripts/build-handbook.py`, one chapter per deployed world. Result: Text-to-SQL
keeps its chapter (deep chapter), Testwright gets one (quotes `QA_WORLD_GUIDE`,
already 5 stages), `/ml /eda /vision` each get a chapter from their `guide.ts`,
and the 4 security tools appear automatically (they now have `userGuide.ts`). No
prose was invented — every platform chapter quotes an already-maintained source.

Also: fixed `registry.json` Testwright `4`→`5` stages + added Visual, added a 5th
part colour to `09-handbook.css`, bumped `EDITION` to September 2026. Regenerate
is deterministic (CI diff passes). Commit ml-portfolio `8ebd569`. Book is 5 parts
/ 60 chapters (later 63/58 as tools were added this session). Decision (via
AskUserQuestion): Platforms as **Part 1, first**.

---

## 2. Testwright stale copy (found by "is everything done?")

A sweep after the handbook found real, user-visible falsehoods: `theme.ts` said
"four-stage" and the Author blurb advertised "a recorded click-through" (but
record-and-playback was **dropped** in Part 298); `page.tsx` `TOOL_SUMMARY` (which
feeds the in-world AI assistant) said "Four stages… Heal (roadmap)" — wrong count,
and Heal is live. Fixed all to five live stages, dropped the recorder claim.
Commit ml-portfolio `7bf0183`.

---

## 3. MMRAG backlog triage → then cleared it

Reviewed the remaining MMRAG items. **Dropped before building:** MMRAG-22 (show
citation images to shared viewers — only helps shared-link viewers, medium-high
effort) and MMRAG-19 (confidence/hesitation cue — already decided against in
Aug, ~55-65% accuracy ceiling). Then built the rest.

### MMRAG-18 — Periodicity Finder ✓ (`/tools/periodicity-finder`)
Fully client-side, zero backend. Paste a numeric series or event timestamps →
radix-2 FFT (detrend + Hann window) → dominant repeating cycle(s) with a strength
above the spectrum's noise floor; timestamps auto-binned and reported in real
time units. Engine ground-truth verified (sine p=12→12.2, weekly ts→~7.0 days,
noise stays ~3× vs 10-225× for real signals). **Bug caught in live Playwright:**
invalid SVG `height="auto"` (must be a length) → fixed to CSS. Commit `dc9e872`.

### MMRAG-17 — Scan Descreen ✓ (`/tools/scan-descreen`)
Backend `mm_descreen.py` (`POST /rag/mm-descreen`, mounted like `mm_moire`):
2D FFT → notch the sharp periodic peaks (halftone/moire) + mirrors with a soft
gaussian → inverse FFT. Non-generative (can't invent detail, unlike the paid
`mm_deblur`). **Threshold tuned from measured data, not guessed:** first pass
false-positived on a clean image; probing showed real screen spikes read
hundreds× the local median while a realistic clean image tops ~5×, so the notch
threshold is 10× (clean → removed=0). Verified live end-to-end via Playwright.
Commits: ML-Unified `e07b0d4` (deployed), ml-portfolio `dcb3bde`.

### MMRAG-21 — Meeting Intelligence (lean → full)
Started lean, grew across four commits as the user asked for each extra.

- **Lean tool** (`/tools/meeting-intelligence`): mostly orchestration — reuses
  `transcribe_video()` (Whisper + diarization) + `generate_chapters()` (agenda);
  the only new code is one structured LLM extraction (summary/decisions/action
  items, instructed never to invent) + talk-time. Multipart upload. Verified live
  with a `say`-generated 2-speaker clip (known decision + action items):
  everything accurate. ML-Unified `c73bf20`, ml-portfolio `ee04993`.
- **Transcript Q&A**: `POST /rag/mm-meeting/ask` answers strictly from the
  client-held transcript, declines when not present. Verified: answerable Q
  grounded, out-of-scope Q correctly declined. `0bcde9f` / `45584a6`.
- **SSE progress**: `POST /rag/mm-meeting/stream` emits step events with a 10s
  heartbeat during transcription (blocking call in a ThreadPoolExecutor while the
  async gen heartbeats) so a long clip's connection never idles into the proxy
  timeout. `73541fe` / `f8f577d`.
- **In-tool player + clickable timestamps**: plays the uploaded file via an
  object URL from the in-memory `File` (no upload/storage); every timestamp in
  the agenda AND the transcript seeks the player. `29fe770` (frontend-only).
- **Speaker renaming DROPPED** — mostly redundant (the extraction already
  surfaces spoken names in owners/decisions), cosmetic-only, per-session, and
  would inherit diarization mislabels.

---

## Key decisions

- **The 10MB body cap → Option B (per-route override), not a global bump.** The
  App Safeguard's `body_size.py` cap is global and env-configurable, but raising
  the env var loosens all ~50 routes. Instead added `_ROUTE_CAPS` — only
  `/rag/mm-meeting` and `/rag/mm-meeting/stream` get 50MB; the tight 10MB default
  holds everywhere else.
- **Stopgap thumbnails.** `thumbnails.py add` needs `PEXELS_API_KEY` (not handled
  here), and `rebuild` re-treats all 58. So each new tool reuses a thematically
  fitting existing photo (manifest entry + copy the webp), flagged for a unique
  photo later. periodicity-finder↔realtime-analytics, scan-descreen↔document-
  intelligence, meeting-intelligence↔optuna.

---

## Lessons

- **`createObjectURL` in `useMemo` + revoke in a separate cleanup breaks under
  React StrictMode.** Dev double-invoke (mount→cleanup→mount) revokes the URL the
  `<audio>`/`<video>` still points to → repeated `ERR_FILE_NOT_FOUND` (25 of
  them). Fix: the state+effect pattern where each effect run creates AND revokes
  its own URL, so the final render keeps a valid one. Caught only by watching the
  live console, not by reading the code.
- **`generate_chapters` is Mistral-only, no fallback, needs ≥4 segments.** So the
  meeting agenda is frequently empty (free-tier 429s + short clips). That's why
  clickable *transcript* timestamps matter more than agenda ones — the transcript
  always has timestamps. Don't build a feature that only reads from an unreliable
  source without a reliable alternative.
- **Tune thresholds from measured data.** Descreen's first threshold (4×)
  false-positived; a quick probe of real vs synthetic spike ratios set a
  defensible 10×. "Build a test the tool can fail," then believe the numbers.
- **SSE keeps a long request alive** past the proxy's idle timeout — but the one
  long blocking step needs a heartbeat (executor future + `asyncio.wait_for` on a
  shield, emit on timeout), or that gap can still idle.
- **A stale doc/copy sweep is worth doing when asked "is X done?"** — the
  Testwright "four stages / recorded authoring / Heal roadmap" falsehoods were all
  live in the UI and the AI-assistant context.

---

## Commits

| Repo | Commits |
|---|---|
| ml-portfolio | `8ebd569` (handbook) · `7bf0183` (Testwright copy) · `dc9e872` (Periodicity Finder) · `dcb3bde` (Scan Descreen UI) · `ee04993` (Meeting lean) · `45584a6` (Q&A) · `f8f577d` (SSE) · `29fe770` (player + timestamps) |
| ML-Unified (ml-api) | `e07b0d4` (descreen) · `c73bf20` (meeting) · `0bcde9f` (Q&A) · `73541fe` (SSE) — all HF-uploaded by the user (token their side) and verified live |

Backend deploys followed the batch-deploy discipline: upload → poll Space until
`stage=RUNNING` AND the new route is in `/openapi.json` (not just RUNNING) →
verify with a direct call → then Playwright the UI against the live backend.

---

## State after this session

- **MMRAG backlog: fully closed.** 17/18/21 shipped, 20 already done, 19/22
  dropped. See [[project_mmrag_feature_backlog]].
- **Handbook: current** (5 parts, Platforms part first, all tools + worlds).
- **Testwright: five stages, copy correct.** See [[project_testwright_qa_platform]].
- Open housekeeping (non-blocking): 3 stopgap thumbnails to replace via
  `thumbnails.py add`; gitignored `.playwright-mcp` dirs + `/tmp` test clips to
  clear (removing workspace dirs needs the user's approval).
