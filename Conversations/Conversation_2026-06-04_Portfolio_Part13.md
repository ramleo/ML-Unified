# Conversation – 2026-06-04 (Part 13): XGBoost/LightGBM/CatBoost + MCP Setup

---

## What Was Done This Session

---

### 1. Added XGBoost, LightGBM, CatBoost as Algorithm Options (commit `e927cba`)

**Repo:** `github.com/ramleo/ML-Unified`

**Files changed:**
- `requirements.txt` — added `xgboost`, `lightgbm`, `catboost`
- `app.py` — imports added; classification and regression branches extended
- `frontend/index.html` — `algorithmOptions()` updated for classification and regression

**Backend estimator selection (classification):**
```python
if algorithm == "XGBoost":
    estimator = XGBClassifier(n_estimators=100, random_state=42, eval_metric="logloss", verbosity=0)
elif algorithm == "LightGBM":
    estimator = LGBMClassifier(n_estimators=100, random_state=42, verbose=-1)
elif algorithm == "CatBoost":
    estimator = CatBoostClassifier(iterations=100, random_seed=42, verbose=0)
elif algorithm == "Random Forest":
    estimator = RandomForestClassifier(n_estimators=100, random_state=42)
else:
    estimator = GradientBoostingClassifier(n_estimators=100, random_state=42)
```

Same pattern for regression (XGBRegressor, LGBMRegressor, CatBoostRegressor).

**Frontend dropdown now shows:**
- Classification: Random Forest, Gradient Boosting, XGBoost, LightGBM, CatBoost
- Regression: Gradient Boosting, Random Forest, XGBoost, LightGBM, CatBoost

**License notes:** XGBoost (Apache 2.0), LightGBM (MIT), CatBoost (Apache 2.0) — all commercial-friendly.

---

### 2. Fixed DBSCAN 0-Cluster Issue + PCA Label (commit `cf1e001`)

**Root cause:** Numeric features were not being scaled before DBSCAN. With raw feature values (e.g. 100, 5000, 0.3), eps=0.5 is effectively zero — all points become noise.

**Fix:** Added `StandardScaler` to the numeric preprocessing pipeline in `/unsupervised`:
```python
transformers.append(("num", Pipeline([
    ("imp", SimpleImputer(strategy="median")),
    ("scaler", StandardScaler()),
]), num_cols))
```

After scaling, eps=0.5 means "half a standard deviation" — sensible for any dataset. K-Means and t-SNE/PCA also benefit.

**PCA label fix:** Changed "Dimensions" → "n_components — components to extract" with options 2 and 3, so users understand it controls how many PCA components are extracted.

---

### 3. MCP Servers Set Up for Both Repos

**What MCP is:** Model Context Protocol — lets Claude connect to external tools (filesystem, browser, GitHub) as first-class integrations within a Claude Code session.

**Files created:**
- `ml-portfolio/.mcp.json`
- `ML-Unified/.mcp.json`

Both files contain:
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "<repo-path>"]
    },
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "<PAT>"
      }
    }
  }
}
```

**`.mcp.json` added to `.gitignore`** in both repos — PAT is never committed to GitHub.

**Activation:** Run `claude` inside each project folder → one-time prompt "3 new MCP servers found in .mcp.json" → press Enter to confirm all three. Done for ML-Unified; ml-portfolio pending.

**What each server enables:**

| Server | Benefit |
|---|---|
| filesystem | Claude reads project files directly without user needing to confirm each read |
| playwright | Claude can screenshot the live Render app to verify UI changes itself |
| github | Claude can check deploys, read PRs, inspect CI status |

---

## Commits (ML-Unified)

| Hash | Description |
|---|---|
| `e927cba` | Add XGBoost, LightGBM, CatBoost as algorithm options for classification and regression |
| `cf1e001` | Fix DBSCAN 0-cluster issue: add StandardScaler; label PCA n_components clearly |

---

## Pending (Next Session)

- ⬜ Confirm MCP servers in ml-portfolio (run `claude` → `/mcp` → approve)
- ⬜ `image-classification` task type — CNN, image file upload
- ⬜ Data drift / model drift detection (Point 13)
- ⬜ MLflow experiment tracking (Point 14)
- ⬜ Monitoring — Grafana + Prometheus (Point 12)
- ⬜ CI test-gate (Point 17)
- ⬜ E2E browser testing — Playwright (Point 18)

---

## Standing Rules

- Apply changes to ALL affected repos simultaneously
- Conversation logs stored in `ML-Iris/Conversations/` folder
- Light theme: ALL elements must adapt
- Vercel = portfolio only (ML-Portfolio repo); Render = ML app (ML-Unified repo)
- ML-Portfolio → Vercel auto-deploy on push to main
- ML-Unified → Render auto-deploy on push to main (~3–5 min free tier)
- pkl files trained with scikit-learn==1.8.0 — keep pinned
- Unsupervised analysis: always dataset-in → visualization-out, no saved model
- `.mcp.json` must never be committed — always in `.gitignore`
