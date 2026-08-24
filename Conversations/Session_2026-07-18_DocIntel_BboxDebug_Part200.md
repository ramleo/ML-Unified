# Session 2026-07-18 — Document Intelligence: Bbox Fixes + Groq Daily Quota Debug (Part 200)

## Summary

Full session debugging and fixing Document Intelligence extraction and bounding box issues.

---

## Issues Found & Fixed

### 1. ITEMS bbox too narrow (only covering Widget A/B text)

**Root cause:** Tier4 `_tier4_keep` filter was excluding "$25.00" and "$50.00" as numeric noise (old filter: any string whose core was all digits after stripping `$.,` was dropped). Only "Widget A" and "Widget B" passed — so bbox only covered the description column (~8% page width).

**Fix in `_extract.py`:**
- `_tier4_keep` now only excludes very short plain integers (≤4 chars): `not (core.isdigit() and len(s) <= 4)`
- "$25.00" (len 6) passes → anchors right side of table
- Added `find_tables()` for JSON array fields — uses PyMuPDF layout-aware table detection; falls back when bbox width < 15% of page

### 2. BANK INFO bbox missing account number "12345678"

**Root cause:** Same old filter excluded all pure-digit strings including long identifiers like "12345678".

**Fix:** `_tier4_keep` allows "12345678" (len 8 > 4) → union bbox now covers "Test Bank" + "12345678" (~27% width).

### 3. ITEMS value showing "Widget A, Widget B" instead of full JSON dict

**Root cause:** Stale results from a previous browser session. Fresh upload confirmed backend returns full JSON array with confidence 1.0 and validation "ok". The `is_json` guard in `_validate.py` (from previous session) correctly prevents LLM consistency pass from overwriting JSON arrays.

### 4. 0 fields returned after many test calls

**Real cause (found via debug endpoint):** Groq daily token limit (TPD) of 100,000 tokens exhausted.
- Used: 99,684. Remaining: 316.
- Classify (~200 tokens) → works.
- Extract (~4,204 tokens) → fails with 429 `RateLimitError`.
- The 429 was swallowed by `except Exception: return ""` in `_groq()`, making it look like a code bug.
- Debug endpoint `/document/test-llm` hit the API directly without try-except → exposed the real error:
  ```
  Rate limit reached... Limit 100000, Used 99684, Requested 4204. 
  Please try again in 55m59.232s.
  ```

**Wrong diagnoses (time wasted):**
1. "It's per-minute rate limit" → wrong
2. "It's not rate limits" → wrong
3. "It's max_tokens=2000 causing JSON truncation" → wrong
4. Real cause: TPD exhausted

**Lesson saved to memory:** `feedback_debug_first.md` — When external API fails silently, add a raw debug call (no try-except) FIRST. Never state a cause without evidence.

### 5. Analyze step staying ○ (not turning green) after pipeline completes

**Root cause:** No `{step: "analyze", status: "done"}` event was emitted in `router.py`. The event was missing between the field extraction try/except block and Step 4 (self-correction loop).

**Fix:** Added `yield _sse({"step": "analyze", "status": "done"})` after the extraction except block.

---

## Files Changed

| File | Commit | Change |
|------|--------|--------|
| `services/ml-api/routers/document/_extract.py` | 81ea06a | Full bbox fix: find_tables for arrays + _tier4_keep filter |
| `services/ml-api/routers/document/_llm.py` | 9c82c29 | max_tokens 2000 → 4096; analyze:done SSE event |
| `services/ml-api/routers/document/router.py` | 9c82c29 | analyze:done SSE event added |
| `services/ml-api/routers/document/_validate.py` | 71a2090 | is_json guard (previous session) |

---

## Deployed State (HF Space `wram1708/ml-unified`)

- `_extract.py`: full bbox fix with find_tables + _tier4_keep
- `_llm.py`: max_tokens=4096
- `router.py`: analyze:done event, no debug endpoint
- `_validate.py`: is_json guard

---

## Pending Verification

Groq daily TPD quota resets ~56 minutes after the error was found. After reset:
- ITEMS bbox should be wide (covering Description through Amount columns)
- BANK INFO bbox should cover both "Test Bank" and "12345678"
- All 11 fields should extract correctly with Located badges

---

## Key Code: `_tier4_keep` in `_extract.py`

```python
def _tier4_keep(s: str) -> bool:
    """Only exclude very short plain integers (qty like 2, 10, 100)."""
    if len(s) < 3:
        return False
    core = s.lstrip("-$€£¥").replace(",", "").replace(".", "")
    return not (core.isdigit() and len(s) <= 4)
```

**Effect:**
- "Widget A" → kept (has letters)
- "$25.00" → kept (len 6 > 4)
- "12345678" → kept (len 8 > 4)
- "2", "10" → excluded (plain int ≤4 chars)
- "100" → excluded (plain int ≤4 chars)

---

## Technical Notes

- PyMuPDF `find_tables()` works well for PDFs with visible borders; returns narrow bbox for borderless text-aligned tables
- 15% page-width guard: if find_tables returns width < 15%, falls back to Tier4 value search
- `_tier4_keep` is generic — works across invoice, bank statement, PO, contract (any JSON array/object field)
- `max_tokens=4096` genuinely better for complex multi-field extraction even though it wasn't the cause of the 0-fields issue
