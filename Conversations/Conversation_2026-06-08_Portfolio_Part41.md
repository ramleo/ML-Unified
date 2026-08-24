# Conversation — 2026-06-08 | Pipeline Mode + UI Redesign (Part 41)

**Date:** 2026-06-08
**Projects:** ML-Unified (Render)
**Continued from:** Part 40

---

## Commits This Session

| Hash | Repo | Summary |
|---|---|---|
| `8ca1cf8` | ML-Unified | Add Pipeline mode — visual sklearn pipeline inspector |
| `04099a5` | ML-Unified | Redesign Pipeline view + fix card visibility in light theme |
| `cb86070` | ML-Unified | Redesign ML Unified predict section to match AIRaML editorial style |
| `b47b54e` | ML-Unified | Align EDA and Vision sections to AIRaML design system |

---

## Clarifications

### "AIRaML" reference
User referred to "airaml" — confirmed via conversation history that this is the portfolio brand name **AIRaML** (ml-portfolio, Vercel). All design decisions for ML Unified should match the AIRaML design language.

### Pipeline lazy-loading explained
- Fetches `/pipeline/{model_id}` only on first click of "Pipeline" tab
- Rendered HTML cached in DOM (`dataset.loaded = '1'`), no re-fetch on tab toggle
- `renderMain()` rebuilds entire `#main` on model switch → pipeline div destroyed → resets naturally for next model

### Title tooltip already present
User asked to add `title` tooltip to SHAP label elements — confirmed it was already added in Part 40 (`title="${f.label}"` on `.shap-feat-name`).

### Design sync status (Part 36 confirmed)
All AIRaML design elements were synced to ML Unified as of Part 36:
dark theme, gradient top bar, glassmorphism, gradient text, Geist font, neural network logo, favicon, colored accent bars, particles, ambient blobs, SVG icons.

---

## Feature: #7 Build Pipeline Mode

### Backend — `routers/pipeline.py`
New file. `GET /pipeline/{model_id}` introspects the sklearn Pipeline at runtime.

Returns:
```json
{
  "model_id": "diabetes",
  "title": "...",
  "task": "classification",
  "input_fields": ["Pregnancies", "Glucose (mg/dL)", ...],
  "steps": [
    {
      "kind": "preprocessor",
      "type": "ColumnTransformer",
      "label": "Column Transformer",
      "transformers": [
        {
          "name": "num",
          "columns": ["Pregnancies", "Glucose (mg/dL)", ...],
          "steps": [
            {"type": "SimpleImputer", "label": "Imputer", "params": {"strategy": "median"}},
            {"type": "StandardScaler", "label": "Standard Scaler", "params": {"with_mean": "True", "with_std": "True"}}
          ]
        }
      ]
    },
    {
      "kind": "estimator",
      "type": "RandomForestClassifier",
      "label": "Random Forest",
      "params": {"n_estimators": "100", "max_depth": "None", ...}
    }
  ]
}
```

Key helpers: `_key_params()` (returns important hyperparams per estimator type), `_describe_step()`, `_describe_transformer()`. Circular import avoided via `from app import MODELS` inside route function.

Mounted in `app.py`:
```python
from routers import pipeline as _pipeline_router
app.include_router(_pipeline_router.router)
```

### Frontend — Pipeline tab + flow diagram

**Tabs:** "Predict | Pipeline" added to model header as underline-style nav tabs.

**Flow diagram:** Timeline layout — numbered circle badges (1 → 2 → 3) connected by vertical accent-colored line. Each step is a card with 3px left accent bar:
- Step 1: Input — feature chips in accent color
- Step 2: Preprocessing — ColumnTransformer with sub-cards per branch (NUM/CAT), showing column chips + step dots + params
- Step 3: Estimator — type label + key hyperparameter pills

All colors follow `var(--active-accent)` — green for Diabetes, sky blue for Titanic, etc.

Lazy-loads on first click, cached per model, resets on model switch.

---

## Light Theme Opacity Fixes

Root cause: Many elements used `bg-glass` (60% transparent white in light mode) and hardcoded `rgba(0,0,0,0.3)` shadows — invisible/washed out on light background.

**Fixed (`04099a5`):**
| Element | Before | After |
|---|---|---|
| `model-header` | `bg-glass` + `rgba(0,0,0,0.3)` shadow | `bg-card` + `var(--shadow)` |
| `result-state` | `bg-glass` + hardcoded shadow | `bg-card` + `var(--shadow)` |
| `shap-panel` | `bg-glass` + `rgba(0,0,0,0.2)` shadow | `bg-card` + `var(--shadow)` |
| `empty-state` | `bg-glass` + `1px dashed border2` | `bg-card` + `1.5px dashed border2` |

---

## AIRaML Design Alignment Redesign

### Problem identified (user comparison)
AIRaML portfolio: content flows directly on background, large editorial typography, no card-in-card nesting, restrained color usage.

ML Unified predict section: model title trapped in white card, form fields inconsistently outside card, ALL-CAPS form labels, dashed-border empty state card, tabs as pill buttons — "web form from 2015" aesthetic.

### Root cause of section inconsistency
Three sections built at different times:
- **Predict** (most recent): uses `var(--bg-card)` + `var(--shadow)`
- **EDA** (older): hardcoded `rgba(255,255,255,0.02)` + `#34d399` accent throughout
- **Vision** (older): hardcoded `#38bdf8` for confidence, specific rgba backgrounds

EDA/Vision fixes done later this session — see section below.

### Predict redesign applied (`cb86070`)

| Element | Before | After |
|---|---|---|
| Model header | White card floating on gray bg | Open section, content on background |
| Title | 1.5rem inside a box | 2rem, owns the page |
| Task badge | Rounded pill with accent fill | Small uppercase eyebrow (task · model type) in accent color |
| Metric | Separate pill card | Plain large number + label, right-aligned |
| Tabs | Bordered button pills | Underline nav (border-bottom on active) |
| Field labels | ALL-CAPS + letter-spacing | Sentence case |
| Fill Sample btn | ⚡ emoji | SVG icon, color follows `var(--active-accent)` |
| Empty state | Dashed border card with shadow | Icon + text on background, `opacity: 0.75` |
| Section label | None | "Inputs" eyebrow above form grid |

---

## EDA + Vision Design Alignment (`b47b54e`)

### Root cause identified
Three sections built at different times with different design systems — EDA used dark glassmorphism + hardcoded `#34d399`, Vision used hardcoded `#38bdf8`, Predict was recently modernised. All three sections share sidebar/navbar but main content felt like different apps.

### Changes applied

**All 6 panel headers** — colored `u-dot` circle replaced with `model-eyebrow` text:
- `Vision · Image Classification`, `Vision · Image Processing`, `Vision · Object Detection`, `Vision · Image Segmentation`
- `Data Tools · Exploratory Analysis`
- `Unsupervised Analysis · Clustering` (and Density Clustering, Visualization, Dimensionality Reduction)
- `u-title` bumped from `1.2rem` to `1.8rem` editorial scale

**Double padding removed** — `eda-panel`/`u-panel`/`vision-panel` had own `padding:1.5rem` inside `.main` which already has `2rem`; panels now `padding:0`, headers use `padding-top:2rem`

**EDA section cards** — dark glassmorphism (`rgba(255,255,255,0.03)` + inset shadows) → `var(--bg-card)` + `var(--border2)` + `var(--shadow)` — same system as predict section

**EDA nav tabs** — hardcoded `#34d399` → `color-mix(in srgb, var(--active-accent) …)` — follows palette

**EDA section title accent bar** — hardcoded gradient `#34d399→#38bdf8` → `var(--accent-from)` to `var(--accent-via)`

**EDA tables** — `rgba(255,255,255,0.07)` borders → `var(--border)`; hover row uses `color-mix` accent

**EDA dist cards** — `rgba` glassmorphism → `var(--bg-card)` + `var(--border2)`; hover border uses `var(--accent-from)`

**Vision Object Detection** — conf slider `accent-color` and value color → `var(--active-accent,var(--accent-from))`

**`UNSUPERVISED_META`** — added `type` field to each model (`'Clustering'`, `'Density Clustering'`, `'Visualization'`, `'Dimensionality Reduction'`) for eyebrow label

**Intentionally kept (semantic identity colors):**
- EDA overview chips (rows/cols/missing/dups/quality) — semantic status colors
- `eda-type-num/cat` badges — semantic type colors
- `eda-insight-danger/warning/info` — semantic severity colors
- Vision model chip colors (purple/orange/blue/purple per section) — section identity

---

## Standing Rules (unchanged)

- Conversation logs: `ML-Iris/Conversations/Conversation_YYYY-MM-DD_Topic_PartXX.md`
- Never expose `ramleo84@gmail.com` publicly
- `vision_cache/` and `.mcp.json` must never be committed
- Always run `ruff check` + `pytest` before pushing ML-Unified
- User-facing errors: plain English only
- Every project launched from portfolio inherits active palette via `?palette=xxx`
- After commit: always push or ask to push

---

## Pending Tasks

| # | Item | Status |
|---|---|---|
| 7 | Build Pipeline mode | ✅ Done this session |
| — | EDA/Vision design alignment | ✅ Done this session |
| 8 | Prediction confidence bar chart | Next up |
| 10 | Training history / comparison | Pending |
| 11 | Cleaned CSV download | Deferred |
| 12 | EDA microservice extraction | Pending |
| 13 | 35 EDA unit tests | Pending |
| 14 | Side-by-side vision results | Pending |
| 15 | Batch predict for vision | Pending |
| 16 | Vision ambient themes | Pending |
| 17 | Mobile bottom tab bar | Pending |
| 18 | Data drift detection | Pending |
| 19 | MLflow experiment tracking | Pending |
| 20 | Playwright E2E tests | Pending |
