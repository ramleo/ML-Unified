# Session 2026-07-17 — Document Intelligence Debugging & Fixes (Part 197)

## Summary

Continuation from Part 196. HF Space was stuck in build queue, factory reset required. Document Intelligence backend came live and was tested end-to-end with a real resume PDF. Multiple extraction and UI bugs were found and fixed iteratively.

---

## 1. HF Space Build — Stuck Queue

### Problem
Build was queued at `05:50:58` for 40+ minutes with zero log output. Previous session ended while build was in `RUNNING_BUILDING`. After the last docker layer-split commit (`a8f1413`), build was triggered but never assigned a runner.

### Fix
User performed factory reset from HF Space settings page. Build restarted, logs appeared, `pip install` ran ~15 min and completed. Space flipped to `RUNNING`.

### Lesson Recorded
If build shows "Build Queued" with zero log output for >10 minutes → it's stuck. Suggest factory reset immediately, do not say "just wait".

### Commits involved
| Commit | Description |
|--------|-------------|
| `a8f1413` | fix(docker): split requirements into base + app layers for faster rebuilds |
| `ba1632e` | feat(document-intelligence): backend — 8 doc types, SSE streaming |

---

## 2. Resume Extraction — Missing Fields

### Problem
Uploading resume PDF only extracted: name, email, phone, location, linkedin, github, top_skills, education_summary. Missing: projects, career timeline, soft skills, work experience, certifications, achievements.

### Root Causes
1. **Resume schema too narrow** — only 9 predefined fields, no projects/career_timeline/soft_skills
2. **Text extraction limit** — `text[:4000]` only covered page 1 of a multi-page PDF
3. **LLM prompt not dynamic** — only extracted predefined fields, didn't pick up arbitrary section headers
4. **Visual content not extracted** — career timeline and soft skills were images/graphics embedded in the PDF; text extraction returns empty for these

### Fixes Applied

**Schema expansion** (`_schema.py`):
- Added: `work_experience`, `projects`, `certifications`, `achievements`, `soft_skills`, `career_timeline`, `linkedin`, `github`, `technical_skills`, `languages`

**Dynamic section extraction** (`_llm.py`):
- Updated prompt to extract predefined fields first, then append any additional sections/headers found in the document
- `_normalize_fields` now accepts extra fields not in schema — uses LLM-provided label as display label

**Text limit increase** (`_llm.py`):
- `text[:4000]` → `text[:10000]` — covers full multi-page resume content

**Visual extraction via Gemini Vision** (`_llm.py`, `router.py`):
- Added `extract_visual_sections()` — sends rendered page images to Gemini Vision
- Called after text extraction for digital PDFs; merges results
- Initially sent all pages in one call → was timing out silently
- Fixed to send **one page per Gemini call**, loop through up to 4 pages, merge results

**Page render coverage** (`_extract.py`):
- `max_pages=2` → `max_pages=5` — renders all pages
- Scale `1.5x` → `1.2x` — smaller images, faster Gemini processing

| Commit | Description |
|--------|-------------|
| `017a93b` | fix(document): expand resume schema — add work_experience, projects, certifications |
| `80b8317` | fix(document): generalize extraction — LLM captures any section header as dynamic field |
| `4c9fac5` | feat(document): supplement text extraction with Gemini Vision for embedded images/timelines |
| `286a62a` | fix(document): send all page images to Gemini Vision, render up to 5 pages |
| `1da36ca` | fix(document): add soft_skills+career_timeline to schema; fix Gemini visual prompt |
| `9f9b611` | fix(document): text extraction limit 4000→10000; done event sends all page_images array |
| `0847479` | fix(document): [WRONG] used Anthropic as primary — reverted next commit |
| `1906f10` | fix(document): revert to Gemini-only; one page per call to avoid size timeout |

---

## 3. Wrong Vision Provider Assumption

### Problem
Career timeline was still not extracted. Assumed `ANTHROPIC_API_KEY` was set because `anthropic` package is in requirements. Switched Anthropic to primary vision provider, Gemini to fallback.

### Reality
HF Space secrets screenshot showed:
- `GEMINI_API_KEY` ✓ (set 1 month ago)
- `GROQ_API_KEY` ✓
- `COHERE_API_KEY` ✓
- `TAVILY_API_KEY` ✓
- `HF_TOKEN` ✓
- NO `ANTHROPIC_API_KEY`

Reverted immediately. `GEMINI_API_KEY` is the correct vision provider.

**Real root cause of career timeline failure:** All 5 page images were sent in a single Gemini request (~5-10MB total). Gemini was timing out silently (exception caught, `[]` returned). Fix: one page per call.

---

## 4. Document Preview — Only Page 1 Shown

### Problem
`DocViewerPanel` only showed first page (`page_images[0]`). Career timeline on page 3/4 not visible in preview.

### Fix
- **Backend** (`router.py`): changed done event from `page_image: page_images[0]` to `page_images: page_images` (full array)
- **Frontend** (`_types.ts`, `DocIntelRunner.tsx`, `DocViewerPanel.tsx`): updated to accept `pageImages: string[]`, render all pages stacked vertically with page number badges, scrollable up to 600px

| Commit | Repo | Description |
|--------|------|-------------|
| `6fe568d` | ml-portfolio | fix(document): show all pages in preview; confidence shows %; send page_images array |

---

## 5. SSE Chunking Bug — Preview Never Appeared

### Problem
Document preview panel always showed "Processing document…" even after extraction completed. `pageImage` state never got set.

### Root Cause
The `done` SSE event contains base64 image(s) — potentially 500KB–5MB. Browser's `ReadableStream` splits large events across multiple `read()` calls. Frontend was:
```tsx
const lines = decoder.decode(value).split("\n").filter(Boolean);
// → JSON.parse fails on incomplete line, caught silently, pageImage stays null
```

### Fix (`DocIntelRunner.tsx`)
```tsx
let buf = "";
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buf += decoder.decode(value, { stream: true });
  const lines = buf.split("\n");
  buf = lines.pop() ?? ""; // hold incomplete last line
  for (const line of lines) { ... }
}
```

| Commit | Repo | Description |
|--------|------|-------------|
| `2c9d670` | ml-portfolio | fix(document): buffer SSE chunks — base64 page_image was split across reads |

---

## 6. Confidence Ring Label

### Problem
Confidence ring showed "90", "80" numbers with no context. User didn't know what they meant.

### Fix
Added "%" suffix to ring text: `{Math.round(pct * 100)}%`

---

## 7. Status at Session End

| Component | Status |
|-----------|--------|
| HF Space | Running — backend live |
| Document preview | Shows all pages stacked |
| Text extraction | Covers 10000 chars across all pages |
| Visual extraction | Gemini Vision, one page per call, up to 4 pages |
| Career timeline / soft skills | Pending verification after last fix (`1906f10`) |
| Confidence ring | Shows "%" suffix |

## Pending / Next Steps

- [ ] Re-test resume upload — verify career timeline and soft skills now extracted
- [ ] LLM Fine-tuning Pipeline (next on real-world use cases shortlist)
- [ ] Time Series Forecasting
- [ ] Multimodal RAG

---

## Key Lessons

1. **Always check HF Space secrets before assuming an API key is set** — presence of a package in requirements.txt does NOT mean the key is configured
2. **Sending large base64 images in bulk to Gemini silently times out** — send one page at a time
3. **SSE large events split across chunks** — always buffer with `buf += decode(..., {stream: true})` and `buf.split("\n"); buf = lines.pop()`
4. **Stuck HF build queue** — "Build Queued" with no log output for >10 min = factory reset immediately
