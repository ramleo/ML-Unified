# TC-P12 — Parts 250–259

**Prefix:** TC-P12
**Parts covered:** 250–259 (10 sessions)
**Status:** ✅ Complete
**Method:** Inline — no subagents, per standing project practice; full line-by-line re-read of all 10 session logs.

Covers: the 5-batch silent-exception logging audit; the homepage search-bar scroll bug (4 real bugs across 2 parts); the sitewide theme-consistency audit (`--fg-rgb` token, hardcoded-color classes); FFT investigations (moiré/steganography shipped, periodic-artifact AI-splice rejected); stegomalware payload ID; PRNU camera fingerprinting; the EC-001→008 multi-doc edge-case pass; full Groq removal from default paths; deepfake A/V detection; domain-specific NER; and a run of new standalone tools — face deanonymization demo, video-call keystroke inference, movement/gait comparison, email auth checker, browser-extension permission analyzer, LLM prompt-injection playground, AI-code detector, crime-scene SfM, Grounded-SAM rotoscope, astrophotography anomaly, wildlife re-ID, PPE compliance, ASL fingerspelling.

---

## Logging / Observability Audit (Part 250)

### TC-P12-001
**Category:** Backend API
**Test Name:** LLM provider-cascade exhaustion is logged, not silently swallowed
**Steps:**
1. Force every provider in the Document Intelligence / Text-to-SQL cascade to fail (bad keys).
2. Trigger a generation call.
**Expected Result:** The real exhaustion is emitted via `logger.warning`/`error` (batch-1 fix, commit `868a1f4`), not discarded behind the generic fallback.
**Automation Hint:** pytest with caplog; monkeypatch providers to raise, assert a log record exists.
**Source:** Part250

### TC-P12-002
**Category:** Backend API
**Test Name:** Every SQL security rejection is logged
**Steps:**
1. Submit a Text-to-SQL query that trips a guardrail (e.g. DROP/DELETE).
**Expected Result:** The rejection is logged with context in `ml-sql/_execute.py`, not silently returned.
**Automation Hint:** pytest caplog on the guardrail path.
**Source:** Part250

### TC-P12-003
**Category:** Backend API
**Test Name:** Gemini daily-budget cap hits are logged
**Steps:**
1. Exhaust the Gemini daily image-gen budget.
2. Issue another image-gen call.
**Expected Result:** `_image_gen_budget.py` logs the cap hit rather than failing silently.
**Automation Hint:** pytest — stub budget store at cap, assert log + correct response.
**Source:** Part250

### TC-P12-004
**Category:** Backend API
**Test Name:** Semantic-cache lookup failure is logged (not treated as a miss)
**Steps:**
1. Force the RAG semantic-cache lookup to raise.
2. Issue a query.
**Expected Result:** `rag/query.py` logs the real cache error (batch-2, `293b8ea`); query still proceeds.
**Automation Hint:** pytest caplog; monkeypatch cache to raise.
**Source:** Part250

### TC-P12-005
**Category:** Backend API
**Test Name:** Document cross-field validation skip is logged on bad JSON
**Steps:**
1. Feed Document Intelligence a response whose line-items/experience JSON is malformed.
**Expected Result:** `document/_validate.py` logs the skipped recompute (batch-3, `39a8830`) instead of silently passing.
**Automation Hint:** pytest caplog with malformed validation input.
**Source:** Part250

### TC-P12-006
**Category:** Architecture
**Test Name:** `routers/eda.py` is confirmed dead code (never mounted)
**Steps:**
1. Grep `app.py` for an import/mount of `routers/eda.py`.
**Expected Result:** No import exists — the static `eda.html` calls the separate `ml-eda` microservice directly; its logging fix is harmless but unreachable.
**Automation Hint:** test asserting `eda` router is absent from the app's route table.
**Source:** Part250

### TC-P12-007
**Category:** Architecture
**Test Name:** Silent-by-design handlers are NOT instrumented
**Steps:**
1. Review per-item best-effort loops, SSE token-chunk parse skips, image-decode-to-400 paths.
**Expected Result:** These remain intentionally silent (judged case-by-case across all 5 batches); only real discarded exceptions got logging.
**Automation Hint:** manual review checklist; no assertion.
**Source:** Part250

### TC-P12-008
**Category:** Data
**Test Name:** HF Docker-SDK Space creation requires a paid plan (grandfathered existing)
**Steps:**
1. Attempt to create a NEW `sdk: docker` HF Space on a free personal account.
**Expected Result:** Blocked/paid since the ~2026-07-08 policy change; existing pre-change Spaces are grandfathered. Checking an existing Space answers "does Docker work" not "is new creation free."
**Automation Hint:** documentation/process check, not automatable.
**Source:** Part250

### TC-P12-009
**Category:** Architecture
**Test Name:** Render does not retroactively apply `render.yaml` env type to existing services
**Steps:**
1. Compare a Render service's live `env` vs the repo's `render.yaml` (`env: docker`).
**Expected Result:** Pre-existing services keep `env: python` (buildpack) unless manually flipped or Blueprint-resynced — a code-only commit is insufficient.
**Automation Hint:** manual/ops check.
**Source:** Part250

### TC-P12-010
**Category:** UI
**Test Name:** "Portfolio" nav label renamed to "Home" on all 3 static tool pages
**Steps:**
1. Load `/`, `/?mode=eda`, `/?mode=vision` (served by ml-api).
**Expected Result:** The nav pill reads "Home" on all three (commit `e2945c8`); link target unchanged.
**Automation Hint:** grep served HTML / Playwright text assert on each route.
**Source:** Part250

---

## Homepage Search-Bar Scroll Bug (Parts 251–252)

### TC-P12-011
**Category:** Bug-Regression
**Test Name:** Sticky search bar self-corrects when a zero-match query collapses the page
**Steps:**
1. Scroll deep on the homepage.
2. Type a zero-match query (e.g. "zzz").
**Expected Result:** A `useEffect` on `query`/`activeDomain` detects the bar's `getBoundingClientRect().top < 0` and `scrollIntoView`s it back; "No tools match" becomes visible.
**Automation Hint:** Playwright — assert `scrollY` corrects and bar `top` ≈ 0.
**Source:** Part251 (`6eb5844`)

### TC-P12-012
**Category:** Bug-Regression
**Test Name:** Ordinary typing does not trigger an unwanted scroll jump
**Steps:**
1. From a comfortable scroll position, type "p" then "pi".
**Expected Result:** `scrollY` and bar `top` unchanged (effect only fires when bar is actually above the viewport).
**Automation Hint:** Playwright — assert no scroll delta.
**Source:** Part251

### TC-P12-013
**Category:** Bug-Regression
**Test Name:** Results in a domain ABOVE current scroll are brought into view
**Steps:**
1. Scroll down to Computer Vision, type "pi" (match is in a higher domain).
**Expected Result:** Fix retargets the plain (non-sticky) section container with `behavior:"instant"`; the matching results become visible.
**Automation Hint:** Playwright real mouse-wheel scroll, then assert results visible.
**Source:** Part252 (`09db8de`/`33f11b8`)

### TC-P12-014
**Category:** Bug-Regression
**Test Name:** Visibility check uses real content height (≥120px), not position proxies
**Steps:**
1. Produce a state where results are ~90% scrolled off but the bar's top and section bottom still "pass" the old heuristics.
**Expected Result:** Fix measures `.cap-grid`/`.cap-no-results` actual visible height, requiring ≥120px genuinely visible.
**Automation Hint:** Playwright — assert on measured element visible height.
**Source:** Part252 (`b63623a`)

### TC-P12-015
**Category:** Bug-Regression
**Test Name:** Auto-scroll effect is skipped on initial page load
**Steps:**
1. Load/refresh the homepage (query="" on mount, section below the fold).
**Expected Result:** `isFirstRun` ref skips the effect's first run — no forced auto-scroll on fresh load.
**Automation Hint:** Playwright — assert `scrollY` stays 0 on load.
**Source:** Part252

---

## Sitewide Theme-Consistency Audit (Part 251)

### TC-P12-016
**Category:** UI
**Test Name:** `--fg-rgb` token resolves per-theme for alpha-based colors
**Steps:**
1. Inspect `rgba(var(--fg-rgb),X)` usages in light and dark themes.
**Expected Result:** `--fg-rgb` (RGB triplet matching `--text`) is defined per theme in `globals.css`.
**Automation Hint:** Playwright — assert computed value differs by theme.
**Source:** Part251

### TC-P12-017
**Category:** UI
**Test Name:** Chart gridlines/axis labels adapt to theme (not hardcoded white)
**Steps:**
1. Toggle theme on Drift/Optuna/SHAP charts.
**Expected Result:** Gridlines/axis labels/progress tracks use theme tokens, readable in both modes.
**Automation Hint:** Playwright theme toggle + computed color check.
**Source:** Part251

### TC-P12-018
**Category:** Bug-Regression
**Test Name:** `SchemaDiagram.tsx` adapts to theme (was permanently-dark card)
**Steps:**
1. View the Text-to-SQL schema diagram in light mode.
**Expected Result:** No longer a fixed dark card; adapts to theme.
**Automation Hint:** Playwright computed background check.
**Source:** Part251

### TC-P12-019
**Category:** Bug-Regression
**Test Name:** Form controls are readable in light mode (no dark-on-dark)
**Steps:**
1. Inspect `<select>`/`<input>` (e.g. Optuna) in light mode.
**Expected Result:** Background adapts; text stays legible (fixed-dark-bg bug removed).
**Automation Hint:** Playwright contrast check.
**Source:** Part251 (`87550ea`)

### TC-P12-020
**Category:** Bug-Regression
**Test Name:** `ShareWatermark.tsx` is visible in light mode
**Steps:**
1. Render the anti-screenshot-leak watermark in light mode.
**Expected Result:** Watermark is visible (was literally invisible/non-functional in light mode before `8691818`).
**Automation Hint:** Playwright opacity/color assertion.
**Source:** Part251

### TC-P12-021
**Category:** Bug-Regression
**Test Name:** `SchemaPanel.tsx` icon strokes are visible in dark mode
**Steps:**
1. View SchemaPanel icons in dark mode.
**Expected Result:** Strokes no longer hardcoded dark slate (reverse-direction bug, fixed `f33ab6e`).
**Automation Hint:** Playwright stroke-color check in dark.
**Source:** Part251

### TC-P12-022
**Category:** Architecture
**Test Name:** Theme-independent patterns are left alone (reusable checklist)
**Steps:**
1. Review box-shadows/modal scrims, camera viewfinder chrome, image-overlay badges, text-inside-colored-shapes, solid-accent-button text, semantic color-lookup maps.
**Expected Result:** These are correctly NOT flagged as theme bugs.
**Automation Hint:** manual audit checklist.
**Source:** Part251

---

## FFT: Steganography (shipped) & AI-Splice Detection (rejected) (Parts 252–253)

### TC-P12-023
**Category:** Feature
**Test Name:** Chi-square LSB steganography detection separates clean vs embedded
**Steps:**
1. Run `mm_steganography.py` on clean real JPEGs and on the same with a 100% LSB payload.
**Expected Result:** Clean ≈ 8.9–18.0, 100%-embed ≈ 0.5–1.3; clean separation, no false positives (sensitivity below ~20–30% honestly disclosed).
**Automation Hint:** pytest with embedded fixtures.
**Source:** Part252 (`4c371d0`)

### TC-P12-024
**Category:** Bug-Regression
**Test Name:** Chi-square averages across RGB channels (not MIN)
**Steps:**
1. Run detection on china.jpg (R channel alone reads falsely "detected").
**Expected Result:** Averaging across channels avoids the false positive while preserving signal; luminance-only was tested and rejected (destroys bit-level structure).
**Automation Hint:** pytest asserting per-channel averaging path.
**Source:** Part252

### TC-P12-025
**Category:** Bug-Regression
**Test Name:** A new backend field is wired through every explicit field list
**Steps:**
1. Add a stego field; trace it through `mm_ingest_payload.py` SSE list and `IngestProgressRail.tsx` snake→camel map.
**Expected Result:** Field reaches the frontend (both lists updated), not dropped mid-stack.
**Automation Hint:** contract test matching computed fields to each list.
**Source:** Part252

### TC-P12-026
**Category:** Feature
**Test Name:** Steganography bit-plane "show what the computer sees" visualization is honest
**Steps:**
1. Call `/rag/mm-steganography/visualize` on stego and clean images.
**Expected Result:** Both render ~50/50 static bit-planes (indistinguishable); caption states it is NOT the hidden message/location.
**Automation Hint:** pytest — assert both outputs statistically similar.
**Source:** Part252 (`eba6a20`)

### TC-P12-027
**Category:** Architecture
**Test Name:** FFT periodic-artifact AI-splice detector was rejected, not shipped
**Steps:**
1. Confirm no `mm_fft_artifacts.py` module is wired/committed.
**Expected Result:** Rejected after a synthetic splice scored lower than an untouched original (4.60 vs 4.93 std); negative finding recorded in `project_tampering_detector_precision`.
**Automation Hint:** grep repo — assert module absent.
**Source:** Part252

### TC-P12-028
**Category:** Feature
**Test Name:** Plant-growth phase-correlation frame alignment is applied in the exported GIF
**Steps:**
1. Measure a plant series with simulated ~29/-14px camera shake, export the GIF.
2. Re-measure shift between exported frames.
**Expected Result:** Residual drops to ~1.2px — alignment is in the output, not just computed; falls back to centered-draw when unavailable.
**Automation Hint:** numeric residual assertion on exported frames.
**Source:** Part252 (`d9ce4c1`)

---

## FFT Moiré, Stegomalware, PRNU, OCR & Doc-Switch (Part 253)

### TC-P12-029
**Category:** Feature
**Test Name:** Radon-style moiré detection separates real photos from synthetic moiré
**Steps:**
1. Run `mm_moire.py` at realistic fine scales (4–8px period).
**Expected Result:** Real photos 4.3–7.7 vs synthetic moiré 12–370; 89/90 combos clear the ceiling. (2D-FFT DC-excluded approach was blind to axis-aligned moiré — rejected.)
**Automation Hint:** pytest with synthetic moiré fixtures.
**Source:** Part253 (`a0fd4b2`)

### TC-P12-030
**Category:** Feature
**Test Name:** Moiré visualization circles the detected peak (raw spectra look identical)
**Steps:**
1. Call `/mm-moire/visualize` on clean and moiré images.
**Expected Result:** The actual peak (brightest pixel outside DC disk) is circled in red; raw 2D-FFT alone was non-diagnostic to a human.
**Automation Hint:** assert marker pixels present in returned bytes.
**Source:** Part253

### TC-P12-031
**Category:** Bug-Regression
**Test Name:** Steganography minimum-resolution gate raised to 500px
**Steps:**
1. Run stego detection on small/resized photos (≤500px).
**Expected Result:** `_MIN_DIM` is 500 (was 32); previously-false-positive small photos now read `detected:false`; a genuine 100% embed on a large image still detects.
**Automation Hint:** pytest across resolutions.
**Source:** Part253 (`b34d1f6`)

### TC-P12-032
**Category:** Bug-Regression
**Test Name:** OCR-hallucinated junk "table" chunk is filtered
**Steps:**
1. Ingest a plain photo whose Mistral OCR emits a fake pipe-table around an image placeholder.
**Expected Result:** `is_junk_table_block()` strips placeholder/table syntax; if nothing substantive remains it's not a table. `face.jpeg` yields exactly 1 chunk.
**Automation Hint:** pytest on the hallucinated vs genuine table patterns.
**Source:** Part253 (`cb6de26`)

### TC-P12-033
**Category:** Bug-Regression
**Test Name:** Clicking a Session-Sources row switches the active document
**Steps:**
1. Upload two images; click the other document's row in Session Sources.
**Expected Result:** `selectDocument(source)` switches the Evidence panel to that doc (both directions) — previously only toggled a summary popup.
**Automation Hint:** Playwright — assert Evidence panel doc changes on row click.
**Source:** Part253 (`d4f4304`)

### TC-P12-034
**Category:** Feature
**Test Name:** Stegomalware payload identification matches known file signatures
**Steps:**
1. Embed a ZIP-magic payload and a 4-byte-length-prefixed PE signature via LSB; run detection.
**Expected Result:** `scan_for_file_signature()` sets `payload_type` (ZIP/PE/etc.); clean photos match zero signatures.
**Automation Hint:** pytest with crafted LSB payloads across the 8 signatures.
**Source:** Part253 (`e3a4860`)

### TC-P12-035
**Category:** Feature
**Test Name:** PRNU camera fingerprint uses PCE (resists content-similarity confound)
**Steps:**
1. Compare same-camera (inject residual) vs different-camera real pairs vs same-content/different-pattern.
**Expected Result:** Same-camera PCE huge (~72k), different-camera low (~22–31), content-similar-but-different-sensor stays in baseline (not fooled) — PCE, not plain correlation.
**Automation Hint:** pytest on `mm_prnu.py` with the 5 validation scenarios.
**Source:** Part253 (`4a5b57f`)

---

## Multi-Doc Edge-Case Pass EC-001→008 (Part 254)

### TC-P12-036
**Category:** Bug-Regression
**Test Name:** EC-001 — visualAction resets on document switch
**Steps:**
1. Select "Detect objects" on doc B, switch to doc A.
**Expected Result:** `useCitationVisualState` keyed on `editKey` (`source:page`) resets per-citation state; doc A shows its own last action, not B's.
**Automation Hint:** Playwright before/after repro.
**Source:** Part254 (`9dd24be`)

### TC-P12-037
**Category:** Bug-Regression
**Test Name:** EC-002 — removing the active document falls back cleanly
**Steps:**
1. Remove the currently-active document.
**Expected Result:** Evidence panel shows "Click a citation to see its page," no crash; remaining doc intact.
**Automation Hint:** Playwright.
**Source:** Part254

### TC-P12-038
**Category:** UI
**Test Name:** EC-003 — switching documents resets to that doc's page 1 (intended)
**Steps:**
1. Switch to another document's row.
**Expected Result:** Resets to page 1 of that doc — confirmed intentional, flagged as product decision not a bug.
**Automation Hint:** Playwright assert page index.
**Source:** Part254

### TC-P12-039
**Category:** Bug-Regression
**Test Name:** EC-007 — fabricated-collage caption is caught and retried
**Steps:**
1. Ingest a single plain portrait that triggers a "vertical collage of N sections" hallucination.
**Expected Result:** `looks_like_fabricated_collage()` cross-checks object-detection bbox sizes (a real collage tiles the frame) and retries; widened matcher relies on the bbox contradiction, not word proximity. 5/5 fresh ingests return the correct plain caption.
**Automation Hint:** pytest on the two wordings + bbox contradiction guard.
**Source:** Part254 (`9814f79`+`a14d356`)

### TC-P12-040
**Category:** Bug-Regression
**Test Name:** EC-004b — AI Sharpen surfaces an accurate 429 (not generic 502)
**Steps:**
1. Call `/rag/mm-deblur` when Gemini image-gen is quota-exhausted.
**Expected Result:** `mm_deblur.py` catches `HTTPStatusError` and returns a real 429 message; `useSharpen.ts` reads the status.
**Automation Hint:** pytest — stub Gemini 429, assert message.
**Source:** Part254 (`8e985ce`)

### TC-P12-041
**Category:** Architecture
**Test Name:** EC-004b — Sharpen result is never persisted across a citation switch (by design)
**Steps:**
1. Read `useSharpen.ts`'s `syncKey` effect.
**Expected Result:** All sharpen state nulled when `editKey` changes (generative output can hallucinate — deliberately not persisted, unlike `useInpaint`).
**Automation Hint:** unit test on state reset when key changes.
**Source:** Part254

### TC-P12-042
**Category:** E2E
**Test Name:** EC-006 — video-frame citation re-seeks correctly after a doc switch
**Steps:**
1. Click a video-frame citation (seeks 8.2s); add another doc, switch away and back, re-click.
**Expected Result:** Seeks to the identical 8.2s both times; no bug.
**Automation Hint:** Playwright on a built multi-scene MP4 fixture.
**Source:** Part254

### TC-P12-043
**Category:** Bug-Regression
**Test Name:** EC-005/008 — RAG default provider no longer resolves to Groq
**Steps:**
1. POST `/rag/query` with NO `provider` field.
**Expected Result:** `served_provider: mistral`, `primary_failure: null`; `QueryRequest` defaults no longer pin `groq`/`groq/compound` (the `req.provider or _DEFAULT` could never fall through before).
**Automation Hint:** live/integration assert on served provider.
**Source:** Part254 (`9747241`)

### TC-P12-044
**Category:** Bug-Regression
**Test Name:** `complete()` dispatches Mistral/Perplexity, not just groq/openai
**Steps:**
1. Call `complete()` with `provider="mistral"`.
**Expected Result:** Routes through `stream_groq_openai()` via `OPENAI_COMPAT_BASES` (previously returned `""` for Mistral) — unblocks contradiction judge, query expansion, eval, text-to-image enhance.
**Automation Hint:** pytest on `complete()` provider dispatch.
**Source:** Part254

### TC-P12-045
**Category:** Architecture
**Test Name:** Groq removed from every default/automatic path (BYOK kept)
**Steps:**
1. Grep defaults in `query.py`, `contradictions.py`, `evaluate*.py`, `document/_llm.py`, `generation.py`, `drift/*`, plus `ml-eda`'s `_suggest.py`.
**Expected Result:** No Groq in defaults/cascades; Groq remains BYOK-selectable only; dead `_groq_vision_raw` removed.
**Automation Hint:** grep assertion + provider-cascade test.
**Source:** Part254

### TC-P12-046
**Category:** Architecture
**Test Name:** Edge cases are dual-tracked (EDGECASES.md + numbered TC)
**Steps:**
1. Add a new edge case.
**Expected Result:** It appears in BOTH `EDGECASES.md` and a numbered TC entry; all 8 EC items from this pass are resolved, none open.
**Automation Hint:** doc-consistency check.
**Source:** Part254

---

## Deepfake A/V Detection & Domain NER (Part 255)

### TC-P12-047
**Category:** Feature
**Test Name:** Deepfake AV-sync uses DTW (beats correlation)
**Steps:**
1. Score a genuinely-synced real clip vs shuffled/shifted negative controls.
**Expected Result:** Synced clip 0.267 < all 5 shuffled controls (0.289–0.322) and the shifted control (0.274); correlation-based scoring failed and was dropped.
**Automation Hint:** pytest on `mm_deepfake.py` DTW path with fixtures.
**Source:** Part255 (`b31f19c`)

### TC-P12-048
**Category:** Architecture
**Test Name:** YuNet replaces Haar cascades (absent in opencv 5.x)
**Steps:**
1. Attempt `cv2.CascadeClassifier`; load `models/face-detection-yunet.onnx`.
**Expected Result:** Haar cascades don't exist in `opencv-python-headless` 5.0.0; YuNet (DNN module, bundled ONNX) detects faces + landmarks.
**Automation Hint:** pytest — assert YuNet loads and returns landmarks on a real face.
**Source:** Part255

### TC-P12-049
**Category:** Feature
**Test Name:** Voice-clone spectral-flatness signal fires on synthetic dub
**Steps:**
1. Run deepfake detection on real video + dubbed macOS `say` audio.
**Expected Result:** AV-desync and voice-artifact both fire (100% / 79%); clean clip produces no false positive.
**Automation Hint:** pytest with the synthetic manipulated clip.
**Source:** Part255

### TC-P12-050
**Category:** Feature
**Test Name:** Domain NER extracts legal/financial/medical terms
**Steps:**
1. Ingest a doc with legal-clause, financial-term, and medical-condition text.
**Expected Result:** `entities.py` emits `legal_clause`/`financial_term`/`medical_condition`; plain prose yields zero spurious matches; three new filter chips render.
**Automation Hint:** pytest on the regexes + Playwright chip check.
**Source:** Part255 (`84ae970`)

### TC-P12-051
**Category:** Architecture
**Test Name:** NER pipeline is generic over `ENTITY_TYPES` (no per-type wiring)
**Steps:**
1. Add a new entity type to `ENTITY_TYPES` + one label-map line.
**Expected Result:** `retrieve.py` `has_{type}` filter and the citation render pick it up automatically (already generic).
**Automation Hint:** unit test adding a dummy type.
**Source:** Part255

### TC-P12-052
**Category:** UI
**Test Name:** Multimodal-RAG mobile tabbed workspace (Documents/Evidence/Chat)
**Steps:**
1. Load the tool at ~376px width with documents present.
**Expected Result:** Below `lg`, a tab switcher shows one bounded, internally-scrolling panel; desktop 3-column view byte-identical at `lg`.
**Automation Hint:** Playwright at phone width; assert no horizontal overflow + bounded chat list.
**Source:** Part255 (`8afe705`)

### TC-P12-053
**Category:** Bug-Regression
**Test Name:** Zero-document mobile state still shows the upload dropzone
**Steps:**
1. Open the tool on mobile with no documents.
**Expected Result:** `DocumentTray` (holds the dropzone) ignores `mobileTab` when `documents.length === 0` — dropzone not hidden behind the chat default.
**Automation Hint:** Playwright zero-doc mobile.
**Source:** Part255

### TC-P12-054
**Category:** UI
**Test Name:** Action `<select>` groups options into `<optgroup>`s; empty groups omitted
**Steps:**
1. Open the citation action dropdown for an image.
**Expected Result:** Options grouped Describe/Detect/Verify; a group with no visible options doesn't render; `<select>` has an aria-label.
**Automation Hint:** Playwright DOM assert on optgroups.
**Source:** Part255 (`87e6fc1`)

### TC-P12-055
**Category:** UI
**Test Name:** Skeleton loading states appear during real multi-second waits
**Steps:**
1. Trigger a contradiction check and an answer wait.
**Expected Result:** `Skeleton.tsx` shows 6 (contradiction) / 9 (evidence cards) pulse blocks, then clears; page height doesn't balloon.
**Automation Hint:** Playwright 50ms-post-click DOM capture.
**Source:** Part255 (`b03a84f`)

---

## Face Deanonymization, Keystroke Inference, Movement Comparison (Part 256)

### TC-P12-056
**Category:** Feature
**Test Name:** Face deanonymization demo ranks a gallery by real cosine similarity
**Steps:**
1. Upload a target + 2–10 gallery photos.
**Expected Result:** `mm_face_reid_demo.py` reuses face-cloak's embed helpers; same-person ≈ 0.99, different-person ≈ 0.46 ("uncertain").
**Automation Hint:** API test with two distinct people.
**Source:** Part256 (`3a69923`)

### TC-P12-057
**Category:** E2E
**Test Name:** "Protect & re-test" breaks the re-identification
**Steps:**
1. Run the search, then click "Protect target & re-test" (calls existing `/mm-face-cloak/run`).
**Expected Result:** Best-match similarity flips (e.g. 0.9935 → -0.7737), verdict "same" → "different."
**Automation Hint:** Playwright on live site; assert score drop + verdict flip.
**Source:** Part256

### TC-P12-058
**Category:** Feature
**Test Name:** Video-call keystroke inference detects WHEN keys pressed (never WHAT)
**Steps:**
1. Upload a typing video; run analysis.
**Expected Result:** Deterministic frame-stepping (20 fps) + prominence tap detection → keystroke timeline, WPM, rhythm; no character output; disclosure present.
**Automation Hint:** Playwright on a real typing clip; assert events/WPM, no characters.
**Source:** Part256 (`cb6e9f9`)

### TC-P12-059
**Category:** Bug-Regression
**Test Name:** Tap detection handles flat-topped peak plateaus
**Steps:**
1. Feed a synthetic fingertip series with equal-height plateau peaks.
**Expected Result:** Radius-2 local-max + directional valley-walk recovers all taps (naive single-neighbor diff missed plateau peaks).
**Automation Hint:** unit test on `keystrokeSignal.ts`.
**Source:** Part256

### TC-P12-060
**Category:** Feature
**Test Name:** Movement comparison aligns clips on a 0–100% phase axis
**Steps:**
1. Compare two same-exercise clips of different durations (e.g. 4s vs 8s).
**Expected Result:** `resampleToPhase` yields byte-identical output for same-shape/different-duration curves; 6 joint-angle curves ranked worst-first by RMS deviation.
**Automation Hint:** unit test on `jointAngles.ts` + Playwright chart render.
**Source:** Part256 (`a288ada`)

### TC-P12-061
**Category:** Data
**Test Name:** Movement comparison uses 3D world landmarks (distance-invariant)
**Steps:**
1. Inspect the angle computation source.
**Expected Result:** Uses metric 3D world landmarks, not normalized 2D image coords; `angleAtJoint` returns exact 90°/180°/0° for constructed triples.
**Automation Hint:** unit test on geometry.
**Source:** Part256

---

## Email Auth Checker & Extension Permission Analyzer (Part 257)

### TC-P12-062
**Category:** Feature
**Test Name:** Email auth checker parses `Authentication-Results` + live DNS
**Steps:**
1. Paste real headers (sample button) and a weak-signal case.
**Expected Result:** Relays spf/dkim/dmarc verdicts AND runs independent SPF/`_dmarc`/DKIM DNS lookups; reports policy strictness + From-domain alignment; "Weak authentication" not overclaimed as "phishing."
**Automation Hint:** unit test `check_spf_record`/`check_dmarc_record` against a known domain.
**Source:** Part257 (`e1530f4`)

### TC-P12-063
**Category:** Bug-Regression
**Test Name:** Public-DNS fallback only on genuine network failure
**Steps:**
1. Force the default resolver to time out; then test an authoritative NXDOMAIN.
**Expected Result:** Falls back to 8.8.8.8/1.1.1.1 only on network failure, not on NXDOMAIN/NoAnswer (avoids doubling latency on the common no-record case).
**Automation Hint:** pytest — stub resolver timeout vs NXDOMAIN.
**Source:** Part257

### TC-P12-064
**Category:** Feature
**Test Name:** Extension permission analyzer flags dangerous permission combos
**Steps:**
1. Paste a manifest with broad host access + webRequest + cookies.
**Expected Result:** Flagged high-risk with a combo callout; a benign manifest drops to "Low risk."
**Automation Hint:** unit test on `permissionRisk.ts` across fixtures.
**Source:** Part257 (`a1b0572`)

### TC-P12-065
**Category:** Bug-Regression
**Test Name:** `<all_urls>` (MV2) is detected as broad host access
**Steps:**
1. Paste an MV2 `permissions` array containing `<all_urls>`.
**Expected Result:** Detected as broad host access (the `"://"`-substring filter was fixed); combo with webRequestBlocking+cookies flagged high.
**Automation Hint:** unit test on the MV2 case.
**Source:** Part257

### TC-P12-066
**Category:** Architecture
**Test Name:** All 10 Security & Trust tools have User Guide + ToolsAIChat
**Steps:**
1. Open each Security & Trust tool.
**Expected Result:** Every one has a "User Guide" modal + "AI Assistant" widget scoped to that tool's `userGuide.ts` (6 newer tools backfilled, `3b44d75`/`ecfa03b`).
**Automation Hint:** Playwright presence check per tool.
**Source:** Part257

---

## Prompt-Injection Playground & AI-Code Detector (Part 258)

### TC-P12-067
**Category:** Feature
**Test Name:** Prompt-injection playground combines regex evidence + LLM judge
**Steps:**
1. Submit direct-override, indirect, jailbreak, and benign-control inputs.
**Expected Result:** `prompt_injection_check.py` shows raw regex matches + an independent judge verdict; distinct correct risk badges; benign text with "ignore" in a non-attack sense → no false positive.
**Automation Hint:** pytest heuristics (5 cases) + live judge check.
**Source:** Part258 (`03b4177`)

### TC-P12-068
**Category:** Feature
**Test Name:** AI-code detector never outputs a probability/verdict (honest by construction)
**Steps:**
1. Submit AI-style, messy-human, and clean-human snippets.
**Expected Result:** Client stylometry shows caveated signals; the judge stays "inconclusive" unless a genuine LLM chat-artifact tell exists (e.g. trailing "Let me know if…"). No probability anywhere.
**Automation Hint:** pytest stylometry + judge calibration.
**Source:** Part258 (`4c49b10`)

### TC-P12-069
**Category:** Bug-Regression
**Test Name:** No internal `[[memory-link]]` syntax leaks into user-facing copy
**Steps:**
1. Open the AI-code detector guide "Purpose" section.
**Expected Result:** No `[[tool-name]]` cross-link syntax in prose (leak fixed `f326ce4`).
**Automation Hint:** grep guide text / Playwright content assert.
**Source:** Part258

### TC-P12-070
**Category:** Architecture
**Test Name:** Gaussian Splat scanner rejected (CPU-only Space, no GPU)
**Steps:**
1. Check the Space hardware; confirm no 3DGS tool shipped.
**Expected Result:** `hardware.current = cpu-basic`; real 3DGS needs CUDA — rejected rather than relabeled; do not revisit without GPU evidence.
**Automation Hint:** none (process/doc).
**Source:** Part258

### TC-P12-071
**Category:** Feature
**Test Name:** Crime-scene SfM recovers camera geometry within tight error
**Steps:**
1. Run incremental SfM on synthetic ground-truth geometry; then on textured synthetic images.
**Expected Result:** Pose error <0.0001°; 3 photos → ~1119 points/3 cameras; texture-less input stops with a clear message. Disclosed as not forensic-grade (sparse, no bundle adjustment).
**Automation Hint:** pytest on the math against known geometry.
**Source:** Part258 (`a2be6cb`)

### TC-P12-072
**Category:** Bug-Regression
**Test Name:** SfM point cloud renders in front of the Three.js camera
**Steps:**
1. Render a reconstruction in the WebGL viewer.
**Expected Result:** Z negated (OpenCV +Z forward vs Three.js -Z) and camera auto-framed from centroid/radius; `preserveDrawingBuffer:true` so pixel readback is non-zero.
**Automation Hint:** Playwright WebGL pixel readback.
**Source:** Part258 (`6761673`/`e3dccea`)

### TC-P12-073
**Category:** Feature
**Test Name:** Gait comparison segments strides and compares a gait signature
**Steps:**
1. Feed synthetic oscillating knee-angle pose data.
**Expected Result:** Cadence ~59 vs true 60; near-identical gait "similar" (RMS 2.5°) vs different (RMS 18.5°); non-oscillating clip warns; qualitative label only, never a bare %.
**Automation Hint:** unit test on the stride detector + deviation.
**Source:** Part258 (`d39ce02`)

### TC-P12-074
**Category:** Architecture
**Test Name:** Rotoscope build paused on a real torch version conflict
**Steps:**
1. Attempt to deploy Grounded-SAM with `sam2` (torch≥2.5.1) and `facenet-pytorch` (torch<2.3.0).
**Expected Result:** Two `BUILD_ERROR`s (sentence-transformers<6 pin fixed first, then the torch floor/ceiling conflict) → stop per "two failures = stop"; paused, not force-fixed.
**Automation Hint:** none (deploy/process).
**Source:** Part258

---

## Rotoscope Deploy + Four CV Tools (Part 259)

### TC-P12-075
**Category:** Bug-Regression
**Test Name:** `facenet-pytorch --no-deps` unblocks deploy without breaking face tools
**Steps:**
1. Install facenet-pytorch with `--no-deps`; deploy; live-call Face Cloak + Face Re-ID Demo.
**Expected Result:** Build succeeds; Face Cloak (cos sim -0.769 "strong") and Re-ID (self=1.0, no-face handled) still correct — shared dependency verified, not assumed.
**Automation Hint:** live API checks on both tools post-deploy.
**Source:** Part259 (`26e629c`)

### TC-P12-076
**Category:** Bug-Regression
**Test Name:** Rotoscope discloses Grounding DINO has no reliable "nothing matches" signal
**Steps:**
1. Prompt "the elephant" on a flower video.
**Expected Result:** Returns a confident-looking wrong mask (not a clean "couldn't find") — guide corrected to disclose a wrong prompt can produce a plausible-but-wrong result.
**Automation Hint:** API test with a mismatched prompt; assert disclosure copy.
**Source:** Part259 (`d429ae3`)

### TC-P12-077
**Category:** Feature
**Test Name:** Rotoscope tracks/masks the prompted object through all frames
**Steps:**
1. Prompt a flower on a real zoom clip.
**Expected Result:** Grounding DINO localizes (~80%); SAM2 masks just the flower across all 16 frames (not leaves/second bud).
**Automation Hint:** pytest/Playwright on the flower clip.
**Source:** Part259

### TC-P12-078
**Category:** Feature
**Test Name:** Astrophotography anomaly uses dipole-vs-monopole discrimination
**Steps:**
1. Run on a synthetic drifting star field with an injected meteor + a multi-frame satellite.
**Expected Result:** Stars (drift) leave paired +/- dipoles and are suppressed; transients (monopole) are detected; median stack suppresses both; 0 false positives. One honest "possible meteor or satellite" label (drift-based classifier was tested and rejected as unreliable).
**Automation Hint:** pytest with synthetic frames.
**Source:** Part259 (`0c91122`)

### TC-P12-079
**Category:** Feature
**Test Name:** Wildlife re-ID uses purpose-built MegaDescriptor + detect-crop-embed
**Steps:**
1. Compare two different individuals vs the same individual to itself.
**Expected Result:** Different ≈ 0.60 ("different"), same ≈ 1.00 ("same"); OIV7 detector crops the animal first; a 48px avatar is correctly NOT detected (detection is a real gate). License CC-BY-NC-4.0 disclosed.
**Automation Hint:** API test on `mm_wildlife_reid` (or equivalent) with real crops.
**Source:** Part259 (`ff14bf4`)

### TC-P12-080
**Category:** Feature
**Test Name:** PPE compliance reads explicit present/absent classes (never inferred)
**Steps:**
1. Run on higher-res photos of people in/out of PPE and gear laid on the ground.
**Expected Result:** Hardhat 0.72–0.88, vest 0.39–0.69; gear-on-ground correctly "unclear" (no false compliance); compliance read from an explicit fired class, never from absence.
**Automation Hint:** API test on `mm_ppe_compliance.py` with the 3 photos.
**Source:** Part259 (`a7305ec`)

### TC-P12-081
**Category:** Architecture
**Test Name:** PPE model shipped as ONNX (no new AGPL `ultralytics` runtime dep)
**Steps:**
1. Inspect runtime deps for PPE detection.
**Expected Result:** `best.pt` exported to ONNX locally (dev-only ultralytics), served via existing `onnxruntime`; ONNX output verified to match `.pt` on the test photos.
**Automation Hint:** grep requirements — assert no ultralytics; parity test.
**Source:** Part259

### TC-P12-082
**Category:** Feature
**Test Name:** ASL fingerspelling classifier reproduces training accuracy in TS
**Steps:**
1. Run the shipped TS k-NN over the held-out set.
**Expected Result:** 248/314 (79%) matching the Python training script exactly; 24 static letters (J/Z excluded as motion letters); translation+scale normalization (rotation-norm tested and dropped: 75.5%→67.8%).
**Automation Hint:** Node parity test vs the prototype JSON.
**Source:** Part259 (`2c99aa1`)

### TC-P12-083
**Category:** Data
**Test Name:** ASL dataset split pools detected photos (removes drawings)
**Steps:**
1. Rebuild the train/test split from the HF alphabet dataset.
**Expected Result:** Sketch/line-drawing illustrations (MediaPipe can't detect a hand) are pooled out and re-split cleanly — fixes the systematic ~50% vs ~80% detection-rate gap.
**Automation Hint:** data-prep unit check.
**Source:** Part259

### TC-P12-084
**Category:** UI
**Test Name:** Homepage tool cards are alphabetized within each domain
**Steps:**
1. Inspect a domain section's card order.
**Expected Result:** `MLCapabilities.tsx` sorts per-domain `items` via `localeCompare` (source array unchanged).
**Automation Hint:** Playwright assert ordered titles.
**Source:** Part259 (`3d70098`)

---

## Cross-cutting / Process (Parts 250–259)

### TC-P12-085
**Category:** Architecture
**Test Name:** Client-side-only tools make zero backend calls
**Steps:**
1. Network-trace Pose VJ Visuals, Video-Call Keystroke Inference, Movement/Gait Comparison, Extension Permission Analyzer, ASL Fingerspelling.
**Expected Result:** No backend/`/rag` request; MediaPipe/parsing run in-browser.
**Automation Hint:** Playwright network assertion (no API calls).
**Source:** Parts255–259

### TC-P12-086
**Category:** Architecture
**Test Name:** New ONNX/model tools add no new runtime dependency where avoidable
**Steps:**
1. Review deepfake (YuNet), PPE (ONNX), wildlife (timm), SfM (SIFT patent-free).
**Expected Result:** Each reuses existing runtime (`onnxruntime`/`timm`/opencv) — no gratuitous heavy dep; YuNet/ONNX bundled as static assets.
**Automation Hint:** requirements diff review.
**Source:** Parts255–259

### TC-P12-087
**Category:** Backend API
**Test Name:** Every backend deploy is verified with a real functional call (not stage=RUNNING)
**Steps:**
1. After an HF Space upload, poll stage then fire a real request against the production endpoint.
**Expected Result:** Correctness confirmed from returned content, not just `RUNNING` — standing discipline applied across all deploys this range.
**Automation Hint:** deploy-check script pattern.
**Source:** Parts250–259

### TC-P12-088
**Category:** Architecture
**Test Name:** Files near the 400-line cap are modularized before adding
**Steps:**
1. Track `CitationThumbnailPanel.tsx` (→ `useCitationVisualState`/`useVisualizeActions`) and `RagSourceCard.tsx` (→ `RagRetrievalTrace`).
**Expected Result:** Each refactored back under 400 lines with no behavior change before new features landed.
**Automation Hint:** `wc -l` gate in CI.
**Source:** Parts253–255

### TC-P12-089
**Category:** Architecture
**Test Name:** `ml-eda` is a separate Space with its own copy of shared bugs
**Steps:**
1. Confirm `wram1708/ml-eda` deploy of the provider fix + its `MISTRAL_API_KEY` secret.
**Expected Result:** `_suggest.py` default-provider bug fixed on ml-eda too; `/eda/suggest` with no provider streams via Mistral once the secret is set.
**Automation Hint:** live call to the ml-eda Space.
**Source:** Part254

### TC-P12-090
**Category:** Feature
**Test Name:** CAPTCHA Hardening Lab reads the hardened image + parses VLM JSON shape
**Steps:**
1. Upload a CAPTCHA; increase the hardening slider; compare VLM reads.
**Expected Result:** Non-gradient perturbations stack; Mistral vision's forced `{"text": "..."}` JSON is parsed via `_parse_json`; honest framing ("how much hardening it takes").
**Automation Hint:** API/Playwright on `mm_captcha.py`.
**Source:** Part255 (`d24b5a1`/`57adc32`)

### TC-P12-091
**Category:** Feature
**Test Name:** Malware-image triage entropy window is wide enough (1024B)
**Steps:**
1. Run entropy on true `os.urandom()` output.
**Expected Result:** Reads 7.78–7.84 bits/byte and buckets "high" (256B window capped ~7.2 and under-flagged); byte-plot + PE packer-tell parse never execute the file.
**Automation Hint:** pytest on the entropy window + PE fixtures.
**Source:** Part255 (`a7ec9e6`)

### TC-P12-092
**Category:** Architecture
**Test Name:** Password checker calls HIBP range API directly from the browser (k-anonymity)
**Steps:**
1. Check a password's breach exposure.
**Expected Result:** Only a 5-char SHA-1 prefix leaves the browser; `zxcvbn-ts` scores strength locally — a disclosed deviation from the backend-proxy precedent, justified by HIBP being key-less and browser-safe.
**Automation Hint:** Playwright network assert (only prefix sent).
**Source:** Part259 (item #58, `127abea`)

### TC-P12-093
**Category:** UI
**Test Name:** Accessibility: click-only cards/dropzones are keyboard-reachable
**Steps:**
1. Tab to `DocumentTray` rows, `RagSourceCard`, and the ingest dropzone; press Enter.
**Expected Result:** `role="button"` + `tabIndex=0` + `onKeyDown` fire the same action as a click; icon-only buttons have aria-labels; contradiction results use `aria-live`, deepfake box `role="alert"`.
**Automation Hint:** Playwright accessibility-tree + keyboard assertions.
**Source:** Parts254–255

### TC-P12-094
**Category:** Architecture
**Test Name:** Rejected/deferred items are recorded so they aren't re-litigated
**Steps:**
1. Review the pending list's "Deferred — not buildable in this hosted architecture" section.
**Expected Result:** GS scanner (no GPU), fire/smoke (#30), gesture-desktop (#12), live-webcam surveillance (#21), UEBA/process-injection/ransomware-canary, etc. grouped with rationale.
**Automation Hint:** doc presence check.
**Source:** Parts256–259

---

**Total: 94 test cases, Parts 250–259.**
