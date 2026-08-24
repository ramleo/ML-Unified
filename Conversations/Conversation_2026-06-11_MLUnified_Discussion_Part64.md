# Conversation — 2026-06-11 — ML-Unified — Feature Discussion — Part 64

---

## Session Summary

Three discussion topics: duplicate rows display, resume-worthy project ideas, and login feature consideration.

---

## Topic 1 — Display Duplicate Entries in Clean & Export

**Question:** Is it possible to display the actual duplicate rows when "6 found" is shown?

**Answer:** Yes — feasible. The backend already has the duplicate rows in memory during EDA analysis. Plan:
- Add `duplicate_rows` field to the EDA analysis response
- Frontend renders a collapsible section under "6 found" showing the actual rows
- Helps the user make an informed decision about whether to remove them

**Status:** Not implemented yet — identified as a worthwhile improvement.

---

## Topic 2 — Resume-Worthy AI/ML Project Ideas

**Context:** User wants real use cases to showcase on resume.

### High-priority (most resume impact)

| Project / Feature | Why it matters |
|---|---|
| **RAG (Retrieval-Augmented Generation)** | Extremely hot; shows LLM + vector DB knowledge |
| **Automated retraining pipeline** | End-to-end MLOps loop — very impressive |
| **Drift alerting (email/Slack)** | Real MLOps pattern used in production |

### Medium priority

| Project / Feature | Why it matters |
|---|---|
| **AutoML pipeline** | Auto-try RF/XGBoost/LightGBM, pick best by CV — shows model selection thinking |
| **Model versioning + rollback** | Standard MLOps; shows production reliability thinking |
| **Time series forecasting** | Adds Prophet/ARIMA/LSTM; widely used in finance/ops |
| **Batch predictions (#21)** | Already planned; genuine production use case |
| **LLM-assisted feature suggestion** | After EDA, LLM suggests feature engineering — classical ML + LLMs combo |

### CI/CD additions

| Addition | Why it matters |
|---|---|
| **Model quality gate in CI** | CI fails if retrained model accuracy drops below baseline — ML discipline |

---

## Topic 3 — Login Feature

**Question:** Should a login/authentication feature be added?

**Recommendation: Skip full login, or defer it.**

**Arguments for:**
- Shows full-stack thinking
- Enables per-user model history and saved datasets
- JWT + OAuth (Google login) is a recognized production pattern

**Arguments against (for a portfolio):**
- Gates the demo — recruiters want to click and immediately see ML features, not create an account
- Auth boilerplate doesn't showcase ML/MLOps skills (every web app has it)
- Adds significant complexity: sessions, token refresh, password reset, email verification
- Render free tier complicates persistent user data storage

**Alternative suggestion:** Demo mode vs. API key mode — app works freely as a demo, but a user can enter an API key to unlock saving models and history. Shows multi-tenancy thinking without building a full auth system.

**Bottom line:** RAG, automated retraining, drift alerting will impress ML/AI interviewers far more than a login page. Auth is table stakes; those features are differentiators.

---

## Topic 4 — Dockerizing Timing

**Question:** Should Dockerizing be done last, after all upgrades?

**Answer: Yes — correct instinct.**

- Docker adds consistency but doesn't change functionality
- Iterating fast with `uvicorn` directly is faster during active development
- One natural trigger: when E2E tests are added to CI, Docker makes the CI setup cleaner
- **Suggested order:** finish features → E2E tests in CI → Dockerize → final polish

---

## Commit Log (recent)

| Hash | Description | Pushed |
|------|-------------|--------|
| `8c2b116` | fix(clean): replace emoji with SVGs in Clean & Export header, show filename prominently | Yes |
| `0bf7a89` | fix(clean): split imputation by type, progress bar on submit, add ml-eda to CI | Yes |
| `429544b` | test(e2e): add Playwright E2E suite — 13 tests across inference, drift, home, clean | Yes |

---

## Pending

| # | Item | Status |
|---|------|--------|
| **Action** | Add `RENDER_EDA_DEPLOY_HOOK_URL` to GitHub Secrets | Still needed |
| **Improvement** | Show duplicate rows in collapsible section | Identified, not started |
| **#22** | Dockerize full app | Do last |
| **#21** | Batch predict | Deferred |
| **#5** | Proxy page | Deferred |
