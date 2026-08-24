# Session 2026-07-18 — Document Intelligence: Agentic Self-Correction + bbox Fix (Part 199)

## Summary

Continuation from Part 198. Implemented the agentic self-correction loop for Document Intelligence, then fixed bounding box search across three iterations, verified end-to-end with Playwright.

---

## 1. Agentic Self-Correction Loop

### What was built

New file `services/ml-api/routers/document/_validate.py` (201 lines) — three-pass validation after field extraction:

**Pass 1 — Rule-based (free, instant)**
- Date fields: regex check against common date formats
- Email fields: `@` format check
- Phone fields: minimum 7 digits
- Low confidence: fields below 55% flagged as `low_confidence`

**Pass 2 — Invoice arithmetic (deterministic, no LLM)**
- `total ≈ subtotal + tax` check
- Flags both fields with the exact discrepancy note

**Pass 3 — LLM consistency (Groq llama-3.3-70b-versatile)**
- Sends all extracted fields back to LLM
- Asks for cross-field consistency issues, implausible values, swapped fields
- Returns `{status, note, corrected_value}` per flagged field
- Corrected values applied in-place before streaming to frontend

Each field gets a `validation` key: `{status: "ok"|"corrected"|"flagged"|"low_confidence", note: "..."}`.

### Router change

Step 4 in `router.py` now runs `validate_and_correct()` in the existing `ThreadPoolExecutor` before the bbox lookup. SSE label updates: "Checking field consistency" → "Locating fields in document".

### Frontend change

`DocFieldsPanel.tsx` — `ValidationBadge` component:
- Amber pill + triangle icon = **Flagged**
- Indigo pill + star icon = **Corrected**
- Red pill + circle icon = **Low confidence**
- Hover tooltip shows the `note` explaining the issue
- Footer: **"N need review"** in amber when any non-OK fields exist

`_types.ts` — added `FieldValidation` interface.

### Playwright verification

Uploaded `test_invoice.pdf` (subtotal $100 + tax $10, total $150 — deliberate mismatch):
- Arithmetic check caught it: SUBTOTAL + TOTAL AMOUNT both showed **Flagged** badge
- Footer: **"2 need review"** in amber
- All 4 steps completed in stepper

| Commit | Repo | Description |
|--------|------|-------------|
| `fc76eec` | ML-Unified | feat(document): agentic self-correction loop |
| `8c8f418` | ml-portfolio | feat(document): validation badges on extracted fields |

---

## 2. Bounding Box Search — Substring Fallback (3 iterations)

### Problem

`search_bbox_in_doc` used verbatim text search (`page.search_for(val[:80])`). Fields where the LLM reformatted or combined values got no "Located" badge:
- **Bank Info**: LLM returned `"Test Bank, Account: 12345678"` → PDF has `"Bank: Test Bank | Account: 12345678"`
- **Invoice Items**: LLM returned `"Widget A: 2 x $25.00 = $50.00, Widget B: ..."` → PDF has tabular columns

### Fix — 3 tiers of candidates

**Tier 1**: full value (capped at 80 chars) — original behaviour

**Tier 2** (`481230f`): split on delimiters (`[,|;\n]+`), try each chunk longest-first
- Solved Bank Info: `"Test Bank"` found after comma split

**Tier 3** (`37a2ae4`): strip punctuation from each chunk, try first 2-3 words
- Intended to solve Invoice Items: `"Widget A: $50.00"` → words → `"Widget A"`

**Bug in Tier 3** (`2751a3c`): filter `len(w) >= 2` dropped single-char tokens — `"A"` in `"Widget A"` was filtered out, generating `"Widget $50"` instead. Fixed by only filtering empty strings.

### Playwright verification results

| Run | Fields | Located | Notes |
|-----|--------|---------|-------|
| Before any fix | 11 | 7/11 | Bank Info, Invoice Details missing |
| After Tier 2 | 9 | 9/9 | LLM returned fewer fields that run |
| After Tier 3 (with explicit Invoice type) | 11 | 10/11 | Bank Info located, Invoice Items still missing |
| After single-char fix | 10 | 10/10 | All extracted fields located (LLM skipped Invoice Items this run) |

Invoice Items non-determinism is an LLM temperature issue (see pending below).

| Commit | Description |
|--------|-------------|
| `481230f` | fix(document): delimiter split fallback |
| `37a2ae4` | fix(document): word-level fallback (tier 3) |
| `2751a3c` | fix(document): keep single-char words in tier 3 |

---

## 3. Key Technical Decisions

- **Explicit Invoice type vs Auto-detect**: Auto-detect causes more LLM variation in which fields get returned. Explicitly selecting the document type locks the schema and reduces non-determinism.
- **Playwright JS eval**: Used `browser_evaluate` with `document.querySelectorAll` to get exact Located badge status per field — more reliable than screenshot parsing at small scale.
- **3-tier bbox search**: Full → delimiter-split → word n-grams. Ordered by specificity; returns on first match.

---

## 4. LLM Stack (Document Intelligence)

| Role | Provider | Model |
|------|----------|-------|
| Text extraction / classification / validation | Groq (primary) | `llama-3.3-70b-versatile` |
| Text fallback | Gemini | `gemini-2.0-flash` |
| Text fallback 2 | Cohere | `command-r-plus` |
| Visual extraction | Groq Vision (primary) | `llama-3.2-11b-vision-preview` |
| Visual fallback | Gemini Vision | `gemini-2.0-flash` |

All free-tier APIs.

---

## 5. Pending

- [ ] Add `temperature=0` to Groq text extraction call (reduce field non-determinism)
- [ ] Career timeline still unverified — left it, too much time already spent
- [ ] LLM Fine-tuning Pipeline — left it, no GPU/subscription available
- [ ] Time Series Forecasting — next candidate
- [ ] Multimodal RAG — next candidate
