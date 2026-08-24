# Session 2026-07-19/20 — DocIntel Improvements, IDP Features, HF Outage, Chatbot Grounding (Part 202)

Continuation after Part 201 (Mistral integration + Codestral in ml-sql). Covers the
Document Intelligence improvement program, three IDP features, the HF Space outage,
and per-tool chatbot grounding.

---

## 1. Five DocIntel improvements (all verified)

| # | Improvement | Commits |
|---|-------------|---------|
| 1 | OCR bounding boxes for scanned/image docs — Mistral OCR blocks (pixel bboxes + page dims) mapped to fields via `locate_fields_from_ocr` | b919ec0 |
| 2 | Multi-page bbox search — all pages, candidate-priority outer loop, `(bbox, page)` return; frontend per-page SVG overlays (viewBox 0-100, non-scaling-stroke) | b919ec0 + portfolio 23e2674 |
| 3 | Provider attribution — `last_provider` in text+vision cascades, "via <Provider>" chip; fixed overwrite by visual-sections pass (capture right after main extraction) | ffe7b03, c5173bc, portfolio e599c7a |
| 4 | Hash result cache — sha256(file)+doc_type+provider(+custom_fields), 10 entries, 24h TTL (researched exact-match convention), "(cached)" chip; only successful runs cached; fixed done-event overwriting the suffix | 3acba39, abcf1d2, 8bd88fc |
| 5 | DOCX support — python-docx text+tables; detection by ext or zip signature | 440321b + portfolio 9283678 |

Validator polish (696f5c2): bank statement closing=opening+credits−debits; line-items-sum
vs subtotal for invoice/receipt/PO; date-order rules (invoice/contract/id_card/PO,
ambiguous dd/mm skipped); 8 unit tests + broken-invoice E2E caught every planted error.

## 2. DOCX deep fixes (user's designed CG resume)

- Resume had 0 body paragraphs — everything in tables + 24 text boxes. python-docx
  paragraphs API misses text boxes/headers/footers → email/phone/linkedin missing.
- Fix 1 (0702240): `_docx_extra_text` — stdlib zip+ElementTree walk of all w:p in
  document/header/footer parts, deduped against body.
- Still failed → root cause 2: merged table cells repeat content per spanned col/row,
  inflating 6k chars to 19k → extras section pushed past the 14k prompt cap.
- Fix 2 (31ef2c6): dedupe merged cells by tc element id + extras FIRST. 19,199→6,189
  chars, email at char 54. Result: 8 → 22 fields.
- Preview panel message replaced with success-styled card (portfolio f21dc8f).

## 3. Experience calculation (user correction)

- "19 years" was last-minus-first over gap years (2010-12, 2017-24). Prompt rule added
  (4e35b49) — model then listed right periods but summed wrong (17).
- Deterministic fix (494ffc4): `_recompute_experience` parses month-year ranges per
  role, sums in code, corrects the field ("~10-11 years", Corrected badge).
  Lesson: compute in code what LLMs compute badly.

## 4. Three IDP features ("do as you mentioned")

1. **Chat with the document** — POST /document/chat (doc_text + fields + history via
   cascade); `doc_text` added to done event; DocChatPanel with suggestion chips.
   Answers grounded, refuses not-in-doc, prose-coerced (452752f, a135a76, 0fb7ff1).
2. **Custom fields** — `custom_fields` form param merged into schema + cache key;
   input on upload screen. Verified: "Currency Used"→USD.
3. **HITL editing** — pencil icon on field cards, inline textarea, Corrected/
   human-verified badge, confidence→100%; exports carry edits (portfolio d5c9048).
   User verified all three in UI (experience ~12→~11 edit).

Fake Excel export removed (portfolio 0febe77) — SpreadsheetML-as-.xls only opens in
desktop MS Excel; CSV covers spreadsheets everywhere.

## 5. HF Space outage (major incident)

- ~10 rapid deploys → HF edge routing broke: proxy 500 HTML (Content-Length 3044)
  served while app healthy (internal health 200s, analyze 200s in container logs);
  failed requests never reached the app. Even huggingface.co's own Space page 500'd.
- Factory reboot (API + user-initiated) eventually recovered; flapping persisted for
  hours. Diagnosis method: app logs via huggingface.co/api/spaces/{id}/logs/run.
- **CLAUDE.md rule 5 added**: batch deploys, verify new code actually serving (not
  stage=RUNNING), two failures = stop and root-cause with direct evidence.
- User anger justified: repeated deploy-test collisions after the pattern was known.

## 6. Per-tool chatbot grounding (user guides)

- Floating ToolsAIChat (RAG) was answering AutoML data-science questions on every page.
- `ToolChatContext` extended with `guide` + `suggestions`; `buildToolContext` injects
  strict scope rules (tool + website only, polite refusal) + site summary + guide as
  source of truth. Backend /rag/query already injects tool_context verbatim; cache is
  ctx-hashed → frontend-only change.
- Guides: DI (written fresh — userGuide.ts, also rendered in new DocUserGuideModal via
  "User Guide" header button), Text-to-SQL (distilled from existing UserGuideModal),
  Real-Time Analytics (distilled from AnalyticsUserGuideSections).
- Guide mode hides RAG controls (upload, Deep/Std, Web, Jina/Std toggles, Jina banner)
  — they confused users and Web could break scoping.
- Verified live: off-topic log1p question refused; Flagged-badge question answered
  from guide; per-page chips on all three pages.
- Commits: portfolio 0732fac, 3a676f4, e352903.

## 7. Assistant header polish

- "AI Assistant · <Tool>" clipped the gear on long names. Iterations: ellipsis+smaller
  font (e352903) → prefix removed, tool-name only (eff516f) → 0.55rem still truncated
  "FEATURE ENGINEERING" on button-heavy RAG pages → **two-row header** on non-guide
  pages (title full-width line, buttons below) (b000ef0). Verified: full name + all
  buttons on Feature Engineering.

## 8. Explained (no action)

- User-guide UI differences: Text-to-SQL/Analytics = hand-built React modals (icons,
  key caps, anchor sections); DI = markdown-rendered modal sharing the chatbot's
  source text (single source of truth, near-zero maintenance).
- Home vs Back navigation: pipeline-era tools (sticky navbar, Step badge, "Home") vs
  standalone-era tools ("Back" chevron) — both go to /#capabilities; unification
  options offered (label rename cheap; shared ToolPageHeader proper).
- Groq vision 404 noted in logs (llama-4-scout name may have changed) — cascade falls
  through to Mistral vision; verify against Groq's live model list next backend pass.

## 9. Key lessons reinforced

- Verify with real calls before integrating/recommending (Mistral tested before wiring;
  contrast with Cerebras incident).
- Deterministic computation over LLM arithmetic (experience, invoice totals).
- Batch deploys; a readiness check that gives false positives must be fixed, not
  worked around (CLAUDE.md rule 5).
- HF proxy 500 HTML ≠ app error — check container logs to see if requests arrived.
