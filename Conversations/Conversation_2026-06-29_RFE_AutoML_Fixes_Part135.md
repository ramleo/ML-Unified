# Conversation — 2026-06-29 | RFE Fix + AutoML Chain + Card Reorder | Part 135

## Session Overview

Follow-up to Part 134. Applied 3 pending fixes and also addressed FE auto-load UX issue.

---

## Commits This Session

| Hash | Repo | Message |
|---|---|---|
| `2d6f228` | ml-portfolio | fix(fs): RFE NaN early-break; store fsCsvB64 after run; move AutoML card to step 4 |

All frontend only — no HF Space upload required.

---

## Bug Fixes Applied

### Fix 1 — RFE keeps exactly N features (not N+1)

**Root cause:** In `src/lib/fsMain.ts` RFE loop, `miScore()` returns `NaN` for features with zero-variance or failed MI computation. `NaN < Infinity === false` in JavaScript, so `minName` stayed empty for those features, causing `if (!minName) break` to fire early — leaving more features than requested.

**Fix:**
```typescript
// Before
const score = mi * (1 - 0.35 * avgR);
if (score < minScore) { minScore = score; minName = col.name; }

// After
const raw = mi * (1 - 0.35 * (isFinite(avgR) ? avgR : 0));
const score = isFinite(raw) ? raw : 0;
if (score < minScore) { minScore = score; minName = col.name; }
```
NaN scores now treated as 0 → always valid candidates for removal → loop runs to target count.

### Fix 2 — fsCsvB64 stored in context after FS run

**Root cause:** FS page only stored `selectedFeatures` (column name list) after worker result. Never encoded `result.csvText` as base64, so AutoML couldn't auto-load it.

**Fix** in `src/app/tools/feature-selection/page.tsx`:
```typescript
const fsCsvB64 = btoa(unescape(encodeURIComponent(sr.csvText)));
setState(prev => ({ ...prev, selectedFeatures: kept, fsCsvB64 }));
```
Now the full CSV chain works: Preprocessing → FE → FS → AutoML.

### Fix 3 — AutoML card position in capabilities grid

**Root cause:** `src/data/capabilities.ts` had AutoML at slot 2, before FE and FS.

**Fix:** Moved AutoML to slot 4. New order:
```
1. Preprocessing
2. Feature Engineering
3. Feature Selection
4. AutoML         ← moved here
5. Optuna
6. SHAP
7. Ensemble
```

---

## Other Fixes (earlier in session, committed as a83aebf and 3da3626)

### FE/FS Banner UX — "Use this data →" button

**Problem:** FE page showed "Using preprocessed data" banner + upload zone simultaneously. Silent background auto-load gave no feedback if it failed.

**Fix:** Replaced silent `useEffect` auto-load with explicit `loadFromContext()` function triggered by a **"Use this data →"** button in the banner. Shows spinner while parsing, clears when step advances to "configure". Same fix applied to FS page.

Files: `src/components/CsvFromContextBanner.tsx` (added `onUseData`, `loading` props), FE page, FS page.

### Groq AI Suggest 401 error message

**Problem:** FS page "AI Suggest Methods" showed raw `401: {"error":{"message":"Invalid API Key"...}}`.

**Root cause:** `GROQ_API_KEY` in Vercel env is invalid/expired. NOT a code bug.

**Fix:** `callOpenAICompat` in `/api/ai-tools/route.ts` now returns friendly messages on 401/429.

**To fully fix:** Regenerate GROQ_API_KEY at console.groq.com and update in Vercel dashboard → Project Settings → Environment Variables.

---

## Full CSV Chain — End-to-End Status

```
User uploads CSV → Preprocessing → FE → FS → AutoML → Optuna / SHAP / Ensemble
                        ↓             ↓      ↓      ↓
                 preprocessedCsvB64  feCsvB64 fsCsvB64  (model results: automlWinner, tunedModel, shapValues)
                   all stored in MLPipelineState (localStorage-safe base64 strings)
```

**UX per page:**
- FE: banner "Using preprocessed data — N rows × M cols" + **"Use this data →"** button
- FS: same banner (uses feCsvB64 ?? preprocessedCsvB64)
- AutoML: silently injects CSV from context chain when modal opens (no banner yet)
- Optuna/SHAP/Ensemble: pre-select model from `automlWinner`/`automlRanking`

**Missing (AutoML banner):** AutoML upload zone still shows empty — no CsvFromContextBanner added there. Context CSV IS loaded internally when modal opens, but not visible to user. This is a known gap.

---

## Pending Items

| # | Item | Notes |
|---|------|-------|
| AutoML banner | Show "Using FS data" banner in AutoML upload zone | Same pattern as FE/FS |
| GROQ_API_KEY | Update in Vercel env vars | Key expired — regenerate at console.groq.com |
| #24 | RAG-enhanced AI explanation | Not started |
| #33 | Categorical drift frequencies | Not started |
| #45 | E2E Playwright CI | Suite exists locally, not wired |

