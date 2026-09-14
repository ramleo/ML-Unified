# ML-Unified Conversation Log

---

## Part 49 — 2026-06-10

### Completed
- **UI elegance pass — branch `ui-elegance`** (all changes isolated, `main` untouched, rollback = delete branch)
  - **6 themes** added: Dark (existing), Light (improved), Midnight (black + purple/pink), Ocean (navy + cyan), Sunset (warm dark + orange), Forest (dark green + emerald)
  - **Theme picker dropdown** in navbar — replaces old single toggle button; shows color swatches per theme, persists to localStorage
  - **Semantic CSS variables** added: `--color-success/warning/danger/info` + `*-bg` variants, all theme-aware
  - **Hardcoded colors replaced** in CSS: drift badges, SHAP bars, EDA insights, batch cards, wizard done-step, EDA type chips, EDA chip-dups — all now use `var(--color-*)` 
  - **Confidence bars** — gradient fill, pill shape (9999px radius)
  - **Card polish** — unified border-radius to 16px, improved padding/spacing on result + SHAP panels, wider SHAP feature name column (160px)
  - **Light theme** — improved contrast and border values

- **Iris SHAP all-zeros diagnosed** — `LinearExplainer` given `X_prep` as background; SHAP = deviation from itself = 0. Fix: use `np.zeros_like(X_prep)` as background. **Not yet applied** (user asked to save first).

### Still To Do on `ui-elegance` Branch
- JS template literals in EDA/drift still use some hardcoded hex strings inside `${}` — need JS-side fix
- Vision module chips still use hardcoded `#e879f9` purple
- Preview on Render: change deploy branch to `ui-elegance` in Render dashboard to test live

### Pending
- **Iris SHAP zeros fix** — `shap.LinearExplainer(model, np.zeros_like(X_prep))` in `services/ml-api/routers/shap.py`
- **Merge `ui-elegance` → `main`** after user approves
- **#22** Dockerize full application
- **#20** Playwright E2E tests

### Deferred
- #19 MLflow — skipped
- #11 Cleaned CSV download — until use case defined
- #21 Batch predict for Object Detection + Segmentation

---

## Part 48 — 2026-06-10

### Completed
- **CSS shimmer** on SSE progress bar fill — white sweep animation via `::after` pseudo-element on `.sse-progress-fill`
- **ml-vision retry bug fixed** — `return` was outside `except` in both detect-objects and segment-image workers; model loaded then exited without running inference on first call; users needed 2-3 retries. Fixed by indenting `return` inside `except`. User confirmed resolved.
- **Training metrics expanded**
  - Classifiers: Accuracy (main) + F1 weighted + ROC-AUC chips
  - Regressors: MAE (main) + RMSE chip (R² dropped — looks bad on Insurance dataset)
- **EDA tests** — 35 tests already existed in `services/ml-eda/tests/test_eda.py`; all 35 passing in 1.24s
- **SHAP fix for Iris** — pre-built Iris pipeline uses `LogisticRegression`, not Random Forest. `TreeExplainer` only works for tree models → was silently failing. Added `LinearExplainer` fallback in `services/ml-api/routers/shap.py`. Corrected `iris.json` schema label from "Random Forest" → "Logistic Regression".
- **MLflow** — decided to skip. Local file-based has no user-visible benefit; remote server costs money.

### Bugs Found / Diagnosed (not yet fixed)
- **Iris Feature Impact all zeros** — `LinearExplainer` receives `X_prep` as background; SHAP = deviation from itself = 0 by definition.
  - **Fix:** In `_compute()` in `services/ml-api/routers/shap.py`, change:
    ```python
    explainer = shap.LinearExplainer(model, X_prep)
    ```
    to:
    ```python
    explainer = shap.LinearExplainer(model, np.zeros_like(X_prep))
    ```

### Pending
- **#22** Dockerize full application (ml-api + ml-eda + ml-vision)
- **#20** Playwright E2E tests
- **UI elegance pass** — user shared screenshot of Iris predict result (confidence bars + Feature Impact panel); wants it more elegant. Clarify what specifically to change at next session.

### Deferred
- #19 MLflow — skipped
- #11 Cleaned CSV download — until use case defined
- #21 Batch predict for Object Detection + Segmentation

---

## Part 47 — 2026-06-09

### Completed
- SSE streaming for ml-vision `/detect-objects` and `/segment-image` (5 stages each)
- `color_segmentation` stays plain JSON (too fast to need streaming)
- 2s keepalive heartbeat in `shared/progress.py` (both ml-api and ml-vision) to prevent Render proxy timeout
- Fixed ruff E702 violations (semicolon-separated `p.finish()/return`)
- Fixed drift NaN bug — `_is_number()` now rejects `float('nan')` and `float('inf')`; NaN rows counted as `null_rate` instead of crashing `json.dumps`
- #12 EDA microservice — fully live (Render service + ML_EDA_URL env var)
