# Conversation — 2026-06-17 — ML-Unified — Part 93

---

## Session Summary

Continued from Part 92. Fixed HF Space (wrong upload path + stale .pyc cache). Switched portfolio backend to HF Space (Render pipeline minutes exhausted). Built 5 major features: ML model toggle, custom LLM endpoint, model_comparison chart, animated progress bar, user API key input. Currently mid-implementation with TSC pending.

---

## Completed & Committed This Session

| Hash | Repo | Description |
|---|---|---|
| `ac7b4f4` | ml-portfolio | LLM dropdown + platform-independent URL |
| `6360ecb` | ml-portfolio | Progress bar starts at 8% (visible immediately) |
| `c154c48` | ML-Unified | Extra Trees + improved LLM prompt + Mixtral |

HF Space: app.py from c154c48 uploaded, factory rebooted, confirmed live.
GROQ_API_KEY added to HF Space secrets by user.
NEXT_PUBLIC_ML_UNIFIED_URL = https://wram1708-ml-unified.hf.space set in Vercel.

---

## Uncommitted Changes (IN PROGRESS)

### ml-portfolio `src/components/modals/AutoMLModal.tsx`

All changes made but **TSC not yet run, not committed**:

**Types added:**
```ts
type LLMProvider = "gemini-2.5" | "anthropic" | "openai" | "groq" | "groq-mixtral" | "custom";
type ModelComparisonItem = { algorithm: string; fitness_score: number; reason: string };
type ActionableInsight   = { title: string; detail: string };
// Explanation type updated to include model_comparison? and actionable_insights?
```

**LLM_PROVIDERS updated:**
- Added `{ value: "groq-mixtral", label: "Mixtral 8x7B (Groq)" }`
- Added `{ value: "custom", label: "Custom (OpenAI-compatible)" }`

**New state:**
```ts
const [llmProgress, setLlmProgress]       = useState(0);
const [userApiKey, setUserApiKey]         = useState("");
const [showKeyInput, setShowKeyInput]     = useState(false);
const [customLLMUrl, setCustomLLMUrl]     = useState("");
const [customLLMModel, setCustomLLMModel] = useState("");
const ALL_ML_MODELS = ["Random Forest","XGBoost","LightGBM","CatBoost","Extra Trees"] as const;
const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set(ALL_ML_MODELS));
const toggleModel = useCallback((m: string) => { ... }, []);
```

**handleTrain:** passes `selected_models: JSON.stringify([...selectedModels])` in FormData

**handleGenerateAnalysis:** 
- Starts `llmProgress` at 8, animates via setInterval
- Sends `user_api_key`, `custom_base_url`, `custom_model` if set
- Sets `llmProgress(100)` on success

**New subcomponent `ModelComparisonChart`:**
- Sorts by fitness_score desc
- Colour-coded bars: green ≥80, yellow ≥60, red <60
- Shows reason text under each bar

**Config step UI additions:**
- "Models to compete" pill toggles (all 5 checked by default, minimum 1)

**Training step:** shows only `[...selectedModels]` cards, dynamic grid columns

**AI Analysis box additions:**
- "Own key" toggle button
- When `showKeyInput || llmProvider === "custom"`: shows API key input
- When `llmProvider === "custom"`: additionally shows base URL + model name inputs
- Animated progress bar (8% → 85% random increments → 100% on done)
- `ModelComparisonChart` rendered when `llmExp.model_comparison` exists
- Actionable insights cards rendered when `llmExp.actionable_insights` exists
- `score_analysis` text shown alongside `why_won`

### ML-Unified `services/ml-api/app.py`

Also **not yet committed** (additional changes on top of c154c48):

**`/train` endpoint:**
- New param: `selected_models: str = Form('["Random Forest","XGBoost","LightGBM","CatBoost","Extra Trees"]')`
- Parsed to `_selected_models` set early in handler
- Classification + regression CV loops wrapped with `if "ModelName" in _selected_models`
- Progress steps dynamic based on model index

**`_llm_explanation`:**
- New params: `custom_base_url: str = ""`, `custom_model: str = ""`
- "custom" provider branch: uses `openai.OpenAI(api_key=key or "none", base_url=custom_base_url)` with `custom_model`

**`/explain` endpoint:**
- Reads `custom_base_url` and `custom_model` from body
- Passes them to `_llm_explanation`

---

## Next Steps (resume here after compact)

1. **Run TSC** on ml-portfolio: `cd ml-portfolio && npx tsc --noEmit`
2. **Commit** AutoMLModal.tsx → `git push origin main`
3. **Commit** app.py → `git push origin main`
4. **Upload** root app.py to HF Space:
```python
from huggingface_hub import HfApi
api = HfApi(token='<REDACTED_HF_TOKEN>')
api.upload_file(
    path_or_fileobj='/Users/wrks/Downloads/Claude-documentation/Projects/ML-Unified/services/ml-api/app.py',
    path_in_repo='app.py',
    repo_id='wram1708/ml-unified',
    repo_type='space',
    commit_message='feat: ML model selection + custom LLM endpoint',
)
api.restart_space(repo_id='wram1708/ml-unified', factory_reboot=True)
```
5. Wait for Space to come back up and test

---

## Architecture Notes

### HF Space deploy process (permanent — git push broken due to .pkl files)
```python
from huggingface_hub import HfApi
api = HfApi(token='<REDACTED_HF_TOKEN>')
api.upload_file(path_or_fileobj='services/ml-api/app.py', path_in_repo='app.py',
                repo_id='wram1708/ml-unified', repo_type='space', commit_message='...')
api.restart_space(repo_id='wram1708/ml-unified', factory_reboot=True)
```

### Custom LLM flow
- User selects "Custom (OpenAI-compatible)" in dropdown
- Inputs appear: API key + base URL + model name
- Frontend sends `{ provider: "custom", user_api_key, custom_base_url, custom_model }`
- Backend uses `openai.OpenAI(api_key=key, base_url=custom_base_url)` with `custom_model`
- Works with: Ollama, LM Studio, Together AI, Fireworks, any OpenAI-compatible endpoint

### ML model selection flow
- User toggles models in config step (pill buttons, min 1)
- Frontend sends `selected_models: '["XGBoost","CatBoost"]'` in FormData
- Backend parses to set, wraps each CV block with `if "ModelName" in _selected_models`

---

## Pending Items (Longer Term)

### ml-portfolio — Steps 3-4
- Step 3: Remaining 6 card modals (Preprocessing, Feature Eng, Feature Select, Optuna, SHAP, Ensemble)
- Step 4: Pipeline builder UI

### ML-Unified — Queued
- Fix `showAutoMLWizard()` — always start fresh (line ~4566)
- Phase 9: Ensemble / stacking
- Phase 10–13: Pipeline export, Encoding, GPU, SMOTE
- Retrain 80 Cereals model

---

## Process Reminders
- NO EMOJIS ever
- Always report short git hash with every commit
- Always push to GitHub after every commit
- HF Space: upload root app.py via Python SDK (git push blocked by .pkl files)
- Playwright: maximize window (1440x900), close after deploy confirmation
