# Session 2026-07-18 — Document Intelligence Fixes + Analytics User Guide (Part 198)

## Summary

Continuation from Part 197. Fixed CI test failures, document intelligence visual extraction failures (Gemini rate limits → switched to Groq Vision), added export (JSON/CSV/Excel) and table extraction to Document Intelligence, updated analytics user guide.

---

## 1. CI Test Failures — xgboost + sklearn Version

### Problem
`test_train_classification` and `test_train_regression` failed with `No module named 'xgboost'`.
Then `model-quality` job failed with `No module named '_loss'` for titanic model.

### Root Cause
- `xgboost`, `scikit-learn`, `pandas`, `numpy`, etc. were only in `requirements-base.txt` (Docker layer) but not in `requirements.txt` (what CI installs)
- First fix used `>=` version pins → CI installed `scikit-learn==1.9.0` while models were pickled with `1.8.0` → `_loss` module missing in 1.9.0

### Fix
Added all ML packages to `requirements.txt` with exact pinned versions matching `requirements-base.txt`:
```
scikit-learn==1.8.0
pandas==2.2.2
numpy==1.26.4
joblib==1.5.3
xgboost==2.1.1
lightgbm==4.6.0
catboost==1.2.10
shap==0.47.2
```

| Commit | Description |
|--------|-------------|
| `82ce629` | fix(ci): add ML packages to requirements.txt so pytest train tests find xgboost |
| `b2f2d7b` | fix(ci): pin ML package versions to match pickled models (sklearn==1.8.0) |

---

## 2. Document Intelligence — Visual Extraction Failures

### Problem
Career timeline and soft skills never extracted despite multiple previous fix attempts.

### Root Causes Found (in order)

**Bug 1 — "null" string blocking visual merge**
Text LLM returned `"career_timeline": "null"` (string). `_normalize_fields` let it through (`value is None` check doesn't catch strings). In `existing_all`, career_timeline existed with value `"null"` (truthy). Visual extraction merge check `not f.get("value")` → `not "null"` → False. Real visual data was silently discarded.

Fix: Added `_NULL_VALUES` set in `_normalize_fields` filtering `"null"`, `"none"`, `"n/a"`, etc.

**Bug 2 — Visual extraction not targeting missing fields**
Gemini/Groq Vision was told "here's what we already found" but not "here's what we still need". Changed `_visual_prompt` to receive `missing_names` and explicitly say "PRIORITY: find these MISSING fields".

**Bug 3 — Blocking the async event loop**
`extract_visual_sections` (sync, ~90s per page) called directly in async FastAPI generator. Moved to `ThreadPoolExecutor` via `loop.run_in_executor()`.

**Bug 4 — Gemini 429 rate limiting**
All 3 Gemini Vision calls fired within 300ms. Free tier = 15 RPM. Added retry with backoff (5s/10s/15s) and 4s delay between pages. Still failed — daily quota exhausted.

**Bug 5 — Gemini daily quota fully exhausted**
No amount of waiting helped. Every call returned 429. Root fix: **switched to Groq Vision** (`llama-3.2-11b-vision-preview`) as primary, Gemini as fallback.

### Files Changed
- `services/ml-api/routers/document/_llm.py` — `_NULL_VALUES`, `_visual_prompt` targeting, `_groq_vision_page()`, `_gemini_vision_page()`, updated `extract_visual_sections()`
- `services/ml-api/routers/document/router.py` — `run_in_executor`, pass `missing_names`

| Commit | Description |
|--------|-------------|
| `0c42025` | fix(document): target missing fields in Gemini Vision; filter null-string values; run in thread pool |
| `90fa110` | fix(document): retry Gemini Vision on 429; add 4s delay between pages (15 RPM limit) |
| `50e417c` | fix(document): switch visual extraction to Groq Vision; Gemini as fallback |

---

## 3. HF Space Build Error (exit code 128)

After uploading files directly to HF Space while also pushing via git, the Space got into a conflicted state and failed with exit code 128.

**Fix:** Used `api.restart_space()` via HF Python SDK. Space recovered to `RUNNING`.

---

## 4. Document Intelligence — Export Feature

### What was added
Replaced single "Export JSON" button with a dropdown (JSON / CSV / Excel):

- **JSON** — includes `document_type`, `exported_at`, `field_count`, per-field `label` + `confidence`
- **CSV** — Field Name, Label, Value, Confidence% columns; Excel-compatible
- **Excel** — SpreadsheetML XML format (`.xls`), no library dependency, Excel opens natively

File: `ml-portfolio/src/app/tools/document-intelligence/DocFieldsPanel.tsx`

| Commit | Repo | Description |
|--------|------|-------------|
| `594ceb3` | ml-portfolio | feat(document): export dropdown — JSON + CSV |
| `4310c6e` | ml-portfolio | feat(document): add Excel export — pure XML SpreadsheetML, no library needed |

---

## 5. Document Intelligence — Table Extraction

### What was added
Added `extract_tables_markdown()` to `_extract.py` using pymupdf's built-in `find_tables()`. Zero new dependencies.

- Extracts structured table data from digital PDFs
- Converts to markdown pipe-table format
- Appended to document text before LLM step as `## DOCUMENT TABLES`
- LLM text limit increased `10000 → 14000` chars

**Impact:** Invoices, bank statements, purchase orders now have clean line-item data instead of flattened text.

File: `services/ml-api/routers/document/_extract.py`, `router.py`, `_llm.py`

| Commit | Description |
|--------|-------------|
| `89b956b` | feat(document): dedicated table extraction step using pymupdf find_tables() |

---

## 6. Analytics User Guide — Updated

### Missing sections added
Four sections were absent from the user guide despite being live on the dashboard:

1. **HF Space Tools** — ML Unified API activity cards, page/copy/open sub-counts
2. **Portfolio Tools** — per-tool event cards for all portfolio tools (including Document Intelligence)
3. **Visitors by Device** — desktop/mobile/tablet donut chart
4. **AI Provider → By Model** — specific model name breakdown (llama-3.3-70b, gemini-2.0-flash, etc.)

Nav pills updated to include all new sections.

Files: `AnalyticsUserGuideSections.tsx`, `AnalyticsUserGuide.tsx`

| Commit | Repo | Description |
|--------|------|-------------|
| `10e495b` | ml-portfolio | docs(analytics): update user guide — add HF Tools, Portfolio Tools, By Device, AI Model sections |

---

## Key Lessons

1. **Gemini free tier has RPD (requests/day) limit** — not just RPM. When quota exhausted, retries don't help. Always have a fallback provider (Groq Vision).
2. **LLM "null" strings are truthy in Python** — `value is None` doesn't catch them. Always filter known null-equivalent strings.
3. **HF Space exit code 128** = git conflict between direct file uploads and git push. Fix: `api.restart_space()`.
4. **Excel export without xlsx library** — SpreadsheetML XML format works natively in Excel, zero dependencies.
5. **pymupdf `find_tables()`** — built into pymupdf ≥ 1.23.0, no extra dependencies, produces clean table data for LLM.

---

## Actionable Improvements, Ranked by Impact

**High Impact**
1. **Multi-model routing by document complexity** — simple docs → cheap model, complex → frontier. Cuts cost, improves accuracy.
2. **Table extraction as dedicated step** ✅ Done — pymupdf `find_tables()` before LLM.
3. **Confidence-based human review flag** — fields below 0.7 flagged as "needs review", separate export for low-confidence fields.

**Medium Impact**
4. **Reading order reconstruction** — multi-column PDFs extracted in wrong order by pymupdf4llm. Surya OCR or `pdfplumber` preserve column order.
5. **Automatic skew/orientation correction** — Pillow auto-rotate from EXIF or Tesseract OSD before extraction.
6. **Field-level grounding / citations** — show "found on page 2, paragraph 3" per field. Makes tool trustworthy for legal/medical.
7. **Agentic self-correction loop** — second LLM pass validates own output (invoice total = sum of line items?, valid date format?, valid email?).

**Low Effort, Good UX**
8. **Export to JSON/CSV/Excel** ✅ Done.
9. **Side-by-side diff view** — highlight manually edited fields vs original extraction.
10. **Document history** — remember last 5 uploads in localStorage.

---

## Pending

- [ ] Agentic self-correction loop for Document Intelligence (next up)
- [ ] Verify career timeline extraction after Groq Vision switch
- [ ] LLM Fine-tuning Pipeline
- [ ] Time Series Forecasting
- [ ] Multimodal RAG
