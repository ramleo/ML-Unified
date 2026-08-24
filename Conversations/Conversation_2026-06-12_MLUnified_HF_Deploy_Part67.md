# Conversation — 2026-06-12 — ML-Unified — HF Deployment + UI Fixes — Part 67

---

## Session Summary

Handled Render pipeline minute limit, migrated to HuggingFace Spaces deployment, fixed AutoML UI, fixed drift high-cardinality bug, and started navbar redesign.

---

## Deployment: Render Pipeline Minutes Exhausted

- **Problem**: Render blocked all deploys (manual + auto) — 502/500 pipeline minutes used
- **Billing reset**: July 1, 2026
- **Solution**: Migrated to HuggingFace Spaces (free, no pipeline minute concept)
- **HF Space URL**: https://huggingface.co/spaces/wram1708/ml-unified

---

## HuggingFace Spaces Setup

### Steps taken
1. Created HF account + Space (Docker, Blank template)
2. Added `services/ml-api/README.md` with HF Space metadata (`sdk: docker`, `app_port: 8000`)
3. Used `git subtree push` → rejected (binary pkl files in history)
4. Used `git push hf $(git subtree split ...)` → rejected (XET storage required for binaries)
5. Cloned HF Space to `/tmp/hf-space`, used `rsync` excluding `*.pkl` to copy files
6. Uploaded pkl files separately via `huggingface_hub.upload_file()` to XET storage
7. Installed `git-lfs` via homebrew for future reference

### Key workflow for future HF pushes
```bash
rsync -a --exclude='models/*.pkl' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.venv' --exclude='data/*.json' \
  /Users/wrks/Downloads/Claude-documentation/Projects/ML-Unified/services/ml-api/ /tmp/hf-space/
cd /tmp/hf-space && git add -A && git commit -m "..." && git pull --rebase && git push
```

### HF remote in main repo
```bash
git remote add hf https://wram1708:<REDACTED_HF_TOKEN>@huggingface.co/spaces/wram1708/ml-unified
```

### pkl files — uploaded via huggingface_hub
7 files uploaded to XET storage:
- `models/diabetes_pipeline.pkl` (416 KB)
- `models/diabetes_labels.pkl`
- `models/iris_pipeline.pkl` (3 KB)
- `models/iris_labels.pkl`
- `models/titanic_pipeline.pkl` (127 KB)
- `models/titanic_labels.pkl`
- `models/insurance_pipeline.pkl` (879 KB)

---

## Errors & Fixes During HF Setup

| Error | Cause | Fix |
|-------|-------|-----|
| `fatal: could not read Username` | No HF auth on remote URL | Added token to remote URL |
| `remote rejected — binary files` | pkl files in git history | Cloned separately, rsync excluding pkl |
| `ERROR: failed to calculate checksum of /models` | `COPY models/ models/` with empty dir | Changed to `RUN mkdir -p models` initially |
| `FileNotFoundError: diabetes_pipeline.pkl` | XET files not in Docker build context | Tried various approaches (see below) |
| `SUPERVISED MODELS` empty in sidebar | Same pkl loading issue | Under investigation |

### pkl loading saga
1. `COPY models/ models/` → failed (empty dir)
2. `RUN mkdir -p models` + uploaded to XET → app starts but no models (XET not in build context)
3. `start.sh` with `hf_hub_download` at startup → didn't work
4. Back to `COPY models/ models/` → under investigation

### Graceful startup fix (`1caf6c9`)
```python
# In _load():
pkl_path = os.path.join(MODEL_DIR, f"{mid}_pipeline.pkl")
if not os.path.exists(pkl_path):
    continue  # skip missing models instead of crashing
pipeline = joblib.load(pkl_path)
```

---

## AutoML Dashboard Redesign (`79a8eb8`)

Replaced simple bar cards with full dashboard layout.

### New layout
```
┌─────────────────────────────────────────────────────────┐
│  [Trophy] Well Suited For Your Data                     │
│           LightGBM                          75.2%       │
│           Outperformed XGB & RF · Class [Imbal·F1]     │
├──────────┬──────────┬──────────────────────────────────┤
│  WINNER  │  DATASET │  MODELS TESTED                   │
│  LightGBM│  889     │  3                               │
│  Classif │  rows·3CV│  RF · XGB · LGB                  │
├──────────┴──────────┴──────────────────────────────────┤
│  Algorithm Comparison  │  Feature Importance           │
│  [32px tall bars]      │  [ranked with circles]        │
│  RF   WINNER [=====]   │  1 sugars   49.7% [=======]  │
│  XGB        [====]     │  2 calories 24.6% [====]      │
│  LGB        [==]       │  ...                          │
├────────────────────────────────────────────────────────┤
│  [Brain] Why LightGBM won              [AUTO]          │
│  Explanation text...                                   │
│  [API key input] [Get AI Explanation]                  │
└────────────────────────────────────────────────────────┘
```

### Key CSS classes added
- `.aml-dashboard` — wrapper with `margin-top: 1.5rem`, top border separator
- `.aml-hero` — accent-gradient tinted banner
- `.aml-hero-label` — "Well Suited For Your Data" (changed from "Best Algorithm")
- `.aml-stats` — 3-column stat tiles
- `.aml-charts` — 2-column chart grid
- `.aml-algo-row` — 32px tall algorithm bars with WINNER pill
- `.aml-feat-row` — ranked feature importance with numbered circles
- `.aml-exp-card` — explanation card with brain SVG icon
- `.aml-imbal-tag` — amber pill tag inline in hero subtitle (replaced full-width banner)

### Imbalanced note fix (`559880a`)
Replaced full-width yellow banner between buttons and hero with a small amber inline pill in the hero subtitle:
```
"Outperformed XGBoost & LightGBM on 3-fold CV · Classification [IMBALANCED · F1-MACRO]"
```

---

## Predict Section — Confidence Bars Redesign (`5cc9f2e`)

### Before
- 8px thin bars
- Simple flat layout

### After
- 22px tall bars with `box-shadow: inset` track
- Card wrapper with header: "Confidence / probability per class"
- Divider lines between class rows
- Winner row gets accent-tinted background
- Non-winner bars: `rgba(255,255,255,0.08)` fill

### New CSS
```css
.proba-section { border: 1px solid var(--border2); border-radius: 14px; overflow: hidden; }
.proba-section-header { padding: 0.75rem 1rem; border-bottom: 1px solid var(--border2); }
.proba-rows { display: flex; flex-direction: column; }
.proba-row { padding: 0.7rem 1rem; border-bottom: 1px solid var(--border2); }
.proba-bar-wrap { height: 22px; border-radius: 8px; box-shadow: inset 0 1px 2px rgba(0,0,0,0.2); }
```

### SHAP bars upgrade
- Height: 10px → 16px
- Track: subtle `rgba(255,255,255,0.03)` background with border-radius
- Smoother cubic-bezier transition

---

## Drift — High Cardinality Fix (`b259f8e`)

### Problem
Columns like "Ticket", "Name", "PassengerId" had 500+ unique values — each shown as a separate 0% bar in drift analysis.

### Fix — Backend (`routers/drift.py`)
```python
# In _process_categorical():
if n_opts > 20:
    vals = [str(r[name]) for r in rows if name in r and r[name] is not None]
    return {
        "name": name, "label": field.get("label", name),
        "type": "categorical", "high_cardinality": True,
        "n_opts": n_opts, "n_unique_recent": len(set(vals)),
        "drift_score": 0.0, "drift_level": "low",
        "psi": 0.0, "psi_level": "low", "null_rate": 0.0,
    }
```

### Fix — Frontend (`index.html`)
```javascript
} else if (f.high_cardinality) {
  return `<div class="drift-feature">
    ${topRow}
    <div class="drift-cat-note" style="margin-top:0.6rem;font-style:normal;color:var(--text2)">
      High-cardinality column — <strong>${f.n_opts}</strong> unique values in training,
      <strong>${f.n_unique_recent}</strong> in recent data. Per-value drift not shown.
    </div>
  </div>`;
}
```

---

## Navbar Redesign — IN PROGRESS (not committed)

### Change applied locally but NOT pushed
Local edit to `index.html` CSS:
- `.nav` height: 56px → 60px, padding: 0 1.75rem, subtle accent-tinted background
- `.nav-logo-mark` size: 30px → 34px, border-radius: 8px → 10px, stronger glow
- `.nav-title` font-size: 0.95rem → 1rem, tighter letter-spacing
- `.theme-picker-btn` border-radius: 8px → 9999px (pill shape), accent-tinted bg + border

**Status**: Committed and pushed — `efdf337` (GitHub), `33d7551` (HF Space).

---

## All Commits This Session

| Hash | Description | Where |
|------|-------------|-------|
| `c645939` | chore(deploy): add HuggingFace Spaces metadata | GitHub |
| `3a01044` | chore(deploy): track pkl files with Git LFS | GitHub |
| `0944781` | fix(docker): create empty models dir instead of COPY | GitHub |
| `1caf6c9` | fix(startup): skip missing pkl files in _load() | GitHub |
| `79a8eb8` | feat(automl): redesign report as full dashboard | GitHub |
| `559880a` | fix(automl): replace imbalanced banner with inline pill | GitHub |
| `5cc9f2e` | fix(ui): AutoML spacing + label; taller confidence + SHAP bars | GitHub |
| `b259f8e` | fix(drift): skip per-value bars for high-cardinality categoricals | GitHub |
| `efdf337` | feat(navbar): accent-tinted bg, larger logo mark, pill theme picker, refined spacing | GitHub |
| HF `7a0b453` | fix(hf): revert to COPY models/ approach | HF only |
| HF `33d7551` | feat(navbar): accent-tinted bg, larger logo mark, pill theme picker | HF only |
| `b1abc79` | fix(hf): download pkl files from XET storage at startup on HuggingFace Spaces | GitHub |
| HF `7f48d51` | fix(hf): download pkl files from XET storage at startup | HF only |
| `dc0bd98` | fix(navbar): plain white title font, remove gradient top bar | GitHub |
| HF `6794f5b` | fix(navbar): plain white title font, remove gradient top bar | HF only |
| `9e211e2` | fix(navbar): reduce background opacity to 60% | GitHub |
| HF `4f21150` | fix(navbar): reduce background opacity to 60% | HF only |
| `5b35fb8` | feat(automl): Phase 1 — SHAP + What-If tabs in AutoML results page | GitHub |
| HF `8fa618b` | feat(automl): Phase 1 — SHAP + What-If tabs | HF only |
| `28dbd30` | feat(automl): two-column results layout — summary left, dashboard+tabs right | GitHub |
| HF `6b2276c` | feat(automl): two-column results layout | HF only |
| `27510db` | feat(automl): training info in left card, full-width breadcrumb, auto-scroll | GitHub |
| HF `884596e` | feat(automl): training info in left card, full-width breadcrumb, auto-scroll | HF only |
| `91d70ea` | feat(automl): 3-col layout with sticky SHAP/What-If panel, fix scroll + SHAP errors | GitHub |
| HF `06335b7` | feat(automl): 3-col layout + SHAP/What-If panel | HF only |
| `dfe2525` | fix(automl): compact SHAP row grid for 280px side panel | GitHub |
| HF `e90c128` | fix(automl): compact SHAP row grid | HF only |
| `3d1b9d0` | fix(shap): add check_additivity=False — TreeExplainer additivity error | GitHub |
| HF `6e95e60` | fix(shap): check_additivity=False | HF only |
| `a2f50ac` | fix(automl+shap): 2-col layout, SHAP/What-If at bottom, RF SHAP fallback | GitHub |
| HF `fdbf06c` | fix(automl+shap): 2-col layout, SHAP/What-If at bottom, RF SHAP fallback | HF only |
| `565accb` | fix(automl): remove sticky from summary card; add sidebar section dividers | GitHub |
| HF `870c7ca` | fix(automl): remove sticky from summary card; sidebar section dividers | HF only |
| `dfb17d6` | fix(ui): navbar opacity 35%, theme picker font matches title, sidebar padding | GitHub |
| HF `4d92ce0` | fix(ui): navbar opacity 35%, theme picker font, sidebar padding | HF only |
| `ce295d2` | fix(sidebar): consistent section spacing, remove conflicting inline margins | GitHub |
| HF `963983a` | fix(sidebar): consistent section spacing | HF only |
| `424d544` | fix(sidebar): more breathing room — increase item padding, restore section dividers | GitHub |
| HF `925d063` | fix(sidebar): more breathing room | HF only |
| `9783f61` | fix(sidebar): increase gap between items to 0.5rem | GitHub |
| HF `0a2bc45` | fix(sidebar): increase gap to 0.5rem | HF only |
| `2a474a0` | fix(sidebar): increase gap to 0.65rem | GitHub |
| HF `1063cf1` | fix(sidebar): increase gap to 0.65rem | HF only |
| `126d6c2` | fix(sidebar): restore original spacing — gap 0.4rem, original label/btn padding | GitHub |
| HF `47b3f6c` | fix(sidebar): restore original spacing | HF only |
| `7e1a0bf` | fix(sidebar): taller items — 1.1rem padding, larger fonts, more gap | GitHub |
| HF `6308449` | fix(sidebar): taller items | HF only |
| `0149bfe` | fix(sidebar): increase item height to 1.4rem padding | GitHub |
| HF `b3647ca` | fix(sidebar): increase item height to 1.4rem padding | HF only |
| `557b2a7` | feat(automl): multi-provider AI explanation — Anthropic, OpenAI, Gemini | GitHub |
| HF `7da4432` | feat(automl): multi-provider AI explanation | HF only |
| `2102b23` | fix(automl): update Gemini model to gemini-2.0-flash | GitHub |
| HF `5bb195a` | fix(automl): Gemini 2.0 flash | HF only |
| `6c44c04` | fix(automl): update Gemini model to gemini-3.5-flash | GitHub |
| HF `f03f574` | fix(automl): Gemini 3.5 flash | HF only |
| `25066db` | feat(automl): structured 4-section AI explanation with rich prompt + markdown rendering | GitHub |
| HF `62d26b1` | feat(automl): structured 4-section AI explanation | HF only |
| `1a2d84d` | fix(automl): keep key row after explanation — allow regenerate; fix AI badge | GitHub |
| HF `5b7e30d` | fix(automl): keep key row, allow regenerate, fix AI badge | HF only |
| `af5fb74` | feat(automl): add Gemini 2.5 Flash and Groq (Llama-3.3-70b) as providers | GitHub |
| HF `e9e5f9f` | feat(automl): Gemini 2.5 Flash + Groq providers | HF only |
| `e8844dc` | feat(automl): animated progress bar for AI explanation | GitHub |
| HF `cf8fe95` | feat(automl): animated progress bar | HF only |
| `7326c46` | feat(automl): Phase 2 — Train with AutoML button in Clean & Export | GitHub |
| HF `d07c863` | feat(automl): Phase 2 — Train with AutoML from Clean & Export | HF only |
| `f35d07f` | fix(automl): reset progress bar to 0 instantly on Regenerate | GitHub |
| HF `69a6367` | fix(automl): reset progress bar on Regenerate | HF only |
| `8c84133` | fix(automl): Enter key in API key input triggers Get AI Explanation | GitHub |
| HF `67e4bc5` | fix(automl): Enter key triggers Get AI Explanation | HF only |
| `45b4341` | fix(automl): show AI error message only after progress bar hides | GitHub |
| HF `3dcee99` | fix(automl): show AI error after progress bar hides | HF only |

---

## AutoML Unified Workflow — Phase 1 Complete

Phase 1 implemented: After AutoML training, the results page now shows:
- **Left**: Summary card (model name, winner, primary metric, extra metrics, Use Model button, Training Info section)
- **Right**: Full dashboard (hero, stats, algo comparison, feature importance, AI explanation) + SHAP Analysis / What-If tabs at bottom
- `activeModel` is auto-set after training so SHAP and What-If work immediately without navigating away
- SHAP uses `check_additivity=False` + `feature_perturbation='interventional'` fallback for Random Forest

---

## AutoML Unified Workflow — Phase 2 Complete

- **"Train with AutoML →"** button appears in Clean & Export success summary after cleaning
- Clicking it passes the cleaned CSV directly into AutoML — skips Step 1 upload, jumps to Step 2 (Configure)
- `_lastCleanedFile` stores the File object; `_launchAutoMLFromClean()` sets `automlFile` and calls `_analyzeAutoMLCSV()` directly
- Works for both clean paths (EDA-style and column-specific)

## AI Explanation Improvements

- **5 providers**: Anthropic (claude-haiku-4-5), OpenAI (gpt-4o-mini), Gemini 3.5 Flash, Gemini 2.5 Flash, Groq (llama-3.3-70b-versatile via OpenAI-compatible endpoint)
- **Structured 4-section prompt**: Why [Model] Won / What the Scores Tell Us / Key Drivers / Recommendations — `max_tokens` 800
- **Markdown rendering**: `**Section**` → styled uppercase label headers
- **Key row stays visible** after explanation — button changes to "Regenerate" / "Try Again"
- **AI badge** only shown when `source === 'user_key'` (real LLM response)
- **Animated progress bar** with phase labels (Sending context → Model is thinking → Generating → Almost done)
- **Enter key** triggers Get AI Explanation from the key input
- **Error message** shown only after progress bar hides (after 1200ms), not during
- **Regenerate** resets bar to 0% instantly (no visible 100→0 jump)

---

## Pending / Next Steps

| Item | Status |
|------|--------|
| Navbar redesign + polish | Done — `dfb17d6` / HF `4d92ce0` |
| Supervised models loading on HF | Done — `b1abc79` startup download via hf_hub_download |
| Render deploy | Blocked until July 1 pipeline reset |
| **AutoML Unified Workflow** | Phases 1 & 2 done |
| → Phase 3: Drift with data versioning | Not started — V1 = training baseline; V2+ = prev vs. new batch |
| → Phase 4: RAG-enhanced AI explanation | Not started |
| Model versioning + rollback | Not started |
| Drift alerting (email/Slack) | Not started |
| LLM-assisted feature suggestions | Not started |
| Automated retraining pipeline | Not started |
| Time series forecasting | Not started |
| #21 Batch predictions | Deferred |
| #5 Proxy page | Deferred |
| #22 Dockerize (full) | Do last |

---

## HF Space Notes

- **Two Dockerfiles**: HF Space (`COPY models/ models/`) vs GitHub main (`RUN mkdir -p models`)
- **HF push workflow**: Always `rsync` from `services/ml-api/` to `/tmp/hf-space/`, then commit + `git pull --rebase` + push
- **HF token**: `<REDACTED_HF_TOKEN>` (Write access)
- **XET storage**: pkl files uploaded via `huggingface_hub.upload_file()` — NOT in regular git
- **Render reset**: July 1, 2026 — all GitHub commits will auto-deploy then
