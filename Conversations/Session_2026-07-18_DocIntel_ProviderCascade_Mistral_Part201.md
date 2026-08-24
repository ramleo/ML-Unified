# Session 2026-07-18 — DocIntel: Free API Providers, Mistral Integration, OCR-First Pipeline (Part 201)

Continuation of Part 200 (bbox fixes + Groq quota debug). Covers everything from "search online and list free api key providers" to end of session.

---

## 1. Free LLM API Provider Research

Web search for free LLM API providers (2026). Shortlist relevant to the document cascade:

| Provider | Reported free limit | Model |
|----------|--------------------|-------|
| Groq | 100K TPD, 30 RPM | llama-3.3-70b (already wired) |
| Google Gemini | 1,500 RPD | gemini-2.0-flash (already wired) |
| Cerebras | 1M tokens/day (reported) | llama-3.3-70b (reported) |
| SambaNova | 200K TPD, 20 RPD | llama-3.3-70b |
| NVIDIA NIM | ~1,000 credits | 100+ models |
| OpenRouter | 35+ free models | various |
| GitHub Models | free w/ GitHub token | GPT-4o, Llama, Phi |
| Mistral | ~1B tokens/month "Experiment" tier | mistral catalog |
| Cohere | 1,000 calls/month trial | command-r-plus (already wired) |

## 2. Cerebras Attempt — FAILED (402)

- User created Cerebras account + key, added `CEREBRAS_API_KEY` to HF Space secrets (name verified correct in screenshot)
- Code added: `_cerebras()` provider in `_llm.py` (commit d812b69)
- **Direct key test: 402 "Payment required" on every model** — free tier requires payment method; user declined for now
- Also: blog-reported model `llama-3.3-70b` doesn't exist in Cerebras catalog anymore — actual catalog: `zai-glm-4.7`, `gpt-oss-120b`, `gemma-4-31b`. Code updated to `gpt-oss-120b` (commit 233704c) so it works if quota ever activates
- **Lesson saved to memory** (`feedback_verify_before_recommending.md`): never present web-search claims about free tiers/models as fact — test with a real key first. Always hit provider's /models endpoint rather than trusting docs/blogs

## 3. Interim fixes (same session, before Mistral)

- `router.py`: emit `{"warning": ...}` SSE event when extraction returns 0 fields (commit 5c359af); frontend shows amber warning banner (ml-portfolio f9c5f45)
- `_llm.py`: provider errors escalated logger.warning → logger.error
- Keyword fallback classifier `_keyword_classify()` (commit d6b6861) — when all LLM providers fail, classify via keyword matching instead of defaulting to "invoice" (this was why the resume misclassified as Invoice 70% → correct schema now chosen even in outage)
- Groq vision model `llama-3.2-11b-vision-preview` was decommissioned → replaced with `meta-llama/llama-4-scout-17b-16e-instruct` (commit 6d4d954); image path got Groq primary + Gemini fallback
- Frontend: "network error" → human-readable "Connection lost — server may be restarting" (ml-portfolio d7f0d8c)
- Temporary `/document/test-providers` debug endpoint used to expose real provider errors, then removed

## 4. Provider status truth table (verified by direct API calls)

| Provider | Status | Evidence |
|----------|--------|----------|
| Groq | Works; daily 100K TPD resets midnight UTC | Extracted fields when quota fresh; 429 when exhausted |
| Gemini | Key VALID, quota exhausted | 429 "exceeded your current quota" |
| Cohere | Key VALID, trial 1000 calls/month exhausted | 429 trial-key message |
| Cerebras | Key valid but 402 payment required | tested all 3 catalog models |
| Mistral | **WORKING** | see below |

## 5. Mistral Integration (the win)

User created free Mistral key (console.mistral.ai, Experiment tier, no card). **Verified BEFORE integration** per new rule:

- `mistral-small/medium/large-latest` text+JSON: all 200
- `mistral-medium-latest` VISION on real resume image: 200, name+email EXACT
- `mistral-large-latest` VISION: 200 but hallucinated email typo ("ramleox84") → medium chosen for vision
- `mistral-ocr-latest` OCR API: 200 on free key (docs claim Premier/paid) — returns clean per-page markdown

Docs review (docs.mistral.ai): Medium 3.5 = frontier multimodal; Large 3 = multimodal; OCR 4 = bounding boxes + structural labels.

### User decisions
1. Keep large for TEXT despite vision typo (typo was a pixel-reading failure; text path never reads pixels) — but medium runs FIRST, large only if medium returns empty/invalid JSON
2. Text cascade order: **Groq → Mistral (medium→large) → Gemini → Cohere → Cerebras** (Cerebras last, it's 402-dead)
3. Vision: implement BOTH OCR-first path AND vision fallback
4. Models must suit all 9 doc types (Invoice, Receipt, Contract, Resume/CV, Medical Report, Bank Statement, ID Card, Purchase Order, Auto-detect)

## 6. Final Architecture (commit 3e754ff)

`_llm.py` was 390 lines (>350 limit) → modularized: vision/OCR functions moved to new `_vision.py`.

| File | Lines | Contents |
|------|-------|----------|
| `_llm.py` | 243 | text providers, cascade, classify (LLM + keyword fallback), extract_fields_from_text, _normalize_fields |
| `_vision.py` | 183 | mistral_ocr_pages, vision cascade (_groq/_mistral/_gemini_vision_raw), extract_visual_sections, extract_fields_from_image |
| `router.py` | 221 | OCR-first flow + vision fallback wiring |

### Pipeline flow
- **Digital PDF:** PyMuPDF text → cascade Groq → Mistral medium → Mistral large → Gemini → Cohere → Cerebras
- **Scanned/image:** `mistral-ocr-latest` → markdown → same text cascade (classify now reads REAL text — no more blind "invoice" 0.4 default) → if 0 fields: one-shot vision fallback Groq scout → Mistral medium vision → Gemini Vision
- `_mistral()` text: medium first; large retry on empty/invalid JSON

### HF Space secrets
`MISTRAL_API_KEY` added by user. All uploads to `wram1708/ml-unified` via api.upload_file.

## 7. Playwright Verification — PASS

Resume upload with Groq exhausted (perfect stress test — Mistral carried everything):

| Check | Before | After |
|-------|--------|-------|
| Classification | "Invoice" 70% | **"Resume / CV"** ✅ |
| Fields | 6 | **17, all high confidence** |
| Contact fields | missing | Full Name, Email, Phone, Location, LinkedIn, GitHub ✅ |
| Career Timeline | missing | company/title/dates structure ✅ |
| Soft Skills (pie chart) | missing | all 6 values ✅ |
| Languages, DockerHub, Projects | missing | present with Located badges ✅ |

3 fields flagged for review = self-correction validator working as designed.

## 8. Commits (ML-Unified)

| Commit | Change |
|--------|--------|
| 5c359af | warning SSE event + logger.error escalation |
| d6b6861 | keyword fallback classifier; debug endpoint removed |
| 6d4d954 | Groq llama-4-scout vision; image path Groq primary |
| d812b69 | Cerebras provider added |
| 233704c | Cerebras model → gpt-oss-120b |
| 97171a0 | Mistral (large) added to cascade |
| 3e754ff | OCR-first pipeline, _vision.py split, medium→large, final cascade order |

ml-portfolio: f9c5f45 (warning banner), d7f0d8c (network error message).

## 9. Memory updates

- `feedback_verify_before_recommending.md` — NEW: test provider keys with raw call before integrating; label web claims unverified
- `project_realworld_usecases.md` — Document Intelligence marked ✅ Core done (2026-07-18) with full provider status; Gemini/Cohere keys noted VALID but quota-exhausted (recover on billing-cycle reset)

## 10. User corrections during session

- Called out Cerebras recommendation failure: "initially u said cerebras, now you say cerebras free needs activation" → led to the verify-before-recommending rule
- Clarified Gemini/Cohere "keys are correct" → memory wording fixed to "VALID but quota-exhausted" (not broken keys)
- Model switched mid-session: Sonnet 4.6 → Claude Fable 5 (`/model claude-fable-5[1m]`)
