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

**Status: research only in this turn — implemented in the next turn, see
Section 10.**

## 10. UI/UX #2 (toolbar/chip grouping) + #4 (aria coverage) — planned, built, shipped

User: *"start with #2 (toolbar/chip grouping) and #4 (aria coverage)"* —
picking two of the five findings from Section 9 to act on.

### Planning (EnterPlanMode)
Read `CitationToolbar.tsx`, `CitationResultsPanel.tsx`, `DocumentChipsRow.tsx`,
`ContradictionsPanel.tsx`, and `DocumentTray.tsx` to ground the plan in the
actual JSX rather than the earlier survey's summary. Per the standing "plan
before proceeding" practice, wrote and got explicit approval (`ExitPlanMode`)
for a concrete plan before touching any file. The prior plan file (domain-
specific NER, already shipped) was overwritten — different task, not a
continuation.

### Scope
Deliberately narrow — presentational-only, no new dependency, no backend
change, no prop/behavior changes:
- **`CitationToolbar.tsx`**: grouped the action `<select>`'s ~15 flat
  `<option>`s into `<optgroup>`s (Describe / Detect / Verify), each only
  rendered when it has at least one visible option — native HTML, zero new
  dependency, `VisualAction` values unchanged. Added
  `aria-label="Choose a detection or edit action"` to the `<select>` itself
  (previously unlabeled beyond its placeholder option).
- **`DocumentChipsRow.tsx`**: split the single "Only search:" chip row
  (content types + 9 entity types mixed together) into two labeled sub-rows
  — "Content type:" and "Contains:" — each only rendered under the same
  conditions as before. Added `aria-label` to the "▸ summary"/"×" buttons
  (symbol-only text isn't a real accessible name), matching their existing
  `title` text.
- **`DocumentTray.tsx`**: each document row was a `<div onClick=...>` with
  no keyboard access at all — a real gap, not cosmetic. Added
  `role="button"`, `tabIndex={0}`, an `onKeyDown` handler firing the same
  action on Enter/Space, and `aria-label` naming the document; its "×"
  button got the same `aria-label` treatment.
- **`ContradictionsPanel.tsx`**: wrapped the results region in
  `aria-live="polite"`, mirroring the exact pattern `ChatPanel.tsx` already
  uses for streaming-answer announcements — so a screen-reader user is told
  the contradiction-check result the same way sighted users see it appear.
- **`DocumentSummaryPanel.tsx`**: added `role="alert"` to the red "Possible
  deepfake signals" box (this session's own Section 3 feature) so it's
  actually announced when it appears, rather than silently.

### Build and live verification
`tsc --noEmit` came back clean. Ran a real local dev server against the
**live production HF Space backend** (pointed `NEXT_PUBLIC_ML_UNIFIED_URL`
at `wram1708-ml-unified.hf.space` for this one test, since the local venv
still has the unrelated missing-package gap noted in Section 3) and drove it
via Playwright:
- Uploaded a real PDF (legal/financial/medical/generic entity terms) — the
  "Contains:" sub-row correctly showed all 9 entity chips separately from
  "Only search:"/"All."
- Uploaded a second file (a plain PNG) to get 2 chunk types — the
  "Content type:" sub-row then correctly appeared alongside "Contains:".
- Confirmed via `DOM` inspection (`browser_evaluate`) that the action
  `<select>` actually contains real `<optgroup>` elements (only the
  "Describe" group had entries for this test image, and empty groups
  correctly didn't render).
- Confirmed via `DOM` inspection that two `aria-live="polite"` regions exist
  once 2 documents are loaded (ChatPanel's pre-existing one + the new
  ContradictionsPanel one), and that the deepfake `role="alert"` box
  correctly does NOT render when no video/audio was uploaded (conditional,
  working as designed — not a bug).
- Confirmed `DocumentTray`'s new `aria-label`s render correctly ("Select
  ui_test.pdf", "Remove ui_test.pdf") in the live accessibility snapshot.

Cleaned up all scratch test files (`ui_test.pdf`/`ui_test.png`, a stray
`.playwright-mcp/` directory that had landed in `ml-portfolio` before
discovering Playwright's allowed root was actually `ML-Unified`) and
confirmed `git status` showed only the 5 intended files changed before
committing. Committed and pushed (ml-portfolio `87e6fc1`) — frontend-only,
so no HF Space upload needed per the plan's own verification section.

## 11. Mobile responsiveness (#1) — planned, built, shipped

User: *"proceed with Mobile responsiveness (#1)"* (asked twice, same
message) — the last of the original 5 UI/UX findings, previously flagged
as "highest-value long-term but a much bigger lift."

### Planning
Two Explore agents read every relevant file in full and found the real
bug: `ChatPanel.tsx`'s message list only becomes a bounded, internally-
scrolling box when its ancestor chain has a *definite* height, which only
existed via the desktop grid's `lg:h-[88vh]`. Below `lg`, that height
vanished — chat history grew to fit every message instead of scrolling,
and the composer just ended up wherever that landed on an ever-growing
page. `DocumentTray.tsx` had the identical dependency. Also found:
`page.tsx`'s header button row had no wrap (could overflow near 375px);
`EvidenceColumn.tsx`'s image+page-rail row squeezed uncomfortably narrow
next to a fixed 88px rail; `PageThumbnailRail.tsx` was a fixed vertical
column unsuited to a stacked mobile layout; `CitationToolbar.tsx`'s button
row had no wrap.

### Approach decision (AskUserQuestion)
Below `lg`, switch from "stack all 3 panels vertically" to a **tabbed
single-panel view** (Documents | Evidence | Chat, defaulting to Chat) —
each tab given a real bounded height (`max-lg:h-[70dvh]`) so it scrolls
internally, matching desktop behavior — chosen over "keep all 3 stacked,
cap each one's own height" (the lighter alternative, but leaves nested
scrolling). Confirmed Tailwind v4 supports `max-lg:` variants, so this
touches nothing at `lg:` — the existing simultaneous 3-column view stays
byte-for-byte identical there.

### Build and a real bug caught mid-implementation
Added the mobile tab switcher to `MmRagRunner.tsx`, wrapped `EvidenceColumn`/
`PageThumbnailRail`'s image+rail row to stack vertically below `sm`, wrapped
`page.tsx`'s header row, added `flex-wrap` to `CitationToolbar.tsx`. Caught
a real bug before shipping: with `mobileTab` defaulting to `"chat"`, the
very first mobile visitor (zero documents yet) would have had the
`DocumentTray` — which holds the upload dropzone — silently hidden, since
the tab switcher itself only renders once `documents.length > 0`. Fixed by
making the `DocumentTray` wrapper ignore `mobileTab` entirely when there
are no documents yet.

### Verification
Playwright at a real ~376px CSS-pixel viewport (this environment doubles
`browser_resize` dimensions — confirmed via `matchMedia` and adjusted).
Confirmed: no horizontal overflow; tab switcher correctly isolates one
panel; zero-doc state still shows the upload dropzone (the caught bug,
now fixed); Evidence tab stacks image above a horizontal-scrolling
thumbnail strip; Chat tab's message list stayed bounded at 568px (=0.7×812)
after a real live question — page height only grew to 897px, not
unbounded. Resized back to desktop width and confirmed the `EvidencePanel`
wrapper still measured exactly 502px and the simultaneous 3-column layout
was unchanged. Committed and pushed (ml-portfolio `8afe705`).

User then asked how to access the app on mobile — answered: same public
Vercel URL, no separate app or setup, since it's a public web page.

## 12. Skeleton loading states — planned, built, shipped

User: *"proceed with No skeleton loading states, Accessibility is
inconsistent, Citation trust signals could go further, one by one"* — the
three remaining research findings from Section 9, tackled sequentially.

An Explore agent surveyed every async wait in the directory and found most
were already fine (ChatPanel's bouncing dots, existing progress bars for
sharpen/AI-fill) or too brief to matter (instant citation-image swaps,
synchronous document switching). Three genuine multi-second waits showed
only text-only feedback over a blank area: `ContradictionsPanel.tsx`'s
"Checking for contradictions…", `EvidencePanel.tsx` (fully blank during
the whole answer wait), and `CitationResultsPanel.tsx`'s steganography/
moire "Generating…" visualize buttons. Deliberately did NOT add a skeleton
for "Find similar figures," since its loading flag lives in a different
component than its results list — would have meant threading a new prop
through the already-largest file in the directory for one moderate-value
spot.

Built a tiny shared `Skeleton.tsx` (Tailwind `animate-pulse`, zero new
dependency) and wired it into all three spots. Verified live: used a
50ms-after-click DOM check (React state updates aren't visible
synchronously within the same `evaluate` call) to actually catch the
loading window before the real API response landed — confirmed 6 skeleton
elements appear then clear for the contradiction check, 9 for the
evidence-panel cards, matching 2×3 and 3×3 bar counts respectively; also
confirmed the page didn't balloon in height while the skeleton was up. The
steganography/moire skeleton uses the identical proven pattern but wasn't
triggered live (no real flagged test image on hand) — disclosed as such,
not silently assumed working. Committed and pushed (ml-portfolio
`b03a84f`).

## 13. Accessibility pass 2 — planned, built, shipped

Second of the three remaining findings. An Explore agent found the first
aria pass (Section 10) left 4 real gaps elsewhere: `RagSourceCard.tsx`
(the citation card, `src/components/`) was a `<div onClick>` with no
keyboard path, the same pattern already fixed for `DocumentTray.tsx`;
`IngestProgressRail.tsx`'s upload drop zone had the identical gap;
`ChatPanel.tsx`'s stop/send buttons and `DetectionBoxOverlay.tsx`'s "✕"
remove-region button were icon-only with only a `title`, no `aria-label`.
`FreehandDrawLayer` (pointer/drag-only by nature) was explicitly flagged
as a disclosed, inherent limitation rather than a fixable gap.

Fixed all 4. While doing so, `RagSourceCard.tsx` crossed the 400-line cap
(399→403) from the new attributes — extracted the "Why was this cited?"
retrieval-trace detail block into a new `RagRetrievalTrace.tsx` sibling
component (matching the file's existing pattern of small extracted
siblings), bringing it back to 340 lines with zero behavior change.
Verified live: citation card renders as `button "Citation 1, page 1"` in
the accessibility tree, is Tab-reachable, and Enter expands it identically
to a click — including confirming the extracted retrieval-trace component
still renders correctly post-split. Committed and pushed (ml-portfolio
`1965708`).

**Playwright maximize technique corrected mid-session**: `browser_resize`
(Playwright's `setViewportSize`) turned out to only emulate the page's CSS
viewport in this environment — `window.outerWidth/outerHeight` stayed
stuck at 1200×806 regardless of what was requested, confirmed via direct
inspection after the user pointed out the window still wasn't actually
maximized. Fixed by calling the real CDP window-bounds API directly via
`browser_run_code_unsafe` (`Browser.getWindowForTarget` +
`Browser.setWindowBounds` with `windowState: "maximized"`), verified via
`outerWidth`/`outerHeight` actually changing to ~1470×850. Saved to memory
(`feedback_playwright_workflow.md`) so future sessions use the correct
technique first instead of rediscovering this.

## 14. "What next" review — corrected a stale pending-list row

User asked "what's pending in computer-vision, cybersecurity" — verified
every candidate row against actual code before presenting (per the
project's standing "grep before presenting" discipline) and found one
stale entry: "blur/quality detection at upload" was listed as unbuilt but
turned out to already be fully shipped — `blur.py` (MMRAG-01, variance-of-
Laplacian, an earlier FFT-ratio version was tried and replaced after
proving non-monotonic on real photos), wired through `mm_image.py`/
`mm_pdf.py` into citations/ingest/retrieval, surfaced in the UI as
`RagSourceCard.tsx`'s "maybe blurry" flag. Corrected in memory. User then
asked which tool it's implemented in — answered: Multimodal RAG, the same
tool this whole session's UI/UX work was on.

## 15. Three new standalone tools, built in sequence

User: *"first do pose-driven generative VJ visuals, then malware-as-image
classification"* — two more pending-list items, requested back-to-back.
(A third, CAPTCHA-solving, was requested and shipped earlier the same
session — see below, out of narrative order since it happened before this
"what next" round but is grouped here with the other two new-tool builds.)

### CAPTCHA Hardening Lab (`/tools/captcha-hardening-lab`)
User: *"proceed with CAPTCHA-solving as adversarial research"*. Built as a
defensive research demo: upload a CAPTCHA image, a VLM
(`_vision_cascade_raw`, reused from `routers/document/_vision.py`) reads
it, then a single intensity slider stacks three classic non-gradient
perturbations (noise/occlusion-wave/contrast-jitter — deliberately NOT
FGSM/PGD, since the VLM is a black-box hosted API with no gradient access,
unlike `adversarial-robustness-lab`'s local torchvision model) and the VLM
reads the hardened version too. Scoped to user-uploaded images only, same
boundary every tool in this project already respects — never automates a
live CAPTCHA challenge. Real bug caught during the first live test:
Mistral vision forces `response_format=json_object` regardless of prompt
wording, so a synthetic test CAPTCHA the VLM actually read correctly
("K9R2X") still failed the ground-truth match because the raw answer came
back as `{"text": "K9R2X"}` — fixed by requesting and parsing that JSON
shape explicitly with the existing `_parse_json` helper. Genuine finding,
reported honestly: even at maximum hardening intensity, this VLM still
read a large-clear-font synthetic CAPTCHA correctly — the tool's own copy
already frames the point as "how much hardening it takes," not "does it
fail," so no overclaiming needed. Backend `mm_captcha.py` (ML-Unified
`d24b5a1`, fix `57adc32`), frontend (ml-portfolio `156a174`). Verified
live end-to-end via Playwright + direct API calls, screenshot confirmed
the hardened image visibly distorted while the VLM still solved it
correctly.

### Pose VJ Visuals (`/tools/pose-vj-visuals`)
Real architectural first for this codebase: entirely client-side, no
backend call at all (round-tripping webcam frames to Python would be too
slow for real-time visuals). Confirmed via exploration: no pose-detection
library existed yet — added `@mediapipe/tasks-vision` (new dependency,
runs via WASM fully in-browser). **Scope decision confirmed with user
(AskUserQuestion)**: build both pose tracking AND mic-reactive audio (Web
Audio `AnalyserNode`, zero new dependency, first audio feature in this
codebase) rather than pose-only, so it actually delivers "for music."
`HandLandmarker` tracks hand landmarks off the live video in a
`requestAnimationFrame` loop, driving a 2D canvas particle/trail system;
mic amplitude scales particle size/density. Honest, disclosed verification
limitation flagged upfront in the plan itself: this sandboxed browser
grants camera/mic permissions but never delivers real frame data
(`video.videoWidth` stayed 0), so real hand-driven motion on actual
hardware is an open follow-up check, same class of gap as plant-growth's
live-camera feature. What WAS verified live: page loads, camera/mic
permission flow works, the MediaPipe WASM model actually loads and runs
(confirmed via real console logs — "GL version...", "Graph successfully
started running"), canvas renders safely with zero particles rather than
erroring when no real frame exists. A mic-toggle flake on the first
attempt (silent failure) was retested clean on a fresh page load and
attributed to a dev-server hot-reload race from active file editing, not
a code bug. Committed and pushed (ml-portfolio `457ea1b`).

### Binary Byte-Plot & Entropy Triage (`/tools/malware-image-triage`)
Researched feasibility before building, per the project's standing
practice (same discipline that rejected fire-detection and signature-
verification after real scrutiny): the original brainstorm ("malware
family CNN classifier on Malimg") has no ready pretrained model, and the
Malimg dataset is only reachable via Kaggle auth or an unreliable Google
Drive bulk scrape (confirmed the folder loads, but that's not the same as
a reliable bulk download). **Scope decision confirmed with user
(AskUserQuestion)**: rather than gamble session time on the Drive scrape,
ship the real technique the field falls back on for triage instead — a
Nataraj et al. byte-plot image + sliding-window Shannon entropy heatmap
(the same signal PEiD/Detect It Easy use to flag packed/encrypted
content) + a hand-rolled PE-header packer-tell check (entry point in the
file's last section), all pure Python/PIL/numpy/struct, zero new
dependency, never executes the uploaded file. Real bug caught during
testing: a 256-byte entropy window capped even true `os.urandom()` output
around 7.2 bits/byte — well under the "high entropy" threshold meant to
catch exactly that case — widened to 1024 bytes (verified real random data
then reads 7.78-7.84, correctly bucketing as "high"). PE parser tested
against two hand-built synthetic PE fixtures (entry point in an early
section vs. the last section) plus truncated/malformed/empty input, none
of which crashed. Backend `mm_malware_image.py` (ML-Unified `a7ec9e6`),
frontend (ml-portfolio `09a991c`). Verified live end-to-end: a plain-text
fixture read "low (0%)" and a random-bytes fixture read "high (94%)" with
an all-red entropy heatmap, both matching local results exactly.

Memory (`project_pending_master_list.md`) updated to mark all three items
done, including the real rescoping rationale for the malware tool so a
future session doesn't re-litigate the CNN-classifier idea without new
information.

## 16. Follow-up: pretrained-model technique, and a scoping note

User asked "what is VJ in Pose VJ Visuals?" — answered: video jockey, the
visual equivalent of a DJ; explained the tool is a small VJ-style
instrument in that spirit.

User then pasted a technical claim about using pretrained ImageNet
backbones (VGG16/ResNet-50/InceptionV3) for malware-image classification
and asked for a view on it — assessed rather than accepted at face value:
the architecture claims were accurate, but the pasted text answered a
different question than the one that actually blocked the malware tool's
original CNN-classifier scope. Pretrained ImageNet weights give a
head-start on generic image features, but the classification HEAD still
needs the labeled Malimg dataset to fine-tune on — the real blocker
(dataset access, not architecture availability) remains unsolved by this
suggestion. Offered a genuine alternative if ever revisited (generate
labeled data locally via a real packer like UPX against local
executables, training a smaller "packed vs not" binary classifier instead
of the full 25-family problem, sidestepping the dataset-access gate
entirely) but flagged it as a new decision, not something to fold in
silently. User: *"no need to flag it"* — acknowledged, no action taken.

## Commits this session (updated)

| Repo | Commit | What |
|---|---|---|
| ml-portfolio | `87e6fc1` | UI/UX #2+#4: toolbar optgroups, chip-row split, aria coverage |
| ml-portfolio | `8afe705` | UI/UX #1: mobile tabbed workspace, header wrap, evidence/rail stacking |
| ml-portfolio | `b03a84f` | UI/UX finding: skeleton loading states (3 real multi-second waits) |
| ml-portfolio | `1965708` | UI/UX finding: accessibility pass 2 + RagRetrievalTrace extraction |
| ML-Unified | `d24b5a1`, `57adc32` | CAPTCHA Hardening Lab backend + JSON-parsing fix |
| ml-portfolio | `156a174` | CAPTCHA Hardening Lab frontend |
| ml-portfolio | `457ea1b` | Pose VJ Visuals (client-side, new tool) |
| ML-Unified | `a7ec9e6` | Binary Byte-Plot & Entropy Triage backend |
| ml-portfolio | `09a991c` | Binary Byte-Plot & Entropy Triage frontend |

## Pending list status after this session (final)

- **UI/UX 5-item research list**: 4 of 5 shipped (toolbar/chip grouping,
  mobile responsiveness, skeleton loading states, accessibility). Inline
  citation-confidence indicator explicitly NOT built — user said "stop
  here" after asking whether it was required; noted in memory so it isn't
  re-offered without being raised again.
- **Cybersecurity**: CAPTCHA-solving and malware-as-image (rescoped) both
  done. Still open: face-recognition deanonymization demo, video-call
  keystroke inference.
- **Computer Vision**: blur/quality detection corrected from stale-unbuilt
  to already-done; pose-driven VJ visuals done. Still open: sports form
  tracker, PPE compliance, gait analysis, sign language translator,
  gesture-controlled desktop, live-webcam surveillance, home biomechanics
  coach, wildlife re-identification, SAM3 rotoscope, phone-video 3D
  Gaussian Splat scanner, backyard astrophotography, near-duplicate
  video-frame skipping, FFT periodicity detection; fire/smoke/gas remains
  blocked (no viable model found).
- **NLP**: only LLM Fine-tuning Pipeline remains (GPU-gated, not started).
