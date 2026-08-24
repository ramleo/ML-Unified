# Session 2026-08-25 — Deepfake Detector + Domain-Specific NER (Part 255)

Continues from Part 254 (edge-case pass + Groq removal). This session covered
a full "what's next" pending-list review across CV/cybersecurity/NLP,
followed by two shipped features end-to-end: audio-visual deepfake detection
and domain-specific NER, plus a user-guide catch-up pass for both.

---

## 1. Pending-list review — "what next in CV, cybersecurity, NLP?"

Before answering, verified the standing pending-list memory against actual
code (per the established "grep before presenting" lesson) and found it was
stale in several places from work already committed but never reflected back
into memory:

- **PRNU camera-fingerprint matching** (`mm_prnu.py`) — already shipped, commit `4a5b57f`.
- **Steganography detection** (`mm_steganography.py`) + **moire detection**
  (`mm_moire.py`) — already shipped, commits `b34d1f6`/`cb6de26`/`e3a4860`/`a0fd4b2`.
- **Answer-groundedness scoring** (`groundedness.py`) and **speaker
  diarization** (`mm_diarize.py`) — both already built, previously sitting in
  a 2026-07-25 brainstorm list marked "not built."
- **Query decomposition**, **multilingual Q&A**, **region-level captioning**,
  **chart data extraction** — all already shipped in earlier sessions.

Corrected memory (`project_pending_master_list.md`) accordingly before
presenting the real remaining list, organized by category with effort
estimates. User then asked specifically about the **"confidence/hesitation-
cue"** deception-detection item.

## 2. Accountability moment — confidence-cue reasoning corrected

User: *"you said it was not worth doing because prediction is 50-50
probability, right?"* — this was **not quite right**, and I corrected it
rather than concede:

- The near-chance accuracy (~54-67%) was the reason a literal **genuine/fake
  verdict** deception detector was rejected.
- The **confidence/hesitation-cue** feature (the one actually on the pending
  list) was a different, honestly-designed fallback — approved specifically
  *because* it never renders a clean verdict, not despite being near-chance.

Asked for a recommendation on whether to keep it: recommended dropping it —
its only real value was the honesty-framing demonstration itself, not a
showcased technique, and building it (facial micro-cue + vocal-stress
extraction) would cost real effort for low payoff versus other open items.
User agreed: **"then drop it, proceed with deepfake detector."** Dropped
and documented in memory with the corrected reasoning (why it was approved,
why it was later dropped — two different things, not a reversal).

## 3. Deepfake video/audio fraud detection — planned, built, shipped

### Planning (EnterPlanMode)
Explored `mm_tampering.py`/`mm_prnu.py`'s existing detector patterns, video/
audio pipeline (`mm_video.py`, `mm_video_audio.py`, `mm_ingest.py`), and
`requirements.txt` (confirmed: no torch/onnxruntime/mediapipe/dlib — CPU-only
Space). Scoped the plan around two coarse signal-processing heuristics
(AV lip-sync desync, voice-clone spectral-flatness), explicitly avoiding a
heavier SyncNet/MediaPipe approach to keep zero new heavy dependencies.

### Real validation gap surfaced and resolved
No real human-voice or real-face video existed anywhere on the machine to
validate against — asked the user directly rather than substitute macOS
`say` output as a fake negative control (per the plan's own explicit gate).
User provided `Original_recording5.mp4` (a real UN General Assembly speech
recording, S. Jaishankar) for testing.

### Real architecture surprise: Haar cascades don't exist in this opencv build
`cv2.CascadeClassifier` doesn't exist at all in `opencv-python-headless`
5.0.0, and `cv2.data.haarcascades` is an empty directory — a real finding
that invalidated the plan's "zero new dependency" assumption. Tested and
confirmed **YuNet** (OpenCV Zoo's own official face detector for the 5.x DNN
engine — ~230KB MIT-licensed ONNX file, runs via `cv2`'s own DNN module, no
`onnxruntime` package needed) works correctly against the real clip (92.9%
confidence, plus real eye/nose/mouth-corner landmarks — better than the
originally-planned Haar-cascade approach). Got explicit user sign-off before
bundling it as a new static asset (`models/face-detection-yunet.onnx`), per
the standing "no unilateral dependency" lesson.

### Real negative result, honestly reported and NOT smoothed over
First AV-sync scoring attempt (correlation-based, both a max-lag cross-
correlation and a corrected zero-lag Pearson) **failed outright**: the
genuinely-synced real clip scored WORSE (in one case negative) than a
1s-shifted or fully-shuffled negative control. Reported this plainly and
dropped the signal, matching the fire-detection-model precedent — no
further parameter-tuning against a single clip, which would have been
overfitting to noise, not validation.

### User pushed back with a technical suggestion — partially right, adopted the useful part
User pasted a third-party technical suggestion (SyncNet, MediaPipe Face
Mesh, DTW, phoneme alignment). Assessed each piece honestly rather than
either dismissing it wholesale or accepting it wholesale:
- SyncNet/MediaPipe: would likely work better, but needs new heavy
  dependencies (torch, or a real ~34MB MediaPipe wheel) this project has
  consistently avoided — held off pending explicit sign-off, none given.
  (Corrected an initial wrong claim mid-conversation: MediaPipe does NOT
  need torch, and DOES have a working Python 3.14 wheel — verified by
  actually downloading it, not assumed.)
- Landmark-to-phoneme mapping: too big a lift (needs a forced-aligner ASR).
- **DTW instead of correlation: right, and cheap (no new dependency).**

Reran the same real-clip test with DTW instead of correlation:
synced clip scored 0.267, cleanly below the full range of 5 independently
shuffled negative controls (0.289-0.322) and a 1s-shifted control (0.274).
A real, correctly-directed, replicable effect — recovered the signal without
adopting the heavier suggested architecture. Got explicit user sign-off
before un-dropping the signal and proceeding to build.

### Build, deploy, and live verification
Built `mm_deepfake.py` (YuNet mouth-landmark motion + DTW path cost vs audio
RMS envelope for AV-desync; STFT spectral-flatness variance for voice-clone
artifact — both disclosed with their real validation limits in the module
docstring). Wired into `mm_ingest.py` (video branch, whole-clip not
per-frame) and `mm_audio.py` (voice-artifact only, standalone audio path).
Frontend: `DeepfakeSignals` type + a document-summary-level warning block
in `DocumentSummaryPanel.tsx` (chapters-like pattern, not the per-citation
dropdown pattern, since this is whole-clip data).

Verified via direct Python calls locally against the real clip (clean, no
false positive) AND a synthetic manipulated clip (real video + dubbed-in
macOS `say` audio — both signals correctly fired: AV-desync 100% confidence,
voice-artifact 79%). Committed (ML-Unified `b31f19c`, ml-portfolio `881b470`),
pushed, HF Space files uploaded, rebuild confirmed RUNNING and healthy, then
**re-verified live** against the real production API (both the clean and
manipulated test cases reproduced identically to local results) and via
Playwright against the live Vercel site (accessibility snapshot captured the
rendered "Possible deepfake signals" box with correct confidence percentages
and disclosure text).

Saved a reusable technical-lesson memory
(`project_deepfake_detector_dtw_lesson.md`) documenting both findings
(opencv 5.x dropping Haar cascades; DTW beating correlation for AV-sync
scoring) for future CV work in this project.

## 4. "How can I verify?" / "what it does?" — plain-language follow-ups

User asked for verification instructions (given three options: UI upload of
a normal clip, UI upload of a deliberately mismatched clip, or a raw curl
against the API) and a plain-language explanation of what the feature
checks for and why it matters (referencing the real Arup deepfake-video-call
$25M fraud case).

## 5. Domain-specific NER — planned, built, shipped

User picked this as "what next," per an earlier direct recommendation
(lowest remaining effort, fills the thinnest category, reuses existing
infrastructure rather than starting cold).

### Planning
Read `entities.py` (MMRAG-26) and confirmed it already does GENERIC NER
(money/date/percent regex, person/org/location via a lazy-loaded spaCy
`en_core_web_sm` pass, baked into the Docker image, no new dependency) — the
real gap was DOMAIN categories, not generic ones. Traced the full pipeline
(`retrieve.py`'s `has_{type}` Chroma-metadata hard filter, and
`CitationResultsPanel.tsx`'s `{e.type}: {e.value}` render) and confirmed
both are **already fully generic** over whatever's in `ENTITY_TYPES` — no
new wiring needed beyond the entity-extraction module itself and one
frontend label-map line.

### Scope decision
The original brainstorm named 3 categories: medical conditions, legal
clauses, financial terms. Flagged the medical category as a real risk
(a shallow keyword list could imply clinical-grade extraction it can't
back up, same reasoning as the earlier Medical Scan Analyzer rejection) and
asked the user directly rather than deciding unilaterally. User chose to
**include medical anyway**, explicitly disclosed as a non-diagnostic keyword
list.

### Build and verification
Added `_LEGAL_CLAUSE_RE`/`_FINANCIAL_TERM_RE`/`_MEDICAL_CONDITION_RE`
(curated term-list regexes, same technique as the existing money/date/
percent regexes) to `entities.py`, extended `ENTITY_TYPES`, added the label
map entries in `DocumentChipsRow.tsx`. Unit-tested locally against four
representative real-sentence fixtures (mock legal/financial/medical
paragraphs plus a plain-prose negative control) — all three categories
matched correctly, and plain prose produced zero spurious matches. Committed
(ML-Unified `84ae970`, ml-portfolio `4314178`), pushed, HF Space uploaded
(`entities.py` only, no new dependency), rebuild confirmed RUNNING, then
verified live: a real PDF ingested through the deployed API returned
`financial_term`/`legal_clause`/`medical_condition` in `entity_types`, and
Playwright confirmed all three new filter chips ("Financial Term," "Legal
Clause," "Medical Condition") render correctly on the live Vercel site.

Updated the pending-list memory to reflect this shipped.

## 6. User-guide catch-up pass

User asked "what it does?" again in plain language for the NER feature,
then asked to **"update user guide."** Found that BOTH features shipped this
session (deepfake detector, domain NER) had never received a user-guide
pass. Fixed both:
- `overview.ts` — added the automatic deepfake-signal description right
  after the transcript/chapters section it renders alongside in
  `DocumentSummaryPanel.tsx`, with the same disclosed-limitation framing
  used in the code.
- `citations.ts` — added a "Domain-term chips" entry next to the existing
  "Key facts chips" entry, same disclosure style.
- `documentTools.ts` — extended the "Only search" filter-chip list to
  mention the three new entity types.

Committed and pushed (ml-portfolio `3565b30`) — docs-only, no backend
change, no HF Space upload needed.

## 7. Follow-up questions (live document walkthrough)

User uploaded a real "Deed of Hypothecation" legal document into the live
Multimodal RAG tool and asked me to explain, in simple words, what the
"Legal Clause" filter chip does — given a concrete example grounded in the
actual visible document text (definitions, creditor/collateral language, the
LawRato.com attribution footer) rather than a generic explanation.

## 8. DOCX upload — feasibility question, not yet built

User asked directly ("just tell") whether `.docx` upload could be added to
Multimodal RAG. Answered plainly: yes, and there's a shortcut — Document
Intelligence (the separate tool) already has full DOCX parsing built
(text boxes, merged cells), so the actual parsing code exists; it's just not
wired into Multimodal RAG's upload pipeline (currently PDF/image/CSV/video/
audio only). **Not built** — user said "maybe next time," explicitly
deferred, not committed to.

---

## Commits this session

| Repo | Commit | What |
|---|---|---|
| ML-Unified | `b31f19c` | Deepfake detector backend (`mm_deepfake.py` + wiring + YuNet model asset) |
| ml-portfolio | `881b470` | Deepfake detector frontend (`DocumentSummaryPanel.tsx` + types) |
| ML-Unified | `84ae970` | Domain-specific NER backend (`entities.py`) |
| ml-portfolio | `4314178` | Domain-specific NER frontend (`DocumentChipsRow.tsx` label map) |
| ml-portfolio | `3565b30` | User-guide catch-up for both features |

Both backend commits were deployed to the `wram1708/ml-unified` HF Space and
verified live (health check + real functional API call + Playwright UI
check) before being reported done, per the project's standing verification
discipline.

## Pending list status after this session

- **CV**: still open — blur/quality detection, home biomechanics coach,
  sports form tracker, PPE compliance, SAM3 rotoscope, wildlife re-ID, sign
  language translator, gait analysis, gesture-controlled desktop/live-webcam
  surveillance (architecturally different), fire/smoke/gas (blocked, no
  viable model found).
- **Cybersecurity**: still open — CAPTCHA-solving research, video-call
  keystroke inference, malware-as-image classification, face-recognition
  deanonymization demo.
- **NLP**: domain-specific NER now done. Only LLM Fine-tuning Pipeline
  remains (GPU-gated, not started).
- **New, not yet built**: Multimodal RAG `.docx` upload support (deferred,
  "maybe next time").

## 9. UI/UX improvement scope — researched, not built

User asked: *"is there scope to improve UI/UX of the app, search online and
tell."* Ran this as research-only (web search + a structural Explore-agent
survey of the actual `multimodal-rag/` frontend), not implementation.

**Web research** (2026 RAG chat UI/UX best practices) surfaced: numbered
inline citations expanding to source cards with confidence indicators;
streaming responses with a stop button and typing indicators; keyboard
shortcuts, conversation branching, message pinning; document-preview
citation highlighting; mobile composer must be docked (not floating/
overlapping) with keyboard-safe padding; readable line length ~65-72 chars
and line-height ~1.6; trust/adoption evaluated on capability transparency,
recovery patterns, confidence display, and accessibility.

**Structural survey** (Explore agent, `multimodal-rag/` — ~40 files, 5,505
lines) found:
- **Mobile is effectively unsupported.** Only `MmRagRunner.tsx` has any
  responsive breakpoints (`lg:grid-cols-[...]`), collapsing the 3-column
  workspace to a single stack below `lg` — nothing tuned narrower than that.
  Notable since the app has a "share publicly" toggle, meaning shared links
  can genuinely be opened on a phone.
- **Chip/toolbar clutter is real.** `DocumentChipsRow.tsx` already stacks
  two pill rows (doc names + "Only search" filters), now carrying 9 entity
  types after this session's NER work. `CitationToolbar.tsx` covers ~15
  detection modes in one flat dropdown; `CitationResultsPanel.tsx` renders
  results as small 9-10px gray text blocks with minimal grouping.
- **No skeleton loading states anywhere** — ingestion uses progress bars/
  dots, everything else just uses disabled buttons + "…ing" text.
- **Accessibility is inconsistent.** `ChatPanel.tsx` has real practice
  (`aria-live="polite"` for streaming, `aria-label`s on feedback buttons);
  no other file in the app uses any `aria-*`/`role`, relying on bare
  `<button>`/`<select>` + `title` tooltips.
- **Citation trust signals could go further** — the app already has a
  groundedness badge (`EvidencePanel.tsx`) and a "why was this cited" trace
  panel (MMRAG-08), ahead of most RAG tools, but nothing surfaces
  confidence at the point a citation renders inline in the chat answer,
  only after expanding.

**Recommendation given** (not yet acted on): start with toolbar/chip
grouping and aria coverage — both contained, don't touch the two files
already near the 400-line cap (`CitationThumbnailPanel.tsx` at 375 lines,
`DocumentSummaryPanel.tsx` at 310), no new dependency. Mobile responsiveness
is the highest-value item long-term but a much bigger lift touching most of
the 40 files — flagged as worth scoping separately if pursued.

**Status: research only, nothing implemented or committed this turn.**
