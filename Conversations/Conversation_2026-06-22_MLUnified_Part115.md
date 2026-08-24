# Conversation — Part 115
**Date:** 2026-06-22  
**Projects:** ML-Unified, ml-portfolio  
**Topics:** HF Space deployment, platform independence, Groq/Gemini fixes, AutoML UX

---

## Summary

Continuation of Part 114. Resolved multiple deployment, LLM, and navigation issues across ML-Unified (HF Space) and ml-portfolio (Vercel).

---

## Issues Resolved

### 1. HF Space — Training Stuck at 93%
- **Root cause:** `p.finish()` was called AFTER `_upload_model_to_hf()` which blocked the SSE stream until HF upload completed. Proxy timed out.
- **Fix:** Call `p.finish(result=resp)` first, then run upload in a daemon thread.
- **Commit:** `1a06bfd` (ML-Unified)

### 2. ML-Unified Right Panel Empty
- **Root cause:** `_renderExplanationDashboard()` was gated behind `isAI = true`. Charts never rendered without LLM.
- **Fix:** Always call `_renderExplanationDashboard()` regardless of LLM source.
- **Commit:** `ba22e35` (ML-Unified)

### 3. HF Space Push Rejected (Binary .pkl Files)
- **Root cause:** HF Space rejects git pushes containing `.pkl` binary files.
- **Fix:** Used `huggingface_hub` Python API to upload only changed text files directly, bypassing git.
- **Files uploaded:** `app.py`, `requirements.txt`, `frontend/index.html`

### 4. Gemini 2.5 Flash — Raw JSON in AI Analysis
- **Root cause:** `maxTokens: 1200` was too small for the 6-field JSON response. Gemini truncated the output, `extractJson` failed, raw text was shown.
- **Fix:** Increased to `maxTokens: 3000` in `useAutoMLExplain.ts`.
- **Commits:** `809b110`, then `b9d0f9a` (ml-portfolio)

### 5. LLM Errors Not Shown to User
- **Root cause:** `llmError` was piped into top-level `error` state shown only on Steps 1-3, never on Step 4 (Results).
- **Fix:** Added `llmError` prop to `Step4Results.tsx` with inline red error banner.
- **Commit:** `dac77f6` (ml-portfolio)

### 6. Groq Model IDs Outdated
- **Old:** `llama3-70b-8192`, `llama3-8b-8192`
- **New:** `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`
- **Files updated:** `useAutoMLExplain.ts`, `automlUtils.ts`, `ToolsAIChat.tsx`, `chat/route.ts`, `app.py`
- **Commits:** `37b0f80` (ml-portfolio), `79950a0` (ML-Unified)

### 7. ML-Unified Launch App → Render (Hardcoded URL)
- **Root cause:** `registry.json` had 3 hardcoded `onrender.com` URLs for Launch App buttons.
- **Fix:** Updated all 3 to `https://wram1708-ml-unified.hf.space`.
- **Commit:** `28eb210` (ml-portfolio)

---

## Architecture Decisions

### Platform Independence (Major Discussion)

**Problem:** App was split across Render (ML backend), HF Space (ML-Unified UI), Vercel (ml-portfolio) — fragile, Render cold starts, push rejections.

**Solution implemented:**
- **Level 2** (already done): Single env var `NEXT_PUBLIC_ML_UNIFIED_URL` in `src/config/urls.ts` controls all backend calls
- **Level 3**: Switched from Render → HF Space as the single ML backend
- **Vercel env var updated:** `NEXT_PUBLIC_ML_UNIFIED_URL = https://wram1708-ml-unified.hf.space`
- **Render eliminated** from the picture

### Dockerfile Hardened
Added to `services/ml-api/Dockerfile`:
- Non-root user (`appuser`) — required by Fly.io/Railway
- `EXPOSE ${PORT:-8000}`
- `HEALTHCHECK` pointing to `/health`
- `.dockerignore` created
- **Commit:** `d2b365a` (ML-Unified)

**Why Docker matters:** Makes `app.py` portable to any Level 3 platform (Fly.io, Railway, DigitalOcean) with zero code changes — just point `NEXT_PUBLIC_ML_UNIFIED_URL` at the new host.

---

## Features Added

### Dynamic "Use My API Key" Flow
**Before:** Entering any key with a provider in dropdown → key validated against that provider only.  
**After:** User can use ANY OpenAI-compatible provider by entering:
1. Their API key
2. Provider base URL (e.g. `https://api.cohere.com/compatibility/v1`)
3. Model name (e.g. `command-r-plus`)

**Changes:**
- `route.ts`: Accept `baseUrl` from request body; if present, call `callOpenAICompat(baseUrl, key, model)` directly — bypasses provider lookup entirely
- `useAutoMLExplain.ts`: Send `customLLMUrl` as `baseUrl` for any provider when filled
- `Step4Results.tsx`: Show Base URL field whenever "Use my API key" is active
- `callOpenAICompat`: Now accepts `maxTokens` and `jsonMode` params (was hardcoded 800 tokens, no JSON mode)
- **Commits:** `9ece6cc`, `4291134`, `b9d0f9a` (ml-portfolio)

### Removed "Custom (OpenAI-compatible)" Dropdown Option
Now redundant — covered by the dynamic base URL flow on any provider selection.
- **Commit:** `31ced38` (ml-portfolio)

---

## Bug Fixes

### AutoML Back Button (ML-Unified)
- **Root cause:** Multiple Back buttons throughout the AutoML wizard were navigating to wrong steps — some going forward in the flow.
- **Fix:** All Back buttons now return to `_renderAutoMLStep1()` (Upload screen) for consistent navigation.
  - Line 5592 (Feature Engineering): was `_renderAutoMLStep1b` → now `_renderAutoMLStep1`
  - Lines 5011, 5030 (Preprocessing config): was `_renderAutoMLStep0` → now `_renderAutoMLStep1`
- **Commits:** `8273625`, `7f73d0f`, `9e9d176` (ML-Unified)
- **HF Space uploads:** Multiple direct uploads via `huggingface_hub` API

### extractJson Hardened
- Handles double-encoded JSON (Gemini sometimes wraps JSON in a string)
- Strips markdown fences before bracket-depth extraction
- **Commit:** `dac77f6` (ml-portfolio)

---

## Commits This Session

### ml-portfolio
| Commit | Description |
|--------|-------------|
| `dac77f6` | Surface LLM errors in results view + robust JSON extraction |
| `809b110` | maxTokens 1200→2000 |
| `5b14f33` | .env.example → HF Space default, Render removed |
| `28eb210` | registry.json URLs → HF Space + maxTokens 2000→3000 |
| `37b0f80` | Groq model IDs updated |
| `9ece6cc` | Dynamic Use my API key — any OpenAI-compat provider |
| `31ced38` | Remove Custom dropdown, model field Required hint |
| `4291134` | Use custom model override when base URL provided |
| `b9d0f9a` | callOpenAICompat: pass maxTokens + jsonMode |

### ML-Unified
| Commit | Description |
|--------|-------------|
| `d2b365a` | Dockerfile hardened (non-root, EXPOSE, HEALTHCHECK, .dockerignore) |
| `79950a0` | Groq model IDs updated |
| `8273625` | Back button fix attempt 1 |
| `7f73d0f` | Back button fix attempt 2 |
| `9e9d176` | All Back buttons → Upload step (final fix) |

---

## Key Concepts Discussed

### Levels of Platform Independence
- **Level 1:** One backend instead of two (consolidate Render + HF Space → just HF Space)
- **Level 2:** Single env var controls backend URL — swap platforms without code changes (already implemented)
- **Level 3:** Choice of hosting platform (HF Space is valid Level 3; Fly.io/Railway for always-on)

### Why Docker
- Makes app portable across Level 3 platforms
- Pins OS + dependencies — no "works locally, breaks on server"
- HF Space already uses Docker internally (you just don't control the Dockerfile)
- Write once, deploy anywhere

### ngrok
- Runs local `app.py` accessible via public URL
- Great for development (instant updates, no deploy wait)
- Not suitable for production (Mac must stay on)

---

## Pending / Known Issues
- HF Space free tier still sleeps after inactivity (cold start problem not eliminated, just moved from Render)
- Upgrade to HF Pro ($9/mo) for always-on
- Cohere integration tested but may need further validation with correct API endpoint
