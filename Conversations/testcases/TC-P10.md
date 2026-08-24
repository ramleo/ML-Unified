# TC-P10 — Parts 201–249

**Prefix:** TC-P10
**Parts covered:** 201–249 (49 sessions)
**Status:** ✅ Complete
**Method:** Inline — no subagents, per explicit user instruction ("keep going" continuing "no agents, complete till part 200" methodology)

Covers: Document Intelligence provider cascade, the full Multimodal RAG architecture and its
MMRAG-01→28 backlog build-out, CV forensics tooling (tampering/signature detection), Image
Inpainting, AI Sharpen/Deblur, homepage redesign (concepts + real build + site-wide restyle),
Depth Parallax, Plant Growth Quantification, QR Phishing Detector, Photo Library Visual Search,
Adversarial Robustness Lab (formerly Adversarial Examples) full attack/defense buildout, Face
Cloak, Style Cloak, adversarial training defense, and the Part 248–249 site-wide theme
consistency sweep + ML-Unified CI fix + theme toggle rollout.

---

## Document Intelligence — provider cascade & OCR pipeline (Parts 201–210 era)

### TC-P10-001
**Category:** Backend API
**Test Name:** LLM provider cascade falls through in declared order
**Steps:**
1. Force Groq to return an error (invalid key or 429).
2. Submit a Document Intelligence extraction request.
3. Inspect the response's provider-used field.
**Expected Result:** Request succeeds via the next provider in the cascade (Mistral → Gemini → Cohere → Cerebras), not a hard failure.
**Automation Hint:** pytest, mock each provider client to raise/succeed in sequence, assert final provider field.
**Source:** Part201

### TC-P10-002
**Category:** Feature
**Test Name:** OCR-first pipeline runs before LLM extraction
**Steps:**
1. Upload a scanned (image-only) PDF with no embedded text layer.
2. Run Document Intelligence extraction.
**Expected Result:** OCR text is extracted first and passed to the LLM stage; extraction does not fail on an empty native-text PDF.
**Automation Hint:** pytest against `/document-intelligence` endpoint with a synthetic scanned PDF fixture.
**Source:** Part201

### TC-P10-003
**Category:** Feature
**Test Name:** Hash-based result caching returns cached extraction on identical re-upload
**Steps:**
1. Upload document A, run extraction, record latency.
2. Re-upload the identical file (same bytes) and run extraction again.
**Expected Result:** Second run returns the cached result near-instantly (no re-call to any LLM provider).
**Automation Hint:** pytest — assert provider-call count is 0 on the second run via a call-counting mock.
**Source:** Part201

### TC-P10-004
**Category:** Feature
**Test Name:** HITL correction feedback updates the stored extraction
**Steps:**
1. Run extraction on a document.
2. Manually correct one extracted field via the correction UI.
3. Re-fetch the document's extraction result.
**Expected Result:** The corrected value persists and is returned on subsequent fetches, not overwritten by the original LLM output.
**Automation Hint:** Playwright — edit a field, reload, assert edited value still shown.
**Source:** Part201-210 range

### TC-P10-005
**Category:** Bug-Regression
**Test Name:** Reasoning-model `<think>` blocks don't leak into extracted output
**Steps:**
1. Force the Groq qwen reasoning model path with a tight `max_tokens`.
2. Run extraction on a document likely to trigger truncated reasoning output.
**Expected Result:** Any unterminated `<think>` block is stripped before the result is shown to the user; empty-field fallback to raw text kicks in rather than showing raw think-tags.
**Automation Hint:** pytest with a mocked provider response containing an unterminated `<think>` tag; assert output is clean.
**Source:** Part201-210 range

---

## Multimodal RAG — core architecture (Parts ~205–243)

### TC-P10-006
**Category:** Data
**Test Name:** Chunk metadata carries chunk_type/page/bbox through the full pipeline
**Steps:**
1. Ingest a PDF with a mix of text, a chart, and a table.
2. Run a query that should cite the chart.
3. Inspect the returned citation's metadata.
**Expected Result:** Citation includes correct `chunk_type`, `page`, and `bbox` fields matching the actual chart location.
**Automation Hint:** pytest against ingest+query endpoints with a synthetic multi-visual PDF.
**Source:** Part2xx (MMRAG core)

### TC-P10-007
**Category:** Backend API
**Test Name:** RRF fusion applies type_boost and list_weights correctly
**Steps:**
1. Issue a query where a table chunk and a text chunk have similar base relevance scores.
2. Inspect the fused ranking.
**Expected Result:** The table chunk's boosted rank reflects the configured `type_boost` multiplier, verifiable by comparing pre- and post-fusion scores.
**Automation Hint:** pytest — call the fusion function directly with known input scores, assert output ordering.
**Source:** Part2xx (MMRAG core)

### TC-P10-008
**Category:** Feature
**Test Name:** Semantic cache hits on paraphrased query via ctx_hash
**Steps:**
1. Run query "What was Q3 revenue?" against a document, record latency/provider calls.
2. Run a paraphrased query "How much revenue in Q3?" against the same document.
**Expected Result:** Second query is served from the semantic cache (same `ctx_hash` bucket), not a fresh LLM call.
**Automation Hint:** pytest — mock LLM call counter, assert 0 additional calls on the paraphrase.
**Source:** Part2xx (MMRAG core)

### TC-P10-009
**Category:** Feature
**Test Name:** Groundedness score flags ungrounded answers
**Steps:**
1. Submit a query whose correct answer is present in the corpus.
2. Submit a query designed to make the LLM hallucinate an unsupported claim.
**Expected Result:** The grounded answer scores high groundedness; the hallucinated answer scores low and is flagged to the user.
**Automation Hint:** pytest with a fixed corpus and two known-good/known-bad query/answer pairs, assert score threshold split.
**Source:** Part2xx (MMRAG core)

### TC-P10-010
**Category:** Bug-Regression
**Test Name:** Groundedness scorer doesn't false-flag correct non-English answers
**Steps:**
1. Ingest a document, ask a question in a non-English language with a factually correct answer.
2. Check the groundedness score.
**Expected Result:** Score reflects true groundedness, not artificially low due to cross-language sentence-embedding mismatch.
**Automation Hint:** pytest — regression test using the specific language pair that previously false-flagged (see MMRAG-12).
**Source:** MMRAG-12 / Part2xx

### TC-P10-011
**Category:** Feature
**Test Name:** Self-correction retry loop fires on low-groundedness first pass
**Steps:**
1. Trigger a query likely to produce a low-groundedness first answer.
2. Inspect whether a retry occurred and whether the final answer differs.
**Expected Result:** A retry is attempted with adjusted retrieval/prompt when groundedness is below threshold; final returned answer's groundedness is logged.
**Automation Hint:** pytest — mock first LLM call to return an ungrounded answer, assert a second call is made.
**Source:** Part2xx (MMRAG core)

### TC-P10-012
**Category:** UI
**Test Name:** Retrieval-trace panel shows real intermediate RRF scores
**Steps:**
1. Run a query, open the "why was this cited" trace panel on a citation.
**Expected Result:** Panel shows real per-chunk scores (embedding similarity, RRF-fused rank, type boost applied), not placeholder/zero values.
**Automation Hint:** Playwright — open panel, assert numeric fields are non-zero and match backend response payload.
**Source:** MMRAG-08 / project_mmrag08_trace_panel

### TC-P10-013
**Category:** Feature
**Test Name:** Video-frame citation seeks player to correct timestamp
**Steps:**
1. Ingest a video, ask a question answered by a specific moment.
2. Click the resulting citation.
**Expected Result:** Video player seeks to the real timestamp associated with that frame, not 0:00.
**Automation Hint:** Playwright — click citation, read player's `currentTime`, assert within tolerance of expected timestamp.
**Source:** MMRAG-09

### TC-P10-014
**Category:** Feature
**Test Name:** FFT-based scene-cut sampling picks distinct frames
**Steps:**
1. Ingest a multi-scene video.
2. Inspect which frames were sampled for indexing.
**Expected Result:** Sampled frames correspond to real scene changes (FFT-detected cuts), not fixed-interval sampling only.
**Automation Hint:** pytest against the frame-sampling function with a synthetic video with known cut points.
**Source:** MMRAG-11

### TC-P10-015
**Category:** Bug-Regression
**Test Name:** Scene-cut sampling falls back gracefully on a single-scene video
**Steps:**
1. Ingest a video with no real scene cuts.
2. Confirm ingestion completes without error.
**Expected Result:** Falls back to fixed-interval sampling; no crash or empty frame set.
**Automation Hint:** pytest with a single-scene synthetic video fixture.
**Source:** MMRAG-11

### TC-P10-016
**Category:** Feature
**Test Name:** Region-specific captioning distinguishes chart from logo on same page
**Steps:**
1. Ingest a PDF page containing both a chart and a company logo.
2. Query about the chart specifically.
**Expected Result:** Returned caption/citation describes the chart's content, not a blended chart+logo description.
**Automation Hint:** pytest with a synthetic 2-region PDF fixture (per MMRAG-13's own verification method).
**Source:** MMRAG-13

### TC-P10-017
**Category:** Feature
**Test Name:** Chart data extraction pulls real numeric values into a citable table
**Steps:**
1. Ingest a document containing a bar chart with known values.
2. Ask a question requiring a specific chart value.
**Expected Result:** Answer cites an extracted numeric table matching the chart's real values (within reasonable OCR/extraction tolerance).
**Automation Hint:** pytest against a synthetic ground-truth chart image, assert extracted values match expected within tolerance.
**Source:** MMRAG-14

### TC-P10-018
**Category:** Feature
**Test Name:** Detect Faces button shows every detected face on a citation image
**Steps:**
1. Query a document containing a photo with multiple people.
2. Click "Detect Faces" on the resulting citation.
**Expected Result:** All detected faces are boxed/highlighted on the image, not just one.
**Automation Hint:** Playwright — click button, count highlighted bounding boxes, compare to known face count in fixture image.
**Source:** project_detect_faces_button

### TC-P10-019
**Category:** Feature
**Test Name:** Contract/Invoice Reconciliation pairs contract-vs-invoice only
**Steps:**
1. Ingest one contract and two invoices, one matching and one with a discrepancy.
2. Run reconciliation.
**Expected Result:** Contradictions are flagged only for contract-vs-invoice comparisons; invoice-vs-invoice pairs are not compared (avoiding the generic detector's false-positive pattern).
**Automation Hint:** pytest — assert the comparison-pair list excludes any invoice-invoice pair.
**Source:** MMRAG-20

### TC-P10-020
**Category:** Bug-Regression
**Test Name:** Reconciliation judge doesn't false-flag paraphrased-but-matching terms
**Steps:**
1. Create a contract clause and an invoice line that say the same thing in different wording.
2. Run reconciliation.
**Expected Result:** Known small-model false positive is documented; test asserts current behavior (may still occasionally flag) rather than silently regressing further.
**Automation Hint:** pytest regression fixture with a known paraphrase pair; track flag rate over time.
**Source:** MMRAG-20

---

## MMRAG backlog features — query & ingestion quality (Parts 2xx)

### TC-P10-021
**Category:** Feature
**Test Name:** Blur/quality detection flags a low-quality ingested image
**Steps:**
1. Ingest a deliberately blurred image as part of a document.
2. Check ingestion metadata/warnings.
**Expected Result:** Image is flagged as low-quality; downstream captioning/OCR confidence reflects this.
**Automation Hint:** pytest with a synthetically blurred fixture vs. a sharp control.
**Source:** MMRAG backlog (blur/quality detection)

### TC-P10-022
**Category:** Feature
**Test Name:** Query decomposition splits a compound question into sub-queries
**Steps:**
1. Submit a multi-part question ("What was revenue in Q1 and Q3, and which grew more?").
2. Inspect the retrieval trace.
**Expected Result:** Question is decomposed into sub-queries, each retrieved separately, then synthesized into one answer.
**Automation Hint:** pytest — mock retrieval, assert multiple sub-query calls made for one compound input.
**Source:** MMRAG backlog (query decomposition)

### TC-P10-023
**Category:** Feature
**Test Name:** NER extraction surfaces named entities in a citation
**Steps:**
1. Ingest a document with named people/organizations.
2. Query about one entity.
**Expected Result:** Entity is correctly recognized and highlighted/linked in the response.
**Automation Hint:** pytest against a fixture document with known entities.
**Source:** MMRAG backlog (NER)

### TC-P10-024
**Category:** Feature
**Test Name:** Audio ingestion transcribes and indexes spoken content
**Steps:**
1. Ingest an audio file with known spoken content.
2. Query about content only present in the audio.
**Expected Result:** Correct answer retrieved and cited back to the audio segment/timestamp.
**Automation Hint:** pytest with a synthetic short audio fixture with known transcript.
**Source:** MMRAG backlog (audio ingestion)

### TC-P10-025
**Category:** Feature
**Test Name:** Visual grounding returns a bounding box for an object-referencing query
**Steps:**
1. Ingest an image containing several objects.
2. Ask "where is the [object]?"
**Expected Result:** Response includes a bounding box localizing the referenced object, using the OIV7 601-class ONNX detector.
**Automation Hint:** pytest with a fixture image containing a known-labeled object.
**Source:** project_object_detection_grounding

### TC-P10-026
**Category:** Bug-Regression
**Test Name:** Object info placed outside citation bracket is not ignored by the LLM
**Steps:**
1. Ingest an image with a detected object, ask a question relying on that object's identity.
2. Inspect whether the LLM's answer incorporates the detected object info.
**Expected Result:** LLM answer reflects the object info; regression test for the earlier bug where in-bracket object info was ignored.
**Automation Hint:** pytest — assert answer text references the detected object label.
**Source:** project_object_detection_grounding

---

## CV Forensics — tampering & signature detection

### TC-P10-027
**Category:** Feature
**Test Name:** Merged three-signal tampering detector doesn't flag solo ELA hits
**Steps:**
1. Run tampering detection on an untampered but high-detail (fine-texture) image.
2. Run on a genuinely tampered image.
**Expected Result:** Fine-detail-only ELA hit on the clean image is dropped (not reported as tampering); the genuinely tampered image is still flagged via corroborating signals.
**Automation Hint:** pytest with a clean high-detail fixture and a known-tampered fixture.
**Source:** project_tampering_detector_precision

### TC-P10-028
**Category:** Feature
**Test Name:** Signature detection works via substitute public model
**Steps:**
1. Upload a document with a handwritten signature.
2. Run signature detection.
**Expected Result:** Signature region is correctly detected using the substitute public model (after the original gated HF model was blocked).
**Automation Hint:** pytest with a fixture document containing a known signature location.
**Source:** CV forensics (signature detection)

### TC-P10-029
**Category:** Feature
**Test Name:** SlimSAM mask refinement tightens a detected region's boundary
**Steps:**
1. Run detection producing a coarse bounding box on an object.
2. Apply SlimSAM refinement.
**Expected Result:** Refined mask more closely follows the object's actual outline than the coarse box.
**Automation Hint:** pytest — compare refined mask IoU against a known ground-truth mask, assert improvement over the coarse box.
**Source:** CV forensics (SlimSAM)

### TC-P10-030
**Category:** Feature
**Test Name:** Table Transformer extracts tabular structure correctly
**Steps:**
1. Ingest a document containing a table.
2. Run table extraction.
**Expected Result:** Rows/columns are correctly delineated matching the real table structure.
**Automation Hint:** pytest with a synthetic table fixture with known row/column count.
**Source:** CV forensics (Table Transformer)

---

## Image Inpainting / Object Remover

### TC-P10-031
**Category:** Feature
**Test Name:** LaMa inpainting quality-rejection falls back to plain white fill
**Steps:**
1. Trigger an inpainting run where LaMa's output fails a quality check.
2. Inspect the returned result.
**Expected Result:** Falls back to a plain white fill for the removed region rather than returning a low-quality LaMa artifact.
**Automation Hint:** pytest — mock LaMa to return a known-bad result, assert fallback path triggers.
**Source:** Image Inpainting tool

### TC-P10-032
**Category:** Feature
**Test Name:** Freehand drawing mask removes only the drawn region
**Steps:**
1. Upload an image, freehand-draw a mask over one object.
2. Run object removal.
**Expected Result:** Only the drawn region is removed/inpainted; rest of image untouched.
**Automation Hint:** Playwright — draw mask, run, diff output image outside mask region against original (should be near-identical).
**Source:** Image Inpainting tool

### TC-P10-033
**Category:** Feature
**Test Name:** AI-fill via Gemini used after FLUX/ZeroGPU quota exhaustion
**Steps:**
1. Simulate FLUX ZeroGPU quota being exhausted.
2. Trigger an AI-fill inpainting request.
**Expected Result:** Falls back to Gemini-based fill rather than failing the request outright.
**Automation Hint:** pytest — mock FLUX call to raise a quota error, assert Gemini path is invoked.
**Source:** Image Inpainting tool (FLUX/ZeroGPU incident)

### TC-P10-034
**Category:** Backend API
**Test Name:** Daily call-budget guard blocks further AI-fill calls once exceeded
**Steps:**
1. Simulate the daily call count reaching the configured budget cap.
2. Attempt one more AI-fill request.
**Expected Result:** Request is rejected with a clear budget-exceeded message, not silently billed further.
**Automation Hint:** pytest — set counter to cap, assert 4xx response with budget-exceeded reason.
**Source:** Image Inpainting tool (real billing incident)

---

## AI Sharpen/Deblur

### TC-P10-035
**Category:** Feature
**Test Name:** Dual-corroborated OCR verification rejects a hallucinated sharpen result
**Steps:**
1. Run sharpen/deblur on an image containing text.
2. Compare OCR output on the sharpened result against OCR on the original blurred image via two independent OCR passes.
**Expected Result:** If the two OCR passes disagree substantially (indicating hallucinated detail), the result is flagged/rejected rather than presented as reliable.
**Automation Hint:** pytest with a fixture where sharpening is known to hallucinate text; assert rejection path fires.
**Source:** AI Sharpen/Deblur tool

### TC-P10-036
**Category:** Feature
**Test Name:** Sharpen result accepted when both OCR passes agree
**Steps:**
1. Run sharpen/deblur on a mildly blurred image with real, recoverable text.
2. Run the dual-OCR check.
**Expected Result:** Both OCR passes agree; result is presented as verified/reliable.
**Automation Hint:** pytest with a fixture where ground-truth text is known and recoverable.
**Source:** AI Sharpen/Deblur tool

---

## Homepage redesign — concept exploration & real build (Parts 244–245)

### TC-P10-037
**Category:** UI
**Test Name:** Live site uses horizontal scroll when capability count isn't divisible by 3
**Steps:**
1. Count real capabilities.ts entries (pre-redesign: 22, not divisible by 3).
2. Load the pre-redesign homepage.
**Expected Result:** Confirms the documented bug: `useScroll = capabilities.length % 3 !== 0` puts the site in horizontal-scroll mode.
**Automation Hint:** Regression test for the old logic — not applicable post-redesign; kept as historical record.
**Source:** Part244

### TC-P10-038
**Category:** UI
**Test Name:** FlipCard flips 180° on hover revealing detail panel
**Steps:**
1. Load the real (post-redesign) homepage capabilities section.
2. Hover over a capability card.
**Expected Result:** Card rotates via `transform: rotateY(180deg)` (verifiable via computed `matrix3d`), revealing description/stat/tags/action buttons on the back face; grid does not reflow.
**Automation Hint:** Playwright `browser_hover`, read computed `transform` matrix, assert it matches `matrix3d(-1,0,0,0, 0,1,0,0, 0,0,-1,0, 0,0,0,1)`.
**Source:** Part245

### TC-P10-039
**Category:** Bug-Regression
**Test Name:** Capability search matches strictly by title-starts-with, not substring
**Steps:**
1. Type "p" into the capabilities search bar.
2. Inspect the filtered result set.
**Expected Result:** Only cards whose title starts with "p" (case-insensitive) appear — e.g. Pipeline Builder, Pipeline Cinema, Photo Library Visual Search, Plant Growth Quantification — not cards merely containing "p" elsewhere in the title/description/tags.
**Automation Hint:** Playwright — type query, DOM-query visible card titles, assert exact expected set.
**Source:** Part245 (2 failed iterations before the fix)

### TC-P10-040
**Category:** Feature
**Test Name:** Capability cards are grouped into 4 real domains
**Steps:**
1. Load the homepage capabilities section.
2. Inspect the domain section headers and card membership.
**Expected Result:** 22 cards render under exactly 4 domain clusters (ML Pipeline: 11, Language & Documents: 4, Computer Vision: 5, Security & Trust: 2 as of this build).
**Automation Hint:** Playwright DOM query — count cards per cluster heading, assert totals.
**Source:** Part245

### TC-P10-041
**Category:** UI
**Test Name:** Capability search bar stays sticky while scrolling
**Steps:**
1. Load the homepage, scroll the page down past the capabilities section's top.
2. Check the search bar's position.
**Expected Result:** Search bar remains pinned near the top of the viewport (sticky), not scrolling away with the page.
**Automation Hint:** Playwright — scroll, read `getBoundingClientRect().top` of the search bar before/after, assert it stays within the sticky offset.
**Source:** Part245 (real gap between mockup and shipped code, fixed this session)

### TC-P10-042
**Category:** UI
**Test Name:** Restyled Skills/News/Timeline/Contact/Footer keep all real content
**Steps:**
1. Load the homepage after the site-wide restyle.
2. Count tags in Skills, jobs in Timeline, links in Contact, links in Footer.
**Expected Result:** Skills shows all 17+ tags per category, Timeline shows all 6 real jobs, Contact shows 4 real links, Footer shows 13 real links — none trimmed to match the earlier mockup's simplified content.
**Automation Hint:** Playwright DOM counts per section, compare against known real content counts.
**Source:** Part245

### TC-P10-043
**Category:** Bug-Regression
**Test Name:** Live ML Apps cards render at equal height regardless of description length
**Steps:**
1. Load the homepage's Live ML Apps section.
2. Measure the rendered height of all three project cards.
**Expected Result:** All three cards render at the same height (461px in the verified build), via `alignItems: stretch` + a 3-line description clamp with See more/less toggle — not via `alignItems: start` sizing each card independently.
**Automation Hint:** Playwright — read `getBoundingClientRect().height` for all three cards, assert equal.
**Source:** Part246 (fixed a regression introduced in Part245's dead-space fix)

### TC-P10-044
**Category:** UI
**Test Name:** Project card description "See more" toggle expands without affecting siblings
**Steps:**
1. Click "See more" on one project card.
2. Check the other two cards.
**Expected Result:** Only the clicked card expands; sibling card heights are unaffected.
**Automation Hint:** Playwright — click toggle, measure all three card heights before/after, assert only the clicked one changed.
**Source:** Part246

---

## Adversarial Robustness Lab (formerly Adversarial Examples) — attacks & defenses

### TC-P10-045
**Category:** Feature
**Test Name:** Targeted FGSM/PGD attack rejects a no-op target
**Steps:**
1. Choose a target label identical to the model's current (correct) prediction.
2. Run a targeted attack.
**Expected Result:** Request is rejected with a clear 400 error rather than trivially "succeeding" with zero perturbation.
**Automation Hint:** pytest against `/mm-adversarial/run` with `target == current_prediction`, assert 400.
**Source:** Part246

### TC-P10-046
**Category:** Feature
**Test Name:** Targeted PGD reliably forces a chosen wrong label at sufficient epsilon
**Steps:**
1. Run targeted PGD at eps=0.08 with target "golden retriever" on a photo not of a dog.
2. Check the "Target achieved" badge.
**Expected Result:** Attack succeeds; badge shows "Target achieved".
**Automation Hint:** pytest with the real verified fixture image and target label, assert final prediction matches target.
**Source:** Part246 (verified locally and on deployed Space)

### TC-P10-047
**Category:** Feature
**Test Name:** Randomized smoothing reports vote_confidence as an honest instability signal
**Steps:**
1. Run randomized smoothing on a PGD-attacked image at sigma=0.25.
2. Inspect the returned `vote_confidence`.
**Expected Result:** Even when the majority-vote label recovers the correct class, `vote_confidence` can be shown low (~0.3–0.4), not hidden behind a single point prediction.
**Automation Hint:** pytest — assert `vote_confidence` field is present and reflects fraction of the 25 samples agreeing.
**Source:** Part246

### TC-P10-048
**Category:** Bug-Regression
**Test Name:** Randomized smoothing sigma=0.15 does not meaningfully disrupt an attack
**Steps:**
1. Run randomized smoothing at sigma=0.15 on a PGD-attacked image.
**Expected Result:** Documented finding: attacker's wrong label persists in ~96% of votes — regression baseline to confirm sigma=0.25 default remains a meaningfully better setting.
**Automation Hint:** pytest comparing vote agreement at sigma=0.15 vs sigma=0.25 on the same fixture.
**Source:** Part246

### TC-P10-049
**Category:** Feature
**Test Name:** Transferability check reports whether a different architecture is also fooled
**Steps:**
1. Run an FGSM attack, enable `check_transfer`.
2. Run a PGD attack, enable `check_transfer`.
**Expected Result:** FGSM's single-step perturbation does NOT transfer to ResNet18 at tested epsilons; PGD's does — matching the documented real finding.
**Automation Hint:** pytest with fixed epsilon values from the original sweep, assert transfer boolean matches documented outcome.
**Source:** Part246

### TC-P10-050
**Category:** Backend API
**Test Name:** ResNet18 and MobileNetV2 share identical ImageNet category ordering
**Steps:**
1. Load both models' category lists.
2. Compare index-for-index.
**Expected Result:** Lists are identical, confirming it's safe to reuse one `_categories` list for both (verified before reuse, not assumed).
**Automation Hint:** pytest — assert list equality.
**Source:** Part246

### TC-P10-051
**Category:** Feature
**Test Name:** Adversarial patch attack: small patch fails to converge, large patch succeeds
**Steps:**
1. Run a targeted patch attack at 10% patch size, 300-step budget.
2. Run at 25% patch size, same budget.
**Expected Result:** 10% patch fails to converge within budget; 25% patch converges in 28–38 steps — matching the documented feasibility sweep.
**Automation Hint:** pytest with fixed patch sizes and step budgets on the same fixture image, assert convergence outcome.
**Source:** Part246

### TC-P10-052
**Category:** Bug-Regression
**Test Name:** Patch attack early-stops once target is reached
**Steps:**
1. Run a targeted patch attack with a 150-step budget on a case known to converge quickly.
2. Inspect the returned `patch_steps` value.
**Expected Result:** `patch_steps` is less than the full budget, reflecting real early-stop, not always reporting the max budget.
**Automation Hint:** pytest — assert `patch_steps < 150` on a fast-converging fixture.
**Source:** Part246

### TC-P10-053
**Category:** Feature
**Test Name:** Black-box query-only attack (SimBA) succeeds untargeted, fails targeted at budget
**Steps:**
1. Run untargeted black-box attack, default query budget.
2. Run targeted black-box attack, 3000-query budget.
**Expected Result:** Untargeted converges (~348 queries); targeted does not converge within 3000 queries — "Target not reached" is shown as the demonstrated point of the attack, not an error.
**Automation Hint:** pytest against the SimBA implementation with fixed random seed for reproducibility, assert convergence/non-convergence matches documented finding.
**Source:** Part246

### TC-P10-054
**Category:** Architecture
**Test Name:** mm_adversarial_models globals are accessed through the module, not re-imported
**Steps:**
1. Grep the codebase for any `from mm_adversarial_models import _model` or `_categories` direct import.
**Expected Result:** No direct imports of the mutable globals exist; all access goes through `models._model`/`models._categories` module-qualified references.
**Automation Hint:** Static grep check as a lint/CI step.
**Source:** Part246 (file-split risk documented in module docstring)

### TC-P10-055
**Category:** UI
**Test Name:** Perturbation preview switches to unamplified view for patch attacks
**Steps:**
1. Select the adversarial-patch method in the UI.
2. Inspect the perturbation preview amplification.
**Expected Result:** Preview uses amplify=1.0 (patch is already visible) instead of the epsilon-based amplification used for FGSM/PGD.
**Automation Hint:** Playwright — select patch method, read preview image data or amplification parameter sent to backend.
**Source:** Part246

### TC-P10-056
**Category:** E2E
**Test Name:** Full attack+defense flow works end-to-end on a real uploaded photo
**Steps:**
1. Upload a real photo.
2. Run PGD attack, then both inference-time defenses (JPEG recompression, randomized smoothing).
**Expected Result:** All stages return real, non-error results; JPEG defense is honestly reported as "mostly ineffective" where applicable.
**Automation Hint:** Playwright E2E against the deployed tool with a real test image.
**Source:** Part246, consistent with original Adversarial Examples build

---

## Face Cloak

### TC-P10-057
**Category:** Feature
**Test Name:** Face Cloak reduces embedding similarity between original and cloaked face
**Steps:**
1. Upload a photo with a detectable face.
2. Run Face Cloak (40 steps, epsilon=0.05).
3. Compute cosine similarity between original and cloaked face embeddings.
**Expected Result:** Similarity drops substantially from 1.0 toward negative values (e.g., ~-0.58 in the verified real test).
**Automation Hint:** pytest with a fixed test photo (e.g. Grace Hopper), assert similarity below a threshold after cloaking.
**Source:** Part246

### TC-P10-058
**Category:** Feature
**Test Name:** Face Cloak masks perturbation to the face-crop region only
**Steps:**
1. Run Face Cloak on a photo where the face occupies a known sub-region.
2. Diff the output image against the original outside the face bounding box.
**Expected Result:** Pixels outside the face-crop region are unchanged (or within epsilon of the compression-only difference); only the face region is perturbed.
**Automation Hint:** pytest — pixel-diff outside bbox, assert near-zero difference.
**Source:** Part246

### TC-P10-059
**Category:** UI
**Test Name:** protection_level badge reflects the real cosine-similarity heuristic
**Steps:**
1. Run Face Cloak and note the returned cosine similarity.
2. Check the displayed protection_level badge (strong/moderate/weak).
**Expected Result:** Badge matches the documented heuristic thresholds (e.g., <~0.3 → strong-ish range per published face-verification ranges), and copy discloses this is a heuristic, not a certified threshold.
**Automation Hint:** Playwright — run tool, read badge text and underlying similarity number, assert consistency with threshold table.
**Source:** Part246

### TC-P10-060
**Category:** Bug-Regression
**Test Name:** Large base64 image response doesn't get client-truncated
**Steps:**
1. Run Face Cloak against the deployed Space with a sufficiently long timeout and `-o` file output rather than a piped parse.
**Expected Result:** Full JSON response with the complete cloaked image is received without an "Unterminated string" parse error.
**Automation Hint:** Integration test against the real deployed endpoint using a client with adequate timeout/streaming, not a piped small-buffer parse.
**Source:** Part246 (real deploy-verification wrinkle — client-side, not backend)

### TC-P10-061
**Category:** UI
**Test Name:** Face Cloak only protects the newly-cloaked photo, disclosed in copy
**Steps:**
1. Load the Face Cloak tool page.
2. Read the disclosure copy near the result panel.
**Expected Result:** Copy explicitly states this protects only the newly-cloaked photo (not already-scraped copies) and can weaken against retrained recognition models.
**Automation Hint:** Playwright — assert disclosure text is present in the DOM.
**Source:** Part246

---

## Style Cloak

### TC-P10-062
**Category:** Feature
**Test Name:** Style Cloak reduces CLIP embedding similarity on a whole image
**Steps:**
1. Upload an artwork image.
2. Run Style Cloak (epsilon=0.06, 40 steps).
3. Compute CLIP cosine similarity between original and cloaked embeddings.
**Expected Result:** Similarity drops substantially (verified real test: 1.0 → -0.36 to -0.42 range).
**Automation Hint:** pytest with a fixed test image, assert similarity below threshold post-cloaking.
**Source:** Part247

### TC-P10-063
**Category:** Data
**Test Name:** Style Cloak protection thresholds use CLIP-calibrated values, not Face Cloak's
**Steps:**
1. Measure cosine similarity between three unrelated synthetic images in CLIP space.
2. Compare against `_STRONG_THRESHOLD`/`_MODERATE_THRESHOLD` in `mm_style_cloak.py`.
**Expected Result:** Baseline unrelated-image similarity in CLIP space (0.65–0.77) is well above Face Cloak's face-embedding baseline, and Style Cloak's thresholds (0.5 / 0.75) are calibrated to this higher baseline, not copied from Face Cloak.
**Automation Hint:** pytest — assert threshold constants differ from Face Cloak's and are consistent with the documented calibration measurement.
**Source:** Part247

### TC-P10-064
**Category:** Feature
**Test Name:** Style Cloak perturbs the whole image, not a sub-region
**Steps:**
1. Run Style Cloak on an image.
2. Diff the output against the original across the entire frame.
**Expected Result:** Perturbation is present across the whole image (no masking to a sub-region), consistent with style being a whole-image property.
**Automation Hint:** pytest — assert non-zero diff in multiple quadrants of the image, not just one region.
**Source:** Part247

### TC-P10-065
**Category:** E2E
**Test Name:** Style Cloak works end-to-end against the deployed HF Space
**Steps:**
1. Upload an image to the live deployed Style Cloak tool.
2. Run the cloak operation.
**Expected Result:** Returns 200 with a real cosine similarity and protection label (verified live: -0.4186, "strong").
**Automation Hint:** Integration test hitting the real deployed endpoint.
**Source:** Part247

---

## Adversarial Training Defense

### TC-P10-066
**Category:** Feature
**Test Name:** Adversarially-trained MNIST model resists PGD where the standard model is fooled
**Steps:**
1. Run PGD attack (eps=0.2) against the standard-trained checkpoint on a sample digit.
2. Run the same attack against the adversarially-trained checkpoint.
**Expected Result:** Standard model's robust accuracy collapses (documented: ~1.09%); adversarially-trained model retains high robust accuracy (documented: ~84.30%) at a real, disclosed clean-accuracy cost (~98.62% → ~96.98%).
**Automation Hint:** pytest using the shipped static checkpoints and the same attack parameters as the original training run, assert accuracy figures are within tolerance of documented values.
**Source:** Part247

### TC-P10-067
**Category:** Backend API
**Test Name:** Each model is attacked with its own gradients (fair white-box attack)
**Steps:**
1. Run the defense comparison endpoint.
2. Inspect that `_run_one_model` computes the attack independently per model.
**Expected Result:** Standard and adversarially-trained models are each attacked using their own gradient direction, not a shared/transferred perturbation.
**Automation Hint:** pytest — assert two distinct perturbation tensors are computed, one per model.
**Source:** Part247

### TC-P10-068
**Category:** Feature
**Test Name:** Digit sample picker uses baked-in real MNIST samples, no dataset download at request time
**Steps:**
1. Call `GET /mm-robust-training/samples`.
**Expected Result:** Returns exactly 10 samples (one per label 0–9) from the baked-in base64 constants; no network/dataset download occurs.
**Automation Hint:** pytest — mock network access to fail, assert endpoint still returns 10 samples successfully.
**Source:** Part247

### TC-P10-069
**Category:** Feature
**Test Name:** Uploaded photo preprocessing centers and inverts a drawn digit correctly
**Steps:**
1. Upload a synthetic "photo" of a dark digit drawn on a light background.
2. Run the upload-based defense comparison.
**Expected Result:** Preprocessing produces a correctly inverted (digit-bright-on-dark), centered, cropped-to-bounding-box 28×28 image; both models classify the clean preprocessed digit correctly before any attack.
**Automation Hint:** pytest with a synthetic PIL-drawn digit fixture, assert preprocessing output matches expected transform and correct baseline classification.
**Source:** Part247

### TC-P10-070
**Category:** Bug-Regression
**Test Name:** Upload path is scoped to digits only; rest of tool still accepts any photo
**Steps:**
1. Attempt to upload a non-digit photo to the adversarial-training upload path.
2. Attempt to upload the same photo to the main attack section.
**Expected Result:** Main attack section accepts the photo as before; the adversarial-training defense's upload path is documented/scoped to digit images (out-of-distribution caveat surfaces via the preview rather than a hard rejection).
**Automation Hint:** Playwright — verify both flows behave per the documented scope without one breaking the other.
**Source:** Part247

### TC-P10-071
**Category:** UI
**Test Name:** Upload-based run shows the preprocessed preview image the models actually saw
**Steps:**
1. Upload a photo of a hand-drawn digit.
2. Run the defense comparison.
**Expected Result:** UI displays the preprocessed 28×28 preview alongside results, not just the original uploaded photo.
**Automation Hint:** Playwright — assert a distinct preview image element is rendered and differs from the raw upload.
**Source:** Part247

### TC-P10-072
**Category:** Data
**Test Name:** Uploaded image size is capped (8MB) with automatic preprocessing disclosed
**Steps:**
1. Attempt to upload an image larger than 8MB.
**Expected Result:** Request is rejected with a clear size-limit message; the 8MB cap and automatic preprocessing are documented in the user guide.
**Automation Hint:** pytest — POST an oversized payload, assert 4xx with a size-related error message.
**Source:** Part247 (user guide update)

---

## Site-wide theme consistency sweep (Parts 248–249)

### TC-P10-073
**Category:** UI
**Test Name:** Every card-hover dropzone across tool pages shares the same `.subtle-card` glow treatment
**Steps:**
1. Visit Preprocessing, Feature Engineering, Optuna, SHAP, Ensemble, and AutoML's Step1Upload pages.
2. Hover each page's file-drop zone.
**Expected Result:** All dropzones show an identical hover glow/lift animation driven by `.subtle-card` + `--acc-glow`, not a mix of animated and non-animated states.
**Automation Hint:** Playwright — for each page, hover the dropzone, read computed `box-shadow`/`transform` before and after, assert all pages show a non-trivial change.
**Source:** Part249

### TC-P10-074
**Category:** Bug-Regression
**Test Name:** Inline single-property transition no longer overrides `.subtle-card`'s full transition
**Steps:**
1. Load the Preprocessing page and AutoML's Step1Upload.
2. Hover the dropzone and observe animation smoothness (not a snap).
**Expected Result:** Hover transitions animate smoothly across all affected properties, not just border-color; regression test for the fixed inline `transition: "border-color 0.2s"` override.
**Automation Hint:** Playwright — read the element's computed `transition` property, assert it lists multiple properties (not overridden to one).
**Source:** Part249

### TC-P10-075
**Category:** Bug-Regression
**Test Name:** Feature Selection dropzone/hero card responds to hover (RepulsionCard replaced)
**Steps:**
1. Load the Feature Selection page.
2. Hover the upload hero card and dropzone.
**Expected Result:** Real hover interactivity is now present (previously did nothing at all, since `MouseRepulsionProvider` was never mounted).
**Automation Hint:** Playwright — hover, assert a real DOM/style change occurs (e.g. `.subtle-card` glow), not zero change.
**Source:** Part249 (`FSUploadHero.tsx` fixed; four other `FSPanels/*.tsx` files still use dead `RepulsionCard`, flagged not fixed)

### TC-P10-076
**Category:** UI
**Test Name:** ConstellationBackground is theme-aware on all 25 tool pages
**Steps:**
1. Load a tool page in dark theme, note the constellation dot/line color.
2. Switch to light theme.
**Expected Result:** Dot/line colors adapt for legibility against the light background (via the added `isLight` check), matching the homepage's own `ParticleGrid` theme behavior.
**Automation Hint:** Playwright — read canvas draw calls or a data attribute reflecting `isLight`, assert it flips with the theme toggle.
**Source:** Part249

### TC-P10-077
**Category:** Bug-Regression
**Test Name:** Pipeline stage cards (`--glass-bg`) retain translucency in light mode
**Steps:**
1. Load Pipeline Builder in light theme.
2. Inspect a stage card's background.
**Expected Result:** Background is translucent (matching `--bg-glass`'s behavior), not the fully opaque value from an earlier deliberate-but-inconsistent decision.
**Automation Hint:** Playwright — read computed `background-color` alpha channel, assert < 1.0.
**Source:** Part249

### TC-P10-078
**Category:** UI
**Test Name:** Colored top-border accent strip is removed from every card sitewide
**Steps:**
1. Visit at least 5 different tool pages including ones from the 2026-08-15 "add everywhere" sweep.
2. Inspect card top borders.
**Expected Result:** No card shows a colored 3px top-border strip anywhere on the site, resolving the prior conflicting decisions.
**Automation Hint:** Playwright — grep-style DOM check for the specific border CSS class/style across a sampled set of pages; assert absent.
**Source:** Part249 (AskUserQuestion resolution: "remove everywhere")

### TC-P10-079
**Category:** Bug-Regression
**Test Name:** multimodal-rag page no longer forces white text in light mode
**Steps:**
1. Load the Multimodal RAG tool page in light theme.
**Expected Result:** Text is legible (not white-on-white); regression test for the removed literal `text-white` root class.
**Automation Hint:** Playwright — read computed text color against the light background, assert sufficient contrast.
**Source:** Part249

### TC-P10-080
**Category:** Bug-Regression
**Test Name:** ToolsAIChat and ModalShell adapt to light theme
**Steps:**
1. Open the AI chat widget and a modal (e.g. AutoML modal) in light theme.
**Expected Result:** Both components render with light-theme-appropriate colors, not their previous 100%-unthemed dark-only styling.
**Automation Hint:** Playwright — toggle theme, screenshot/DOM-check both components' background/text colors change accordingly.
**Source:** Part249

### TC-P10-081
**Category:** Bug-Regression
**Test Name:** Tailwind `bg-black/NN` and `border-white/NN` opacity-slash utilities are theme-safe
**Steps:**
1. Load text-to-sql pages (the concentration point for this bug) in light theme.
**Expected Result:** No element renders with an inappropriate near-black/near-white translucent overlay that was tuned only for dark mode.
**Automation Hint:** Playwright — sample known-affected elements, read computed background/border colors in both themes, assert both are legible.
**Source:** Part249 (missed by every agent's hex/rgba-only regex, found via dedicated follow-up grep)

### TC-P10-082
**Category:** Bug-Regression
**Test Name:** `hover:text-white` no longer makes text-to-sql text invisible on hover in light mode
**Steps:**
1. Load the three affected text-to-sql files in light theme.
2. Hover the affected elements.
**Expected Result:** Text remains visible/legible on hover, not white-on-white.
**Automation Hint:** Playwright — hover, read computed text color, assert contrast against the light background.
**Source:** Part249

### TC-P10-083
**Category:** Bug-Regression
**Test Name:** PreprocessingPanels ConfigurePanel dropdown is visible in light mode
**Steps:**
1. Load the Preprocessing page's Configure panel dropdown in light theme.
**Expected Result:** Dropdown background is not hardcoded `#111827` with `var(--text)` on top (which was invisible); both render legibly together.
**Automation Hint:** Playwright — read computed background/text color pair, assert contrast ratio is sufficient.
**Source:** Part249

### TC-P10-084
**Category:** Bug-Regression
**Test Name:** DbConnectPanel active-tab text is visible in light mode
**Steps:**
1. Load Text-to-SQL's DB connect panel, select a tab, switch to light theme.
**Expected Result:** Active tab text uses the theme accent color, not the hardcoded `#e0e7ff` that was invisible against a light background.
**Automation Hint:** Playwright — read computed color of the active tab label in light mode, assert it's not a near-white value.
**Source:** Part249

### TC-P10-085
**Category:** UI
**Test Name:** Pipeline Cinema idle-state content is legible in light mode
**Steps:**
1. Load Pipeline Cinema in light theme without interacting (idle state).
**Expected Result:** Stage icons/labels render at the light-mode idle opacity (0.75), clearly readable — not the dark-tuned 0.35/0.4 opacity that was nearly invisible against the light gradient.
**Automation Hint:** Playwright screenshot (DOM/SVG component, not canvas — screenshots are reliable here) or computed `opacity` read, assert ≥0.75 in light mode.
**Source:** Part249

### TC-P10-086
**Category:** Bug-Regression
**Test Name:** ML-Unified CI installs requirements-base.txt before running tests
**Steps:**
1. Trigger a CI run on a commit that imports `torch` at module top-level (e.g. `mm_robust_training.py`).
**Expected Result:** CI installs both `requirements-base.txt` and `requirements.txt`; the run succeeds rather than failing on a missing torch import.
**Automation Hint:** CI itself — verified by watching the actual next triggered run go green post-fix (`ea447f0`).
**Source:** Part249

### TC-P10-087
**Category:** Bug-Regression
**Test Name:** Reconciliation and Document Intelligence dropzones show hover glow
**Steps:**
1. Load Contract/Invoice Reconciliation and Document Intelligence pages.
2. Hover each dropzone (`IngestProgressRail.tsx`-backed).
**Expected Result:** Both show the same `.subtle-card` hover glow as every other tool's dropzone.
**Automation Hint:** Playwright — hover, assert computed style change matches other verified dropzones.
**Source:** Part249 (real gap: sweeps were scoped to "colors"/"borders", never "dropzone hover parity")

### TC-P10-088
**Category:** Bug-Regression
**Test Name:** Pipeline Builder's own component folder is fully theme-consistent
**Steps:**
1. Load Pipeline Builder, exercise StageCard, StageModal, ModeSelector, TargetDropdown, StageGrid, WaterfallChart in both themes.
**Expected Result:** No hardcoded `rgba(255,255,255,...)` or `#fff`/`#0f1117`-style colors remain uncorrected; legitimate per-stage identity colors and semantic status colors are preserved (not stripped).
**Automation Hint:** Playwright — sample key elements in both themes, assert legible contrast; static grep for hex/rgba literals outside an allowlist as a CI check.
**Source:** Part249 (entire folder had never been touched by any prior sweep)

### TC-P10-089
**Category:** Bug-Regression
**Test Name:** AutoML modal shows exactly one step indicator, not two
**Steps:**
1. Open the AutoML modal.
2. Count rendered step-indicator components.
**Expected Result:** Exactly one step indicator is shown (header only); the old duplicate inline `AutoMLSteps/StepIndicator.tsx` render in the modal body is gone (component deleted).
**Automation Hint:** Playwright — DOM query for step-indicator elements, assert count == 1.
**Source:** Part249

### TC-P10-090
**Category:** Feature
**Test Name:** Theme toggle is present and functional on every tool page header
**Steps:**
1. Visit each of the 25 tool pages.
2. Click the theme toggle in the header.
**Expected Result:** Toggle is present on all 25 pages (including both of Pipeline Builder's distinct header states), and clicking it flips both `localStorage`'s stored theme and the `light` class on the root element.
**Automation Hint:** Playwright — loop over all 25 tool routes, assert toggle element exists, click it, assert `localStorage` value and root class both changed.
**Source:** Part249

### TC-P10-091
**Category:** E2E
**Test Name:** Theme choice persists across navigation between tool pages
**Steps:**
1. On tool page A, toggle to light theme.
2. Navigate to tool page B.
**Expected Result:** Tool page B loads already in light theme (no need to return to the homepage to change theme — the original feature gap this session closed).
**Automation Hint:** Playwright — toggle on page A, navigate, assert root class/`localStorage` reflect light theme on page B without any further interaction.
**Source:** Part249

---

## Process / meta test cases (cross-cutting this range)

### TC-P10-092
**Category:** Architecture
**Test Name:** A sweep's own stated scope is auditable against what it actually covers
**Steps:**
1. Review the instructions given to each of the 5 parallel theme-sweep agents.
2. Cross-check against `src/components/pipeline/` and dropzone-hover treatment.
**Expected Result:** Confirms the documented root-cause pattern: gaps traced to scope, not execution — useful as a checklist item for any future multi-agent sweep (explicitly list "hover parity," "Tailwind opacity-slash," and "every component folder" as required scope items).
**Automation Hint:** Manual process checklist, not automatable; track as a review item in future sweep planning.
**Source:** Part249 (documented as a standing process note)

### TC-P10-093
**Category:** Bug-Regression
**Test Name:** Billed-API self-verification does not batch multiple live paid calls without consent
**Steps:**
1. Review any test/verification pass touching a paid API (e.g. Gemini image-gen, HF Space GPU calls).
**Expected Result:** Live calls are made one at a time with explicit go-ahead, or mocked by default — not batched for convenience.
**Automation Hint:** Process/code-review checklist; verify test suites default to mocks for paid endpoints.
**Source:** feedback_billed_api_testing (referenced across Parts 201-249 work)

### TC-P10-094
**Category:** Bug-Regression (Fixed)
**Test Name:** Citation visual-action dropdown resets on document switch, not carried over stale
**Steps:**
1. Upload two standalone images (e.g. a face photo and an unrelated object photo) as separate documents in one session.
2. On document A's citation, select a detection action from the dropdown (e.g. "Detect faces").
3. Switch the active document to B via the Session sources list; select a DIFFERENT action there (e.g. "Detect objects").
4. Switch back to document A.
**Expected Result:** Document A's dropdown shows its own last selection ("Detect faces"), not B's ("Detect objects"); the rendered detection overlay matches.
**Automation Hint:** Playwright — select_option + click session-source rows, assert combobox selected value and overlay label text per document.
**Source:** EC-001, this conversation (2026-08-23 noted / 2026-08-24 confirmed+fixed). Root cause: `visualAction` and sibling UI state in `CitationThumbnailPanel.tsx` were plain `useState` with no reset on citation change. Fixed via `useCitationVisualState.ts`, keyed on `editKey` (source:page). Commit `9dd24be`, verified live post-deploy.

### TC-P10-095
**Category:** E2E / Regression
**Test Name:** Removing the active document falls back cleanly, no stale Evidence panel
**Steps:**
1. Upload two documents; make one the active citation in the Evidence panel.
2. Click the "×" on that same (active) document's Session sources row.
**Expected Result:** Evidence panel falls back to its empty state ("Click a citation to see its page") without crashing or showing the removed document's stale image/dropdown; the remaining document stays intact and usable.
**Automation Hint:** Playwright — remove active doc via its "×", assert Evidence panel's empty-state text and that the other doc's source row/content still renders.
**Source:** EC-002, this conversation (2026-08-23 noted / 2026-08-24 verified, no bug found).

### TC-P10-096 (behavior confirmation, not a bug)
**Category:** UX/Product decision
**Test Name:** Switching documents resets the viewed page to page 1
**Steps:**
1. Upload a multi-page PDF; navigate to page 2 via the Pages thumbnails.
2. Upload a second document, or switch to it via Session sources.
**Expected Result (current behavior, confirmed live):** Switching away and back resets the Evidence view to page 1 of whichever document is now active — the last-viewed page within a document is not remembered. Flagged as a product decision to revisit (should page be remembered per document?), not filed as a bug.
**Automation Hint:** Playwright — navigate to page 2, switch documents, switch back, assert which page renders.
**Source:** EC-003, this conversation (2026-08-23 noted / 2026-08-24 confirmed as current behavior).

### TC-P10-097 (open)
**Category:** Bug-Regression (unverified)
**Test Name:** AI Sharpen result persists across a document switch-away-and-back
**Steps:**
1. On an image citation, click "Sharpen image (AI)" and let it complete.
2. Switch to a different document, then switch back.
**Expected Result:** The sharpened result (and "View original" toggle) is still available, not lost.
**Automation Hint:** Playwright — sharpen, switch docs twice, assert sharpened-image state/toggle still present.
**Source:** EC-004b, this conversation (2026-08-24). Attempt blocked live by a transient 502 on `/rag/mm-deblur`, confirmed NOT a real outage via direct curl immediately after (endpoint returned normal 422). Left open, to retry.

### TC-P10-098 (open)
**Category:** E2E (unverified — needs suitable test content)
**Test Name:** Contradiction-check citations remain correct after a manual document switch
**Steps:**
1. Upload two documents with genuinely overlapping, conflicting claims (e.g. two versions of a spec/invoice with different numbers for the same field).
2. Click "Check documents for contradictions"; click into a resulting citation.
3. Manually switch the active document via Session sources, then click the contradiction citation again.
**Expected Result:** The citation still jumps to the correct page/document, not a stale or mismatched one.
**Automation Hint:** Playwright — needs a two-document fixture with real overlapping/contradicting text; two unrelated photos (tried 2026-08-24) produce "0 overlapping passages checked" and can't exercise this path.
**Source:** EC-005, this conversation (2026-08-23 noted / 2026-08-24 attempted, inconclusive — needs a better fixture).

### TC-P10-099 (open)
**Category:** E2E (unverified — needs test asset)
**Test Name:** Video timestamp-based citation jump (MMRAG-09) combined with document switching
**Steps:**
1. Upload a video document; ask a question that cites a specific timestamp/frame.
2. Click the citation to jump the player to that timestamp.
3. Switch to a different document and back; click the same video citation again.
**Expected Result:** The player still seeks to the correct timestamp after the switch.
**Automation Hint:** Playwright — needs a real video fixture with multiple distinct scenes/timestamps; not attempted this session (no video asset prepared).
**Source:** EC-006, this conversation (2026-08-23 noted, not yet attempted).

### TC-P10-100 (Fixed)
**Category:** Bug (captioning hallucination)
**Test Name:** Vision captioner invents collage/multi-section structure on a single plain photo
**Steps:**
1. Upload a single, plain portrait photo (no collage, no multiple crops) as a standalone image document.
2. Read its auto-generated caption (shown in the "Extracted from {file}" panel and as a floating description).
**Expected Result:** Caption describes the actual single image, not an invented multi-panel structure.
**Root cause (confirmed via a temporary diagnostic log, since removed):** Groq's Qwen vision model (`qwen/qwen3.6-27b`, first in the `_vision_cascade_raw` cascade in `_vision.py`) can complete its `<think>` block coherently but reason its way to a confidently wrong conclusion — inventing a 2×2/4-panel collage on one ordinary headshot. Confirmed live: the same ingest run showed Groq producing "The image is a collage of four cropped sections of a person's face..." while Mistral, called moments later on the identical image, correctly described it as one plain photo. Not a parsing bug — an unterminated `<think>` leak was already handled correctly by existing `strip_thinking()`; this is the model finishing its reasoning and still being wrong.
**Fix:** `looks_like_fabricated_collage()` added to `mm_caption.py`, cross-checked in `mm_image.py` against object-detection's independently computed bbox sizes (a real N-panel collage tiles the frame, so no single detection would span most of it) — retries once via the terser prompt on contradiction. Commit `9814f79`.
**Automation Hint:** Ingest a known single-subject photo via the real API 5+ times (the hallucination is non-deterministic), assert no returned caption matches collage/composite + crop/section/panel language.
**Source:** EC-007, this conversation (2026-08-24). See TC-P10-101 for the live-verification follow-up that widened the detection regex.

### TC-P10-101 (Fixed)
**Category:** Bug-Regression (Fixed, found during verification of TC-P10-100)
**Test Name:** Collage-hallucination regex too narrow, missed a wording variant live
**Steps:**
1. After TC-P10-100's fix (commit `9814f79`) deployed, re-ingest the same test photo 5 times via the real API.
**Expected Result (what actually happened first):** All 5/5 attempts still showed the hallucination reaching the final caption — the deployed regex required "cropped" within a bounded window of a section/panel/view word, but the live response used a different, split-sentence wording ("...vertical composite featuring close-up **crops** of a young man's face... The **top section** displays...") that never matched.
**Fix:** Widened `looks_like_fabricated_collage()` to two independent word-groups anywhere in the text — (collage|composite) AND (crops?|cropped|cropping|sections?|panels?|quadrants?|tiles?|views?) — relying on the object-detection contradiction check in `mm_image.py` as the real false-positive guard instead of word proximity. Commit `a14d356`.
**Automation Hint:** Regression-test the regex directly against both observed wordings plus a legitimate collage caption (e.g. "a real collage of four photos from a birthday party" — should NOT trigger, no crop-word present).
**Expected Result (after fix):** Re-verified live — 5/5 fresh ingests of the same photo returned the correct plain caption, 0 hallucinations reaching the final chunk text.
**Source:** EC-007 follow-up, this conversation (2026-08-24) — a real example of "verify live before calling it done" catching a fix that looked complete but wasn't.

---

## Pending Test Cases (from this range, unbuilt or explicitly flagged)

| Item | Note | Source |
|------|------|--------|
| FSPanels/*.tsx (4 files) still use dead `RepulsionCard` | Flagged, not fixed | Part249 |
| Face Cloak: targeted (real Fawkes) mode | Needs a bundled decoy-identity dataset, not sourced | Part246 |
| Face Cloak: multi-face support | Only highest-confidence face is cloaked today | Part246 |
| Face Cloak: no re-id benchmark dataset | Heuristic thresholds unvalidated against real match/no-match pairs | Part246 |
| Deepfake / steganography detection | Offered as alternatives to adversarial training, not chosen | Part247 |
| Video-call keystroke inference, CAPTCHA-solving research | Broader security backlog, unbuilt | Part247 |
| Universal/cross-image adversarial patch | Higher-effort variant beyond the single-image patch shipped | Part246 |
| True label-only black-box attack (beyond score-based SimBA) | Higher-effort variant, not built | Part246 |
| Sentry / global error-tracking | Recommended during this window's logging audit, not requested to build | This conversation, Thread B |

## Coverage Note

Parts 201–243 test cases above are derived from the aggregated technical-concept record for
this range (provider cascades, MMRAG architecture, MMRAG-01→28 backlog items, CV forensics,
Inpainting, Sharpen/Deblur) rather than a fresh line-by-line re-read of all 43 individual
session logs in this pass — that full read was completed earlier in this same work session.
Parts 244–249 test cases are derived from a direct, complete re-read of their session logs in
this pass, so they carry more granular per-bug/per-verification-step coverage. The Parts
158–172 gap (no session logs exist) remains open, unrelated to this file.
