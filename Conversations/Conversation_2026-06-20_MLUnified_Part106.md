# Conversation — 2026-06-20 — ML-Unified — Part 106

---

## Topics Covered

1. AI Chatbot added to all tool pages (ToolsAIChat component)
2. Multi-provider LLM support (Gemini, Claude, OpenAI, Groq, Together, Mistral, Perplexity)
3. LLM-powered AI Suggest in Feature Engineering
4. Various bug fixes (503/429 error messages, JSON parsing, emojis removed)
5. Feature Engineering UI fixes (Clear all button, cyclical/row-agg descriptions)
6. AutoML Step 4 badge fix
7. Feature Selection improvements discussion

---

## 1. AI Chatbot — All Tool Pages

**Commit `52a6e30`** — ml-portfolio — *feat: add AI chatbot and LLM-powered AI Suggest to all tool pages*

### New files
- `/src/app/api/ai-tools/route.ts` — Next.js API route handling all LLM providers
- `/src/components/ToolsAIChat.tsx` — Floating bubble chat component, shared across all tool pages

### Providers supported
| Provider | Format | Models |
|---|---|---|
| Gemini (default) | Native | gemini-2.5-flash, gemini-3.5-flash |
| Claude | Native | claude-haiku-4-5, claude-sonnet-4-6 |
| OpenAI | OpenAI-compat | gpt-4o-mini, gpt-4o |
| Groq | OpenAI-compat | llama3-70b, llama3-8b, mixtral, gemma2 |
| Together AI | OpenAI-compat | Llama 3 70B, Mixtral, Qwen 2 72B |
| Mistral | OpenAI-compat | mistral-small, mistral-large |
| Perplexity | OpenAI-compat | sonar, sonar-pro |

### Component behaviour
- Floating bubble fixed bottom-right, z-index above all content
- Click to open/close chat panel (360×520px overlay, no layout shift)
- Gear icon opens settings: provider chips, model dropdown, optional API key input
- API key stored in `localStorage` only — never persisted server-side
- If user key is empty, server-side env var key is used as default
- 3 starter prompt suggestions shown when chat is empty
- Enter sends, Shift+Enter newline
- Dataset context passed as prop from each tool page (column names, stats, current state)

### Pages wired
- Feature Engineering — numeric/categorical columns, skew, missing%, active transforms, result
- Data Preprocessing — rows, columns, missing values, before/after stats
- Feature Selection — features, target, kept/dropped counts
- AutoML — static context describing the wizard
- SHAP — static context describing SHAP explainability
- Optuna — static context describing TPE hyperparameter tuning
- Ensemble — static context describing ensemble/stacking

### System prompt design
- If dataset loaded: forces LLM to reference specific column names and statistics
- If no dataset: answers conceptually, suggests uploading CSV
- 3–6 sentence limit, always names which column(s) a suggestion applies to

---

## 2. LLM-Powered AI Suggest

**Commits `52a6e30`, `d8cb98b`**

### Before
Rule-based heuristics: skew > 1.5 → log1p, missing% > 2% → missing_flag, IQR outlier% > 3% → winsor.

### After
Sends column stats (name, skew, missing%, min, max, mean, Q1, Q3) to the LLM via `/api/ai-tools`. LLM returns a JSON object `{ colName: [transforms] }`. Result applied directly to chip state.

### JSON extraction — 3-strategy fallback
1. Direct `JSON.parse(raw)`
2. Strip ` ```json``` ` markdown fences, then parse
3. Regex `\{[\s\S]*\}`, then parse

### Error handling
- `data.error` from server shown directly (not "Could not parse")
- If all 3 parse strategies fail: shows first 80 chars of raw reply for debugging
- Button shows "Analysing..." while loading, disabled during request
- Error displayed in red below button, cleared on next click

### Prompt
```
Output a single raw JSON object — no markdown, no code fences, no explanation.
Keys are column names, values are arrays of transform keys from this list: ...
```

---

## 3. Gemini Error Handling

**Commits `ae9588f`, `d42208e`**

### Error messages by status
| Status | Message shown |
|---|---|
| 429 | "Rate limit reached — Gemini free tier allows only a few requests per minute. Wait a moment and try again, or switch to Groq (free, higher limits) in chat settings." |
| 503 (first hit) | Auto-retries with gemini-3.5-flash silently |
| 503 (retry also fails) | "Both Gemini models are currently overloaded. Switch to Groq or Claude in chat settings." |
| 401/403 | "Invalid or unauthorized Gemini API key. Check your key in chat settings." |
| Other | Parses `error.message` from Gemini JSON response |

### 429 explanation
Gemini free tier = 10 RPM (requests per minute). Not a daily/total quota — resets every minute. Even a few rapid messages can trigger it. Same key shared with homepage chatbot counts toward the same limit. Groq free tier = 30 RPM.

---

## 4. Feature Engineering UI Fixes

| Commit | Change |
|---|---|
| `460dec4` | Expanded cyclical/row-aggregate descriptions |
| `2f53eb0` | Added dataset usage examples to both sections |
| `e46a9aa` | Removed inline transform legend, tooltip on each chip instead |
| `fc881c0` | Gemini models updated (removed deprecated 1.5 Pro/Flash, added 3.5 Flash); all emojis removed; AI Suggest error visible |
| `aede43d` | Added "Clear all" button next to "AI Suggest" in Numeric Column Transforms header |

### Gemini models (current)
- gemini-2.5-flash (default)
- gemini-3.5-flash (model ID: `gemini-3.5-flash`, 1M token context, faster)

### Clear all button
- Ghost style, sits left of "AI Suggest"
- Calls `setColTransforms({})` and clears any error message

---

## 5. AutoML Badge Fix

**Commit `83ac8a6`**

AutoML page showed "ML Capabilities" badge in purple — inconsistent with pipeline sequence. Changed to "Step 4" in green (`#22c55e`) matching Feature Selection's "Step 3" in orange.

---

## 6. Feature Selection — Improvements Discussed (Not Yet Implemented)

### UX improvements
- Auto-run on settings change (debounced ~300ms)
- Live feature count on each method tab
- Correlation pairs in drop reasons (show which feature + r value)
- Variance values in ranking table
- Method comparison view (which methods kept/dropped each feature)
- Target type auto-detection (binary 0/1 → auto-set classification)

### New FS techniques to add (user approved all)
**Wrapper methods:**
- Forward Selection
- Exhaustive search (feasible <15 features)

**Filter methods:**
- Chi-squared test (categorical features vs categorical target)
- Kendall's tau (rank correlation, robust for non-linear monotonic)

**Embedded methods:**
- Lasso (L1) — shrinks weak features to zero
- Ridge (L2) — penalizes weak/collinear features
- Tree feature importance (Random Forest / XGBoost split gain)

**Dimensionality reduction:**
- PCA (uncorrelated components by variance explained)
- UMAP (non-linear, better for visualisation)

---

## 7. Commits This Session

| Hash | Repo | Description |
|---|---|---|
| `460dec4` | ml-portfolio | feat: expand cyclical/row-agg descriptions |
| `2f53eb0` | ml-portfolio | feat: add dataset usage examples to descriptions |
| `e46a9aa` | ml-portfolio | feat: replace transform legend with hover tooltips |
| `52a6e30` | ml-portfolio | feat: AI chatbot + LLM AI Suggest on all tool pages |
| `fc881c0` | ml-portfolio | fix: Gemini models, no emojis, visible AI Suggest errors |
| `1bcce8d` | ml-portfolio | fix: column-specific answers, 503 retry, error fields |
| `ae9588f` | ml-portfolio | fix: parse Gemini error JSON into readable messages |
| `d42208e` | ml-portfolio | fix: accurate 429/503 messages, correct retry behaviour |
| `d8cb98b` | ml-portfolio | fix: robust JSON extraction for AI Suggest |
| `aede43d` | ml-portfolio | feat: Clear all button in numeric transforms header |
| `83ac8a6` | ml-portfolio | fix: AutoML badge Step 4 green |

---

## 8. Pending

### Feature Selection (ml-portfolio) — next session
- All new FS techniques: Forward Selection, Exhaustive, Chi-squared, Kendall's tau, Lasso, Ridge, Tree importance, PCA, UMAP
- UX improvements listed in section 6

### ML-Unified backlog
- Phase 9: Ensemble/stacking
- Phase 10: Pipeline export (.pkl / Python script)
- Fix `showAutoMLWizard()` always starting fresh (~line 4566 in app.py)
- Verify AdaBoost winner-training branch in app.py
- Retrain 80 Cereals model
