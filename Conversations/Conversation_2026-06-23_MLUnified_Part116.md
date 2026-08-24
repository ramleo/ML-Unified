# Conversation — Part 116
**Date:** 2026-06-23
**Projects:** ML-Unified, ml-portfolio
**Topics:** Bug fixes (Back button, page crash, Cohere, AI Explanation), pending.md updated

---

## Summary

Continuation of Part 115. Fixed all outstanding bugs from the previous session and updated the pending items tracker.

---

## Bugs Fixed

### 1. Back Button — ML-Unified AutoML Wizard (Final Fix)
- **Root cause:** Wrong step order mapping. All Back buttons were set to `_renderAutoMLStep1()` which is "AutoML: Model Selection" (the upload screen) — forcing re-upload every time.
- **Correct step order:**
  1. `_renderAutoMLStep1()` = "AutoML: Model Selection" (upload)
  2. `_renderAutoMLStep0()` = "Before we begin" (target column, dataset name)
  3. `_renderAutoMLStep1c()` = Feature Engineering
  4. `_renderAutoMLStep1b()` = Data Quality & Preprocessing
  5. `_renderAutoMLStep2()` = Run AutoML
- **Fix:**
  - Feature Engineering Back (line 5592): `_renderAutoMLStep1()` → `_renderAutoMLStep0()`
  - Data Quality & Preprocessing Back (lines 5011, 5030): `_renderAutoMLStep1()` → `_renderAutoMLStep1c()`
- **Commit:** `7afb72c` (ML-Unified), uploaded to HF Space

### 2. Page Crash — Gemini/Cohere causing "This page couldn't load" (ml-portfolio)
- **Root cause:** Schema mismatch between LLM prompt and `ModelComparisonChart`. Prompt asked for `{title, detail}` but chart expected `{algorithm, fitness_score, reason}`. `shortName(item.algorithm)` called `undefined.replace()` → TypeError crashed the React render → Chrome showed "This page couldn't load".
- **Three fixes in `808c439`:**
  1. LLM prompt updated to return `{algorithm, fitness_score (0-100), reason}` for `model_comparison`
  2. `shortName()` guarded against undefined: `(name ?? "").replace(...)`
  3. `error.tsx` added for `/tools/automl` — catches future render errors with a "Try again" button
- **Prior fix `e80230c`:** `extractJson` now normalizes all array fields via `toArr()` — prevents crash if LLM returns strings instead of arrays

### 3. Cohere Model Deprecated
- **Error:** `model 'command-r-plus' was removed on September 15, 2025`
- **Fix:** Updated UI placeholder hint from `command-r-plus` → `command-a-03-2025`
- **Commit:** `e80230c` (ml-portfolio)
- **User action required:** Type `command-a-03-2025` as the model name in the custom model field

### 4. AI Explanation Auto-Showing — ML-Unified
- **Root cause:** `ba22e35` (previous session) made `_renderExplanationDashboard()` unconditional to fix empty right panel. This caused the rule-based "WHY IT WON" text AND all charts to auto-show on training completion without user clicking anything.
- **Fix history:**
  - `83a3f89`: Pass `null` when `isAI=false` → hid WHY IT WON but still showed charts
  - User clarified: ALL content should be hidden until button clicked
  - `fab6231`: Changed to `isAI ? _renderExplanationDashboard(...) : ''` → nothing shows until "Get AI Explanation" is clicked
- **Both commits pushed to GitHub AND uploaded to HF Space**

### 5. Progress Label Showing Wrong Provider
- **Error:** When using Cohere (custom base URL), label showed "Asking Gemini 2.5 Flash..." — and vice versa after switching back
- **Root cause (first fix `75e056c`):** Label used `llmProvider` from dropdown regardless of `customLLMUrl`
- **Root cause (second bug `33a23c5`):** After fixing, stale `customLLMModel` showed even when key input was hidden
- **Final fix `33a23c5`:**
  - Label: `(showKeyInput && customLLMUrl.trim()) ? customLLMModel : providerLabel`
  - Hook: only sends `baseUrl` when `userApiKey` is also provided — prevents stale Cohere URL routing requests to wrong provider

---

## All Commits This Session

### ml-portfolio
| Commit | Description |
|--------|-------------|
| `e80230c` | normalize LLM array fields + update Cohere model hint |
| `808c439` | fix model_comparison schema mismatch — root cause of page crash |
| `75e056c` | show custom model name in progress label when using own API key |
| `33a23c5` | provider label and baseUrl only active when key input is shown |

### ML-Unified
| Commit | Description |
|--------|-------------|
| `7afb72c` | correct Back button navigation in AutoML wizard |
| `83a3f89` | suppress auto explanation text until user clicks Get AI Explanation |
| `fab6231` | hide ALL AI Explanation content until Get AI Explanation is clicked |

---

## Key Decisions / Learnings

### Back Button Root Cause
The original session summary said `_renderAutoMLStep1()` = "Upload". It is actually "AutoML: Model Selection" (the full upload + config screen). This misnaming caused multiple wrong fixes across sessions. Always verify by grepping for the actual heading text inside the function.

### "This page couldn't load" in Chrome
Not always a network error. Can be caused by an uncaught TypeError in React's render phase crashing the JavaScript runtime at the tab level. In this case: `shortName(undefined)` → `undefined.replace()` during `ModelComparisonChart` render.

### Custom Provider Routing
When `showKeyInput` is hidden but `customLLMUrl` has a stale value in state, the hook was silently routing to the wrong provider. Fix: gate `baseUrl` on both `customLLMUrl.trim()` AND `userApiKey.trim()` being non-empty.

---

## Pending Items Updated

File: `Conversations/pending.md`

Newly ticked off:
- **#1** One-hot encoding ✅ (user confirmed)
- **#2** Target encoding ✅ (user confirmed)
- **#3** Transform presets ✅ (user confirmed)
- **#34** Persistent drift buffer ✅ (verified in `routers/drift.py` — done in Part 45)
- **#48** Cleaned CSV download ✅ (user confirmed)

Previously ticked (Part 115):
- **#14** "Use my API key" UX ✅
- **#35** Gemini 2.5 Flash ✅
- **#36** Groq model IDs ✅
- **#38** Render model persistence ✅ (moot — Render removed)

**Total: 9 done / 52 items**
